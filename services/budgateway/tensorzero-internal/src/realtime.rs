use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};
use crate::tool::Tool;
#[expect(unused_imports)]
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

// Session Management Types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RealtimeSessionRequest {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voice: Option<AudioVoice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_format: Option<AudioInputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_audio_format: Option<AudioOutputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_noise_reduction: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_response_output_tokens: Option<MaxResponseOutputTokens>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modalities: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub instructions: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub turn_detection: Option<TurnDetection>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<Tool>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_transcription: Option<InputAudioTranscription>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tracing: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RealtimeTranscriptionRequest {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_format: Option<AudioInputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_transcription: Option<InputAudioTranscription>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub turn_detection: Option<TurnDetection>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modalities: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RealtimeSessionResponse {
    pub id: String,
    pub object: String, // "realtime.session"
    pub model: String,
    pub expires_at: i64,
    pub client_secret: ClientSecret,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voice: Option<AudioVoice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_format: Option<AudioInputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_audio_format: Option<AudioOutputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_noise_reduction: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_response_output_tokens: Option<MaxResponseOutputTokens>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modalities: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub instructions: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub turn_detection: Option<TurnDetection>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<Tool>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_transcription: Option<InputAudioTranscription>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tracing: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RealtimeTranscriptionResponse {
    pub id: String,
    pub object: String, // "realtime.transcription_session"
    pub model: String,
    pub expires_at: i64,
    pub client_secret: ClientSecret,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_format: Option<AudioInputFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_audio_transcription: Option<InputAudioTranscription>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub turn_detection: Option<TurnDetection>,
    pub modalities: Vec<String>, // Always ["text"] for transcription
}

