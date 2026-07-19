#!/usr/bin/env bash
set -Eeuo pipefail

GENERATOR=/usr/local/sbin/rose-generate-device-subscriptions
ENV_FILE=/etc/rose-device-identities.env
CONFIG=${1:-/etc/v2ray-agent/xray/conf/00-rose-dmit.json}
CONFIG_DIR=$(dirname "$CONFIG")
CONFIG_NAME=$(basename "$CONFIG")
CANDIDATE=$(mktemp "$CONFIG_DIR/.${CONFIG_NAME}.device-candidate.XXXXXX")
BACKUP=$(mktemp "$CONFIG_DIR/.${CONFIG_NAME}.device-backup.XXXXXX")
TEST_DIR=$(mktemp -d)

cleanup() {
  rm -f "$CANDIDATE" "$BACKUP"
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

rollback() {
  if [[ -s "$BACKUP" ]]; then
    mv "$BACKUP" "$CONFIG"
  fi
  systemctl restart xray || true
  systemctl is-active --quiet xray || true
}

if "$GENERATOR" reconcile --env "$ENV_FILE" --config "$CONFIG" >/dev/null 2>&1; then
  exit 0
else
  rc=$?
fi
if [[ $rc -ne 2 ]]; then
  exit "$rc"
fi

# Build and mutate an isolated candidate; the live file remains untouched.
cp -p "$CONFIG" "$CANDIDATE"
"$GENERATOR" reconcile --env "$ENV_FILE" --config "$CANDIDATE" --apply

# Validate a complete temporary confdir with the candidate replacing only the
# managed file. Candidate/backup suffixes are deliberately not .json so Xray's
# live confdir loader cannot consume them during a concurrent restart.
for source in "$CONFIG_DIR"/*.json; do
  cp -p "$source" "$TEST_DIR/"
done
cp -p "$CANDIDATE" "$TEST_DIR/$CONFIG_NAME"
/usr/local/bin/xray run -test -confdir "$TEST_DIR"

cp -p "$CONFIG" "$BACKUP"
mv "$CANDIDATE" "$CONFIG"
if ! systemctl restart xray; then
  rollback
  exit 1
fi
if ! systemctl is-active --quiet xray; then
  rollback
  exit 1
fi

# A post-restart readback proves the installed file is idempotent and complete.
if ! "$GENERATOR" reconcile --env "$ENV_FILE" --config "$CONFIG" >/dev/null; then
  rollback
  exit 1
fi
rm -f "$BACKUP"
