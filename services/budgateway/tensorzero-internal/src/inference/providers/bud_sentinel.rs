use std::collections::HashMap;
use std::sync::OnceLock;
use std::time::Duration;

use secrecy::{ExposeSecret, SecretString};
use serde::Deserialize;
use serde_json::json;
use tokio::sync::OnceCell;
use tonic::metadata::MetadataValue;
use tonic::transport::{Channel, Endpoint};
use tonic::{Code, Request, Status};
use url::Url;
use uuid::Uuid;

use crate::endpoints::inference::InferenceCredentials;
use crate::error::{Error, ErrorDetails};
use crate::inference::types::{current_timestamp, Latency, Usage};
use crate::model::{build_creds_caching_default, Credential, CredentialLocation};
use crate::moderation::{
    ModerationCategories, ModerationCategoryScores, ModerationProvider, ModerationProviderResponse,
    ModerationRequest, ModerationResult,
};

pub mod generated {
    tonic::include_proto!("bud");
}

use generated::bud_service_client::BudServiceClient;
use generated::{
    DeleteProfileRequest, GetProfileRequest, ModerationRequest as BudModerationRequest,
    ModerationResult as BudModerationResult, Profile, ProfileRequest,
};

const PROVIDER_NAME: &str = "Bud Sentinel";
const PROVIDER_TYPE: &str = "bud_sentinel";

#[derive(Debug)]
pub struct BudSentinelProvider {
    endpoint: Url,
    credentials: BudSentinelCredentials,
    default_profile_id: Option<String>,
    default_severity_threshold: Option<f32>,
    channel: OnceCell<Channel>,
}

#[derive(Clone, Debug, Deserialize)]
pub enum BudSentinelCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl BudSentinelProvider {
    pub fn new(
        endpoint: Url,
        api_key_location: Option<CredentialLocation>,
        default_profile_id: Option<String>,
        default_severity_threshold: Option<f32>,
    ) -> Result<Self, Error> {
        let credentials = build_creds_caching_default(
            api_key_location,
            default_api_key_location(),
            PROVIDER_TYPE,
            &DEFAULT_CREDENTIALS,
        )?;

        Ok(Self {
            endpoint,
            credentials,
            default_profile_id,
            default_severity_threshold,
            channel: OnceCell::new(),
        })
    }

