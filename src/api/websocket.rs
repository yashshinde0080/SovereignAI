// src/api/websocket.rs
use crate::core::runtime::Runtime;
use crate::engines::traits::InferenceRequest;
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct WsRequest {
    #[serde(rename = "type")]
    msg_type: String,
    payload: serde_json::Value,
}

#[derive(Debug, Serialize)]
struct WsResponse {
    #[serde(rename = "type")]
    msg_type: String,
    payload: serde_json::Value,
}

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(runtime): State<Arc<Runtime>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, runtime))
}

async fn handle_socket(
    mut socket: WebSocket,
    runtime: Arc<Runtime>,
) {
    tracing::info!("WebSocket client connected");

    while let Some(msg) = socket.recv().await {
        match msg {
            Ok(Message::Text(text)) => {
                match serde_json::from_str::<WsRequest>(&text) {
                    Ok(request) => {
                        let response = handle_ws_message(
                            &request,
                            &runtime,
                        ).await;

                        let json =
                            serde_json::to_string(&response)
                                .unwrap_or_default();

                        if socket
                            .send(Message::Text(json.into()))
                            .await
                            .is_err()
                        {
                            break;
                        }
                    }
                    Err(e) => {
                        let error = WsResponse {
                            msg_type: "error".into(),
                            payload: serde_json::json!({
                                "message": format!(
                                    "Invalid request: {}", e
                                )
                            }),
                        };

                        let json =
                            serde_json::to_string(&error)
                                .unwrap_or_default();

                        if socket
                            .send(Message::Text(json.into()))
                            .await
                            .is_err()
                        {
                            break;
                        }
                    }
                }
            }
            Ok(Message::Close(_)) => break,
            Err(_) => break,
            _ => {}
        }
    }

    tracing::info!("WebSocket client disconnected");
}

async fn handle_ws_message(
    request: &WsRequest,
    runtime: &Runtime,
) -> WsResponse {
    match request.msg_type.as_str() {
        "chat" => {
            let prompt = request.payload["prompt"]
                .as_str()
                .unwrap_or("");

            let max_tokens = request.payload["max_tokens"]
                .as_u64()
                .unwrap_or(256) as usize;

            let temperature = request.payload["temperature"]
                .as_f64()
                .unwrap_or(0.7) as f32;

            let req = InferenceRequest {
                prompt: prompt.to_string(),
                max_tokens,
                temperature,
                top_p: 0.9,
                stop_sequences: vec![],
                stream: false,
            };

            match runtime.inference(req).await {
                Ok(response) => WsResponse {
                    msg_type: "chat_response".into(),
                    payload: serde_json::json!({
                        "text": response.text,
                        "tokens": response.tokens_generated,
                        "time_ms": response.total_time_ms,
                        "ttft_ms":
                            response.time_to_first_token_ms,
                        "mode": response.mode,
                        "tps": if response.total_time_ms > 0 {
                            response.tokens_generated as f64
                                / (response.total_time_ms
                                    as f64
                                    / 1000.0)
                        } else {
                            0.0
                        },
                    }),
                },
                Err(e) => WsResponse {
                    msg_type: "error".into(),
                    payload: serde_json::json!({
                        "message": e.to_string()
                    }),
                },
            }
        }

        "status" => {
            let status = runtime.system_status();
            WsResponse {
                msg_type: "status_response".into(),
                payload: serde_json::to_value(status)
                    .unwrap_or_default(),
            }
        }

        _ => WsResponse {
            msg_type: "error".into(),
            payload: serde_json::json!({
                "message": format!(
                    "Unknown message type: {}",
                    request.msg_type
                )
            }),
        },
    }
}