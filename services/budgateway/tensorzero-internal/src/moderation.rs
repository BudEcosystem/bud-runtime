use std::future::Future;
use std::sync::Arc;

use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::inference::types::{Latency, Usage};

use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json;
use uuid::Uuid;

// Note: ModerationModelConfig and related types have been removed as moderation
// is now handled through the unified model system with endpoint capabilities

/// Represents the input for moderation requests
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ModerationInput {
    Single(String),
    Batch(Vec<String>),
}

impl ModerationInput {
    /// Get all input strings as a vector
    pub fn as_vec(&self) -> Vec<&str> {
        match self {
            ModerationInput::Single(text) => vec![text],
            ModerationInput::Batch(texts) => texts.iter().map(|s| s.as_str()).collect(),
        }
    }

    /// Get the number of inputs
    pub fn len(&self) -> usize {
        match self {
            ModerationInput::Single(_) => 1,
            ModerationInput::Batch(texts) => texts.len(),
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

/// Request structure for moderation API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModerationRequest {
    pub input: ModerationInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// Provider-specific parameters passed through from the request
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider_params: Option<serde_json::Value>,
}

/// Categories that can be flagged by the moderation API
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ModerationCategory {
    Hate,
    #[serde(rename = "hate/threatening")]
    HateThreatening,
    Harassment,
    #[serde(rename = "harassment/threatening")]
    HarassmentThreatening,
    Illicit,
    #[serde(rename = "illicit/violent")]
    IllicitViolent,
    Illegal,
    #[serde(rename = "regulated-advice")]
    RegulatedAdvice,
    SelfHarm,
    #[serde(rename = "self-harm/intent")]
    SelfHarmIntent,
    #[serde(rename = "self-harm/instructions")]
    SelfHarmInstructions,
    Sexual,
    #[serde(rename = "sexual/minors")]
    SexualMinors,
    Violence,
    #[serde(rename = "violence/graphic")]
    ViolenceGraphic,
    // AWS Comprehend Moderation
    Profanity,
    Insult,
    Toxicity,
    // AWS Comprehend Prompt Safety, Azure Prompt Safety
    Malicious,
    #[serde(rename = "pii")]
    PII,
    #[serde(rename = "secrets")]
    Secrets,
    // Azure Protect Content
    IPViolation,
    // Groundedness/Hallucination detection
    Hallucination,
}

impl ModerationCategory {
    /// Get all category names
    pub fn all() -> &'static [ModerationCategory] {
        &[
            ModerationCategory::Hate,
            ModerationCategory::HateThreatening,
            ModerationCategory::Harassment,
            ModerationCategory::HarassmentThreatening,
            ModerationCategory::Illicit,
            ModerationCategory::IllicitViolent,
            ModerationCategory::Illegal,
            ModerationCategory::RegulatedAdvice,
            ModerationCategory::SelfHarm,
            ModerationCategory::SelfHarmIntent,
            ModerationCategory::SelfHarmInstructions,
            ModerationCategory::Sexual,
            ModerationCategory::SexualMinors,
            ModerationCategory::Violence,
            ModerationCategory::ViolenceGraphic,
            ModerationCategory::Profanity,
            ModerationCategory::Insult,
            ModerationCategory::Toxicity,
            ModerationCategory::Malicious,
            ModerationCategory::PII,
            ModerationCategory::Secrets,
            ModerationCategory::IPViolation,
            ModerationCategory::Hallucination,
        ]
    }

    /// Get the string representation of the category
    pub fn as_str(&self) -> &'static str {
        match self {
            ModerationCategory::Hate => "hate",
            ModerationCategory::HateThreatening => "hate/threatening",
            ModerationCategory::Harassment => "harassment",
            ModerationCategory::HarassmentThreatening => "harassment/threatening",
            ModerationCategory::Illicit => "illicit",
            ModerationCategory::IllicitViolent => "illicit/violent",
            ModerationCategory::Illegal => "illegal",
            ModerationCategory::RegulatedAdvice => "regulated-advice",
            ModerationCategory::SelfHarm => "self-harm",
            ModerationCategory::SelfHarmIntent => "self-harm/intent",
            ModerationCategory::SelfHarmInstructions => "self-harm/instructions",
            ModerationCategory::Sexual => "sexual",
            ModerationCategory::SexualMinors => "sexual/minors",
            ModerationCategory::Violence => "violence",
            ModerationCategory::ViolenceGraphic => "violence/graphic",
            ModerationCategory::Profanity => "profanity",
            ModerationCategory::Insult => "insult",
            ModerationCategory::Toxicity => "toxicity",
            ModerationCategory::Malicious => "malicious",
            ModerationCategory::PII => "pii",
            ModerationCategory::Secrets => "secrets",
            ModerationCategory::IPViolation => "ip-violation",
            ModerationCategory::Hallucination => "hallucination",
        }
    }
}

