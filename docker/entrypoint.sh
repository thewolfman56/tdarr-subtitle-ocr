#!/bin/sh
set -eu

DEFAULT_UID=10001
DEFAULT_GID=10001
TARGET_UID="${PUID:-$DEFAULT_UID}"
TARGET_GID="${PGID:-$DEFAULT_GID}"

sync_runtime_user() {
  current_uid=$(id -u tdarr)
  current_gid=$(id -g tdarr)

  if [ "$current_gid" != "$TARGET_GID" ]; then
    groupmod -o -g "$TARGET_GID" tdarr
  fi

  if [ "$current_uid" != "$TARGET_UID" ]; then
    usermod -o -u "$TARGET_UID" -g "$TARGET_GID" tdarr
  fi
}

ensure_dir() {
  target="$1"
  mkdir -p "$target" 2>/dev/null || true
  chown tdarr:tdarr "$target" 2>/dev/null || true
}

run_as_tdarr() {
  if runuser -u tdarr -- true 2>/dev/null; then
    exec runuser -u tdarr -- "$@"
  fi

  echo "WARNING: Unable to drop privileges to tdarr; continuing as current user." >&2
  exec "$@"
}

prepare_dir() {
  target="$1"
  if [ -z "$target" ]; then
    return 0
  fi

  parent_dir=$(dirname "$target")
  mkdir -p "$parent_dir" 2>/dev/null || true
  runuser -u tdarr -- mkdir -p "$parent_dir"
  runuser -u tdarr -- mkdir -p "$target"
  chown -R tdarr:tdarr "$target" "$parent_dir" 2>/dev/null || true
}

sync_runtime_user
ensure_dir /home/tdarr
ensure_dir /tmp/tdarr-subtitle-ocr
prepare_dir "/config"
prepare_dir "${OCR_COPY_CLIENT_DIR:-}"
chown -R tdarr:tdarr /tmp/tdarr-subtitle-ocr /config /home/tdarr 2>/dev/null || true

run_as_tdarr "$@"
