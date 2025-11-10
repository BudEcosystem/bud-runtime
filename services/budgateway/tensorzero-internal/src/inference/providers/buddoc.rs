use crate::documents::{
    DocumentProcessingProvider, DocumentProcessingProviderResponse, DocumentProcessingRequest,
    DocumentType, PageResult, UsageInfo,
};
use crate::endpoints::inference::InferenceCredentials;
use crate::error::{Error, ErrorDetails};
use crate::inference::types::{Latency, Usage};
use crate::model::{Credential, CredentialLocation};
use reqwest::Client;
use secrecy::{ExposeSecret, SecretString};
use serde::{Deserialize, Serialize};
use std::time::Instant;
use uuid::Uuid;

#[derive(Debug)]
pub struct BudDocProvider {
    pub api_base: String,
    pub credentials: BudDocCredentials,
}

impl BudDocProvider {
    pub fn new(
        api_base: String,
        api_key_location: Option<CredentialLocation>,
    ) -> Result<Self, Error> {
        let credentials = if let Some(location) = api_key_location {
            BudDocCredentials::try_from(Credential::try_from((location, "BudDoc"))?)?
        } else {
            BudDocCredentials::None
        };
        Ok(Self {
            api_base,
            credentials,
        })
    }
}

#[derive(Debug, Clone)]
pub enum BudDocCredentials {
    Static(SecretString),
    Dynamic(String),
    None,
}

impl TryFrom<Credential> for BudDocCredentials {
    type Error = Error;

    fn try_from(credentials: Credential) -> Result<Self, Error> {
        match credentials {
            Credential::Static(key) => Ok(BudDocCredentials::Static(key)),
            Credential::Dynamic(key_name) => Ok(BudDocCredentials::Dynamic(key_name)),
            Credential::None | Credential::Missing => Ok(BudDocCredentials::None),
            _ => Err(Error::new(ErrorDetails::Config {
                message: "Invalid api_key_location for BudDoc provider".to_string(),
            })),
        }
    }
}

impl BudDocCredentials {
    pub fn get_api_key<'a>(
        &self,
        dynamic_api_keys: &'a InferenceCredentials,
    ) -> Option<&'a SecretString> {
        match self {
            BudDocCredentials::Static(_api_key) => {
                // For static credentials, we need to return a reference from dynamic_api_keys
                // This is a workaround - ideally we'd store the static key differently
                None
            }
            BudDocCredentials::Dynamic(key_name) => dynamic_api_keys.get(key_name),
            BudDocCredentials::None => None,
        }
    }

    pub fn get_static_api_key(&self) -> Option<&SecretString> {
        match self {
            BudDocCredentials::Static(api_key) => Some(api_key),
            _ => None,
        }
    }
}

// BudDoc-specific request format (matching OCRRequest in buddoc)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct BudDocOCRRequest {
    model: String,
    document: BudDocDocumentInput,
    #[serde(skip_serializing_if = "Option::is_none")]
    prompt: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BudDocDocumentInput {
    #[serde(rename = "type")]
    doc_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    document_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    image_url: Option<String>,
}

