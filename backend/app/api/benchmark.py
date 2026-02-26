"""Benchmark API Endpoints"""
import time
import asyncio
from fastapi import APIRouter, HTTPException, Request

from app.schemas.benchmark import BenchmarkRequest, BenchmarkResult


router = APIRouter()


@router.post("/run", response_model=BenchmarkResult)
async def run_benchmark(request: Request, bench_request: BenchmarkRequest):
    """Run inference benchmark"""
    app = request.app
    
    if not app.state.active_engine:
        raise HTTPException(status_code=400, detail="No model loaded")
    
    engine = app.state.active_engine
    
    # Test prompts
    test_prompts = [
        "Hello, how are you?",
        "Explain quantum computing in simple terms.",
        "Write a short poem about artificial intelligence.",
    ]
    
    results = {
        "model": app.state.active_model,
        "mode": app.state.active_mode,
        "iterations": bench_request.iterations,
        "runs": []
    }
    
    total_tokens = 0
    total_time = 0
    
    for i in range(bench_request.iterations):
        prompt = test_prompts[i % len(test_prompts)]
        
        # Measure inference
        start_time = time.perf_counter()
        
        response = await engine.generate(
            prompt=prompt,
            max_tokens=bench_request.max_tokens
        )
        
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        tokens = response.get("completion_tokens", 0)
        tps = tokens / elapsed if elapsed > 0 else 0
        
        total_tokens += tokens
        total_time += elapsed
        
        results["runs"].append({
            "iteration": i + 1,
            "tokens": tokens,
            "time_seconds": round(elapsed, 3),
            "tokens_per_second": round(tps, 2)
        })
    
    # Calculate averages
    avg_tps = total_tokens / total_time if total_time > 0 else 0
    
    results["summary"] = {
        "total_tokens": total_tokens,
        "total_time_seconds": round(total_time, 3),
        "average_tokens_per_second": round(avg_tps, 2),
        "peak_ram_gb": engine.get_memory_usage().get("peak_ram_gb", 0)
    }
    
    return BenchmarkResult(**results)


@router.get("/compare")
async def compare_modes(request: Request):
    """Compare fullram vs layerstream performance"""
    app = request.app
    
    if not app.state.active_model:
        raise HTTPException(status_code=400, detail="No model loaded")
    
    # This would require loading in both modes
    # Return cached comparison if available
    return {
        "status": "not_implemented",
        "message": "Mode comparison requires model reload"
    }