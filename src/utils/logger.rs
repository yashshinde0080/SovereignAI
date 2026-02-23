// src/utils/logger.rs
use tracing_subscriber::EnvFilter;

pub fn init_logger(level: &str) {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| {
            EnvFilter::new(
                format!("sovereign_ai={}", level)
            )
        });

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .init();
}