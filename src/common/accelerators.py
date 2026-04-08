from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AcceleratorStatus:
    name: str
    available: bool
    reason: str


def detect_nvidia() -> AcceleratorStatus:
    visible_devices = os.environ.get("NVIDIA_VISIBLE_DEVICES", "").strip().lower()
    driver_hint = Path("/proc/driver/nvidia/version").exists()
    if visible_devices in {"void", "none"}:
        return AcceleratorStatus("nvidia", False, "NVIDIA_VISIBLE_DEVICES disables GPU exposure.")

    if not visible_devices and not driver_hint:
        return AcceleratorStatus("nvidia", False, "No NVIDIA device exposure detected in the container.")

    try:
        ort = importlib.import_module("onnxruntime")
        providers = list(getattr(ort, "get_available_providers", lambda: [])())
    except Exception as exc:  # pragma: no cover - runtime dependency probe
        return AcceleratorStatus("nvidia", False, f"onnxruntime probe failed: {exc}")

    if "CUDAExecutionProvider" not in providers:
        return AcceleratorStatus("nvidia", False, "CUDAExecutionProvider is not available in onnxruntime.")

    return AcceleratorStatus("nvidia", True, "CUDAExecutionProvider is available.")


def detect_intel() -> AcceleratorStatus:
    dri_devices = sorted(Path("/dev/dri").glob("renderD*")) if Path("/dev/dri").exists() else []
    if not dri_devices:
        return AcceleratorStatus("intel", False, "No /dev/dri render node is available in the container.")

    try:
        ov = importlib.import_module("openvino")
        core = ov.Core()
        devices = list(getattr(core, "available_devices", []))
    except Exception as exc:  # pragma: no cover - runtime dependency probe
        return AcceleratorStatus("intel", False, f"OpenVINO probe failed: {exc}")

    if not any(device == "GPU" or device.startswith("GPU.") for device in devices):
        return AcceleratorStatus("intel", False, f"OpenVINO did not report a GPU device: {devices}")

    return AcceleratorStatus("intel", True, f"OpenVINO GPU devices available: {devices}")


def detect_all() -> dict[str, AcceleratorStatus]:
    return {
        "nvidia": detect_nvidia(),
        "intel": detect_intel(),
    }
