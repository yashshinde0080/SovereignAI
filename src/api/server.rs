// src/api/server.rs
use crate::api::routes;
use crate::cli::display;
use crate::core::runtime::Runtime;
use anyhow::Result;
use axum::Router;
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::services::ServeDir;

pub async fn start_server(
    runtime: Arc<Runtime>,
    port: u16,
    open_browser: bool,
) -> Result<()> {
    let bind_addr = if runtime.config.security.allow_remote_access {
        format!("0.0.0.0:{}", port)
    } else {
        format!("127.0.0.1:{}", port)
    };

    let addr: SocketAddr = bind_addr.parse()?;

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Serve static Web UI files
    let static_service = ServeDir::new("ui/web/build")
        .fallback(
            tower_http::services::ServeFile::new(
                "ui/web/build/index.html"
            ),
        );

    let app = Router::new()
        .merge(routes::create_routes())
        .nest_service("/", static_service)
        .layer(cors)
        .with_state(runtime.clone());

    display::print_banner();
    display::print_header("API Server");
    display::print_key_value(
        "Address:",
        &format!("http://{}", addr),
    );
    display::print_key_value(
        "API:",
        &format!("http://{}/v1/", addr),
    );
    display::print_key_value(
        "Web UI:",
        &format!("http://{}", addr),
    );

    if !runtime.config.security.allow_remote_access {
        display::print_info(
            "Bound to localhost only (secure mode)",
        );
    }

    println!();
    display::print_success("Server started");

    if open_browser {
        let url = format!("http://{}", addr);
        let _ = open::that(&url);
    }

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}