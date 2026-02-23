// src/cli/logs.rs
use crate::cli::display;
use anyhow::Result;
use std::io::{BufRead, BufReader};

pub async fn execute(
    lines: usize,
    follow: bool,
    filter: Option<&str>,
) -> Result<()> {
    display::print_header("Runtime Logs");

    let log_path = "workspace/logs/sovereign.log";

    if !std::path::Path::new(log_path).exists() {
        display::print_info("No log file found.");
        display::print_info(&format!(
            "Expected: {}", log_path
        ));
        return Ok(());
    }

    let file = std::fs::File::open(log_path)?;
    let reader = BufReader::new(file);

    let all_lines: Vec<String> = reader
        .lines()
        .filter_map(|l| l.ok())
        .collect();

    let start = if all_lines.len() > lines {
        all_lines.len() - lines
    } else {
        0
    };

    for line in &all_lines[start..] {
        if let Some(f) = filter {
            if !line.contains(f) {
                continue;
            }
        }

        // Color-code log levels
        if line.contains("ERROR") {
            println!(
                "{}{}{}",
                display::RED, line, display::RESET,
            );
        } else if line.contains("WARN") {
            println!(
                "{}{}{}",
                display::YELLOW, line, display::RESET,
            );
        } else if line.contains("INFO") {
            println!("{}", line);
        } else {
            println!(
                "{}{}{}",
                display::DIM, line, display::RESET,
            );
        }
    }

    if follow {
        display::print_info(
            "Follow mode not yet implemented. \
            Use: tail -f workspace/logs/sovereign.log",
        );
    }

    Ok(())
}