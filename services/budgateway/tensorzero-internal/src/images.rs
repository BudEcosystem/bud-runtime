use crate::endpoints::inference::InferenceCredentials;
use crate::error::Error;
use crate::error::ErrorDetails;
use crate::inference::types::{Latency, Usage};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::str::FromStr;
use std::sync::Arc;
use uuid::Uuid;

// Image generation types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageGenerationRequest {
    pub id: Uuid,
    pub prompt: String,
    pub model: Arc<str>,
    pub n: Option<u8>,
    pub size: Option<ImageSize>,
    pub quality: Option<ImageQuality>,
    pub style: Option<ImageStyle>,
    pub response_format: Option<ImageResponseFormat>,
    pub user: Option<String>,
    // GPT-Image-1 specific parameters
    pub background: Option<ImageBackground>,
    pub moderation: Option<ImageModeration>,
    pub output_compression: Option<u8>, // 0-100
    pub output_format: Option<ImageOutputFormat>,
}

// Image edit types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageEditRequest {
    pub id: Uuid,
    pub image: Vec<u8>,
    pub image_filename: String,
    pub prompt: String,
    pub mask: Option<Vec<u8>>,
    pub mask_filename: Option<String>,
    pub model: Arc<str>,
    pub n: Option<u8>,
    pub size: Option<ImageSize>,
    pub response_format: Option<ImageResponseFormat>,
    pub user: Option<String>,
    // Model-specific parameters
    pub background: Option<ImageBackground>,
    pub quality: Option<ImageQuality>,
    pub output_compression: Option<u8>,
    pub output_format: Option<ImageOutputFormat>,
}

// Image variation types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageVariationRequest {
    pub id: Uuid,
    pub image: Vec<u8>,
    pub image_filename: String,
    pub model: Arc<str>,
    pub n: Option<u8>,
    pub size: Option<ImageSize>,
    pub response_format: Option<ImageResponseFormat>,
    pub user: Option<String>,
}

// Response types - specific for each operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageGenerationResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageEditResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageVariationResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageData {
    pub url: Option<String>,
    pub b64_json: Option<String>,
    pub revised_prompt: Option<String>, // DALL-E 3 only
}

// Image size enum supporting all model variants
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageSize {
    #[serde(rename = "256x256")]
    Size256x256,
    #[serde(rename = "512x512")]
    Size512x512,
    #[serde(rename = "1024x1024")]
    Size1024x1024,
    #[serde(rename = "1024x1536")]
    Size1024x1536, // DALL-E 2 and GPT-Image-1
    #[serde(rename = "1536x1024")]
    Size1536x1024, // DALL-E 2 and GPT-Image-1
    #[serde(rename = "1024x1792")]
    Size1024x1792, // DALL-E 3 only
    #[serde(rename = "1792x1024")]
    Size1792x1024, // DALL-E 3 only
}

// Image quality enum supporting model-specific quality levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageQuality {
    Auto,     // GPT-Image-1
    Low,      // GPT-Image-1
    Medium,   // GPT-Image-1
    High,     // GPT-Image-1
    Standard, // DALL-E 2/3
    #[serde(rename = "hd")]
    HD, // DALL-E 3 only
}

// Image style enum for DALL-E 3
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageStyle {
    Vivid,   // DALL-E 3 only
    Natural, // DALL-E 3 only
}

// Response format enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageResponseFormat {
    Url,
    #[serde(rename = "b64_json")]
    B64Json,
}

// Background control for GPT-Image-1
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageBackground {
    Transparent, // GPT-Image-1 only
    Opaque,      // GPT-Image-1 only
    Auto,        // GPT-Image-1 only
}

// Moderation level for GPT-Image-1
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageModeration {
    Low,  // GPT-Image-1 only
    Auto, // GPT-Image-1 only
}

// Output format for GPT-Image-1
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageOutputFormat {
    Png,
    Jpeg,
    Webp,
}

// Provider response types
#[derive(Debug, Clone)]
pub struct ImageGenerationProviderResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone)]
pub struct ImageEditProviderResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

#[derive(Debug, Clone)]
pub struct ImageVariationProviderResponse {
    pub id: Uuid,
    pub created: u64,
    pub data: Vec<ImageData>,
    pub raw_request: String,
    pub raw_response: String,
    pub usage: Usage,
    pub latency: Latency,
}

