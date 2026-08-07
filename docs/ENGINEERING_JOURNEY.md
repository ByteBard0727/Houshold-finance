# Engineering Journey

This document records how I architected and evolved this project, including the technical hardships I overcame along the way. It covers work that predates the current Codex-assisted implementation and draws on my own history of the project as well as the repository, deployment artifacts, and architecture reviews.

## 1. Starting point: a spreadsheet-backed dashboard

I began the project as a household expense dashboard centered on a shared Google workbook. Each month is a worksheet such as `Aug2026`; rows represent days and columns represent categories including food, leisure, utilities, automatic withdrawals, SMBC payments, and household items.

I used Django to import the workbook into a flat PostgreSQL table and serve Chart.js endpoints. Google Sheets was already operationally important, but I had not yet made that architectural boundary explicit. Docker Compose proposed local PostgreSQL, Redis, Nginx, and Daphne while Django settings pointed to Supabase. Upload routes were incomplete, migration history was fragmented, configuration was inconsistent, and the frontend still contained theme-demo sections.

My most important early decision was therefore not a technology choice but a contract:

> Google Sheets is the authoritative ledger. PostgreSQL is a synchronized projection for the dashboard.

That decision prevented a risky bidirectional rewrite and gave me a stable boundary for every later change.

## 2. Hosting experiments on a rooted Honor 8

I wanted the application to run on my existing Honor 8 rather than a paid cloud server. To achieve that, I rooted the phone and built a server environment inside Termux on Android 7.

I experimented with Docker and Podman artifacts, a local PostgreSQL data directory, Redis, ngrok, and native service scripts. Those experiments exposed the gap between Android and a conventional Linux server:

- no systemd;
- no normal `/etc/os-release` environment;
- no `/dev/net/tun` device;
- SELinux and Android application sandboxing;
- Huawei background-process management;
- native ARM package and wheel availability;
- storage and memory pressure from containers and local database services;
- version transitions that can strand an existing PostgreSQL data directory.

I deliberately reduced the phone’s responsibility in the final deployment:

- Daphne and Django run natively in a Termux virtual environment.
- Redis runs locally for Channels.
- Supabase hosts PostgreSQL, avoiding a local database server in the critical path.
- Google hosts Sheets, Apps Script, and Gemini.
- Tailscale provides networking.

This was not “Docker failed, therefore abandon deployment.” I decomposed the stack according to what the hardware could run reliably.

## 3. Rebuilding the Android Python environment

The old phone checkout contained extensive local modifications on top of a single early Git commit. Rather than overwrite it, I cloned a clean deployment checkout alongside it and preserved the legacy tree for recovery.

Termux itself contained mixed package generations. I performed a controlled distribution upgrade that moved the phone to Python 3.14, Redis 8, PostgreSQL 18 tooling, and current OpenSSH packages while preserving existing configuration. I created the deployment virtual environment with access to Termux system packages so I could reuse expensive native components such as Pillow and cryptography.

Several Python packages still had to compile on ARM64/Android. I removed pandas, NumPy usage, and django-pandas from the synchronization runtime, replacing DataFrame transformations with dictionaries and `datetime`. This reduced build risk, memory use, and startup weight while preserving synchronization behavior.

## 4. Stabilizing the legacy dashboard

The dashboard initially contained date-format inconsistencies, assumptions about fixed total rows, stale/future worksheets, selectors that did not update the area chart, and layout inherited from a Bootstrap admin theme.

My work included:

- parsing Sheet dates such as `2026/2/12`;
- respecting the actual highest `PK_Unique` total row per worksheet;
- keeping future worksheet templates from becoming the initial month;
- making month selection update area-chart data;
- showing the current month first;
- sharing one category response between progress bars and the pie chart;
- moving the pie chart beside the breakdown;
- replacing demo navigation and “generate report” controls with real receipt navigation;
- removing search, badges, template-user names, color-system demos, illustration demos, and sidebar marketing copy;
- adding a restrained dark mode suitable for a real household tool.

I preserved the existing projection architecture rather than using the receipt feature as an excuse to rewrite the dashboard.

## 5. Building receipt processing in safe phases

### Phase 1: upload foundation

I replaced a broken upload route with a mobile-first image upload. I designed a `Receipt` model to store UUID-addressed pipeline state, images, extracted JSON, confirmed JSON, errors, and timestamps. Uploaded files are decoded rather than trusted by extension, size-limited, and stored outside static assets.

### Phase 2: Gemini extraction

I placed Gemini behind a service boundary rather than calling it from views. It receives image bytes and returns structured JSON for store, Japan-local date, integer yen total, category, and best-effort items. Provider errors become controlled receipt states instead of request crashes.

One real configuration bug was especially instructive: settings loaded `.env` through `python-decouple` and were later overwritten with empty `os.getenv()` values. I standardized configuration loading and fixed a misleading “Gemini is not configured” failure.

