"""llmfit Hardware Probe Wrapper

Thin wrapper around llmfit.hardware.probe_hardware() that returns
the same Dict[str, Any] format as HardwareDetector.detect().

llmfit detects RAM, CPU (AVX2/AVX-512/NEON), GPU VRAM (NVIDIA/AMD/Apple),
disk speed, and available backends -- all in a single call.
"""
import logging
import platform
from typing import Dict, Any
import psutil

logger = logging.getLogger(__name__)


def detect_via_llmfit() -> Dict[str, Any]:
    """Probe hardware via llmfit and return SovereignAI-compatible profile.

    Falls back to existing HardwareDetector if llmfit is not installed.
    """
    try:
        from llmfit.hardware import probe_hardware

        hw = probe_hardware()

        def field(name: str, fallback):
            # `or`, not just the getattr default: llmfit sets several of these to
            # None on a machine it cannot classify, and an attribute that exists
            # but is None would otherwise reach HardwareProfile and make
            # /v1/system/hardware raise a ValidationError.
            return getattr(hw, name, None) or fallback

        features = (getattr(hw, "cpu_features", "") or "").lower()
        profile = {
            "cpu_name": field("cpu_name", platform.processor() or "Unknown CPU"),
            "cpu_cores": field("cpu_cores", psutil.cpu_count(logical=False) or 1),
            "cpu_threads": field("cpu_threads", psutil.cpu_count(logical=True) or 1),
            "has_avx2": "avx2" in features,
            "has_avx512": "avx512" in features,
            "ram_total_gb": field("ram_total_gb", round(psutil.virtual_memory().total / (1024**3), 2)),
            "gpu_name": field("gpu_name", None),
            "gpu_vram_gb": field("gpu_vram_gb", None),
            # Never inferred from speed: a fast disk is not proof of an SSD, and
            # DiskDetector's own probe is the thing that actually knows.
            "disk_type": field("disk_type", "Unknown"),
            "disk_speed_mb_s": field("disk_speed_mb_s", 0.0),
            "available_backends": getattr(hw, "available_backends", []),
            "_source": "llmfit",
        }
        return profile
    except ImportError as exc:
        # Expected on most installs: the PyPI `llmfit` package is a CLI wrapper
        # with no `hardware` module. The legacy detector below covers it.
        logger.debug("llmfit probe unavailable (%s); falling back to HardwareDetector", exc)
        return {"_source": "unavailable"}
    except Exception as exc:
        logger.warning("llmfit probe failed: %s", exc)
        return {"_source": "error", "_error": str(exc)}


def detect_hardware() -> Dict[str, Any]:
    """Top-level hardware detection.

    Prefers llmfit for richer detection (GPU, disk, backends).
    Falls back to HardwareDetector when llmfit unavailable.
    """
    result = detect_via_llmfit()
    if result.get("_source") == "llmfit":
        return result

    # Fallback
    from app.core.hardware_detector import HardwareDetector
    fallback = HardwareDetector().detect()
    fallback["_source"] = "legacy"
    return fallback
