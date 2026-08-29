# Production operations

## Readiness

The public endpoint is `https://panel.ecormecejhelizstore.com/health/ready`.
GitHub Actions checks it every five minutes. A successful response must report
`status=ready` and all dependencies as true.

## Authentication deployment rollback

The pre-deployment archive on the production host is:

```text
/home/deploy/mail-control-enterprise/backups/pre-unified-auth-20260811T065622Z.tar.gz
```

Before rollback, capture the current files. Then extract the archive from the
application directory, validate Compose, rebuild the affected images, and
recreate only `api`, `worker`, `microsoft-worker`, and `sync-scheduler`.

```bash
cd /home/deploy/mail-control-enterprise
tar -xzf backups/pre-unified-auth-20260811T065622Z.tar.gz
docker compose config --quiet
docker compose build api worker microsoft-worker sync-scheduler
docker compose up -d --no-deps --force-recreate \
  api worker microsoft-worker sync-scheduler
docker compose ps
curl -fsS http://127.0.0.1:8100/health/ready
```

The archive was extraction-tested after creation. PostgreSQL was not changed by
this deployment and does not need restoration for this rollback.

## Backup restoration verification

The PostgreSQL custom dump
`backups/mail-control-before-email-change-20260809.dump` was restored into an
isolated temporary database on 2026-08-11. The test found 15 public tables and
21 mail accounts. The temporary database and copied dump were removed after the
check.
