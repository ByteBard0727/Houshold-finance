# Engineering Journey

This document records how I architected and evolved this project, including the technical hardships I overcame along the way. It covers work that predates the current Codex-assisted implementation and draws on my own history of the project as well as the repository, deployment artifacts, and architecture reviews.

## 1. Starting point: a spreadsheet-backed dashboard

I began the project as a household expense dashboard centered on a shared Google workbook. Each month is a worksheet such as `Aug2026`; rows represent days and columns represent categories including food, leisure, utilities, automatic withdrawals, SMBC payments, and household items.

I used Django to import the workbook into a flat PostgreSQL table and serve Chart.js endpoints. Google Sheets was already operationally important, but I had not yet made that architectural boundary explicit. Docker Compose proposed local PostgreSQL, Redis, Nginx, and Daphne while Django settings pointed to Supabase. Upload routes were incomplete, migration history was fragmented, configuration was inconsistent, and the frontend still contained theme-demo sections.

My most important early decision was therefore not a technology choice but a contract:

> Google Sheets is the authoritative ledger. PostgreSQL is a synchronized projection for the dashboard.

That decision prevented a risky bidirectional rewrite and gave me a stable boundary for every later change.

## 2. Unlocking and rooting the Honor 8

Before I could turn the Honor 8 into a server, I had to regain control of hardware that Huawei no longer supported as an unlockable development device. Huawei had stopped issuing bootloader unlock codes, so the ordinary developer workflow was no longer available.

I adapted the physical test-point method documented for the closely related FRD-L19 to my FRD-L09. I enabled OEM unlocking and USB debugging, removed the glued rear cover without heating the battery, exposed the board test point, and shorted it to the shield while connecting USB. That placed the Kirin device into the low-level serial mode needed by PotatoNV. I used PotatoNV to recover the bootloader unlock code, saved it, returned the phone to fastboot mode, and unlocked the bootloader. The unlock deliberately factory-reset the phone.

With the bootloader open, I used fastboot to flash TWRP and then used TWRP to install Magisk. The live phone now provides direct evidence of the resulting chain:

- model: Honor 8 `FRD-L09` (`HWFRD`);
- firmware: Android 7.0 / API 24, EMUI 5.0.4, build `FRD-L09C432B418`;
- Android security patch: 2019-08-01;
- kernel: Huawei downstream `4.1.18-g777bc27`, AArch64;
- recovery: TWRP 3.1.1-1, confirmed by the retained recovery log;
- root: Magisk 23.0, running in the Magisk SELinux domain;
- boot state: unlocked (`flash.locked=0`, verified-boot state `ORANGE`) with dm-verity still enforcing.

The distinction between guide and device matters. The test-point write-up describes an FRD-L19 on a different regional build; I used its hardware method, but the version record above comes from commands run on my actual FRD-L09.

I also considered replacing Android with a complete postmarketOS installation. The Honor 8 port proved that the display, touchscreen, internal storage, USB networking, and USB OTG could work on a downstream 4.1.18 kernel. It also exposed risks that were unacceptable for this household service: no mainline kernel, partial flashing support, a boot image larger than the 32 MB boot partition, PotatoNV-related fastboot restrictions, broken 3D acceleration and camera support, partial battery support, and untested Wi-Fi, audio, Bluetooth, GPS, and modem functions. The device catalog classifies downstream ports as stepping stones toward mainline and warns that they can be unsuitable for modern userspace such as Docker or systemd.

I reviewed the device-specific downstream kernel source as another possible route, but maintaining a private mobile-Linux kernel and completing missing hardware support would have expanded the project far beyond the financial application. I therefore kept the verified Huawei Android 7 kernel, Magisk root, and Termux userspace. This preserved the phone’s working drivers while still giving me enough control to build a reliable service host.

## 3. Hosting experiments on a rooted Honor 8

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

## 4. Rebuilding the Android Python environment

The old phone checkout contained extensive local modifications on top of a single early Git commit. Rather than overwrite it, I cloned a clean deployment checkout alongside it and preserved the legacy tree for recovery.

Termux itself contained mixed package generations. I performed a controlled distribution upgrade that moved the phone to Python 3.14, Redis 8, PostgreSQL 18 tooling, and current OpenSSH packages while preserving existing configuration. I created the deployment virtual environment with access to Termux system packages so I could reuse expensive native components such as Pillow and cryptography.

