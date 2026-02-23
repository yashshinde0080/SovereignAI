// src/cli/system_info.rs
use crate::cli::display;
use crate::core::hardware_detector::ExecutionMode;
use crate::core::runtime::Runtime;
use anyhow::Result;
use std::sync::Arc;

pub async fn execute(
    runtime: Arc<Runtime>,
    benchmark_disk: bool,
) -> Result<()> {
    display::print_banner();
    display::print_header("Hardware Profile");

    let hw = &runtime.hardware;

    display::print_key_value("CPU:", &hw.cpu_brand);
    display::print_key_value(
        "Cores:",
        &hw.cpu_cores.to_string(),
    );
    display::print_key_value_colored(
        "AVX2:",
        if hw.has_avx2 { "Yes" } else { "No" },
        if hw.has_avx2 { display::GREEN } else { display::RED },
    );
    display::print_key_value_colored(
        "AVX512:",
        if hw.has_avx512 { "Yes" } else { "No" },
        if hw.has_avx512 {
            display::GREEN
        } else {
            display::DIM
        },
    );

    println!();
    display::print_key_value(
        "Total RAM:",
        &display::human_readable_size(hw.total_ram_bytes),
    );
    display::print_key_value(
        "Available RAM:",
        &display::human_readable_size(hw.available_ram_bytes),
    );
    display::print_key_value(
        "Usable RAM:",
        &display::human_readable_size(hw.usable_ram_bytes(
            runtime.config.runtime.max_ram_usage_percent,
        )),
    );

    println!();
    display::print_key_value(
        "Disk Speed:",
        &format!("{:.0} MB/s", hw.disk_read_speed_mbps),
    );
    display::print_key_value("OS:", &hw.os);
    display::print_key_value("Arch:", &hw.arch);

    if let Some(gpu) = &hw.gpu_info {
        println!();
        display::print_key_value("GPU:", &gpu.name);
        display::print_key_value(
            "VRAM:",
            &display::human_readable_size(gpu.vram_bytes),
        );
        display::print_key_value("Backend:", &gpu.backend);
    } else {
        println!();
        display::print_key_value_colored(
            "GPU:",
            "Not detected",
            display::DIM,
        );
    }

    // Recommendations
    display::print_header("Recommendations");

    let usable_gb = hw.usable_ram_bytes(
        runtime.config.runtime.max_ram_usage_percent,
    ) as f64
        / (1024.0 * 1024.0 * 1024.0);

    let (max_model, recommended_mode) = if usable_gb >= 24.0 {
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

    display::print_key_value_colored(
        "Recommended Mode:",
        recommended_mode,
        display::CYAN,
    );
    display::print_key_value_colored(
        "Max Safe Model:",
        max_model,
        display::GREEN,
    );

    if hw.disk_read_speed_mbps < 100.0 {
        println!();
        display::print_warning(
            "Disk speed below 100 MB/s. \
            LayerStream may be slow.",
        );
    }

    // Memory tracker status
    display::print_header("Memory Tracker");
    let snapshot = runtime.memory_tracker.snapshot();
    display::print_key_value(
        "Allocated:",
        &display::human_readable_size(snapshot.total_used),
    );
    display::print_key_value(
        "Maximum:",
        &display::human_readable_size(snapshot.total_max),
    );
    display::print_key_value(
        "Utilization:",
        &format!(
            "{:.1}%",
            (snapshot.total_used as f64
                / snapshot.total_max as f64)
                * 100.0
        ),
    );
    display::print_key_value(
        "Allocations:",
        &snapshot.allocation_count.to_string(),
    );

    // Storage
    display::print_header("Storage");
    let storage = crate::model_manager::storage::StorageManager::new(
        &runtime.config.models.base_path,
        runtime.config.models.max_storage_gb,
    );

    display::print_key_value(
        "Used:",
        &display::human_readable_size(storage.total_used_bytes()),
    );
    display::print_key_value(
        "Available:",
        &display::human_readable_size(storage.available_bytes()),
    );
    display::print_key_value(
        "Max:",
        &format!("{} GB", runtime.config.models.max_storage_gb),
    );

    if benchmark_disk {
        display::print_header("Disk Benchmark");
        display::print_info("Running sequential read test...");

        let hw_fresh =
            crate::core::hardware_detector::HardwareProfile::detect()?;
        display::print_metric(
            "Sequential Read:",
            &format!("{:.0}", hw_fresh.disk_read_speed_mbps),
            "MB/s",
        );
    }

    Ok(())
}