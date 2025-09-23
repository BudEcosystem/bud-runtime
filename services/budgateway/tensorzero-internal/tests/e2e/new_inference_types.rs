use std::collections::HashMap;
use tensorzero_internal::inference::types::{
    AudioTranscriptionInferenceResult, AudioTranslationInferenceResult, AudioType,
    EmbeddingInferenceResult, ImageData, ImageGenerationInferenceResult, InferenceResult,
    ModerationInferenceResult, ModerationResult, TextToSpeechInferenceResult, Usage,
};
use uuid::Uuid;

#[test]
fn test_embedding_inference_result_creation() {
    let inference_id = Uuid::now_v7();
    let embeddings = vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]];

    let embedding_result = EmbeddingInferenceResult {
        inference_id,
        created: 1642694400,
        embeddings: embeddings.clone(),
        embedding_dimensions: 3,
        input_count: 2,
        usage: Usage {
            input_tokens: 10,
            output_tokens: 0,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::Embedding(embedding_result);

    assert_eq!(inference_result.endpoint_type(), "embedding");
    assert_eq!(inference_result.usage().input_tokens, 10);
    assert_eq!(inference_result.usage().output_tokens, 0);
}

#[test]
fn test_audio_transcription_inference_result_creation() {
    let inference_id = Uuid::now_v7();

    let audio_result = AudioTranscriptionInferenceResult {
        inference_id,
        created: 1642694400,
        text: "Hello world".to_string(),
        language: Some("en".to_string()),
        duration_seconds: Some(2.5),
        words: None,
        segments: None,
        usage: Usage {
            input_tokens: 0,
            output_tokens: 2,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::AudioTranscription(audio_result);

    assert_eq!(inference_result.endpoint_type(), "audio_transcription");
    assert_eq!(inference_result.usage().input_tokens, 0);
    assert_eq!(inference_result.usage().output_tokens, 2);
}

#[test]
fn test_audio_translation_inference_result_creation() {
    let inference_id = Uuid::now_v7();

    let audio_result = AudioTranslationInferenceResult {
        inference_id,
        created: 1642694400,
        text: "Hello world".to_string(),
        language: Some("en".to_string()),
        duration_seconds: Some(2.5),
        usage: Usage {
            input_tokens: 0,
            output_tokens: 2,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::AudioTranslation(audio_result);

    assert_eq!(inference_result.endpoint_type(), "audio_translation");
}

#[test]
fn test_text_to_speech_inference_result_creation() {
    let inference_id = Uuid::now_v7();

    let tts_result = TextToSpeechInferenceResult {
        inference_id,
        created: 1642694400,
        audio_data: vec![1, 2, 3, 4, 5],
        audio_format: "mp3".to_string(),
        duration_seconds: Some(1.5),
        usage: Usage {
            input_tokens: 5,
            output_tokens: 0,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::TextToSpeech(tts_result);

    assert_eq!(inference_result.endpoint_type(), "text_to_speech");
}

#[test]
fn test_image_generation_inference_result_creation() {
    let inference_id = Uuid::now_v7();

    let images = vec![ImageData {
        url: Some("https://example.com/image.png".to_string()),
        base64: None,
        revised_prompt: Some("A beautiful landscape".to_string()),
    }];

    let image_result = ImageGenerationInferenceResult {
        inference_id,
        created: 1642694400,
        images: images.clone(),
        image_count: 1,
        size: "1024x1024".to_string(),
        quality: "standard".to_string(),
        style: Some("vivid".to_string()),
        usage: Usage {
            input_tokens: 10,
            output_tokens: 0,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::ImageGeneration(image_result);

    assert_eq!(inference_result.endpoint_type(), "image_generation");
}

#[test]
fn test_moderation_inference_result_creation() {
    let inference_id = Uuid::now_v7();

    let mut categories = HashMap::new();
    categories.insert("hate".to_string(), false);
    categories.insert("violence".to_string(), true);

    let mut category_scores = HashMap::new();
    category_scores.insert("hate".to_string(), 0.1);
    category_scores.insert("violence".to_string(), 0.8);

    let results = vec![ModerationResult {
        flagged: true,
        categories: categories.clone(),
        category_scores: category_scores.clone(),
    }];

    let moderation_result = ModerationInferenceResult {
        inference_id,
        created: 1642694400,
        results: results.clone(),
        usage: Usage {
            input_tokens: 5,
            output_tokens: 0,
        },
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    };

    let inference_result = InferenceResult::Moderation(moderation_result);

    assert_eq!(inference_result.endpoint_type(), "moderation");
}

#[test]
fn test_audio_type_serialization() {
    use serde_json;

    assert_eq!(
        serde_json::to_string(&AudioType::Transcription).unwrap(),
        "\"transcription\""
    );
    assert_eq!(
        serde_json::to_string(&AudioType::Translation).unwrap(),
        "\"translation\""
    );
    assert_eq!(
        serde_json::to_string(&AudioType::TextToSpeech).unwrap(),
        "\"text_to_speech\""
    );
}

#[test]
fn test_inference_result_endpoint_type_mapping() {
    let inference_id = Uuid::now_v7();

    // Test all endpoint types
    let embedding_result = InferenceResult::Embedding(EmbeddingInferenceResult {
        inference_id,
        created: 1642694400,
        embeddings: vec![vec![1.0]],
        embedding_dimensions: 1,
        input_count: 1,
        usage: Default::default(),
        model_inference_results: vec![],
        inference_params: Default::default(),
        original_response: None,
    });

    assert_eq!(embedding_result.endpoint_type(), "embedding");

    let audio_transcription =
        InferenceResult::AudioTranscription(AudioTranscriptionInferenceResult {
            inference_id,
            created: 1642694400,
            text: "test".to_string(),
            language: None,
            duration_seconds: None,
            words: None,
            segments: None,
            usage: Default::default(),
            model_inference_results: vec![],
            inference_params: Default::default(),
            original_response: None,
        });

    assert_eq!(audio_transcription.endpoint_type(), "audio_transcription");
}