// Provider traits
pub trait ImageGenerationProvider {
    fn generate_image(
        &self,
        request: &ImageGenerationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl std::future::Future<Output = Result<ImageGenerationProviderResponse, Error>> + Send;
}

pub trait ImageEditProvider {
    fn edit_image(
        &self,
        request: &ImageEditRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl std::future::Future<Output = Result<ImageEditProviderResponse, Error>> + Send;
}

pub trait ImageVariationProvider {
    fn create_image_variation(
        &self,
        request: &ImageVariationRequest,
        client: &Client,
        dynamic_api_keys: &InferenceCredentials,
    ) -> impl std::future::Future<Output = Result<ImageVariationProviderResponse, Error>> + Send;
}

// Helper methods for enum conversions
impl ImageSize {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageSize::Size256x256 => "256x256",
            ImageSize::Size512x512 => "512x512",
            ImageSize::Size1024x1024 => "1024x1024",
            ImageSize::Size1024x1536 => "1024x1536",
            ImageSize::Size1536x1024 => "1536x1024",
            ImageSize::Size1024x1792 => "1024x1792",
            ImageSize::Size1792x1024 => "1792x1024",
        }
    }
}

impl FromStr for ImageSize {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "256x256" => Ok(ImageSize::Size256x256),
            "512x512" => Ok(ImageSize::Size512x512),
            "1024x1024" => Ok(ImageSize::Size1024x1024),
            "1024x1536" => Ok(ImageSize::Size1024x1536),
            "1536x1024" => Ok(ImageSize::Size1536x1024),
            "1024x1792" => Ok(ImageSize::Size1024x1792),
            "1792x1024" => Ok(ImageSize::Size1792x1024),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported image size: {s}"),
            })),
        }
    }
}

impl ImageQuality {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageQuality::Auto => "auto",
            ImageQuality::Low => "low",
            ImageQuality::Medium => "medium",
            ImageQuality::High => "high",
            ImageQuality::Standard => "standard",
            ImageQuality::HD => "hd",
        }
    }
}

impl FromStr for ImageQuality {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "auto" => Ok(ImageQuality::Auto),
            "low" => Ok(ImageQuality::Low),
            "medium" => Ok(ImageQuality::Medium),
            "high" => Ok(ImageQuality::High),
            "standard" => Ok(ImageQuality::Standard),
            "hd" => Ok(ImageQuality::HD),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported image quality: {s}"),
            })),
        }
    }
}

impl ImageStyle {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageStyle::Vivid => "vivid",
            ImageStyle::Natural => "natural",
        }
    }
}

impl FromStr for ImageStyle {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "vivid" => Ok(ImageStyle::Vivid),
            "natural" => Ok(ImageStyle::Natural),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported image style: {s}"),
            })),
        }
    }
}

impl ImageResponseFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageResponseFormat::Url => "url",
            ImageResponseFormat::B64Json => "b64_json",
        }
    }
}

impl FromStr for ImageResponseFormat {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "url" => Ok(ImageResponseFormat::Url),
            "b64_json" => Ok(ImageResponseFormat::B64Json),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported response format: {s}"),
            })),
        }
    }
}

impl ImageBackground {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageBackground::Transparent => "transparent",
            ImageBackground::Opaque => "opaque",
            ImageBackground::Auto => "auto",
        }
    }
}

impl FromStr for ImageBackground {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "transparent" => Ok(ImageBackground::Transparent),
            "opaque" => Ok(ImageBackground::Opaque),
            "auto" => Ok(ImageBackground::Auto),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported background: {s}"),
            })),
        }
    }
}

impl ImageModeration {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageModeration::Low => "low",
            ImageModeration::Auto => "auto",
        }
    }
}

impl FromStr for ImageModeration {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "low" => Ok(ImageModeration::Low),
            "auto" => Ok(ImageModeration::Auto),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported moderation level: {s}"),
            })),
        }
    }
}

impl ImageOutputFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            ImageOutputFormat::Png => "png",
            ImageOutputFormat::Jpeg => "jpeg",
            ImageOutputFormat::Webp => "webp",
        }
    }
}

impl FromStr for ImageOutputFormat {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "png" => Ok(ImageOutputFormat::Png),
            "jpeg" => Ok(ImageOutputFormat::Jpeg),
            "webp" => Ok(ImageOutputFormat::Webp),
            _ => Err(Error::new(ErrorDetails::InvalidRequest {
                message: format!("Unsupported output format: {s}"),
            })),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_image_size_serialization() {
        let size = ImageSize::Size1024x1024;
        let serialized = serde_json::to_string(&size).unwrap();
        assert_eq!(serialized, "\"1024x1024\"");

        let size = ImageSize::Size1792x1024;
        let serialized = serde_json::to_string(&size).unwrap();
        assert_eq!(serialized, "\"1792x1024\"");
    }

    #[test]
    fn test_image_quality_serialization() {
        let quality = ImageQuality::HD;
        let serialized = serde_json::to_string(&quality).unwrap();
        assert_eq!(serialized, "\"hd\"");

        let quality = ImageQuality::Standard;
        let serialized = serde_json::to_string(&quality).unwrap();
        assert_eq!(serialized, "\"standard\"");
    }

    #[test]
    fn test_image_style_serialization() {
        let style = ImageStyle::Vivid;
        let serialized = serde_json::to_string(&style).unwrap();
        assert_eq!(serialized, "\"vivid\"");

        let style = ImageStyle::Natural;
        let serialized = serde_json::to_string(&style).unwrap();
        assert_eq!(serialized, "\"natural\"");
    }

