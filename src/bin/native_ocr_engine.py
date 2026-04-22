#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = SCRIPT_ROOT / "src"
for candidate in (SCRIPT_ROOT, SOURCE_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

IMAGE_EXTENSIONS = {".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native OCR engine wrapper using ONNX Runtime CPU.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    recognizer = build_cpu_ocr()

    if input_path.suffix.lower() == ".json":
        write_manifest_srt(recognizer, input_path, output_path)
    elif input_path.suffix.lower() in IMAGE_EXTENSIONS:
        text = recognize_text(recognizer, input_path)
        write_single_image_srt(text, output_path)
    else:
        raise SystemExit(
            f"Native OCR engine only supports raster images or manifest JSON inputs. Got '{input_path.suffix}'."
        )

    print("ENGINE:native-onnxruntime-rapidocr")
    return 0


def build_cpu_ocr():
    ort = importlib.import_module("onnxruntime")
    preload = getattr(ort, "preload_dlls", None)
    if callable(preload):
        try:
            preload()
        except Exception:
            pass

    module = importlib.import_module("rapidocr_onnxruntime")
    rapid_ocr_cls = getattr(module, "RapidOCR")

    constructor_kwargs = {}
    try:
        signature = inspect.signature(rapid_ocr_cls)
        if "providers" in signature.parameters:
            constructor_kwargs["providers"] = ["CPUExecutionProvider"]
    except (TypeError, ValueError):
        pass

    return rapid_ocr_cls(**constructor_kwargs)


def write_manifest_srt(recognizer: Any, input_path: Path, output_path: Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    cues = payload["cues"] if isinstance(payload, dict) else payload
    lines: list[str] = []
    cue_index = 0

    for cue in cues:
        image_path = Path(cue["image_path"]).resolve()
        text = recognize_text(recognizer, image_path).strip()
        if not text:
            continue
        cue_index += 1
        lines.extend(
            [
                str(cue_index),
                f"{format_timestamp_ms(int(cue['start_ms']))} --> {format_timestamp_ms(int(cue['end_ms']))}",
                text,
                "",
            ]
        )

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_single_image_srt(text: str, output_path: Path) -> None:
    content = "\n".join(
        [
            "1",
            "00:00:00,000 --> 00:00:05,000",
            text.strip() or "[NO OCR TEXT DETECTED]",
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")


def recognize_text(recognizer: Any, image_path: Path) -> str:
    result = recognizer(str(image_path))
    entries = normalize_ocr_result(result)
    texts = [entry for entry in entries if entry]
    return "\n".join(texts)


def normalize_ocr_result(result: Any) -> list[str]:
    if result is None:
        return []

    if isinstance(result, tuple) and result:
        return normalize_ocr_result(result[0])

    if isinstance(result, str):
        return [result]

    if isinstance(result, list):
        texts: list[str] = []
        for item in result:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, (list, tuple)):
                if len(item) >= 2 and isinstance(item[1], str):
                    texts.append(item[1])
                elif len(item) >= 2 and isinstance(item[1], (list, tuple)) and item[1]:
                    candidate = item[1][0]
                    if isinstance(candidate, str):
                        texts.append(candidate)
            elif isinstance(item, dict):
                candidate = item.get("text") or item.get("txt")
                if isinstance(candidate, str):
                    texts.append(candidate)
        return texts

    if isinstance(result, dict):
        candidate = result.get("text") or result.get("txt")
        return [candidate] if isinstance(candidate, str) else []

    return []


def format_timestamp_ms(value: int) -> str:
    total_ms = max(0, value)
    hours = total_ms // 3_600_000
    remainder = total_ms % 3_600_000
    minutes = remainder // 60_000
    remainder %= 60_000
    seconds = remainder // 1_000
    milliseconds = remainder % 1_000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    raise SystemExit(main())
