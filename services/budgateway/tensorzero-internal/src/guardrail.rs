use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use futures::stream::{FuturesUnordered, StreamExt};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::endpoints::inference::InferenceClients;
use crate::error::{Error, ErrorDetails};
use crate::guardrail_table::{
    merge_moderation_results, ExecutionMode, FailureMode, GuardType, GuardrailConfig,
    GuardrailResult, GuardrailTable, ProviderGuardrailResult,
};
use crate::inference::providers::bud_sentinel::{
    generated::{CustomRule as BudSentinelCustomRule, Profile as BudSentinelProfile},
    BudSentinelProvider,
};
use crate::model::CredentialLocation;
use crate::moderation::{ModerationInput, ModerationProvider, ModerationRequest, ModerationResult};
use tonic::Code;

/// Execute a guardrail configuration against input text
/// This version creates separate provider instances for each probe
pub async fn execute_guardrail<'a>(
    guardrail_config: &GuardrailConfig,
    input: ModerationInput,
    guard_type: GuardType,
    clients: &InferenceClients<'a>,
    provider_params: Option<serde_json::Value>,
    skip_guard_type_validation: bool,
) -> Result<GuardrailResult, Error> {
    // Validate the guardrail configuration
    guardrail_config.validate()?;

    // Check if this guardrail supports the requested guard type
    if !skip_guard_type_validation && !guardrail_config.guard_types.contains(&guard_type) {
        return Ok(GuardrailResult {
            guardrail_id: guardrail_config.id.clone(),
            flagged: false,
            provider_results: vec![],
            merged_categories: crate::moderation::ModerationCategories::default(),
            merged_scores: crate::moderation::ModerationCategoryScores::default(),
            merged_category_applied_input_types: None,
            merged_unknown_categories: Default::default(),
            merged_other_score: 0.0,
            hallucination_details: None,
            ip_violation_details: None,
        });
    }

    // Create probe execution tasks
    let probe_tasks = create_probe_tasks(guardrail_config, &input);

    let provider_results = match guardrail_config.execution_mode {
        ExecutionMode::Parallel => {
            execute_parallel(
                probe_tasks,
                guardrail_config,
                input.clone(),
                clients,
                provider_params.clone(),
            )
            .await?
        }
        ExecutionMode::Sequential => {
            execute_sequential(
                probe_tasks,
                guardrail_config,
                input.clone(),
                clients,
                provider_params.clone(),
            )
            .await?
        }
    };

    // Merge all results
    let moderation_results: Vec<ModerationResult> = provider_results
        .iter()
        .filter_map(|pr| {
            if pr.error.is_none() {
                Some(pr.raw_result.clone())
            } else {
                None
            }
        })
        .collect();

    let (
        merged_categories,
        merged_scores,
        merged_category_applied_input_types,
        merged_unknown_categories,
        merged_other_score,
    ) = merge_moderation_results(moderation_results);

    // Extract special details from provider results
    let mut hallucination_details = None;
    let mut ip_violation_details = None;

    for pr in &provider_results {
        if pr.error.is_none() {
            if hallucination_details.is_none() && pr.raw_result.hallucination_details.is_some() {
                hallucination_details = pr.raw_result.hallucination_details.clone();
            }
            if ip_violation_details.is_none() && pr.raw_result.ip_violation_details.is_some() {
                ip_violation_details = pr.raw_result.ip_violation_details.clone();
            }
        }
    }

    // Determine overall flagged status
    // Each provider determines its own flagged status based on its internal logic
    // The guardrail is flagged if any provider flagged the content
    let flagged = provider_results
        .iter()
        .any(|pr| pr.error.is_none() && pr.flagged);

    Ok(GuardrailResult {
        guardrail_id: guardrail_config.id.clone(),
        flagged,
        provider_results,
        merged_categories,
        merged_scores,
        merged_category_applied_input_types,
        merged_unknown_categories,
        merged_other_score,
        hallucination_details,
        ip_violation_details,
    })
}

/// Represents a single probe execution task
struct ProbeTask {
    provider_type: String,
    guardrail_id: String,
    guardrail_severity: f64,
    provider_enabled_probes: Vec<String>,
    provider_enabled_rules: HashMap<String, Vec<String>>,
    probe_id: String,
    rules: Vec<String>,
    provider_config: serde_json::Value,
}