    #[test]
    fn test_image_response_format_serialization() {
        let format = ImageResponseFormat::B64Json;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"b64_json\"");

        let format = ImageResponseFormat::Url;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"url\"");
    }

    #[test]
    fn test_image_background_serialization() {
        let background = ImageBackground::Transparent;
        let serialized = serde_json::to_string(&background).unwrap();
        assert_eq!(serialized, "\"transparent\"");

        let background = ImageBackground::Auto;
        let serialized = serde_json::to_string(&background).unwrap();
        assert_eq!(serialized, "\"auto\"");
    }

    #[test]
    fn test_image_moderation_serialization() {
        let moderation = ImageModeration::Low;
        let serialized = serde_json::to_string(&moderation).unwrap();
        assert_eq!(serialized, "\"low\"");

        let moderation = ImageModeration::Auto;
        let serialized = serde_json::to_string(&moderation).unwrap();
        assert_eq!(serialized, "\"auto\"");
    }

    #[test]
    fn test_image_output_format_serialization() {
        let format = ImageOutputFormat::Webp;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"webp\"");

        let format = ImageOutputFormat::Png;
        let serialized = serde_json::to_string(&format).unwrap();
        assert_eq!(serialized, "\"png\"");
    }

    #[test]
    fn test_image_size_as_str() {
        assert_eq!(ImageSize::Size256x256.as_str(), "256x256");
        assert_eq!(ImageSize::Size1024x1792.as_str(), "1024x1792");
    }

    #[test]
    fn test_image_size_from_str() {
        assert_eq!(
            "512x512".parse::<ImageSize>().unwrap(),
            ImageSize::Size512x512
        );
        assert_eq!(
            "1792x1024".parse::<ImageSize>().unwrap(),
            ImageSize::Size1792x1024
        );
        assert!("invalid".parse::<ImageSize>().is_err());
    }

    #[test]
    fn test_image_quality_as_str() {
        assert_eq!(ImageQuality::HD.as_str(), "hd");
        assert_eq!(ImageQuality::Standard.as_str(), "standard");
        assert_eq!(ImageQuality::Auto.as_str(), "auto");
    }

    #[test]
    fn test_image_generation_request_creation() {
        let request = ImageGenerationRequest {
            id: Uuid::now_v7(),
            prompt: "A beautiful sunset".to_string(),
            model: Arc::from("dall-e-3"),
            n: Some(1),
            size: Some(ImageSize::Size1024x1024),
            quality: Some(ImageQuality::HD),
            style: Some(ImageStyle::Vivid),
            response_format: Some(ImageResponseFormat::Url),
            user: None,
            background: None,
            moderation: None,
            output_compression: None,
            output_format: None,
        };

        assert_eq!(request.prompt, "A beautiful sunset");
        assert_eq!(request.model.as_ref(), "dall-e-3");
        assert_eq!(request.n, Some(1));
        assert_eq!(request.size, Some(ImageSize::Size1024x1024));
        assert_eq!(request.quality, Some(ImageQuality::HD));
        assert_eq!(request.style, Some(ImageStyle::Vivid));
    }

    #[test]
    fn test_image_edit_request_creation() {
        let request = ImageEditRequest {
            id: Uuid::now_v7(),
            image: vec![1, 2, 3, 4],
            image_filename: "test.png".to_string(),
            prompt: "Make it brighter".to_string(),
            mask: Some(vec![5, 6, 7, 8]),
            mask_filename: Some("mask.png".to_string()),
            model: Arc::from("dall-e-2"),
            n: Some(2),
            size: Some(ImageSize::Size512x512),
            response_format: Some(ImageResponseFormat::B64Json),
            user: None,
            background: None,
            quality: None,
            output_compression: None,
            output_format: None,
        };

        assert_eq!(request.image, vec![1, 2, 3, 4]);
        assert_eq!(request.image_filename, "test.png");
        assert_eq!(request.prompt, "Make it brighter");
        assert_eq!(request.mask, Some(vec![5, 6, 7, 8]));
        assert_eq!(request.model.as_ref(), "dall-e-2");
    }

    #[test]
    fn test_image_variation_request_creation() {
        let request = ImageVariationRequest {
            id: Uuid::now_v7(),
            image: vec![1, 2, 3, 4],
            image_filename: "original.png".to_string(),
            model: Arc::from("dall-e-2"),
            n: Some(3),
            size: Some(ImageSize::Size1024x1024),
            response_format: Some(ImageResponseFormat::Url),
            user: Some("user123".to_string()),
        };

        assert_eq!(request.image, vec![1, 2, 3, 4]);
        assert_eq!(request.image_filename, "original.png");
        assert_eq!(request.model.as_ref(), "dall-e-2");
        assert_eq!(request.n, Some(3));
        assert_eq!(request.user, Some("user123".to_string()));
    }
}
