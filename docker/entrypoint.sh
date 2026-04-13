#!/bin/sh
set -eu

prepare_dir() {
  target="$1"
  if [ -z "$target" ]; then
    return 0
  fi

  parent_dir=$(dirname "$target")
  mkdir -p "$parent_dir"
  mkdir -p "$target"
  chown -R tdarr:tdarr "$target" "$parent_dir" 2>/dev/null || true
}

prepare_dir "/config"
prepare_dir "${OCR_COPY_CLIENT_DIR:-}"
mkdir -p /tmp/tdarr-subtitle-ocr
chown -R tdarr:tdarr /tmp/tdarr-subtitle-ocr /config 2>/dev/null || true

exec runuser -u tdarr -- "$@"
