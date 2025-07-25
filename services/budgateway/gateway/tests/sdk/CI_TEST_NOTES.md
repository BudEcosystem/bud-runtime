# CI Test Notes

## Dummy Provider Behavior

The dummy provider is designed for testing and has specific behaviors that tests need to accommodate:

### Chat Models
- **gpt-3.5-turbo**: Configured with `model_name = "json"` → Returns `{"answer":"Hello"}`
- **gpt-4**: Configured with `model_name = "test"` → Returns Megumin story

### Image Models
- Default behavior: Returns URLs like `https://example.com/dummy-image-{uuid}.png`
- With `response_format="b64_json"`: Returns base64-encoded 1x1 transparent PNG
- All models (dall-e-2, dall-e-3, gpt-image-1) configured with `model_name = "image"`

### Key Differences from Real Providers
1. **No input validation**: Empty messages, invalid parameters are accepted
2. **Fixed responses**: Content doesn't change based on input
3. **Simplified error handling**: Only model existence is validated

## Test Files

- `test_ci_basic.py`: Comprehensive CI tests covering all endpoints
- `test_ci_chat.py`: Chat-specific tests adapted for dummy provider
- `test_ci_images.py`: Image endpoint tests with URL/base64 handling
- `test_*.py`: Full integration tests requiring real API keys

## Running CI Tests

```bash
# With gateway running on port 3001 with test_config_ci.toml:
pytest test_ci_basic.py -v
pytest test_ci_chat.py -v
pytest test_ci_images.py -v
```

## Common Issues

1. **Tests expecting specific content**: Dummy provider returns fixed content
2. **Base64 vs URL responses**: Use `response_format="b64_json"` for base64
3. **Validation differences**: Dummy provider is more permissive than real APIs