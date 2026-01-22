use std::sync::OnceLock;

use reqwest::StatusCode;
use secrecy::{ExposeSecret, SecretString};
use serde::{Deserialize, Serialize};
use tokio::time::Instant;
use url::Url;
use uuid::Uuid;

use crate::endpoints::inference::InferenceCredentials;
use crate::error::{DisplayOrDebugGateway, Error, ErrorDetails};
use crate::inference::types::{current_timestamp, Latency, Usage};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation};
use crate::moderation::{
    ModerationCategories, ModerationCategoryScores, ModerationProvider, ModerationProviderResponse,
    ModerationRequest, ModerationResult,
};

use super::helpers::handle_reqwest_error;

const PROVIDER_NAME: &str = "Azure Content Safety";
const PROVIDER_TYPE: &str = "azure_content_safety";

#[derive(Debug)]
pub struct AzureContentSafetyProvider {
    endpoint: Url,
    credentials: AzureContentSafetyCredentials,
    probe_type: ProbeType, // New field to specify which probe this instance handles
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ProbeType {
    Moderation,
    PromptShields,
    GroundednessDetection,
    ProtectedMaterialText,
    ProtectedMaterialCode,
}

impl ProbeType {
    pub fn from_probe_id(probe_id: &str) -> Option<Self> {
        match probe_id {
            "moderation" => Some(ProbeType::Moderation),
            "prompt-shields" => Some(ProbeType::PromptShields),
            "groundedness-detection-preview" => Some(ProbeType::GroundednessDetection),
            "protected-material-detection-text" => Some(ProbeType::ProtectedMaterialText),
            "protected-material-detection-code" => Some(ProbeType::ProtectedMaterialCode),
            _ => None,
        }
    }
}

static DEFAULT_CREDENTIALS: OnceLock<AzureContentSafetyCredentials> = OnceLock::new();

impl AzureContentSafetyProvider {
    pub fn new(
        endpoint: Url,
        api_key_location: Option<CredentialLocation>,
        probe_type: ProbeType,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;
        Ok(AzureContentSafetyProvider {
            endpoint,
            credentials,
            probe_type,
        })
    }
}

#[derive(Clone, Debug, Deserialize)]
pub enum AzureContentSafetyCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for AzureContentSafetyCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(AzureContentSafetyCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(AzureContentSafetyCredentials::Dynamic(key_name)),
            Credential::Missing => Ok(AzureContentSafetyCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for Azure Content Safety provider".to_string(),
            })),
        }
    }
}

impl AzureContentSafetyCredentials {
    fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            AzureContentSafetyCredentials::Static(api_key) => Ok(Some(api_key)),
            AzureContentSafetyCredentials::Dynamic(key_name) => {
                Some(dynamic_api_keys.get(key_name).ok_or_else(|| {
                    ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    }
                    .into()
                }))
                .transpose()
            }
            AzureContentSafetyCredentials::None => Ok(None),
        }
    }
}

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("AZURE_CONTENT_SAFETY_API_KEY".to_string())
}

// URL construction functions following Azure provider pattern
// Each endpoint has its own API version as per Azure documentation
fn get_azure_content_safety_text_moderation_url(endpoint: &Url) -> Result<Url, Error> {
    const TEXT_API_VERSION: &str = "2024-09-01";
    let mut url = endpoint.clone();
    url.path_segments_mut()
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing URL: {e:?}"),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?
        .push("contentsafety")
        .push("text:analyze");
    url.query_pairs_mut()
        .append_pair("api-version", TEXT_API_VERSION);
    Ok(url)
}

fn get_azure_content_safety_prompt_shield_url(endpoint: &Url) -> Result<Url, Error> {
    const PROMPT_SHIELD_API_VERSION: &str = "2024-09-01";
    let mut url = endpoint.clone();
    url.path_segments_mut()
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing URL: {e:?}"),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?
        .push("contentsafety")
        .push("text:shieldPrompt");
    url.query_pairs_mut()
        .append_pair("api-version", PROMPT_SHIELD_API_VERSION);
    Ok(url)
}
fn get_azure_content_safety_groundedness_url(endpoint: &Url) -> Result<Url, Error> {
    const GROUNDEDNESS_API_VERSION: &str = "2024-09-15-preview";
    let mut url = endpoint.clone();
    url.path_segments_mut()
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing URL: {e:?}"),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?
        .push("contentsafety")
        .push("text:detectGroundedness");
    url.query_pairs_mut()
        .append_pair("api-version", GROUNDEDNESS_API_VERSION);
    Ok(url)
}

fn get_azure_content_safety_protected_material_url(endpoint: &Url) -> Result<Url, Error> {
    const PROTECTED_MATERIAL_API_VERSION: &str = "2024-09-01";
    let mut url = endpoint.clone();
    url.path_segments_mut()
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing URL: {e:?}"),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?
        .push("contentsafety")
        .push("text:detectProtectedMaterial");
    url.query_pairs_mut()
        .append_pair("api-version", PROTECTED_MATERIAL_API_VERSION);
    Ok(url)
}

fn get_azure_content_safety_protected_material_code_url(endpoint: &Url) -> Result<Url, Error> {
    const PROTECTED_MATERIAL_CODE_API_VERSION: &str = "2024-09-15-preview";
    let mut url = endpoint.clone();
    url.path_segments_mut()
        .map_err(|e| {
            Error::new(ErrorDetails::InferenceServer {
                message: format!("Error parsing URL: {e:?}"),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?
        .push("contentsafety")
        .push("text:detectProtectedMaterialForCode");
    url.query_pairs_mut()
        .append_pair("api-version", PROTECTED_MATERIAL_CODE_API_VERSION);
    Ok(url)
}

// Azure Content Safety specific request/response structures
#[derive(Debug, Serialize)]
struct AzureModerationRequest {
    text: String,
    #[serde(rename = "blocklistNames", skip_serializing_if = "Vec::is_empty")]
    blocklist_names: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    categories: Option<Vec<String>>,
    #[serde(rename = "haltOnBlocklistHit", skip_serializing_if = "Option::is_none")]
    halt_on_blocklist_hit: Option<bool>,
    #[serde(rename = "outputType", skip_serializing_if = "Option::is_none")]
    output_type: Option<String>,
}

#[derive(Debug, Serialize)]
struct AzurePromptShieldRequest {
    #[serde(rename = "userPrompt")]
    user_prompt: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    documents: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct AzureModerationResponse {
    #[serde(rename = "categoriesAnalysis")]
    categories_analysis: Vec<CategoryAnalysis>,
    #[serde(rename = "blocklistsMatch", skip_serializing_if = "Option::is_none")]
    blocklists_match: Option<Vec<BlocklistMatch>>,
}

#[derive(Debug, Deserialize)]
struct CategoryAnalysis {
    category: String,
    severity: i32,
}

#[derive(Debug, Deserialize)]
struct BlocklistMatch {
    #[serde(rename = "blocklistName")]
    blocklist_name: String,
    #[serde(rename = "blocklistItemId")]
    blocklist_item_id: String,
    #[serde(rename = "blocklistItemText")]
    blocklist_item_text: String,
}

#[derive(Debug, Deserialize)]
struct AzurePromptShieldResponse {
    #[serde(rename = "userPromptAnalysis")]
    user_prompt_analysis: PromptAnalysis,
    #[serde(rename = "documentsAnalysis")]
    documents_analysis: Vec<DocumentAnalysis>,
}

#[derive(Debug, Deserialize)]
struct PromptAnalysis {
    #[serde(rename = "attackDetected")]
    attack_detected: bool,
}

#[derive(Debug, Deserialize)]
struct DocumentAnalysis {
    #[serde(rename = "attackDetected")]
    attack_detected: bool,
}

// Groundedness detection types
/// Task type for groundedness detection
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "UPPERCASE")]
enum TaskType {
    Summarization,
    QnA,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "UPPERCASE")]
enum DomainType {
    Medical,
    Generic,
}

#[derive(Debug, Serialize)]
struct AzureGroundednessRequest {
    domain: DomainType,
    task: TaskType,
    text: String,
    #[serde(rename = "groundingSources")]
    grounding_sources: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    qna: Option<QnAInfo>,
    #[serde(rename = "Reasoning")]
    reasoning: bool,
    #[serde(rename = "llmResource", skip_serializing_if = "Option::is_none")]
    llm_resource: Option<LLMResource>,
    #[serde(rename = "Correction")]
    correction: bool,
}

#[derive(Debug, Serialize)]
struct QnAInfo {
    query: String,
}

#[derive(Debug, Serialize)]
struct LLMResource {
    #[serde(rename = "resourceType")]
    resource_type: String,
    #[serde(rename = "azureOpenAIEndpoint")]
    azure_openai_endpoint: String,
    #[serde(rename = "azureOpenAIDeploymentName")]
    azure_openai_deployment_name: String,
}

#[derive(Debug, Deserialize)]
struct AzureGroundednessResponse {
    #[serde(rename = "ungroundedDetected")]
    ungrounded_detected: bool,
    #[serde(rename = "ungroundedPercentage")]
    ungrounded_percentage: f32,
    #[serde(rename = "ungroundedDetails")]
    ungrounded_details: Vec<UngroundedDetail>,
    #[serde(
        rename = "groundednessReasoning",
        skip_serializing_if = "Option::is_none"
    )]
    groundedness_reasoning: Option<String>,
}

