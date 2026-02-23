// src/security/audit_logger.rs
use tracing::info;

pub struct AuditLogger {
    enabled: bool,
}

impl AuditLogger {
    pub fn new(enabled: bool) -> Self {
        Self { enabled }
    }

    pub fn log(&self, event_type: &str, message: &str) {
        if self.enabled {
            info!(
                event_type = event_type,
                message = message,
                "AUDIT"
            );
        }
    }

    pub fn log_security_event(
        &self,
        event_type: &str,
        severity: &str,
        message: &str,
    ) {
        if self.enabled {
            tracing::warn!(
                event_type = event_type,
                severity = severity,
                message = message,
                "SECURITY_AUDIT"
            );
        }
    }
}