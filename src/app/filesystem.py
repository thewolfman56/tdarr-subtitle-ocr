from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from .config import Settings
from .security import ensure_within_allowed_roots


def validate_input_path(raw_path: str, settings: Settings) -> Path:
    resolved = ensure_within_allowed_roots(Path(raw_path), settings.allowed_roots)

    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input file was not found.")

    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input path must be a file.")

    extension = resolved.suffix.lower()
    if extension not in {value.lower() for value in settings.allowed_extensions}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input extension '{extension}' is not allowed.",
        )

    size_limit_bytes = settings.max_input_size_mb * 1024 * 1024
    size_bytes = resolved.stat().st_size
    if size_bytes > size_limit_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Input file exceeds the configured size limit of {settings.max_input_size_mb} MB.",
        )

    return resolved


def validate_output_path(raw_path: str, settings: Settings) -> Path:
    resolved = ensure_within_allowed_roots(Path(raw_path), settings.allowed_roots)
    parent = resolved.parent

    if not parent.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Output directory '{parent}' does not exist.",
        )

    if not parent.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Output parent must be a directory.")

    return resolved
