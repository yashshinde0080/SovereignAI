// src/model_manager/registry.rs
use crate::core::config::ModelsConfig;
use crate::database::sqlite::Database;
use crate::model_manager::model_metadata::{ModelMetadata, ModelSource};
use anyhow::Result;
use std::sync::Arc;

pub struct ModelRegistry {
    db: Arc<Database>,
    config: ModelsConfig,
}

impl ModelRegistry {
    pub fn new(db: Arc<Database>, config: ModelsConfig) -> Self {
        Self { db, config }
    }

    pub async fn register_model(
        &self,
        model: &ModelMetadata,
    ) -> Result<()> {
        let source_json = serde_json::to_string(&model.source)?;
        let engines_json = serde_json::to_string(
            &model.engines_supported
        )?;

        sqlx::query(
            "INSERT OR REPLACE INTO models \
            (id, name, family, size_label, quantization, \
            file_path, file_size_bytes, checksum_sha256, \
            source, engines_supported, downloaded, version, \
            created_at) \
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
            .bind(&model.id)
            .bind(&model.name)
            .bind(&model.family)
            .bind(&model.size_label)
            .bind(&model.quantization)
            .bind(&model.file_path)
            .bind(model.file_size_bytes as i64)
            .bind(&model.checksum_sha256)
            .bind(&source_json)
            .bind(&engines_json)
            .bind(model.downloaded)
            .bind(&model.version)
            .bind(&model.created_at)
            .execute(self.db.pool())
            .await?;

        tracing::info!(
            "Registered model: {} ({})",
            model.name, model.id
        );

        Ok(())
    }

    pub async fn find_model(
        &self,
        family: &str,
        size: &str,
        version: Option<&str>,
    ) -> Result<Option<ModelMetadata>> {
        let query = if let Some(ver) = version {
            sqlx::query_as::<_, ModelRow>(
                "SELECT * FROM models \
                WHERE family = ? AND size_label = ? \
                AND version = ? AND downloaded = 1"
            )
                .bind(family)
                .bind(size)
                .bind(ver)
        } else {
            sqlx::query_as::<_, ModelRow>(
                "SELECT * FROM models \
                WHERE family = ? AND size_label = ? \
                AND downloaded = 1 \
                ORDER BY created_at DESC LIMIT 1"
            )
                .bind(family)
                .bind(size)
        };

        let row = query.fetch_optional(self.db.pool()).await?;

        Ok(row.map(|r| r.into_metadata()))
    }

    pub async fn list_models(&self) -> Result<Vec<ModelMetadata>> {
        let rows = sqlx::query_as::<_, ModelRow>(
            "SELECT * FROM models WHERE downloaded = 1 \
            ORDER BY family, size_label"
        )
            .fetch_all(self.db.pool())
            .await?;

        Ok(rows.into_iter().map(|r| r.into_metadata()).collect())
    }

    pub async fn remove_model(&self, id: &str) -> Result<()> {
        // Get file path first
        let row = sqlx::query_as::<_, ModelRow>(
            "SELECT * FROM models WHERE id = ?"
        )
            .bind(id)
            .fetch_optional(self.db.pool())
            .await?;

        if let Some(row) = row {
            // Delete file
            if std::path::Path::new(&row.file_path).exists() {
                std::fs::remove_file(&row.file_path)?;
            }

            // Remove from registry
            sqlx::query("DELETE FROM models WHERE id = ?")
                .bind(id)
                .execute(self.db.pool())
                .await?;

            tracing::info!("Removed model: {}", id);
        }

        Ok(())
    }
}

#[derive(sqlx::FromRow)]
struct ModelRow {
    id: String,
    name: String,
    family: String,
    size_label: String,
    quantization: String,
    file_path: String,
    file_size_bytes: i64,
    checksum_sha256: String,
    source: String,
    engines_supported: String,
    downloaded: bool,
    version: String,
    created_at: String,
}

impl ModelRow {
    fn into_metadata(self) -> ModelMetadata {
        let source: ModelSource = serde_json::from_str(&self.source)
            .unwrap_or(ModelSource::Local);
        let engines: Vec<String> =
            serde_json::from_str(&self.engines_supported)
                .unwrap_or_default();

        ModelMetadata {
            id: self.id,
            name: self.name,
            family: self.family,
            size_label: self.size_label,
            quantization: self.quantization,
            file_path: self.file_path,
            file_size_bytes: self.file_size_bytes as u64,
            checksum_sha256: self.checksum_sha256,
            source,
            engines_supported: engines,
            downloaded: self.downloaded,
            version: self.version,
            created_at: self.created_at,
        }
    }
}