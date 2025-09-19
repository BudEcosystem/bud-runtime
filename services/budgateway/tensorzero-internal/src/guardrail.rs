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
use crate::moderation::{ModerationInput, ModerationProvider, ModerationRequest, ModerationResult};

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

    let (merged_categories, merged_scores, merged_category_applied_input_types) =
        merge_moderation_results(moderation_results);

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
            )
            .await
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
            )
            .await
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
