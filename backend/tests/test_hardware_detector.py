"""Hardware detection tests (fast).

Regression coverage for the System page showing wrong CPU/Storage details:
the Windows path used to hard-code AVX2/AVX-512 as unsupported and return
"Unknown" for the disk type, even on CPUs/disks that report otherwise. The GPU
cases cover the AMD/Intel fallback for machines with no nvidia-smi.
"""
import platform
import subprocess
from types import SimpleNamespace

import pytest

from app.core import hardware_detector
from app.core.hardware_detector import HardwareDetector


def _numpy_cpu_features():
    try:  # numpy >= 2.0
        from numpy._core._multiarray_umath import __cpu_features__
    except ImportError:  # numpy < 2.0
        from numpy.core._multiarray_umath import __cpu_features__
    return __cpu_features__


def test_cpu_has_mirrors_the_platforms_real_answer():
    """On non-Linux, _cpu_has must agree with numpy's CPU feature table."""
    if platform.system() == "Linux":
        pytest.skip("Linux reads /proc/cpuinfo; covered by the Linux run itself")
    features = _numpy_cpu_features()
    hw = HardwareDetector()
    assert hw._cpu_has("AVX2") == bool(features.get("AVX2"))
    assert hw._cpu_has("AVX512F") == bool(features.get("AVX512F"))


def test_avx2_is_not_hardcoded_false_on_a_supported_cpu():
    if not _numpy_cpu_features().get("AVX2"):
        pytest.skip("CPU has no AVX2 to detect")
    assert HardwareDetector()._check_avx2() is True


def test_detect_returns_the_full_profile(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "workspace_dir", tmp_path)
    profile = HardwareDetector().detect()

    for key in ("cpu_name", "cpu_cores", "cpu_threads", "has_avx2", "has_avx512",
                "ram_total_gb", "gpu_name", "gpu_vram_gb", "disk_type",
                "disk_speed_mb_s"):
        assert key in profile, f"missing {key}"
    assert isinstance(profile["has_avx2"], bool)
    assert isinstance(profile["has_avx512"], bool)
    assert profile["ram_total_gb"] > 0


def test_disk_type_never_reports_unknown_when_a_speed_is_known(tmp_path, monkeypatch):
    """No probe answer => the measured sequential write decides, not 'Unknown'.

    Each scenario gets its own workspace so the per-machine cache (which is the
    whole point of the caching) does not short-circuit the second case.
    """
    from app import config

    hw = HardwareDetector()
    monkeypatch.setattr(hw, "_probe_disk_type", lambda: "Unknown")

    monkeypatch.setattr(config.settings, "workspace_dir", tmp_path / "fast")
    assert hw._detect_disk_type(300.0) == "SSD"

    monkeypatch.setattr(config.settings, "workspace_dir", tmp_path / "slow")
    assert hw._detect_disk_type(50.0) == "HDD"


# --------------------------------------------------------------------------- #
# GPU
# --------------------------------------------------------------------------- #

def _no_nvidia_smi(*args, **kwargs):
    raise FileNotFoundError("nvidia-smi")


def test_gpu_falls_back_when_nvidia_smi_is_absent(monkeypatch):
    """AMD/Intel machines have no nvidia-smi; the card used to read "None"."""
    hw = HardwareDetector()
    monkeypatch.setattr(hardware_detector.subprocess, "run", _no_nvidia_smi)
    monkeypatch.setattr(hw, "_probe_gpu_name", lambda: "AMD Radeon RX 6600")

    assert hw._query_gpu() == ("AMD Radeon RX 6600", None)


def test_gpu_falls_back_when_nvidia_smi_lists_nothing(monkeypatch):
    hw = HardwareDetector()
    monkeypatch.setattr(
        hardware_detector.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=""),
    )
    monkeypatch.setattr(hw, "_probe_gpu_name", lambda: "Intel(R) UHD Graphics 630")

    assert hw._query_gpu() == ("Intel(R) UHD Graphics 630", None)


def test_probe_gpu_name_skips_software_adapters(monkeypatch):
    """A GPU-less session must report nothing, not the Microsoft basic adapter."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hardware_detector.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="Microsoft Basic Display Adapter|Intel(R) UHD Graphics 620",
        ),
    )
    assert HardwareDetector()._probe_gpu_name() == "Intel(R) UHD Graphics 620"


def test_probe_gpu_name_returns_none_when_only_software_adapters(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        hardware_detector.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="Microsoft Basic Display Adapter|",
        ),
    )
    assert HardwareDetector()._probe_gpu_name() is None


def test_probe_gpu_name_never_raises_without_the_tool(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(hardware_detector.subprocess, "run", _no_nvidia_smi)
    assert HardwareDetector()._probe_gpu_name() is None


def test_gpu_vram_is_only_reported_by_nvidia_smi(monkeypatch):
    """A vendor-agnostic name must not come with a guessed VRAM figure."""
    hw = HardwareDetector()
    monkeypatch.setattr(
        hardware_detector.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="NVIDIA GeForce GTX 1650, 4096\n"
        ),
    )
    assert hw._query_gpu() == ("NVIDIA GeForce GTX 1650", 4.0)


def test_disk_type_caches_the_probe_result(tmp_path, monkeypatch):
    from app import config
    import json

    monkeypatch.setattr(config.settings, "workspace_dir", tmp_path)
    calls = []

    def probe():
        calls.append(1)
        return "SSD"

    hw = HardwareDetector()
    monkeypatch.setattr(hw, "_probe_disk_type", probe)

    assert hw._detect_disk_type() == "SSD"
    assert hw._detect_disk_type() == "SSD"          # served from cache
    assert len(calls) == 1, "probe must run once per machine, not per launch"
    assert json.loads((tmp_path / ".hw_cache.json").read_text())["hardware_disk_type"] == "SSD"
