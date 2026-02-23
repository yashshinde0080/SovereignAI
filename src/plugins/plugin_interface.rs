// src/plugins/plugin_interface.rs
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub name: String,
    pub version: String,
    pub description: String,
    pub entry_point: String,
    pub permissions: Vec<PluginPermission>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PluginPermission {
    FileRead,
    FileWrite,
    NetworkAccess,
    ModelAccess,
    VectorStoreAccess,
}

pub trait Plugin: Send + Sync {
    fn name(&self) -> &str;
    fn version(&self) -> &str;
    fn execute(
        &self,
        input: &str,
    ) -> Result<String>;
}