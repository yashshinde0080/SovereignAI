import os
import psutil

class HardwareDetector:
    def __init__(self):
        self.profile = self._detect()

    def _detect(self):
        ram = psutil.virtual_memory()
        cpu_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        # Note: In a real implementation we would benchmark disk speed and check for GPU/AVX2
        # This is a stubbed hardware profile based on psutil info.
        return {
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_available_gb": round(ram.available / (1024**3), 2),
            "cpu_cores": cpu_cores,
            "logical_cores": logical_cores,
            "disk_speed_mb_s": 1500, # Mock SSD speed
            "gpu": "None", # Mock GPU
            "avx2": True # Mock AVX2 support
        }

    def get_profile(self):
        return self.profile

    def get_live_metrics(self):
        ram = psutil.virtual_memory()
        return {
            "ram_usage_gb": round((ram.total - ram.available) / (1024**3), 2),
            "ram_percent": ram.percent,
            "cpu_percent": psutil.cpu_percent(interval=None)
        }
