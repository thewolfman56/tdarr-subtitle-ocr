#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.accelerators import detect_all

IMAGE_EXTENSIONS = {".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".json"}
SUBTITLE_CONTAINER_EXTENSIONS = {".sup", ".sub", ".idx", ".mkv"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-select OCR backend.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    backend_policy = os.environ.get("OCR_BACKEND_POLICY", "auto").strip().lower()
    strict_mode = os.environ.get("OCR_BACKEND_STRICT", "false").strip().lower() == "true"
    statuses = detect_all()

    if input_path.suffix.lower() in IMAGE_EXTENSIONS:
        engine = choose_gpu_engine(backend_policy, statuses, strict_mode)
        if engine:
            return run_command(
                [
                    sys.executable,
                    "/opt/tdarr-subtitle-ocr/bin/gpu_ocr_engine.py",
                    "--backend",
                    engine,
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--language",
                    args.language,
                ]
            )

    if strict_mode and backend_policy in {"nvidia", "intel", "npu"} and input_path.suffix.lower() in SUBTITLE_CONTAINER_EXTENSIONS:
        raise SystemExit(
            f"Strict mode forbids fallback, and the {backend_policy} GPU backend does not parse '{input_path.suffix}' directly."
        )

    return run_command(
        [
            sys.executable,
            "/opt/tdarr-subtitle-ocr/bin/subtitle_edit_engine.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--language",
            args.language,
        ]
    )


def choose_gpu_engine(backend_policy: str, statuses, strict_mode: bool) -> str | None:
    if backend_policy == "subtitleedit":
        return None

    requested = []
    if backend_policy == "nvidia":
        requested = ["nvidia"]
    elif backend_policy == "intel":
        requested = ["intel"]
    elif backend_policy == "npu":
        requested = ["npu"]
    else:
        requested = ["nvidia", "intel", "npu"]

    for name in requested:
        if statuses[name].available:
            return name

    if strict_mode and backend_policy in {"nvidia", "intel", "npu"}:
        raise SystemExit(statuses[backend_policy].reason)

    return None


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