    async fn client(&self) -> Result<BudServiceClient<Channel>, Error> {
        let channel = self
            .channel
            .get_or_try_init(|| async {
                let mut endpoint =
                    Endpoint::from_shared(self.endpoint.to_string()).map_err(|e| {
                        Error::new(ErrorDetails::Config {
                            message: format!(
                                "Invalid Bud Sentinel endpoint URL '{}': {e}",
                                self.endpoint
                            ),
                        })
                    })?;

                endpoint = endpoint
                    .tcp_keepalive(Some(Duration::from_secs(60)))
                    .http2_keep_alive_interval(Duration::from_secs(30))
                    .keep_alive_timeout(Duration::from_secs(10))
                    .keep_alive_while_idle(true);

                endpoint.connect().await.map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!("Failed to connect to Bud Sentinel endpoint: {e}"),
                        provider_type: PROVIDER_TYPE.to_string(),
                        raw_request: None,
                        raw_response: None,
                    })
                })
            })
            .await?;

        Ok(BudServiceClient::new(channel.clone()))
    }

    fn apply_request_metadata<T>(
        &self,
        request: &mut Request<T>,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<(), Error> {
        if let Some(bearer_token) = dynamic_api_keys.get("authorization") {
            let value = MetadataValue::try_from(format!(
                "Bearer {}",
                bearer_token.expose_secret()
            ))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Invalid Bud Sentinel bearer token metadata value: {e}"),
                })
            })?;
            request.metadata_mut().insert("authorization", value);
        }

        if let Some(api_key) = self.credentials.get_api_key(dynamic_api_keys)? {
            let value = MetadataValue::try_from(api_key.expose_secret()).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Invalid Bud Sentinel API key metadata value: {e}"),
                })
            })?;
            request.metadata_mut().insert("x-api-token", value);
        }

        request.metadata_mut().insert(
            "x-bud-sentinel-client",
            MetadataValue::from_static("tensorzero-gateway"),
        );

        Ok(())
    }

    fn map_status_error(operation: &str, status: Status) -> Error {
        let raw_response = json!({
            "code": status.code() as i32,
            "code_name": status.code().to_string(),
            "message": status.message(),
        })
        .to_string();

        Error::new(ErrorDetails::InferenceServer {
            message: format!("Bud Sentinel {operation} failed: {status}"),
            provider_type: PROVIDER_TYPE.to_string(),
            raw_request: None,
            raw_response: Some(raw_response),
        })
    }

    pub async fn get_profile(
        &self,
        profile_id: &str,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<Option<Profile>, Error> {
        let mut client = self.client().await?;
        let mut request = Request::new(GetProfileRequest {
            id: profile_id.to_string(),
        });
        self.apply_request_metadata(&mut request, dynamic_api_keys)?;
        match client.get_profile(request).await {
            Ok(response) => Ok(response.into_inner().profile),
            Err(status) if status.code() == Code::NotFound => Ok(None),
            Err(status) => Err(Self::map_status_error("get_profile", status)),
        }
    }

    pub async fn create_profile(
        &self,
        profile: Profile,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<Profile, Error> {
        let mut client = self.client().await?;
        let mut request = Request::new(ProfileRequest {
            profile: Some(profile),
        });
        self.apply_request_metadata(&mut request, dynamic_api_keys)?;
        client
            .create_profile(request)
            .await
            .map_err(|status| Self::map_status_error("create_profile", status))?
            .into_inner()
            .profile
            .ok_or_else(|| {
                Error::new(ErrorDetails::InferenceServer {
                    message: "Bud Sentinel create_profile returned no profile".to_string(),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            })
    }

    pub async fn update_profile(
        &self,
        profile: Profile,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<Profile, Error> {
        let mut client = self.client().await?;
        let mut request = Request::new(ProfileRequest {
            profile: Some(profile),
        });
        self.apply_request_metadata(&mut request, dynamic_api_keys)?;
        client
            .update_profile(request)
            .await
            .map_err(|status| Self::map_status_error("update_profile", status))?
            .into_inner()
            .profile
            .ok_or_else(|| {
                Error::new(ErrorDetails::InferenceServer {
                    message: "Bud Sentinel update_profile returned no profile".to_string(),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            })
    }

    pub async fn delete_profile(
        &self,
        profile_id: &str,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<(), Error> {
        let mut client = self.client().await?;
        let mut request = Request::new(DeleteProfileRequest {
            id: profile_id.to_string(),
        });
        self.apply_request_metadata(&mut request, dynamic_api_keys)?;
        match client.delete_profile(request).await {
            Ok(_) => {}
            Err(status) if status.code() == Code::NotFound => {}
            Err(status) => return Err(Self::map_status_error("delete_profile", status)),
        }
        Ok(())
    }

    pub async fn ensure_profile(
        &self,
        profile: Profile,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<Profile, Error> {
        let profile_id = profile.id.clone();
        if profile_id.is_empty() {
            return Err(Error::new(ErrorDetails::Config {
                message: "Bud Sentinel profile requires an 'id' field".to_string(),
            }));
        }

        match self.get_profile(&profile_id, dynamic_api_keys).await? {
            Some(_) => self.update_profile(profile, dynamic_api_keys).await,
            None => self.create_profile(profile, dynamic_api_keys).await,
        }
    }
}

impl TryFrom<Credential> for BudSentinelCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(BudSentinelCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(BudSentinelCredentials::Dynamic(key_name)),
            Credential::Missing => Ok(BudSentinelCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for Bud Sentinel provider".to_string(),
            })),
        }
    }
}

impl BudSentinelCredentials {
    fn get_api_key<'a>(
        &'a self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            BudSentinelCredentials::Static(api_key) => Ok(Some(api_key)),
            BudSentinelCredentials::Dynamic(key_name) => {
                Some(dynamic_api_keys.get(key_name).ok_or_else(|| {
                    ErrorDetails::ApiKeyMissing {
                        provider_name: PROVIDER_NAME.to_string(),
                    }
                    .into()
                }))
                .transpose()
            }
            BudSentinelCredentials::None => Ok(None),
        }
    }
}

static DEFAULT_CREDENTIALS: OnceLock<BudSentinelCredentials> = OnceLock::new();

fn default_api_key_location() -> CredentialLocation {
    CredentialLocation::Env("BUD_SENTINEL_API_KEY".to_string())
}

#[derive(Debug, Default, Deserialize)]
struct BudSentinelProviderParams {
    profile_id: Option<String>,
    severity_threshold: Option<f32>,
}

impl BudSentinelProviderParams {
    fn from_value(value: Option<&serde_json::Value>) -> Result<Self, Error> {
        if let Some(v) = value {
            serde_json::from_value(v.clone()).map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Invalid Bud Sentinel provider params: {e}"),
                })
            })
        } else {
            Ok(Self::default())
        }
    }
}

fn map_categories(categories: &HashMap<String, bool>) -> ModerationCategories {
    let mut mapped = ModerationCategories::default();
    for (key, value) in categories {
        let v = *value;
        match key.as_str() {
            "hate" => mapped.hate = v,
            "hate/threatening" => mapped.hate_threatening = v,
            "harassment" => mapped.harassment = v,
            "harassment/threatening" => mapped.harassment_threatening = v,
            "illicit" => mapped.illicit = v,
            "illicit/violent" => mapped.illicit_violent = v,
            "illegal" => mapped.illegal = v,
            "regulated-advice" => mapped.regulated_advice = v,
            "self-harm" => mapped.self_harm = v,
            "self-harm/intent" => mapped.self_harm_intent = v,
            "self-harm/instructions" => mapped.self_harm_instructions = v,
            "sexual" => mapped.sexual = v,
            "sexual/minors" => mapped.sexual_minors = v,
            "violence" => mapped.violence = v,
            "violence/graphic" => mapped.violence_graphic = v,
            "profanity" => mapped.profanity = v,
            "insult" => mapped.insult = v,
            "toxicity" => mapped.toxicity = v,
            "malicious" => mapped.malicious = v,
            "pii" => mapped.pii = v,
            "secrets" => mapped.secrets = v,
            "ip-violation" => mapped.ip_violation = v,
            "hallucination" => mapped.hallucination = v,
            _ => {}
        }
    }
    mapped
}

