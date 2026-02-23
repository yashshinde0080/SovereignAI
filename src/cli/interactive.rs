// src/cli/interactive.rs
use crate::cli::display;
use crate::core::hardware_detector::ExecutionMode;
use crate::core::runtime::Runtime;
use crate::engines::traits::InferenceRequest;
use crate::model_manager::resolver::ModelResolver;
use anyhow::Result;
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Instant;

struct SessionState {
    model_name: String,
    mode: String,
    total_tokens: usize,
    total_time_ms: u128,
    turn_count: usize,
}

impl SessionState {
    fn avg_tps(&self) -> f64 {
        if self.total_time_ms > 0 {
            self.total_tokens as f64
                / (self.total_time_ms as f64 / 1000.0)
        } else {
            0.0
        }
    }
}

pub async fn start_session(
    runtime: Arc<Runtime>,
    model_spec: &str,
    mode_str: &str,
) -> Result<()> {
    display::print_banner();

    let resolver = ModelResolver::new(runtime.registry.clone());

    display::print_info(&format!(
        "Resolving model: {}", model_spec
    ));

    let model = resolver
        .resolve(model_spec, &runtime.hardware)
        .await?;

    let mode: ExecutionMode = mode_str.parse()?;

    let resolved_mode = match &mode {
        ExecutionMode::Auto => runtime.hardware.recommend_mode(
            model.file_size_bytes,
            runtime.config.runtime.max_ram_usage_percent,
        ),
        other => other.clone(),
    };

    display::print_header("Loading Model");
    display::print_key_value("Model:", &model.name);
    display::print_key_value("Mode:", &resolved_mode.to_string());

    runtime.load_model(model.clone(), mode)?;
    display::print_success("Model loaded");
    println!();

    println!(
        "{}{}Interactive Chat Session{}",
        display::BOLD,
        display::CYAN,
        display::RESET
    );
    println!(
        "{}Commands: /stats /mode /model /clear /help /exit{}",
        display::DIM,
        display::RESET
    );
    println!();

    let mut state = SessionState {
        model_name: model.name.clone(),
        mode: resolved_mode.to_string(),
        total_tokens: 0,
        total_time_ms: 0,
        turn_count: 0,
    };

    display::print_status_bar(
        &state.model_name,
        &state.mode,
        runtime.memory_tracker.current_usage() / (1024 * 1024),
        None,
    );

    loop {
        print!(
            "\n{}{}User >{} ",
            display::BOLD,
            display::BLUE,
            display::RESET,
        );
        io::stdout().flush()?;

        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let input = input.trim();

        if input.is_empty() {
            continue;
        }

        // Handle commands
        if input.starts_with('/') {
            match handle_command(input, &state, &runtime) {
                CommandResult::Continue => continue,
                CommandResult::Exit => {
                    display::print_info("Session ended.");
                    print_session_summary(&state);
                    break;
                }
                CommandResult::Error(msg) => {
                    display::print_error(&msg);
                    continue;
                }
            }
        }

        // Inference
        let request = InferenceRequest {
            prompt: input.to_string(),
            max_tokens: 512,
            temperature: 0.7,
            top_p: 0.9,
            stop_sequences: vec![],
            stream: false,
        };

        let start = Instant::now();

        match runtime.inference(request).await {
            Ok(response) => {
                let elapsed = start.elapsed();
                let tps = if elapsed.as_millis() > 0 {
                    response.tokens_generated as f64
                        / elapsed.as_secs_f64()
                } else {
                    0.0
                };

                // Print response
                println!(
                    "\n{}{}Assistant >{} {}",
                    display::BOLD,
                    display::GREEN,
                    display::RESET,
                    response.text,
                );

                // Print inline metrics
                println!(
                    "{}[{} tokens, {}ms, {:.1} tok/s]{}",
                    display::DIM,
                    response.tokens_generated,
                    response.total_time_ms,
                    tps,
                    display::RESET,
                );

                // Update state
                state.total_tokens += response.tokens_generated;
                state.total_time_ms += response.total_time_ms;
                state.turn_count += 1;
            }
            Err(e) => {
                display::print_error(&format!(
                    "Inference error: {}", e
                ));
            }
        }
    }

    Ok(())
}

enum CommandResult {
    Continue,
    Exit,
    Error(String),
}

fn handle_command(
    cmd: &str,
    state: &SessionState,
    runtime: &Runtime,
) -> CommandResult {
    match cmd {
        "/exit" | "/quit" | "/q" => CommandResult::Exit,

        "/stats" => {
            display::print_header("Session Statistics");
            display::print_key_value(
                "Model:",
                &state.model_name,
            );
            display::print_key_value(
                "Mode:",
                &state.mode,
            );
            display::print_key_value(
                "Turns:",
                &state.turn_count.to_string(),
            );
            display::print_key_value(
                "Total tokens:",
                &state.total_tokens.to_string(),
            );
            display::print_key_value(
                "Total time:",
                &format!("{}ms", state.total_time_ms),
            );
            display::print_key_value(
                "Avg speed:",
                &format!("{:.1} tok/s", state.avg_tps()),
            );

            let snapshot = runtime.memory_tracker.snapshot();
            display::print_key_value(
                "RAM used:",
                &display::human_readable_size(
                    snapshot.total_used
                ),
            );
            display::print_key_value(
                "RAM max:",
                &display::human_readable_size(
                    snapshot.total_max
                ),
            );
            display::print_key_value(
                "RAM %:",
                &format!(
                    "{:.1}%",
                    (snapshot.total_used as f64
                        / snapshot.total_max as f64)
                        * 100.0
                ),
            );

            CommandResult::Continue
        }

        "/clear" => {
            // Clear terminal
            print!("\x1b[2J\x1b[1;1H");
            display::print_status_bar(
                &state.model_name,
                &state.mode,
                runtime.memory_tracker.current_usage()
                    / (1024 * 1024),
                Some(state.avg_tps()),
            );
            CommandResult::Continue
        }

        "/help" => {
            display::print_header("Commands");
            display::print_key_value(
                "/stats",
                "Show session statistics",
            );
            display::print_key_value(
                "/clear",
                "Clear screen",
            );
            display::print_key_value(
                "/help",
                "Show this help",
            );
            display::print_key_value(
                "/exit",
                "End session",
            );
            CommandResult::Continue
        }

        _ => CommandResult::Error(format!(
            "Unknown command: {}. Type /help",
            cmd
        )),
    }
}

fn print_session_summary(state: &SessionState) {
    display::print_header("Session Summary");
    display::print_key_value(
        "Turns:",
        &state.turn_count.to_string(),
    );
    display::print_key_value(
        "Total tokens:",
        &state.total_tokens.to_string(),
    );
    display::print_key_value(
        "Avg speed:",
        &format!("{:.1} tok/s", state.avg_tps()),
    );
}