// src/core/runtime.rs
use crate::core::config::AppConfig;
use crate::core::engine_factory::EngineFactory;
use crate::core::hardware_detector::{ExecutionMode, HardwareProfile};
use crate::core::memory_tracker::MemoryTracker;
use crate::database::sqlite::Database;
use crate::engines::traits::{InferenceEngine, InferenceRequest, InferenceResponse};
use crate::model_manager::registry::ModelRegistry;
use crate::model_manager::model_metadata::ModelMetadata;
use crate::security::audit_logger::AuditLogger;
use crate::vectorstore::store::VectorStore;
use anyhow::Result;
use parking_lot::RwLock;
use std::sync::Arc;

pub struct Runtime {
    pub config: AppConfig,
    pub hardware: HardwareProfile,
    pub memory_tracker: Arc<MemoryTracker>,
    pub database: Arc<Database>,
    pub registry: Arc<ModelRegistry>,
    pub vector_store: Arc<VectorStore>,
    pub audit_logger: Arc<AuditLogger>,
    active_engine: RwLock<Option<Box<dyn InferenceEngine>>>,
    active_model: RwLock<Option<ModelMetadata>>,
}

impl Runtime {
    pub async fn initialize(config: AppConfig) -> Result<Arc<Self>> {
        tracing::info!("Initializing SovereignAI Runtime v{}",
            config.runtime.version);

        // Detect hardware
        let hardware = HardwareProfile::detect()?;
        tracing::info!(
            "Hardware: {} cores, {} MB RAM, {:.1} MB/s disk",
            hardware.cpu_cores,
            hardware.total_ram_bytes / (1024 * 1024),
            hardware.disk_read_speed_mbps
        );

        // Initialize memory tracker
        let usable_ram = hardware.usable_ram_bytes(
            config.runtime.max_ram_usage_percent
        );
        let memory_tracker = MemoryTracker::new(usable_ram);

        // Initialize database
        let database = Database::initialize(
            &config.models.registry_db
        ).await?;
        let database = Arc::new(database);

        // Initialize model registry
        let registry = ModelRegistry::new(
            database.clone(),
            config.models.clone(),
        );
        let registry = Arc::new(registry);

        // Initialize vector store
        let vector_store = VectorStore::new(
            &config.vectorstore
        )?;
        let vector_store = Arc::new(vector_store);

        // Initialize audit logger
        let audit_logger = AuditLogger::new(
            config.security.audit_logging
        );
        let audit_logger = Arc::new(audit_logger);

        // Ensure directories exist
        Self::ensure_directories(&config)?;

        let runtime = Arc::new(Self {
            config,
            hardware,
            memory_tracker,
            database,
            registry,
            vector_store,
            audit_logger,
            active_engine: RwLock::new(None),
            active_model: RwLock::new(None),
        });

        tracing::info!("Runtime initialized successfully");
        Ok(runtime)
    }

    fn ensure_directories(config: &AppConfig) -> Result<()> {
        std::fs::create_dir_all(&config.models.base_path)?;
        std::fs::create_dir_all(&config.models.cache_path)?;
        std::fs::create_dir_all(&config.vectorstore.index_path)?;
        std::fs::create_dir_all("workspace/sessions")?;
        std::fs::create_dir_all("workspace/documents")?;
        std::fs::create_dir_all("workspace/logs")?;
        std::fs::create_dir_all("workspace/exports")?;
        Ok(())
    }

    pub fn load_model(
        &self,
        model: ModelMetadata,
        mode: ExecutionMode,
    ) -> Result<()> {
        // Unload previous engine
        self.unload_model();

        let engine = EngineFactory::create(
            mode,
            &model,
            &self.hardware,
            self.memory_tracker.clone(),
            &self.config,
        )?;

        *self.active_engine.write() = Some(engine);
        *self.active_model.write() = Some(model);

        self.audit_logger.log("model_loaded", "Model loaded successfully");

        Ok(())
    }

    pub fn unload_model(&self) {
        let mut engine = self.active_engine.write();
        if engine.is_some() {
            *engine = None;
            *self.active_model.write() = None;
            tracing::info!("Previous model unloaded");
        }
    }

    pub async fn inference(
        &self,
        request: InferenceRequest
    ) -> Result<InferenceResponse> {
        let engine = self.active_engine.read();
        let engine = engine.as_ref()
            .ok_or_else(|| anyhow::anyhow!("No model loaded"))?;

        let response = engine.generate(&request).await?;

        self.audit_logger.log(
            "inference",
            &format!("Generated {} tokens", response.tokens_generated)
        );

        Ok(response)
    }

    pub fn active_model_info(&self) -> Option<ModelMetadata> {
        self.active_model.read().clone()
    }

    pub fn system_status(&self) -> SystemStatus {
        let snapshot = self.memory_tracker.snapshot();
        SystemStatus {
            runtime_version: self.config.runtime.version.clone(),
            hardware: self.hardware.clone(),
            memory_used: snapshot.total_used,
            memory_max: snapshot.total_max,
            memory_percent: (snapshot.total_used as f64
                / snapshot.total_max as f64) * 100.0,
            active_model: self.active_model.read().as_ref()
                .map(|m| m.name.clone()),
            allocation_count: snapshot.allocation_count,
        }
    }
}

#[derive(Debug, serde::Serialize)]
pub struct SystemStatus {
    pub runtime_version: String,
    pub hardware: HardwareProfile,
    pub memory_used: u64,
    pub memory_max: u64,
    pub memory_percent: f64,
    pub active_model: Option<String>,
    pub allocation_count: usize,
}