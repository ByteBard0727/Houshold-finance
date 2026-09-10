# Next Session Handoff

Last updated: 2026-09-10 (Asia/Tokyo)

This file is intentionally sanitized. Retrieve hostnames, credentials, workbook identifiers, and service connection strings from the existing private deployment configuration, never from Git history.

## Shipped this session

- Multi-image uploads use one ordered batch confirmation page.
- Failed receipt extractions remain visible with their stored images and error state.
- Production receipt previews use a receipt-specific private endpoint.
- Confirmed batch items synchronize independently with their original duplicate-safe UUIDs.
- Gemini extraction performs bounded retries, examines all returned text parts, and records specific safe failure categories.
- The dashboard can create the next monthly Google Sheet after validating the strict ledger schema, dates, formulas, and globally continuous primary keys.
- The current changes were deployed to the Honor 8 and the local Redis, upload, and dashboard health checks passed after recovery.

## Current production state

- Google Sheets remains the authoritative ledger; Supabase remains a rebuildable dashboard projection.
- The established root watchdog is active through the Magisk `service.d` entry point.
- The experimental guardian/worker split is inactive and was rolled back after a duplicate-process startup race. Do not enable it merely because its files may still exist on the phone.
- Termux:Boot was observed with Android's stopped flag after a reboot. Opening its activity cleared the flag and allowed the service stack to recover.
- The direct Supabase endpoint's IPv6 route from the Honor 8 remains intermittent and can surface as dashboard HTTP 500 errors.

## First checks next time

```bash
git status --short --branch
git pull --ff-only origin master
python manage.py check
redis-cli ping
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/upload/
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/dashboard/
```

Use the isolated test settings described in the private troubleshooting skill when the normal settings would connect to Supabase. The full focused suite is:

```bash
PYTHONPATH="/tmp:$PWD" DJANGO_SETTINGS_MODULE=household_batch_test_settings ../venv/bin/python manage.py test dashboard expense_upload
```

## Prioritized follow-up

1. Migrate the Honor 8 database connection from the IPv6-dependent direct Supabase endpoint to the Session Pooler. Obtain the exact connection string from the Supabase dashboard, preserve it only in private configuration, then verify Django checks, a dashboard projection read, and receipt synchronization.
2. Redesign the guardian/worker experiment off-device. Tests must cover simultaneous starts, atomic singleton locking, stale PID reuse, child crashes, bounded commands, and cleanup before any phone deployment.
3. Re-run a controlled multi-image receipt batch and verify image previews, one-click confirmation, individual sync statuses, Sheet values, and the refreshed dashboard projection.
4. Confirm the bound Apps Script deployment is the intended current version before changing synchronization behavior; its source and deployment metadata are maintained outside this public repository.

## Non-negotiable safety rules

- Never re-upload or manually write a questionable receipt until the Sheet and Apps Script UUID state have been reconciled.
- Never expose the dashboard, upload route, or receipt images through Funnel.
- Never commit `.env`, service-account files, phone addresses, receipt media, Sheet data, or shared secrets.
- Preserve unrelated phone and workbook state during deployment; use fast-forward pulls and inspect migrations before applying them.
