// src/database/sqlite.rs
use anyhow::Result;
use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};
use std::path::Path;

pub struct Database {
    pool: SqlitePool,
}

impl Database {
    pub async fn initialize(db_path: &str) -> Result<Self> {
        // Ensure parent directory exists
        if let Some(parent) = Path::new(db_path).parent() {
            std::fs::create_dir_all(parent)?;
        }

        let url = format!("sqlite://{}?mode=rwc", db_path);

        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect(&url)
            .await?;

        let db = Self { pool };
        db.run_migrations().await?;

        tracing::info!("Database initialized: {}", db_path);

        Ok(db)
    }

    pub fn pool(&self) -> &SqlitePool {
        &self.pool
    }

    async fn run_migrations(&self) -> Result<()> {
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                family TEXT NOT NULL,
                size_label TEXT NOT NULL,
                quantization TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                source TEXT NOT NULL,
                engines_supported TEXT NOT NULL,
                downloaded BOOLEAN NOT NULL DEFAULT 0,
                version TEXT NOT NULL DEFAULT 'latest',
                created_at TEXT NOT NULL
            )"
        )
            .execute(&self.pool)
            .await?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                tokens_generated INTEGER NOT NULL DEFAULT 0,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                total_time_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )"
        )
            .execute(&self.pool)
            .await?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS hardware_profiles (
                id TEXT PRIMARY KEY,
                total_ram_bytes INTEGER NOT NULL,
                cpu_cores INTEGER NOT NULL,
                cpu_brand TEXT NOT NULL,
                gpu_info TEXT,
                disk_speed_mbps REAL NOT NULL,
                os TEXT NOT NULL,
                arch TEXT NOT NULL,
                detected_at TEXT NOT NULL
            )"
        )
            .execute(&self.pool)
            .await?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )"
        )
            .execute(&self.pool)
            .await?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS benchmarks (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                mode TEXT NOT NULL,
                tokens_per_second REAL NOT NULL,
                time_to_first_token_ms INTEGER NOT NULL,
                peak_memory_bytes INTEGER NOT NULL,
                tested_at TEXT NOT NULL
            )"
        )
            .execute(&self.pool)
            .await?;

        tracing::info!("Database migrations complete");
        Ok(())
    }

    pub async fn log_session(
        &self,
        model_id: &str,
        mode: &str,
        tokens_generated: usize,
        prompt_tokens: usize,
        total_time_ms: u128,
    ) -> Result<()> {
        sqlx::query(
            "INSERT INTO sessions \
            (id, model_id, mode, tokens_generated, \
            prompt_tokens, total_time_ms, created_at) \
            VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
            .bind(uuid::Uuid::new_v4().to_string())
            .bind(model_id)
            .bind(mode)
            .bind(tokens_generated as i64)
            .bind(prompt_tokens as i64)
            .bind(total_time_ms as i64)
            .bind(chrono::Utc::now().to_rfc3339())
            .execute(&self.pool)
            .await?;

        Ok(())
    }
}