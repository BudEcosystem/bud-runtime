// This is an internal crate, so we're the only consumers of
// traits with async fns for now.
#![expect(async_fn_in_trait)]
#![allow(dead_code)]

pub mod analytics; // gateway analytics data structures
pub mod analytics_batcher; // analytics batching for high-throughput ClickHouse writes
pub mod analytics_middleware; // gateway analytics middleware
pub mod audio; // audio transcription, translation, and text-to-speech
pub mod auth;
pub mod baggage; // W3C Baggage support for business context propagation
pub mod baggage_processor; // SpanProcessor to copy baggage to span attributes
pub mod blocking_middleware; // blocking rules enforcement middleware
pub mod blocking_rules; // blocking rules management
pub mod cache;
pub mod clickhouse;
pub mod completions; // text completion inference
pub mod config_parser; // TensorZero config file
pub mod documents; // document processing and OCR
pub mod embeddings; // embedding inference
pub mod encryption; // RSA encryption/decryption for API keys
pub mod endpoints; // API endpoints
pub mod error; // error handling
pub mod evaluations; // evaluation
pub mod file_storage; // file storage for OpenAI batch API
pub mod function; // types and methods for working with TensorZero functions
pub mod gateway_util; // utilities for gateway
pub mod geoip; // GeoIP lookup service
pub mod guardrail; // guardrail execution logic
pub mod guardrail_table; // guardrail configurations for advanced moderation
pub mod images; // image generation, editing, and variations
pub mod inference; // model inference
pub mod inference_batcher; // inference batching for high-throughput ClickHouse writes
pub mod jsonl_processor; // JSONL processing for OpenAI batch API
pub mod jsonschema_util; // utilities for working with JSON schemas
pub mod kafka; // Kafka integration
mod minijinja_util; // utilities for working with MiniJinja templates
pub mod model; // types and methods for working with TensorZero-supported models
pub mod model_table;
pub mod moderation; // moderation API
pub mod observability; // utilities for observability (logs, metrics, etc.)
pub mod openai_batch; // OpenAI-compatible batch API types
pub mod rate_limit; // rate limiting
pub mod realtime; // realtime API session management
pub mod redis_client; // redis client
pub mod responses; // OpenAI-compatible Responses API
mod testing;
pub mod tool; // types and methods for working with TensorZero tools
pub mod usage_limit; // usage limiting
mod uuid_util; // utilities for working with UUIDs
pub mod variant; // types and methods for working with TensorZero variants // authentication

pub mod built_info {
    #![expect(clippy::allow_attributes)]
    include!(concat!(env!("OUT_DIR"), "/built.rs"));
}