/// Create probe execution tasks from guardrail configuration
fn create_probe_tasks(
    guardrail_config: &GuardrailConfig,
    _input: &ModerationInput,
) -> Vec<ProbeTask> {
    let mut tasks = Vec::new();

    for provider_config in &guardrail_config.providers {
        if provider_config.provider_type == "bud_sentinel" {
            tasks.push(ProbeTask {
                provider_type: provider_config.provider_type.clone(),
                guardrail_id: guardrail_config.id.clone(),
                guardrail_severity: guardrail_config.severity_threshold,
                provider_enabled_probes: provider_config.enabled_probes.clone(),
                provider_enabled_rules: provider_config.enabled_rules.clone(),
                probe_id: provider_config
                    .enabled_probes
                    .first()
                    .cloned()
                    .unwrap_or_else(|| "bud_sentinel".to_string()),
                rules: provider_config
                    .enabled_rules
                    .values()
                    .flat_map(|r| r.clone())
                    .collect(),
                provider_config: provider_config.provider_config.clone(),
            });
            continue;
        }

        for probe_id in &provider_config.enabled_probes {
            let rules = provider_config
                .enabled_rules
                .get(probe_id)
                .cloned()
                .unwrap_or_default();

            // Special handling for protected-material-detection
            if probe_id == "protected-material-detection"
                && provider_config.provider_type == "azure_content_safety"
            {
                // Create separate probe tasks for each rule type
                for rule in &rules {
                    let specific_probe_id = match rule.as_str() {
                        "text" => "protected-material-detection-text".to_string(),
                        "code-preview" => "protected-material-detection-code".to_string(),
                        _ => continue, // Skip unknown rules
                    };

                    tasks.push(ProbeTask {
                        provider_type: provider_config.provider_type.clone(),
                        guardrail_id: guardrail_config.id.clone(),
                        guardrail_severity: guardrail_config.severity_threshold,
                        provider_enabled_probes: provider_config.enabled_probes.clone(),
                        provider_enabled_rules: provider_config.enabled_rules.clone(),
                        probe_id: specific_probe_id,
                        rules: vec![rule.clone()], // Single rule for this specific probe
                        provider_config: provider_config.provider_config.clone(),
                    });
                }
            } else {
                // Normal probe task creation
                tasks.push(ProbeTask {
                    provider_type: provider_config.provider_type.clone(),
                    guardrail_id: guardrail_config.id.clone(),
                    guardrail_severity: guardrail_config.severity_threshold,
                    provider_enabled_probes: provider_config.enabled_probes.clone(),
                    provider_enabled_rules: provider_config.enabled_rules.clone(),
                    probe_id: probe_id.clone(),
                    rules,
                    provider_config: provider_config.provider_config.clone(),
                });
            }
        }
    }

    tasks
}

/// Execute probe tasks in parallel
async fn execute_parallel<'a>(
    probe_tasks: Vec<ProbeTask>,
    guardrail_config: &GuardrailConfig,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    provider_params: Option<serde_json::Value>,
) -> Result<Vec<ProviderGuardrailResult>, Error> {
    let mut futures = FuturesUnordered::new();

    for task in probe_tasks {
        let future = execute_single_probe(task, input.clone(), clients, provider_params.clone());

        futures.push(future);
    }

    let mut results = Vec::new();
    while let Some(result) = futures.next().await {
        match (result, guardrail_config.failure_mode) {
            (Ok(provider_result), _) => results.push(provider_result),
            (Err(e), FailureMode::FailFast) => return Err(e),
            (Err(e), FailureMode::BestEffort) => {
                tracing::warn!("Probe failed in best-effort mode: {e}");
                // Continue with other probes
            }
        }
    }

    Ok(results)
}

/// Execute probe tasks sequentially
async fn execute_sequential<'a>(
    probe_tasks: Vec<ProbeTask>,
    guardrail_config: &GuardrailConfig,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    provider_params: Option<serde_json::Value>,
) -> Result<Vec<ProviderGuardrailResult>, Error> {
    let mut results = Vec::new();

    for task in probe_tasks {
        match execute_single_probe(task, input.clone(), clients, provider_params.clone()).await {
            Ok(provider_result) => {
                let should_stop = provider_result.flagged
                    && guardrail_config.execution_mode == ExecutionMode::Sequential;
                results.push(provider_result);

                if should_stop {
                    break; // Stop on first flagged result in sequential mode
                }
            }
            Err(e) => {
                if guardrail_config.failure_mode == FailureMode::FailFast {
                    return Err(e);
                } else {
                    tracing::warn!("Probe failed in best-effort mode: {e}");
                    // Continue with next probe
                }
            }
        }
    }

    Ok(results)
}

