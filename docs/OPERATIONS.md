# Operations Runbook

This is a sanitized operational guide. It intentionally contains no credentials, private IP addresses, deployment IDs, workbook IDs, or live hostnames.

## Runtime topology

| Component | Location | Purpose |
|---|---|---|
| Django/Daphne | Honor 8 Termux | UI, receipt workflow and webhook processing |
| Redis | Honor 8 Termux | Django Channels layer |
| Tailscale Serve | Honor 8 | Private HTTPS application access |
| Tailscale Funnel | Honor 8, separate listener | Public Apps Script webhook path only |
| PostgreSQL | Supabase | Synchronized dashboard projection |
| Google Sheets | Google | Authoritative household ledger |
| Apps Script | Bound spreadsheet project | Receipt writes and synchronization notification |
| Gemini | Google API | Structured receipt extraction |

## Important invariants

1. Google Sheets is authoritative.
2. PostgreSQL is a projection, not an independent ledger.
3. A receipt must be reviewed before it can be sent.
4. A receipt UUID must never increment the Sheet twice.
5. `/upload/` and `/dashboard/` remain private.
6. Only `/expenses_webhook/` is publicly routed, and it requires its own secret.
7. Never clear an Apps Script `pending` receipt property before reconciling the Sheet.

## Deployment locations

The production checkout and virtual environment are separate from the preserved legacy checkout. The Termux deployment uses a clean Git clone, an outer `.env`, a local `secrets/google_service_account.json`, and phone-only boot scripts under `~/.termux/boot/`.

The outer `Private/` documentation and Apps Script reference sources are not part of the nested Git repository. Apps Script changes must be copied and deployed through the bound Google project.

## Standard health checks

Run on the Honor 8 from the Django project directory:

```bash
python manage.py check
redis-cli ping
pgrep -af daphne
pgrep -af redis-server
pgrep -af tailscaled
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/upload/
```

Expected results:

- Django: no system-check issues;
- Redis: `PONG`;
- one Daphne process bound to localhost port 8000;
- one Redis process;
- one userspace `tailscaled` process;
- local upload response: HTTP 200.

Inspect Tailscale routing:

```bash
tailscale --socket="$PREFIX/var/run/tailscale/tailscaled.sock" serve status
tailscale --socket="$PREFIX/var/run/tailscale/tailscaled.sock" funnel status
```

Confirm private Serve owns the normal HTTPS listener and Funnel exposes only the webhook path on its separate listener.

## Updating Django

```bash
cd <production-checkout>
git status --short --branch
git pull --ff-only origin master
python manage.py check
```

Preserve untracked media, credentials, environment files, and any unrelated user changes. Do not run migrations blindly: inspect `showmigrations` and `migrate --plan` first because the legacy migration history was incomplete in early repository versions.

Restart Daphne only after checks pass. The boot script starts Daphne with an explicit virtual-environment binary and localhost binding.

## Environment variables

Required names are listed in the project README. When updating `.env`:

- transfer it with restrictive permissions;
- do not print values into logs or chat;
- restart Daphne because settings are loaded at process start;
- remember that a long-running shell can retain an older exported value even after `.env` changes;
- verify the deployment identifier or hostname through a boolean/redacted check rather than printing secrets.

## Apps Script deployment

The service-account credential used for Sheets reads cannot edit or deploy Apps Script. Apps Script management requires a Google user OAuth flow; current deployment is manual.

After changing Apps Script:

1. Save all bound-project files.
2. Run newly permissioned helper functions manually once when required.
3. Approve scopes.
4. create a new web-app deployment version;
5. update `APPS_SCRIPT_RECEIPT_URL` if the `/exec` URL changes;
6. restart Daphne;
7. perform a controlled receipt test;
8. inspect Apps Script Executions and Django receipt state.

## Receipt troubleshooting

### Batch review and synchronization

- Multi-image uploads keep their original order and open one editable confirmation form.
- Failed extractions remain visible with their stored images and safe error messages; they are not silently dropped from the batch.
- Receipt images are served through the receipt-specific `receipt_image` view with private, no-store caching. Do not expose the media directory through a general production route.
- One confirmation stores all valid edits transactionally. The browser then sends each confirmed receipt separately with its original UUID, so a later failure does not lose the rest of the batch.
- Before manually inserting a failed receipt, cross-check the authoritative Sheet and its UUID state to avoid a duplicate write.

### Upload says unsupported format

- Confirm the error’s detected format.
- JPEG, PNG, and JPEG-compatible MPO are supported.
- HEIC/HEIF is not decoded in the current deployment.
- Changing iPhone Camera Formats affects new photos only.

### Extraction fails

- Confirm the image remains stored.
- Inspect receipt status and safe error text.
- Verify Gemini configuration names exist without printing values.
- Confirm the configured model remains available.
- The provider makes the configured bounded number of attempts and searches returned text parts for valid JSON.
- Distinguish timeout, request, and incomplete-response messages when diagnosing failures.
- Avoid additional manual retry loops during an external outage.