// Supporting Types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientSecret {
    pub value: String,
    pub expires_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioVoice {
    Alloy,
    Echo,
    Fable,
    Onyx,
    Nova,
    Shimmer,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioInputFormat {
    Pcm16,
    G711Ulaw,
    G711Alaw,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioOutputFormat {
    Pcm16,
    G711Ulaw,
    G711Alaw,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum MaxResponseOutputTokens {
    Number(u32),
    Infinite(String), // "inf"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TurnDetection {
    #[serde(rename = "type")]
    pub detection_type: TurnDetectionType,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub threshold: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prefix_padding_ms: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub silence_duration_ms: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub create_response: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interrupt_response: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TurnDetectionType {
    ServerVad,
    None,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InputAudioTranscription {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt: Option<String>,
}

// Provider Traits
#[async_trait::async_trait]
pub trait RealtimeSessionProvider {
    async fn create_session(
        &self,
        request: &RealtimeSessionRequest,
        client: &Client,
        credentials: &InferenceCredentials,
    ) -> Result<RealtimeSessionResponse, Error>;
}

#[async_trait::async_trait]
pub trait RealtimeTranscriptionProvider {
    async fn create_transcription_session(
        &self,
        request: &RealtimeTranscriptionRequest,
        client: &Client,
        credentials: &InferenceCredentials,
    ) -> Result<RealtimeTranscriptionResponse, Error>;
}

// Internal Request Types for provider routing
#[derive(Debug, Clone)]
pub struct RealtimeSessionInternalRequest {
    pub id: Uuid,
    pub model: Arc<str>,
    pub voice: Option<AudioVoice>,
    pub input_audio_format: Option<AudioInputFormat>,
    pub output_audio_format: Option<AudioOutputFormat>,
    pub input_audio_noise_reduction: Option<bool>,
    pub temperature: Option<f32>,
    pub max_response_output_tokens: Option<MaxResponseOutputTokens>,
    pub modalities: Option<Vec<String>>,
    pub instructions: Option<String>,
    pub turn_detection: Option<TurnDetection>,
    pub tools: Option<Vec<Tool>>,
    pub tool_choice: Option<String>,
    pub input_audio_transcription: Option<InputAudioTranscription>,
    pub include: Option<Vec<String>>,
    pub speed: Option<f32>,
    pub tracing: Option<serde_json::Value>,
}

#[derive(Debug, Clone)]
pub struct RealtimeTranscriptionInternalRequest {
    pub id: Uuid,
    pub model: Arc<str>,
    pub input_audio_format: Option<AudioInputFormat>,
    pub input_audio_transcription: Option<InputAudioTranscription>,
    pub turn_detection: Option<TurnDetection>,
    pub modalities: Option<Vec<String>>,
}

// Internal Response Types
#[derive(Debug, Clone)]
pub struct RealtimeSessionInternalResponse {
    pub id: Uuid,
    pub session_id: String,
    pub model: Arc<str>,
    pub expires_at: i64,
    pub client_secret: ClientSecret,
    pub voice: Option<AudioVoice>,
    pub input_audio_format: Option<AudioInputFormat>,
    pub output_audio_format: Option<AudioOutputFormat>,
    pub input_audio_noise_reduction: Option<bool>,
    pub temperature: Option<f32>,
    pub max_response_output_tokens: Option<MaxResponseOutputTokens>,
    pub modalities: Option<Vec<String>>,
    pub instructions: Option<String>,
    pub turn_detection: Option<TurnDetection>,
    pub tools: Option<Vec<Tool>>,
    pub tool_choice: Option<String>,
    pub input_audio_transcription: Option<InputAudioTranscription>,
    pub include: Option<Vec<String>>,
    pub speed: Option<f32>,
    pub tracing: Option<serde_json::Value>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone)]
pub struct RealtimeTranscriptionInternalResponse {
    pub id: Uuid,
    pub session_id: String,
    pub model: Arc<str>,
    pub expires_at: i64,
    pub client_secret: ClientSecret,
    pub input_audio_format: Option<AudioInputFormat>,
    pub input_audio_transcription: Option<InputAudioTranscription>,
    pub turn_detection: Option<TurnDetection>,
    pub modalities: Option<Vec<String>>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

// Conversion implementations
impl From<RealtimeSessionRequest> for RealtimeSessionInternalRequest {
    fn from(req: RealtimeSessionRequest) -> Self {
        Self {
            id: Uuid::now_v7(),
            model: req.model.into(),
            voice: req.voice,
            input_audio_format: req.input_audio_format,
            output_audio_format: req.output_audio_format,
            input_audio_noise_reduction: req.input_audio_noise_reduction,
            temperature: req.temperature,
            max_response_output_tokens: req.max_response_output_tokens,
            modalities: req.modalities,
            instructions: req.instructions,
            turn_detection: req.turn_detection,
            tools: req.tools,
            tool_choice: req.tool_choice,
            input_audio_transcription: req.input_audio_transcription,
            include: req.include,
            speed: req.speed,
            tracing: req.tracing,
        }
    }
}

impl From<RealtimeTranscriptionRequest> for RealtimeTranscriptionInternalRequest {
    fn from(req: RealtimeTranscriptionRequest) -> Self {
        Self {
            id: Uuid::now_v7(),
            model: req.model.into(),
            input_audio_format: req.input_audio_format,
            input_audio_transcription: req.input_audio_transcription,
            turn_detection: req.turn_detection,
            modalities: req.modalities,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audio_voice_serialization() {
        let voice = AudioVoice::Alloy;
        let serialized = serde_json::to_string(&voice).unwrap();
        assert_eq!(serialized, "\"alloy\"");

        let deserialized: AudioVoice = serde_json::from_str("\"nova\"").unwrap();
        assert!(matches!(deserialized, AudioVoice::Nova));
    }

    #[test]
    fn test_audio_input_format_serialization() {
        let format = AudioInputFormat::Pcm16;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"pcm16\"");

        let deserialized: AudioInputFormat = serde_json::from_str("\"g711_ulaw\"").unwrap();
        assert!(matches!(deserialized, AudioInputFormat::G711Ulaw));
    }

    #[test]
    fn test_max_response_output_tokens_serialization() {
        let tokens_num = MaxResponseOutputTokens::Number(1000);
        let serialized = serde_json::to_string(&tokens_num).unwrap();
        assert_eq!(serialized, "1000");

        let tokens_inf = MaxResponseOutputTokens::Infinite("inf".to_string());
        let serialized = serde_json::to_string(&tokens_inf).unwrap();
        assert_eq!(serialized, "\"inf\"");
    }

    #[test]
    fn test_turn_detection_serialization() {
        let turn_detection = TurnDetection {
            detection_type: TurnDetectionType::ServerVad,
            threshold: Some(0.5),
            prefix_padding_ms: Some(300),
            silence_duration_ms: Some(200),
            create_response: Some(true),
            interrupt_response: Some(true),
        };

        let serialized = serde_json::to_string(&turn_detection).unwrap();
        let deserialized: TurnDetection = serde_json::from_str(&serialized).unwrap();

        assert!(matches!(
            deserialized.detection_type,
            TurnDetectionType::ServerVad
        ));
        assert_eq!(deserialized.threshold, Some(0.5));
        assert_eq!(deserialized.prefix_padding_ms, Some(300));
        assert_eq!(deserialized.silence_duration_ms, Some(200));
        assert_eq!(deserialized.create_response, Some(true));
        assert_eq!(deserialized.interrupt_response, Some(true));
    }

    #[test]
    fn test_realtime_session_request_from_conversion() {
        let request = RealtimeSessionRequest {
            model: "gpt-4o-realtime".to_string(),
            voice: Some(AudioVoice::Alloy),
            input_audio_format: Some(AudioInputFormat::Pcm16),
            output_audio_format: Some(AudioOutputFormat::Pcm16),
            input_audio_noise_reduction: None,
            temperature: Some(0.8),
            max_response_output_tokens: Some(MaxResponseOutputTokens::Infinite("inf".to_string())),
            modalities: Some(vec!["text".to_string(), "audio".to_string()]),
            instructions: Some("You are a helpful assistant.".to_string()),
            turn_detection: None,
            tools: None,
            tool_choice: None,
            input_audio_transcription: None,
            include: None,
            speed: None,
            tracing: None,
        };

        let internal_request: RealtimeSessionInternalRequest = request.into();
        assert_eq!(internal_request.model.as_ref(), "gpt-4o-realtime");
        assert!(matches!(internal_request.voice, Some(AudioVoice::Alloy)));
        assert!(matches!(
            internal_request.input_audio_format,
            Some(AudioInputFormat::Pcm16)
        ));
        assert_eq!(internal_request.temperature, Some(0.8));
    }

    #[test]
    fn test_realtime_transcription_request_from_conversion() {
        let request = RealtimeTranscriptionRequest {
            model: "whisper-1".to_string(),
            input_audio_format: Some(AudioInputFormat::Pcm16),
            input_audio_transcription: Some(InputAudioTranscription {
                model: "whisper-1".to_string(),
                language: Some("en".to_string()),
                prompt: None,
            }),
            turn_detection: None,
            modalities: Some(vec!["text".to_string()]),
        };

        let internal_request: RealtimeTranscriptionInternalRequest = request.into();
        assert_eq!(internal_request.model.as_ref(), "whisper-1");
        assert!(matches!(
            internal_request.input_audio_format,
            Some(AudioInputFormat::Pcm16)
        ));
        assert!(internal_request.input_audio_transcription.is_some());
    }

    #[test]
    fn test_realtime_session_response_json_format() {
        let response = RealtimeSessionResponse {
            id: "sess_123".to_string(),
            object: "realtime.session".to_string(),
            model: "gpt-4o-realtime-preview".to_string(),
            expires_at: 1751348520,
            client_secret: ClientSecret {
                value: "ek_686372d0921881918f11db13194992b4".to_string(),
                expires_at: 1751348520,
            },
            voice: Some(AudioVoice::Alloy),
            input_audio_format: Some(AudioInputFormat::Pcm16),
            output_audio_format: Some(AudioOutputFormat::Pcm16),
            input_audio_noise_reduction: None,
            temperature: Some(0.8),
            max_response_output_tokens: Some(MaxResponseOutputTokens::Infinite("inf".to_string())),
            modalities: Some(vec!["audio".to_string(), "text".to_string()]),
            instructions: Some("You are a friendly assistant.".to_string()),
            turn_detection: Some(TurnDetection {
                detection_type: TurnDetectionType::ServerVad,
                threshold: Some(0.5),
                prefix_padding_ms: Some(300),
                silence_duration_ms: Some(200),
                create_response: Some(true),
                interrupt_response: Some(true),
            }),
            tools: Some(vec![]),
            tool_choice: Some("auto".to_string()),
            input_audio_transcription: None,
            include: None,
            speed: Some(1.0),
            tracing: None,
        };

        let json = serde_json::to_string_pretty(&response).unwrap();

        // Verify key fields are present and correctly formatted
        assert!(json.contains("\"object\": \"realtime.session\""));
        assert!(json.contains("\"voice\": \"alloy\""));
        assert!(json.contains("\"input_audio_format\": \"pcm16\""));
        assert!(json.contains("\"max_response_output_tokens\": \"inf\""));
        assert!(json.contains("\"type\": \"server_vad\""));
        assert!(json.contains("\"create_response\": true"));
        assert!(json.contains("\"interrupt_response\": true"));
        assert!(json.contains("\"tool_choice\": \"auto\""));
        assert!(json.contains("\"speed\": 1.0"));
    }

    #[test]
    fn test_realtime_transcription_response_json_format() {
        let response = RealtimeTranscriptionResponse {
            id: "ts_123".to_string(),
            object: "realtime.transcription_session".to_string(),
            model: "gpt-4o-mini-transcribe".to_string(),
            expires_at: 0,
            client_secret: ClientSecret {
                value: "eph_transcribe_686372d0921881918f11db13194992b4".to_string(),
                expires_at: 1751348520,
            },
            input_audio_format: Some(AudioInputFormat::Pcm16),
            input_audio_transcription: Some(InputAudioTranscription {
                model: "whisper-1".to_string(),
                language: Some("en".to_string()),
                prompt: Some("Transcribe this audio".to_string()),
            }),
            turn_detection: Some(TurnDetection {
                detection_type: TurnDetectionType::ServerVad,
                threshold: Some(0.5),
                prefix_padding_ms: Some(300),
                silence_duration_ms: Some(200),
                create_response: Some(true),
                interrupt_response: Some(true),
            }),
            modalities: vec!["text".to_string()],
        };

        let json = serde_json::to_string_pretty(&response).unwrap();

        // Verify key fields are present and correctly formatted
        assert!(json.contains("\"object\": \"realtime.transcription_session\""));
        assert!(json.contains("\"expires_at\": 0"));
        assert!(json.contains("\"modalities\": [\n    \"text\"\n  ]"));
        assert!(json.contains("\"input_audio_format\": \"pcm16\""));

        // Verify it doesn't contain realtime-only fields
        assert!(!json.contains("\"voice\""));
        assert!(!json.contains("\"instructions\""));
        assert!(!json.contains("\"tools\""));
        assert!(!json.contains("\"output_audio_format\""));
    }
}