/// Execute a single probe
async fn execute_single_probe<'a>(
    task: ProbeTask,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    request_provider_params: Option<serde_json::Value>,
) -> Result<ProviderGuardrailResult, Error> {
    match task.provider_type.as_str() {
        "azure_content_safety" => {
            execute_azure_content_safety_probe(
                task.probe_id.clone(),
                task.rules,
                task.provider_config,
                task.guardrail_severity,
                input,
                clients,
                request_provider_params.clone(),
            )
            .await
        }
        "openai" => {
            execute_openai_probe(
                task.probe_id.clone(),
                task.rules,
                task.provider_config,
                task.guardrail_severity,
                input,
                clients,
                request_provider_params.clone(),
            )
            .await
        }
        "bud_sentinel" => {
            execute_bud_sentinel_probe(task, input, clients, request_provider_params.clone()).await
        }
        _ => Err(Error::new(ErrorDetails::Config {
            message: format!("Unsupported provider type: {}", task.provider_type),
        })),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builds_profile_with_custom_rules() {
        let provider_config = serde_json::json!({
            "profile_id": "test-profile",
            "strategy_id": "strategy-1",
            "description": "Test profile",
            "version": "v1",
            "metadata_json": "{\"llm\":{}}",
            "rule_overrides_json": "",
            "custom_rules": [
                {
                    "id": "custom_spam_detector",
                    "scanner": "llm",
                    "scanner_config_json": "{\"model_id\":\"foo\"}",
                    "target_labels": ["spam"],
                    "severity_threshold": 0.5,
                    "probe": "pii",
                    "name": "Spam",
                    "description": "Detect spam",
                    "post_processing_json": "[]"
                }
            ]
        });

        let profile = build_bud_sentinel_profile(
            "guardrail-1",
            0.7,
            &["pii".to_string()],
            &HashMap::new(),
            provider_config.as_object().expect("provider config object"),
        )
        .expect("profile build");

        assert_eq!(profile.custom_rules.len(), 1);
        let rule = &profile.custom_rules[0];
        assert_eq!(rule.id, "custom_spam_detector");
        assert_eq!(rule.scanner, "llm");
        assert_eq!(rule.target_labels, vec!["spam"]);
        assert_eq!(rule.probe.as_deref(), Some("pii"));
    }
}

/// Execute Azure Content Safety probe
async fn execute_azure_content_safety_probe<'a>(
    probe_id: String,
    rules: Vec<String>,
    provider_config: serde_json::Value,
    severity_threshold: f64,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    request_provider_params: Option<serde_json::Value>,
) -> Result<ProviderGuardrailResult, Error> {
    use crate::inference::providers::azure_content_safety::{
        AzureContentSafetyProvider, ProbeType,
    };
    use crate::model::CredentialLocation;

    // Map probe ID to probe type
    let probe_type = ProbeType::from_probe_id(&probe_id).ok_or_else(|| {
        Error::new(ErrorDetails::Config {
            message: format!("Unknown Azure Content Safety probe: {}", probe_id),
        })
    })?;

    // Extract Azure Content Safety configuration from provider_config
    let endpoint = provider_config
        .get("endpoint")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: "Missing 'endpoint' in Azure Content Safety provider configuration"
                    .to_string(),
            })
        })?;

    let endpoint_url = url::Url::parse(endpoint).map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Invalid Azure Content Safety endpoint URL: {}", e),
        })
    })?;

    let api_key_location = provider_config
        .get("api_key_location")
        .and_then(|v| serde_json::from_value::<CredentialLocation>(v.clone()).ok());

    // Create a new Azure Content Safety provider instance for this specific probe
    let probe_provider =
        AzureContentSafetyProvider::new(endpoint_url, api_key_location, probe_type)?;

    // Prepare provider parameters based on probe type and rules
    let provider_params =
        build_azure_probe_params(&probe_id, &rules, &provider_config, request_provider_params);

    let request = ModerationRequest {
        input: input.clone(),
        model: None,
        provider_params: Some(provider_params),
    };

    // Execute moderation
    match probe_provider
        .moderate(&request, clients.http_client, clients.credentials)
        .await
    {
        Ok(response) => {
            let result = response
                .results
                .first()
                .cloned()
                .unwrap_or_else(|| ModerationResult {
                    flagged: false,
                    categories: crate::moderation::ModerationCategories::default(),
                    category_scores: crate::moderation::ModerationCategoryScores::default(),
                    category_applied_input_types: None,
                    hallucination_details: None,
                    ip_violation_details: None,
                    unknown_categories: Default::default(),
                    other_score: 0.0,
                });

            // Apply threshold check for Azure Content Safety
            // If we have scores, use our threshold check exclusively
            // If we don't have scores (detection-only), use the provider's flagged status
            let flagged = if result.category_scores.has_non_zero_scores() {
                let max_score = get_max_score(&result.category_scores);
                max_score >= severity_threshold
            } else {
                // For detection-only probes without scores, trust the provider
                result.flagged
            };

            Ok(ProviderGuardrailResult {
                provider_type: "azure_content_safety".to_string(),
                flagged,
                executed_probes: vec![probe_id.clone()],
                enabled_rules: if !rules.is_empty() {
                    let mut enabled = HashMap::new();
                    enabled.insert(probe_id.clone(), rules.clone());
                    enabled
                } else {
                    HashMap::new()
                },
                raw_result: result,
                error: None,
            })
        }
        Err(e) => Ok(ProviderGuardrailResult {
            provider_type: "azure_content_safety".to_string(),
            flagged: false,
            executed_probes: vec![probe_id.clone()],
            enabled_rules: if !rules.is_empty() {
                let mut enabled = HashMap::new();
                enabled.insert(probe_id, rules);
                enabled
            } else {
                HashMap::new()
            },
            raw_result: ModerationResult {
                flagged: false,
                categories: crate::moderation::ModerationCategories::default(),
                category_scores: crate::moderation::ModerationCategoryScores::default(),
                category_applied_input_types: None,
                hallucination_details: None,
                ip_violation_details: None,
                unknown_categories: Default::default(),
                other_score: 0.0,
            },
            error: Some(e.to_string()),
        }),
    }
}

