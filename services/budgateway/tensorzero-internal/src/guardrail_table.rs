use crate::error::Error;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Represents a guardrail configuration that can include multiple providers
/// and probes/rules for comprehensive content moderation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuardrailConfig {
    /// Unique identifier for the guardrail configuration
    pub id: String,

    /// Human-readable name for the guardrail
    pub name: String,

    /// List of providers to execute for this guardrail
    /// Each provider will be executed and results merged
    pub providers: Vec<GuardrailProvider>,

    /// Execution mode: parallel or sequential
    #[serde(default = "default_execution_mode")]
    pub execution_mode: ExecutionMode,

    /// How to handle provider failures
    #[serde(default = "default_failure_mode")]
    pub failure_mode: FailureMode,

    pub severity_threshold: f64,
    pub guard_types: Vec<GuardType>,
}

/// Execution mode for multiple providers
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionMode {
    /// Execute all providers in parallel
    Parallel,
    /// Execute providers sequentially, stopping on first failure
    Sequential,
}

/// How to handle provider failures
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FailureMode {
    /// If any provider fails, the entire guardrail fails
    FailFast,
    /// Continue even if some providers fail
    BestEffort,
}

fn default_execution_mode() -> ExecutionMode {
    ExecutionMode::Parallel
}

fn default_failure_mode() -> FailureMode {
    FailureMode::BestEffort
}

/// Configuration for a single provider within a guardrail
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuardrailProvider {
    /// Provider type (e.g., "bud_sentinel", "azure_content_safety", "openai")
    pub provider_type: String,

    /// Enabled probes/features for this provider
    pub enabled_probes: Vec<String>,

    /// Enabled rules for each probe (if not specified, all rules are enabled)
    #[serde(default)]
    pub enabled_rules: HashMap<String, Vec<String>>,

    /// Provider-specific configuration
    #[serde(default)]
    pub provider_config: serde_json::Value,
}

/// Probe configuration - represents a category of checks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProbeConfig {
    pub id: String,
    pub rules: Vec<RuleConfig>,
}

/// Rule configuration - represents a specific check within a probe
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleConfig {
    pub id: String,
    pub modalities: Vec<String>,
    pub guard_types: Vec<GuardType>,
}

/// Where to apply the guard
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum GuardType {
    Input,
    Output,
}

impl GuardType {
    /// Convert to u8 for database storage
    pub fn to_db_value(self) -> u8 {
        match self {
            GuardType::Input => 1,
            GuardType::Output => 2,
        }
    }
}

/// Table of guardrail configurations indexed by ID
pub type GuardrailTable = HashMap<Arc<str>, Arc<GuardrailConfig>>;

/// Result from a guardrail execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuardrailResult {
    /// ID of the guardrail that was executed
    pub guardrail_id: String,

    /// Overall flagged status (true if any provider flagged content)
    pub flagged: bool,

    /// Results from each provider
    pub provider_results: Vec<ProviderGuardrailResult>,

    /// Merged categories and scores
    pub merged_categories: crate::moderation::ModerationCategories,
    pub merged_scores: crate::moderation::ModerationCategoryScores,
    pub merged_category_applied_input_types: Option<crate::moderation::CategoryAppliedInputTypes>,
    #[serde(default)]
    pub merged_other_categories: HashMap<String, f32>,

    /// Additional details from providers
    pub hallucination_details: Option<crate::moderation::HallucinationDetails>,
    pub ip_violation_details: Option<crate::moderation::IPViolationDetails>,
}

/// Result from a single provider within a guardrail
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderGuardrailResult {
    /// Provider type
    pub provider_type: String,

    /// Whether this provider flagged the content
    pub flagged: bool,

    /// Probes that were executed
    pub executed_probes: Vec<String>,

    /// Rules that were enabled for this probe (probe_id -> rule_ids)
    /// For OpenAI moderation, these would be the category filters like ["harassment", "hate"]
    pub enabled_rules: HashMap<String, Vec<String>>,

    /// Raw result from the provider
    pub raw_result: crate::moderation::ModerationResult,

    /// Any errors encountered
    pub error: Option<String>,
}

