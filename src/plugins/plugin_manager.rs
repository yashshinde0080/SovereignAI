// src/plugins/plugin_manager.rs
use crate::plugins::plugin_interface::PluginManifest;
use anyhow::Result;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

pub struct PluginManager {
    plugin_dir: PathBuf,
    loaded_plugins: Vec<PluginManifest>,
    sandbox_enabled: bool,
    max_memory_mb: u64,
}

impl PluginManager {
    pub fn new(
        plugin_dir: &str,
        sandbox: bool,
        max_memory_mb: u64,
    ) -> Self {
        Self {
            plugin_dir: PathBuf::from(plugin_dir),
            loaded_plugins: Vec::new(),
            sandbox_enabled: sandbox,
            max_memory_mb,
        }
    }

    pub fn discover_plugins(&mut self) -> Result<Vec<PluginManifest>> {
        let mut plugins = Vec::new();

        if !self.plugin_dir.exists() {
            return Ok(plugins);
        }

        for entry in WalkDir::new(&self.plugin_dir)
            .max_depth(2)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            if entry.file_name() == "manifest.json" {
                let content = std::fs::read_to_string(
                    entry.path()
                )?;
                let manifest: PluginManifest =
                    serde_json::from_str(&content)?;

                tracing::info!(
                    "Discovered plugin: {} v{}",
                    manifest.name, manifest.version
                );

                plugins.push(manifest);
            }
        }

        self.loaded_plugins = plugins.clone();
        Ok(plugins)
    }

    pub fn list_plugins(&self) -> &[PluginManifest] {
        &self.loaded_plugins
    }
}