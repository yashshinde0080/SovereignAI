// src/cli/display.rs
//! Unified CLI display utilities.
//! Every CLI output goes through here for consistency.

use std::io::{self, Write};

/// Terminal colors (ANSI)
pub const RESET: &str = "\x1b[0m";
pub const BOLD: &str = "\x1b[1m";
pub const DIM: &str = "\x1b[2m";
pub const CYAN: &str = "\x1b[36m";
pub const GREEN: &str = "\x1b[32m";
pub const YELLOW: &str = "\x1b[33m";
pub const RED: &str = "\x1b[31m";
pub const BLUE: &str = "\x1b[34m";
pub const MAGENTA: &str = "\x1b[35m";
pub const WHITE: &str = "\x1b[37m";

pub fn print_banner() {
    println!(
        "{}{}╔══════════════════════════════════════╗{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║     SovereignAI Edge v0.1.0          ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║     Portable Offline LLM Runtime     ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}╚══════════════════════════════════════╝{}",
        BOLD, CYAN, RESET
    );
    println!();
}

pub fn print_header(text: &str) {
    println!();
    println!("{}{}{}{}", BOLD, WHITE, text, RESET);
    println!(
        "{}{}{}",
        DIM,
        "─".repeat(text.len().max(40)),
        RESET
    );
}

pub fn print_status_bar(
    model: &str,
    mode: &str,
    ram_mb: u64,
    tps: Option<f64>,
) {
    let tps_str = match tps {
        Some(t) => format!("{:.1} tok/s", t),
        None => "—".to_string(),
    };

    println!(
        "{}{}Model:{} {} {}│{} {}Mode:{} {} {}│{} \
        {}RAM:{} {} MB {}│{} {}TPS:{} {}{}",
        BOLD, DIM, RESET,
        model,
        DIM, RESET,
        DIM, RESET,
        mode,
        DIM, RESET,
        DIM, RESET,
        ram_mb,
        DIM, RESET,
        DIM, RESET,
        tps_str, RESET,
    );
    println!(
        "{}{}{}",
        DIM,
        "─".repeat(70),
        RESET
    );
}

pub fn print_table(
    headers: &[&str],
    rows: &[Vec<String>],
    widths: &[usize],
) {
    // Header
    let header_line: String = headers
        .iter()
        .zip(widths.iter())
        .map(|(h, w)| format!("{:<width$}", h, width = w))
        .collect::<Vec<_>>()
        .join(" ");

    println!("{}{}{}{}", BOLD, DIM, header_line, RESET);
    println!(
        "{}{}{}",
        DIM,
        "─".repeat(widths.iter().sum::<usize>() + widths.len()),
        RESET
    );

    // Rows
    for row in rows {
        let line: String = row
            .iter()
            .zip(widths.iter())
            .map(|(cell, w)| format!("{:<width$}", cell, width = w))
            .collect::<Vec<_>>()
            .join(" ");
        println!("{}", line);
    }
}

pub fn print_key_value(key: &str, value: &str) {
    println!(
        "  {}{:<20}{} {}",
        DIM, key, RESET, value
    );
}

pub fn print_key_value_colored(
    key: &str,
    value: &str,
    color: &str,
) {
    println!(
        "  {}{:<20}{} {}{}{}",
        DIM, key, RESET, color, value, RESET
    );
}

pub fn print_success(msg: &str) {
    println!("{}{}✓ {}{}", BOLD, GREEN, msg, RESET);
}

pub fn print_warning(msg: &str) {
    println!("{}{}⚠ {}{}", BOLD, YELLOW, msg, RESET);
}

pub fn print_error(msg: &str) {
    println!("{}{}✗ {}{}", BOLD, RED, msg, RESET);
}

pub fn print_info(msg: &str) {
    println!("{}{}ℹ {}{}", BOLD, BLUE, msg, RESET);
}

pub fn print_metric(
    label: &str,
    value: &str,
    unit: &str,
) {
    println!(
        "  {}{:<20}{} {}{}{} {}{}{}",
        DIM, label, RESET,
        BOLD, value, RESET,
        DIM, unit, RESET,
    );
}

pub fn print_progress_stage(
    stage: &str,
    status: ProgressStatus,
) {
    let (icon, color) = match status {
        ProgressStatus::Pending => ("○", DIM),
        ProgressStatus::Active => ("◐", CYAN),
        ProgressStatus::Complete => ("●", GREEN),
        ProgressStatus::Failed => ("✗", RED),
    };
    println!(
        "  {}{}{} {}{}",
        color, icon, RESET, stage, RESET
    );
}

pub enum ProgressStatus {
    Pending,
    Active,
    Complete,
    Failed,
}

pub fn print_comparison_table(
    mode_a: &str,
    mode_b: &str,
    metrics: &[(String, String, String)],
) {
    println!();
    println!(
        "  {}{:<20} {:<15} {:<15}{}",
        BOLD, "Metric", mode_a, mode_b, RESET
    );
    println!(
        "  {}{}{}",
        DIM,
        "─".repeat(50),
        RESET
    );

    for (metric, val_a, val_b) in metrics {
        println!(
            "  {:<20} {:<15} {:<15}",
            metric, val_a, val_b
        );
    }
}

pub fn prompt_user(prompt: &str) -> String {
    print!(
        "{}{}{}>{} ",
        BOLD, CYAN, prompt, RESET
    );
    io::stdout().flush().unwrap();

    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    input.trim().to_string()
}

pub fn prompt_confirm(question: &str) -> bool {
    print!(
        "{}{} [y/N]:{} ",
        YELLOW, question, RESET
    );
    io::stdout().flush().unwrap();

    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    matches!(
        input.trim().to_lowercase().as_str(),
        "y" | "yes"
    )
}

pub fn human_readable_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.1}GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.1}MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.1}KB", bytes as f64 / KB as f64)
    } else {
        format!("{}B", bytes)
    }
}