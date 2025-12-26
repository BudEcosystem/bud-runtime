use std::io::Write;
use std::sync::Arc;
use std::{collections::HashMap, path::PathBuf};

use anyhow::{anyhow, bail, Result};
use clap::Parser;
use dataset::query_dataset;
use evaluators::{evaluate_inference, EvaluateInferenceParams};
use helpers::{get_cache_options, get_tool_params_args};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use stats::{EvaluationError, EvaluationInfo, EvaluationStats, EvaluationUpdate};
use tensorzero_internal::cache::CacheEnabledMode;
use tensorzero_internal::config_parser::MetricConfigOptimize;
use tensorzero_internal::endpoints::inference::{
    InferenceOutput, InferenceParams, InferenceResponse, Params as InferenceRequestParams,
};
use tensorzero_internal::evaluations::{EvaluationConfig, EvaluatorConfig};
use tensorzero_internal::inference::types::{
    current_timestamp, ChatInferenceResult, InferenceResult, Input, InternalJsonInferenceOutput,
    JsonInferenceResult, Usage,
};
use tensorzero_internal::tool::DynamicToolParams;
use tensorzero_internal::{
    clickhouse::ClickHouseConnectionInfo, config_parser::Config, endpoints::datasets::Datapoint,
    function::FunctionConfig,
};
use tokio::{sync::Semaphore, task::JoinSet};
use url::Url;
use uuid::Uuid;

pub mod dataset;
pub mod evaluators;
pub mod helpers;
pub mod stats;