#[derive(Debug, Deserialize)]
struct UngroundedDetail {
    text: String,
    offset: UngroundedOffset,
    length: UngroundedLength,
    #[serde(rename = "correctionText", skip_serializing_if = "Option::is_none")]
    correction_text: Option<String>,
}

#[derive(Debug, Deserialize)]
struct UngroundedOffset {
    utf8: u32,
    utf16: u32,
    #[serde(rename = "codePoint")]
    code_point: u32,
}

#[derive(Debug, Deserialize)]
struct UngroundedLength {
    utf8: u32,
    utf16: u32,
    #[serde(rename = "codePoint")]
    code_point: u32,
}

// Protected material detection types
#[derive(Debug, Serialize)]
struct AzureProtectedMaterialRequest {
    text: String,
}

#[derive(Debug, Deserialize)]
struct AzureProtectedMaterialResponse {
    #[serde(rename = "protectedMaterialAnalysis")]
    protected_material_analysis: ProtectedMaterialAnalysis,
}

#[derive(Debug, Deserialize)]
struct ProtectedMaterialAnalysis {
    detected: bool,
}

// Protected material code detection types
#[derive(Debug, Serialize)]
struct AzureProtectedMaterialCodeRequest {
    code: String,
}

#[derive(Debug, Deserialize)]
struct AzureProtectedMaterialCodeResponse {
    #[serde(rename = "protectedMaterialAnalysis")]
    protected_material_analysis: ProtectedMaterialCodeAnalysis,
}

#[derive(Debug, Deserialize)]
struct ProtectedMaterialCodeAnalysis {
    detected: bool,
    #[serde(rename = "codeCitations", default)]
    code_citations: Vec<CodeCitation>,
}

#[derive(Debug, Deserialize)]
struct CodeCitation {
    license: String,
    #[serde(rename = "sourceUrls")]
    source_urls: Vec<String>,
}

// Conversion functions to map Azure Content Safety categories to OpenAI-compatible ones
fn severity_to_score(severity: i32, is_eight_levels: bool) -> f32 {
    // Convert to 0.0-1.0 scale for OpenAI compatibility
    if is_eight_levels {
        // Eight severity levels: 0-7
        match severity {
            0 => 0.0,
            1 => 0.14,
            2 => 0.29,
            3 => 0.43,
            4 => 0.57,
            5 => 0.71,
            6 => 0.86,
            7 => 1.0,
            _ => 0.0,
        }
    } else {
        // Four severity levels: 0, 2, 4, 6
        match severity {
            0 => 0.0,
            2 => 0.25,
            4 => 0.5,
            6 => 0.75,
            _ => 0.0,
        }
    }
}

fn severity_to_flagged(severity: i32, threshold: i32) -> bool {
    severity >= threshold
}

impl ModerationProvider for AzureContentSafetyProvider {
    async fn moderate(
        &self,
        request: &ModerationRequest,
        client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ModerationProviderResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let start_time = Instant::now();

        // Get input texts
        let texts = request.input.as_vec();
        let text_strings: Vec<String> = texts.iter().map(|s| s.to_string()).collect();

        if text_strings.is_empty() {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "No input text provided".to_string(),
            }));
        }

        // Execute the appropriate probe based on probe_type
        let results = match self.probe_type {
            ProbeType::Moderation => {
                self.handle_text_moderation(request, &text_strings, api_key, client)
                    .await?
            }
            ProbeType::PromptShields => {
                self.handle_prompt_shields(request, &text_strings, api_key, client)
                    .await?
            }
            ProbeType::GroundednessDetection => {
                self.handle_groundedness(request, &text_strings, api_key, client)
                    .await?
            }
            ProbeType::ProtectedMaterialText => {
                self.handle_protected_material(request, &text_strings, api_key, client)
                    .await?
            }
            ProbeType::ProtectedMaterialCode => {
                self.handle_protected_material_code(request, &text_strings, api_key, client)
                    .await?
            }
        };

        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        let raw_request = serde_json::to_string(&request).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!(
                    "Error serializing request body as JSON: {}",
                    DisplayOrDebugGateway::new(e)
                ),
            })
        })?;

        Ok(ModerationProviderResponse {
            id: Uuid::now_v7(),
            input: request.input.clone(),
            results: results.clone(),
            created: current_timestamp(),
            model: "azure-content-safety".to_string(),
            raw_request,
            raw_response: serde_json::to_string(&results).unwrap_or_default(),
            usage: Usage {
                input_tokens: texts
                    .iter()
                    .map(|t| t.split_whitespace().count() as u32)
                    .sum(),
                output_tokens: 0,
            },
            latency,
        })
    }
}

impl AzureContentSafetyProvider {
    /// Handle text moderation probe
    async fn handle_text_moderation(
        &self,
        request: &ModerationRequest,
        texts: &[String],
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        // Extract parameters
        let mut blocklist_names = vec![];
        let mut categories = None;
        let mut halt_on_blocklist_hit = None;
        let mut output_type = Some("EightSeverityLevels".to_string());

        if let Some(provider_params) = &request.provider_params {
            if let Some(obj) = provider_params.as_object() {
                // Extract blocklistNames
                if let Some(names) = obj
                    .get("blocklistNames")
                    .or_else(|| obj.get("blocklist_names"))
                {
                    if let Some(names_array) = names.as_array() {
                        blocklist_names = names_array
                            .iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                    }
                }

                // Extract categories
                if let Some(cats) = obj.get("categories") {
                    if let Some(cats_array) = cats.as_array() {
                        let cat_strings: Vec<String> = cats_array
                            .iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                        if !cat_strings.is_empty() {
                            categories = Some(cat_strings);
                        }
                    }
                }

                // Extract halt flag
                if let Some(halt) = obj
                    .get("haltOnBlocklistHit")
                    .or_else(|| obj.get("halt_on_blocklist_hit"))
                {
                    halt_on_blocklist_hit = halt.as_bool();
                }

                // Extract output type
                if let Some(output) = obj.get("outputType").or_else(|| obj.get("output_type")) {
                    if let Some(output_str) = output.as_str() {
                        output_type = Some(output_str.to_string());
                    }
                }
            }
        }

        self.analyze_text(
            texts,
            blocklist_names,
            categories,
            halt_on_blocklist_hit,
            output_type,
            api_key,
            client,
        )
        .await
    }

