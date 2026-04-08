from __future__ import annotations

import asyncio
import logging
import os
import shutil
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from .config import Settings

LOGGER = logging.getLogger("tdarr_subtitle_ocr")
ENGINE_PREFIX = "ENGINE:"


@dataclass(frozen=True)
class JobResult:
    job_id: str
    engine: str
    output_path: Path
    message: str


class OcrRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_jobs)

    async def run(
        self,
        input_path: Path,
        output_path: Path,
        language: str,
        language2: str | None,
        language3: str | None,
    ) -> JobResult:
        async with self._semaphore:
            job_id = uuid.uuid4().hex
            job_dir = self.settings.job_work_root / job_id
            job_dir.mkdir(parents=True, exist_ok=False)

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._run_sync,
                        job_id,
                        job_dir,
                        input_path,
                        output_path,
                        language,
                        language2,
                        language3,
                    ),
                    timeout=self.settings.request_timeout_seconds,
                )
                return result
            except asyncio.TimeoutError as exc:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="OCR job timed out.",
                ) from exc
            finally:
                shutil.rmtree(job_dir, ignore_errors=True)

    def _run_sync(
        self,
        job_id: str,
        job_dir: Path,
        input_path: Path,
        output_path: Path,
        language: str,
        language2: str | None,
        language3: str | None,
    ) -> JobResult:
        command = self._build_command(
            input_path=input_path,
            output_path=output_path,
            language=language,
            language2=language2,
            language3=language3,
            job_dir=job_dir,
        )
        LOGGER.info("Starting OCR job %s with engine '%s'.", job_id, self.settings.preferred_engine)
        completed = asyncio.run(self._run_subprocess(command, job_dir))

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "OCR backend failed."
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OCR backend failed: {stderr}",
            )

        if not output_path.exists():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OCR backend completed without producing '{output_path}'.",
            )

        return JobResult(
            job_id=job_id,
            engine=self._parse_engine_name(completed.stdout) or self.settings.preferred_engine,
            output_path=output_path,
            message="OCR conversion completed successfully.",
        )

    async def _run_subprocess(self, command: list[str], job_dir: Path):
        env = os.environ.copy()
        env["OCR_JOB_DIR"] = str(job_dir)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(job_dir),
            env=env,
        )
        stdout, stderr = await process.communicate()
        return type(
            "Completed",
            (),
            {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            },
        )()

    def _build_command(
        self,
        input_path: Path,
        output_path: Path,
        language: str,
        language2: str | None,
        language3: str | None,
        job_dir: Path,
    ) -> list[str]:
        placeholders = {
            "input": str(input_path),
            "output": str(output_path),
            "language": language,
            "language2": language2 or "",
            "language3": language3 or "",
            "jobdir": str(job_dir),
            "subtitleedit": str(self.settings.subtitle_edit_bin),
            "tessdata": self.settings.tesseract_data_dir,
        }

        tokens = shlex.split(self.settings.backend_command, posix=True)
        command: list[str] = []
        for token in tokens:
            rendered = token
            for key, value in placeholders.items():
                rendered = rendered.replace(f"{{{key}}}", value)
            command.append(rendered)

        if not command:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OCR backend command is empty.",
            )

        return command

    def _parse_engine_name(self, stdout: str) -> str | None:
        for line in stdout.splitlines():
            if line.startswith(ENGINE_PREFIX):
                return line.removeprefix(ENGINE_PREFIX).strip()
        return None
