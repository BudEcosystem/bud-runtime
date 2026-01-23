# budplayground Service Documentation

---

## Overview

budplayground is an interactive model testing interface that allows developers and ML engineers to experiment with deployed models, compare responses, and tune parameters.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budplayground |
| **Port** | 8008 |
| **Language** | TypeScript 5.x |
| **Framework** | Next.js |
| **UI Library** | React |

---

## Responsibilities

- Interactive chat interface for model testing
- Side-by-side model comparison
- Parameter tuning (temperature, top_p, etc.)
- Response analysis and metrics
- Prompt template management
- Export conversation history

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Chat Interface** | Interactive conversation with models |
| **Model Comparison** | Compare responses from multiple models |
| **Parameter Tuning** | Adjust inference parameters in real-time |
| **Streaming** | Real-time token streaming |
| **Metrics Display** | Show latency, token counts |
| **Prompt Library** | Save and reuse prompts |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_GATEWAY_URL` | budgateway URL | Required |
| `NEXT_PUBLIC_API_URL` | budapp API URL | Required |

---

## Development

```bash
cd services/budplayground
npm install
npm run dev
```

---

## Related Documents

- [ML Engineer Training](../training/ml-engineer.md)