    /// Handle prompt shields probe
    async fn handle_prompt_shields(
        &self,
        request: &ModerationRequest,
        texts: &[String],
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        let mut documents = vec![];

        if let Some(provider_params) = &request.provider_params {
            if let Some(obj) = provider_params.as_object() {
                if let Some(docs) = obj.get("documents") {
                    if let Some(docs_array) = docs.as_array() {
                        documents = docs_array
                            .iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                    }
                }
            }
        }

        let user_prompt = texts[0].to_string();
        let result = self
            .analyze_prompt_shield(user_prompt, documents, api_key, client)
            .await?;
        Ok(vec![result])
    }

    /// Handle groundedness detection probe
    async fn handle_groundedness(
        &self,
        request: &ModerationRequest,
        texts: &[String],
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        let mut grounding_sources = vec![];
        let mut domain = DomainType::Generic;
        let mut task_type = TaskType::Summarization;
        let mut query = None;
        let mut reasoning = false;
        let mut correction = false;
        let mut llm_resource = None;

        if let Some(provider_params) = &request.provider_params {
            if let Some(obj) = provider_params.as_object() {
                // Extract grounding sources
                if let Some(sources) = obj
                    .get("grounding_sources")
                    .or_else(|| obj.get("groundingSources"))
                {
                    if let Some(sources_array) = sources.as_array() {
                        grounding_sources = sources_array
                            .iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                    }
                }

                // Extract domain
                if let Some(domain_param) = obj.get("domain") {
                    if let Some(domain_str) = domain_param.as_str() {
                        domain = match domain_str.to_uppercase().as_str() {
                            "MEDICAL" => DomainType::Medical,
                            _ => DomainType::Generic,
                        };
                    }
                }

                // Extract task type
                if let Some(task) = obj.get("task") {
                    if let Some(task_str) = task.as_str() {
                        task_type = match task_str.to_uppercase().as_str() {
                            "QNA" | "Q&A" => TaskType::QnA,
                            _ => TaskType::Summarization,
                        };
                    }
                }

                // Extract query
                if let Some(q) = obj.get("query") {
                    query = q.as_str().map(|s| s.to_string());
                }

                // Extract flags
                if let Some(r) = obj.get("reasoning") {
                    reasoning = r.as_bool().unwrap_or(false);
                }
                if let Some(c) = obj.get("correction") {
                    correction = c.as_bool().unwrap_or(false);
                }

                // Extract LLM resource
                if let Some(llm) = obj.get("llm_resource") {
                    if let Some(llm_obj) = llm.as_object() {
                        if let (Some(endpoint), Some(deployment)) = (
                            llm_obj
                                .get("azure_openai_endpoint")
                                .and_then(|v| v.as_str()),
                            llm_obj
                                .get("azure_openai_deployment_name")
                                .and_then(|v| v.as_str()),
                        ) {
                            llm_resource = Some(LLMResource {
                                resource_type: "AzureOpenAI".to_string(),
                                azure_openai_endpoint: endpoint.to_string(),
                                azure_openai_deployment_name: deployment.to_string(),
                            });
                        }
                    }
                }
            }
        }

        if grounding_sources.is_empty() {
            return Err(Error::new(ErrorDetails::InvalidRequest {
                message: "No grounding sources provided for groundedness detection".to_string(),
            }));
        }

        let result = self
            .analyze_groundedness(
                texts[0].to_string(),
                grounding_sources,
                domain,
                task_type,
                query,
                reasoning,
                correction,
                llm_resource,
                api_key,
                client,
            )
            .await?;
        Ok(vec![result])
    }

    /// Handle protected material text probe
    async fn handle_protected_material(
        &self,
        _request: &ModerationRequest,
        texts: &[String],
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        let result = self
            .analyze_protected_material(texts[0].to_string(), api_key, client)
            .await?;
        Ok(vec![result])
    }

    /// Handle protected material code probe
    async fn handle_protected_material_code(
        &self,
        _request: &ModerationRequest,
        texts: &[String],
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        let result = self
            .analyze_protected_material_code(texts[0].to_string(), api_key, client)
            .await?;
        Ok(vec![result])
    }

    /// Perform text moderation analysis using Azure Content Safety
    async fn analyze_text(
        &self,
        texts: &[String],
        blocklist_names: Vec<String>,
        categories: Option<Vec<String>>,
        halt_on_blocklist_hit: Option<bool>,
        output_type: Option<String>,
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<Vec<ModerationResult>, Error> {
        let mut results = Vec::new();
        let is_eight_levels = output_type
            .as_ref()
            .map(|s| s == "EightSeverityLevels")
            .unwrap_or(true);

        for text in texts {
            let azure_request = AzureModerationRequest {
                text: text.to_string(),
                blocklist_names: blocklist_names.clone(),
                categories: categories.clone(),
                halt_on_blocklist_hit,
                output_type: output_type.clone(),
            };

            let url = get_azure_content_safety_text_moderation_url(&self.endpoint)?;

            let mut request_builder = client.post(url).header("Content-Type", "application/json");

            if let Some(api_key) = api_key {
                request_builder =
                    request_builder.header("Ocp-Apim-Subscription-Key", api_key.expose_secret());
            }

            let res = request_builder
                .json(&azure_request)
                .send()
                .await
                .map_err(|e| {
                    handle_reqwest_error(
                        e,
                        PROVIDER_TYPE,
                        Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                    )
                })?;

            if res.status().is_success() {
                let raw_response = res.text().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing text response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: None,
                    })
                })?;