/// Categories flagged by the moderation API
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ModerationCategories {
    pub hate: bool,
    #[serde(rename = "hate/threatening")]
    pub hate_threatening: bool,
    pub harassment: bool,
    #[serde(rename = "harassment/threatening")]
    pub harassment_threatening: bool,
    #[serde(default)]
    pub illicit: bool,
    #[serde(rename = "illicit/violent", default)]
    pub illicit_violent: bool,
    #[serde(default)]
    pub illegal: bool,
    #[serde(rename = "regulated-advice", default)]
    pub regulated_advice: bool,
    #[serde(rename = "self-harm")]
    pub self_harm: bool,
    #[serde(rename = "self-harm/intent")]
    pub self_harm_intent: bool,
    #[serde(rename = "self-harm/instructions")]
    pub self_harm_instructions: bool,
    pub sexual: bool,
    #[serde(rename = "sexual/minors")]
    pub sexual_minors: bool,
    pub violence: bool,
    #[serde(rename = "violence/graphic")]
    pub violence_graphic: bool,
    #[serde(default)]
    pub profanity: bool,
    #[serde(default)]
    pub insult: bool,
    #[serde(default)]
    pub toxicity: bool,
    #[serde(default)]
    pub malicious: bool,
    #[serde(default)]
    pub pii: bool,
    #[serde(default)]
    pub secrets: bool,
    #[serde(rename = "ip-violation", default)]
    pub ip_violation: bool,
    #[serde(default)]
    pub hallucination: bool,
}

/// Confidence scores for each moderation category
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ModerationCategoryScores {
    pub hate: f32,
    #[serde(rename = "hate/threatening")]
    pub hate_threatening: f32,
    pub harassment: f32,
    #[serde(rename = "harassment/threatening")]
    pub harassment_threatening: f32,
    #[serde(default)]
    pub illicit: f32,
    #[serde(rename = "illicit/violent", default)]
    pub illicit_violent: f32,
    #[serde(default)]
    pub illegal: f32,
    #[serde(rename = "regulated-advice", default)]
    pub regulated_advice: f32,
    #[serde(rename = "self-harm")]
    pub self_harm: f32,
    #[serde(rename = "self-harm/intent")]
    pub self_harm_intent: f32,
    #[serde(rename = "self-harm/instructions")]
    pub self_harm_instructions: f32,
    pub sexual: f32,
    #[serde(rename = "sexual/minors")]
    pub sexual_minors: f32,
    pub violence: f32,
    #[serde(rename = "violence/graphic")]
    pub violence_graphic: f32,
    #[serde(default)]
    pub profanity: f32,
    #[serde(default)]
    pub insult: f32,
    #[serde(default)]
    pub toxicity: f32,
    #[serde(default)]
    pub malicious: f32,
    #[serde(default)]
    pub pii: f32,
    #[serde(default)]
    pub secrets: f32,
}

