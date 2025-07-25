# Audio API

TensorZero provides OpenAI-compatible audio endpoints for speech-to-text (transcription and translation) and text-to-speech capabilities.

## Authentication

All audio endpoints follow the same authentication pattern as other OpenAI-compatible endpoints. When authentication is enabled in your gateway configuration, you must provide a valid API key in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### Audio Transcription

Convert audio files to text in the original language.

**Endpoint:** `POST /v1/audio/transcriptions`

**Request:** Multipart form data with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | file | Yes | The audio file to transcribe. Supported formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm. Max size: 25MB |
| model | string | Yes | ID of the model to use (e.g., `whisper-1`, `gpt-4o-transcribe`) |
| language | string | No | The language of the input audio in ISO-639-1 format |
| prompt | string | No | Optional text to guide the model's style or continue a previous audio segment |
| response_format | string | No | Format of the response. Options: `json` (default), `text`, `srt`, `verbose_json`, `vtt` |
| temperature | float | No | Sampling temperature between 0 and 1. Default: 0 |
| timestamp_granularities[] | array | No | Timestamp granularities to populate. Options: `word`, `segment`. Requires `verbose_json` format |

**Example Request:**
```bash
curl -X POST https://api.tensorzero.com/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "language=en" \
  -F "response_format=json"
```

**Response (JSON format):**
```json
{
  "text": "Hello, this is a transcription of the audio file."
}
```

**Response (verbose_json format):**
```json
{
  "text": "Hello, this is a transcription of the audio file.",
  "language": "en",
  "duration": 5.2,
  "words": [
    {
      "word": "Hello",
      "start": 0.0,
      "end": 0.5
    },
    ...
  ],
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 5.2,
      "text": "Hello, this is a transcription of the audio file.",
      "tokens": [15339, 11, 428, 318, 257, ...],
      "temperature": 0.0,
      "avg_logprob": -0.2,
      "compression_ratio": 1.2,
      "no_speech_prob": 0.01
    }
  ]
}
```

### Audio Translation

Convert audio files to English text.

**Endpoint:** `POST /v1/audio/translations`

**Request:** Multipart form data with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | file | Yes | The audio file to translate. Same format support as transcription |
| model | string | Yes | ID of the model to use |
| prompt | string | No | Optional text to guide the model's style |
| response_format | string | No | Format of the response. Options: `json` (default), `text`, `srt`, `verbose_json`, `vtt` |
| temperature | float | No | Sampling temperature between 0 and 1. Default: 0 |

**Example Request:**
```bash
curl -X POST https://api.tensorzero.com/v1/audio/translations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@german_audio.mp3" \
  -F "model=whisper-1"
```

**Response:**
```json
{
  "text": "Hello, this is the English translation of the German audio."
}
```

### Text-to-Speech

Generate audio from text input.

**Endpoint:** `POST /v1/audio/speech`

**Request:** JSON body with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| model | string | Yes | ID of the model to use (e.g., `tts-1`, `tts-1-hd`) |
| input | string | Yes | The text to generate audio for. Max length: 4,096 characters |
| voice | string | Yes | The voice to use. Options: `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse` |
| response_format | string | No | Audio format. Options: `mp3` (default), `opus`, `aac`, `flac`, `wav`, `pcm` |
| speed | float | No | Speed of generated audio. Range: 0.25 to 4.0. Default: 1.0 |

**Example Request:**
```bash
curl -X POST https://api.tensorzero.com/v1/audio/speech \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Hello, this is a test of text-to-speech.",
    "voice": "alloy",
    "response_format": "mp3"
  }' \
  --output speech.mp3
```

**Response:** Binary audio data in the requested format

## Model Configuration

Audio models must be configured in your `tensorzero.toml` file with the appropriate endpoint capabilities:

```toml
# Speech-to-text models
[models."whisper-1"]
routing = ["openai"]
endpoints = ["audio_transcription", "audio_translation"]

[models."whisper-1".providers.openai]
type = "openai"
model_name = "whisper-1"

# Text-to-speech models
[models."tts-1"]
routing = ["openai"]
endpoints = ["text_to_speech"]

[models."tts-1".providers.openai]
type = "openai"
model_name = "tts-1"
```

## Supported Models

### Speech-to-Text (Transcription & Translation)
- `whisper-1` - OpenAI's Whisper model
- `gpt-4o-transcribe` - GPT-4 Omni model with transcription capabilities
- `gpt-4o-mini-transcribe` - GPT-4 Omni Mini with transcription capabilities

### Text-to-Speech
- `tts-1` - Optimized for speed
- `tts-1-hd` - Optimized for quality
- `gpt-4o-mini-tts` - GPT-4 Omni Mini with TTS capabilities

## Error Handling

The API returns standard HTTP status codes:

- `400 Bad Request` - Invalid request parameters, unsupported format, or file too large
- `401 Unauthorized` - Invalid or missing API key
- `404 Not Found` - Model not found or doesn't support the requested capability
- `500 Internal Server Error` - Server error during processing

Error responses include a JSON body with details:
```json
{
  "error": {
    "message": "File size exceeds 25MB limit",
    "type": "invalid_request"
  }
}
```

## Rate Limiting

Audio endpoints are subject to the same rate limiting as configured for your gateway. Due to the processing-intensive nature of audio operations, consider setting appropriate rate limits for these endpoints.

## Caching

Audio endpoints do not support caching by default, as audio processing typically involves unique inputs that are unlikely to benefit from caching.

## Best Practices

1. **File Size**: Keep audio files under 25MB for optimal performance
2. **Audio Quality**: Use high-quality audio recordings for better transcription accuracy
3. **Language Hints**: Provide the `language` parameter for transcription when known
4. **Prompts**: Use prompts to maintain consistency across multiple audio segments
5. **Response Format**: Choose the appropriate response format based on your needs:
   - Use `text` for simple transcription needs
   - Use `verbose_json` when you need timestamps or detailed metadata
   - Use `srt` or `vtt` for subtitle generation
6. **Voice Selection**: Experiment with different voices for TTS to find the best match for your use case
7. **Speed Adjustment**: Use the `speed` parameter to adjust speech rate without affecting pitch

## Streaming Support

Currently, the audio endpoints do not support streaming responses. For real-time transcription needs, consider using WebSockets or Server-Sent Events with chunked audio processing (not yet implemented).

## Examples

### Python Example - Transcription
```python
import requests

url = "https://api.tensorzero.com/v1/audio/transcriptions"
headers = {"Authorization": "Bearer YOUR_API_KEY"}
files = {"file": open("audio.mp3", "rb")}
data = {
    "model": "whisper-1",
    "response_format": "verbose_json",
    "timestamp_granularities[]": ["word", "segment"]
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()
print(f"Transcription: {result['text']}")
```

### Python Example - Text-to-Speech
```python
import requests

url = "https://api.tensorzero.com/v1/audio/speech"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "model": "tts-1",
    "input": "Hello from TensorZero!",
    "voice": "nova",
    "speed": 1.1
}

response = requests.post(url, headers=headers, json=data)
with open("output.mp3", "wb") as f:
    f.write(response.content)
```

### Node.js Example - Translation
```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('foreign_audio.mp3'));
form.append('model', 'whisper-1');

fetch('https://api.tensorzero.com/v1/audio/translations', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    ...form.getHeaders()
  },
  body: form
})
.then(res => res.json())
.then(data => console.log('Translation:', data.text));
```