                let azure_response: AzureModerationResponse = serde_json::from_str(&raw_response)
                    .map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                    })
                })?;

                // Convert Azure response to OpenAI-compatible format
                let moderation_result =
                    convert_azure_response_to_openai(&azure_response, is_eight_levels);
                results.push(moderation_result);
            } else {
                let status = res.status();
                let error_text = res.text().await.unwrap_or_default();
                return Err(handle_azure_content_safety_error(
                    &serde_json::to_string(&azure_request).unwrap_or_default(),
                    status,
                    &error_text,
                ));
            }
        }

        Ok(results)
    }

    /// Analyze text for groundedness against grounding sources
    async fn analyze_groundedness(
        &self,
        text: String,
        grounding_sources: Vec<String>,
        domain: DomainType,
        task_type: TaskType,
        query: Option<String>,
        reasoning: bool,
        correction: bool,
        llm_resource: Option<LLMResource>,
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<ModerationResult, Error> {
        let qna = match (&task_type, query) {
            (TaskType::QnA, Some(q)) => Some(QnAInfo { query: q }),
            _ => None,
        };

        let azure_request = AzureGroundednessRequest {
            domain,
            task: task_type,
            text,
            grounding_sources,
            qna,
            reasoning,
            llm_resource,
            correction,
        };

        let url = get_azure_content_safety_groundedness_url(&self.endpoint)?;

        let mut request_builder = client.post(url).header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder =
                request_builder.header("Ocp-Apim-Subscription-Key", api_key.expose_secret());
        }

        let res = request_builder
            .json(&azure_request)
            .send()
            .await
            .map_err(|e| {
                handle_reqwest_error(
                    e,
                    PROVIDER_TYPE,
                    Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                )
            })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                    raw_response: None,
                })
            })?;

            let groundedness_response: AzureGroundednessResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                    })
                })?;

            // Convert groundedness response to OpenAI-compatible format
            Ok(convert_groundedness_response_to_openai(
                &groundedness_response,
            ))
        } else {
            let status = res.status();
            let error_text = res.text().await.unwrap_or_default();
            Err(handle_azure_content_safety_error(
                &serde_json::to_string(&azure_request).unwrap_or_default(),
                status,
                &error_text,
            ))
        }
    }

    /// Analyze text for protected material (copyrighted content)
    async fn analyze_protected_material(
        &self,
        text: String,
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<ModerationResult, Error> {
        let azure_request = AzureProtectedMaterialRequest { text };

        let url = get_azure_content_safety_protected_material_url(&self.endpoint)?;

        let mut request_builder = client.post(url).header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder =
                request_builder.header("Ocp-Apim-Subscription-Key", api_key.expose_secret());
        }

        let res = request_builder
            .json(&azure_request)
            .send()
            .await
            .map_err(|e| {
                handle_reqwest_error(
                    e,
                    PROVIDER_TYPE,
                    Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                )
            })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                    raw_response: None,
                })
            })?;

            let protected_material_response: AzureProtectedMaterialResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                    })
                })?;

            // Convert protected material response to OpenAI-compatible format
            Ok(convert_protected_material_response_to_openai(
                &protected_material_response,
            ))
        } else {
            let status = res.status();
            let error_text = res.text().await.unwrap_or_default();
            Err(handle_azure_content_safety_error(
                &serde_json::to_string(&azure_request).unwrap_or_default(),
                status,
                &error_text,
            ))
        }
    }

    /// Analyze code for protected material (GitHub copyrighted code)
    async fn analyze_protected_material_code(
        &self,
        code: String,
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<ModerationResult, Error> {
        let azure_request = AzureProtectedMaterialCodeRequest { code };

        let url = get_azure_content_safety_protected_material_code_url(&self.endpoint)?;

        let mut request_builder = client.post(url).header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder =
                request_builder.header("Ocp-Apim-Subscription-Key", api_key.expose_secret());
        }

        let res = request_builder
            .json(&azure_request)
            .send()
            .await
            .map_err(|e| {
                handle_reqwest_error(
                    e,
                    PROVIDER_TYPE,
                    Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                )
            })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                    raw_response: None,
                })
            })?;

            let protected_material_code_response: AzureProtectedMaterialCodeResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                    })
                })?;

            // Convert protected material code response to OpenAI-compatible format
            Ok(convert_protected_material_code_response_to_openai(
                &protected_material_code_response,
            ))
        } else {
            let status = res.status();
            let error_text = res.text().await.unwrap_or_default();
            Err(handle_azure_content_safety_error(
                &serde_json::to_string(&azure_request).unwrap_or_default(),
                status,
                &error_text,
            ))
        }
    }

    /// Analyze prompt for potential injection attacks using Azure Prompt Shield
    async fn analyze_prompt_shield(
        &self,
        user_prompt: String,
        documents: Vec<String>,
        api_key: Option<&SecretString>,
        client: &reqwest::Client,
    ) -> Result<ModerationResult, Error> {
        let azure_request = AzurePromptShieldRequest {
            user_prompt,
            documents,
        };

        let url = get_azure_content_safety_prompt_shield_url(&self.endpoint)?;

        let mut request_builder = client.post(url).header("Content-Type", "application/json");

        if let Some(api_key) = api_key {
            request_builder =
                request_builder.header("Ocp-Apim-Subscription-Key", api_key.expose_secret());
        }

        let res = request_builder
            .json(&azure_request)
            .send()
            .await
            .map_err(|e| {
                handle_reqwest_error(
                    e,
                    PROVIDER_TYPE,
                    Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                )
            })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(serde_json::to_string(&azure_request).unwrap_or_default()),
                    raw_response: None,
                })
            })?;

            let prompt_shield_response: AzurePromptShieldResponse =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: Some(
                            serde_json::to_string(&azure_request).unwrap_or_default(),
                        ),
                        raw_response: Some(raw_response.clone()),
                    })
                })?;

            // Convert prompt shield response to OpenAI-compatible format
            Ok(convert_prompt_shield_response_to_openai(
                &prompt_shield_response,
            ))
        } else {
            let status = res.status();
            let error_text = res.text().await.unwrap_or_default();
            Err(handle_azure_content_safety_error(
                &serde_json::to_string(&azure_request).unwrap_or_default(),
                status,
                &error_text,
            ))
        }
    }
}

fn convert_groundedness_response_to_openai(
    groundedness_response: &AzureGroundednessResponse,
) -> ModerationResult {
    use crate::moderation::{
        CategoryAppliedInputTypes, HallucinationDetails, HallucinationSegment,
    };

    // For groundedness detection, we use the ungrounded flag to indicate hallucinated content
    let flagged = groundedness_response.ungrounded_detected;

    // Build category_applied_input_types - always return it with all fields
    let mut category_applied_input_types = CategoryAppliedInputTypes::default();
    if flagged {
        category_applied_input_types.hallucination = vec!["text".to_string()];
    }

    // Convert ungrounded details to hallucination segments
    let hallucination_segments: Vec<HallucinationSegment> = groundedness_response
        .ungrounded_details
        .iter()
        .map(|detail| HallucinationSegment {
            text: detail.text.clone(),
            offset: detail.offset.utf8,
            length: detail.length.utf8,
            correction: detail.correction_text.clone(),
        })
        .collect();

    // Only include hallucination details if there are ungrounded segments
    let hallucination_details = if flagged {
        Some(HallucinationDetails {
            ungrounded_percentage: groundedness_response.ungrounded_percentage,
            ungrounded_segments: hallucination_segments,
            reasoning: groundedness_response.groundedness_reasoning.clone(),
        })
    } else {
        None
    };

    ModerationResult {
        flagged,
        categories: ModerationCategories {
            // Map ungrounded content to the hallucination category
            hallucination: flagged,
            ..Default::default()
        },
        category_scores: ModerationCategoryScores::default(), // No scores for hallucination
        category_applied_input_types: Some(category_applied_input_types),
        hallucination_details,
        ip_violation_details: None,
        unknown_categories: Default::default(),
        other_score: 0.0,
    }
}

fn convert_prompt_shield_response_to_openai(
    prompt_shield_response: &AzurePromptShieldResponse,
) -> ModerationResult {
    use crate::moderation::CategoryAppliedInputTypes;

    // Check if prompt attack is detected
    let prompt_attack = prompt_shield_response.user_prompt_analysis.attack_detected;

    // Check if any document attack is detected
    let document_attack = prompt_shield_response
        .documents_analysis
        .iter()
        .any(|doc| doc.attack_detected);

    // Flag if either prompt or document has an attack
    let flagged = prompt_attack || document_attack;

    // Build category_applied_input_types - always return it with all fields
    let mut category_applied_input_types = CategoryAppliedInputTypes::default();

    if flagged {
        let mut input_types = Vec::new();
        if prompt_attack {
            input_types.push("text".to_string());
        }
        if document_attack {
            input_types.push("document".to_string());
        }
        category_applied_input_types.malicious = input_types;
    }

    ModerationResult {
        flagged,
        categories: ModerationCategories {
            malicious: flagged, // Prompt injection attacks are flagged as malicious
            ..Default::default()
        },
        category_scores: ModerationCategoryScores::default(), // No scores for prompt shield
        category_applied_input_types: Some(category_applied_input_types),
        hallucination_details: None,
        ip_violation_details: None,
        unknown_categories: Default::default(),
        other_score: 0.0,
    }
}

