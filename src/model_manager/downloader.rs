// src/model_manager/downloader.rs
use anyhow::Result;
use indicatif::{ProgressBar, ProgressStyle};
use std::path::{Path, PathBuf};

pub struct ModelDownloader {
    cache_dir: PathBuf,
}

impl ModelDownloader {
    pub fn new(cache_dir: &str) -> Self {
        Self {
            cache_dir: PathBuf::from(cache_dir),
        }
    }

    /// Download model with resume support
    #[cfg(feature = "online")]
    pub async fn download(
        &self,
        url: &str,
        filename: &str,
    ) -> Result<PathBuf> {
        use tokio::io::AsyncWriteExt;

        let dest = self.cache_dir.join(filename);
        std::fs::create_dir_all(&self.cache_dir)?;

        // Check for partial download
        let mut start_byte: u64 = 0;
        if dest.exists() {
            start_byte = std::fs::metadata(&dest)?.len();
            tracing::info!(
                "Resuming download from byte {}", start_byte
            );
        }

        let client = reqwest::Client::new();
        let mut request = client.get(url);

        if start_byte > 0 {
            request = request.header(
                "Range",
                format!("bytes={}-", start_byte)
            );
        }

        let response = request.send().await?;

        let total_size = response.content_length()
            .unwrap_or(0) + start_byte;

        let pb = ProgressBar::new(total_size);
        pb.set_style(
            ProgressStyle::default_bar()
                .template(
                    "{spinner:.green} [{elapsed_precise}] \
                    [{bar:40.cyan/blue}] {bytes}/{total_bytes} \
                    ({bytes_per_sec}, {eta})"
                )?
                .progress_chars("█▓░")
        );
        pb.set_position(start_byte);

        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&dest)
            .await?;

        let mut stream = response.bytes_stream();
        use futures::StreamExt;

        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            file.write_all(&chunk).await?;
            pb.inc(chunk.len() as u64);
        }

        pb.finish_with_message("Download complete");

        Ok(dest)
    }

    /// Import model from local path
    pub fn import_local<P: AsRef<Path>>(
        &self,
        source: P,
        filename: &str,
    ) -> Result<PathBuf> {
        let dest_dir = self.cache_dir.parent()
            .unwrap_or(Path::new("."))
            .join("installed");
        std::fs::create_dir_all(&dest_dir)?;

        let dest = dest_dir.join(filename);
        std::fs::copy(source.as_ref(), &dest)?;

        tracing::info!(
            "Model imported to: {}", dest.display()
        );

        Ok(dest)
    }
}