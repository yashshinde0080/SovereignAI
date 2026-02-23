// src/security/license.rs
use anyhow::Result;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Serialize, Deserialize)]
pub struct License {
    pub id: String,
    pub machine_fingerprint: String,
    pub expires_at: Option<String>,
    pub features: Vec<String>,
    pub signature: String,
}

pub struct LicenseManager;

impl LicenseManager {
    /// Generate machine fingerprint
    pub fn machine_fingerprint() -> String {
        let mut hasher = Sha256::new();

        hasher.update(whoami::hostname().as_bytes());
        hasher.update(
            num_cpus::get().to_string().as_bytes()
        );

        let sys = sysinfo::System::new_all();
        hasher.update(
            sys.total_memory().to_string().as_bytes()
        );

        hex::encode(hasher.finalize())
    }

    /// Validate license file
    pub fn validate(license_path: &str) -> Result<License> {
        let content = std::fs::read_to_string(license_path)?;
        let license: License = serde_json::from_str(&content)?;

        // Check machine fingerprint
        let current = Self::machine_fingerprint();
        if license.machine_fingerprint != current {
            return Err(anyhow::anyhow!(
                "License not valid for this machine"
            ));
        }

        // Check expiration
        if let Some(expires) = &license.expires_at {
            let expires_dt = chrono::DateTime::parse_from_rfc3339(
                expires
            )?;
            if chrono::Utc::now() > expires_dt {
                return Err(anyhow::anyhow!("License expired"));
            }
        }

        Ok(license)
    }

    /// Generate license request file
    pub fn generate_request(output_path: &str) -> Result<()> {
        let request = serde_json::json!({
            "machine_fingerprint": Self::machine_fingerprint(),
            "hostname": whoami::hostname(),
            "os": std::env::consts::OS,
            "arch": std::env::consts::ARCH,
            "requested_at": chrono::Utc::now().to_rfc3339(),
        });

        let json = serde_json::to_string_pretty(&request)?;
        std::fs::write(output_path, json)?;

        tracing::info!(
            "License request generated: {}", output_path
        );

        Ok(())
    }
}