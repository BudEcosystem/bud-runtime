# Images API

The TensorZero Images API provides OpenAI-compatible endpoints for image generation, editing, and creating variations. This allows you to use TensorZero as a drop-in replacement for OpenAI's image endpoints while benefiting from TensorZero's unified model management, routing, and observability features.

## Overview

The Images API includes three main endpoints:

- **Image Generation** (`/v1/images/generations`) - Generate images from text prompts
- **Image Edit** (`/v1/images/edits`) - Edit existing images based on text prompts
- **Image Variations** (`/v1/images/variations`) - Create variations of existing images

## Authentication

When gateway authentication is enabled, include your API key in the `Authorization` header:

```bash
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### Create Image

Generate images from a text prompt.

**Endpoint:** `POST /v1/images/generations`

#### Request Body

```json
{
  "model": "dall-e-3",
  "prompt": "A white siamese cat",
  "n": 1,
  "size": "1024x1024",
  "quality": "standard",
  "style": "natural",
  "response_format": "url",
  "background": "transparent",
  "moderation": "auto",
  "output_format": "png",
  "user": "user-123"
}
```

#### Parameters

- **model** (string, required): The model to use for image generation (e.g., "dall-e-2", "dall-e-3")
- **prompt** (string, required): A text description of the desired image(s). Maximum length is 4000 characters for dall-e-3 and 1000 characters for dall-e-2
- **n** (integer, optional): The number of images to generate. Must be between 1 and 10. Defaults to 1
- **size** (string, optional): The size of the generated images. Must be one of:
  - `256x256`
  - `512x512` 
  - `1024x1024` (default)
  - `1024x1792` (dall-e-3 only)
  - `1792x1024` (dall-e-3 only)
- **quality** (string, optional): The quality of the image. Must be one of:
  - `standard` (default)
  - `hd` (dall-e-3 only)
- **style** (string, optional): The style of the generated images. Must be one of:
  - `vivid` (default for dall-e-3)
  - `natural`
- **response_format** (string, optional): The format in which the generated images are returned:
  - `url` (default) - Returns URLs to the generated images
  - `b64_json` - Returns the generated images as base64 encoded JSON strings
- **background** (string, optional): Background transparency setting:
  - `transparent`
  - `white`
  - `auto` (default)
- **moderation** (string, optional): Content moderation setting:
  - `none`
  - `low`
  - `auto` (default)
- **output_format** (string, optional): Output image format:
  - `png` (default)
  - `jpeg`
  - `webp`
- **user** (string, optional): A unique identifier representing your end-user

#### Response

```json
{
  "created": 1589478378,
  "data": [
    {
      "url": "https://example.com/image.png",
      "revised_prompt": "A white Siamese cat with bright blue eyes sitting elegantly"
    }
  ]
}
```

#### Response Fields

- **created** (integer): Unix timestamp of when the image(s) were created
- **data** (array): Array of image objects
  - **url** (string): The URL of the generated image (when response_format is "url")
  - **b64_json** (string): The base64-encoded JSON of the generated image (when response_format is "b64_json")
  - **revised_prompt** (string, optional): The revised prompt used to generate the image (dall-e-3 only)

### Edit Image

Create an edited or extended image given an original image and a prompt.

**Endpoint:** `POST /v1/images/edits`

#### Request (Multipart Form Data)

```bash
curl -X POST https://gateway.tensorzero.com/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F model="dall-e-2" \
  -F image="@/path/to/image.png" \
  -F mask="@/path/to/mask.png" \
  -F prompt="Add a red bow tie to the cat" \
  -F n=1 \
  -F size="1024x1024"
```

#### Parameters

- **model** (string, required): The model to use for image editing (e.g., "dall-e-2")
- **image** (file, required): The image to edit. Must be a valid PNG file, less than 4MB, and square
- **mask** (file, optional): An additional image whose fully transparent areas indicate where image should be edited. Must be a valid PNG file, less than 4MB, and have the same dimensions as image
- **prompt** (string, required): A text description of the desired edit. Maximum length is 1000 characters
- **n** (integer, optional): The number of images to generate. Must be between 1 and 10. Defaults to 1
- **size** (string, optional): The size of the generated images. Must be one of:
  - `256x256`
  - `512x512`
  - `1024x1024` (default)
- **response_format** (string, optional): The format in which the generated images are returned:
  - `url` (default)
  - `b64_json`
- **background** (string, optional): Background transparency setting
- **quality** (string, optional): Image quality setting
- **output_format** (string, optional): Output image format
- **user** (string, optional): A unique identifier representing your end-user

#### Response

Same format as the image generation endpoint.

### Create Image Variation

Create a variation of a given image.

**Endpoint:** `POST /v1/images/variations`

#### Request (Multipart Form Data)

```bash
curl -X POST https://gateway.tensorzero.com/v1/images/variations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F model="dall-e-2" \
  -F image="@/path/to/image.png" \
  -F n=2 \
  -F size="1024x1024"