// BudDoc-specific response format (matching OCRResponse in buddoc)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct BudDocOCRResponse {
    document_id: Uuid,
    model: String,
    pages: Vec<BudDocPageResult>,
    usage_info: BudDocUsageInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BudDocPageResult {
    page_number: i32,
    markdown: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BudDocUsageInfo {
    pages_processed: i32,
    size_bytes: i64,
    filename: String,
}

impl DocumentProcessingProvider for BudDocProvider {
    async fn process_document(
        &self,
        request: &DocumentProcessingRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> Result<DocumentProcessingProviderResponse, Error> {
        let start_time = Instant::now();

        // Convert request to BudDoc format
        let doc_type = match request.document.doc_type {
            DocumentType::DocumentUrl => "document_url",
            DocumentType::ImageUrl => "image_url",
        };

        let buddoc_request = BudDocOCRRequest {
            model: request.model.to_string(),
            document: BudDocDocumentInput {
                doc_type: doc_type.to_string(),
                document_url: request.document.document_url.clone(),
                image_url: request.document.image_url.clone(),
            },
            prompt: request.prompt.clone(),
        };

        let raw_request = serde_json::to_string(&buddoc_request).map_err(|e| {
            Error::new(ErrorDetails::Serialization {
                message: format!("Failed to serialize BudDoc request: {}", e),
            })
        })?;

        // Build the request (ensure no double slashes)
        let url = if self.api_base.ends_with('/') {
            format!("{}documents/ocr", self.api_base)
        } else {
            format!("{}/documents/ocr", self.api_base)
        };
        let mut req_builder = client.post(url).json(&buddoc_request);

        // Add authorization header based on credentials
        // First check for dynamic API key
        if let Some(api_key) = self.credentials.get_api_key(dynamic_api_keys) {
            req_builder = req_builder.header(
                "Authorization",
                format!("Bearer {}", api_key.expose_secret()),
            );
        }
        // Then check for static API key
        else if let Some(api_key) = self.credentials.get_static_api_key() {
            req_builder = req_builder.header(
                "Authorization",
                format!("Bearer {}", api_key.expose_secret()),
            );
        }

        // Send the request
        let response = req_builder.send().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to send request to BudDoc: {}", e),
                status_code: None,
                provider_type: "BudDoc".to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: None,
            })
        })?;

        let status = response.status();
        let raw_response = response.text().await.map_err(|e| {
            Error::new(ErrorDetails::InferenceClient {
                message: format!("Failed to read BudDoc response: {}", e),
                status_code: Some(status),
                provider_type: "BudDoc".to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: None,
            })
        })?;

        if !status.is_success() {
            return Err(Error::new(ErrorDetails::InferenceServer {
                message: format!("BudDoc returned error status {}: {}", status, raw_response),
                provider_type: "BudDoc".to_string(),
                raw_request: Some(raw_request.clone()),
                raw_response: Some(raw_response.clone()),
            }));
        }

        // Parse the response
        let buddoc_response: BudDocOCRResponse =
            serde_json::from_str(&raw_response).map_err(|e| {
                Error::new(ErrorDetails::Serialization {
                    message: format!("Failed to parse BudDoc response: {}", e),
                })
            })?;

        // Calculate latency
        let latency = Latency::NonStreaming {
            response_time: start_time.elapsed(),
        };

        // Convert pages to our format
        let pages: Vec<PageResult> = buddoc_response
            .pages
            .into_iter()
            .map(|p| PageResult {
                page_number: p.page_number,
                markdown: p.markdown,
            })
            .collect();

        // Convert usage info
        let usage_info = UsageInfo {
            pages_processed: buddoc_response.usage_info.pages_processed,
            size_bytes: buddoc_response.usage_info.size_bytes,
            filename: buddoc_response.usage_info.filename,
        };

        // Create usage metrics (estimate based on document size)
        let usage = Usage {
            input_tokens: (buddoc_response.usage_info.size_bytes / 4) as u32, // Rough estimate
            output_tokens: pages
                .iter()
                .map(|p| p.markdown.len() as u32 / 4)
                .sum::<u32>(),
        };

        Ok(DocumentProcessingProviderResponse {
            document_id: buddoc_response.document_id,
            model: buddoc_response.model,
            pages,
            usage_info,
            raw_request,
            raw_response,
            usage,
            latency,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::documents::DocumentInput;
    use std::sync::Arc;

    #[test]
    fn test_buddoc_request_serialization() {
        let request = BudDocOCRRequest {
            model: "qwen2-vl-7b".to_string(),
            document: BudDocDocumentInput {
                doc_type: "document_url".to_string(),
                document_url: Some("https://example.com/doc.pdf".to_string()),
                image_url: None,
            },
            prompt: Some("Extract text from this document".to_string()),
        };

        let json = serde_json::to_string(&request).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed["model"], "qwen2-vl-7b");
        assert_eq!(parsed["document"]["type"], "document_url");
        assert_eq!(
            parsed["document"]["document_url"],
            "https://example.com/doc.pdf"
        );
        assert_eq!(parsed["prompt"], "Extract text from this document");
    }

    #[test]
    fn test_buddoc_response_deserialization() {
        let response = BudDocOCRResponse {
            document_id: Uuid::parse_str("550e8400-e29b-41d4-a716-446655440000").unwrap(),
            model: "qwen2-vl-7b".to_string(),
            pages: vec![BudDocPageResult {
                page_number: 1,
                markdown: "# Title\n\nContent here".to_string(),
            }],
            usage_info: BudDocUsageInfo {
                pages_processed: 1,
                size_bytes: 1024,
                filename: "test.pdf".to_string(),
            },
        };

        // Test serialization and deserialization
        let json = serde_json::to_string(&response).unwrap();
        let parsed: BudDocOCRResponse = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.model, "qwen2-vl-7b");
        assert_eq!(parsed.pages.len(), 1);
        assert_eq!(parsed.pages[0].page_number, 1);
        assert_eq!(parsed.usage_info.pages_processed, 1);
    }
}
