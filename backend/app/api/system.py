"""System API Endpoints"""
import time

import psutil
from fastapi import APIRouter, Request

from app.schemas.system import (
    HardwareProfile,
    SystemStatus,
    ResourceUsage
)


router = APIRouter()

# Previous disk counters, for turning psutil's cumulative byte totals into a
# throughput. psutil.disk_io_counters() counts since boot, so the raw value is
# "total MB" — reporting it as MB/s made the dashboard show ~48000 MB/s.
_prev_disk_io = None


def _disk_rates_mb_s() -> tuple[float, float]:
    """Read/write throughput in MB/s since the previous call (0 on a cold call)."""
    global _prev_disk_io
    io = psutil.disk_io_counters()
    if io is None:
        return 0.0, 0.0

    now = time.monotonic()
    read_mb_s = write_mb_s = 0.0
    if _prev_disk_io is not None:
        prev_at, prev_read, prev_write = _prev_disk_io
        elapsed = now - prev_at
        if elapsed > 0:
            read_mb_s = max(0, io.read_bytes - prev_read) / (1024 ** 2) / elapsed
            write_mb_s = max(0, io.write_bytes - prev_write) / (1024 ** 2) / elapsed
    _prev_disk_io = (now, io.read_bytes, io.write_bytes)
    return round(read_mb_s, 2), round(write_mb_s, 2)


@router.get("/hardware", response_model=HardwareProfile)
async def get_hardware(request: Request):
    """Get hardware profile"""
    return HardwareProfile(**request.app.state.hardware_profile)


@router.get("/status", response_model=SystemStatus)
async def get_status(request: Request):
    """Get system status"""
    app = request.app
    
    # Get current resource usage
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(app.state.model_manager.models_dir))
    
    engine_stats = {}
    task_type = None
    is_generative = False
    
    if app.state.active_engine:
        engine_stats = app.state.active_engine.get_stats()
        task_metadata = getattr(app.state.active_engine, "task_metadata", {})
        task_type = task_metadata.get("task_type")
        is_generative = task_metadata.get("is_generative", False)
    
    return SystemStatus(
        model_loaded=app.state.active_model is not None,
        current_model=app.state.active_model,
        current_mode=app.state.active_mode,
        task_type=task_type,
        is_generative=is_generative,
        ram_total_gb=round(memory.total / (1024**3), 2),
        ram_used_gb=round(memory.used / (1024**3), 2),
        ram_available_gb=round(memory.available / (1024**3), 2),
        disk_total_gb=round(disk.total / (1024**3), 2),
        disk_used_gb=round(disk.used / (1024**3), 2),
        disk_free_gb=round(disk.free / (1024**3), 2),
        engine_stats=engine_stats
    )


@router.get("/resources", response_model=ResourceUsage)
async def get_resources(request: Request):
    """Get current resource usage"""
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)
    disk_read_mb_s, disk_write_mb_s = _disk_rates_mb_s()

    return ResourceUsage(
        cpu_percent=cpu_percent,
        ram_percent=memory.percent,
        ram_used_gb=round(memory.used / (1024**3), 2),
        disk_read_mb_s=disk_read_mb_s,
        disk_write_mb_s=disk_write_mb_s
    )


@router.get("/recommendation")
async def get_recommendation(request: Request):
    """Get model recommendation based on hardware"""
    hardware = request.app.state.hardware_profile
    ram_gb = hardware["ram_total_gb"]
    
    recommendations = []
    
    if ram_gb >= 32:
        recommendations.append({
            "model": "llama3:70b-q4",
            "mode": "fullram",
            "confidence": "high"
        })
    
    if ram_gb >= 16:
        recommendations.append({
            "model": "llama3:8b-q4",
            "mode": "fullram",
            "confidence": "high"
        })
        recommendations.append({
            "model": "mistral:7b-q4",
            "mode": "fullram", 
            "confidence": "high"
        })
    
    if ram_gb >= 8:
        recommendations.append({
            "model": "llama3:8b-q4",
            "mode": "layerstream",
            "confidence": "medium"
        })
        recommendations.append({
            "model": "phi-2",
            "mode": "fullram",
            "confidence": "high"
        })
    
    if ram_gb < 8:
        recommendations.append({
            "model": "tinyllama:1b",
            "mode": "fullram",
            "confidence": "high"
        })
    
    return {
        "hardware": hardware,
        "recommendations": recommendations
    }