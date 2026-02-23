// src/api/system.rs — Extended version
use crate::core::hardware_detector::ExecutionMode;
use crate::core::runtime::Runtime;
use crate::model_manager::resolver::ModelResolver;
use axum::{
    extract::State,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Serialize)]
pub struct ModelListResponse {
    pub models: Vec<ModelInfo>,
    pub count: usize,
}

#[derive(Debug, Serialize)]
pub struct ModelInfo {
    pub id: String,
    pub name: String,
    pub family: String,
    pub size_label: String,
    pub quantization: String,
    pub file_size_bytes: u64,
    pub file_size_human: String,
    pub engines_supported: Vec<String>,
    pub version: String,
}

pub async fn list_models(
    State(runtime): State<Arc<Runtime>>,
) -> Json<ModelListResponse> {
    let models = runtime
        .registry
        .list_models()
        .await
        .unwrap_or_default();

    let infos: Vec<ModelInfo> = models
        .into_iter()
        .map(|m| ModelInfo {
            id: m.id,
            name: m.name,
            family: m.family,
            size_label: m.size_label,
            quantization: m.quantization,
            file_size_human: crate::cli::display
                ::human_readable_size(m.file_size_bytes),
            file_size_bytes: m.file_size_bytes,
            engines_supported: m.engines_supported,
            version: m.version,
        })
        .collect();

    let count = infos.len();
    Json(ModelListResponse {
        models: infos,
        count,
    })
}

pub async fn active_model(
    State(runtime): State<Arc<Runtime>>,
) -> Json<serde_json::Value> {
    match runtime.active_model_info() {
        Some(model) => Json(serde_json::json!({
            "loaded": true,
            "model": {
                "name": model.name,
                "quantization": model.quantization,
                "size": model.file_size_bytes,
            }
        })),
        None => Json(serde_json::json!({
            "loaded": false,
            "model": null
        })),
    }
}

#[derive(Debug, Deserialize)]
pub struct LoadModelRequest {
    pub model: String,
    pub mode: Option<String>,
}

pub async fn load_model(
    State(runtime): State<Arc<Runtime>>,
    Json(request): Json<LoadModelRequest>,
) -> Result<Json<serde_json::Value>, axum::http::StatusCode> {
    let resolver = ModelResolver::new(runtime.registry.clone());

    let model = resolver
        .resolve(&request.model, &runtime.hardware)
        .await
        .map_err(|_| {
            axum::http::StatusCode::NOT_FOUND
        })?;

    let mode: ExecutionMode = request
        .mode
        .as_deref()
        .unwrap_or("auto")
        .parse()
        .map_err(|_| {
            axum::http::StatusCode::BAD_REQUEST
        })?;

    runtime
        .load_model(model.clone(), mode)
        .map_err(|_| {
            axum::http::StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(serde_json::json!({
        "status": "loaded",
        "model": model.name,
    })))
}

pub async fn unload_model(
    State(runtime): State<Arc<Runtime>>,
) -> Json<serde_json::Value> {
    runtime.unload_model();
    Json(serde_json::json!({
        "status": "unloaded"
    }))
}

pub async fn system_status(
    State(runtime): State<Arc<Runtime>>,
) -> Json<crate::core::runtime::SystemStatus> {
    Json(runtime.system_status())
}

pub async fn hardware_info(
    State(runtime): State<Arc<Runtime>>,
) -> Json<serde_json::Value> {
    let hw = &runtime.hardware;

    let usable_gb = hw.usable_ram_bytes(
        runtime.config.runtime.max_ram_usage_percent,
    ) as f64
        / (1024.0 * 1024.0 * 1024.0);

    let (max_model, rec_mode) = if usable_gb >= 24.0 {
        ("13B Q5", "FullRAM")
    } else if usable_gb >= 12.0 {
        ("13B Q4", "FullRAM")
    } else if usable_gb >= 8.0 {
        ("8B Q4", "FullRAM")
    } else if usable_gb >= 4.0 {
        ("7B Q4", "LayerStream")
    } else {
        ("3B Q4", "LayerStream")
    };

    Json(serde_json::json!({
        "cpu": {
            "brand": hw.cpu_brand,
            "cores": hw.cpu_cores,
            "avx2": hw.has_avx2,
            "avx512": hw.has_avx512,
        },
        "ram": {
            "total_bytes": hw.total_ram_bytes,
            "available_bytes": hw.available_ram_bytes,
            "total_human": crate::cli::display
                ::human_readable_size(hw.total_ram_bytes),
            "available_human": crate::cli::display
                ::human_readable_size(hw.available_ram_bytes),
        },
        "disk": {
            "speed_mbps": hw.disk_read_speed_mbps,
        },
        "gpu": hw.gpu_info,
        "os": hw.os,
        "arch": hw.arch,
        "recommendations": {
            "mode": rec_mode,
            "max_model": max_model,
        }
    }))
}

pub async fn memory_status(
    State(runtime): State<Arc<Runtime>>,
) -> Json<serde_json::Value> {
    let snapshot = runtime.memory_tracker.snapshot();

    Json(serde_json::json!({
        "total_max": snapshot.total_max,
        "total_used": snapshot.total_used,
        "percent": (snapshot.total_used as f64
            / snapshot.total_max as f64) * 100.0,
        "allocation_count": snapshot.allocation_count,
        "total_max_human": crate::cli::display
            ::human_readable_size(snapshot.total_max),
        "total_used_human": crate::cli::display
            ::human_readable_size(snapshot.total_used),
    }))
}

pub async fn run_benchmark(
    State(runtime): State<Arc<Runtime>>,
) -> Result<
    Json<crate::core::benchmark::BenchmarkResult>,
    axum::http::StatusCode,
> {
    let model_info = runtime
        .active_model_info()
        .ok_or(axum::http::StatusCode::BAD_REQUEST)?;

    let req = crate::engines::traits::InferenceRequest {
        prompt: "Explain the concept of machine learning."
            .to_string(),
        max_tokens: 64,
        temperature: 0.0,
        top_p: 1.0,
        stop_sequences: vec![],
        stream: false,
    };

    match runtime.inference(req).await {
        Ok(response) => {
            let tps = if response.total_time_ms > 0 {
                response.tokens_generated as f64
                    / (response.total_time_ms as f64 / 1000.0)
            } else {
                0.0
            };

            Ok(Json(crate::core::benchmark::BenchmarkResult {
                model_name: model_info.name,
                mode: response.mode,
                prompt_tokens: response.prompt_tokens,
                generated_tokens: response.tokens_generated,
                total_time_ms: response.total_time_ms,
                tokens_per_second: tps,
                time_to_first_token_ms:
                    response.time_to_first_token_ms,
                peak_memory_bytes: response.peak_memory_bytes,
            }))
        }
        Err(_) => Err(
            axum::http::StatusCode::INTERNAL_SERVER_ERROR
        ),
    }
}