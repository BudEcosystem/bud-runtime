# ask-bud Service Documentation

---

## Overview

ask-bud is an AI assistant service that helps users with cluster analysis, performance troubleshooting, and platform Q&A using natural language.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | ask-bud |
| **Port** | 9089 |
| **Database** | askbud_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Answer questions about cluster health and configuration
- Analyze performance metrics and suggest optimizations
- Troubleshoot deployment issues
- Provide platform guidance and documentation lookup
- Maintain conversation context

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send message to assistant |
| GET | `/sessions` | List chat sessions |
| GET | `/sessions/{id}` | Get session history |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/analyze/cluster/{id}` | Analyze specific cluster |
| POST | `/analyze/performance` | Performance analysis |

---

## Capabilities

| Feature | Description |
|---------|-------------|
| **Cluster Q&A** | Answer questions about cluster status, nodes, deployments |
| **Performance Analysis** | Interpret metrics, identify bottlenecks |
| **Troubleshooting** | Diagnose errors, suggest fixes |
| **Documentation** | Surface relevant docs and guides |
| **Context Awareness** | Remember conversation history |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `LLM_PROVIDER` | AI provider for responses | `openai` |
| `LLM_MODEL` | Model to use | `gpt-4` |
| `MAX_CONTEXT_MESSAGES` | History to include | `20` |

---

## Related Documents

- [AI Assistant Guide](../training/ai-assistant.md)
