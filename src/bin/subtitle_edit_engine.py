#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

IMAGE_SUBTITLE_CODECS = {
    "hdmv_pgs_subtitle",
    "dvd_subtitle",
    "xsub",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Subtitle Edit OCR engine wrapper.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--subtitle-edit-bin", default="/opt/subtitleedit/SubtitleEdit.exe")
    parser.add_argument("--xvfb-run-bin", default="/usr/bin/xvfb-run")
    parser.add_argument("--mono-bin", default="/usr/bin/mono")
    parser.add_argument("--timeout", type=int, default=3600)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="subtitle-edit-ocr-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        source_for_convert = choose_input_path(input_path, temp_dir, args.language)
        runtime_bin = prepare_runtime_subtitle_edit(Path(args.subtitle_edit_bin).resolve())
        command = [
            args.xvfb_run_bin,
            "-a",
            args.mono_bin,
            str(runtime_bin),
            "/convert",
            str(source_for_convert),
            "subrip",
            f"/outputfolder:{temp_dir}",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(completed.stderr.strip() or completed.stdout.strip() or "Subtitle Edit failed.")

        generated = find_generated_srt(temp_dir)
        if generated is None:
            raise SystemExit("Subtitle Edit completed but no SRT output was found.")

        shutil.move(str(generated), str(output_path))

    print("ENGINE:subtitleedit")
    return 0


def choose_input_path(input_path: Path, temp_dir: Path, language: str) -> Path:
    if input_path.suffix.lower() == ".mkv":
        return extract_subtitle_only_container(input_path, temp_dir, language)

    if input_path.suffix.lower() == ".sub":
        companion_idx = input_path.with_suffix(".idx")
        if companion_idx.exists():
            return companion_idx
    return input_path


def extract_subtitle_only_container(input_path: Path, temp_dir: Path, language: str) -> Path:
    stream = select_subtitle_stream(input_path, language)
    stream_index = stream["index"]
    extracted_path = temp_dir / "subtitle-track.mkv"

    command = [
        "/usr/bin/ffmpeg",
        "-y",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-map",
        f"0:{stream_index}",
        "-c",
        "copy",
        str(extracted_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Failed to extract subtitle stream {stream_index} from '{input_path.name}'."
        )

    return extracted_path


def select_subtitle_stream(input_path: Path, language: str) -> dict[str, object]:
    command = [
        "/usr/bin/ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title",
        "-of",
        "json",
        str(input_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            completed.stderr.strip()
            or completed.stdout.strip()
            or f"Failed to inspect subtitle streams in '{input_path.name}'."
        )

    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams", [])
    if not streams:
        raise SystemExit(f"No subtitle streams were found in '{input_path.name}'.")

    preferred = normalize_language(language)
    image_streams = [stream for stream in streams if stream.get("codec_name") in IMAGE_SUBTITLE_CODECS]
    if not image_streams:
        raise SystemExit(
            f"No image-based subtitle streams were found in '{input_path.name}'. Available codecs: "
            + ", ".join(sorted({str(stream.get('codec_name', 'unknown')) for stream in streams}))
        )

    for stream in image_streams:
        tags = stream.get("tags") or {}
        if normalize_language(str(tags.get("language", ""))) == preferred:
            return stream

    return image_streams[0]


def normalize_language(value: str) -> str:
    lowered = value.strip().lower()
    aliases = {
        "en": "eng",
        "english": "eng",
    }
    return aliases.get(lowered, lowered)


def prepare_runtime_subtitle_edit(source_exe: Path) -> Path:
    runtime_root = Path(os.environ.get("OCR_JOB_DIR", tempfile.gettempdir())).resolve() / "subtitleedit-runtime"
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    shutil.copytree(source_exe.parent, runtime_root)
    return runtime_root / source_exe.name


def find_generated_srt(temp_dir: Path) -> Path | None:
    srt_files = sorted(temp_dir.glob("*.srt"))
    return srt_files[0] if srt_files else None


if __name__ == "__main__":
    raise SystemExit(main())