/// Execute OpenAI probe
async fn execute_openai_probe<'a>(
    probe_id: String,
    rules: Vec<String>,
    provider_config: serde_json::Value,
    severity_threshold: f64,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    _request_provider_params: Option<serde_json::Value>,
) -> Result<ProviderGuardrailResult, Error> {
    use crate::inference::providers::openai::OpenAIProvider;
    use crate::model::CredentialLocation;

    // Extract OpenAI configuration from provider_config
    let api_base = provider_config
        .get("api_base")
        .and_then(|v| v.as_str())
        .and_then(|s| url::Url::parse(s).ok());

    let api_key_location = provider_config
        .get("api_key_location")
        .and_then(|v| serde_json::from_value::<CredentialLocation>(v.clone()).ok());

    // The probe_id is used as the model name for OpenAI moderation
    // (e.g., "omni-moderation-latest")
    let openai_provider = OpenAIProvider::new(probe_id.clone(), api_base, api_key_location)?;

    let request = ModerationRequest {
        input,
        model: Some(probe_id.clone()),
        provider_params: Some(provider_config),
    };

    // Execute moderation
    match openai_provider
        .moderate(&request, clients.http_client, clients.credentials)
        .await
    {
        Ok(response) => {
            let result = response
                .results
                .first()
                .cloned()
                .unwrap_or_else(|| ModerationResult {
                    flagged: false,
                    categories: crate::moderation::ModerationCategories::default(),
                    category_scores: crate::moderation::ModerationCategoryScores::default(),
                    category_applied_input_types: None,
                    hallucination_details: None,
                    ip_violation_details: None,
                    unknown_categories: Default::default(),
                    other_score: 0.0,
                });

            // Apply threshold check for OpenAI
            // If we have scores, use our threshold check exclusively
            // If we don't have scores (shouldn't happen for OpenAI), use the provider's flagged status
            let flagged = if result.category_scores.has_non_zero_scores() {
                let max_score = if !rules.is_empty() {
                    // Only check scores for the specified categories
                    get_max_score_for_categories(&result.category_scores, &rules)
                } else {
                    // Check all scores
                    get_max_score(&result.category_scores)
                };
                max_score >= severity_threshold
            } else {
                // For detection-only probes without scores, trust the provider
                result.flagged
            };

            Ok(ProviderGuardrailResult {
                provider_type: "openai".to_string(),
                flagged,
                executed_probes: vec![probe_id.clone()],
                enabled_rules: if !rules.is_empty() {
                    let mut enabled = HashMap::new();
                    enabled.insert(probe_id.clone(), rules.clone());
                    enabled
                } else {
                    HashMap::new()
                },
                raw_result: result,
                error: None,
            })
        }
        Err(e) => Ok(ProviderGuardrailResult {
            provider_type: "openai".to_string(),
            flagged: false,
            executed_probes: vec![probe_id.clone()],
            enabled_rules: if !rules.is_empty() {
                let mut enabled = HashMap::new();
                enabled.insert(probe_id, rules);
                enabled
            } else {
                HashMap::new()
            },
            raw_result: ModerationResult {
                flagged: false,
                categories: crate::moderation::ModerationCategories::default(),
                category_scores: crate::moderation::ModerationCategoryScores::default(),
                category_applied_input_types: None,
                hallucination_details: None,
                ip_violation_details: None,
                unknown_categories: Default::default(),
                other_score: 0.0,
            },
            error: Some(e.to_string()),
        }),
    }
}

/// Build Azure-specific parameters for a probe
fn build_azure_probe_params(
    probe_id: &str,
    rules: &[String],
    provider_config: &serde_json::Value,
    request_provider_params: Option<serde_json::Value>,
) -> serde_json::Value {
    use serde_json::json;

    let mut params = provider_config.clone();

    // Merge request-specific provider params if provided
    if let Some(request_params) = request_provider_params {
        if let (
            serde_json::Value::Object(ref mut params_obj),
            serde_json::Value::Object(request_obj),
        ) = (&mut params, request_params)
        {
            for (key, value) in request_obj {
                params_obj.insert(key, value);
            }
        }
    }

    match probe_id {
        "moderation" => {
            // Map rules to categories if specified
            if !rules.is_empty() {
                params["categories"] = json!(rules);
            }
        }
        "groundedness-detection-preview" => {
            // Map rules to domain/task configuration
            // TODO: Only support a single domain+task per probe, see if we need to supoort multiple domains and tasks per probe
            for rule in rules {
                if rule.contains("Medical") {
                    params["domain"] = json!("Medical");
                } else {
                    params["domain"] = json!("Generic");
                }

                if rule.contains("QnA") {
                    params["task"] = json!("QnA");
                } else if rule.contains("Summarization") {
                    params["task"] = json!("Summarization");
                }
            }
        }
        "protected-material-detection" => {
            // Rules determine which type of protected material to check
            // This is handled by the probe type selection
        }
        _ => {}
    }

    params
}

/// Build Bud Sentinel provider params by merging guardrail defaults and request overrides
fn build_bud_sentinel_params(
    provider_config: &serde_json::Value,
    request_provider_params: Option<serde_json::Value>,
) -> serde_json::Value {
    use serde_json::Value;

    let mut params = serde_json::Map::new();

    if let Some(profile_id) = provider_config.get("profile_id") {
        params.insert("profile_id".to_string(), profile_id.clone());
    }

    if let Some(severity) = provider_config.get("severity_threshold") {
        params.insert("severity_threshold".to_string(), severity.clone());
    }

    if let Some(Value::Object(overrides)) = request_provider_params {
        for (key, value) in overrides {
            params.insert(key, value);
        }
    }

    Value::Object(params)
}

pub(crate) fn build_bud_sentinel_profile(
    guardrail_id: &str,
    guardrail_severity: f64,
    enabled_probes: &[String],
    enabled_rules_map: &HashMap<String, Vec<String>>,
    provider_config: &serde_json::Map<String, serde_json::Value>,
) -> Result<BudSentinelProfile, Error> {
    let custom_rules = parse_custom_rules(guardrail_id, provider_config)?;
    let profile_id = provider_config
        .get("profile_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| format!("{guardrail_id}-bud-sentinel"));

    let strategy_id = provider_config
        .get("strategy_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| guardrail_id.to_string());

    let description = provider_config
        .get("description")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| format!("Bud Sentinel profile for guardrail {guardrail_id}"));

    let version = provider_config
        .get("version")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| "1".to_string());

    let metadata_json = provider_config
        .get("metadata_json")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();

    let rule_overrides_json = provider_config
        .get("rule_overrides_json")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();

    let mut enabled_rules: Vec<String> = enabled_rules_map
        .values()
        .flat_map(|rules| rules.clone())
        .collect();
    enabled_rules.sort();
    enabled_rules.dedup();

    let provider_severity = provider_config
        .get("severity_threshold")
        .and_then(|v| v.as_f64())
        .map(|v| v as f32);

    let profile_severity = provider_config
        .get("profile_severity_threshold")
        .and_then(|v| v.as_f64())
        .map(|v| v as f32)
        .or(provider_severity)
        .or(Some(guardrail_severity as f32));

    Ok(BudSentinelProfile {
        id: profile_id,
        strategy_id,
        description,
        version,
        enabled_rules,
        enabled_probes: enabled_probes.to_vec(),
        severity_threshold: profile_severity,
        metadata_json,
        rule_overrides_json,
        custom_rules,
    })
}

