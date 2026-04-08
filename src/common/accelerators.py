from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AcceleratorStatus:
    name: str
    available: bool
    reason: str
    details: dict[str, object] | None = None


def _existing_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if Path(path).exists()]


def collect_intel_debug_details() -> dict[str, object]:
    plugin_candidates = [
        "/opt/intel/openvino/runtime/lib/intel64/plugins.xml",
        "/opt/intel/openvino/runtime/lib/intel64/Release/plugins.xml",
        "/usr/lib/x86_64-linux-gnu/openvino-2024/plugins.xml",
        "/usr/lib/x86_64-linux-gnu/openvino/plugins.xml",
    ]
    library_globs = [
        "/usr/lib*/**/libopenvino_intel_gpu_plugin.so*",
        "/usr/lib*/**/libze_loader.so*",
        "/usr/lib*/**/libOpenCL.so*",
        "/usr/lib*/**/libigdgmm.so*",
        "/usr/lib*/**/libigc.so*",
    ]
    libraries: list[str] = []
    for pattern in library_globs:
        libraries.extend(str(path) for path in Path("/").glob(pattern) if path.is_file())

    return {
        "pythonExecutable": sys.executable,
        "pythonVersion": sys.version,
        "openvinoPluginXmlCandidates": _existing_paths(plugin_candidates),
        "intelGpuLibraryMatches": sorted(set(libraries))[:50],
        "ldLibraryPath": os.environ.get("LD_LIBRARY_PATH"),
    }


def detect_nvidia() -> AcceleratorStatus:
    visible_devices = os.environ.get("NVIDIA_VISIBLE_DEVICES", "").strip().lower()
    driver_hint = Path("/proc/driver/nvidia/version").exists()
    details = {
        "nvidiaVisibleDevices": visible_devices or None,
        "driverVersionPathExists": driver_hint,
    }
    if visible_devices in {"void", "none"}:
        return AcceleratorStatus(
            "nvidia",
            False,
            "NVIDIA_VISIBLE_DEVICES disables GPU exposure.",
            details,
        )

    if not visible_devices and not driver_hint:
        return AcceleratorStatus(
            "nvidia",
            False,
            "No NVIDIA device exposure detected in the container.",
            details,
        )

    try:
        ort = importlib.import_module("onnxruntime")
        providers = list(getattr(ort, "get_available_providers", lambda: [])())
        details["onnxruntimeProviders"] = providers
    except Exception as exc:  # pragma: no cover - runtime dependency probe
        return AcceleratorStatus("nvidia", False, f"onnxruntime probe failed: {exc}", details)

    if "CUDAExecutionProvider" not in providers:
        return AcceleratorStatus(
            "nvidia",
            False,
            "CUDAExecutionProvider is not available in onnxruntime.",
            details,
        )

    return AcceleratorStatus("nvidia", True, "CUDAExecutionProvider is available.", details)


def detect_intel() -> AcceleratorStatus:
    dri_devices = sorted(Path("/dev/dri").glob("renderD*")) if Path("/dev/dri").exists() else []
    details: dict[str, object] = {
        "driPathExists": Path("/dev/dri").exists(),
        "renderNodes": [str(path) for path in dri_devices],
    }
    details.update(collect_intel_debug_details())
    if not dri_devices:
        return AcceleratorStatus(
            "intel",
            False,
            "No /dev/dri render node is available in the container.",
            details,
        )

    try:
        ov = importlib.import_module("openvino")
        core = ov.Core()
        devices = list(getattr(core, "available_devices", []))
        details["openvinoAvailableDevices"] = devices
    except Exception as exc:  # pragma: no cover - runtime dependency probe
        return AcceleratorStatus("intel", False, f"OpenVINO probe failed: {exc}", details)

    if not any(device == "GPU" or device.startswith("GPU.") for device in devices):
        return AcceleratorStatus(
            "intel",
            False,
            f"OpenVINO did not report a GPU device: {devices}",
            details,
        )

    return AcceleratorStatus("intel", True, f"OpenVINO GPU devices available: {devices}", details)


def detect_all() -> dict[str, AcceleratorStatus]:
    return {
        "nvidia": detect_nvidia(),
        "intel": detect_intel(),
    }
