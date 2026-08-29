# Authentication and account monitoring

Mail Control Enterprise is the canonical implementation for Gmail API,
Microsoft Graph, account health, and Telegram incident notifications. The
legacy `mail-control` repository remains a migration reference and must not run
its IMAP scheduler against the same accounts after cutover.

## Gmail OAuth

- Authorization requests offline access and explicit consent so Google returns
  a refresh token.
- Access tokens are refreshed two minutes before expiry.
- Access and refresh tokens are encrypted at rest.
- A rotated refresh token replaces the previous encrypted value only after a
  successful token response. A response without a new refresh token preserves
  the existing value.
- `invalid_grant` changes the account to `reauth_required`; it is not retried as
  a transient provider outage.

Before production cutover, verify in Google Cloud Console that the OAuth consent
screen is **Production**, the Gmail API is enabled, the redirect URI exactly
matches `GOOGLE_REDIRECT_URI`, and the requested Gmail scope is approved. Google
projects left in **Testing** can issue grants that expire after seven days.

## Microsoft Graph

Graph requests retry bounded transient failures (`429`, `500`, `502`, `503`,
`504`) and network errors. `Retry-After` supports both seconds and HTTP dates;
without it the client uses exponential full jitter. A transient failure records
the failed sync run but preserves the account's prior health state and does not
open a Telegram incident.

Microsoft refresh-token rotation is persisted atomically with the refreshed
access token. `invalid_grant` changes the account to `reauth_required`.

## Telegram incident lifecycle

The key is `account + normalized error fingerprint`. Redis suppresses repeats
for `TELEGRAM_ACCOUNT_ALERT_DEDUPE_SECONDS`. An active incident is kept
separately so the first later successful synchronization sends exactly one
recovery message. Redis or Telegram failures never fail mail synchronization.

Production mounts Telegram credentials from a root-owned read-only file via
`TELEGRAM_ALERTS_FILE`. Only the deduplication period belongs in the ordinary
environment:

```env
TELEGRAM_ALERTS_FILE=/run/secrets/telegram-alerts.env
TELEGRAM_ACCOUNT_ALERT_DEDUPE_SECONDS=3600
```

The mounted file contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; never
commit that file or expose its values in logs.
