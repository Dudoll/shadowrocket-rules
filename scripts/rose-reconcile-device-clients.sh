#!/usr/bin/env bash
set -Eeuo pipefail

GENERATOR=/usr/local/sbin/rose-generate-device-subscriptions
ENV_FILE=/etc/rose-device-identities.env
CONFIG=${1:-/etc/v2ray-agent/xray/conf/00-rose-dmit.json}
CONFIG_DIR=$(dirname "$CONFIG")
CONFIG_NAME=$(basename "$CONFIG")
CANDIDATE=
BACKUP=
RESTORE=
TEST_DIR=

# Serialize this reconciler. The checksum guard below also detects writers that
# do not cooperate with this advisory lock.
exec 9>/run/lock/rose-device-clients.lock
flock -n 9 || exit 0
LIVE_SHA=$(sha256sum "$CONFIG" | cut -d' ' -f1)

cleanup() {
  if [[ -n "$CANDIDATE" ]]; then rm -f "$CANDIDATE"; fi
  if [[ -n "$RESTORE" ]]; then rm -f "$RESTORE"; fi
  if [[ -n "$TEST_DIR" ]]; then rm -rf "$TEST_DIR"; fi
  # BACKUP is intentionally not removed here. If rollback itself fails, the
  # same-directory backup must survive for manual recovery.
}
trap cleanup EXIT

rollback() {
  if [[ -z "$BACKUP" || ! -s "$BACKUP" ]]; then
    echo "rollback unavailable; backup retained if present" >&2
    return 1
  fi
  RESTORE=$(mktemp "$CONFIG_DIR/.${CONFIG_NAME}.device-restore.XXXXXX")
  if ! cp -p "$BACKUP" "$RESTORE"; then
    echo "rollback copy failed; backup retained" >&2
    return 1
  fi
  if ! mv "$RESTORE" "$CONFIG"; then
    echo "rollback rename failed; backup retained" >&2
    return 1
  fi
  RESTORE=
  if ! systemctl restart xray || ! systemctl is-active --quiet xray; then
    echo "rollback restored config but Xray health failed; backup retained" >&2
    return 1
  fi
  rm -f "$BACKUP"
  BACKUP=
}

if "$GENERATOR" reconcile --env "$ENV_FILE" --config "$CONFIG" >/dev/null 2>&1; then
  exit 0
else
  rc=$?
fi
if [[ $rc -ne 2 ]]; then
  exit "$rc"
fi

CANDIDATE=$(mktemp "$CONFIG_DIR/.${CONFIG_NAME}.device-candidate.XXXXXX")
TEST_DIR=$(mktemp -d)

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

# Abort rather than overwrite a manager update that landed while the candidate
# was being built and validated.
current_sha=$(sha256sum "$CONFIG" | cut -d' ' -f1)
if [[ "$current_sha" != "$LIVE_SHA" ]]; then
  echo "live Xray config changed during reconciliation; retrying on next timer" >&2
  exit 75
fi

BACKUP=$(mktemp "$CONFIG_DIR/.${CONFIG_NAME}.device-backup.XXXXXX")
cp -p "$CONFIG" "$BACKUP"
backup_sha=$(sha256sum "$BACKUP" | cut -d' ' -f1)
current_sha=$(sha256sum "$CONFIG" | cut -d' ' -f1)
if [[ "$backup_sha" != "$LIVE_SHA" || "$current_sha" != "$LIVE_SHA" ]]; then
  rm -f "$BACKUP"
  BACKUP=
  echo "live Xray config changed before commit; retrying on next timer" >&2
  exit 75
fi

mv "$CANDIDATE" "$CONFIG"
CANDIDATE=
if ! systemctl restart xray; then
  rollback || true
  exit 1
fi
if ! systemctl is-active --quiet xray; then
  rollback || true
  exit 1
fi

# A post-restart readback proves the installed file is idempotent and complete.
if ! "$GENERATOR" reconcile --env "$ENV_FILE" --config "$CONFIG" >/dev/null; then
  rollback || true
  exit 1
fi
rm -f "$BACKUP"
BACKUP=
