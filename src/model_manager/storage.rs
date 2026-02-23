// src/model_manager/storage.rs
use anyhow::Result;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

pub struct StorageManager {
    base_path: PathBuf,
    max_storage_bytes: u64,
}

impl StorageManager {
    pub fn new(base_path: &str, max_storage_gb: u64) -> Self {
        Self {
            base_path: PathBuf::from(base_path),
            max_storage_bytes: max_storage_gb * 1024 * 1024 * 1024,
        }
    }

    pub fn total_used_bytes(&self) -> u64 {
        WalkDir::new(&self.base_path)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter_map(|e| e.metadata().ok())
            .map(|m| m.len())
            .sum()
    }

    pub fn available_bytes(&self) -> u64 {
        let used = self.total_used_bytes();
        if used >= self.max_storage_bytes {
            0
        } else {
            self.max_storage_bytes - used
        }
    }

    pub fn has_space(&self, needed_bytes: u64) -> bool {
        self.available_bytes() >= needed_bytes
    }

    pub fn list_models(&self) -> Result<Vec<PathBuf>> {
        let mut models = Vec::new();

        for entry in WalkDir::new(&self.base_path)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            let path = entry.path();
            if path.extension()
                .map(|e| e == "gguf")
                .unwrap_or(false)
            {
                models.push(path.to_path_buf());
            }
        }

        Ok(models)
    }

    pub fn delete_model<P: AsRef<Path>>(
        &self,
        path: P
    ) -> Result<u64> {
        let metadata = std::fs::metadata(path.as_ref())?;
        let size = metadata.len();
        std::fs::remove_file(path.as_ref())?;
        tracing::info!(
            "Deleted model: {} ({} bytes freed)",
            path.as_ref().display(),
            size
        );
        Ok(size)
    }

    /// Cleanup least recently used models to free space
    pub fn cleanup_lru(&self, needed_bytes: u64) -> Result<u64> {
        let mut files: Vec<(PathBuf, std::time::SystemTime, u64)> =
            WalkDir::new(&self.base_path)
                .into_iter()
                .filter_map(|e| e.ok())
                .filter(|e| {
                    e.path().extension()
                        .map(|ext| ext == "gguf")
                        .unwrap_or(false)
                })
                .filter_map(|e| {
                    let meta = e.metadata().ok()?;
                    let accessed = meta.accessed().ok()?;
                    Some((
                        e.path().to_path_buf(),
                        accessed,
                        meta.len()
                    ))
                })
                .collect();

        // Sort by least recently accessed
        files.sort_by(|a, b| a.1.cmp(&b.1));

        let mut freed = 0u64;
        for (path, _, size) in files {
            if freed >= needed_bytes {
                break;
            }
            std::fs::remove_file(&path)?;
            freed += size;
            tracing::info!(
                "LRU cleanup: deleted {} ({} bytes)",
                path.display(), size
            );
        }

        Ok(freed)
    }
}