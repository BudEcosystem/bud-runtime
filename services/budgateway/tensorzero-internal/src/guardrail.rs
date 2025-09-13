use std::collections::HashMap;
use std::sync::Arc;

use futures::stream::{FuturesUnordered, StreamExt};

use crate::endpoints::inference::InferenceClients;
use crate::error::{Error, ErrorDetails};
use crate::guardrail_table::{
    ExecutionMode, FailureMode, GuardType, GuardrailConfig, GuardrailResult, GuardrailTable,
    ProviderGuardrailResult, merge_moderation_results,
};
use crate::moderation::{
    ModerationInput, ModerationProvider, ModerationRequest, ModerationResult,
};

/// Execute a guardrail configuration against input text
/// This version creates separate provider instances for each probe
pub async fn execute_guardrail<'a>(
    guardrail_config: &GuardrailConfig,
    input: ModerationInput,
    guard_type: GuardType,
    clients: &InferenceClients<'a>,
    provider_params: Option<serde_json::Value>,
) -> Result<GuardrailResult, Error> {
    // Validate the guardrail configuration
    guardrail_config.validate()?;

    // Check if this guardrail supports the requested guard type
    if !guardrail_config.guard_types.contains(&guard_type) {
        return Ok(GuardrailResult {
            guardrail_id: guardrail_config.id.clone(),
            flagged: false,
            provider_results: vec![],
            merged_categories: crate::moderation::ModerationCategories::default(),
            merged_scores: crate::moderation::ModerationCategoryScores::default(),
            merged_category_applied_input_types: None,
            hallucination_details: None,
            ip_violation_details: None,
        });
    }

    // Create probe execution tasks
    let probe_tasks = create_probe_tasks(guardrail_config, &input);

    let provider_results = match guardrail_config.execution_mode {
        ExecutionMode::Parallel => {
            execute_parallel(probe_tasks, guardrail_config, input.clone(), clients, provider_params.clone()).await?
        }
        ExecutionMode::Sequential => {
            execute_sequential(probe_tasks, guardrail_config, input.clone(), clients, provider_params.clone()).await?
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

    let (merged_categories, merged_scores, merged_category_applied_input_types) = merge_moderation_results(moderation_results);

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
    let flagged = provider_results.iter().any(|pr| pr.error.is_none() && pr.flagged);

    Ok(GuardrailResult {
        guardrail_id: guardrail_config.id.clone(),
        flagged,
        provider_results,
        merged_categories,
        merged_scores,
        merged_category_applied_input_types,
        hallucination_details,
        ip_violation_details,
    })
}

/// Represents a single probe execution task
struct ProbeTask {
    provider_type: String,
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
        for probe_id in &provider_config.enabled_probes {
            let rules = provider_config.enabled_rules
                .get(probe_id)
                .cloned()
                .unwrap_or_default();

            // Special handling for protected-material-detection
            if probe_id == "protected-material-detection" && provider_config.provider_type == "azure_content_safety" {
                // Create separate probe tasks for each rule type
                for rule in &rules {
                    let specific_probe_id = match rule.as_str() {
                        "text" => "protected-material-detection-text".to_string(),
                        "code-preview" => "protected-material-detection-code".to_string(),
                        _ => continue, // Skip unknown rules
                    };

                    tasks.push(ProbeTask {
                        provider_type: provider_config.provider_type.clone(),
                        probe_id: specific_probe_id,
                        rules: vec![rule.clone()], // Single rule for this specific probe
                        provider_config: provider_config.provider_config.clone(),
                    });
                }
            } else {
                // Normal probe task creation
                tasks.push(ProbeTask {
                    provider_type: provider_config.provider_type.clone(),
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
        let future = execute_single_probe(
            task,
            guardrail_config.severity_threshold,
            input.clone(),
            clients,
            provider_params.clone(),
        );

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
        match execute_single_probe(
            task,
            guardrail_config.severity_threshold,
            input.clone(),
            clients,
            provider_params.clone(),
        )
        .await
        {
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
    severity_threshold: f64,
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
                severity_threshold,
                input,
                clients,
                request_provider_params.clone(),
            ).await
        }
        "openai" => {
            execute_openai_probe(
                task.probe_id.clone(),
                task.rules,
                task.provider_config,
                severity_threshold,
                input,
                clients,
                request_provider_params.clone(),
            ).await
        }
        _ => Err(Error::new(ErrorDetails::Config {
            message: format!("Unsupported provider type: {}", task.provider_type),
        })),
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
    use crate::inference::providers::azure_content_safety::{AzureContentSafetyProvider, ProbeType};
    use crate::model::CredentialLocation;

    // Map probe ID to probe type
    let probe_type = ProbeType::from_probe_id(&probe_id)
        .ok_or_else(|| Error::new(ErrorDetails::Config {
            message: format!("Unknown Azure Content Safety probe: {}", probe_id),
        }))?;

    // Extract Azure Content Safety configuration from provider_config
    let endpoint = provider_config
        .get("endpoint")
        .and_then(|v| v.as_str())
        .ok_or_else(|| Error::new(ErrorDetails::Config {
            message: "Missing 'endpoint' in Azure Content Safety provider configuration".to_string(),
        }))?;

    let endpoint_url = url::Url::parse(endpoint)
        .map_err(|e| Error::new(ErrorDetails::Config {
            message: format!("Invalid Azure Content Safety endpoint URL: {}", e),
        }))?;

    let api_key_location = provider_config
        .get("api_key_location")
        .and_then(|v| serde_json::from_value::<CredentialLocation>(v.clone()).ok());

    // Create a new Azure Content Safety provider instance for this specific probe
    let probe_provider = AzureContentSafetyProvider::new(endpoint_url, api_key_location, probe_type)?;

    // Prepare provider parameters based on probe type and rules
    let provider_params = build_azure_probe_params(&probe_id, &rules, &provider_config, request_provider_params);

    let request = ModerationRequest {
        input: input.clone(),
        model: None,
        provider_params: Some(provider_params),
    };

    // Execute moderation
    match probe_provider.moderate(&request, clients.http_client, clients.credentials).await {
        Ok(response) => {
            let result = response.results.first().cloned().unwrap_or_else(|| {
                ModerationResult {
                    flagged: false,
                    categories: crate::moderation::ModerationCategories::default(),
                    category_scores: crate::moderation::ModerationCategoryScores::default(),
                    category_applied_input_types: None,
                    hallucination_details: None,
                    ip_violation_details: None,
                }
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
    let openai_provider = OpenAIProvider::new(
        probe_id.clone(),
        api_base,
        api_key_location,
    )?;

    let request = ModerationRequest {
        input,
        model: Some(probe_id.clone()),
        provider_params: Some(provider_config),
    };

    // Execute moderation
    match openai_provider.moderate(&request, clients.http_client, clients.credentials).await {
        Ok(response) => {
            let result = response.results.first().cloned().unwrap_or_else(|| {
                ModerationResult {
                    flagged: false,
                    categories: crate::moderation::ModerationCategories::default(),
                    category_scores: crate::moderation::ModerationCategoryScores::default(),
                    category_applied_input_types: None,
                    hallucination_details: None,
                    ip_violation_details: None,
                }
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
        if let (serde_json::Value::Object(ref mut params_obj), serde_json::Value::Object(request_obj)) = (&mut params, request_params) {
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

    execute_guardrail(&guardrail_config, input, guard_type, clients, None).await
}
