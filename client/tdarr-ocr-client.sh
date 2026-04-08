#!/usr/bin/env sh
set -eu

usage() {
  echo "Usage: tdarr-ocr-client.sh --input <path> --output <path> --language <code> [--language2 <code>] [--language3 <code>]" >&2
}

INPUT=""
OUTPUT=""
LANGUAGE=""
LANGUAGE2=""
LANGUAGE3=""
ENDPOINT="${TDARR_OCR_ENDPOINT:-http://tdarr-subtitle-ocr:8484/v1/ocr}"
TIMEOUT="${TDARR_OCR_TIMEOUT_SECONDS:-3700}"
AUTH_HEADER=""

if [ -n "${TDARR_OCR_API_TOKEN:-}" ]; then
  AUTH_HEADER="Authorization: Bearer ${TDARR_OCR_API_TOKEN}"
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --input)
      INPUT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --language)
      LANGUAGE="$2"
      shift 2
      ;;
    --language2)
      LANGUAGE2="$2"
      shift 2
      ;;
    --language3)
      LANGUAGE3="$2"
      shift 2
      ;;
    *)
      usage
      exit 64
      ;;
  esac
done

if [ -z "$INPUT" ] || [ -z "$OUTPUT" ] || [ -z "$LANGUAGE" ]; then
  usage
  exit 64
fi

BODY=$(printf '{"input_path":"%s","output_path":"%s","language":"%s","language2":"%s","language3":"%s"}' \
  "$(printf '%s' "$INPUT" | sed 's/\\/\\\\/g; s/"/\\"/g')" \
  "$(printf '%s' "$OUTPUT" | sed 's/\\/\\\\/g; s/"/\\"/g')" \
  "$(printf '%s' "$LANGUAGE" | sed 's/\\/\\\\/g; s/"/\\"/g')" \
  "$(printf '%s' "$LANGUAGE2" | sed 's/\\/\\\\/g; s/"/\\"/g')" \
  "$(printf '%s' "$LANGUAGE3" | sed 's/\\/\\\\/g; s/"/\\"/g')"
)

if [ -n "$AUTH_HEADER" ]; then
  curl --fail --silent --show-error \
    --max-time "$TIMEOUT" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    "$ENDPOINT" >/dev/null
else
  curl --fail --silent --show-error \
    --max-time "$TIMEOUT" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    "$ENDPOINT" >/dev/null
fi