fn map_scores(scores: &HashMap<String, f64>) -> ModerationCategoryScores {
    let mut mapped = ModerationCategoryScores::default();
    for (key, value) in scores {
        let v = *value as f32;
        match key.as_str() {
            "hate" => mapped.hate = v,
            "hate/threatening" => mapped.hate_threatening = v,
            "harassment" => mapped.harassment = v,
            "harassment/threatening" => mapped.harassment_threatening = v,
            "illicit" => mapped.illicit = v,
            "illicit/violent" => mapped.illicit_violent = v,
            "illegal" => mapped.illegal = v,
            "regulated-advice" => mapped.regulated_advice = v,
            "self-harm" => mapped.self_harm = v,
            "self-harm/intent" => mapped.self_harm_intent = v,
            "self-harm/instructions" => mapped.self_harm_instructions = v,
            "sexual" => mapped.sexual = v,
            "sexual/minors" => mapped.sexual_minors = v,
            "violence" => mapped.violence = v,
            "violence/graphic" => mapped.violence_graphic = v,
            "profanity" => mapped.profanity = v,
            "insult" => mapped.insult = v,
            "toxicity" => mapped.toxicity = v,
            "malicious" => mapped.malicious = v,
            "pii" => mapped.pii = v,
            "secrets" => mapped.secrets = v,
            _ => {}
        }
    }
    mapped
}

fn map_result(result: &BudModerationResult) -> ModerationResult {
    let categories = map_categories(&result.categories);
    let scores = map_scores(&result.category_scores);

    ModerationResult {
        flagged: result.flagged,
        categories,
        category_scores: scores,
        category_applied_input_types: None,
        hallucination_details: None,
        ip_violation_details: None,
    }
}

impl ModerationProvider for BudSentinelProvider {
    async fn moderate(
        &self,
        request: &ModerationRequest,
        _client: &reqwest::Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ModerationProviderResponse, Error> {
        if request.input.is_empty() {
            return Err(Error::new(ErrorDetails::Config {
                message: "Bud Sentinel moderation request requires at least one input".to_string(),
            }));
        }

        let overrides = BudSentinelProviderParams::from_value(request.provider_params.as_ref())?;
        let profile_id = overrides
            .profile_id
            .or_else(|| self.default_profile_id.clone())
            .ok_or_else(|| {
                Error::new(ErrorDetails::Config {
                    message: "Bud Sentinel provider requires a profile_id".to_string(),
                })
            })?;

        let severity_threshold = overrides
            .severity_threshold
            .or(self.default_severity_threshold);

        let mut client = self.client().await?;

        let inputs: Vec<String> = request
            .input
            .as_vec()
            .into_iter()
            .map(|s| s.to_string())
            .collect();

        let mut grpc_request = Request::new(BudModerationRequest {
            profile_id: profile_id.clone(),
            inputs: inputs.clone(),
            conversations: Vec::new(),
            severity_threshold,
        });

        self.apply_request_metadata(&mut grpc_request, dynamic_api_keys)?;
        grpc_request.set_timeout(Duration::from_secs(30));

        let start_time = tokio::time::Instant::now();
        let response = client
            .moderate(grpc_request)
            .await
            .map_err(|status| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!("Bud Sentinel moderation failed: {status}"),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: None,
                    raw_response: None,
                })
            })?
            .into_inner();
        let latency = start_time.elapsed();

        let results: Vec<ModerationResult> =
            response.results.iter().map(map_result).collect::<Vec<_>>();

        let provider_response = ModerationProviderResponse {
            id: Uuid::now_v7(),
            input: request.input.clone(),
            results,
            created: current_timestamp() as u64,
            model: if response.model.is_empty() {
                profile_id.clone()
            } else {
                response.model
            },
            raw_request: json!({
                "profile_id": profile_id,
                "inputs": inputs,
                "severity_threshold": severity_threshold,
            })
            .to_string(),
            raw_response: json!({
                "results": response.results.iter().map(|r| {
                    json!({
                        "flagged": r.flagged,
                        "categories": r.categories,
                        "category_scores": r.category_scores,
                        "findings": r.findings.iter().map(|f| {
                            json!({
                                "rule_id": f.rule_id.clone(),
                                "triggered": f.triggered,
                            })
                        }).collect::<Vec<_>>(),
                    })
                }).collect::<Vec<_>>(),
            })
            .to_string(),
            usage: Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
            latency: Latency::NonStreaming {
                response_time: latency,
            },
        };

        Ok(provider_response)
    }
}
