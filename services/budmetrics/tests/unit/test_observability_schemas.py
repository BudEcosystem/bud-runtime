"""Unit tests for new observability schemas."""

import pytest
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import ValidationError

from budmetrics.observability.schemas import (
    InferenceListRequest,
    InferenceListItem,
    EmbeddingInferenceDetail,
    AudioInferenceDetail,
    ImageInferenceDetail,
    ModerationInferenceDetail,
    EnhancedInferenceDetailResponse,
)


class TestInferenceListRequest:
    """Test InferenceListRequest schema."""

    def test_valid_request_with_endpoint_type(self):
        """Test creating valid request with endpoint_type filter."""
        request = InferenceListRequest(
            from_date=datetime.now(),
            endpoint_type="embedding",
            limit=50
        )
        assert request.endpoint_type == "embedding"
        assert request.limit == 50

    def test_invalid_endpoint_type(self):
        """Test that invalid endpoint_type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            InferenceListRequest(
                from_date=datetime.now(),
                endpoint_type="invalid_type"
            )
        assert "endpoint_type" in str(exc_info.value)

    def test_all_valid_endpoint_types(self):
        """Test all valid endpoint types."""
        valid_types = [
            "chat", "embedding", "audio_transcription",
            "audio_translation", "text_to_speech",
            "image_generation", "moderation"
        ]

        for endpoint_type in valid_types:
            request = InferenceListRequest(
                from_date=datetime.now(),
                endpoint_type=endpoint_type
            )
            assert request.endpoint_type == endpoint_type


class TestInferenceListItem:
    """Test InferenceListItem schema."""

    def test_with_endpoint_type(self):
        """Test creating item with endpoint_type."""
        item = InferenceListItem(
            inference_id=uuid4(),
            timestamp=datetime.now(),
            model_name="gpt-4",
            prompt_preview="test prompt",
            response_preview="test response",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            response_time_ms=100,
            is_success=True,
            cached=False,
            endpoint_type="chat"
        )
        assert item.endpoint_type == "chat"

    def test_default_endpoint_type(self):
        """Test default endpoint_type is 'chat'."""
        item = InferenceListItem(
            inference_id=uuid4(),
            timestamp=datetime.now(),
            model_name="gpt-4",
            prompt_preview="test",
            response_preview="response",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            response_time_ms=100,
            is_success=True,
            cached=False
        )
        assert item.endpoint_type == "chat"


class TestEmbeddingInferenceDetail:
    """Test EmbeddingInferenceDetail schema."""

    def test_valid_embedding_detail(self):
        """Test creating valid embedding detail."""
        detail = EmbeddingInferenceDetail(
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            embedding_dimensions=3,
            input_count=2,
            input_text="test text"
        )
        assert len(detail.embeddings) == 2
        assert detail.embedding_dimensions == 3
        assert detail.input_count == 2

    def test_empty_embeddings(self):
        """Test with empty embeddings list."""
        detail = EmbeddingInferenceDetail(
            embeddings=[],
            embedding_dimensions=0,
            input_count=0,
            input_text=""
        )
        assert len(detail.embeddings) == 0


class TestAudioInferenceDetail:
    """Test AudioInferenceDetail schema."""

    def test_transcription_detail(self):
        """Test audio transcription detail."""
        detail = AudioInferenceDetail(
            audio_type="transcription",
            input="audio.wav",
            output="Transcribed text",
            language="en",
            duration_seconds=5.5
        )
        assert detail.audio_type == "transcription"
        assert detail.language == "en"
        assert detail.duration_seconds == 5.5

    def test_translation_detail(self):
        """Test audio translation detail."""
        detail = AudioInferenceDetail(
            audio_type="translation",
            input="audio_es.wav",
            output="Translated to English",
            language="es",
            duration_seconds=3.2
        )
        assert detail.audio_type == "translation"

    def test_text_to_speech_detail(self):
        """Test text-to-speech detail."""
        detail = AudioInferenceDetail(
            audio_type="text_to_speech",
            input="Text to speak",
            output="audio_output.mp3",
            response_format="mp3",
            file_size_bytes=524288
        )
        assert detail.audio_type == "text_to_speech"
        assert detail.file_size_bytes == 524288

    def test_invalid_audio_type(self):
        """Test invalid audio type raises error."""
        with pytest.raises(ValidationError):
            AudioInferenceDetail(
                audio_type="invalid",
                input="test",
                output="test"
            )


class TestImageInferenceDetail:
    """Test ImageInferenceDetail schema."""

    def test_valid_image_detail(self):
        """Test creating valid image detail."""
        detail = ImageInferenceDetail(
            prompt="A beautiful sunset",
            image_count=2,
            size="1024x1024",
            quality="hd",
            style="vivid",
            images=[
                {"url": "https://example.com/image1.png"},
                {"url": "https://example.com/image2.png"}
            ]
        )
        assert detail.prompt == "A beautiful sunset"
        assert detail.image_count == 2
        assert detail.size == "1024x1024"
        assert len(detail.images) == 2

    def test_minimal_image_detail(self):
        """Test minimal image detail without optional fields."""
        detail = ImageInferenceDetail(
            prompt="Simple prompt",
            image_count=1,
            size="512x512",
            quality="standard",
            images=[]
        )
        assert detail.style is None


class TestModerationInferenceDetail:
    """Test ModerationInferenceDetail schema."""

    def test_flagged_content(self):
        """Test moderation detail with flagged content."""
        detail = ModerationInferenceDetail(
            input="Some text to moderate",
            results=[{"flagged": True, "categories": {"violence": True}}],
            flagged=True,
            categories={"violence": True, "hate": False},
            category_scores={"violence": 0.9, "hate": 0.1}
        )
        assert detail.flagged is True
        assert detail.categories["violence"] is True
        assert detail.category_scores["violence"] == 0.9

    def test_safe_content(self):
        """Test moderation detail with safe content."""
        detail = ModerationInferenceDetail(
            input="Safe text",
            results=[{"flagged": False}],
            flagged=False,
            categories={},
            category_scores={}
        )
        assert detail.flagged is False


class TestEnhancedInferenceDetailResponse:
    """Test EnhancedInferenceDetailResponse schema."""

    def test_chat_inference_response(self):
        """Test response for chat inference."""
        response = EnhancedInferenceDetailResponse(
            object="inference_detail",
            inference_id=uuid4(),
            timestamp=datetime.now(),
            model_name="gpt-4",
            model_provider="openai",
            model_id=uuid4(),
            messages=[{"role": "user", "content": "Hello"}],
            output="Hi there!",
            input_tokens=5,
            output_tokens=3,
            response_time_ms=100,
            request_arrival_time=datetime.now(),
            request_forward_time=datetime.now(),
            project_id=uuid4(),
            endpoint_id=uuid4(),
            is_success=True,
            cached=False,
            feedback_count=0,
            endpoint_type="chat"
        )
        assert response.endpoint_type == "chat"
        assert response.embedding_details is None

    def test_embedding_inference_response(self):
        """Test response for embedding inference."""
        embedding_detail = EmbeddingInferenceDetail(
            embeddings=[[0.1, 0.2]],
            embedding_dimensions=2,
            input_count=1,
            input_text="test"
        )

        response = EnhancedInferenceDetailResponse(
            object="inference_detail",
            inference_id=uuid4(),
            timestamp=datetime.now(),
            model_name="text-embedding-ada-002",
            model_provider="openai",
            model_id=uuid4(),
            messages=[],
            output="",
            input_tokens=5,
            output_tokens=0,
            response_time_ms=50,
            request_arrival_time=datetime.now(),
            request_forward_time=datetime.now(),
            project_id=uuid4(),
            endpoint_id=uuid4(),
            is_success=True,
            cached=False,
            feedback_count=0,
            endpoint_type="embedding",
            embedding_details=embedding_detail
        )
        assert response.endpoint_type == "embedding"
        assert response.embedding_details is not None
        assert response.embedding_details.input_count == 1

    def test_multiple_type_details_allowed(self):
        """Test that multiple type details can be set (though typically only one would be)."""
        response = EnhancedInferenceDetailResponse(
            object="inference_detail",
            inference_id=uuid4(),
            timestamp=datetime.now(),
            model_name="multi-model",
            model_provider="test",
            model_id=uuid4(),
            messages=[],
            output="",
            input_tokens=0,
            output_tokens=0,
            response_time_ms=0,
            request_arrival_time=datetime.now(),
            request_forward_time=datetime.now(),
            project_id=uuid4(),
            endpoint_id=uuid4(),
            is_success=True,
            cached=False,
            feedback_count=0,
            endpoint_type="chat",
            embedding_details=EmbeddingInferenceDetail(
                embeddings=[],
                embedding_dimensions=0,
                input_count=0,
                input_text=""
            ),
            audio_details=AudioInferenceDetail(
                audio_type="transcription",
                input="",
                output=""
            )
        )
        assert response.embedding_details is not None
        assert response.audio_details is not None
