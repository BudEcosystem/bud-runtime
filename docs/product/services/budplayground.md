# budplayground - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budplayground, the interactive model testing interface of Bud AI Foundry. It enables developers and ML engineers to experiment with deployed models.

### 1.2 Scope

**In Scope:**
- Interactive chat interface
- Model comparison (side-by-side)
- Parameter tuning (temperature, top_p, etc.)
- Response streaming
- Prompt templates

**Out of Scope:**
- Model deployment (handled by budadmin)
- Model inference (handled by budgateway)

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Users need to test models before production use
- Side-by-side comparison helps model selection
- Parameter tuning requires real-time feedback
- Conversation history should be exportable

### 2.2 Technical Assumptions

- Next.js for the frontend
- Direct connection to budgateway for inference
- WebSocket/SSE for streaming responses
- Local storage for conversation history

### 2.3 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| budgateway | Required | No inference | Show error |
| budapp | Required | No auth/model list | Cached data |

---

---

---

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| NEXT_PUBLIC_GATEWAY_URL | Yes | - | budgateway URL |
| NEXT_PUBLIC_API_URL | Yes | - | budapp API URL |

---

## 7. Security Design

- Authentication via Keycloak (shared with budadmin)
- API keys not exposed to browser
- Conversation data stored locally only

---

## 8. Performance & Scalability

### 8.1 Streaming Optimization

- Efficient DOM updates for token streaming
- Virtual scrolling for long conversations
- Debounced parameter changes

---

## 9. Deployment & Infrastructure

### 10.2 Resources

| Component | CPU | Memory |
|-----------|-----|--------|
| budplayground | 250m | 256Mi |
