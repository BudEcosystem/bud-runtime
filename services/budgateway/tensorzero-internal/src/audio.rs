use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};
use futures::Stream;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use uuid::Uuid;

// Audio transcription types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioTranscriptionRequest {
    pub id: Uuid,
    pub file: Vec<u8>,
    pub filename: String,
    pub model: Arc<str>,
    pub language: Option<String>,
    pub prompt: Option<String>,
    pub response_format: Option<AudioTranscriptionResponseFormat>,
    pub temperature: Option<f32>,
    pub timestamp_granularities: Option<Vec<TimestampGranularity>>,
    pub chunking_strategy: Option<ChunkingStrategy>,
    pub include: Option<Vec<String>>,
    pub stream: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ChunkingStrategy {
    #[serde(rename = "auto")]
    Auto,
    #[serde(rename = "static")]
    Static {
        #[serde(skip_serializing_if = "Option::is_none")]
        chunk_size: Option<u32>,
        #[serde(skip_serializing_if = "Option::is_none")]
        overlap_size: Option<u32>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioTranscriptionResponseFormat {
    Json,
    Text,
    Srt,
    VerboseJson,
    Vtt,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TimestampGranularity {
    Word,
    Segment,
}

#[derive(Debug, Clone)]
pub struct AudioTranscriptionResponse {
    pub id: Uuid,
    pub text: String,
    pub language: Option<String>,
    pub duration: Option<f32>,
    pub words: Option<Vec<WordTimestamp>>,
    pub segments: Option<Vec<SegmentTimestamp>>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WordTimestamp {
    pub word: String,
    pub start: f32,
    pub end: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SegmentTimestamp {
    pub id: u64,
    pub seek: u64,
    pub start: f32,
    pub end: f32,
    pub text: String,
    pub tokens: Vec<u64>,
    pub temperature: f32,
    pub avg_logprob: f32,
    pub compression_ratio: f32,
    pub no_speech_prob: f32,
}

// Audio translation types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioTranslationRequest {
    pub id: Uuid,
    pub file: Vec<u8>,
    pub filename: String,
    pub model: Arc<str>,
    pub prompt: Option<String>,
    pub response_format: Option<AudioTranscriptionResponseFormat>,
    pub temperature: Option<f32>,
}

#[derive(Debug, Clone)]
pub struct AudioTranslationResponse {
    pub id: Uuid,
    pub text: String,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

// Text-to-speech types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextToSpeechRequest {
    pub id: Uuid,
    pub input: String,
    pub model: Arc<str>,
    pub voice: AudioVoice,
    pub response_format: Option<AudioOutputFormat>,
    pub speed: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AudioVoice {
    Alloy,
    Ash,
    Ballad,
    Coral,
    Echo,
    Fable,
    Onyx,
    Nova,
    Sage,
    Shimmer,
    Verse,
    #[serde(untagged)]
    Other(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AudioOutputFormat {
    Mp3,
    Opus,
    Aac,
    Flac,
    Wav,
    Pcm,
}

#[derive(Debug, Clone)]
pub struct TextToSpeechResponse {
    pub id: Uuid,
    pub audio_data: Vec<u8>,
    pub format: AudioOutputFormat,
    pub created: u64,
    pub raw_request: String,
    pub usage: Usage,
    pub latency: Latency,
}

// Provider response types
#[derive(Debug, Clone)]
pub struct AudioTranscriptionProviderResponse {
    pub id: Uuid,
    pub text: String,
    pub language: Option<String>,
    pub duration: Option<f32>,
    pub words: Option<Vec<WordTimestamp>>,
    pub segments: Option<Vec<SegmentTimestamp>>,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone)]
pub struct AudioTranslationProviderResponse {
    pub id: Uuid,
    pub text: String,
    pub created: u64,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone)]
pub struct TextToSpeechProviderResponse {
    pub id: Uuid,
    pub audio_data: Vec<u8>,
    pub format: AudioOutputFormat,
    pub created: u64,
    pub raw_request: String,
    pub usage: Usage,
    pub latency: Latency,
}

// Provider traits
pub trait AudioTranscriptionProvider {
    fn transcribe(
        &self,
        request: &AudioTranscriptionRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<AudioTranscriptionProviderResponse, Error>> + Send;
}

pub trait AudioTranslationProvider {
    fn translate(
        &self,
        request: &AudioTranslationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<AudioTranslationProviderResponse, Error>> + Send;
}

pub trait TextToSpeechProvider {
    fn generate_speech(
        &self,
        request: &TextToSpeechRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<TextToSpeechProviderResponse, Error>> + Send;
}

// Streaming support for TTS
pub trait TextToSpeechStreamProvider {
    fn generate_speech_stream(
        &self,
        request: &TextToSpeechRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<(AudioStream, AudioOutputFormat), Error>> + Send;
}

pub type AudioStream = Pin<Box<dyn Stream<Item = Result<Vec<u8>, Error>> + Send>>;

impl AudioTranscriptionResponseFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            AudioTranscriptionResponseFormat::Json => "json",
            AudioTranscriptionResponseFormat::Text => "text",
            AudioTranscriptionResponseFormat::Srt => "srt",
            AudioTranscriptionResponseFormat::VerboseJson => "verbose_json",
            AudioTranscriptionResponseFormat::Vtt => "vtt",
        }
    }
}

impl AudioOutputFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            AudioOutputFormat::Mp3 => "mp3",
            AudioOutputFormat::Opus => "opus",
            AudioOutputFormat::Aac => "aac",
            AudioOutputFormat::Flac => "flac",
            AudioOutputFormat::Wav => "wav",
            AudioOutputFormat::Pcm => "pcm",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audio_transcription_response_format_as_str() {
        assert_eq!(AudioTranscriptionResponseFormat::Json.as_str(), "json");
        assert_eq!(AudioTranscriptionResponseFormat::Text.as_str(), "text");
        assert_eq!(AudioTranscriptionResponseFormat::Srt.as_str(), "srt");
        assert_eq!(
            AudioTranscriptionResponseFormat::VerboseJson.as_str(),
            "verbose_json"
        );
        assert_eq!(AudioTranscriptionResponseFormat::Vtt.as_str(), "vtt");
    }

    #[test]
    fn test_audio_voice_serialization() {
        let voice = AudioVoice::Alloy;
        let serialized = serde_json::to_string(&voice).unwrap();
        assert_eq!(serialized, "\"alloy\"");

        let voice = AudioVoice::Nova;
        let serialized = serde_json::to_string(&voice).unwrap();
        assert_eq!(serialized, "\"nova\"");
    }

    #[test]
    fn test_audio_output_format_serialization() {
        let format = AudioOutputFormat::Mp3;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"mp3\"");

        let format = AudioOutputFormat::Wav;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"wav\"");
    }

    #[test]
    fn test_chunking_strategy_serialization() {
        let strategy = ChunkingStrategy::Auto;
        let serialized = serde_json::to_string(&strategy).unwrap();
        assert_eq!(serialized, "{\"type\":\"auto\"}");

        let strategy = ChunkingStrategy::Static {
            chunk_size: Some(1024),
            overlap_size: Some(256),
        };
        let serialized = serde_json::to_string(&strategy).unwrap();
        let deserialized: ChunkingStrategy = serde_json::from_str(&serialized).unwrap();
        match deserialized {
            ChunkingStrategy::Static {
                chunk_size,
                overlap_size,
            } => {
                assert_eq!(chunk_size, Some(1024));
                assert_eq!(overlap_size, Some(256));
            }
            _ => panic!("Expected Static variant"),
        }
    }

    #[test]
    fn test_timestamp_granularity_serialization() {
        let granularity = TimestampGranularity::Word;
        let serialized = serde_json::to_string(&granularity).unwrap();
        assert_eq!(serialized, "\"word\"");

        let granularity = TimestampGranularity::Segment;
        let serialized = serde_json::to_string(&granularity).unwrap();
        assert_eq!(serialized, "\"segment\"");
    }

    #[test]
    fn test_audio_transcription_request_creation() {
        let request = AudioTranscriptionRequest {
            id: Uuid::now_v7(),
            file: vec![1, 2, 3, 4],
            filename: "test.mp3".to_string(),
            model: Arc::from("whisper-1"),
            language: Some("en".to_string()),
            prompt: None,
            response_format: Some(AudioTranscriptionResponseFormat::Json),
            temperature: None,
            timestamp_granularities: None,
            chunking_strategy: None,
            include: None,
            stream: None,
        };

        assert_eq!(request.file, vec![1, 2, 3, 4]);
        assert_eq!(request.filename, "test.mp3");
        assert_eq!(request.model.as_ref(), "whisper-1");
        assert_eq!(request.language, Some("en".to_string()));
    }

    #[test]
    fn test_text_to_speech_request_creation() {
        let request = TextToSpeechRequest {
            id: Uuid::now_v7(),
            input: "Hello, world!".to_string(),
            model: Arc::from("tts-1"),
            voice: AudioVoice::Alloy,
            response_format: Some(AudioOutputFormat::Mp3),
            speed: Some(1.0),
        };

        assert_eq!(request.input, "Hello, world!");
        assert_eq!(request.model.as_ref(), "tts-1");
        assert_eq!(request.voice, AudioVoice::Alloy);
        assert_eq!(request.response_format, Some(AudioOutputFormat::Mp3));
        assert_eq!(request.speed, Some(1.0));
    }
}
