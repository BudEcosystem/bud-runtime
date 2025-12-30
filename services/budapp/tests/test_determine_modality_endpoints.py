#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for determine_modality_endpoints helper function."""

import pytest

from budapp.commons.constants import ModalityEnum, ModelEndpointEnum
from budapp.commons.helpers import determine_modality_endpoints


class TestDetermineModalityEndpoints:
    """Test suite for determine_modality_endpoints function."""

    @pytest.mark.asyncio
    async def test_llm_category_keyword(self):
        """Test LLM category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("llm")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT]

    @pytest.mark.asyncio
    async def test_mllm_category_keyword(self):
        """Test MLLM category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("mllm")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT, ModelEndpointEnum.DOCUMENT]

    @pytest.mark.asyncio
    async def test_image_category_keyword(self):
        """Test image category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("image")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_GENERATION]

    @pytest.mark.asyncio
    async def test_embedding_category_keyword(self):
        """Test embedding category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("embedding")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.EMBEDDING]

    @pytest.mark.asyncio
    async def test_text_to_speech_category_keyword(self):
        """Test text_to_speech category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("text_to_speech")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.AUDIO_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.TEXT_TO_SPEECH]

    @pytest.mark.asyncio
    async def test_speech_to_text_category_keyword(self):
        """Test speech_to_text category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("speech_to_text")

        assert result["modality"] == [ModalityEnum.AUDIO_INPUT, ModalityEnum.TEXT_OUTPUT]
        # All audio→text models get both transcription and translation endpoints
        assert result["endpoints"] == [ModelEndpointEnum.AUDIO_TRANSCRIPTION, ModelEndpointEnum.AUDIO_TRANSLATION]

    @pytest.mark.asyncio
    async def test_audio_translation_category_keyword(self):
        """Test audio_translation category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("audio_translation")

        assert result["modality"] == [ModalityEnum.AUDIO_INPUT, ModalityEnum.TEXT_OUTPUT]
        # All audio→text models get both transcription and translation endpoints
        assert result["endpoints"] == [ModelEndpointEnum.AUDIO_TRANSCRIPTION, ModelEndpointEnum.AUDIO_TRANSLATION]

    @pytest.mark.asyncio
    async def test_image_edit_category_keyword(self):
        """Test image_edit category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("image_edit")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_EDIT]

    @pytest.mark.asyncio
    async def test_image_variation_category_keyword(self):
        """Test image_variation category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("image_variation")

        assert result["modality"] == [ModalityEnum.IMAGE_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_VARIATION]

    @pytest.mark.asyncio
    async def test_llm_embedding_category_keyword(self):
        """Test llm_embedding category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("llm_embedding")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.EMBEDDING]

    @pytest.mark.asyncio
    async def test_mllm_embedding_category_keyword(self):
        """Test mllm_embedding category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("mllm_embedding")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.EMBEDDING]

    # Test comma-separated modality strings
    @pytest.mark.asyncio
    async def test_comma_separated_llm_modality(self):
        """Test comma-separated LLM modality string."""
        result = await determine_modality_endpoints("text_input, text_output")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT]

    @pytest.mark.asyncio
    async def test_comma_separated_mllm_modality(self):
        """Test comma-separated MLLM modality string (original error case)."""
        result = await determine_modality_endpoints("text_input, text_output, image_input")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT, ModelEndpointEnum.DOCUMENT]

    @pytest.mark.asyncio
    async def test_comma_separated_image_modality(self):
        """Test comma-separated image generation modality string."""
        result = await determine_modality_endpoints("text_input, image_output")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_GENERATION]

    @pytest.mark.asyncio
    async def test_comma_separated_speech_to_text_modality(self):
        """Test comma-separated speech_to_text modality string."""
        result = await determine_modality_endpoints("audio_input, text_output")

        assert result["modality"] == [ModalityEnum.AUDIO_INPUT, ModalityEnum.TEXT_OUTPUT]
        # All audio→text models get both transcription and translation endpoints
        assert result["endpoints"] == [ModelEndpointEnum.AUDIO_TRANSCRIPTION, ModelEndpointEnum.AUDIO_TRANSLATION]

    @pytest.mark.asyncio
    async def test_comma_separated_text_to_speech_modality(self):
        """Test comma-separated text_to_speech modality string."""
        result = await determine_modality_endpoints("text_input, audio_output")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.AUDIO_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.TEXT_TO_SPEECH]

    @pytest.mark.asyncio
    async def test_comma_separated_image_edit_modality(self):
        """Test comma-separated image_edit modality string."""
        result = await determine_modality_endpoints("text_input, image_input, image_output")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_EDIT]

    @pytest.mark.asyncio
    async def test_comma_separated_image_variation_modality(self):
        """Test comma-separated image_variation modality string."""
        result = await determine_modality_endpoints("image_input, image_output")

        assert result["modality"] == [ModalityEnum.IMAGE_INPUT, ModalityEnum.IMAGE_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.IMAGE_VARIATION]

    # Test different ordering and spacing
    @pytest.mark.asyncio
    async def test_comma_separated_different_order(self):
        """Test that order doesn't matter for comma-separated modality."""
        result = await determine_modality_endpoints("image_input, text_output, text_input")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT, ModelEndpointEnum.DOCUMENT]

    @pytest.mark.asyncio
    async def test_comma_separated_extra_spaces(self):
        """Test comma-separated modality with extra spaces."""
        result = await determine_modality_endpoints("text_input  ,   text_output  ,  image_input")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT, ModelEndpointEnum.DOCUMENT]

    @pytest.mark.asyncio
    async def test_comma_separated_mixed_case(self):
        """Test comma-separated modality with mixed case."""
        result = await determine_modality_endpoints("TEXT_INPUT, Text_Output, IMAGE_INPUT")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.IMAGE_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [ModelEndpointEnum.CHAT, ModelEndpointEnum.DOCUMENT]

    # Test new audio modalities
    @pytest.mark.asyncio
    async def test_audio_llm_category_keyword(self):
        """Test audio_llm category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("audio_llm")

        assert result["modality"] == [ModalityEnum.TEXT_INPUT, ModalityEnum.AUDIO_INPUT, ModalityEnum.TEXT_OUTPUT]
        assert result["endpoints"] == [
            ModelEndpointEnum.CHAT,
            ModelEndpointEnum.AUDIO_TRANSCRIPTION,
            ModelEndpointEnum.AUDIO_TRANSLATION,
        ]

    @pytest.mark.asyncio
    async def test_audio_llm_tts_category_keyword(self):
        """Test audio_llm_tts category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("audio_llm_tts")

        assert result["modality"] == [
            ModalityEnum.TEXT_INPUT,
            ModalityEnum.AUDIO_INPUT,
            ModalityEnum.TEXT_OUTPUT,
            ModalityEnum.AUDIO_OUTPUT,
        ]
        assert result["endpoints"] == [
            ModelEndpointEnum.CHAT,
            ModelEndpointEnum.AUDIO_TRANSCRIPTION,
            ModelEndpointEnum.AUDIO_TRANSLATION,
            ModelEndpointEnum.TEXT_TO_SPEECH,
        ]

    @pytest.mark.asyncio
    async def test_omni_category_keyword(self):
        """Test omni category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("omni")

        assert result["modality"] == [
            ModalityEnum.TEXT_INPUT,
            ModalityEnum.AUDIO_INPUT,
            ModalityEnum.IMAGE_INPUT,
            ModalityEnum.TEXT_OUTPUT,
        ]
        assert result["endpoints"] == [
            ModelEndpointEnum.CHAT,
            ModelEndpointEnum.DOCUMENT,
            ModelEndpointEnum.AUDIO_TRANSCRIPTION,
            ModelEndpointEnum.AUDIO_TRANSLATION,
        ]

    @pytest.mark.asyncio
    async def test_omni_tts_category_keyword(self):
        """Test omni_tts category keyword returns correct modality and endpoints."""
        result = await determine_modality_endpoints("omni_tts")

        assert result["modality"] == [
            ModalityEnum.TEXT_INPUT,
            ModalityEnum.AUDIO_INPUT,
            ModalityEnum.IMAGE_INPUT,
            ModalityEnum.TEXT_OUTPUT,
            ModalityEnum.AUDIO_OUTPUT,
        ]
        assert result["endpoints"] == [
            ModelEndpointEnum.CHAT,
            ModelEndpointEnum.DOCUMENT,
            ModelEndpointEnum.AUDIO_TRANSCRIPTION,
            ModelEndpointEnum.AUDIO_TRANSLATION,
            ModelEndpointEnum.TEXT_TO_SPEECH,
        ]

    # Test error cases
    @pytest.mark.asyncio
    async def test_invalid_category_keyword(self):
        """Test that invalid category keyword raises ValueError."""
        with pytest.raises(ValueError, match="Invalid modality"):
            await determine_modality_endpoints("invalid_modality")

    @pytest.mark.asyncio
    async def test_invalid_comma_separated_combination(self):
        """Test that invalid comma-separated combination raises ValueError."""
        with pytest.raises(ValueError, match="Invalid modality value"):
            await determine_modality_endpoints("text_input, video_output")

    @pytest.mark.asyncio
    async def test_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid modality"):
            await determine_modality_endpoints("")

    @pytest.mark.asyncio
    async def test_incomplete_comma_separated(self):
        """Test that incomplete comma-separated modality raises ValueError."""
        with pytest.raises(ValueError, match="Invalid modality"):
            await determine_modality_endpoints("text_input")
