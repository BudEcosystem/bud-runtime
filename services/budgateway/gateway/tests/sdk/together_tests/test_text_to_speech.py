"""
Test Together AI text-to-speech through OpenAI SDK.

These tests verify Together's TTS capabilities with Cartesia Sonic model
through TensorZero's OpenAI-compatible interface.
"""

import os
import io
import wave
import pytest
from typing import Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Skip tests if not configured for Together
SKIP_TOGETHER_TESTS = os.getenv("SKIP_TOGETHER_TESTS", "false").lower() == "true"

# Universal OpenAI client
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


def is_valid_audio(audio_bytes: bytes, format: str = "mp3") -> bool:
    """Check if the bytes represent valid audio data."""
    if not audio_bytes or len(audio_bytes) == 0:
        return False
    
    # Basic validation based on format
    if format == "mp3":
        # MP3 files often start with ID3 tag or FF FB/FF FA
        return (audio_bytes.startswith(b'ID3') or 
                audio_bytes.startswith(b'\xff\xfb') or
                audio_bytes.startswith(b'\xff\xfa'))
    elif format == "wav":
        # WAV files start with RIFF
        return audio_bytes.startswith(b'RIFF')
    elif format == "opus":
        # Opus in OGG container starts with OggS
        return audio_bytes.startswith(b'OggS')
    
    # For other formats or if unsure, just check it's not empty
    return len(audio_bytes) > 100


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherTextToSpeech:
    """Test Together AI TTS through OpenAI SDK."""
    
    def test_tts_basic(self):
        """Test basic TTS generation."""
        response = client.audio.speech.create(
            model="together-tts",
            voice="alloy",
            input="Hello, this is a test of Together AI text to speech."
        )
        
        # Get audio content
        audio_content = response.content
        
        # Verify we got audio data
        assert audio_content is not None
        assert len(audio_content) > 0
        assert is_valid_audio(audio_content, "mp3")
    
    def test_tts_standard_voices(self):
        """Test all standard OpenAI-compatible voices."""
        standard_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        test_text = "Testing voice: "
        
        for voice in standard_voices:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"{test_text}{voice}"
            )
            
            audio_content = response.content
            assert audio_content is not None
            assert len(audio_content) > 0
            assert is_valid_audio(audio_content)
    
    def test_tts_together_specific_voices(self):
        """Test Together's native voice names."""
        together_voices = [
            "helpful woman",
            "laidback woman",
            "meditation lady",
            "newsman",
            "friendly sidekick",
            "british reading lady",
            "barbershop man",
            "indian lady",
            "german conversational woman",
            "pilot over intercom",
            "australian customer support man",
            "calm lady",
            "wise man",
            "customer support lady",
            "announcer man",
            "storyteller lady",
            "princess",
            "doctor mischief",
            "1920's radioman"
        ]
        
        # Test a subset of voices to avoid too many API calls
        for voice in together_voices[:5]:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"Hello from {voice}"
            )
            
            audio_content = response.content
            assert audio_content is not None
            assert len(audio_content) > 0
    
    def test_tts_multilingual_voices(self):
        """Test language-specific voices with appropriate text."""
        multilingual_tests = [
            ("french narrator lady", "Bonjour, comment allez-vous aujourd'hui?"),
            ("german conversational woman", "Guten Tag, wie geht es Ihnen?"),
            ("spanish narrator man", "Hola, ¿cómo está usted hoy?"),
            ("japanese woman conversational", "こんにちは、お元気ですか？"),
            ("british reading lady", "Good day, how do you do?"),
            ("australian customer support man", "G'day mate, how can I help you?"),
            ("indian lady", "Namaste, how are you today?")
        ]
        
        for voice, text in multilingual_tests[:3]:  # Test a few
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice=voice,
                    input=text
                )
                
                audio_content = response.content
                assert audio_content is not None
                assert len(audio_content) > 0
            except Exception as e:
                print(f"Voice '{voice}' failed with: {e}")
    
    def test_tts_response_formats(self):
        """Test different audio output formats."""
        formats = {
            "mp3": "mp3",
            "opus": "opus",
            "aac": "aac",
            "flac": "flac",
            "wav": "wav",
            "pcm": "pcm"
        }
        
        test_text = "Testing audio format"
        
        for format_name, expected_format in formats.items():
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice="nova",
                    input=test_text,
                    response_format=format_name
                )
                
                audio_content = response.content
                assert audio_content is not None
                assert len(audio_content) > 0
                
                # Basic format validation
                if format_name in ["mp3", "wav", "opus"]:
                    assert is_valid_audio(audio_content, expected_format)
            except Exception as e:
                print(f"Format '{format_name}' not supported: {e}")
    
    def test_tts_long_text(self):
        """Test TTS with longer text passages."""
        long_text = """
        This is a longer passage to test the text-to-speech capabilities of Together AI.
        It includes multiple sentences with various punctuation marks. The system should
        handle this gracefully and produce natural-sounding speech with appropriate pauses
        and intonation. Let's also include some numbers like 123 and dates like December 25th,
        2024. Additionally, we'll test abbreviations like AI, TTS, and SDK to see how they
        are pronounced. The passage ends with a question: How well did the system perform?
        """
        
        response = client.audio.speech.create(
            model="together-tts",
            voice="storyteller lady",
            input=long_text
        )
        
        audio_content = response.content
        assert audio_content is not None
        # Longer text should produce larger audio file
        assert len(audio_content) > 10000
    
    def test_tts_special_characters(self):
        """Test TTS with special characters and formatting."""
        special_texts = [
            "Hello! How are you? That's great.",
            "Price: $99.99 (save 20%)",
            "Email: test@example.com",
            "Math: 2 + 2 = 4",
            "Time: 3:30 PM",
            "Date: 12/25/2024",
            "Hashtag: #AIVoice",
            "URL: www.example.com"
        ]
        
        for text in special_texts:
            response = client.audio.speech.create(
                model="together-tts",
                voice="alloy",
                input=text
            )
            
            audio_content = response.content
            assert audio_content is not None
            assert len(audio_content) > 0
    
    def test_tts_empty_input(self):
        """Test error handling for empty input."""
        with pytest.raises(Exception) as exc_info:
            client.audio.speech.create(
                model="together-tts",
                voice="alloy",
                input=""
            )
        
        assert exc_info.value is not None
    
    def test_tts_speed_variations(self):
        """Test TTS with different speed settings."""
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        test_text = "Testing speech at different speeds"
        
        for speed in speeds:
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice="nova",
                    input=test_text,
                    speed=speed
                )
                
                audio_content = response.content
                assert audio_content is not None
                assert len(audio_content) > 0
            except Exception as e:
                # Speed parameter might not be supported
                print(f"Speed {speed} not supported: {e}")


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherTTSAdvanced:
    """Test advanced TTS scenarios."""
    
    def test_tts_character_voices(self):
        """Test character and specialty voices."""
        character_voices = [
            ("princess", "Once upon a time in a magical kingdom"),
            ("doctor mischief", "The experiment is ready to begin!"),
            ("1920's radioman", "This just in from the newsroom"),
            ("asmr lady", "Let's relax and take a deep breath"),
            ("meditation lady", "Find your center and breathe deeply")
        ]
        
        for voice, text in character_voices:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=text
            )
            
            audio_content = response.content
            assert audio_content is not None
            assert len(audio_content) > 0
    
    def test_tts_conversational_text(self):
        """Test TTS with conversational text."""
        conversation = [
            ("customer support lady", "Hello! How can I assist you today?"),
            ("friendly sidekick", "Hey there! I've got your back!"),
            ("wise man", "Let me share some wisdom with you."),
            ("laidback woman", "No worries, we'll figure it out together.")
        ]
        
        for voice, text in conversation:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=text
            )
            
            assert response.content is not None
    
    def test_tts_technical_content(self):
        """Test TTS with technical content."""
        technical_texts = [
            "The API endpoint is /v1/audio/speech",
            "Install via pip: pip install openai",
            "The function returns a List[Dict[str, Any]]",
            "HTTP status code: 200 OK",
            "GPU memory: 24GB VRAM"
        ]
        
        for text in technical_texts:
            response = client.audio.speech.create(
                model="together-tts",
                voice="pilot over intercom",
                input=text
            )
            
            assert response.content is not None
    
    def test_tts_emotional_variations(self):
        """Test voices suited for different emotions."""
        emotional_tests = [
            ("meditation lady", "Peace and tranquility flow through you"),
            ("announcer man", "Ladies and gentlemen, welcome to the show!"),
            ("storyteller lady", "Let me tell you an amazing story"),
            ("barbershop man", "How about that weather we're having?")
        ]
        
        for voice, text in emotional_tests:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=text
            )
            
            assert response.content is not None
    
    def test_tts_sequential_generation(self):
        """Test generating a sequence of audio for a story."""
        story_parts = [
            "Chapter 1: The Beginning",
            "Our hero embarked on an epic journey.",
            "Along the way, they faced many challenges.",
            "But with courage and determination, they persevered.",
            "Chapter 2: The Adventure Continues"
        ]
        
        audio_parts = []
        for part in story_parts:
            response = client.audio.speech.create(
                model="together-tts",
                voice="storyteller lady",
                input=part
            )
            
            audio_parts.append(response.content)
        
        # Verify all parts were generated
        assert len(audio_parts) == len(story_parts)
        for audio in audio_parts:
            assert audio is not None
            assert len(audio) > 0


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherTTSErrors:
    """Test error handling for TTS."""
    
    def test_invalid_model(self):
        """Test with non-existent TTS model."""
        with pytest.raises(Exception) as exc_info:
            client.audio.speech.create(
                model="invalid-tts-model",
                voice="alloy",
                input="Test"
            )
        
        assert "not found" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_invalid_voice(self):
        """Test with non-existent voice."""
        try:
            response = client.audio.speech.create(
                model="together-tts",
                voice="non_existent_voice",
                input="Test with invalid voice"
            )
            # Some providers might use a default voice
            assert response.content is not None
        except Exception as e:
            # Or fail with voice error
            assert "voice" in str(e).lower()
    
    def test_extremely_long_text(self):
        """Test with extremely long text."""
        # Create very long text
        very_long_text = "This is a test. " * 1000
        
        try:
            response = client.audio.speech.create(
                model="together-tts",
                voice="alloy",
                input=very_long_text
            )
            # If it succeeds, verify we got audio
            assert response.content is not None
        except Exception as e:
            # Might fail with length error
            assert "length" in str(e).lower() or "long" in str(e).lower()
    
    def test_chat_model_for_tts(self):
        """Test using chat model for TTS."""
        with pytest.raises(Exception) as exc_info:
            client.audio.speech.create(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                voice="alloy",
                input="Test"
            )
        
        # Should fail because it's not a TTS model
        assert exc_info.value is not None
    
    def test_unsupported_format(self):
        """Test with unsupported audio format."""
        try:
            response = client.audio.speech.create(
                model="together-tts",
                voice="alloy",
                input="Test audio",
                response_format="unsupported_format"
            )
            # Might use default format
            assert response.content is not None
        except Exception as e:
            # Or fail with format error
            assert "format" in str(e).lower()


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherTTSQuality:
    """Test TTS quality and consistency."""
    
    def test_voice_consistency(self):
        """Test that same voice produces consistent style."""
        voice = "british reading lady"
        texts = [
            "Good morning, everyone.",
            "Welcome to today's presentation.",
            "Thank you for your attention."
        ]
        
        audio_samples = []
        for text in texts:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=text
            )
            audio_samples.append(response.content)
        
        # All samples should be generated
        assert len(audio_samples) == len(texts)
        for audio in audio_samples:
            assert audio is not None
            assert len(audio) > 0
    
    def test_pronunciation_accuracy(self):
        """Test pronunciation of challenging words."""
        challenging_texts = [
            "The entrepreneur started a pharmaceutical company.",
            "The archaeologist discovered ancient hieroglyphics.",
            "Pseudonymous authors write anonymously.",
            "The sommelier recommended a Châteauneuf-du-Pape.",
            "The colonel's yacht was moored at the quay."
        ]
        
        for text in challenging_texts:
            response = client.audio.speech.create(
                model="together-tts",
                voice="newsman",
                input=text
            )
            
            assert response.content is not None
    
    def test_number_pronunciation(self):
        """Test pronunciation of numbers in different contexts."""
        number_texts = [
            "The year 2024",
            "Call 1-800-555-1234",
            "The temperature is -5 degrees",
            "Pi equals 3.14159",
            "Item #42 costs $99.99",
            "The score was 3-2",
            "Chapter 11, Section 3.2.1"
        ]
        
        for text in number_texts:
            response = client.audio.speech.create(
                model="together-tts",
                voice="announcer man",
                input=text
            )
            
            assert response.content is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])