fn build_enabled_rules_map(probe_id: &str, rules: &[String]) -> HashMap<String, Vec<String>> {
    if rules.is_empty() {
        return HashMap::new();
    }

    let mut enabled = HashMap::new();
    enabled.insert(probe_id.to_string(), rules.to_vec());
    enabled
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CustomRuleConfig {
    id: String,
    scanner: String,
    scanner_config_json: String,
    #[serde(default)]
    target_labels: Vec<String>,
    #[serde(default)]
    severity_threshold: Option<f32>,
    #[serde(default)]
    probe: Option<String>,
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    post_processing_json: Option<String>,
}

impl From<CustomRuleConfig> for BudSentinelCustomRule {
    fn from(config: CustomRuleConfig) -> Self {
        BudSentinelCustomRule {
            id: config.id,
            scanner: config.scanner,
            scanner_config_json: config.scanner_config_json,
            target_labels: config.target_labels,
            severity_threshold: config.severity_threshold,
            probe: config.probe,
            name: config.name,
            description: config.description,
            post_processing_json: config.post_processing_json,
        }
    }
}

impl From<BudSentinelCustomRule> for CustomRuleConfig {
    fn from(rule: BudSentinelCustomRule) -> Self {
        Self {
            id: rule.id,
            scanner: rule.scanner,
            scanner_config_json: rule.scanner_config_json,
            target_labels: rule.target_labels,
            severity_threshold: rule.severity_threshold,
            probe: rule.probe,
            name: rule.name,
            description: rule.description,
            post_processing_json: rule.post_processing_json,
        }
    }
}

fn parse_custom_rules(
    guardrail_id: &str,
    provider_config: &serde_json::Map<String, serde_json::Value>,
) -> Result<Vec<BudSentinelCustomRule>, Error> {
    let Some(custom_rules) = provider_config.get("custom_rules") else {
        return Ok(Vec::new());
    };

    let configs: Vec<CustomRuleConfig> =
        serde_json::from_value(custom_rules.clone()).map_err(|e| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Invalid 'custom_rules' for Bud Sentinel guardrail '{guardrail_id}': {e}"
                ),
            })
        })?;

    Ok(configs
        .into_iter()
        .map(BudSentinelCustomRule::from)
        .collect())
}

pub(crate) fn custom_rules_to_value(
    custom_rules: &[BudSentinelCustomRule],
    guardrail_id: &str,
) -> Result<serde_json::Value, Error> {
    let configs: Vec<CustomRuleConfig> = custom_rules
        .iter()
        .cloned()
        .map(CustomRuleConfig::from)
        .collect();

    serde_json::to_value(configs).map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!(
                "Failed to serialize Bud Sentinel custom_rules for guardrail '{guardrail_id}': {e}"
            ),
        })
    })
}

fn bud_sentinel_error_metadata(error: &Error) -> Option<(Code, String)> {
    match error.get_details() {
        ErrorDetails::InferenceServer {
            provider_type,
            raw_response,
            ..
        } if provider_type == "bud_sentinel" => {
            if let Some(raw) = raw_response {
                if let Ok(value) = serde_json::from_str::<serde_json::Value>(raw) {
                    if let Some(code) = value.get("code").and_then(|v| v.as_i64()) {
                        let message = value
                            .get("message")
                            .and_then(|v| v.as_str())
                            .unwrap_or_default()
                            .to_string();
                        return Some((Code::from_i32(code as i32), message));
                    }
                }
            }
            None
        }
        _ => None,
    }
}

