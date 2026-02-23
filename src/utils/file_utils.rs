// src/utils/file_utils.rs
use anyhow::Result;
use std::path::Path;

pub fn ensure_dir<P: AsRef<Path>>(path: P) -> Result<()> {
    std::fs::create_dir_all(path.as_ref())?;
    Ok(())
}

pub fn file_size_mb<P: AsRef<Path>>(path: P) -> Result<f64> {
    let metadata = std::fs::metadata(path.as_ref())?;
    Ok(metadata.len() as f64 / (1024.0 * 1024.0))
}

pub fn human_readable_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.2} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.2} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.2} KB", bytes as f64 / KB as f64)
    } else {
        format!("{} bytes", bytes)
    }
}