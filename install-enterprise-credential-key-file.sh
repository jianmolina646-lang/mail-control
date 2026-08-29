#!/usr/bin/env bash
set -euo pipefail
umask 077

cd /home/deploy/mail-control-enterprise
mkdir -p backups/pre-keyfile-61da82e
cp --parents compose.yaml src/mail_control/settings.py tests/test_settings.py \
  backups/pre-keyfile-61da82e/
cp .env backups/pre-keyfile-61da82e/env.backup

archive_hash="$(sha256sum mail-control-enterprise-keyfile-61da82e.tar.gz | cut -d' ' -f1)"
if [[ "$archive_hash" != "418305bfc3fa84d7b252d5740651a637c90b083093565ee26873fa26991372a8" ]]; then
  echo "archive checksum mismatch" >&2
  exit 1
fi
tar -xzf mail-control-enterprise-keyfile-61da82e.tar.gz

current_key="$(sed -n 's/^CREDENTIAL_ENCRYPTION_KEY=//p' .env | head -n1)"
if (( ${#current_key} < 32 )); then
  echo "current credential key is missing or too short" >&2
  exit 1
fi

mkdir -p secrets
printf '%s\n' "$current_key" > secrets/credential-encryption-key.tmp
chmod 600 secrets/credential-encryption-key.tmp
mv secrets/credential-encryption-key.tmp secrets/credential-encryption-key

source_hash="$(printf '%s' "$current_key" | sha256sum | cut -d' ' -f1)"
file_hash="$(tr -d '\r\n' < secrets/credential-encryption-key | sha256sum | cut -d' ' -f1)"
if [[ "$source_hash" != "$file_hash" ]]; then
  echo "credential key verification failed" >&2
  exit 1
fi

sed -i '/^CREDENTIAL_ENCRYPTION_KEY=/d' .env
chmod 600 .env secrets/credential-encryption-key
unset current_key source_hash file_hash

echo "credential key moved and verified"
stat -c '%a %U:%G %n' .env secrets/credential-encryption-key
grep -q '^CREDENTIAL_ENCRYPTION_KEY=' .env && exit 1 || true