/// Execute Bud Sentinel probe
async fn execute_bud_sentinel_probe<'a>(
    task: ProbeTask,
    input: ModerationInput,
    clients: &InferenceClients<'a>,
    request_provider_params: Option<serde_json::Value>,
) -> Result<ProviderGuardrailResult, Error> {
    let ProbeTask {
        provider_type: _,
        guardrail_id,
        guardrail_severity,
        provider_enabled_probes,
        provider_enabled_rules,
        provider_config,
        probe_id,
        rules,
    } = task;

    let provider_config_obj = provider_config.as_object().ok_or_else(|| {
        Error::new(ErrorDetails::Config {
            message: format!(
                "Bud Sentinel provider configuration for guardrail '{guardrail_id}' must be a JSON object"
            ),
        })
    })?;

    let endpoint = provider_config_obj
        .get("endpoint")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!(
                    "Missing 'endpoint' in Bud Sentinel provider configuration for guardrail '{guardrail_id}'"
                ),
            })
        })?;

    let endpoint_url = url::Url::parse(endpoint).map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Invalid Bud Sentinel endpoint URL: {e}"),
        })
    })?;

    let api_key_location = provider_config_obj
        .get("api_key_location")
        .cloned()
        .and_then(|value| serde_json::from_value::<CredentialLocation>(value).ok());

    let provider_default_severity = provider_config_obj
        .get("severity_threshold")
        .and_then(|v| v.as_f64())
        .map(|v| v as f32);

    let mut profile = build_bud_sentinel_profile(
        &guardrail_id,
        guardrail_severity,
        &provider_enabled_probes,
        &provider_enabled_rules,
        provider_config_obj,
    )?;

    let provider = BudSentinelProvider::new(
        endpoint_url,
        api_key_location,
        Some(profile.id.clone()),
        provider_default_severity,
    )?;

    let mut provider_params = build_bud_sentinel_params(&provider_config, request_provider_params);

    if provider_config_obj
        .get("profile_sync_pending")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
    {
        match provider
            .ensure_profile(profile.clone(), clients.credentials)
            .await
        {
            Ok(updated_profile) => {
                profile = updated_profile;
                if let Some(params) = provider_params.as_object_mut() {
                    params.insert(
                        "profile_id".to_string(),
                        serde_json::Value::String(profile.id.clone()),
                    );
                }
            }
            Err(err) => {
                tracing::warn!(
                    guardrail_id = guardrail_id.as_str(),
                    probe_id = probe_id.as_str(),
                    "Bud Sentinel profile synchronization retry failed during guardrail execution: {err}"
                );
            }
        }
    }

    let mut moderation_request = ModerationRequest {
        input: input.clone(),
        model: None,
        provider_params: Some(provider_params.clone()),
    };

    let mut attempts = 0usize;
    loop {
        match provider
            .moderate(
                &moderation_request,
                clients.http_client,
                clients.credentials,
            )
            .await
        {
            Ok(response) => {
                let result =
                    response
                        .results
                        .first()
                        .cloned()
                        .unwrap_or_else(|| ModerationResult {
                            flagged: false,
                            categories: crate::moderation::ModerationCategories::default(),
                            category_scores: crate::moderation::ModerationCategoryScores::default(),
                            category_applied_input_types: None,
                            hallucination_details: None,
                            ip_violation_details: None,
                            unknown_categories: Default::default(),
                            other_score: 0.0,
                        });

                let flagged = if result.category_scores.has_non_zero_scores()
                    || result.other_score > 0.0
                {
                    let max_score =
                        get_max_score(&result.category_scores).max(result.other_score as f64);
                    max_score >= guardrail_severity
                } else {
                    result.flagged
                };

                return Ok(ProviderGuardrailResult {
                    provider_type: "bud_sentinel".to_string(),
                    flagged,
                    executed_probes: vec![probe_id.clone()],
                    enabled_rules: build_enabled_rules_map(&probe_id, &rules),
                    raw_result: result,
                    error: None,
                });
            }
            Err(err) => {
                let error_info = bud_sentinel_error_metadata(&err);
                let code_opt = error_info.as_ref().map(|(code, _)| *code);
                let message = error_info
                    .as_ref()
                    .map(|(_, msg)| msg.as_str())
                    .unwrap_or_default()
                    .to_ascii_lowercase();
                let fallback_message = err.to_string().to_ascii_lowercase();

                let missing_profile = message.contains("profile not found")
                    || (message.contains("profile '") && message.contains("not found"))
                    || fallback_message.contains("profile not found")
                    || (fallback_message.contains("profile '")
                        && fallback_message.contains("not found"))
                    || matches!(code_opt, Some(Code::NotFound));

                let transient_error = matches!(
                    code_opt,
                    Some(Code::Unavailable | Code::Unknown | Code::DeadlineExceeded)
                );

                if attempts == 0 && missing_profile {
                    match provider.get_profile(&profile.id, clients.credentials).await {
                        Ok(Some(_)) => {
                            // Profile exists; no corrective action required.
                        }
                        Ok(None) => match provider
                            .ensure_profile(profile.clone(), clients.credentials)
                            .await
                        {
                            Ok(ensured_profile) => {
                                profile = ensured_profile;
                                if let Some(params) = provider_params.as_object_mut() {
                                    params.insert(
                                        "profile_id".to_string(),
                                        serde_json::Value::String(profile.id.clone()),
                                    );
                                }
                                moderation_request.provider_params = Some(provider_params.clone());
                                attempts += 1;
                                continue;
                            }
                            Err(sync_err) => {
                                tracing::warn!(
                                    guardrail_id = guardrail_id.as_str(),
                                    probe_id = probe_id.as_str(),
                                    "Failed to re-register Bud Sentinel profile: {sync_err}"
                                );
                            }
                        },
                        Err(fetch_err) => {
                            tracing::warn!(
                                guardrail_id = guardrail_id.as_str(),
                                probe_id = probe_id.as_str(),
                                "Failed to fetch Bud Sentinel profile state: {fetch_err}"
                            );
                        }
                    }
                } else if attempts == 0 && transient_error {
                    tokio::time::sleep(Duration::from_millis(200)).await;
                    attempts += 1;
                    continue;
                }

                return Ok(ProviderGuardrailResult {
                    provider_type: "bud_sentinel".to_string(),
                    flagged: false,
                    executed_probes: vec![probe_id.clone()],
                    enabled_rules: build_enabled_rules_map(&probe_id, &rules),
                    raw_result: ModerationResult {
                        flagged: false,
                        categories: crate::moderation::ModerationCategories::default(),
                        category_scores: crate::moderation::ModerationCategoryScores::default(),
                        category_applied_input_types: None,
                        hallucination_details: None,
                        ip_violation_details: None,
                        unknown_categories: Default::default(),
                        other_score: 0.0,
                    },
                    error: Some(err.to_string()),
                });
            }
        }
    }
}