impl GuardrailConfig {
    /// Validate that all provider types are supported
    pub fn validate(&self) -> Result<(), crate::error::Error> {
        const SUPPORTED_PROVIDERS: &[&str] = &["azure_content_safety", "openai", "bud_sentinel"];

        for provider in &self.providers {
            if !SUPPORTED_PROVIDERS.contains(&provider.provider_type.as_str()) {
                // Log warning instead of returning error for unknown providers
                tracing::warn!(
                    "Unsupported provider type '{}' in guardrail '{}' - this provider will be skipped during execution",
                    provider.provider_type,
                    self.id
                );
                continue; // Skip validation for unsupported providers
            }

            // Validate that enabled probes are not empty
            if provider.enabled_probes.is_empty() {
                return Err(crate::error::Error::new(
                    crate::error::ErrorDetails::Config {
                        message: format!(
                            "Provider '{}' in guardrail '{}' has no enabled probes",
                            provider.provider_type, self.id
                        ),
                    },
                ));
            }
        }
        Ok(())
    }
}

/// Helper function to merge two string vectors keeping unique values
fn merge_string_vec(target: &mut Vec<String>, source: Vec<String>) {
    for item in source {
        if !target.contains(&item) {
            target.push(item);
        }
    }
}

/// Merge multiple moderation results into a single result
pub fn merge_moderation_results(
    results: Vec<crate::moderation::ModerationResult>,
) -> (
    crate::moderation::ModerationCategories,
    crate::moderation::ModerationCategoryScores,
    Option<crate::moderation::CategoryAppliedInputTypes>,
    HashMap<String, f32>,
) {
    use crate::moderation::{
        CategoryAppliedInputTypes, ModerationCategories, ModerationCategoryScores,
    };

    let mut merged_categories = ModerationCategories::default();
    let mut merged_scores = ModerationCategoryScores::default();
    let mut merged_applied_input_types: Option<CategoryAppliedInputTypes> = None;
    let mut merged_other_categories = HashMap::new();

    // For categories: OR operation (flagged if any provider flags it)
    // For scores: MAX operation (highest score wins)
    // For applied input types: merge all unique values
    for result in results {
        merged_categories.hate |= result.categories.hate;
        merged_categories.hate_threatening |= result.categories.hate_threatening;
        merged_categories.harassment |= result.categories.harassment;
        merged_categories.harassment_threatening |= result.categories.harassment_threatening;
        merged_categories.illicit |= result.categories.illicit;
        merged_categories.illicit_violent |= result.categories.illicit_violent;
        merged_categories.self_harm |= result.categories.self_harm;
        merged_categories.self_harm_intent |= result.categories.self_harm_intent;
        merged_categories.self_harm_instructions |= result.categories.self_harm_instructions;
        merged_categories.sexual |= result.categories.sexual;
        merged_categories.sexual_minors |= result.categories.sexual_minors;
        merged_categories.violence |= result.categories.violence;
        merged_categories.violence_graphic |= result.categories.violence_graphic;
        merged_categories.profanity |= result.categories.profanity;
        merged_categories.insult |= result.categories.insult;
        merged_categories.toxicity |= result.categories.toxicity;
        merged_categories.malicious |= result.categories.malicious;
        merged_categories.pii |= result.categories.pii;
        merged_categories.secrets |= result.categories.secrets;
        merged_categories.ip_violation |= result.categories.ip_violation;
        merged_categories.hallucination |= result.categories.hallucination;

        merged_scores.hate = merged_scores.hate.max(result.category_scores.hate);
        merged_scores.hate_threatening = merged_scores
            .hate_threatening
            .max(result.category_scores.hate_threatening);
        merged_scores.harassment = merged_scores
            .harassment
            .max(result.category_scores.harassment);
        merged_scores.harassment_threatening = merged_scores
            .harassment_threatening
            .max(result.category_scores.harassment_threatening);
        merged_scores.illicit = merged_scores.illicit.max(result.category_scores.illicit);
        merged_scores.illicit_violent = merged_scores
            .illicit_violent
            .max(result.category_scores.illicit_violent);
        merged_scores.self_harm = merged_scores
            .self_harm
            .max(result.category_scores.self_harm);
        merged_scores.self_harm_intent = merged_scores
            .self_harm_intent
            .max(result.category_scores.self_harm_intent);
        merged_scores.self_harm_instructions = merged_scores
            .self_harm_instructions
            .max(result.category_scores.self_harm_instructions);
        merged_scores.sexual = merged_scores.sexual.max(result.category_scores.sexual);
        merged_scores.sexual_minors = merged_scores
            .sexual_minors
            .max(result.category_scores.sexual_minors);
        merged_scores.violence = merged_scores.violence.max(result.category_scores.violence);
        merged_scores.violence_graphic = merged_scores
            .violence_graphic
            .max(result.category_scores.violence_graphic);
        merged_scores.profanity = merged_scores
            .profanity
            .max(result.category_scores.profanity);
        merged_scores.insult = merged_scores.insult.max(result.category_scores.insult);
        merged_scores.toxicity = merged_scores.toxicity.max(result.category_scores.toxicity);
        merged_scores.malicious = merged_scores
            .malicious
            .max(result.category_scores.malicious);
        merged_scores.pii = merged_scores.pii.max(result.category_scores.pii);
        merged_scores.secrets = merged_scores.secrets.max(result.category_scores.secrets);
        merged_scores.other = merged_scores.other.max(result.category_scores.other);

        merged_categories.other |= result.categories.other;

        for (key, score) in &result.other_categories {
            let entry = merged_other_categories.entry(key.clone()).or_insert(0.0);
            if *entry < *score {
                *entry = *score;
            }
        }

        // Merge category applied input types
        if let Some(applied_types) = result.category_applied_input_types {
            let merged_types =
                merged_applied_input_types.get_or_insert_with(CategoryAppliedInputTypes::default);

            // Merge all unique values for each category
            merge_string_vec(&mut merged_types.hate, applied_types.hate);
            merge_string_vec(
                &mut merged_types.hate_threatening,
                applied_types.hate_threatening,
            );
            merge_string_vec(&mut merged_types.harassment, applied_types.harassment);
            merge_string_vec(
                &mut merged_types.harassment_threatening,
                applied_types.harassment_threatening,
            );
            merge_string_vec(&mut merged_types.illicit, applied_types.illicit);
            merge_string_vec(
                &mut merged_types.illicit_violent,
                applied_types.illicit_violent,
            );
            merge_string_vec(&mut merged_types.self_harm, applied_types.self_harm);
            merge_string_vec(
                &mut merged_types.self_harm_intent,
                applied_types.self_harm_intent,
            );
            merge_string_vec(
                &mut merged_types.self_harm_instructions,
                applied_types.self_harm_instructions,
            );
            merge_string_vec(&mut merged_types.sexual, applied_types.sexual);
            merge_string_vec(&mut merged_types.sexual_minors, applied_types.sexual_minors);
            merge_string_vec(&mut merged_types.violence, applied_types.violence);
            merge_string_vec(
                &mut merged_types.violence_graphic,
                applied_types.violence_graphic,
            );
            merge_string_vec(&mut merged_types.malicious, applied_types.malicious);
            merge_string_vec(&mut merged_types.pii, applied_types.pii);
            merge_string_vec(&mut merged_types.secrets, applied_types.secrets);
            merge_string_vec(&mut merged_types.ip_violation, applied_types.ip_violation);
            merge_string_vec(&mut merged_types.hallucination, applied_types.hallucination);
        }
    }

    (
        merged_categories,
        merged_scores,
        merged_applied_input_types,
        merged_other_categories,
    )
}