I audited the live host again on 2026-08-14 rather than relying on remembered installation versions. It was running Termux 0.119.0-beta.3, Python 3.14.6, Redis 8.8.1, Tailscale 1.94.2, Django 4.2.17, and Daphne 4.1.2. These are observed deployment versions, not minimum project requirements.

Several Python packages still had to compile on ARM64/Android. I removed pandas, NumPy usage, and django-pandas from the synchronization runtime, replacing DataFrame transformations with dictionaries and `datetime`. This reduced build risk, memory use, and startup weight while preserving synchronization behavior.

## 5. Stabilizing the legacy dashboard

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

## 6. Building receipt processing in safe phases

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

## 7. Replacing ngrok with Tailscale

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

## 8. Securing the machine webhook

The original Sheet notification accepted any POST and triggered a complete workbook import. Receipt-write authentication existed, but it protected the opposite direction.

I introduced a separate inbound secret:

- Apps Script reads `EXPENSES_WEBHOOK_SHARED_SECRET` from Script Properties.
- It sends `X-Webhook-Secret`.
- Django fails closed when configuration is missing.
- Missing or incorrect secrets return 401 before any external or database work.
- Valid secrets use constant-time comparison.
- Non-JSON requests are rejected.

I verified that the public Funnel listener returned 404 for upload and dashboard paths while the authenticated webhook remained available.

## 9. Solving the false receipt failure

The first live receipt was correctly written to Google Sheets but displayed a failure in Django. The write request took several minutes because `ReceiptWrite.gs` synchronously called `sendNotificationToDjango()`, which pulled the entire workbook before Apps Script returned its acknowledgement. Safari disconnected; Apps Script finished the financial write; Django recorded `sync_failed`.

My solution preserved both idempotency and architecture:

- acknowledge the financial write promptly;
- schedule the existing projection refresh with a one-time Apps Script trigger;
- coalesce pending refresh triggers;
- delete one-time triggers after execution;
- safely retry the same UUID without another increment.

The retry returned successfully in about ten seconds and changed Django state to `synced` without duplicating the Sheet amount.

## 10. Mobile compatibility lessons

Changing an iPhone to “Most Compatible” mode still produced a photo rejected by strict format validation. The filename and Photos metadata said JPEG, but Pillow can identify multi-picture JPEG containers as `MPO`.

I updated the validator to accept `MPO` as a JPEG-compatible decoded format while retaining real image decoding and size limits. Unsupported files now report the detected format, making future HEIF troubleshooting evidence-based.

## 11. Keeping Android alive with the screen off

My first background-lifecycle design used:

- Termux:Boot scripts for Tailscale, Redis, and Daphne;
- idempotent process checks to prevent duplicates;
- Termux CPU wake lock;
- Android Doze whitelist;
- allowed background execution and wake-lock app operations;
- screen-on-while-charging disabled so hosting does not require an illuminated display.

That was necessary but not sufficient on EMUI. The complete stack later disappeared without a phone reboot. Daphne and Redis stopped first, Tailscale survived for several more hours, and their logs ended without application exceptions or graceful shutdown messages. When I inspected the phone, no Termux wake lock remained and Android marked Termux:Boot `stopped=true`.

