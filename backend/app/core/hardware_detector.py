"""Hardware Detection"""
import os
import platform
import subprocess
import json
from typing import Dict, Any, Optional
import psutil


class HardwareDetector:
    """Detect system hardware capabilities"""

    def __init__(self):
        self._hw_cache: Optional[Dict[str, Any]] = None

    def detect(self) -> Dict[str, Any]:
        """Detect and return hardware profile (cached after first call)."""
        if self._hw_cache is not None:
            return self._hw_cache
        gpu_name, gpu_vram = self._query_gpu()
        disk_speed = self._cached_disk_speed()
        profile = {
            "cpu_name": self._get_cpu_name(),
            "cpu_cores": psutil.cpu_count(logical=False) or 1,
            "cpu_threads": psutil.cpu_count(logical=True) or 1,
            "has_avx2": self._check_avx2(),
            "has_avx512": self._check_avx512(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "gpu_name": gpu_name,
            "gpu_vram_gb": gpu_vram,
            "disk_type": self._detect_disk_type(disk_speed),
            "disk_speed_mb_s": disk_speed
        }
        self._hw_cache = profile
        return profile

    def _query_gpu(self) -> tuple[Optional[str], Optional[float]]:
        """GPU name + VRAM.

        nvidia-smi first — the only source that reports real VRAM. It only
        exists on NVIDIA driver installs, so an AMD/Intel/software adapter used
        to report nothing at all (the dashboard showed "None"); fall back to a
        vendor-agnostic adapter listing before giving up.
        """
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = [p.strip() for p in result.stdout.strip().split(",")]
                # An empty/blank listing leaves parts == [''] — truthy, which is
                # why an unnamed GPU used to be reported as "".
                if parts and parts[0]:
                    vram = None
                    if len(parts) > 1 and parts[1]:
                        try:
                            vram = round(float(parts[1]) / 1024, 2)
                        except ValueError:
                            vram = None
                    return parts[0], vram
        except Exception:
            pass
        return self._probe_gpu_name(), None

    def _probe_gpu_name(self) -> Optional[str]:
        """First real display adapter, or None. Vendor-agnostic (AMD/Intel/other).

        Software fallbacks ("Microsoft Basic Display Adapter", RDP's remote
        display) are skipped so a GPU-less session is not reported as a GPU.
        """
        try:
            system = platform.system()
            if system == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "(Get-CimInstance Win32_VideoController | "
                     "Select-Object -ExpandProperty Name) -join '|'"],
                    capture_output=True, text=True, timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                candidates = (result.stdout or "").split("|")
            elif system == "Linux":
                result = subprocess.run(
                    ["lspci"], capture_output=True, text=True, timeout=5
                )
                candidates = [
                    line.split(": ", 1)[-1]
                    for line in (result.stdout or "").splitlines()
                    if "VGA compatible controller" in line or "3D controller" in line
                ]
            else:
                return None

            for name in candidates:
                name = name.strip()
                lowered = name.lower()
                if not name or "basic display" in lowered or "remote display" in lowered:
                    continue
                return name
        except Exception:
            pass
        return None
    
    def _get_cpu_name(self) -> str:
        """Get CPU name"""
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                )
                return winreg.QueryValueEx(key, "ProcessorNameString")[0]
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            elif platform.system() == "Darwin":
                return subprocess.check_output(
                    ["sysctl", "-n", "machdep.cpu.brand_string"]
                ).decode().strip()
        except Exception:
            pass
        return platform.processor() or "Unknown CPU"
    
    def _cpu_has(self, feature: str) -> bool:
        """True when the CPU exposes an instruction-set feature.

        Linux reads /proc/cpuinfo. Everywhere else (Windows/macOS) we ask
        numpy's CPU feature table — numpy is already a hard dependency and that
        table is what the interpreter itself detected, so no cpuid plumbing is
        needed. Windows previously returned a hard-coded False here, which is
        why the System page reported AVX2/AVX-512 as unsupported on CPUs that
        support them.
        """
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    return feature.lower() in f.read().lower()
            try:  # numpy >= 2.0
                from numpy._core._multiarray_umath import __cpu_features__
            except ImportError:  # numpy < 2.0
                from numpy.core._multiarray_umath import __cpu_features__
            return bool(__cpu_features__.get(feature))
        except Exception:
            return False

    def _check_avx2(self) -> bool:
        """Check AVX2 support"""
        return self._cpu_has("AVX2")
    
    def _check_avx512(self) -> bool:
        """Check AVX512 support"""
        return self._cpu_has("AVX512F")
    
    def _detect_disk_type(self, speed_mb_s: float = 0.0) -> str:
        """Detect disk type (SSD/HDD), cached to .hw_cache.json.

        Linux answers from the rotational flag. Windows has no cheap equivalent
        (Get-PhysicalDisk spawns PowerShell, ~1.5s), so the probe result is
        cached next to the disk-speed entry — it runs once per machine rather
        than on every launch. Falls back to the measured sequential write when
        the probe cannot answer (HDDs top out well under 200 MB/s).
        """
        cache_key = "hardware_disk_type"
        from app.config import settings
        cache_file = settings.workspace_dir / ".hw_cache.json"
        try:
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    cached = json.load(f)
                if cached.get(cache_key):
                    return cached[cache_key]
        except Exception:
            pass

        disk = self._probe_disk_type()
        if disk == "Unknown" and speed_mb_s > 0:
            disk = "SSD" if speed_mb_s > 200 else "HDD"

        try:
            os.makedirs(os.path.dirname(str(cache_file)), exist_ok=True)
            cached = {}
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    cached = json.load(f)
            cached[cache_key] = disk
            with open(cache_file, "w") as f:
                json.dump(cached, f)
        except Exception:
            pass
        return disk

    def _probe_disk_type(self) -> str:
        """One-shot platform probe; 'Unknown' when the platform has no answer."""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["cat", "/sys/block/sda/queue/rotational"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return "HDD" if result.stdout.strip() == "1" else "SSD"
            elif platform.system() == "Windows":
                # MediaType is "SSD"/"HDD"/"Unspecified"; wmic is gone on
                # newer Windows 11 builds, so use the Storage module.
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "(Get-PhysicalDisk -ErrorAction SilentlyContinue | "
                     "Select-Object -First 1 -ExpandProperty MediaType)"],
                    capture_output=True, text=True, timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                media = (result.stdout or "").strip().upper()
                if media in ("SSD", "HDD"):
                    return media
        except Exception:
            pass
        return "Unknown"
    
    def _cached_disk_speed(self) -> float:
        """Disk benchmark, cached to DB after first run."""
        cache_key = "hardware_disk_speed"
        from app.config import settings
        cache_file = str(settings.workspace_dir / ".hw_cache.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    cached = json.load(f)
                if cache_key in cached:
                    return cached[cache_key]
        except Exception:
            pass

        speed = self._benchmark_disk_speed()

        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            cached = {}
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    cached = json.load(f)
            cached[cache_key] = speed
            with open(cache_file, "w") as f:
                json.dump(cached, f)
        except Exception:
            pass
        return speed

    def _benchmark_disk_speed(self) -> float:
        """Quick disk speed benchmark (10MB write test)."""
        import tempfile
        import time

        try:
            data = b"x" * (10 * 1024 * 1024)  # 10MB
            with tempfile.NamedTemporaryFile(delete=True) as f:
                start = time.perf_counter()
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
                elapsed = time.perf_counter() - start
            speed = (10 / elapsed) if elapsed > 0 else 0
            return round(speed, 2)
        except Exception:
            return 0.0