#[cfg(test)]
mod tests {
    use super::merge_moderation_results;
    use crate::moderation::{ModerationCategories, ModerationCategoryScores, ModerationResult};
    use std::collections::HashMap;

    #[test]
    fn merge_moderation_results_preserves_other_categories() {
        let mut unknown_a = HashMap::new();
        unknown_a.insert("high_risk_spam".to_string(), 1.0);
        let mut unknown_b = HashMap::new();
        unknown_b.insert("high_risk_spam".to_string(), 0.4);
        unknown_b.insert("new_category".to_string(), 0.7);

        let mut first_categories = ModerationCategories::default();
        first_categories.other = true;
        let mut first_scores = ModerationCategoryScores::default();
        first_scores.other = 1.0;
        let first = ModerationResult {
            flagged: false,
            categories: first_categories,
            category_scores: first_scores,
            category_applied_input_types: None,
            hallucination_details: None,
            ip_violation_details: None,
            other_categories: unknown_a,
        };

        let mut second_categories = ModerationCategories::default();
        second_categories.other = true;
        let mut second_scores = ModerationCategoryScores::default();
        second_scores.other = 0.7;
        let second = ModerationResult {
            flagged: false,
            categories: second_categories,
            category_scores: second_scores,
            category_applied_input_types: None,
            hallucination_details: None,
            ip_violation_details: None,
            other_categories: unknown_b,
        };

        let (_categories, scores, _applied, other_categories) =
            merge_moderation_results(vec![first, second]);

        assert_eq!(other_categories.get("high_risk_spam"), Some(&1.0));
        assert_eq!(other_categories.get("new_category"), Some(&0.7));
        assert!((scores.other - 1.0).abs() < 1e-6);
    }
}

