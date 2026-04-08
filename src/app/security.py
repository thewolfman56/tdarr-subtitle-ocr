from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import HTTPException, status

from .config import Settings


def require_api_token(settings: Settings, authorization: str | None) -> None:
    if not settings.api_token:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
        )


def ensure_within_allowed_roots(path: Path, allowed_roots: list[Path]) -> Path:
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Path '{resolved}' is outside the allowed roots.",
    )
