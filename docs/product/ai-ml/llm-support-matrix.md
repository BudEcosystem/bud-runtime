# LLM Support Matrix

---

## Overview

This document lists all supported large language models, frameworks, and deployment configurations in Bud AI Foundry.

---

## Supported Model Architectures

| Architecture | Examples | Status |
|--------------|----------|--------|
| **Llama** | Llama 3.1, Llama 3, Llama 2 | Full Support |
| **Mistral** | Mistral 7B, Mixtral 8x7B, Mixtral 8x22B | Full Support |
| **Qwen** | Qwen 2.5, Qwen 2, Qwen 1.5 | Full Support |
| **Falcon** | Falcon 40B, Falcon 180B | Full Support |
| **MPT** | MPT-7B, MPT-30B | Full Support |
| **Phi** | Phi-3, Phi-2 | Full Support |
| **Gemma** | Gemma 2, Gemma 7B | Full Support |
| **StarCoder** | StarCoder 2, StarCoder | Full Support |
| **DeepSeek** | DeepSeek-V2, DeepSeek Coder | Full Support |

---

## Pre-Validated Models

### Foundation Models

| Model | Parameters | Context | GPU Memory | Recommended Config |
|-------|------------|---------|------------|-------------------|
| Llama 3.1 405B | 405B | 128K | 800GB | 8x H100-80GB, TP=8 |
| Llama 3.1 70B | 70B | 128K | 140GB | 2x H100-80GB, TP=2 |
| Llama 3.1 8B | 8B | 128K | 16GB | 1x A100-40GB |
| Mistral 7B | 7B | 32K | 14GB | 1x A100-40GB |
| Mixtral 8x7B | 47B | 32K | 100GB | 2x A100-80GB, TP=2 |
| Mixtral 8x22B | 141B | 64K | 280GB | 4x H100-80GB, TP=4 |
| Qwen 2.5 72B | 72B | 128K | 144GB | 2x H100-80GB, TP=2 |

### Instruct/Chat Models

| Model | Base | Fine-Tune |
|-------|------|-----------|
| Llama-3.1-8B-Instruct | Llama 3.1 8B | Instruction following |
| Llama-3.1-70B-Instruct | Llama 3.1 70B | Instruction following |
| Mistral-7B-Instruct-v0.3 | Mistral 7B | Instruction following |
| Mixtral-8x7B-Instruct-v0.1 | Mixtral 8x7B | Instruction following |

### Code Models

| Model | Parameters | Languages |
|-------|------------|-----------|
| CodeLlama-34B | 34B | Python, C++, Java, JS, ... |
| DeepSeek-Coder-33B | 33B | 86 languages |
| StarCoder2-15B | 15B | 600+ languages |

---

## Quantization Support

| Format | Precision | Memory Savings | Quality Impact |
|--------|-----------|----------------|----------------|
| FP16 | 16-bit | Baseline | None |
| BF16 | 16-bit | Baseline | Minimal |
| INT8 | 8-bit | ~50% | Small |
| INT4 (GPTQ) | 4-bit | ~75% | Moderate |
| INT4 (AWQ) | 4-bit | ~75% | Small |
| GGUF | Variable | 50-75% | Variable |

---

## Runtime Compatibility

| Model | vLLM | SGLang | TensorRT-LLM |
|-------|------|--------|--------------|
| Llama 3.1 | Yes | Yes | Yes |
| Mistral | Yes | Yes | Yes |
| Mixtral (MoE) | Yes | Yes | Yes |
| Qwen 2.5 | Yes | Yes | Partial |
| Falcon | Yes | No | Yes |
| Phi-3 | Yes | Yes | Yes |

---

## Hardware Requirements

### By Model Size

| Size | Min GPU Memory | Recommended GPU |
|------|----------------|-----------------|
| 7B | 16GB | A10G, T4 |
| 13B | 28GB | A100-40GB |
| 34B | 70GB | A100-80GB |
| 70B | 140GB | 2x A100-80GB |
| 180B | 360GB | 4x H100-80GB |
| 405B | 800GB | 8x H100-80GB |

### GPU Compatibility

| GPU | Memory | Supported |
|-----|--------|-----------|
| NVIDIA H100 | 80GB | Full |
| NVIDIA A100 | 40GB/80GB | Full |
| NVIDIA L40S | 48GB | Full |
| NVIDIA A10G | 24GB | Full |
| NVIDIA T4 | 16GB | Limited |
| Intel Gaudi 2 | 96GB | Beta |

---

## Context Length Support

| Model | Native | Extended (RoPE) |
|-------|--------|-----------------|
| Llama 3.1 | 128K | N/A |
| Llama 3 | 8K | 128K |
| Mistral | 32K | 128K |
| Mixtral | 32K | 64K |
| Qwen 2.5 | 128K | N/A |

---

## Adding New Models

### Requirements

1. Compatible architecture (transformer-based)
2. Safetensors or PyTorch format
3. Tokenizer files (tokenizer.json or sentencepiece)
4. Model configuration (config.json)

### Process

1. Upload to model registry
2. Specify architecture and parameters
3. Run compatibility test
4. Configure deployment settings
5. Deploy to cluster

---

## Related Documents

- [Model Registry Documentation](./model-registry.md)
- [GPU Support Guide](./gpu-support.md)
- [Custom Model Onboarding](./custom-model-onboarding.md)
