# Bud Sentinel v2 Integration Implementation Plan

**Goal:** Update the Bud Sentinel proto and guardrail profile handling to support v2 fields, and forward request-scoped bearer auth to Sentinel.

**Architecture:** Replace `bud.proto` with the v2 schema and keep it as the canonical public proto. Extend guardrail profile building/sync to include `custom_rules`, `metadata_json`, and `rule_overrides_json`. Add request-scoped bearer forwarding from incoming moderation requests into Bud Sentinel gRPC metadata alongside the stored API token header.

**Tech Stack:** Rust (serde_json, tonic/prost), gRPC metadata, ClickHouse guardrail config.

### Task 1: Replace the Bud Sentinel proto and document it

**Files:**
- Modify: `tensorzero-internal/proto/bud.proto`
- Modify: `tensorzero-internal/proto/README.md`

**Step 1: Write the new proto contents**

Replace `tensorzero-internal/proto/bud.proto` with the contents of `tensorzero-internal/proto/bud-v2.proto` verbatim.

**Step 2: Update proto README**

Add a note that `bud.proto` is the v2 schema used to understand Sentinel’s public contract, and outline the refresh steps referencing `bud-v2.proto` as the source.

**Step 3: (Optional) verify protobuf generation**

Run: `cargo build -p tensorzero-internal`
Expected: Build succeeds; `tonic-build` regenerates Bud Sentinel stubs.

### Task 2: Add Bud Sentinel profile v2 mapping + tests

**Files:**
- Modify: `tensorzero-internal/src/guardrail.rs`
- Modify: `tensorzero-internal/src/redis_client.rs`
- Test: `tensorzero-internal/src/guardrail.rs` (unit tests module)

**Step 1: Write failing test for custom_rules mapping**

```rust
#[test]
fn builds_profile_with_custom_rules() {
    let provider_config = serde_json::json!({
        "profile_id": "test-profile",
        "strategy_id": "strategy-1",
        "description": "Test profile",
        "version": "v1",
        "metadata_json": "{\"llm\":{}}",
        "rule_overrides_json": "",
        "custom_rules": [
            {
                "id": "custom_spam_detector",
                "scanner": "llm",
                "scanner_config_json": "{\"model_id\":\"foo\"}",
                "target_labels": ["spam"],
                "severity_threshold": 0.5,
                "probe": "pii",
                "name": "Spam",
                "description": "Detect spam",
                "post_processing_json": "[]"
            }
        ]
    });

    let profile = build_bud_sentinel_profile(
        "guardrail-1",
        0.7,
        &["pii".to_string()],
        &std::collections::HashMap::new(),
        provider_config.as_object().unwrap(),
    )
    .expect("profile build");

    assert_eq!(profile.custom_rules.len(), 1);
    let rule = &profile.custom_rules[0];
    assert_eq!(rule.id, "custom_spam_detector");
    assert_eq!(rule.scanner, "llm");
    assert_eq!(rule.target_labels, vec!["spam"]);
    assert_eq!(rule.probe.as_deref(), Some("pii"));
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p tensorzero-internal builds_profile_with_custom_rules`
Expected: FAIL (missing `custom_rules` mapping or struct fields).

**Step 3: Implement custom_rules parsing + profile mapping**

- In `build_bud_sentinel_profile`, parse `custom_rules` from provider config into the generated proto type.
- Add a small `CustomRuleConfig` struct (serde) and conversion helper.
- Ensure `metadata_json` and `rule_overrides_json` continue to be filled.

**Step 4: Update guardrail sync to persist returned custom_rules**

- When `sync_bud_sentinel_profiles` writes provider config, store `custom_rules` from the returned profile as a JSON array of objects (same shape as input).

**Step 5: Run test to verify it passes**

Run: `cargo test -p tensorzero-internal builds_profile_with_custom_rules`
Expected: PASS

### Task 3: Forward bearer auth + update API token header name

**Files:**
- Modify: `tensorzero-internal/src/endpoints/openai_compatible.rs`
- Modify: `tensorzero-internal/src/inference/providers/bud_sentinel.rs`

**Step 1: Add request-scoped credential merge for moderation**

Call `merge_credentials_from_headers(&headers, &mut credentials)` inside `moderation_handler` after loading credential store, so the incoming `Authorization` bearer is available for the request only.

**Step 2: Forward bearer metadata in Bud Sentinel provider**

- In `apply_request_metadata`, if `dynamic_api_keys` contains `authorization`, add `authorization: Bearer <token>` to the gRPC metadata.
- Change the stored API key header to `x-api-token` (instead of `x-api-key`) to match Sentinel expectations.

**Step 3: Sanity test (manual)**

No automated test; verify by inspection that bearer tokens are only pulled from request headers and are not persisted in config.

### Task 4: Full test run (optional)

**Step 1: Run targeted tests**

Run: `cargo test -p tensorzero-internal guardrail`
Expected: PASS

**Step 2: Run full build**

Run: `cargo build -p tensorzero-internal`
Expected: PASS
