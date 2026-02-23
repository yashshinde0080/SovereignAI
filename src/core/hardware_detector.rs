// src/core/hardware_detector.rs
use serde::{Deserialize, Serialize};
use sysinfo::System;
use std::time::Instant;
use anyhow::Result;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareProfile {
    pub total_ram_bytes: u64,
    pub available_ram_bytes: u64,
    pub cpu_cores: usize,
    pub cpu_brand: String,
    pub has_avx2: bool,
    pub has_avx512: bool,
    pub gpu_info: Option<GpuInfo>,
    pub disk_read_speed_mbps: f64,
    pub os: String,
    pub arch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuInfo {
    pub name: String,
    pub vram_bytes: u64,
    pub backend: String,
}

impl HardwareProfile {
    pub fn detect() -> Result<Self> {
        let mut sys = System::new_all();
        sys.refresh_all();

        let total_ram = sys.total_memory();
        let available_ram = sys.available_memory();
        let cpu_cores = num_cpus::get();

        let cpu_brand = sys.cpus()
            .first()
            .map(|c| c.brand().to_string())
            .unwrap_or_else(|| "Unknown".to_string());

        let has_avx2 = Self::detect_avx2();
        let has_avx512 = Self::detect_avx512();

        let disk_speed = Self::benchmark_disk_speed()?;

        let gpu_info = Self::detect_gpu();

        Ok(Self {
            total_ram_bytes: total_ram,
            available_ram_bytes: available_ram,
            cpu_cores,
            cpu_brand,
            has_avx2,
            has_avx512,
            gpu_info,
            disk_read_speed_mbps: disk_speed,
            os: std::env::consts::OS.to_string(),
            arch: std::env::consts::ARCH.to_string(),
        })
    }

    fn detect_avx2() -> bool {
        #[cfg(target_arch = "x86_64")]
        {
            is_x86_feature_detected!("avx2")
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            false
        }
    }

    fn detect_avx512() -> bool {
        #[cfg(target_arch = "x86_64")]
        {
            is_x86_feature_detected!("avx512f")
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            false
        }
    }

    fn benchmark_disk_speed() -> Result<f64> {
        let temp_file = tempfile::NamedTempFile::new()?;
        let test_size: usize = 64 * 1024 * 1024; // 64MB
        let data = vec![0u8; test_size];

        std::fs::write(temp_file.path(), &data)?;

        let start = Instant::now();
        let _ = std::fs::read(temp_file.path())?;
        let elapsed = start.elapsed();

        let speed_mbps = (test_size as f64 / (1024.0 * 1024.0))
            / elapsed.as_secs_f64();

        Ok(speed_mbps)
    }

    fn detect_gpu() -> Option<GpuInfo> {
        // GPU detection requires platform-specific code
        // Placeholder for CUDA/Metal/Vulkan detection
        None
    }

    pub fn usable_ram_bytes(&self, max_percent: u8) -> u64 {
        (self.available_ram_bytes as f64
            * (max_percent as f64 / 100.0)) as u64
    }

    pub fn recommend_mode(
        &self,
        model_size_bytes: u64,
        max_ram_percent: u8
    ) -> ExecutionMode {
        let usable = self.usable_ram_bytes(max_ram_percent);
        let required_fullram = (model_size_bytes as f64 * 1.4) as u64;

        if usable >= required_fullram {
            ExecutionMode::FullRam
        } else if self.disk_read_speed_mbps > 100.0
            && usable >= model_size_bytes / 4
        {
            ExecutionMode::LayerStream
        } else {
            ExecutionMode::Insufficient
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ExecutionMode {
    FullRam,
    LayerStream,
    Auto,
    Insufficient,
}

impl std::fmt::Display for ExecutionMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::FullRam => write!(f, "fullram"),
            Self::LayerStream => write!(f, "layerstream"),
            Self::Auto => write!(f, "auto"),
            Self::Insufficient => write!(f, "insufficient"),
        }
    }
}

impl std::str::FromStr for ExecutionMode {
    type Err = anyhow::Error;

    fn from_str(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            "fullram" | "full_ram" | "full-ram" => Ok(Self::FullRam),
            "layerstream" | "layer_stream" | "layer-stream" => {
                Ok(Self::LayerStream)
            }
            "auto" => Ok(Self::Auto),
            _ => Err(anyhow::anyhow!("Unknown execution mode: {}", s)),
        }
    }
}