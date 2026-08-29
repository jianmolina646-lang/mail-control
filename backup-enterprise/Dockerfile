FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates cron curl openssl postgresql-client tzdata wget \
    && wget -q \
      https://mega.nz/linux/repo/xUbuntu_24.04/amd64/megacmd-xUbuntu_24.04_amd64.deb \
      -O /tmp/megacmd.deb \
    && apt-get install -y /tmp/megacmd.deb \
    && rm -f /tmp/megacmd.deb \
    && rm -rf /var/lib/apt/lists/*

COPY backup.sh /usr/local/bin/mailctl-enterprise-backup
COPY verify-restore.sh /usr/local/bin/mailctl-enterprise-verify-restore
COPY entrypoint.sh /usr/local/bin/enterprise-backup-entrypoint
COPY crontab /etc/cron.d/mailctl-enterprise-backup

RUN chmod 700 \
      /usr/local/bin/mailctl-enterprise-backup \
      /usr/local/bin/mailctl-enterprise-verify-restore \
      /usr/local/bin/enterprise-backup-entrypoint \
    && chmod 0644 /etc/cron.d/mailctl-enterprise-backup \
    && crontab /etc/cron.d/mailctl-enterprise-backup

ENTRYPOINT ["/usr/local/bin/enterprise-backup-entrypoint"]