/// Get the maximum score from ModerationCategoryScores
fn get_max_score(scores: &crate::moderation::ModerationCategoryScores) -> f64 {
    vec![
        scores.hate,
        scores.hate_threatening,
        scores.harassment,
        scores.harassment_threatening,
        scores.illicit,
        scores.illicit_violent,
        scores.self_harm,
        scores.self_harm_intent,
        scores.self_harm_instructions,
        scores.sexual,
        scores.sexual_minors,
        scores.violence,
        scores.violence_graphic,
        scores.profanity,
        scores.insult,
        scores.toxicity,
        scores.malicious,
        scores.pii,
        scores.secrets,
    ]
    .into_iter()
    .fold(0.0_f64, |max, val| max.max(val as f64))
}

/// Get the maximum score for specific categories only
fn get_max_score_for_categories(
    scores: &crate::moderation::ModerationCategoryScores,
    categories: &[String],
) -> f64 {
    let mut max_score = 0.0_f64;

    for category in categories {
        let score = match category.as_str() {
            "hate" => scores.hate,
            "hate/threatening" => scores.hate_threatening,
            "harassment" => scores.harassment,
            "harassment/threatening" => scores.harassment_threatening,
            "illicit" => scores.illicit,
            "illicit/violent" => scores.illicit_violent,
            "self-harm" => scores.self_harm,
            "self-harm/intent" => scores.self_harm_intent,
            "self-harm/instructions" => scores.self_harm_instructions,
            "sexual" => scores.sexual,
            "sexual/minors" => scores.sexual_minors,
            "violence" => scores.violence,
            "violence/graphic" => scores.violence_graphic,
            "profanity" => scores.profanity,
            "insult" => scores.insult,
            "toxicity" => scores.toxicity,
            "malicious" => scores.malicious,
            "pii" => scores.pii,
            "secrets" => scores.secrets,
            _ => 0.0,
        };
        max_score = max_score.max(score as f64);
    }

    max_score
}

/// Get a guardrail configuration by ID
pub async fn get_guardrail(
    guardrail_id: &str,
    guardrails: &GuardrailTable,
) -> Option<Arc<GuardrailConfig>> {
    guardrails.get(guardrail_id).cloned()
}

/// Execute guardrail by ID
pub async fn execute_guardrail_by_id<'a>(
    guardrail_id: &str,
    input: ModerationInput,
    guard_type: GuardType,
    guardrails: &GuardrailTable,
    clients: &InferenceClients<'a>,
) -> Result<GuardrailResult, Error> {
    let guardrail_config = get_guardrail(guardrail_id, guardrails)
        .await
        .ok_or_else(|| {
            Error::new(ErrorDetails::Config {
                message: format!("Guardrail '{}' not found", guardrail_id),
            })
        })?;

    execute_guardrail(&guardrail_config, input, guard_type, clients, None, false).await
}

// ================== Observability Types ==================

/// Represents the scan mode for guardrail execution
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ScanMode {
    Single = 1,
    ProviderManagedMulti = 2,
    GatewayManagedMulti = 3,
}

impl ScanMode {
    /// Convert to u8 for database storage
    pub fn to_db_value(self) -> u8 {
        match self {
            ScanMode::Single => 1,
            ScanMode::ProviderManagedMulti => 2,
            ScanMode::GatewayManagedMulti => 3,
        }
    }
}

/// Represents the status of a guardrail scan
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ScanStatus {
    Completed = 1,
    InProgress = 2,
    Cancelled = 3,
    TimedOut = 4,
}

impl ScanStatus {
    /// Convert to u8 for database storage
    pub fn to_db_value(self) -> u8 {
        match self {
            ScanStatus::Completed => 1,
            ScanStatus::InProgress => 2,
            ScanStatus::Cancelled => 3,
            ScanStatus::TimedOut => 4,
        }
    }
}

/// Database insert model for GuardrailInference table
#[derive(Clone, Debug, Serialize)]
pub struct GuardrailInferenceDatabaseInsert {
    pub id: Uuid,
    pub inference_id: Uuid,
    pub parent_scan_id: Option<Uuid>,
    pub guardrail_profile: String,
    pub guard_type: u8, // Enum representation
    pub scan_stage: String,
    pub scan_mode: u8, // Enum representation
    pub flagged: bool,
    pub confidence_score: Option<f32>,
    pub provider_results: String, // JSON
    pub scan_status: u8,          // Enum representation
    pub scan_latency_ms: Option<u32>,
    #[serde(serialize_with = "serialize_datetime64")]
    pub scan_started_at: chrono::DateTime<chrono::Utc>,
    #[serde(serialize_with = "serialize_optional_datetime64")]
    pub scan_completed_at: Option<chrono::DateTime<chrono::Utc>>,
    pub action_taken: String,
    pub external_scan_id: Option<String>,
    pub input_hash: String,
    pub scan_metadata: String, // JSON
}

/// Serialize DateTime to ClickHouse DateTime64(3) format
fn serialize_datetime64<S>(
    dt: &chrono::DateTime<chrono::Utc>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    let formatted = dt.format("%Y-%m-%d %H:%M:%S%.3f").to_string();
    serializer.serialize_str(&formatted)
}

