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
        profile = {
            "cpu_name": self._get_cpu_name(),
            "cpu_cores": psutil.cpu_count(logical=False) or 1,
            "cpu_threads": psutil.cpu_count(logical=True) or 1,
            "has_avx2": self._check_avx2(),
            "has_avx512": self._check_avx512(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "gpu_name": gpu_name,
            "gpu_vram_gb": gpu_vram,
            "disk_type": self._detect_disk_type(),
            "disk_speed_mb_s": self._cached_disk_speed()
        }
        self._hw_cache = profile
        return profile

    def _query_gpu(self) -> tuple[Optional[str], Optional[float]]:
        """Single nvidia-smi call for both name and VRAM."""
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    return parts[0].strip(), round(float(parts[1].strip()) / 1024, 2)
                elif parts:
                    return parts[0].strip(), None
        except Exception:
            pass
        return None, None
    
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
    
    def _check_avx2(self) -> bool:
        """Check AVX2 support"""
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    return "avx2" in f.read().lower()
            elif platform.system() == "Windows":
                return False  # conservative: no easy check without cpuid
        except Exception:
            pass
        return False
    
    def _check_avx512(self) -> bool:
        """Check AVX512 support"""
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    return "avx512" in f.read().lower()
        except Exception:
            pass
        return False
    
    def _detect_disk_type(self) -> str:
        """Detect disk type (SSD/HDD)"""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["cat", "/sys/block/sda/queue/rotational"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return "HDD" if result.stdout.strip() == "1" else "SSD"
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