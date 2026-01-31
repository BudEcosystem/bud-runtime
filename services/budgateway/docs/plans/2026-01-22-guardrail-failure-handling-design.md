# Guardrail Failure Handling Design

## Context
Guardrails are enforced in two OpenAI-compatible paths:
1) chat completions guardrail middleware (input/output + streaming output scans)
2) moderations endpoint where guardrail results are returned as the moderation response

We must never skip guardrail failures. Any provider error or guardrail execution error is a security risk and must be surfaced.

## Goals
- Chat completions: retry guardrail execution on retryable errors with small backoff (3 attempts). If still failing, return HTTP 502.
- Moderations: return HTTP 502 on guardrail execution errors or provider errors; no skipping.
- Treat provider-level errors inside a successful GuardrailResult as a failure.
- No behavior changes for non-guardrail paths.

## Non-Goals
- Changing guardrail provider implementations or retry logic inside provider modules.
- Adjusting guardrail configuration schema.
- Adding new observability schemas beyond existing guardrail records.

## Proposed Design
Add a guardrail execution wrapper in `tensorzero-internal/src/endpoints/openai_compatible.rs` used by both chat completions guardrail middleware and moderation handler.

**Retry policy:**
- Attempts: 3
- Backoff: 200ms, 400ms, 800ms
- Retryable errors: `InferenceTimeout`, `ProviderTimeout`, `InferenceServer`, and (for Bud Sentinel gRPC) `Unavailable`, `DeadlineExceeded`, `Unknown`.
- Non-retryable errors: `ApiKeyMissing`, `BadCredentialsPreInference`, config/validation errors, and gRPC `Unauthenticated`/`PermissionDenied`.

**Failure behavior:**
- Any `Err` from guardrail execution after retries returns HTTP 502.
- Any `GuardrailResult` containing a non-empty `provider_results[*].error` is treated as failure and returns HTTP 502.

**Chat completions:**
- Use wrapper for input guardrail, output guardrail, and streaming output windows. If failure occurs, return 502 (not 200) with an error payload.

**Moderations:**
- If guardrail execution fails or provider errors exist, return 502 instead of a normal moderation response.

## Error Payload
Use existing OpenAI-compatible error JSON. For guardrail failures, return `server_error` with status 502 and a message like "Guardrail execution failed".

## Testing
- Unit test: guardrail wrapper classifies retryable vs non-retryable errors.
- Integration smoke: moderation handler returns 502 on guardrail error.
- Chat completions: simulate guardrail provider error to ensure 502 is returned and no inference proceeds.