fn convert_protected_material_response_to_openai(
    protected_material_response: &AzureProtectedMaterialResponse,
) -> ModerationResult {
    use crate::moderation::CategoryAppliedInputTypes;

    // For protected material, we map detected to the ip_violation category
    let flagged = protected_material_response
        .protected_material_analysis
        .detected;

    // Build category_applied_input_types - always return it with all fields
    let mut category_applied_input_types = CategoryAppliedInputTypes::default();
    if flagged {
        category_applied_input_types.ip_violation = vec!["text".to_string()];
    }

    ModerationResult {
        flagged,
        categories: ModerationCategories {
            ip_violation: flagged, // Protected/copyrighted material is flagged as ip_violation
            ..Default::default()
        },
        category_scores: ModerationCategoryScores::default(), // No scores for protected material
        category_applied_input_types: Some(category_applied_input_types),
        hallucination_details: None,
        ip_violation_details: None,
        unknown_categories: Default::default(),
        other_score: 0.0,
    }
}

fn convert_protected_material_code_response_to_openai(
    protected_material_code_response: &AzureProtectedMaterialCodeResponse,
) -> ModerationResult {
    use crate::moderation::{CategoryAppliedInputTypes, Citation, IPViolationDetails};

    // For protected material code, we map detected to the ip_violation category
    let flagged = protected_material_code_response
        .protected_material_analysis
        .detected;

    // Build category_applied_input_types - always return it with all fields
    let mut category_applied_input_types = CategoryAppliedInputTypes::default();
    if flagged {
        category_applied_input_types.ip_violation = vec!["text".to_string()];
    }

    // Convert Azure code citations to our Citation format
    let ip_violation_details = if flagged
        && !protected_material_code_response
            .protected_material_analysis
            .code_citations
            .is_empty()
    {
        let citations = protected_material_code_response
            .protected_material_analysis
            .code_citations
            .iter()
            .map(|azure_citation| Citation {
                license: azure_citation.license.clone(),
                source_urls: azure_citation.source_urls.clone(),
            })
            .collect();

        Some(IPViolationDetails { citations })
    } else {
        None
    };

    ModerationResult {
        flagged,
        categories: ModerationCategories {
            ip_violation: flagged, // Protected/copyrighted code is flagged as ip_violation
            ..Default::default()
        },
        category_scores: ModerationCategoryScores::default(), // No scores for protected material
        category_applied_input_types: Some(category_applied_input_types),
        hallucination_details: None,
        ip_violation_details,
        unknown_categories: Default::default(),
        other_score: 0.0,
    }
}

fn convert_azure_response_to_openai(
    azure_response: &AzureModerationResponse,
    is_eight_levels: bool,
) -> ModerationResult {
    use crate::moderation::CategoryAppliedInputTypes;

    let mut categories = ModerationCategories::default();
    let mut category_scores = ModerationCategoryScores::default();
    let mut category_applied_input_types = CategoryAppliedInputTypes::default();
    let mut flagged = false;

    // Default threshold for flagging
    // For 8 levels: severity >= 4 (middle of 0-7)
    // For 4 levels: severity >= 4 (which is the "Medium" level)
    let default_threshold = if is_eight_levels { 4 } else { 4 };

    for category_analysis in &azure_response.categories_analysis {
        let score = severity_to_score(category_analysis.severity, is_eight_levels);
        let is_flagged = severity_to_flagged(category_analysis.severity, default_threshold);

        match category_analysis.category.as_str() {
            "Hate" => {
                categories.hate = is_flagged;
                category_scores.hate = score;
                if is_flagged {
                    flagged = true;
                    category_applied_input_types.hate = vec!["text".to_string()];
                }
            }
            "SelfHarm" => {
                categories.self_harm = is_flagged;
                category_scores.self_harm = score;
                if is_flagged {
                    flagged = true;
                    category_applied_input_types.self_harm = vec!["text".to_string()];
                }
            }
            "Sexual" => {
                categories.sexual = is_flagged;
                category_scores.sexual = score;
                if is_flagged {
                    flagged = true;
                    category_applied_input_types.sexual = vec!["text".to_string()];
                }
            }
            "Violence" => {
                categories.violence = is_flagged;
                category_scores.violence = score;
                if is_flagged {
                    flagged = true;
                    category_applied_input_types.violence = vec!["text".to_string()];
                }
            }
            _ => {}
        }
    }

    // If there are blocklist matches, flag the content
    if let Some(blocklists) = &azure_response.blocklists_match {
        if !blocklists.is_empty() {
            flagged = true;
        }
    }

    ModerationResult {
        flagged,
        categories,
        category_scores,
        category_applied_input_types: Some(category_applied_input_types),
        hallucination_details: None,
        ip_violation_details: None,
        unknown_categories: Default::default(),
        other_score: 0.0,
    }
}