// Helper function to convert ResolvedInput to Input
fn resolved_input_to_input(
    resolved_input: &tensorzero_internal::inference::types::ResolvedInput,
) -> Input {
    use tensorzero_internal::inference::types::{InputMessage, InputMessageContent, TextKind};

    let messages = resolved_input.messages.iter().map(|msg| {
        let content = msg.content.iter().map(|content_block| {
            match content_block {
                tensorzero_internal::inference::types::ResolvedInputMessageContent::Text { value } => {
                    match value {
                        Value::String(s) => InputMessageContent::Text(TextKind::Text { text: s.clone() }),
                        Value::Object(obj) => InputMessageContent::Text(TextKind::Arguments { arguments: obj.clone() }),
                        _ => InputMessageContent::Text(TextKind::LegacyValue { value: value.clone() }),
                    }
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::ToolCall(tc) => {
                    InputMessageContent::ToolCall(tc.clone())
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::ToolResult(tr) => {
                    InputMessageContent::ToolResult(tr.clone())
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::RawText { value } => {
                    InputMessageContent::RawText { value: value.clone() }
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::Thought(t) => {
                    InputMessageContent::Thought(t.clone())
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::File(_) => {
                    // For now, we'll skip file content in evaluations
                    InputMessageContent::Text(TextKind::Text { text: "[File content]".to_string() })
                }
                tensorzero_internal::inference::types::ResolvedInputMessageContent::Unknown { data, model_provider_name } => {
                    InputMessageContent::Unknown { data: data.clone(), model_provider_name: model_provider_name.clone() }
                }
            }
        }).collect();

        InputMessage {
            role: msg.role,
            content,
        }
    }).collect();

    Input {
        system: resolved_input.system.clone(),
        messages,
    }
}

#[derive(clap::ValueEnum, Clone, Debug, Default, PartialEq)]
#[clap(rename_all = "snake_case")]
pub enum OutputFormat {
    Jsonl,
    #[default]
    Pretty,
}

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
pub struct Args {
    /// Path to tensorzero.toml.
    #[arg(long, default_value = "./config/tensorzero.toml")]
    pub config_file: PathBuf,

    /// URL of a running TensorZero HTTP gateway server to use for requests. This runs evaluations using that gateway.
    #[arg(long)]
    pub gateway_url: Option<Url>,

    /// Name of the evaluation to run.
    #[arg(short, long)]
    pub evaluation_name: String,

    /// Name of the dataset to run on.
    #[arg(short, long)]
    pub dataset_name: String,

    /// Name of the variant to run.
    #[arg(short, long)]
    pub variant_name: String,

    /// Number of concurrent requests to make.
    #[arg(short, long, default_value = "1")]
    pub concurrency: usize,

    #[arg(short, long, default_value = "pretty")]
    pub format: OutputFormat,

    #[arg(long, default_value = "on")]
    pub inference_cache: CacheEnabledMode,
}

pub struct Clients {
    pub tensorzero_client: ThrottledTensorZeroClient,
    pub clickhouse_client: ClickHouseConnectionInfo,
}

pub async fn run_evaluation(
    args: Args,
    evaluation_run_id: Uuid,
    mut writer: impl Write,
) -> Result<()> {
    let semaphore = Semaphore::new(args.concurrency);
    let clickhouse_url = std::env::var("TENSORZERO_CLICKHOUSE_URL")
        .map_err(|_| anyhow!("Missing ClickHouse URL at TENSORZERO_CLICKHOUSE_URL"))?;

    // We do not validate credentials here since we just want the evaluator config
    // If we are using an embedded gateway, credentials are validated when that is initialized
    let config =
        Config::load_from_path_optional_verify_credentials(&args.config_file, false).await?;
    let evaluation_config = config
        .evaluations
        .get(&args.evaluation_name)
        .ok_or(anyhow!("evaluation not found"))?
        .clone();
    let EvaluationConfig::Static(static_evaluation_config) = &*evaluation_config;
    let function_config = config
        .get_function(&static_evaluation_config.function_name)?
        .into_owned();
    let (gateway_url, http_client) = match args.gateway_url {
        Some(gateway_url) => {
            let http_client = reqwest::Client::new();
            (gateway_url, http_client)
        }
        None => {
            bail!(
                "Embedded gateway mode is not currently supported. Please provide a --gateway-url."
            );
        }
    };
    let clients = Arc::new(Clients {
        tensorzero_client: ThrottledTensorZeroClient::new(gateway_url, http_client, semaphore),
        clickhouse_client: ClickHouseConnectionInfo::new(&clickhouse_url).await?,
    });

    let mut join_set = JoinSet::new();

    let dataset = query_dataset(
        &clients.clickhouse_client,
        &args.dataset_name,
        &static_evaluation_config.function_name,
        &function_config,
    )
    .await?;
    let dataset_name = Arc::new(args.dataset_name);
    let variant_name = Arc::new(args.variant_name);
    let evaluation_name = Arc::new(args.evaluation_name);
    let dataset_len = dataset.len();
    let mut task_id_to_datapoint_id = HashMap::new();

    write_run_info(
        &mut writer,
        &RunInfo {
            evaluation_run_id,
            num_datapoints: dataset_len,
        },
        &args.format,
    )?;

    // Spawn concurrent tasks for each datapoint
    for datapoint in dataset {
        let clients_clone = clients.clone();
        let variant_name = variant_name.clone();
        let function_config = function_config.clone();
        let evaluation_config = evaluation_config.clone();
        let dataset_name = dataset_name.clone();
        let function_name = static_evaluation_config.function_name.clone();
        let evaluation_name = evaluation_name.clone();
        let evaluation_run_id_clone = evaluation_run_id;
        let datapoint = Arc::new(datapoint);
        let datapoint_id = datapoint.id();
        let abort_handle = join_set.spawn(async move {
            let input = Arc::new(resolved_input_to_input(datapoint.input()));
            let inference_response = Arc::new(
                infer_datapoint(InferDatapointParams {
                    clients: &clients_clone,
                    function_name: &function_name,
                    variant_name: &variant_name,
                    evaluation_run_id: evaluation_run_id_clone,
                    dataset_name: &dataset_name,
                    datapoint: &datapoint,
                    evaluation_name: &evaluation_name,
                    function_config: &function_config,
                    input: &input,
                    inference_cache: args.inference_cache,
                })
                .await?,
            );

            let evaluation_result = evaluate_inference(
                EvaluateInferenceParams {
                    inference_response: inference_response.clone(),
                    datapoint: datapoint.clone(),
                    input,
                    evaluation_config,
                    evaluation_name,
                    clients: clients_clone.clone(),
                    evaluation_run_id: evaluation_run_id_clone,
                    inference_cache: args.inference_cache,
                })
                .await?;

            Ok::<(Datapoint, InferenceResponse, evaluators::EvaluationResult), anyhow::Error>((
                Arc::into_inner(datapoint).ok_or_else(|| anyhow!("Failed to get datapoint for datapoint. This should never happen. Please file a bug report at https://github.com/tensorzero/tensorzero/discussions/categories/bug-reports."))?,
                Arc::into_inner(inference_response).ok_or_else(|| anyhow!("Failed to get inference response for datapoint. This should never happen. Please file a bug report at https://github.com/tensorzero/tensorzero/discussions/categories/bug-reports."))?,
                evaluation_result,
            ))
        });
        task_id_to_datapoint_id.insert(abort_handle.id(), datapoint_id);
    }

    // Collect results
    let mut evaluation_stats = EvaluationStats::new(args.format, dataset_len);

    while let Some(result) = join_set.join_next_with_id().await {
        match result {
            Ok((_, Ok((datapoint, inference_response, evaluation_result)))) => {
                evaluation_stats.push(
                    EvaluationUpdate::Success(EvaluationInfo::new(
                        datapoint,
                        inference_response,
                        evaluation_result,
                    )),
                    &mut writer,
                )?;
            }
            Ok((task_id, Err(e))) => {
                tracing::warn!("Task error: {}", e);
                evaluation_stats.push(
                    EvaluationUpdate::Error(EvaluationError {
                        datapoint_id: task_id_to_datapoint_id[&task_id],
                        message: e.to_string(),
                    }),
                    &mut writer,
                )?;
            }
            Err(e) => evaluation_stats.push(
                EvaluationUpdate::Error(EvaluationError {
                    datapoint_id: task_id_to_datapoint_id[&e.id()],
                    message: e.to_string(),
                }),
                &mut writer,
            )?,
        }
    }

    if let Some(progress_bar) = &evaluation_stats.progress_bar {
        progress_bar.finish_with_message("Done");
    }

    if evaluation_stats.output_format == OutputFormat::Pretty {
        let stats = evaluation_stats.compute_stats(&static_evaluation_config.evaluators);

        // Print all stats
        for (evaluator_name, evaluator_stats) in &stats {
            writeln!(writer, "{evaluator_name}: {evaluator_stats}")?;
        }

        // Check cutoffs and handle failures
        let failures = check_evaluator_cutoffs(&stats, &static_evaluation_config.evaluators)?;

        // Print failure messages
        for (name, cutoff, actual) in &failures {
            writeln!(
                writer,
                "Failed cutoff for evaluator {name} ({cutoff:.2}, got {actual:.2})"
            )?;
        }

        // If there are failures, return an error with all failures listed
        if !failures.is_empty() {
            let failure_messages = format_cutoff_failures(&failures);
            bail!("Failed cutoffs for evaluators: {}", failure_messages);
        }
    }

    Ok(())
}

/// Checks if evaluator results meet their cutoff thresholds
///
/// Returns a vector of failures with (evaluator_name, cutoff, actual_value)
pub fn check_evaluator_cutoffs(
    stats: &HashMap<String, stats::EvaluatorStats>,
    evaluator_configs: &HashMap<String, EvaluatorConfig>,
) -> Result<Vec<(String, f32, f32)>> {
    let mut failures = Vec::new();

    for (evaluator_name, evaluator_stats) in stats {
        let evaluator_config = evaluator_configs
            .get(evaluator_name)
            .ok_or_else(|| anyhow!("Evaluator not found for computing stats"))?;

        if let Some(cutoff) = evaluator_config.cutoff() {
            match evaluator_config.optimize() {
                MetricConfigOptimize::Max => {
                    if evaluator_stats.mean < cutoff {
                        failures.push((evaluator_name.clone(), cutoff, evaluator_stats.mean));
                    }
                }
                MetricConfigOptimize::Min => {
                    if evaluator_stats.mean > cutoff {
                        failures.push((evaluator_name.clone(), cutoff, evaluator_stats.mean));
                    }
                }
            }
        }
    }

    Ok(failures)
}

/// Formats a list of cutoff failures into a human-readable string
pub fn format_cutoff_failures(failures: &[(String, f32, f32)]) -> String {
    failures
        .iter()
        .map(|(name, cutoff, actual)| format!("{name} (cutoff: {cutoff:.2}, got: {actual:.2})"))
        .collect::<Vec<_>>()
        .join("\n")
}

struct InferDatapointParams<'a> {
    clients: &'a Clients,
    function_name: &'a str,
    variant_name: &'a str,
    evaluation_run_id: Uuid,
    dataset_name: &'a str,
    datapoint: &'a Datapoint,
    input: &'a Input,
    evaluation_name: &'a str,
    function_config: &'a FunctionConfig,
    inference_cache: CacheEnabledMode,
}

async fn infer_datapoint(params: InferDatapointParams<'_>) -> Result<InferenceResponse> {
    let InferDatapointParams {
        clients,
        function_name,
        variant_name,
        evaluation_run_id,
        dataset_name,
        datapoint,
        evaluation_name,
        function_config,
        input,
        inference_cache,
    } = params;

    let dynamic_tool_params = match datapoint.tool_call_config() {
        Some(tool_params) => get_tool_params_args(tool_params, function_config).await,
        None => DynamicToolParams::default(),
    };
    let output_schema = match (datapoint.output_schema(), function_config) {
        // If the datapoint has an output schema, use it only in the case where it is not the same as the output schema of the function
        (Some(output_schema), FunctionConfig::Json(json_function_config)) => {
            if output_schema == json_function_config.output_schema.value {
                None
            } else {
                Some(output_schema)
            }
        }
        (Some(_), FunctionConfig::Chat(_)) => {
            return Err(anyhow!("Chat function does not support output schema"));
        }
        (None, _) => None,
    };
    let params = InferenceRequestParams {
        function_name: Some(function_name.to_string()),
        variant_name: Some(variant_name.to_string()),
        input: input.clone(),
        tags: HashMap::from([
            (
                "tensorzero::evaluation_run_id".to_string(),
                evaluation_run_id.to_string(),
            ),
            (
                "tensorzero::datapoint_id".to_string(),
                datapoint.id().to_string(),
            ),
            (
                "tensorzero::evaluation_name".to_string(),
                evaluation_name.to_string(),
            ),
            (
                "tensorzero::dataset_name".to_string(),
                dataset_name.to_string(),
            ),
        ]),
        dynamic_tool_params,
        output_schema: output_schema.cloned(),
        credentials: HashMap::new(),
        cache_options: get_cache_options(inference_cache),
        dryrun: Some(false),
        episode_id: None,
        model_name: None,
        stream: Some(false),
        params: InferenceParams::default(),
        include_original_response: false,
        internal: true,
        extra_body: Default::default(),
        extra_headers: Default::default(),
        observability_metadata: None,
        gateway_request: None,
        observability_span: None,
    };
    let inference_result = clients.tensorzero_client.inference(params).await?;
    match inference_result {
        InferenceOutput::NonStreaming { response, .. } => Ok(response),
        InferenceOutput::Streaming(_inference_stream) => {
            bail!("Streaming inference should never happen in evaluations")
        }
    }
}

fn write_run_info(
    writer: &mut impl Write,
    run_info: &RunInfo,
    format: &OutputFormat,
) -> Result<()> {
    match format {
        OutputFormat::Jsonl => {
            writeln!(writer, "{}", serde_json::to_string(run_info)?)?;
        }
        OutputFormat::Pretty => {
            writeln!(writer, "Run ID: {}", run_info.evaluation_run_id)?;
            writeln!(writer, "Number of datapoints: {}", run_info.num_datapoints)?;
        }
    }
    Ok(())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RunInfo {
    pub evaluation_run_id: Uuid,
    pub num_datapoints: usize,
}

pub struct ThrottledTensorZeroClient {
    pub gateway_url: Url,
    pub http_client: reqwest::Client,
    semaphore: Semaphore,
}

impl ThrottledTensorZeroClient {
    pub fn new(gateway_url: Url, http_client: reqwest::Client, semaphore: Semaphore) -> Self {
        Self {
            gateway_url,
            http_client,
            semaphore,
        }
    }

    async fn inference(&self, params: InferenceRequestParams) -> Result<InferenceOutput> {
        let _permit = self
            .semaphore
            .acquire()
            .await
            .map_err(|_| anyhow!("Failed to acquire semaphore"))?;

        // Convert params to JSON manually since Params doesn't implement Serialize
        let params_json = serde_json::json!({
            "function_name": params.function_name,
            "variant_name": params.variant_name,
            "input": params.input,
            "tags": params.tags,
            "dynamic_tool_params": params.dynamic_tool_params,
            "output_schema": params.output_schema,
            "credentials": {}, // Empty credentials for evaluations
            "cache_options": params.cache_options,
            "dryrun": params.dryrun,
            "episode_id": params.episode_id,
            "model_name": params.model_name,
            "stream": params.stream,
            "params": params.params,
            "include_original_response": params.include_original_response,
            "internal": params.internal,
            "extra_body": {},  // Simplified for evaluations
            "extra_headers": {},  // Simplified for evaluations
        });

        let response = self
            .http_client
            .post(self.gateway_url.join("/inference")?)
            .json(&params_json)
            .send()
            .await?;

        if !response.status().is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            bail!("Inference request failed: {}", error_text);
        }

        let inference_response: InferenceResponse = response.json().await?;
        // Create a dummy result to match the new InferenceOutput structure
        let dummy_result = match &inference_response {
            InferenceResponse::Chat(chat_response) => InferenceResult::Chat(ChatInferenceResult {
                inference_id: chat_response.inference_id,
                created: current_timestamp(),
                content: chat_response.content.clone(),
                usage: Usage::default(),
                model_inference_results: vec![],
                inference_params: InferenceParams::default(),
                original_response: None,
                finish_reason: None,
            }),
            InferenceResponse::Json(json_response) => {
                InferenceResult::Json(JsonInferenceResult {
                    inference_id: json_response.inference_id,
                    created: current_timestamp(),
                    output: InternalJsonInferenceOutput {
                        raw: json_response.output.raw.clone(),
                        parsed: json_response.output.parsed.clone(),
                        auxiliary_content: vec![], // Not available in response
                        json_block_index: None,
                    },
                    usage: Usage::default(),
                    model_inference_results: vec![],
                    output_schema: serde_json::Value::Null,
                    inference_params: InferenceParams::default(),
                    original_response: None,
                    finish_reason: None,
                })
            }
        };
        Ok(InferenceOutput::NonStreaming {
            response: inference_response,
            result: dummy_result,
            write_info: None,
        })
    }

    async fn feedback(
        &self,
        metric_name: String,
        value: Value,
        inference_id: Uuid,
        tags: HashMap<String, String>,
    ) -> Result<()> {
        let feedback_params = serde_json::json!({
            "metric_name": metric_name,
            "value": value,
            "inference_id": inference_id,
            "dryrun": false,
            "internal": true,
            "tags": tags
        });

        let response = self
            .http_client
            .post(self.gateway_url.join("/feedback")?)
            .json(&feedback_params)
            .send()
            .await?;

        if !response.status().is_success() {
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            bail!("Feedback request failed: {}", error_text);
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use tensorzero_internal::evaluations::ExactMatchConfig;

    use super::*;

    #[test]
    fn test_format_cutoff_failures() {
        let failures = vec![
            ("evaluator1".to_string(), 0.5, 0.4),
            ("evaluator2".to_string(), 0.6, 0.3),
        ];
        let formatted = format_cutoff_failures(&failures);
        assert_eq!(
            formatted,
            "evaluator1 (cutoff: 0.50, got: 0.40)\nevaluator2 (cutoff: 0.60, got: 0.30)"
        );
    }

    #[test]
    fn test_check_evaluator_cutoffs() {
        let stats = {
            let mut stats = HashMap::new();
            stats.insert(
                "evaluator1".to_string(),
                stats::EvaluatorStats {
                    mean: 0.4,
                    stderr: 0.1,
                },
            );
            stats.insert(
                "evaluator2".to_string(),
                stats::EvaluatorStats {
                    mean: 0.3,
                    stderr: 0.1,
                },
            );
            stats.insert(
                "evaluator3".to_string(),
                stats::EvaluatorStats {
                    mean: 0.1,
                    stderr: 0.05,
                },
            );
            stats
        };
        let evaluators = {
            let mut evaluators = HashMap::new();
            evaluators.insert(
                "evaluator1".to_string(),
                EvaluatorConfig::ExactMatch(ExactMatchConfig { cutoff: Some(0.5) }),
            );
            evaluators.insert(
                "evaluator2".to_string(),
                EvaluatorConfig::ExactMatch(ExactMatchConfig { cutoff: Some(0.6) }),
            );
            evaluators.insert(
                "evaluator3".to_string(),
                EvaluatorConfig::ExactMatch(ExactMatchConfig { cutoff: None }),
            );
            evaluators
        };
        let failures = check_evaluator_cutoffs(&stats, &evaluators).unwrap();
        assert_eq!(failures.len(), 2);

        // Check that both expected failures are present, regardless of order
        assert!(failures.contains(&("evaluator1".to_string(), 0.5, 0.4)));
        assert!(failures.contains(&("evaluator2".to_string(), 0.6, 0.3)));

        // Check that evaluator3 is not in the failures list since it has no cutoff
        assert!(!failures.iter().any(|(name, _, _)| name == "evaluator3"));
    }
}
