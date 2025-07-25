#![expect(clippy::print_stdout)]

use reqwest::{Client, StatusCode};
use serde_json::{json, Value};

use crate::common::get_gateway_endpoint;

// NOTE: These tests require a running gateway instance with the realtime endpoints enabled.
// To run these tests:
// 1. Ensure the test_tensorzero.toml includes the realtime models (gpt-4o-realtime-preview, etc.)
// 2. Start the gateway: cargo run --bin gateway -- --config-file test_tensorzero.toml
// 3. Run the tests: cargo test --package tensorzero-internal --features e2e_tests --test '*' realtime

#[tokio::test]
async fn test_realtime_session_creation() {
    let client = Client::new();

    // Test creating a realtime session with minimal parameters
    let payload = json!({
        "model": "gpt-4o-realtime-preview",
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Check Response is OK
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("Realtime session response: {response_json:?}");

    // Verify response structure matches OpenAI format
    assert_eq!(
        response_json.get("object").unwrap().as_str().unwrap(),
        "realtime.session"
    );
    assert!(response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("sess_"));
    assert_eq!(
        response_json.get("model").unwrap().as_str().unwrap(),
        "gpt-4o-realtime-preview"
    );
    assert_eq!(
        response_json.get("expires_at").unwrap().as_i64().unwrap(),
        0
    );

    // Check client_secret structure
    let client_secret = response_json.get("client_secret").unwrap();
    assert!(client_secret
        .get("value")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("eph_"));
    assert!(client_secret.get("expires_at").unwrap().as_i64().unwrap() > 0);

    // Check default values
    assert_eq!(
        response_json.get("voice").unwrap().as_str().unwrap(),
        "alloy"
    );
    assert_eq!(
        response_json
            .get("input_audio_format")
            .unwrap()
            .as_str()
            .unwrap(),
        "pcm16"
    );
    assert_eq!(
        response_json
            .get("output_audio_format")
            .unwrap()
            .as_str()
            .unwrap(),
        "pcm16"
    );
    assert_eq!(
        response_json.get("temperature").unwrap().as_f64().unwrap(),
        0.8
    );
    assert_eq!(
        response_json
            .get("max_response_output_tokens")
            .unwrap()
            .as_str()
            .unwrap(),
        "inf"
    );
    assert_eq!(
        response_json.get("tool_choice").unwrap().as_str().unwrap(),
        "auto"
    );
    assert_eq!(response_json.get("speed").unwrap().as_f64().unwrap(), 1.0);

    // Check modalities
    let modalities = response_json.get("modalities").unwrap().as_array().unwrap();
    assert_eq!(modalities.len(), 2);
    assert!(modalities.contains(&json!("text")));
    assert!(modalities.contains(&json!("audio")));

    // Check turn detection
    let turn_detection = response_json.get("turn_detection").unwrap();
    assert_eq!(
        turn_detection.get("type").unwrap().as_str().unwrap(),
        "server_vad"
    );
    assert_eq!(
        turn_detection.get("threshold").unwrap().as_f64().unwrap(),
        0.5
    );
    assert_eq!(
        turn_detection
            .get("prefix_padding_ms")
            .unwrap()
            .as_u64()
            .unwrap(),
        300
    );
    assert_eq!(
        turn_detection
            .get("silence_duration_ms")
            .unwrap()
            .as_u64()
            .unwrap(),
        200
    );
    assert!(turn_detection
        .get("create_response")
        .unwrap()
        .as_bool()
        .unwrap());
    assert!(turn_detection
        .get("interrupt_response")
        .unwrap()
        .as_bool()
        .unwrap());

    // Check tools is empty array
    let tools = response_json.get("tools").unwrap().as_array().unwrap();
    assert_eq!(tools.len(), 0);
}

#[tokio::test]
async fn test_realtime_session_creation_with_custom_params() {
    let client = Client::new();

    // Test creating a realtime session with custom parameters
    let payload = json!({
        "model": "gpt-4o-realtime-preview",
        "voice": "nova",
        "temperature": 0.5,
        "instructions": "You are a helpful coding assistant.",
        "modalities": ["text"],
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.7,
            "prefix_padding_ms": 500,
            "silence_duration_ms": 300,
        },
        "input_audio_format": "g711_ulaw",
        "output_audio_format": "g711_alaw",
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Check Response is OK
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("Custom realtime session response: {response_json:?}");

    // Verify custom parameters are preserved
    assert_eq!(
        response_json.get("voice").unwrap().as_str().unwrap(),
        "nova"
    );
    assert_eq!(
        response_json.get("temperature").unwrap().as_f64().unwrap(),
        0.5
    );
    assert_eq!(
        response_json.get("instructions").unwrap().as_str().unwrap(),
        "You are a helpful coding assistant."
    );
    assert_eq!(
        response_json
            .get("input_audio_format")
            .unwrap()
            .as_str()
            .unwrap(),
        "g711_ulaw"
    );
    assert_eq!(
        response_json
            .get("output_audio_format")
            .unwrap()
            .as_str()
            .unwrap(),
        "g711_alaw"
    );

    // Check custom modalities
    let modalities = response_json.get("modalities").unwrap().as_array().unwrap();
    assert_eq!(modalities.len(), 1);
    assert!(modalities.contains(&json!("text")));

    // Check custom turn detection
    let turn_detection = response_json.get("turn_detection").unwrap();
    assert_eq!(
        turn_detection.get("threshold").unwrap().as_f64().unwrap(),
        0.7
    );
    assert_eq!(
        turn_detection
            .get("prefix_padding_ms")
            .unwrap()
            .as_u64()
            .unwrap(),
        500
    );
    assert_eq!(
        turn_detection
            .get("silence_duration_ms")
            .unwrap()
            .as_u64()
            .unwrap(),
        300
    );
}

#[tokio::test]
async fn test_transcription_session_creation() {
    let client = Client::new();

    // Test creating a transcription session
    let payload = json!({
        "model": "gpt-4o-mini-transcribe",
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": "en",
            "prompt": "Transcribe this conversation"
        }
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/transcription_sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Check Response is OK
    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    println!("Transcription session response: {response_json:?}");

    // Verify response structure matches OpenAI format
    assert_eq!(
        response_json.get("object").unwrap().as_str().unwrap(),
        "realtime.transcription_session"
    );
    assert!(response_json
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("sess_"));
    assert_eq!(
        response_json.get("model").unwrap().as_str().unwrap(),
        "gpt-4o-mini-transcribe"
    );
    assert_eq!(
        response_json.get("expires_at").unwrap().as_i64().unwrap(),
        0
    );

    // Check client_secret structure
    let client_secret = response_json.get("client_secret").unwrap();
    assert!(client_secret
        .get("value")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("eph_transcribe_"));
    assert!(client_secret.get("expires_at").unwrap().as_i64().unwrap() > 0);

    // Check defaults
    assert_eq!(
        response_json
            .get("input_audio_format")
            .unwrap()
            .as_str()
            .unwrap(),
        "pcm16"
    );

    // Check modalities is always ["text"] for transcription
    let modalities = response_json.get("modalities").unwrap().as_array().unwrap();
    assert_eq!(modalities.len(), 1);
    assert_eq!(modalities[0].as_str().unwrap(), "text");

    // Check input_audio_transcription
    let input_audio_transcription = response_json.get("input_audio_transcription").unwrap();
    assert_eq!(
        input_audio_transcription
            .get("model")
            .unwrap()
            .as_str()
            .unwrap(),
        "whisper-1"
    );
    assert_eq!(
        input_audio_transcription
            .get("language")
            .unwrap()
            .as_str()
            .unwrap(),
        "en"
    );
    assert_eq!(
        input_audio_transcription
            .get("prompt")
            .unwrap()
            .as_str()
            .unwrap(),
        "Transcribe this conversation"
    );

    // Verify realtime-only fields are not present
    assert!(response_json.get("voice").is_none());
    assert!(response_json.get("output_audio_format").is_none());
    assert!(response_json.get("instructions").is_none());
    assert!(response_json.get("tools").is_none());
    assert!(response_json.get("tool_choice").is_none());
    assert!(response_json.get("speed").is_none());
}

#[tokio::test]
async fn test_realtime_session_invalid_model() {
    let client = Client::new();

    // Test with a model that doesn't support realtime sessions
    let payload = json!({
        "model": "gpt-4",
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Should return error
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json = response.json::<Value>().await.unwrap();
    let error_message = error_json
        .get("error")
        .unwrap()
        .get("message")
        .unwrap()
        .as_str()
        .unwrap();
    assert!(error_message.contains("not found or does not support realtime sessions"));
}

#[tokio::test]
async fn test_transcription_session_invalid_model() {
    let client = Client::new();

    // Test with a model that doesn't support transcription sessions
    let payload = json!({
        "model": "gpt-4",
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/transcription_sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    // Should return error
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let error_json = response.json::<Value>().await.unwrap();
    let error_message = error_json
        .get("error")
        .unwrap()
        .get("message")
        .unwrap()
        .as_str()
        .unwrap();
    assert!(error_message.contains("not found or does not support realtime transcription"));
}

#[tokio::test]
async fn test_max_response_output_tokens_formats() {
    let client = Client::new();

    // Test with numeric max tokens
    let payload = json!({
        "model": "gpt-4o-realtime-preview",
        "max_response_output_tokens": 1000,
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    assert_eq!(
        response_json
            .get("max_response_output_tokens")
            .unwrap()
            .as_u64()
            .unwrap(),
        1000
    );

    // Test with "inf" string
    let payload = json!({
        "model": "gpt-4o-realtime-preview",
        "max_response_output_tokens": "inf",
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();
    assert_eq!(
        response_json
            .get("max_response_output_tokens")
            .unwrap()
            .as_str()
            .unwrap(),
        "inf"
    );
}

#[tokio::test]
async fn test_realtime_session_with_tools() {
    let client = Client::new();

    // Test with tools
    let payload = json!({
        "model": "gpt-4o-realtime-preview",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"]
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
        "tool_choice": "required"
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&payload)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let response_json = response.json::<Value>().await.unwrap();

    // Check tools are preserved
    let tools = response_json.get("tools").unwrap().as_array().unwrap();
    assert_eq!(tools.len(), 1);
    let tool = &tools[0];
    assert_eq!(tool.get("type").unwrap().as_str().unwrap(), "function");
    assert_eq!(
        tool.get("function")
            .unwrap()
            .get("name")
            .unwrap()
            .as_str()
            .unwrap(),
        "get_weather"
    );

    // Check tool_choice
    assert_eq!(
        response_json.get("tool_choice").unwrap().as_str().unwrap(),
        "required"
    );
}

// SDK-style test using the response structure
#[tokio::test]
async fn test_sdk_style_realtime_session() {
    let client = Client::new();

    // Create a session like the SDK would
    let create_params = json!({
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "voice": "alloy",
        "instructions": "You are a friendly assistant.",
        "modalities": ["audio", "text"],
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 200,
            "create_response": true,
            "interrupt_response": true
        },
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "temperature": 0.8,
        "max_response_output_tokens": "inf",
        "tool_choice": "auto",
        "tools": []
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/sessions"))
        .json(&create_params)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let session = response.json::<Value>().await.unwrap();

    // Verify the response matches the expected SDK format
    assert!(session
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("sess_"));
    assert_eq!(
        session.get("object").unwrap().as_str().unwrap(),
        "realtime.session"
    );
    assert_eq!(session.get("expires_at").unwrap().as_i64().unwrap(), 0);

    let client_secret = session.get("client_secret").unwrap();
    assert!(client_secret
        .get("value")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("eph_"));
    let secret_expires_at = client_secret.get("expires_at").unwrap().as_i64().unwrap();
    assert!(secret_expires_at > 0);

    // Verify all fields match the request
    assert_eq!(
        session.get("model").unwrap().as_str().unwrap(),
        "gpt-4o-realtime-preview-2024-12-17"
    );
    assert_eq!(session.get("voice").unwrap().as_str().unwrap(), "alloy");
    assert_eq!(
        session.get("instructions").unwrap().as_str().unwrap(),
        "You are a friendly assistant."
    );

    let modalities = session.get("modalities").unwrap().as_array().unwrap();
    assert_eq!(modalities.len(), 2);
    assert!(modalities.contains(&json!("audio")));
    assert!(modalities.contains(&json!("text")));

    // Verify turn detection
    let td = session.get("turn_detection").unwrap();
    assert_eq!(td.get("type").unwrap().as_str().unwrap(), "server_vad");
    assert!(td.get("create_response").unwrap().as_bool().unwrap());
    assert!(td.get("interrupt_response").unwrap().as_bool().unwrap());

    // The session ID and client secret can be used for WebSocket connection
    println!("Session created with ID: {}", session.get("id").unwrap());
    println!("Client secret: {}", client_secret.get("value").unwrap());
}

// SDK-style transcription session test
#[tokio::test]
async fn test_sdk_style_transcription_session() {
    let client = Client::new();

    // Create a transcription session like the SDK would
    let create_params = json!({
        "model": "gpt-4o-mini-transcribe",
        "input_audio_format": "pcm16",
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": "en",
            "prompt": "Transcribe this audio"
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 200
        },
        "modalities": ["text"]
    });

    let response = client
        .post(get_gateway_endpoint("/v1/realtime/transcription_sessions"))
        .json(&create_params)
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let session = response.json::<Value>().await.unwrap();

    // Verify the response matches the expected SDK format
    assert!(session
        .get("id")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("sess_"));
    assert_eq!(
        session.get("object").unwrap().as_str().unwrap(),
        "realtime.transcription_session"
    );
    assert_eq!(session.get("expires_at").unwrap().as_i64().unwrap(), 0);

    let client_secret = session.get("client_secret").unwrap();
    assert!(client_secret
        .get("value")
        .unwrap()
        .as_str()
        .unwrap()
        .starts_with("eph_transcribe_"));

    // Verify modalities is always ["text"] for transcription
    let modalities = session.get("modalities").unwrap().as_array().unwrap();
    assert_eq!(modalities.len(), 1);
    assert_eq!(modalities[0].as_str().unwrap(), "text");

    // Verify input_audio_transcription
    let iat = session.get("input_audio_transcription").unwrap();
    assert_eq!(iat.get("model").unwrap().as_str().unwrap(), "whisper-1");
    assert_eq!(iat.get("language").unwrap().as_str().unwrap(), "en");
}