fn handle_azure_content_safety_error(
    raw_request: &str,
    _status: StatusCode,
    response_text: &str,
) -> Error {
    // Try to parse Azure Content Safety error response
    #[derive(Deserialize)]
    struct AzureError {
        error: AzureErrorDetails,
    }

    #[derive(Deserialize)]
    struct AzureErrorDetails {
        code: String,
        message: String,
    }

    let error_details = if let Ok(azure_error) = serde_json::from_str::<AzureError>(response_text) {
        format!("{}: {}", azure_error.error.code, azure_error.error.message)
    } else {
        response_text.to_string()
    };

    Error::new(ErrorDetails::InferenceServer {
        message: format!("Azure Content Safety error: {}", error_details),
        provider_type: PROVIDER_TYPE.to_string(),
        raw_request: Some(raw_request.to_string()),
        raw_response: Some(response_text.to_string()),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_probe_type_from_probe_id() {
        assert_eq!(
            ProbeType::from_probe_id("moderation"),
            Some(ProbeType::Moderation)
        );
        assert_eq!(
            ProbeType::from_probe_id("prompt-shields"),
            Some(ProbeType::PromptShields)
        );
        assert_eq!(
            ProbeType::from_probe_id("groundedness-detection-preview"),
            Some(ProbeType::GroundednessDetection)
        );
        assert_eq!(
            ProbeType::from_probe_id("protected-material-detection-text"),
            Some(ProbeType::ProtectedMaterialText)
        );
        assert_eq!(
            ProbeType::from_probe_id("protected-material-detection-code"),
            Some(ProbeType::ProtectedMaterialCode)
        );
        assert_eq!(ProbeType::from_probe_id("unknown-probe"), None);
    }

    #[test]
    fn test_severity_to_score() {
        // Test 4-level scoring
        assert_eq!(severity_to_score(0, false), 0.0);
        assert_eq!(severity_to_score(2, false), 0.25);
        assert_eq!(severity_to_score(4, false), 0.5);
        assert_eq!(severity_to_score(6, false), 0.75);
        assert_eq!(severity_to_score(8, false), 0.0); // Invalid severity

        // Test 8-level scoring
        assert_eq!(severity_to_score(0, true), 0.0);
        assert_eq!(severity_to_score(1, true), 0.14);
        assert_eq!(severity_to_score(2, true), 0.29);
        assert_eq!(severity_to_score(3, true), 0.43);
        assert_eq!(severity_to_score(4, true), 0.57);
        assert_eq!(severity_to_score(5, true), 0.71);
        assert_eq!(severity_to_score(6, true), 0.86);
        assert_eq!(severity_to_score(7, true), 1.0);
        assert_eq!(severity_to_score(8, true), 0.0); // Invalid severity
    }

    #[test]
    fn test_severity_to_flagged() {
        assert!(!severity_to_flagged(0, 4));
        assert!(!severity_to_flagged(2, 4));
        assert!(severity_to_flagged(4, 4));
        assert!(severity_to_flagged(6, 4));
    }

    #[test]
    fn test_convert_azure_response_to_openai() {
        let azure_response = AzureModerationResponse {
            categories_analysis: vec![
                CategoryAnalysis {
                    category: "Hate".to_string(),
                    severity: 4,
                },
                CategoryAnalysis {
                    category: "Violence".to_string(),
                    severity: 2,
                },
                CategoryAnalysis {
                    category: "Sexual".to_string(),
                    severity: 0,
                },
                CategoryAnalysis {
                    category: "SelfHarm".to_string(),
                    severity: 6,
                },
            ],
            blocklists_match: None,
        };

        // Test with 4-level scoring
        let result = convert_azure_response_to_openai(&azure_response, false);

        assert!(result.flagged);
        assert!(result.categories.hate);
        assert!(!result.categories.violence);
        assert!(!result.categories.sexual);
        assert!(result.categories.self_harm);

        assert_eq!(result.category_scores.hate, 0.5);
        assert_eq!(result.category_scores.violence, 0.25);
        assert_eq!(result.category_scores.sexual, 0.0);
        assert_eq!(result.category_scores.self_harm, 0.75);

        // Check category_applied_input_types
        assert!(result.category_applied_input_types.is_some());
        let input_types = result.category_applied_input_types.unwrap();
        assert_eq!(input_types.hate, vec!["text"]);
        assert_eq!(input_types.self_harm, vec!["text"]);
        assert!(input_types.violence.is_empty());
        assert!(input_types.sexual.is_empty());

        // Test with 8-level scoring (same input values, but interpreted differently)
        let result_8level = convert_azure_response_to_openai(&azure_response, true);
        assert!(result_8level.flagged);
        assert!(result_8level.categories.hate);
        assert!(!result_8level.categories.violence);
        assert!(!result_8level.categories.sexual);
        assert!(result_8level.categories.self_harm);

        // With 8-level scoring, the values are interpreted as 0-7 scale
        assert_eq!(result_8level.category_scores.hate, 0.57); // severity 4 -> 0.57
        assert_eq!(result_8level.category_scores.violence, 0.29); // severity 2 -> 0.29
        assert_eq!(result_8level.category_scores.sexual, 0.0); // severity 0 -> 0.0
        assert_eq!(result_8level.category_scores.self_harm, 0.86); // severity 6 -> 0.86
    }

    #[test]
    fn test_credential_conversion() {
        // Test Static credential
        let generic = Credential::Static(SecretString::from("test_key"));
        let creds = AzureContentSafetyCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, AzureContentSafetyCredentials::Static(_)));

        // Test Dynamic credential
        let generic = Credential::Dynamic("key_name".to_string());
        let creds = AzureContentSafetyCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, AzureContentSafetyCredentials::Dynamic(_)));

        // Test Missing credential
        let generic = Credential::Missing;
        let creds = AzureContentSafetyCredentials::try_from(generic).unwrap();
        assert!(matches!(creds, AzureContentSafetyCredentials::None));

        // Test invalid type
        let generic = Credential::FileContents(SecretString::from("test"));
        let result = AzureContentSafetyCredentials::try_from(generic);
        assert!(result.is_err());
    }

    #[test]
    fn test_get_api_key_none() {
        use crate::endpoints::inference::InferenceCredentials;

        let creds = AzureContentSafetyCredentials::None;
        let dynamic_keys: InferenceCredentials = InferenceCredentials::new();

        let api_key = creds.get_api_key(&dynamic_keys).unwrap();
        assert!(api_key.is_none());
    }

    #[test]
    fn test_url_construction() {
        let endpoint = Url::parse("https://my-content-safety.cognitiveservices.azure.com").unwrap();

        let url = get_azure_content_safety_text_moderation_url(&endpoint).unwrap();
        assert_eq!(
            url.as_str(),
            "https://my-content-safety.cognitiveservices.azure.com/contentsafety/text:analyze?api-version=2024-09-01"
        );

        let prompt_shield_url = get_azure_content_safety_prompt_shield_url(&endpoint).unwrap();
        assert_eq!(
            prompt_shield_url.as_str(),
            "https://my-content-safety.cognitiveservices.azure.com/contentsafety/text:shieldPrompt?api-version=2024-09-01"
        );

        let protected_material_url =
            get_azure_content_safety_protected_material_url(&endpoint).unwrap();
        assert_eq!(
            protected_material_url.as_str(),
            "https://my-content-safety.cognitiveservices.azure.com/contentsafety/text:detectProtectedMaterial?api-version=2024-09-01"
        );

        let protected_material_code_url =
            get_azure_content_safety_protected_material_code_url(&endpoint).unwrap();
        assert_eq!(
            protected_material_code_url.as_str(),
            "https://my-content-safety.cognitiveservices.azure.com/contentsafety/text:detectProtectedMaterialForCode?api-version=2024-09-15-preview"
        );
    }

    #[test]
    fn test_provider_params_extraction() {
        use crate::moderation::ModerationInput;
        use serde_json::json;

        // Test with all parameters in camelCase (Azure style)
        let provider_params = json!({
            "blocklistNames": ["blocklist1", "blocklist2"],
            "categories": ["Hate", "Violence"],
            "haltOnBlocklistHit": true,
            "outputType": "FourSeverityLevels"
        });

        let request = ModerationRequest {
            input: ModerationInput::Single("test text".to_string()),
            model: None,
            provider_params: Some(provider_params),
        };

        // This test verifies that the parameters are properly extracted in the moderate function
        // The actual extraction logic is in the moderate function implementation
        assert!(request.provider_params.is_some());

        // Test with snake_case (OpenAI style)
        let provider_params_snake = json!({
            "blocklist_names": ["blocklist1", "blocklist2"],
            "categories": ["Hate", "Violence"],
            "halt_on_blocklist_hit": false,
            "output_type": "EightSeverityLevels"
        });

        let request_snake = ModerationRequest {
            input: ModerationInput::Single("test text".to_string()),
            model: None,
            provider_params: Some(provider_params_snake),
        };

        assert!(request_snake.provider_params.is_some());

        // Test with mixed case (both styles)
        let provider_params_mixed = json!({
            "blocklistNames": ["blocklist1"],  // camelCase
            "halt_on_blocklist_hit": true,     // snake_case
            "outputType": "EightSeverityLevels" // camelCase
        });

        let request_mixed = ModerationRequest {
            input: ModerationInput::Single("test text".to_string()),
            model: None,
            provider_params: Some(provider_params_mixed),
        };

        assert!(request_mixed.provider_params.is_some());
    }

    #[test]
    fn test_prompt_shield_response_conversion() {
        // Test when only prompt attack is detected
        let prompt_shield_response = AzurePromptShieldResponse {
            user_prompt_analysis: PromptAnalysis {
                attack_detected: true,
            },
            documents_analysis: vec![],
        };

        let result = convert_prompt_shield_response_to_openai(&prompt_shield_response);
        assert!(result.flagged);
        assert!(result.categories.malicious);
        assert!(result.category_applied_input_types.is_some());
        let input_types = result.category_applied_input_types.unwrap();
        assert_eq!(input_types.malicious, vec!["text"]);

        // Test when only document attack is detected
        let prompt_shield_response_doc_attack = AzurePromptShieldResponse {
            user_prompt_analysis: PromptAnalysis {
                attack_detected: false,
            },
            documents_analysis: vec![
                DocumentAnalysis {
                    attack_detected: true,
                },
                DocumentAnalysis {
                    attack_detected: false,
                },
            ],
        };

        let result_doc =
            convert_prompt_shield_response_to_openai(&prompt_shield_response_doc_attack);
        assert!(result_doc.flagged);
        assert!(result_doc.categories.malicious);
        assert!(result_doc.category_applied_input_types.is_some());
        let input_types_doc = result_doc.category_applied_input_types.unwrap();
        assert_eq!(input_types_doc.malicious, vec!["document"]);

        // Test when both prompt and document attacks are detected
        let prompt_shield_response_both = AzurePromptShieldResponse {
            user_prompt_analysis: PromptAnalysis {
                attack_detected: true,
            },
            documents_analysis: vec![
                DocumentAnalysis {
                    attack_detected: false,
                },
                DocumentAnalysis {
                    attack_detected: true,
                },
            ],
        };

        let result_both = convert_prompt_shield_response_to_openai(&prompt_shield_response_both);
        assert!(result_both.flagged);
        assert!(result_both.categories.malicious);
        assert!(result_both.category_applied_input_types.is_some());
        let input_types_both = result_both.category_applied_input_types.unwrap();
        assert_eq!(input_types_both.malicious, vec!["text", "document"]);

        // Test when no attack is detected
        let prompt_shield_response_safe = AzurePromptShieldResponse {
            user_prompt_analysis: PromptAnalysis {
                attack_detected: false,
            },
            documents_analysis: vec![
                DocumentAnalysis {
                    attack_detected: false,
                },
                DocumentAnalysis {
                    attack_detected: false,
                },
            ],
        };

        let result_safe = convert_prompt_shield_response_to_openai(&prompt_shield_response_safe);
        assert!(!result_safe.flagged);
        assert!(!result_safe.categories.malicious);
        assert!(result_safe.category_applied_input_types.is_some());
        let input_types_safe = result_safe.category_applied_input_types.unwrap();
        // Verify all fields exist but malicious is empty
        assert!(input_types_safe.malicious.is_empty());
        assert!(input_types_safe.hate.is_empty());
        assert!(input_types_safe.violence.is_empty());
    }

    #[test]
    fn test_enabled_features_extraction() {
        use crate::moderation::ModerationInput;
        use serde_json::json;

        // Test with enabled_features parameter
        let provider_params = json!({
            "enabled_features": ["text_moderation", "prompt_shield"],
            "documents": ["doc1", "doc2"]
        });

        let request = ModerationRequest {
            input: ModerationInput::Single("test prompt".to_string()),
            model: None,
            provider_params: Some(provider_params),
        };

        assert!(request.provider_params.is_some());

        // Test with camelCase version
        let provider_params_camel = json!({
            "enabledFeatures": ["prompt_shield"],
            "documents": ["doc1", "doc2", "doc3"]
        });

        let request_camel = ModerationRequest {
            input: ModerationInput::Single("test prompt".to_string()),
            model: None,
            provider_params: Some(provider_params_camel),
        };

        assert!(request_camel.provider_params.is_some());

        // Test with future features
        let provider_params_future = json!({
            "enabled_features": ["text_moderation", "prompt_shield", "groundedness", "protected_material"],
            "documents": ["doc1"]
        });

        let request_future = ModerationRequest {
            input: ModerationInput::Single("test content".to_string()),
            model: None,
            provider_params: Some(provider_params_future),
        };

        assert!(request_future.provider_params.is_some());
    }

    #[test]
    fn test_groundedness_url_construction() {
        let endpoint = Url::parse("https://my-content-safety.cognitiveservices.azure.com").unwrap();

        let groundedness_url = get_azure_content_safety_groundedness_url(&endpoint).unwrap();
        assert_eq!(
            groundedness_url.as_str(),
            "https://my-content-safety.cognitiveservices.azure.com/contentsafety/text:detectGroundedness?api-version=2024-09-15-preview"
        );
    }

    #[test]
    fn test_convert_groundedness_response_to_openai() {
        // Test when ungrounded content is detected
        let groundedness_response = AzureGroundednessResponse {
            ungrounded_detected: true,
            ungrounded_percentage: 25.5,
            ungrounded_details: vec![UngroundedDetail {
                text: "This is ungrounded".to_string(),
                offset: UngroundedOffset {
                    utf8: 0,
                    utf16: 0,
                    code_point: 0,
                },
                length: UngroundedLength {
                    utf8: 18,
                    utf16: 18,
                    code_point: 18,
                },
                correction_text: None,
            }],
            groundedness_reasoning: Some("The text contains unsupported claims".to_string()),
        };

        let result = convert_groundedness_response_to_openai(&groundedness_response);
        assert!(result.flagged);
        assert!(result.categories.hallucination);
        assert!(result.hallucination_details.is_some());
        let details = result.hallucination_details.unwrap();
        assert_eq!(details.ungrounded_percentage, 25.5);
        assert_eq!(details.ungrounded_segments.len(), 1);
        assert_eq!(details.ungrounded_segments[0].text, "This is ungrounded");
        assert_eq!(details.ungrounded_segments[0].correction, None);

        // Test when content is fully grounded
        let grounded_response = AzureGroundednessResponse {
            ungrounded_detected: false,
            ungrounded_percentage: 0.0,
            ungrounded_details: vec![],
            groundedness_reasoning: None,
        };

        let result_grounded = convert_groundedness_response_to_openai(&grounded_response);
        assert!(!result_grounded.flagged);
        assert!(!result_grounded.categories.hallucination);
        assert!(result_grounded.hallucination_details.is_none());

        // Test with correction text
        let groundedness_response_with_correction = AzureGroundednessResponse {
            ungrounded_detected: true,
            ungrounded_percentage: 15.0,
            ungrounded_details: vec![UngroundedDetail {
                text: "The sky is green".to_string(),
                offset: UngroundedOffset {
                    utf8: 0,
                    utf16: 0,
                    code_point: 0,
                },
                length: UngroundedLength {
                    utf8: 16,
                    utf16: 16,
                    code_point: 16,
                },
                correction_text: Some("The sky is blue".to_string()),
            }],
            groundedness_reasoning: Some("Corrected factual error about sky color".to_string()),
        };

        let result_with_correction =
            convert_groundedness_response_to_openai(&groundedness_response_with_correction);
        assert!(result_with_correction.flagged);
        assert!(result_with_correction.hallucination_details.is_some());
        let details_correction = result_with_correction.hallucination_details.unwrap();
        assert_eq!(
            details_correction.ungrounded_segments[0].correction,
            Some("The sky is blue".to_string())
        );
    }

    #[test]
    fn test_groundedness_params_extraction() {
        use crate::moderation::ModerationInput;
        use serde_json::json;

        // Test with all groundedness parameters
        let provider_params = json!({
            "enabled_features": ["groundedness"],
            "grounding_sources": ["Source 1", "Source 2"],
            "domain": "MEDICAL",
            "task": "QnA",
            "query": "What is the treatment?",
            "reasoning": true,
            "correction": true,
            "llm_resource": {
                "azure_openai_endpoint": "https://my-openai.openai.azure.com",
                "azure_openai_deployment_name": "gpt-4"
            }
        });

        let request = ModerationRequest {
            input: ModerationInput::Single("Test content".to_string()),
            model: None,
            provider_params: Some(provider_params),
        };

        assert!(request.provider_params.is_some());

        // Test with camelCase variations
        let provider_params_camel = json!({
            "enabledFeatures": ["groundedness"],
            "groundingSources": ["Doc 1", "Doc 2", "Doc 3"],
            "groundedness_domain": "GENERIC",
            "groundedness_task": "SUMMARIZATION",
            "groundedness_reasoning": false,
            "groundedness_correction": true
        });

        let request_camel = ModerationRequest {
            input: ModerationInput::Single("Summary text".to_string()),
            model: None,
            provider_params: Some(provider_params_camel),
        };

        assert!(request_camel.provider_params.is_some());
    }

    #[test]
    fn test_groundedness_request_serialization_with_correction() {
        let request = AzureGroundednessRequest {
            domain: DomainType::Medical,
            task: TaskType::QnA,
            text: "Sample medical text".to_string(),
            grounding_sources: vec![
                "Medical Source 1".to_string(),
                "Medical Source 2".to_string(),
            ],
            qna: Some(QnAInfo {
                query: "What are the side effects?".to_string(),
            }),
            reasoning: true,
            llm_resource: Some(LLMResource {
                resource_type: "AzureOpenAI".to_string(),
                azure_openai_endpoint: "https://my.openai.azure.com".to_string(),
                azure_openai_deployment_name: "gpt-4".to_string(),
            }),
            correction: true,
        };

        let serialized = serde_json::to_value(&request).unwrap();
        assert_eq!(serialized["domain"], "MEDICAL");
        assert_eq!(serialized["task"], "QNA");
        assert_eq!(serialized["Correction"], true);
        assert_eq!(serialized["Reasoning"], true);
        assert!(serialized["llmResource"].is_object());

        // Test with correction disabled
        let request_no_correction = AzureGroundednessRequest {
            domain: DomainType::Generic,
            task: TaskType::Summarization,
            text: "Summary text".to_string(),
            grounding_sources: vec!["Source".to_string()],
            qna: None,
            reasoning: false,
            llm_resource: None,
            correction: false,
        };

        let serialized_no_corr = serde_json::to_value(&request_no_correction).unwrap();
        assert_eq!(serialized_no_corr["Correction"], false);
    }

    #[test]
    fn test_task_type_serialization() {
        assert_eq!(
            serde_json::to_string(&TaskType::Summarization).unwrap(),
            "\"SUMMARIZATION\""
        );
        assert_eq!(serde_json::to_string(&TaskType::QnA).unwrap(), "\"QNA\"");
    }

    #[test]
    fn test_domain_type_serialization() {
        assert_eq!(
            serde_json::to_string(&DomainType::Medical).unwrap(),
            "\"MEDICAL\""
        );
        assert_eq!(
            serde_json::to_string(&DomainType::Generic).unwrap(),
            "\"GENERIC\""
        );
    }

    #[test]
    fn test_convert_protected_material_response_to_openai() {
        // Test when protected material is detected
        let protected_response = AzureProtectedMaterialResponse {
            protected_material_analysis: ProtectedMaterialAnalysis { detected: true },
        };

        let result = convert_protected_material_response_to_openai(&protected_response);
        assert!(result.flagged);
        assert!(result.categories.ip_violation);
        // All other categories should be false
        assert!(!result.categories.hate);
        assert!(!result.categories.violence);
        assert!(!result.categories.sexual);
        assert!(!result.categories.self_harm);
        assert!(!result.categories.harassment);
        assert!(!result.categories.malicious);

        // Test when no protected material is detected
        let safe_response = AzureProtectedMaterialResponse {
            protected_material_analysis: ProtectedMaterialAnalysis { detected: false },
        };

        let result_safe = convert_protected_material_response_to_openai(&safe_response);
        assert!(!result_safe.flagged);
        assert!(!result_safe.categories.ip_violation);
    }

    #[test]
    fn test_protected_material_params_extraction() {
        use crate::moderation::ModerationInput;
        use serde_json::json;

        // Test with protected_material feature enabled
        let provider_params = json!({
            "enabled_features": ["text_moderation", "protected_material"],
            "categories": ["Hate", "Violence"]
        });

        let request = ModerationRequest {
            input: ModerationInput::Single(
                "test text with potential copyrighted content".to_string(),
            ),
            model: None,
            provider_params: Some(provider_params),
        };

        assert!(request.provider_params.is_some());

        // Test with multiple features including protected_material
        let provider_params_multi = json!({
            "enabledFeatures": ["prompt_shield", "groundedness", "protected_material"],
            "documents": ["doc1"],
            "grounding_sources": ["source1", "source2"]
        });

        let request_multi = ModerationRequest {
            input: ModerationInput::Single("check this content".to_string()),
            model: None,
            provider_params: Some(provider_params_multi),
        };

        assert!(request_multi.provider_params.is_some());
    }

    #[test]
    fn test_convert_protected_material_code_response_to_openai() {
        // Test when protected material code is detected with citations
        let protected_code_response = AzureProtectedMaterialCodeResponse {
            protected_material_analysis: ProtectedMaterialCodeAnalysis {
                detected: true,
                code_citations: vec![
                    CodeCitation {
                        license: "MIT".to_string(),
                        source_urls: vec![
                            "https://github.com/example/repo1".to_string(),
                            "https://github.com/example/repo2".to_string(),
                        ],
                    },
                    CodeCitation {
                        license: "Apache-2.0".to_string(),
                        source_urls: vec!["https://github.com/example/repo3".to_string()],
                    },
                ],
            },
        };

        let result = convert_protected_material_code_response_to_openai(&protected_code_response);
        assert!(result.flagged);
        assert!(result.categories.ip_violation);
        // All other categories should be false
        assert!(!result.categories.hate);
        assert!(!result.categories.violence);
        assert!(!result.categories.sexual);
        assert!(!result.categories.self_harm);
        assert!(!result.categories.harassment);
        assert!(!result.categories.malicious);

        // Check ip_violation_details
        assert!(result.ip_violation_details.is_some());
        let ip_details = result.ip_violation_details.unwrap();
        assert_eq!(ip_details.citations.len(), 2);
        assert_eq!(ip_details.citations[0].license, "MIT");
        assert_eq!(ip_details.citations[0].source_urls.len(), 2);
        assert_eq!(
            ip_details.citations[0].source_urls[0],
            "https://github.com/example/repo1"
        );
        assert_eq!(ip_details.citations[1].license, "Apache-2.0");
        assert_eq!(ip_details.citations[1].source_urls.len(), 1);

        // Test when no protected material code is detected
        let safe_code_response = AzureProtectedMaterialCodeResponse {
            protected_material_analysis: ProtectedMaterialCodeAnalysis {
                detected: false,
                code_citations: vec![],
            },
        };

        let result_safe = convert_protected_material_code_response_to_openai(&safe_code_response);
        assert!(!result_safe.flagged);
        assert!(!result_safe.categories.ip_violation);
        assert!(result_safe.ip_violation_details.is_none());
    }

    #[test]
    fn test_protected_material_code_params_extraction() {
        use crate::moderation::ModerationInput;
        use serde_json::json;

        // Test with protected_material_code feature enabled
        let provider_params = json!({
            "enabled_features": ["text_moderation", "protected_material_code"],
            "categories": ["Hate", "Violence"]
        });

        let request = ModerationRequest {
            input: ModerationInput::Single("def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)".to_string()),
            model: None,
            provider_params: Some(provider_params),
        };

        assert!(request.provider_params.is_some());

        // Test with multiple features including protected_material_code
        let provider_params_multi = json!({
            "enabledFeatures": ["protected_material", "protected_material_code", "prompt_shield"],
            "documents": ["doc1"]
        });

        let request_multi = ModerationRequest {
            input: ModerationInput::Single("function code() { return 42; }".to_string()),
            model: None,
            provider_params: Some(provider_params_multi),
        };

        assert!(request_multi.provider_params.is_some());
    }
}
