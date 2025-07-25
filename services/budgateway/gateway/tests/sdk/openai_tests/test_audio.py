import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv
import tempfile
import json
from pathlib import Path

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3000")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Clients
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)

# Test audio file path
AUDIO_SAMPLE_PATH = Path(__file__).parent / "fixtures" / "audio_samples" / "sample.mp3"


class TestAudioTranscription:
    """Test audio transcription endpoint compatibility"""

    def test_basic_transcription(self):
        """Test basic audio transcription"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            # TensorZero request
            tz_response = tensorzero_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json"
            )
        
        # Verify response structure
        assert isinstance(tz_response.text, str)
        assert len(tz_response.text) > 0

    def test_transcription_with_parameters(self):
        """Test transcription with various parameters"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            response = tensorzero_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json",
                language="en",
                prompt="This is a music file",
                temperature=0.2
            )
        
        assert isinstance(response.text, str)

    def test_transcription_response_formats(self):
        """Test different response formats"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        formats = ["json", "text", "verbose_json"]
        
        for format_type in formats:
            with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
                if format_type == "text":
                    # For text format, the response is a string
                    response = tensorzero_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                    assert isinstance(response, str)
                else:
                    response = tensorzero_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format=format_type
                    )
                    assert hasattr(response, 'text')
                    
                    if format_type == "verbose_json":
                        # Verbose format includes additional fields
                        assert hasattr(response, 'duration')
                        assert hasattr(response, 'language')

    def test_transcription_with_timestamp_granularities(self):
        """Test transcription with timestamp granularities"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            response = tensorzero_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"]
            )
        
        assert hasattr(response, 'text')
        if hasattr(response, 'words'):
            assert isinstance(response.words, list)
        if hasattr(response, 'segments'):
            assert isinstance(response.segments, list)

    @pytest.mark.asyncio
    async def test_async_transcription(self):
        """Test async audio transcription"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            response = await async_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        
        assert isinstance(response.text, str)


class TestAudioTranslation:
    """Test audio translation endpoint compatibility"""

    def test_basic_translation(self):
        """Test basic audio translation to English"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            # TensorZero request
            tz_response = tensorzero_client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
                response_format="json"
            )
        
        # Verify response structure
        assert isinstance(tz_response.text, str)
        assert len(tz_response.text) > 0

    def test_translation_with_parameters(self):
        """Test translation with various parameters"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
            response = tensorzero_client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
                response_format="json",
                prompt="Translate this audio to English",
                temperature=0.2
            )
        
        assert isinstance(response.text, str)

    def test_translation_response_formats(self):
        """Test different response formats for translation"""
        if not AUDIO_SAMPLE_PATH.exists():
            pytest.skip("Audio sample file not found")
        
        formats = ["json", "text", "verbose_json"]
        
        for format_type in formats:
            with open(AUDIO_SAMPLE_PATH, "rb") as audio_file:
                if format_type == "text":
                    response = tensorzero_client.audio.translations.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                    assert isinstance(response, str)
                else:
                    response = tensorzero_client.audio.translations.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format=format_type
                    )
                    assert hasattr(response, 'text')


class TestTextToSpeech:
    """Test text-to-speech endpoint compatibility"""

    def test_basic_tts(self):
        """Test basic text-to-speech generation"""
        text = "Hello, this is a test of text to speech."
        
        # TensorZero request
        response = tensorzero_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # Response should be audio bytes
        audio_data = response.read()
        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 0
        
        # Optionally save to file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        # Verify file was created
        assert os.path.exists(temp_path)
        assert os.path.getsize(temp_path) > 0
        
        # Cleanup
        os.unlink(temp_path)

    def test_tts_different_voices(self):
        """Test TTS with different voice options"""
        text = "Testing different voices"
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        
        for voice in voices:
            response = tensorzero_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            audio_data = response.read()
            assert len(audio_data) > 0

    def test_tts_different_formats(self):
        """Test TTS with different output formats"""
        text = "Testing different audio formats"
        formats = ["mp3", "opus", "aac", "flac"]
        
        for audio_format in formats:
            response = tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format=audio_format
            )
            
            audio_data = response.read()
            assert len(audio_data) > 0

    def test_tts_with_speed(self):
        """Test TTS with different speed settings"""
        text = "Testing speech at different speeds"
        speeds = [0.25, 1.0, 2.0, 4.0]
        
        for speed in speeds:
            response = tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                speed=speed
            )
            
            audio_data = response.read()
            assert len(audio_data) > 0

    def test_tts_hd_model(self):
        """Test TTS with HD model"""
        text = "Testing high definition text to speech"
        
        response = tensorzero_client.audio.speech.create(
            model="tts-1-hd",
            voice="alloy",
            input=text
        )
        
        audio_data = response.read()
        assert len(audio_data) > 0

    def test_tts_long_text(self):
        """Test TTS with longer text"""
        long_text = " ".join(["This is a longer text for testing."] * 20)
        
        response = tensorzero_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=long_text
        )
        
        audio_data = response.read()
        assert len(audio_data) > 0

    def test_tts_special_characters(self):
        """Test TTS with special characters and unicode"""
        texts = [
            "Testing with numbers: 123, 456, 789",
            "Testing with punctuation! Question? Yes.",
            "Testing with emojis 🎉 (should be handled gracefully)",
            "Testing with accents: café, naïve, résumé"
        ]
        
        for text in texts:
            response = tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            
            audio_data = response.read()
            assert len(audio_data) > 0

    @pytest.mark.asyncio
    async def test_async_tts(self):
        """Test async text-to-speech"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        text = "Async TTS test"
        
        response = await async_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        audio_data = await response.aread()
        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 0

    def test_tts_error_handling(self):
        """Test TTS error handling"""
        # Empty input
        with pytest.raises(Exception):
            tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=""
            )
        
        # Invalid voice
        with pytest.raises(Exception):
            tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="invalid-voice",
                input="Test"
            )
        
        # Invalid speed
        with pytest.raises(Exception):
            tensorzero_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input="Test",
                speed=5.0  # Max is 4.0
            )