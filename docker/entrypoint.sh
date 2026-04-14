#!/bin/sh
set -eu

DEFAULT_UID=10001
DEFAULT_GID=10001
TARGET_UID="${PUID:-$DEFAULT_UID}"
TARGET_GID="${PGID:-$DEFAULT_GID}"
IS_ROOT=0

if [ "$(id -u)" = "0" ]; then
  IS_ROOT=1
fi

sync_runtime_user() {
  if [ "$IS_ROOT" -ne 1 ]; then
    return 0
  fi

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
  if [ "$IS_ROOT" -eq 1 ]; then
    chown tdarr:tdarr "$target" 2>/dev/null || true
  fi
}

runuser_available() {
  if [ "$IS_ROOT" -ne 1 ]; then
    return 1
  fi

  runuser -u tdarr -- true >/dev/null 2>&1
}

run_tdarr_command() {
  if runuser_available; then
    runuser -u tdarr -- "$@"
    return
  fi

  "$@"
}

run_as_tdarr() {
  if runuser_available; then
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
  run_tdarr_command mkdir -p "$parent_dir"
  run_tdarr_command mkdir -p "$target"
  if [ "$IS_ROOT" -eq 1 ]; then
    chown -R tdarr:tdarr "$target" "$parent_dir" 2>/dev/null || true
  fi
}

sync_runtime_user
ensure_dir /home/tdarr
ensure_dir /tmp/tdarr-subtitle-ocr
prepare_dir "/config"
prepare_dir "${OCR_COPY_CLIENT_DIR:-}"
if [ "$IS_ROOT" -eq 1 ]; then
  chown -R tdarr:tdarr /tmp/tdarr-subtitle-ocr /config /home/tdarr 2>/dev/null || true
fi

run_as_tdarr "$@"