impl ModerationCategoryScores {
    /// Check if any scores are non-zero (indicating this contains actual scoring data)
    pub fn has_non_zero_scores(&self) -> bool {
        self.hate > 0.0
            || self.hate_threatening > 0.0
            || self.harassment > 0.0
            || self.harassment_threatening > 0.0
            || self.illicit > 0.0
            || self.illicit_violent > 0.0
            || self.illegal > 0.0
            || self.regulated_advice > 0.0
            || self.self_harm > 0.0
            || self.self_harm_intent > 0.0
            || self.self_harm_instructions > 0.0
            || self.sexual > 0.0
            || self.sexual_minors > 0.0
            || self.violence > 0.0
            || self.violence_graphic > 0.0
            || self.profanity > 0.0
            || self.insult > 0.0
            || self.toxicity > 0.0
            || self.malicious > 0.0
            || self.pii > 0.0
            || self.secrets > 0.0
    }
}

/// Represents the input types that were applied to each moderation category
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct CategoryAppliedInputTypes {
    #[serde(default)]
    pub sexual: Vec<String>,
    #[serde(rename = "sexual/minors", default)]
    pub sexual_minors: Vec<String>,
    #[serde(default)]
    pub harassment: Vec<String>,
    #[serde(rename = "harassment/threatening", default)]
    pub harassment_threatening: Vec<String>,
    #[serde(default)]
    pub hate: Vec<String>,
    #[serde(rename = "hate/threatening", default)]
    pub hate_threatening: Vec<String>,
    #[serde(default)]
    pub illicit: Vec<String>,
    #[serde(rename = "illicit/violent", default)]
    pub illicit_violent: Vec<String>,
    #[serde(default)]
    pub illegal: Vec<String>,
    #[serde(rename = "regulated-advice", default)]
    pub regulated_advice: Vec<String>,
    #[serde(rename = "self-harm", default)]
    pub self_harm: Vec<String>,
    #[serde(rename = "self-harm/intent", default)]
    pub self_harm_intent: Vec<String>,
    #[serde(rename = "self-harm/instructions", default)]
    pub self_harm_instructions: Vec<String>,
    #[serde(default)]
    pub violence: Vec<String>,
    #[serde(rename = "violence/graphic", default)]
    pub violence_graphic: Vec<String>,
    #[serde(default)]
    pub malicious: Vec<String>,
    #[serde(default)]
    pub pii: Vec<String>,
    #[serde(default)]
    pub secrets: Vec<String>,
    #[serde(rename = "ip-violation", default)]
    pub ip_violation: Vec<String>,
    #[serde(default)]
    pub hallucination: Vec<String>,
}

/// Details about hallucination/groundedness detection
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HallucinationDetails {
    pub ungrounded_percentage: f32,
    pub ungrounded_segments: Vec<HallucinationSegment>,
    pub reasoning: Option<String>,
}

/// A segment of text that was identified as ungrounded/hallucinated
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HallucinationSegment {
    pub text: String,
    pub offset: u32,
    pub length: u32,
    pub correction: Option<String>,
}

/// Details about IP (Intellectual Property) violations
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IPViolationDetails {
    pub citations: Vec<Citation>,
}

/// Citation information for detected IP violations
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Citation {
    pub license: String,
    pub source_urls: Vec<String>,
}

/// Result for a single text input
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ModerationResult {
    pub flagged: bool,
    pub categories: ModerationCategories,
    pub category_scores: ModerationCategoryScores,
    pub category_applied_input_types: Option<CategoryAppliedInputTypes>,
    pub hallucination_details: Option<HallucinationDetails>,
    pub ip_violation_details: Option<IPViolationDetails>,
}

