use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Represents the different endpoint capabilities a model can support
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EndpointCapability {
    Chat,
    Embedding,
    Moderation,
    AudioTranscription,
    AudioTranslation,
    TextToSpeech,
    RealtimeSession,
    RealtimeTranscription,
    Responses,
    Batch,
    ImageGeneration,
    ImageEdit,
    ImageVariation,
    Document,
    Completions,
    Classify,
    // Future capabilities can be added here:
    // FineTuning,
}

impl EndpointCapability {
    /// Returns the human-readable name for error messages
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Chat => "chat",
            Self::Embedding => "embedding",
            Self::Moderation => "moderation",
            Self::AudioTranscription => "audio_transcription",
            Self::AudioTranslation => "audio_translation",
            Self::TextToSpeech => "text_to_speech",
            Self::RealtimeSession => "realtime_session",
            Self::RealtimeTranscription => "realtime_transcription",
            Self::Responses => "responses",
            Self::Batch => "batch",
            Self::ImageGeneration => "image_generation",
            Self::ImageEdit => "image_edit",
            Self::ImageVariation => "image_variation",
            Self::Document => "document",
            Self::Completions => "completions",
            Self::Classify => "classify",
        }
    }
}

/// Default capabilities if none specified (backward compatibility)
pub fn default_capabilities() -> HashSet<EndpointCapability> {
    let mut capabilities = HashSet::new();
    capabilities.insert(EndpointCapability::Chat);
    capabilities
}
