// src/security/encryption.rs
use aes_gcm::{
    aead::{Aead, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};
use anyhow::Result;
use rand::RngCore;
use std::path::Path;

pub struct ModelEncryptor;

impl ModelEncryptor {
    /// Encrypt model file
    pub fn encrypt_file<P: AsRef<Path>>(
        input: P,
        output: P,
        key_bytes: &[u8; 32],
    ) -> Result<()> {
        let plaintext = std::fs::read(input.as_ref())?;

        let key = Key::<Aes256Gcm>::from_slice(key_bytes);
        let cipher = Aes256Gcm::new(key);

        let mut nonce_bytes = [0u8; 12];
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = cipher.encrypt(nonce, plaintext.as_ref())
            .map_err(|e| anyhow::anyhow!(
                "Encryption failed: {}", e
            ))?;

        // Write nonce + ciphertext
        let mut output_data = nonce_bytes.to_vec();
        output_data.extend_from_slice(&ciphertext);
        std::fs::write(output.as_ref(), output_data)?;

        tracing::info!(
            "Encrypted model: {} -> {}",
            input.as_ref().display(),
            output.as_ref().display()
        );

        Ok(())
    }

    /// Decrypt model file into memory
    pub fn decrypt_file<P: AsRef<Path>>(
        input: P,
        key_bytes: &[u8; 32],
    ) -> Result<Vec<u8>> {
        let data = std::fs::read(input.as_ref())?;

        if data.len() < 12 {
            return Err(anyhow::anyhow!(
                "Invalid encrypted file"
            ));
        }

        let (nonce_bytes, ciphertext) = data.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);

        let key = Key::<Aes256Gcm>::from_slice(key_bytes);
        let cipher = Aes256Gcm::new(key);

        let plaintext = cipher.decrypt(nonce, ciphertext)
            .map_err(|e| anyhow::anyhow!(
                "Decryption failed: {}", e
            ))?;

        tracing::info!(
            "Decrypted model: {} ({} bytes)",
            input.as_ref().display(),
            plaintext.len()
        );

        Ok(plaintext)
    }

    /// Derive key from machine fingerprint
    pub fn derive_machine_key() -> [u8; 32] {
        use sha2::{Digest, Sha256};

        let mut hasher = Sha256::new();

        // Combine machine-specific data
        hasher.update(whoami::hostname().as_bytes());
        hasher.update(
            num_cpus::get().to_string().as_bytes()
        );
        hasher.update(std::env::consts::OS.as_bytes());
        hasher.update(std::env::consts::ARCH.as_bytes());

        let result = hasher.finalize();
        let mut key = [0u8; 32];
        key.copy_from_slice(&result);
        key
    }
}