/// Provider-specific moderation response
#[derive(Debug, Serialize)]
pub struct ModerationProviderResponse {
    pub id: Uuid,
    pub input: ModerationInput,
    pub results: Vec<ModerationResult>,
    pub created: u64,
    pub model: String,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

/// Full moderation response
#[derive(Debug, Serialize)]
pub struct ModerationResponse {
    pub id: Uuid,
    pub input: ModerationInput,
    pub results: Vec<ModerationResult>,
    pub created: u64,
    pub model: String,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
    pub moderation_provider_name: Arc<str>,
    pub cached: bool,
}

impl ModerationResponse {
    pub fn new(
        moderation_provider_response: ModerationProviderResponse,
        moderation_provider_name: Arc<str>,
    ) -> Self {
        Self {
            id: moderation_provider_response.id,
            input: moderation_provider_response.input,
            results: moderation_provider_response.results,
            created: moderation_provider_response.created,
            model: moderation_provider_response.model,
            raw_request: moderation_provider_response.raw_request,
            raw_response: moderation_provider_response.raw_response,
            usage: moderation_provider_response.usage,
            latency: moderation_provider_response.latency,
            moderation_provider_name,
            cached: false,
        }
    }
}

/// Trait for providers that support moderation
pub trait ModerationProvider {
    fn moderate(
        &self,
        request: &ModerationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl Future<Output = Result<ModerationProviderResponse, Error>> + Send;
}

// Note: ModerationProviderConfig has been removed as moderation
// is now handled through the unified model system

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_moderation_input_single() {
        let input = ModerationInput::Single("test text".to_string());
        assert_eq!(input.len(), 1);
        assert!(!input.is_empty());
        assert_eq!(input.as_vec(), vec!["test text"]);
    }

    #[test]
    fn test_moderation_input_batch() {
        let input = ModerationInput::Batch(vec![
            "text1".to_string(),
            "text2".to_string(),
            "text3".to_string(),
        ]);
        assert_eq!(input.len(), 3);
        assert!(!input.is_empty());
        assert_eq!(input.as_vec(), vec!["text1", "text2", "text3"]);
    }

    #[test]
    fn test_moderation_input_empty_batch() {
        let input = ModerationInput::Batch(vec![]);
        assert_eq!(input.len(), 0);
        assert!(input.is_empty());
        assert!(input.as_vec().is_empty());
    }

    #[test]
    fn test_moderation_category_str_conversion() {
        assert_eq!(ModerationCategory::Hate.as_str(), "hate");
        assert_eq!(
            ModerationCategory::HateThreatening.as_str(),
            "hate/threatening"
        );
        assert_eq!(ModerationCategory::Harassment.as_str(), "harassment");
        assert_eq!(
            ModerationCategory::HarassmentThreatening.as_str(),
            "harassment/threatening"
        );
        assert_eq!(ModerationCategory::Illicit.as_str(), "illicit");
        assert_eq!(
            ModerationCategory::IllicitViolent.as_str(),
            "illicit/violent"
        );
        assert_eq!(ModerationCategory::Illegal.as_str(), "illegal");
        assert_eq!(
            ModerationCategory::RegulatedAdvice.as_str(),
            "regulated-advice"
        );
        assert_eq!(ModerationCategory::SelfHarm.as_str(), "self-harm");
        assert_eq!(
            ModerationCategory::SelfHarmIntent.as_str(),
            "self-harm/intent"
        );
        assert_eq!(
            ModerationCategory::SelfHarmInstructions.as_str(),
            "self-harm/instructions"
        );
        assert_eq!(ModerationCategory::Sexual.as_str(), "sexual");
        assert_eq!(ModerationCategory::SexualMinors.as_str(), "sexual/minors");
        assert_eq!(ModerationCategory::Violence.as_str(), "violence");
        assert_eq!(
            ModerationCategory::ViolenceGraphic.as_str(),
            "violence/graphic"
        );
        assert_eq!(ModerationCategory::Profanity.as_str(), "profanity");
        assert_eq!(ModerationCategory::Insult.as_str(), "insult");
        assert_eq!(ModerationCategory::Toxicity.as_str(), "toxicity");
        assert_eq!(ModerationCategory::Malicious.as_str(), "malicious");
        assert_eq!(ModerationCategory::PII.as_str(), "pii");
        assert_eq!(ModerationCategory::Secrets.as_str(), "secrets");
        assert_eq!(ModerationCategory::IPViolation.as_str(), "ip-violation");
        assert_eq!(ModerationCategory::Hallucination.as_str(), "hallucination");
    }