/// Serialize Optional DateTime to ClickHouse DateTime64(3) format
fn serialize_optional_datetime64<S>(
    dt: &Option<chrono::DateTime<chrono::Utc>>,
    serializer: S,
) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    match dt {
        Some(dt) => serialize_datetime64(dt, serializer),
        None => serializer.serialize_none(),
    }
}

impl GuardrailInferenceDatabaseInsert {
    pub fn from_result(
        inference_id: Uuid,
        guardrail_profile: String,
        guard_type: GuardType,
        scan_stage: String,
        scan_mode: ScanMode,
        result: &GuardrailResult,
        scan_duration: Option<Duration>,
        input_text: &str,
        parent_scan_id: Option<Uuid>,
    ) -> Self {
        let scan_started_at = chrono::Utc::now();
        let scan_completed_at = scan_duration.map(|_| scan_started_at);
        let scan_latency_ms = scan_duration.map(|d| d.as_millis() as u32);

        // Hash the input for privacy
        let mut hasher = Sha256::new();
        hasher.update(input_text.as_bytes());
        let input_hash = format!("{:x}", hasher.finalize());

        // Serialize provider results
        let provider_results =
            serde_json::to_string(&result.provider_results).unwrap_or_else(|_| "[]".to_string());

        // Determine action taken based on result
        let action_taken = if result.flagged {
            match guard_type {
                GuardType::Input => "block",
                GuardType::Output => "modify_response",
            }
        } else {
            "allow"
        }
        .to_string();

        // Build scan metadata
        let scan_metadata = serde_json::json!({
            "guardrail_id": result.guardrail_id,
            "merged_categories": result.merged_categories,
            "merged_scores": result.merged_scores,
            "hallucination_details": result.hallucination_details,
            "ip_violation_details": result.ip_violation_details,
        })
        .to_string();

        Self {
            id: Uuid::now_v7(),
            inference_id,
            parent_scan_id,
            guardrail_profile,
            guard_type: guard_type.to_db_value(),
            scan_stage,
            scan_mode: scan_mode.to_db_value(),
            flagged: result.flagged,
            confidence_score: None, // Could be extracted from provider results
            provider_results,
            scan_status: ScanStatus::Completed.to_db_value(),
            scan_latency_ms,
            scan_started_at,
            scan_completed_at,
            action_taken,
            external_scan_id: None,
            input_hash,
            scan_metadata,
        }
    }
}

/// Summary of guardrail scans for a model inference
#[derive(Debug, Serialize, Deserialize, Default)]
pub struct GuardrailScanSummary {
    pub input_scans: Option<ScanSummary>,
    pub output_scans: Option<ScanSummary>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScanSummary {
    pub stages_completed: Vec<String>,
    pub final_decision: String,
    pub total_scan_time_ms: u32,
    pub scan_chain: Vec<Uuid>,
}

/// Context for tracking guardrail execution
pub struct GuardrailExecutionContext {
    pub scan_records: Vec<GuardrailInferenceDatabaseInsert>,
    pub input_scan_time_ms: Option<u32>,
    pub output_scan_time_ms: Option<u32>,
    pub response_terminated: bool,
}

impl GuardrailExecutionContext {
    pub fn new() -> Self {
        Self {
            scan_records: Vec::new(),
            input_scan_time_ms: None,
            output_scan_time_ms: None,
            response_terminated: false,
        }
    }

    pub fn add_scan_record(&mut self, record: GuardrailInferenceDatabaseInsert) {
        match record.guard_type {
            1 => {
                // Input
                if let Some(latency) = record.scan_latency_ms {
                    self.input_scan_time_ms = Some(self.input_scan_time_ms.unwrap_or(0) + latency);
                }
            }
            2 => {
                // Output
                if let Some(latency) = record.scan_latency_ms {
                    self.output_scan_time_ms =
                        Some(self.output_scan_time_ms.unwrap_or(0) + latency);
                }
            }
            _ => {}
        }
        self.scan_records.push(record);
    }

    pub fn build_summary(&self) -> GuardrailScanSummary {
        let mut summary = GuardrailScanSummary::default();

        // Group by guard type
        let input_records: Vec<_> = self
            .scan_records
            .iter()
            .filter(|r| r.guard_type == 1)
            .collect();

        let output_records: Vec<_> = self
            .scan_records
            .iter()
            .filter(|r| r.guard_type == 2)
            .collect();

        // Build input scan summary
        if !input_records.is_empty() {
            let stages: Vec<_> = input_records.iter().map(|r| r.scan_stage.clone()).collect();

            let final_decision = if input_records.iter().any(|r| r.flagged) {
                "blocked"
            } else {
                "allowed"
            }
            .to_string();

            let scan_chain: Vec<_> = input_records.iter().map(|r| r.id).collect();

            summary.input_scans = Some(ScanSummary {
                stages_completed: stages,
                final_decision,
                total_scan_time_ms: self.input_scan_time_ms.unwrap_or(0),
                scan_chain,
            });
        }

        // Build output scan summary
        if !output_records.is_empty() {
            let stages: Vec<_> = output_records
                .iter()
                .map(|r| r.scan_stage.clone())
                .collect();

            let final_decision = if output_records.iter().any(|r| r.flagged) {
                "blocked"
            } else {
                "allowed"
            }
            .to_string();

            let scan_chain: Vec<_> = output_records.iter().map(|r| r.id).collect();

            summary.output_scans = Some(ScanSummary {
                stages_completed: stages,
                final_decision,
                total_scan_time_ms: self.output_scan_time_ms.unwrap_or(0),
                scan_chain,
            });
        }

        summary
    }
}