### Sheet contains the receipt but Django says sync failed

- Do not upload the receipt again.
- Retry the same receipt UUID through its confirmation page.
- Apps Script should recognize the UUID as `synced`, avoid another increment, schedule projection refresh, and return a positive acknowledgement.
- If the UUID is `pending`, reconcile actual cells and Apps Script execution logs before changing its property.

### Projection refresh is slow

- Receipt writes acknowledge before the full refresh; `runDeferredDjangoNotification` performs the refresh later.
- Inspect Apps Script Executions for the deferred function.
- The current webhook intentionally reads the configured workbook and may take time.
- Dashboard endpoints are normally subsecond locally; slow UI during a refresh can be resource or network contention.

### Supabase is unreachable from the phone

The direct Supabase database endpoint currently relies on IPv6. The Honor 8 has intermittently reported `No route to host`, which can produce dashboard HTTP 500 responses even while Daphne is healthy.

- Confirm local `/upload/` and `/dashboard/` responses before blaming Tailscale.
- Test the database connection without printing its connection string or password.
- Treat restarting Daphne as recovery, not a network fix.
- The durable follow-up is to move the phone to Supabase's Session Pooler using the connection string copied from the project dashboard, then run Django checks and a projection read before making it permanent.

## Creating the next monthly worksheet

Use **Create Next Month** on the dashboard. The POST-only action:

1. identifies the latest worksheet named like `Sep2026`;
2. chooses the same month from the prior year as the preferred formatting template;
3. validates the exact dashboard headers and 32-row ledger shape;
4. copies formatting and formulas, clears transaction values, and writes the new dates;
5. allocates continuous `PK_Unique` values above the maximum across all monthly tabs;
6. verifies the result and deletes the copied tab if validation fails.

Do not rename monthly worksheets or change the expected columns without updating and testing the dashboard schema contract.

## Webhook troubleshooting

Expected public behavior:

| Request | Expected status |
|---|---:|
| POST without secret | 401 |
| POST with incorrect secret | 401 |
| Authenticated non-JSON POST | 415 |
| Authenticated JSON POST | 200 after synchronization |
| Public upload path on Funnel listener | 404 |
| Public dashboard path on Funnel listener | 404 |

If Apps Script receives 401, compare the property name and value on both sides without logging the value. Receipt-write and inbound-webhook secrets are deliberately different.

## Android and Tailscale troubleshooting

The Honor 8 has no TUN device. `tailscaled` therefore must use userspace networking and the configured Termux socket.

If HTTPS certificate renewal fails:

- verify the localhost DNS forwarder;
- verify IPv6 localhost DNS redirection;
- verify `SSL_CERT_FILE` points to Termux’s CA bundle in the Tailscale boot script;
- inspect the Tailscale state log for DNS, ACME, or x509 errors.

If services disappear with the screen off:

- confirm Termux is on the Doze whitelist;
- confirm `RUN_IN_BACKGROUND` and `WAKE_LOCK` app operations are allowed;
- reacquire `termux-wake-lock`;
- confirm Huawei app-launch/background restrictions;
- verify Termux:Boot scripts remain executable;
- test private `/upload/` after 15 minutes and again after an hour.

If the phone rebooted but the stack did not return, inspect whether Android marked Termux:Boot as stopped. Launching its activity once clears that stopped state; then verify the boot scripts and all standard health checks.

### Root watchdog state

The active recovery mechanism is the established root watchdog launched from Magisk `service.d`. It runs outside the Termux process group and performs bounded health checks before invoking the idempotent Termux launchers.

An experimental guardian/worker split was rolled back on 2026-09-10 after concurrent startup paths spawned duplicate supervisors and made the phone unresponsive. Its script files may remain on the device, but the Magisk entry point must continue to reference the established watchdog. Do not activate the guardian/worker version until its locking, stale-PID handling, and concurrent-start lifecycle are reproduced and tested off-device.

## Backup and recovery

- Google Sheets is the primary recoverable financial record.
- Supabase should be treated as rebuildable projection data.
- Preserve receipt media until its retention policy is implemented.
- Preserve the Tailscale state directory; it contains node identity and certificate state.
- Preserve Apps Script Properties because they contain receipt idempotency state.
- Back up the workbook before changing ledger-write logic.
- Never commit `.env`, Google credentials, Tailscale state, receipt media, database dumps, or generated certificates.

## Security maintenance

- Rotate any credential exposed in logs, shell history, or conversation.
- Rotate SSH passwords shared during setup and prefer SSH keys.
- Disable key expiry only for trusted personal Tailscale devices.
- Revoke shared-machine access when no longer required.
- Keep Funnel path isolation verified after any Serve/Funnel change.
- Apply Android/Termux package updates deliberately; native Python and PostgreSQL major-version changes require compatibility checks.