```

#### Parameters

- **model** (string, required): The model to use for creating variations (e.g., "dall-e-2")
- **image** (file, required): The image to use as the basis for the variation(s). Must be a valid PNG file, less than 4MB, and square
- **n** (integer, optional): The number of images to generate. Must be between 1 and 10. Defaults to 1
- **size** (string, optional): The size of the generated images. Must be one of:
  - `256x256`
  - `512x512`
  - `1024x1024` (default)
- **response_format** (string, optional): The format in which the generated images are returned:
  - `url` (default)
  - `b64_json`
- **output_format** (string, optional): Output image format
- **user** (string, optional): A unique identifier representing your end-user

#### Response

Same format as the image generation endpoint, but without the `revised_prompt` field.

## Model Configuration

To use the Images API, configure your models with the appropriate image capabilities in your `tensorzero.toml`:

```toml
[models."dall-e-3"]
routing = ["openai"]
endpoints = ["image_generation"]

[models."dall-e-3".providers.openai]
type = "openai"
model_name = "dall-e-3"
api_key_location = { env = "OPENAI_API_KEY" }

[models."dall-e-2"]
routing = ["openai"]
endpoints = ["image_generation", "image_edit", "image_variation"]

[models."dall-e-2".providers.openai]
type = "openai"
model_name = "dall-e-2"
api_key_location = { env = "OPENAI_API_KEY" }
```

## Error Handling

The Images API returns errors in the standard OpenAI format:

```json
{
  "error": {
    "message": "Invalid image size: 2048x2048",
    "type": "invalid_request_error",
    "code": "invalid_size"
  }
}
```

Common error codes:
- `invalid_request_error` - Invalid parameters or request format
- `model_not_found` - The specified model doesn't exist or doesn't support the requested capability
- `invalid_size` - The requested image size is not supported
- `file_too_large` - The uploaded image exceeds the 4MB limit
- `invalid_image_format` - The uploaded file is not a valid image

## Examples

### Python Example (using OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://gateway.tensorzero.com/v1",
    api_key="YOUR_API_KEY"
)

# Generate an image
response = client.images.generate(
    model="dall-e-3",
    prompt="A serene landscape with mountains and a lake at sunset",
    size="1024x1024",
    quality="hd",
    n=1
)

image_url = response.data[0].url
print(f"Generated image URL: {image_url}")

# Edit an image
with open("original.png", "rb") as image_file:
    response = client.images.edit(
        model="dall-e-2",
        image=image_file,
        prompt="Add a rainbow over the mountains",
        size="1024x1024",
        n=1
    )

# Create variations
with open("original.png", "rb") as image_file:
    response = client.images.create_variation(
        model="dall-e-2",
        image=image_file,
        n=2,
        size="1024x1024"
    )
```

### cURL Examples

#### Generate Image
```bash
curl -X POST https://gateway.tensorzero.com/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "dall-e-3",
    "prompt": "A futuristic city skyline at night",
    "size": "1024x1024",
    "quality": "hd",
    "response_format": "url"
  }'
```

#### Edit Image with Mask
```bash
curl -X POST https://gateway.tensorzero.com/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F model="dall-e-2" \
  -F image="@city.png" \
  -F mask="@city_mask.png" \
  -F prompt="Replace the sky with aurora borealis" \
  -F n=1 \
  -F size="1024x1024"
```

#### Create Multiple Variations
```bash
curl -X POST https://gateway.tensorzero.com/v1/images/variations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F model="dall-e-2" \
  -F image="@artwork.png" \
  -F n=3 \
  -F size="512x512" \
  -F response_format="b64_json"
```

## Best Practices

1. **Image Formats**: Always use PNG format for input images to ensure compatibility
2. **File Size**: Keep uploaded images under 4MB to avoid errors
3. **Square Images**: For dall-e-2, ensure input images are square for edits and variations
4. **Prompt Length**: Keep prompts concise but descriptive (under 1000 characters for dall-e-2, 4000 for dall-e-3)
5. **Error Handling**: Implement retry logic for transient errors
6. **Response Format**: Use `b64_json` format when you need to process images immediately without making additional HTTP requests

## Rate Limits

Rate limits depend on your configured providers and their respective limits. TensorZero will automatically handle routing and fallbacks based on your model configuration.

## Supported Providers

Currently, the Images API is supported by:
- OpenAI (dall-e-2, dall-e-3)

Additional providers may be added in the future. Check your provider's documentation for model-specific features and limitations.