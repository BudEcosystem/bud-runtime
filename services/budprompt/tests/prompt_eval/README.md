# Prompt Evaluation Test Suite

This directory contains tools for generating and running evaluation tests for prompt executors.

## Overview

The evaluation process has two stages:

1. **Generate Test Data**: Use `generate_test_data.py` to create realistic test input/output values from `dataset.json` schemas
2. **Run Tests**: Use the generated data to test executors across different models (coming soon)

## Files

- `dataset.json` - Schema definitions for 1914 test cases (inputs, outputs, prompts, SLOs)
- `generate_test_data.py` - Script to generate realistic test data using an LLM
- `test_data.json` - Generated test input/output values (created by generate_test_data.py)

## Stage 1: Generate Test Data

### Prerequisites

```bash
# Ensure you have a running gateway and model
# Example: http://20.66.97.208/v1 with qwen3-32b model
```

### Basic Usage

```bash
python tests/prompt_eval/generate_test_data.py \
  --gateway-url http://20.66.97.208/v1 \
  --model-name qwen3-32b \
  --limit 50
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--gateway-url` | Yes | - | Model gateway base URL |
| `--model-name` | Yes | - | Model deployment name (e.g., qwen3-32b) |
| `--api-key` | No | None | Optional API key for authorization |
| `--limit` | No | 50 | Number of test cases to generate |
| `--start-index` | No | 0 | Start from specific record (for resuming) |
| `--output` | No | test_data.json | Output file path |

### Examples

**Generate 50 test cases:**
```bash
python tests/prompt_eval/generate_test_data.py \
  --gateway-url http://20.66.97.208/v1 \
  --model-name qwen3-32b \
  --limit 50 \
  --output test_data.json
```

**Generate 100 test cases with API key:**
```bash
python tests/prompt_eval/generate_test_data.py \
  --gateway-url http://20.66.97.208/v1 \
  --model-name qwen3-32b \
  --api-key your-api-key-here \
  --limit 100 \
  --output test_data_100.json
```

**Resume generation from record 25:**
```bash
python tests/prompt_eval/generate_test_data.py \
  --gateway-url http://20.66.97.208/v1 \
  --model-name qwen3-32b \
  --limit 100 \
  --start-index 25 \
  --output test_data.json
```

### How It Works

1. **Load Dataset**: Reads `dataset.json` and filters records with valid response data
2. **Build Meta-Prompt**: For each record, creates a prompt asking the LLM to generate realistic test data
3. **Generate Data**: Uses executor v3 to call the LLM with the meta-prompt
4. **Parse Response**: Extracts JSON with inputs and outputs from LLM response
5. **Save Results**: Writes to `test_data.json` (saves incrementally every 10 records)

### Output Format

```json
[
  {
    "id": "682253ddd408b8f9e7d9f025",
    "inputs": {
      "context": "The Industrial Revolution (1760-1840) transformed manufacturing through mechanization...",
      "focus_area": "technological innovation"
    },
    "outputs": {
      "changes_list": {
        "area": "Technology",
        "change_description": "Introduction of steam-powered machinery",
        "impact": "Enabled mass production and factory systems"
      }
    }
  }
]
```

### Progress Tracking

The script shows real-time progress:

```
Loading dataset from dataset.json...
Total records in dataset: 1914
Valid records with response data: 1850
Selected records: 50 (from index 0 to 50)

Initializing executor (version 3)...
Using model: qwen3-32b
Gateway URL: http://20.66.97.208/v1

Generating test data for 50 records...

[1/50] Processing 682253ddd408b8f9e7d9f025... ✓ Success
[2/50] Processing 682253efd408b8f9e7d9f027... ✓ Success
...
[10/50] Processing 682253f2d408b8f9e7d9f029... ✓ Success
  → Saved 10 records to test_data.json
```

### Error Handling

- Failed records are logged but don't stop the process
- Results are saved incrementally (every 10 records)
- Can be interrupted with Ctrl+C and resumed using `--start-index`
- Invalid JSON responses from LLM are caught and logged

### Troubleshooting

**Connection errors:**
```bash
# Verify gateway is accessible
curl http://20.66.97.208/v1/models
```

**Import errors:**
```bash
# Ensure you're in the budprompt directory
cd services/budprompt
python tests/prompt_eval/generate_test_data.py --help
```

**Out of memory:**
```bash
# Reduce batch size by generating smaller chunks
python tests/prompt_eval/generate_test_data.py \
  --limit 10 \
  --output test_data_batch1.json
```

## Stage 2: Run Tests (Coming Soon)

Use the generated `test_data.json` to run executor tests across different models and measure performance.

## Dataset Structure

The `dataset.json` contains:

- **Task Descriptions**: System prompts for actual execution
- **Input Schema**: Field definitions (name, type, description)
- **Output Schema**: Expected output structure
- **SLO Metrics**: Performance targets (TTFT, TBT, latency, throughput)
- **Complexity Metadata**: Difficulty, domains, required skills

## Notes

- The script uses executor version 3 (active version with MCP tools support)
- Model temperature is set to 0.7 for creative but reasonable test data
- Each record uses ~500-800 tokens (prompt + response)
- Incremental saves prevent data loss on interruption
