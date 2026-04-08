from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _split_csv(value: str) -> list[str]:
    return [entry.strip() for entry in value.split(",") if entry.strip()]


def _split_paths(value: str) -> list[Path]:
    roots: list[Path] = []
    for raw in value.split(","):
        entry = raw.strip()
        if entry:
            roots.append(Path(entry).resolve())
    return roots


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(value)
    return items


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    api_token: str
    allowed_roots: list[Path]
    allowed_extensions: list[str]
    max_input_size_mb: int
    max_jobs: int
    request_timeout_seconds: int
    job_work_root: Path
    backend_command: str
    subtitle_edit_bin: Path
    subtitle_edit_timeout_seconds: int
    tesseract_data_dir: str
    copy_client_dir: Path | None
    preferred_engine: str
    backend_policy: str
    log_level: str


def load_settings() -> Settings:
    allowed_roots_raw = os.environ.get("OCR_ALLOWED_ROOTS", "/media,/cache,/work")
    allowed_extensions_raw = os.environ.get(
        "OCR_ALLOWED_EXTENSIONS",
        ".sup,.sub,.idx,.mkv,.json,.png,.bmp,.jpg,.jpeg,.tif,.tiff,.webp",
    )

    allowed_roots = _split_paths(allowed_roots_raw)
    if not allowed_roots:
        allowed_roots = [Path("/media"), Path("/cache"), Path("/work")]

    allowed_extensions = _dedupe(
        extension if extension.startswith(".") else f".{extension}"
        for extension in _split_csv(allowed_extensions_raw)
    )

    return Settings(
        host=os.environ.get("OCR_HOST", "0.0.0.0"),
        port=int(os.environ.get("OCR_PORT", "8484")),
        api_token=os.environ.get("OCR_API_TOKEN", "").strip(),
        allowed_roots=allowed_roots,
        allowed_extensions=allowed_extensions or [
            ".sup",
            ".sub",
            ".idx",
            ".mkv",
            ".json",
            ".png",
            ".bmp",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
            ".webp",
        ],
        max_input_size_mb=int(os.environ.get("OCR_MAX_INPUT_SIZE_MB", "256")),
        max_jobs=max(1, int(os.environ.get("OCR_MAX_CONCURRENT_JOBS", "1"))),
        request_timeout_seconds=max(30, int(os.environ.get("OCR_REQUEST_TIMEOUT_SECONDS", "3600"))),
        job_work_root=Path(os.environ.get("OCR_JOB_WORK_ROOT", "/tmp/tdarr-subtitle-ocr")).resolve(),
        backend_command=os.environ.get(
            "OCR_BACKEND_COMMAND",
            "python /opt/tdarr-subtitle-ocr/bin/auto_ocr_engine.py "
            "--input {input} --output {output} --language {language}",
        ).strip(),
        subtitle_edit_bin=Path(
            os.environ.get("OCR_SUBTITLE_EDIT_BIN", "/opt/subtitleedit/SubtitleEdit.exe")
        ).resolve(),
        subtitle_edit_timeout_seconds=max(
            60,
            int(os.environ.get("OCR_SUBTITLE_EDIT_TIMEOUT_SECONDS", "3600")),
        ),
        tesseract_data_dir=os.environ.get("TESSDATA_PREFIX", "/usr/share/tesseract-ocr/5/tessdata").strip(),
        copy_client_dir=(
            Path(os.environ["OCR_COPY_CLIENT_DIR"]).resolve()
            if os.environ.get("OCR_COPY_CLIENT_DIR", "").strip()
            else None
        ),
        preferred_engine=os.environ.get("OCR_PREFERRED_ENGINE", "subtitleedit").strip().lower(),
        backend_policy=os.environ.get("OCR_BACKEND_POLICY", "auto").strip().lower(),
        log_level=os.environ.get("OCR_LOG_LEVEL", "info").strip().lower(),
    )