### Phase 3: editable confirmation

I designed extraction so that it never commits money. A dedicated confirmation page lets the user correct every meaningful field, stores reviewed data separately, and uses explicit state transitions plus post/redirect/get behavior.

### Phase 4: idempotent Google Sheets write-back

I designed Apps Script to derive the monthly worksheet from the confirmed date, find the real date row, and increment both the chosen category and daily total. It does not append transactions, overwrite cells, use `PK_Unique` to locate dates, or modify the projection directly.

Receipt UUID state in Script Properties provides idempotency:

```text
unknown UUID → pending → write cells → synced
synced UUID retry → acknowledge without another increment
ambiguous pending UUID → stop for reconciliation
```

The conservative pending state prioritizes avoiding duplicate household expenses over automatic recovery.

## 6. Replacing ngrok with Tailscale

I initially used rotating ngrok URLs for external access. That created configuration churn for Apps Script and exposed too much of the application.

Tailscale on the Honor 8 was not a standard installation:

- Android 7/Termux had no TUN device.
- Static ARM64 Tailscale binaries were installed.
- `tailscaled` runs with `--tun=userspace-networking` and a Termux socket.
- Termux:Boot starts the daemon after reboot.

HTTPS required additional diagnosis. The daemon initially queried `::1:53`, where no resolver existed, and then could not locate a trusted CA bundle. I solved this with a localhost-only DNS forwarder, targeted IPv6 localhost redirection, and an explicit Termux `SSL_CERT_FILE`. Certificate issuance then succeeded.

My final routing design separates trust domains:

- port 443: Tailscale Serve, private application;
- separate Funnel listener: only `/expenses_webhook/` for Google Apps Script;
- no public handler for dashboard or upload paths.

My wife accesses only the shared `household-finance` machine, not the rest of the tailnet.

## 7. Securing the machine webhook

The original Sheet notification accepted any POST and triggered a complete workbook import. Receipt-write authentication existed, but it protected the opposite direction.

I introduced a separate inbound secret:

- Apps Script reads `EXPENSES_WEBHOOK_SHARED_SECRET` from Script Properties.
- It sends `X-Webhook-Secret`.
- Django fails closed when configuration is missing.
- Missing or incorrect secrets return 401 before any external or database work.
- Valid secrets use constant-time comparison.
- Non-JSON requests are rejected.

I verified that the public Funnel listener returned 404 for upload and dashboard paths while the authenticated webhook remained available.

## 8. Solving the false receipt failure

The first live receipt was correctly written to Google Sheets but displayed a failure in Django. The write request took several minutes because `ReceiptWrite.gs` synchronously called `sendNotificationToDjango()`, which pulled the entire workbook before Apps Script returned its acknowledgement. Safari disconnected; Apps Script finished the financial write; Django recorded `sync_failed`.

My solution preserved both idempotency and architecture:

- acknowledge the financial write promptly;
- schedule the existing projection refresh with a one-time Apps Script trigger;
- coalesce pending refresh triggers;
- delete one-time triggers after execution;
- safely retry the same UUID without another increment.

The retry returned successfully in about ten seconds and changed Django state to `synced` without duplicating the Sheet amount.

## 9. Mobile compatibility lessons

Changing an iPhone to “Most Compatible” mode still produced a photo rejected by strict format validation. The filename and Photos metadata said JPEG, but Pillow can identify multi-picture JPEG containers as `MPO`.

I updated the validator to accept `MPO` as a JPEG-compatible decoded format while retaining real image decoding and size limits. Unsupported files now report the detected format, making future HEIF troubleshooting evidence-based.

## 10. Keeping Android alive with the screen off

The final host uses:

- Termux:Boot scripts for Tailscale, Redis, and Daphne;
- idempotent process checks to prevent duplicates;
- Termux CPU wake lock;
- Android Doze whitelist;
- allowed background execution and wake-lock app operations;
- screen-on-while-charging disabled so hosting does not require an illuminated display.

This design recognizes that root access does not turn Android into systemd. I achieved reliability by designing for Android’s lifecycle rather than pretending it is conventional Linux.

## 11. Outcomes

I verified the finished workflow with real devices and services:

- my wife’s iPhone privately reached the upload endpoint;
- an iPhone JPEG/MPO receipt uploaded successfully;
- Gemini extracted the receipt;
- reviewed data was confirmed;
- Apps Script updated the correct Google Sheets cells once;
- the secured trigger refreshed Supabase;
- Django recorded the receipt as synchronized;
- dashboard endpoints returned successful responses;
- the Honor 8 continued hosting through Tailscale with its screen allowed to sleep.

The most valuable result for me is not any single library. It is the disciplined preservation of invariants while I solved problems across application code, APIs, networking, databases, ARM Linux packaging, browser behavior, and Android operations.
