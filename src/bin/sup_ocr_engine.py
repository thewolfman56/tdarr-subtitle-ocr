#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native SUP OCR engine wrapper.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    job_dir = Path(os.environ.get("OCR_JOB_DIR", "/tmp")).resolve()
    work_dir = job_dir / "sup-native-ocr"
    work_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = build_sup_manifest(input_path, work_dir)
    command = [
        sys.executable,
        "/opt/tdarr-subtitle-ocr/bin/native_ocr_engine.py",
        "--input",
        str(manifest_path),
        "--output",
        str(output_path),
        "--language",
        args.language,
    ]
    completed = subprocess.run(command, check=False)
    return completed.returncode


def build_sup_manifest(input_path: Path, work_dir: Path) -> Path:
    packets = inspect_sup_packets(input_path)
    image_dir = work_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    extract_sup_images(input_path, image_dir)

    images = sorted(image_dir.glob("*.png"))
    if not images:
        raise SystemExit(f"No subtitle images were extracted from '{input_path.name}'.")

    cue_count = min(len(images), len(packets))
    cues = []
    for index in range(cue_count):
        packet = packets[index]
        cues.append(
            {
                "image_path": str(images[index].resolve()),
                "start_ms": packet["start_ms"],
                "end_ms": packet["end_ms"],
            }
        )

    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"cues": cues}, indent=2), encoding="utf-8")
    return manifest_path


def inspect_sup_packets(input_path: Path) -> list[dict[str, int]]:
    command = [
        "/usr/bin/ffprobe",
        "-v",
        "error",
        "-show_entries",
        "packet=pts_time,duration_time",
        "-of",
        "json",
        str(input_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Failed to inspect subtitle packet timing in '{input_path.name}'."
        )

    payload = json.loads(completed.stdout or "{}")
    packets = payload.get("packets", [])
    if not packets:
        raise SystemExit(f"No subtitle packets were found in '{input_path.name}'.")

    cues: list[dict[str, int]] = []
    for index, packet in enumerate(packets):
        start_ms = seconds_to_ms(packet.get("pts_time"))
        duration_ms = seconds_to_ms(packet.get("duration_time"))
        if duration_ms <= 0 and index + 1 < len(packets):
            next_start_ms = seconds_to_ms(packets[index + 1].get("pts_time"))
            duration_ms = max(100, next_start_ms - start_ms)
        if duration_ms <= 0:
            duration_ms = 2000
        cues.append({"start_ms": start_ms, "end_ms": start_ms + duration_ms})

    return cues


def extract_sup_images(input_path: Path, image_dir: Path) -> None:
    command = [
        "/usr/bin/ffmpeg",
        "-y",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vsync",
        "0",
        str(image_dir / "%06d.png"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Failed to extract subtitle images from '{input_path.name}'."
        )


def seconds_to_ms(value: str | None) -> int:
    if not value:
        return 0
    return int(float(value) * 1000)


if __name__ == "__main__":
    raise SystemExit(main())