/// Redis format for guardrail configuration (matches model table structure)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UninitializedGuardrailConfig {
    /// Human-readable name for the guardrail
    pub name: String,

    /// Providers as an object (like model table)
    pub providers: HashMap<String, UninitializedGuardrailProvider>,

    /// Severity threshold for triggering
    pub severity_threshold: f64,

    /// Where to apply the guard
    pub guard_types: Vec<GuardType>,

    /// Execution mode: parallel or sequential
    #[serde(default = "default_execution_mode")]
    pub execution_mode: ExecutionMode,

    /// How to handle provider failures
    #[serde(default = "default_failure_mode")]
    pub failure_mode: FailureMode,

    /// Optional API key to extract (will be stored separately in credential store)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
}

/// Redis format for a provider within a guardrail
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UninitializedGuardrailProvider {
    /// Provider type (e.g., "openai", "azure_content_safety")
    #[serde(rename = "type")]
    pub provider_type: String,

    /// Probe configuration (maps probe names to enabled rules)
    #[serde(default)]
    pub probe_config: HashMap<String, Vec<String>>,

    /// API key location
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key_location: Option<String>,

    /// Additional provider-specific configuration
    #[serde(flatten)]
    pub extra_config: serde_json::Value,
}

impl UninitializedGuardrailConfig {
    /// Convert from Redis format to internal format
    pub fn load(self, id: &str) -> Result<GuardrailConfig, Error> {
        let providers = self
            .providers
            .into_iter()
            .map(|(_provider_name, redis_provider)| {
                // Extract enabled probes and rules from probe_config
                let mut enabled_probes = Vec::new();
                let mut enabled_rules = HashMap::new();

                for (probe_name, rules) in redis_provider.probe_config {
                    enabled_probes.push(probe_name.clone());
                    if !rules.is_empty() {
                        enabled_rules.insert(probe_name, rules);
                    }
                }

                // Build provider config including api_key_location and extra fields
                let mut provider_config = redis_provider.extra_config;
                if let serde_json::Value::Object(ref mut obj) = provider_config {
                    if let Some(api_key_location) = redis_provider.api_key_location {
                        obj.insert(
                            "api_key_location".to_string(),
                            serde_json::Value::String(api_key_location),
                        );
                    }
                }

                GuardrailProvider {
                    provider_type: redis_provider.provider_type,
                    enabled_probes,
                    enabled_rules,
                    provider_config,
                }
            })
            .collect();

        let config = GuardrailConfig {
            id: id.to_string(),
            name: self.name,
            providers,
            execution_mode: self.execution_mode,
            failure_mode: self.failure_mode,
            severity_threshold: self.severity_threshold,
            guard_types: self.guard_types,
        };

        // Validate the configuration
        config.validate()?;

        Ok(config)
    }
}
