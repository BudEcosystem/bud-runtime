use crate::endpoints::inference::InferenceCredentials;
use crate::error::{DisplayOrDebugGateway, Error, ErrorDetails};
use crate::model::{Credential, CredentialLocation};
use reqwest::StatusCode;
use crate::responses::{
    OpenAIResponse, OpenAIResponseCreateParams, ResponseInputItemsList, ResponseProvider,
    ResponseStreamEvent,
};
use futures::{Stream, StreamExt};
use reqwest::Client;
use reqwest_eventsource::{Event, RequestBuilderExt};
use secrecy::{ExposeSecret, SecretString};
use std::time::Instant;
use url::Url;

const PROVIDER_NAME: &str = "BudPrompt";
const PROVIDER_TYPE: &str = "budprompt";

#[derive(Debug)]
pub struct BudPromptProvider {
    pub api_base: Url,
    pub credentials: BudPromptCredentials,
    /// Whether prompts should stream by default (when stream is not explicitly specified in request)
    pub prompt_stream: Option<bool>,
}

impl BudPromptProvider {
    pub fn new(
        api_base: Url,
        api_key_location: Option<CredentialLocation>,
        prompt_stream: Option<bool>,
    ) -> Result<Self, Error> {
        let credentials = if let Some(location) = api_key_location {
            BudPromptCredentials::try_from(Credential::try_from((location, PROVIDER_NAME))?)
        } else {
            Ok(BudPromptCredentials::None)
        }?;

        Ok(Self {
            api_base,
            credentials,
            prompt_stream,
        })
    }
}

#[derive(Debug, Clone)]
pub enum BudPromptCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for BudPromptCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(BudPromptCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(BudPromptCredentials::Dynamic(key_name)),
            Credential::None | Credential::Missing => Ok(BudPromptCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: format!("Invalid api_key_location for {} provider", PROVIDER_NAME),
            })),
        }
    }
}

impl BudPromptCredentials {
    pub fn get_api_key<'a>(
        &self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Result<Option<&'a SecretString>, Error> {
        match self {
            BudPromptCredentials::Static(_) => {
                // For static credentials, we would need to store them differently
                // For now, return None since static keys are typically handled via headers
                Ok(None)
            }
            BudPromptCredentials::Dynamic(key_name) => Ok(dynamic_api_keys.get(key_name)),
            BudPromptCredentials::None => Ok(None),
        }
    }

    pub fn get_static_api_key(&self) -> Option<&SecretString> {
        match self {
            BudPromptCredentials::Static(api_key) => Some(api_key),
            _ => None,
        }
    }
}

// Helper function to construct responses API URL
fn get_responses_url(base_url: &Url) -> Result<Url, Error> {
    base_url.join("responses").map_err(|e| {
        Error::new(ErrorDetails::Config {
            message: format!("Failed to construct responses URL: {e}"),
        })
    })
}

// Helper function to handle API errors
fn handle_budprompt_error(
    raw_request: &str,
    status: StatusCode,
    response_body: &str,
) -> Error {
    // Always use InferenceClient to preserve the backend status code
    // No filtering - pass through all status codes as-is
    ErrorDetails::InferenceClient {
        status_code: Some(status),
        message: response_body.to_string(),
        raw_request: Some(raw_request.to_string()),
        raw_response: Some(response_body.to_string()),
        provider_type: PROVIDER_TYPE.to_string(),
    }
    .into()
}

// Helper function to convert stream errors
async fn convert_stream_error(e: reqwest_eventsource::Error) -> Error {
    Error::new(ErrorDetails::InferenceClient {
        status_code: None,
        message: format!(
            "Error in {} streaming response: {}",
            PROVIDER_NAME,
            DisplayOrDebugGateway::new(e)
        ),
        provider_type: PROVIDER_TYPE.to_string(),
        raw_request: None,
        raw_response: None,
    })
}

