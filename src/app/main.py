from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, Header

from .config import Settings, load_settings
from .filesystem import validate_input_path, validate_output_path
from .models import OcrRequest, OcrResponse
from .runner import OcrRunner
from .security import require_api_token
from src.common.accelerators import detect_all

settings = load_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(title="Tdarr Subtitle OCR", version="1.0.0")
runner = OcrRunner(settings)


def verify_token(authorization: str | None = Header(default=None)) -> None:
    require_api_token(settings, authorization)


def _copy_client_script_if_needed(current_settings: Settings) -> None:
    if not current_settings.copy_client_dir:
        return

    source = Path("/opt/tdarr-subtitle-ocr/client/tdarr-ocr-client.sh")
    destination_dir = current_settings.copy_client_dir
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name

    if not destination.exists() or source.read_bytes() != destination.read_bytes():
        shutil.copy2(source, destination)
        destination.chmod(0o755)


@app.on_event("startup")
def startup() -> None:
    settings.job_work_root.mkdir(parents=True, exist_ok=True)
    _copy_client_script_if_needed(settings)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    accelerators = detect_all()
    return {
        "ok": True,
        "engine": settings.preferred_engine,
        "backendPolicy": settings.backend_policy,
        "allowedRoots": [str(root) for root in settings.allowed_roots],
        "allowedExtensions": settings.allowed_extensions,
        "accelerators": {
            name: {"available": status.available, "reason": status.reason}
            for name, status in accelerators.items()
        },
    }


@app.post("/v1/ocr", response_model=OcrResponse, dependencies=[Depends(verify_token)])
async def ocr(payload: OcrRequest) -> OcrResponse:
    input_path = validate_input_path(payload.input_path, settings)
    output_path = validate_output_path(payload.output_path, settings)

    result = await runner.run(
        input_path=input_path,
        output_path=output_path,
        language=payload.language,
        language2=payload.language2,
        language3=payload.language3,
    )

    return OcrResponse(
        ok=True,
        job_id=result.job_id,
        engine=result.engine,
        output_path=str(result.output_path),
        message=result.message,
    )