Research into the device-specific behavior showed why ordinary Android advice was incomplete. The [Termux EMUI report](https://github.com/termux/termux-app/issues/1172) documents persistent processes being killed despite wake locks. A separate [Huawei wake-lock investigation](https://stackoverflow.com/questions/39954822/battery-optimizations-wakelocks-on-huawei-emui-4-0) identifies two independent policies: SystemManager can remove unprotected applications after screen-off, while PowerGenie can force-stop an application for holding a wake lock too long. A wake lock prevents CPU suspension; it does not guarantee that Android or an OEM process manager will preserve the process that owns it.

I could not honestly attribute this particular termination to one exact EMUI component because the relevant ActivityManager records had already rolled out of `logcat`, and the retained kernel log contained no matching out-of-memory event. I therefore designed for recovery and better evidence rather than presenting an inference as a measured cause.

The first recovery attempt exposed another weakness: an existing Magisk `service.d` watchdog detached itself through Termux, wrote a PID file, and then disappeared. A stale PID file gave the appearance of supervision even though nothing was watching the services. I replaced it with a persistent root supervisor that:

- runs outside the Termux process group as UID 0 with parent PID 1;
- checks Tailscale, Redis, and Daphne every 60 seconds;
- reads `/proc/*/cmdline` directly because Android 7 `ps` output is insufficient for reliable matching;
- restarts only the missing part of the stack through idempotent launchers;
- reacquires the Termux wake lock when it is absent;
- captures recent PowerGenie, EMUI, ActivityManager, and low-memory evidence as soon as it detects a loss;
- validates stale PID files against the actual command line;
- switches to the Termux UID with its required Android network groups;
- binds Redis explicitly to `127.0.0.1` with a writable PID file;
- uses a bounded local HTTP request instead of a potentially hanging Daphne process lookup.

I tested the recovery path by gracefully stopping Redis. The supervisor detected the missing process, started a new Redis PID within one check interval, restored `PONG`, and kept the upload endpoint at HTTP 200. The same application-stack check covers Daphne: if Daphne disappears, the local upload health check fails and the launcher starts it again while Tailscale routing remains in place.

This design recognizes that root access does not turn Android into systemd. I cannot guarantee that EMUI will never kill Termux again, but I moved supervision outside EMUI’s Termux process boundary and reduced expected recovery time to roughly one minute.

## 12. Outcomes

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

## 13. Sources and field references

I used these sources as working references and verified device-specific claims against the live FRD-L09 wherever possible:

### Bootloader, recovery, and root

- [Honor 8 FRD-L19 test-point and PotatoNV guide](https://telegra.ph/Honor-8-FRD-L19-Root-testpoint-04-28) — physical access, test-point mode, PotatoNV, bootloader unlocking, TWRP, and Magisk 23 sequence; adapted carefully because my phone is an FRD-L09.
- [XDA Honor 8 Smart root and TWRP guide](https://xdaforums.com/t/guide-root-huawei-honor-8-smart-and-install-twrp-custom-recovery-emui-5-x.3724656/) — fastboot, custom recovery, and EMUI 5 rooting context.
- [Official TWRP Honor 8 device page](https://twrp.me/huawei/huaweihonor8.html) — Honor 8 recovery identity and fastboot installation reference.

### Full-Linux evaluation

- [postmarketOS Honor 8 device page](https://wiki.postmarketos.org/wiki/Huawei_Honor_8_%28huawei-frd%29) — downstream-kernel status, partition constraints, PotatoNV flashing limitation, and hardware feature matrix.
- [postmarketOS device catalog](https://wiki.postmarketos.org/wiki/Devices) and [device categorization](https://docs.postmarketos.org/pmaports/main/device-categorization.html) — maturity and support expectations for downstream ports.
- [Honor 8 downstream kernel source](https://gitlab.com/Sandelinos/android_kernel_huawei_frd) — device-specific 4.1.18 kernel work considered for a complete Linux installation.

### Android, EMUI, and service survival

- [Termux: “killed in background by EMUI”](https://github.com/termux/termux-app/issues/1172) — direct report of persistent Termux workloads being killed despite a wake lock.
- [Huawei EMUI wake-lock investigation](https://stackoverflow.com/questions/39954822/battery-optimizations-wakelocks-on-huawei-emui-4-0) — observed SystemManager and PowerGenie force-stop behavior.
- [Android wake-lock documentation](https://developer.android.com/develop/background-work/background-tasks/awake/wakelock) — what a wake lock does and does not guarantee.
- [Termux process-killing discussion](https://github.com/termux/termux-app/issues/2015) — Android treatment of detached or empty Termux processes.
- [Termux SSH daemon survival discussion](https://github.com/termux/termux-app/issues/483) — an older Android example of background daemons disappearing even when Termux held a wake lock.
- [Termux:Boot relaunch discussion](https://github.com/termux/termux-boot/issues/298) — limitations of boot-only startup after Android reclaims Termux and motivation for supervision outside the application process.
- [Termux service-notification discussion](https://github.com/termux/termux-app/issues/4657) — relationship between the Termux service, persistent notification or task, wake lock, and detached daemons.
- [Termux:Boot documentation](https://github.com/termux/termux-boot/blob/master/README.md) — opening Termux:Boot once, ordered boot scripts, and acquiring the wake lock.
- [Magisk boot-script documentation](https://github.com/topjohnwu/Magisk/blob/master/docs/guides.md#boot-scripts) — non-blocking `service.d` execution used for the root supervisor.