#[async_trait::async_trait]
impl ResponseProvider for BudPromptProvider {
    async fn create_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url = get_responses_url(&self.api_base)?;
        let _start_time = Instant::now();

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        let res = request_builder.json(&request).send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error sending request to {} Responses API: {}",
                    PROVIDER_NAME,
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIResponse = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing JSON response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: Some(serde_json::to_string(&request).unwrap_or_default()),
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            Ok(response)
        } else {
            Err(handle_budprompt_error(
                &serde_json::to_string(&request).unwrap_or_default(),
                res.status(),
                &res.text().await.unwrap_or_default(),
            ))
        }
    }

    async fn stream_response(
        &self,
        request: &OpenAIResponseCreateParams,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<
        Box<dyn Stream<Item = Result<ResponseStreamEvent, Error>> + Send + Unpin>,
        Error,
    > {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let request_url = get_responses_url(&self.api_base)?;
        let _start_time = Instant::now();

        let mut request_builder = client
            .post(request_url)
            .header("Content-Type", "application/json");

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        // Make sure stream is enabled
        let mut request_with_stream = request.clone();
        request_with_stream.stream = Some(true);

        let event_source = request_builder
            .json(&request_with_stream)
            .eventsource()
            .map_err(|e| {
                Error::new(ErrorDetails::InferenceClient {
                    status_code: None,
                    message: format!(
                        "Error creating event source for {} Responses API: {}",
                        PROVIDER_NAME,
                        DisplayOrDebugGateway::new(e)
                    ),
                    provider_type: PROVIDER_TYPE.to_string(),
                    raw_request: Some(
                        serde_json::to_string(&request_with_stream).unwrap_or_default(),
                    ),
                    raw_response: None,
                })
            })?;

        let inner_stream = async_stream::stream! {
            futures::pin_mut!(event_source);
            while let Some(ev) = event_source.next().await {
                match ev {
                    Err(e) => {
                        if matches!(e, reqwest_eventsource::Error::StreamEnded) {
                            break;
                        }
                        yield Err(convert_stream_error(e).await);
                    }
                    Ok(event) => match event {
                        Event::Open => continue,
                        Event::Message(message) => {
                            if message.data == "[DONE]" {
                                break;
                            }

                            // OpenAI responses API uses event field in SSE and data contains JSON
                            // Create ResponseStreamEvent from the message
                            let event_name = message.event;

                            // Parse the data as generic JSON
                            let data: Result<serde_json::Value, _> = serde_json::from_str(&message.data);

                            match data {
                                Ok(json_data) => {
                                    let stream_event = ResponseStreamEvent {
                                        event: event_name,
                                        data: json_data,
                                    };
                                    yield Ok(stream_event);
                                },
                                Err(e) => {
                                    yield Err(Error::new(ErrorDetails::InferenceServer {
                                        message: format!("Error parsing stream data: {e}"),
                                        raw_request: None,
                                        raw_response: Some(message.data.clone()),
                                        provider_type: PROVIDER_TYPE.to_string(),
                                    }));
                                }
                            }
                        }
                    },
                }
            }
        };

        // Use Box::pin to create a pinned box that implements Stream + Send
        let pinned_stream = Box::pin(inner_stream);

        // Convert to a type that implements Unpin
        struct UnpinStream<S>(std::pin::Pin<Box<S>>);

        impl<S: Stream> Stream for UnpinStream<S> {
            type Item = S::Item;

            fn poll_next(
                mut self: std::pin::Pin<&mut Self>,
                cx: &mut std::task::Context<'_>,
            ) -> std::task::Poll<Option<Self::Item>> {
                self.0.as_mut().poll_next(cx)
            }
        }

        // UnpinStream implements Unpin regardless of whether S does
        impl<S> Unpin for UnpinStream<S> {}

        let unpin_stream = UnpinStream(pinned_stream);

        Ok(Box::new(unpin_stream))
    }

    async fn retrieve_response(
        &self,
        response_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .join(&format!("responses/{response_id}"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response URL: {e}"),
                })
            })?;

        let mut request_builder = client.get(url);

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error retrieving response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIResponse = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing JSON response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            Ok(response)
        } else {
            Err(handle_budprompt_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
            ))
        }
    }

    async fn delete_response(
        &self,
        response_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<serde_json::Value, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .join(&format!("responses/{response_id}"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response URL: {e}"),
                })
            })?;

        let mut request_builder = client.delete(url);

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!("Error deleting response: {}", DisplayOrDebugGateway::new(e)),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: serde_json::Value =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_budprompt_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
            ))
        }
    }

    async fn cancel_response(
        &self,
        response_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<OpenAIResponse, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .join(&format!("responses/{response_id}/cancel"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response cancel URL: {e}"),
                })
            })?;

        let mut request_builder = client.post(url);

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error cancelling response: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: OpenAIResponse = serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing JSON response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: Some(raw_response.clone()),
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            Ok(response)
        } else {
            Err(handle_budprompt_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
            ))
        }
    }

    async fn list_response_input_items(
        &self,
        response_id: &str,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<ResponseInputItemsList, Error> {
        let api_key = self.credentials.get_api_key(dynamic_api_keys)?;
        let url = self
            .api_base
            .join(&format!("responses/{response_id}/input_items"))
            .map_err(|e| {
                Error::new(ErrorDetails::Config {
                    message: format!("Failed to construct response input items URL: {e}"),
                })
            })?;

        let mut request_builder = client.get(url);

        // Add authorization header if API key is available
        if let Some(api_key) = api_key {
            request_builder = request_builder.bearer_auth(api_key.expose_secret());
        } else if let Some(static_key) = self.credentials.get_static_api_key() {
            request_builder = request_builder.bearer_auth(static_key.expose_secret());
        }

        let res = request_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                status_code: e.status(),
                message: format!(
                    "Error listing response input items: {}",
                    DisplayOrDebugGateway::new(e)
                ),
                provider_type: PROVIDER_TYPE.to_string(),
                raw_request: None,
                raw_response: None,
            })
        })?;

        if res.status().is_success() {
            let raw_response = res.text().await.map_err(|e| {
                Error::new(ErrorDetails::InferenceServer {
                    message: format!(
                        "Error parsing text response: {}",
                        DisplayOrDebugGateway::new(e)
                    ),
                    raw_request: None,
                    raw_response: None,
                    provider_type: PROVIDER_TYPE.to_string(),
                })
            })?;

            let response: ResponseInputItemsList =
                serde_json::from_str(&raw_response).map_err(|e| {
                    Error::new(ErrorDetails::InferenceServer {
                        message: format!(
                            "Error parsing JSON response: {}",
                            DisplayOrDebugGateway::new(e)
                        ),
                        raw_request: None,
                        raw_response: Some(raw_response.clone()),
                        provider_type: PROVIDER_TYPE.to_string(),
                    })
                })?;

            Ok(response)
        } else {
            Err(handle_budprompt_error(
                "",
                res.status(),
                &res.text().await.unwrap_or_default(),
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::responses::{OpenAIResponse, ResponseStatus, ResponseUsage};
    use serde_json::json;

    #[test]
    fn test_budprompt_request_serialization() {
        // Create a request object similar to what BudPrompt would send
        let request = OpenAIResponseCreateParams {
            model: "gpt-4".to_string(),
            input: json!("Hello, how can I help you?"),
            instructions: Some("Be helpful and concise".to_string()),
            temperature: Some(0.7),
            max_output_tokens: Some(500),
            stream: Some(false),
            metadata: None,
            tools: None,
            tool_choice: None,
            parallel_tool_calls: None,
            max_tool_calls: None,
            previous_response_id: None,
            response_format: None,
            reasoning: None,
            include: None,
            prompt: None,
            stream_options: None,
            store: None,
            background: None,
            service_tier: None,
            modalities: None,
            user: None,
            unknown_fields: Default::default(),
        };

        // Serialize the request
        let json = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();

        // Verify the serialized format matches what we expect
        assert_eq!(parsed["model"], "gpt-4");
        assert_eq!(parsed["input"], "Hello, how can I help you?");
        assert_eq!(parsed["instructions"], "Be helpful and concise");
        assert_eq!(parsed["temperature"], 0.7);
        assert_eq!(parsed["max_output_tokens"], 500);
        assert_eq!(parsed["stream"], false);
    }

    #[test]
    fn test_budprompt_response_deserialization() {
        // Create a response object similar to what BudPrompt would receive
        let response = OpenAIResponse {
            id: "resp_test_12345".to_string(),
            object: "response".to_string(),
            created_at: 1234567890,
            model: "gpt-4".to_string(),
            status: ResponseStatus::Completed,
            incomplete_details: None,
            output: vec![json!({
                "type": "text",
                "text": "Hello! I'm here to help you."
            })],
            usage: Some(ResponseUsage {
                input_tokens: 10,
                input_tokens_details: None,
                output_tokens: Some(8),
                output_tokens_details: None,
                total_tokens: 18,
            }),
            metadata: None,
            reasoning: None,
            service_tier: None,
            background: None,
            error: None,
            instructions: None,
            input_items: None,
        };

        // Test serialization and deserialization roundtrip
        let json = serde_json::to_string(&response).unwrap();
        let parsed: OpenAIResponse = serde_json::from_str(&json).unwrap();

        // Verify all fields are preserved correctly
        assert_eq!(parsed.id, "resp_test_12345");
        assert_eq!(parsed.model, "gpt-4");
        assert_eq!(parsed.status, ResponseStatus::Completed);
        assert!(!parsed.output.is_empty());
        assert!(parsed.usage.is_some());

        let usage = parsed.usage.unwrap();
        assert_eq!(usage.input_tokens, 10);
        assert_eq!(usage.output_tokens, Some(8));
        assert_eq!(usage.total_tokens, 18);
    }
}
