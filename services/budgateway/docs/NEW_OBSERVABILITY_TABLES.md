# New ClickHouse Observability Tables

This document describes the new ClickHouse tables added to support observability for all OpenAI-compatible endpoints beyond chat completions.

## Overview

The following new tables have been added to track inference requests for different endpoint types:

- `EmbeddingInference` - For embedding requests
- `AudioInference` - For audio transcription, translation, and text-to-speech requests
- `ImageInference` - For image generation requests
- `ModerationInference` - For moderation requests

Additionally, the existing `ModelInference` table has been extended with an `endpoint_type` column to differentiate between different API types.

## Table Schemas

### ModelInference (Enhanced)

The existing `ModelInference` table now includes:

```sql
ALTER TABLE ModelInference
ADD COLUMN IF NOT EXISTS endpoint_type LowCardinality(String) DEFAULT 'chat'
```

**Possible values for endpoint_type:**
- `chat` - Chat completions
- `json` - JSON completions
- `embedding` - Embedding requests
- `audio_transcription` - Audio transcription
- `audio_translation` - Audio translation
- `text_to_speech` - Text-to-speech
- `image_generation` - Image generation
- `moderation` - Content moderation

### EmbeddingInference

Tracks embedding requests and responses:

```sql
CREATE TABLE EmbeddingInference
(
    id UUID,
    function_name LowCardinality(String),
    variant_name LowCardinality(String),
    episode_id UUID,
    input String,
    embeddings String,
    embedding_dimensions UInt32,
    input_count UInt32,
    inference_params String,
    processing_time_ms Nullable(UInt32),
    tags Map(String, String) DEFAULT map(),
    extra_body String DEFAULT '{}',
    timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
) ENGINE = MergeTree()
ORDER BY (function_name, id)
PARTITION BY toYYYYMM(timestamp)
```

**Fields:**
- `embeddings` - JSON array of embedding vectors
- `embedding_dimensions` - Dimension count for each embedding
- `input_count` - Number of input texts embedded

### AudioInference

Tracks all audio-related requests (transcription, translation, TTS):

```sql
CREATE TABLE AudioInference
(
    id UUID,
    function_name LowCardinality(String),
    variant_name LowCardinality(String),
    episode_id UUID,
    audio_type Enum8('transcription' = 1, 'translation' = 2, 'text_to_speech' = 3),
    input String,
    output String,
    language Nullable(String),
    duration_seconds Nullable(Float32),
    file_size_bytes Nullable(UInt64),
    response_format LowCardinality(String),
    inference_params String,
    processing_time_ms Nullable(UInt32),
    tags Map(String, String) DEFAULT map(),
    extra_body String DEFAULT '{}',
    timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
) ENGINE = MergeTree()
ORDER BY (function_name, audio_type, id)
PARTITION BY toYYYYMM(timestamp)
```

**Fields:**
- `audio_type` - Type of audio operation (transcription/translation/text_to_speech)
- `input` - For transcription/translation: filename; for TTS: input text
- `output` - For transcription/translation: text result; for TTS: file info
- `language` - Detected or specified language
- `duration_seconds` - Audio duration
- `file_size_bytes` - Size of audio file (input or output)
- `response_format` - Requested response format (json, text, mp3, etc.)

### ImageInference

Tracks image generation requests:

```sql
CREATE TABLE ImageInference
(
    id UUID,
    function_name LowCardinality(String),
    variant_name LowCardinality(String),
    episode_id UUID,
    prompt String,
    image_count UInt8,
    size LowCardinality(String),
    quality LowCardinality(String),
    style Nullable(String),
    response_format LowCardinality(String),
    images String,
    inference_params String,
    processing_time_ms Nullable(UInt32),
    tags Map(String, String) DEFAULT map(),
    extra_body String DEFAULT '{}',
    timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
) ENGINE = MergeTree()
ORDER BY (function_name, id)
PARTITION BY toYYYYMM(timestamp)
```

**Fields:**
- `prompt` - Text prompt for image generation
- `image_count` - Number of images requested
- `size` - Image dimensions (e.g., "1024x1024")
- `quality` - Image quality setting ("standard", "hd")
- `style` - Art style ("vivid", "natural")
- `images` - JSON array of generated image data (URLs or base64)

### ModerationInference

Tracks content moderation requests:

```sql
CREATE TABLE ModerationInference
(
    id UUID,
    function_name LowCardinality(String),
    variant_name LowCardinality(String),
    episode_id UUID,
    input String,
    results String,
    flagged Bool,
    categories Map(String, Bool),
    category_scores Map(String, Float32),
    inference_params String,
    processing_time_ms Nullable(UInt32),
    tags Map(String, String) DEFAULT map(),
    extra_body String DEFAULT '{}',
    timestamp DateTime MATERIALIZED UUIDv7ToDateTime(id)
) ENGINE = MergeTree()
ORDER BY (function_name, flagged, id)
PARTITION BY toYYYYMM(timestamp)
```

**Fields:**
- `input` - Content being moderated
- `results` - Full moderation results JSON
- `flagged` - Whether content was flagged
- `categories` - Map of category names to boolean flags
- `category_scores` - Map of category names to confidence scores

## Usage Examples

### Query embedding requests by dimension count

```sql
SELECT
    function_name,
    embedding_dimensions,
    COUNT(*) as request_count,
    AVG(processing_time_ms) as avg_processing_time
FROM EmbeddingInference
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY function_name, embedding_dimensions
ORDER BY request_count DESC
```

### Analyze audio processing by type and language

```sql
SELECT
    audio_type,
    language,
    COUNT(*) as requests,
    AVG(duration_seconds) as avg_duration,
    SUM(file_size_bytes) as total_bytes
FROM AudioInference
WHERE timestamp >= now() - INTERVAL 1 WEEK
GROUP BY audio_type, language
ORDER BY requests DESC
```

### Image generation statistics by size and quality

```sql
SELECT
    size,
    quality,
    COUNT(*) as generation_count,
    SUM(image_count) as total_images,
    AVG(processing_time_ms) as avg_time
FROM ImageInference
WHERE timestamp >= now() - INTERVAL 1 MONTH
GROUP BY size, quality
ORDER BY generation_count DESC
```

### Moderation flagging rates by category

```sql
SELECT
    category_key,
    COUNT(*) as total_checks,
    SUM(category_value) as flagged_count,
    (SUM(category_value) * 100.0 / COUNT(*)) as flagging_rate
FROM ModerationInference
ARRAY JOIN categories AS (category_key, category_value)
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY category_key
ORDER BY flagging_rate DESC
```

### Cross-endpoint usage analysis

```sql
SELECT
    endpoint_type,
    COUNT(*) as request_count,
    AVG(response_time_ms) as avg_response_time,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens
FROM ModelInference
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY endpoint_type
ORDER BY request_count DESC
```

## Data Retention

All tables use monthly partitioning based on the timestamp column for efficient data management and query performance. Consider implementing appropriate retention policies based on your observability requirements.

## Indexing Strategy

The tables are optimized with the following ordering keys:
- `EmbeddingInference`: `(function_name, id)`
- `AudioInference`: `(function_name, audio_type, id)`
- `ImageInference`: `(function_name, id)`
- `ModerationInference`: `(function_name, flagged, id)`

This allows for efficient queries by function name and specific filtering criteria while maintaining good insert performance.
