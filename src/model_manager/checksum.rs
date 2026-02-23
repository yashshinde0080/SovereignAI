// src/model_manager/checksum.rs
use anyhow::Result;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::Read;
use std::path::Path;

pub fn compute_sha256<P: AsRef<Path>>(path: P) -> Result<String> {
    let mut file = File::open(path.as_ref())?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 8 * 1024 * 1024]; // 8MB chunks

    loop {
        let bytes_read = file.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        hasher.update(&buffer[..bytes_read]);
    }

    let hash = hasher.finalize();
    Ok(hex::encode(hash))
}

pub fn verify_checksum<P: AsRef<Path>>(
    path: P,
    expected: &str,
) -> Result<bool> {
    let actual = compute_sha256(path)?;
    Ok(actual == expected)
}