    #[test]
    fn test_moderation_category_all() {
        let all_categories = ModerationCategory::all();
        assert_eq!(all_categories.len(), 23);
        assert!(all_categories.contains(&ModerationCategory::Hate));
        assert!(all_categories.contains(&ModerationCategory::HateThreatening));
        assert!(all_categories.contains(&ModerationCategory::Harassment));
        assert!(all_categories.contains(&ModerationCategory::HarassmentThreatening));
        assert!(all_categories.contains(&ModerationCategory::Illicit));
        assert!(all_categories.contains(&ModerationCategory::IllicitViolent));
        assert!(all_categories.contains(&ModerationCategory::Illegal));
        assert!(all_categories.contains(&ModerationCategory::RegulatedAdvice));
        assert!(all_categories.contains(&ModerationCategory::SelfHarm));
        assert!(all_categories.contains(&ModerationCategory::SelfHarmIntent));
        assert!(all_categories.contains(&ModerationCategory::SelfHarmInstructions));
        assert!(all_categories.contains(&ModerationCategory::Sexual));
        assert!(all_categories.contains(&ModerationCategory::SexualMinors));
        assert!(all_categories.contains(&ModerationCategory::Violence));
        assert!(all_categories.contains(&ModerationCategory::ViolenceGraphic));
        assert!(all_categories.contains(&ModerationCategory::Profanity));
        assert!(all_categories.contains(&ModerationCategory::Insult));
        assert!(all_categories.contains(&ModerationCategory::Toxicity));
        assert!(all_categories.contains(&ModerationCategory::Malicious));
        assert!(all_categories.contains(&ModerationCategory::PII));
        assert!(all_categories.contains(&ModerationCategory::Secrets));
        assert!(all_categories.contains(&ModerationCategory::IPViolation));
        assert!(all_categories.contains(&ModerationCategory::Hallucination));
    }

    #[test]
    fn test_moderation_categories_default() {
        let categories = ModerationCategories::default();
        assert!(!categories.hate);
        assert!(!categories.hate_threatening);
        assert!(!categories.harassment);
        assert!(!categories.harassment_threatening);
        assert!(!categories.illicit);
        assert!(!categories.illicit_violent);
        assert!(!categories.self_harm);
        assert!(!categories.self_harm_intent);
        assert!(!categories.self_harm_instructions);
        assert!(!categories.sexual);
        assert!(!categories.sexual_minors);
        assert!(!categories.violence);
        assert!(!categories.violence_graphic);
        assert!(!categories.profanity);
        assert!(!categories.insult);
        assert!(!categories.toxicity);
        assert!(!categories.malicious);
        assert!(!categories.pii);
        assert!(!categories.secrets);
        assert!(!categories.ip_violation);
        assert!(!categories.hallucination);
    }

    #[test]
    fn test_moderation_category_scores_default() {
        let scores = ModerationCategoryScores::default();
        assert_eq!(scores.hate, 0.0);
        assert_eq!(scores.hate_threatening, 0.0);
        assert_eq!(scores.harassment, 0.0);
        assert_eq!(scores.harassment_threatening, 0.0);
        assert_eq!(scores.illicit, 0.0);
        assert_eq!(scores.illicit_violent, 0.0);
        assert_eq!(scores.self_harm, 0.0);
        assert_eq!(scores.self_harm_intent, 0.0);
        assert_eq!(scores.self_harm_instructions, 0.0);
        assert_eq!(scores.sexual, 0.0);
        assert_eq!(scores.sexual_minors, 0.0);
        assert_eq!(scores.violence, 0.0);
        assert_eq!(scores.violence_graphic, 0.0);
        assert_eq!(scores.profanity, 0.0);
        assert_eq!(scores.insult, 0.0);
        assert_eq!(scores.toxicity, 0.0);
        assert_eq!(scores.malicious, 0.0);
        assert_eq!(scores.pii, 0.0);
        assert_eq!(scores.secrets, 0.0);
    }

    // Tests for ModerationModelConfig have been removed as moderation
    // is now handled through the unified model system
}
