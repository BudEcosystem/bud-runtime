# {Service Name} - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

{Why this LLD exists. What decisions does it enable? What should a developer be able to build from this?}

### 1.2 Scope

**In Scope:**
- {Feature/capability 1}
- {Feature/capability 2}

**Out of Scope:**
- {Explicitly excluded item 1}
- {Explicitly excluded item 2}

### 1.3 Intended Audience

| Audience | What They Need |
|----------|----------------|
| Developers | Implementation details, API contracts |
| Reviewers | Architecture decisions, trade-offs |
| Security | Auth flows, encryption, threat model |
| Operations | Deployment, monitoring, runbooks |

### 1.4 References

| Document | Description |
|----------|-------------|
| [High-Level Architecture](../architecture/high-level-architecture.md) | System overview |
| [Main LLD Index](../architecture/low-level-design.md) | Cross-cutting concerns |
| {PRD/RFC} | Requirements source |

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- {Assumption about user behavior, e.g., "Users deploy models averaging 7B-70B parameters"}
- {Assumption about usage patterns}

### 2.2 Technical Assumptions

- {Runtime environment assumptions}
- {Infrastructure assumptions}
- {Dependency availability assumptions}

### 2.3 Constraints

| Constraint Type | Description | Impact |
|-----------------|-------------|--------|
| Latency | {e.g., API responses < 200ms} | {Design impact} |
| Memory | {e.g., Service runs in 512MB-2GB pods} | {Design impact} |
| Regulatory | {e.g., Data residency requirements} | {Design impact} |
| Hardware | {e.g., GPU availability varies} | {Design impact} |

### 2.4 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| {Service/System} | {Required/Optional} | {What breaks} | {How we handle it} |

---

## 3. Detailed Architecture

### 3.1 Component Overview

```
{ASCII diagram showing major components and their relationships}
```

### 3.2 Component Breakdown

#### 3.2.1 {Component Name}

| Property | Value |
|----------|-------|
| **Responsibility** | {Single sentence describing what this component does} |
| **Owner Module** | `{module_path}` |

**Inputs:**
| Input | Source | Format | Validation |
|-------|--------|--------|------------|
| {input_name} | {where it comes from} | {data type/schema} | {validation rules} |

**Outputs:**
| Output | Destination | Format | Guarantees |
|--------|-------------|--------|------------|
| {output_name} | {where it goes} | {data type/schema} | {delivery guarantees} |

**Internal Sub-modules:**
- `{submodule}` - {responsibility}

**Error Handling:**
| Error Condition | Response | Recovery |
|-----------------|----------|----------|
| {condition} | {what happens} | {how to recover} |

**Scalability:**
- Horizontal: {can/cannot scale horizontally, why}
- Vertical: {memory/CPU scaling considerations}
- Bottlenecks: {known bottlenecks}

{Repeat 3.2.x for each major component}

### 3.3 Component Interaction Diagrams

#### 3.3.1 {Flow Name} - Happy Path

```
sequenceDiagram
    participant A as {Actor}
    participant B as {Component}
    participant C as {Component}

    A->>B: {action}
    B->>C: {action}
    C-->>B: {response}
    B-->>A: {response}
```

#### 3.3.2 {Flow Name} - Failure Path

```
sequenceDiagram
    participant A as {Actor}
    participant B as {Component}
    participant C as {Component}

    A->>B: {action}
    B->>C: {action}
    C--xB: {error}
    B-->>A: {error response}
```

#### 3.3.3 State Diagram (if applicable)

```
stateDiagram-v2
    [*] --> State1
    State1 --> State2: event
    State2 --> State3: event
    State3 --> [*]
```

---

## 4. Data Design

### 4.1 Data Models

#### 4.1.1 {Entity Name}

**Table:** `{table_name}`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, NOT NULL | Primary identifier |
| `{column}` | {type} | {constraints} | {description} |

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|
| `{index_name}` | `{columns}` | {B-tree/GIN/etc.} | {why this index exists} |

**Relationships:**
```
{Entity} 1──N {RelatedEntity}  -- {relationship description}
```

{Repeat for each entity}

#### 4.1.2 Entity Relationship Diagram

```
{ERD showing all entities and their relationships}
```

### 4.2 Data Flow

#### 4.2.1 Data Lifecycle

| Stage | Location | Retention | Transition Trigger |
|-------|----------|-----------|-------------------|
| Created | {where} | {how long} | {what triggers next stage} |
| Active | {where} | {how long} | {what triggers next stage} |
| Archived | {where} | {how long} | {what triggers deletion} |

#### 4.2.2 Read/Write Paths

**Write Path:**
```
{Diagram or steps showing how data is written}
```

**Read Path:**
```
{Diagram or steps showing how data is read}
```

#### 4.2.3 Caching Strategy

| Cache Layer | Technology | TTL | Invalidation Strategy |
|-------------|------------|-----|----------------------|
| {layer} | {Redis/Memory/etc.} | {duration} | {when/how cache is invalidated} |

---

## 5. API & Interface Design

### 5.1 Internal APIs

#### 5.1.1 {Endpoint Group}

**`{METHOD} {path}`**

| Property | Value |
|----------|-------|
| **Description** | {what this endpoint does} |
| **Authentication** | {auth mechanism required} |
| **Rate Limit** | {requests/period} |
| **Timeout** | {duration} |

**Request:**
```json
{
  "field": "type - description"
}
```

**Response (Success):**
```json
{
  "field": "type - description"
}
```

**Response (Error):**
| Status Code | Error Code | Description | Retry? |
|-------------|------------|-------------|--------|
| 400 | `VALIDATION_ERROR` | {description} | No |
| 404 | `NOT_FOUND` | {description} | No |
| 500 | `INTERNAL_ERROR` | {description} | Yes |

{Repeat for each endpoint}

### 5.2 External Integrations

#### 5.2.1 {External Service Name}

| Property | Value |
|----------|-------|
| **Purpose** | {why we integrate} |
| **Auth Mechanism** | {API key/OAuth/mTLS} |
| **Rate Limits** | {their limits} |
| **SLA** | {expected availability} |

**Failure Fallback:**
- {What happens when this service is unavailable}
- {Degraded functionality description}

---

## 6. Logic & Algorithm Details

### 6.1 {Algorithm/Process Name}

**Purpose:** {What problem does this solve?}

**Inputs:**
- {input 1}: {description}
- {input 2}: {description}

**Outputs:**
- {output 1}: {description}

**Algorithm (Step-by-Step):**

1. {Step 1}
2. {Step 2}
3. {Step 3}

**Pseudocode:**
```
function processX(input):
    validate(input)
    transformed = transform(input)
    result = compute(transformed)
    return result
```

**Decision Tree:**
```
Is condition A true?
├── Yes → Action 1
│   └── Is condition B true?
│       ├── Yes → Action 2
│       └── No → Action 3
└── No → Action 4
```

**Edge Cases:**
| Edge Case | Behavior | Rationale |
|-----------|----------|-----------|
| {case} | {what happens} | {why this behavior} |

---

## 7. GenAI/ML-Specific Design

> *This section is specific to services handling model inference, deployment, or ML operations.*

### 7.1 Model Deployment Flow

#### 7.1.1 Deployment Pipeline

```
{Diagram showing model deployment stages}
```

| Stage | Duration | Rollback Point | Validation |
|-------|----------|----------------|------------|
| {stage} | {expected time} | {yes/no} | {what's checked} |

#### 7.1.2 Model Configuration

| Parameter | Source | Default | Constraints |
|-----------|--------|---------|-------------|
| `max_model_len` | {calculated/user} | {value} | {min/max} |
| `tensor_parallel` | {calculated/user} | {value} | {hardware dependent} |
| `batch_size` | {calculated/user} | {value} | {memory dependent} |

### 7.2 Inference Request Handling

#### 7.2.1 Request Flow

```
{Sequence diagram for inference request}
```

#### 7.2.2 Request Routing Logic

| Condition | Route To | Rationale |
|-----------|----------|-----------|
| {condition} | {destination} | {why} |

#### 7.2.3 Token Budget Management

| Metric | Calculation | Limit Enforcement |
|--------|-------------|-------------------|
| Input tokens | {how counted} | {what happens at limit} |
| Output tokens | {how counted} | {what happens at limit} |

### 7.3 Hardware Resource Allocation

#### 7.3.1 GPU/Accelerator Selection

| Hardware Type | Detection Method | Allocation Strategy |
|---------------|------------------|---------------------|
| NVIDIA GPU | {NFD labels/device plugin} | {how assigned} |
| Intel Gaudi | {NFD labels/device plugin} | {how assigned} |
| CPU | {node capacity} | {how assigned} |

#### 7.3.2 Resource Calculation

**Memory Formula:**
```
required_memory = model_params * precision_bytes + kv_cache + overhead
```

**GPU Count Formula:**
```
gpu_count = ceil(required_memory / gpu_memory) * tensor_parallel_factor
```

### 7.4 Performance Optimization

#### 7.4.1 Optimization Parameters

| Parameter | Impact | Trade-off |
|-----------|--------|-----------|
| {param} | {what it affects} | {cost of increasing/decreasing} |

#### 7.4.2 Benchmarking Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| TTFT | Time to first token | {target value} |
| TPOT | Time per output token | {target value} |
| Throughput | Tokens/second | {target value} |

### 7.5 Safety & Guardrails

#### 7.5.1 Input Validation

| Check | Implementation | Action on Failure |
|-------|----------------|-------------------|
| {check type} | {how implemented} | {reject/flag/modify} |

#### 7.5.2 Output Filtering

| Filter | Trigger Condition | Response |
|--------|-------------------|----------|
| {filter type} | {when triggered} | {what happens} |

---

## 8. Configuration & Environment Design

### 8.1 Environment Variables

| Variable | Required | Default | Description | Sensitive |
|----------|----------|---------|-------------|-----------|
| `{VAR_NAME}` | Yes/No | `{default}` | {description} | Yes/No |

### 8.2 Feature Flags

| Flag | Default | Description | Rollout Strategy |
|------|---------|-------------|------------------|
| `{flag_name}` | {on/off} | {what it controls} | {how to enable} |

### 8.3 Secrets Management

| Secret | Storage | Rotation | Access |
|--------|---------|----------|--------|
| {secret_name} | {Vault/K8s Secret/etc.} | {frequency} | {who/what can access} |

### 8.4 Environment Differences

| Aspect | Development | Staging | Production |
|--------|-------------|---------|------------|
| {aspect} | {dev value} | {staging value} | {prod value} |

---

## 9. Security Design

### 9.1 Authentication

| Flow | Mechanism | Token Lifetime | Refresh Strategy |
|------|-----------|----------------|------------------|
| {flow name} | {JWT/OAuth/API Key} | {duration} | {how refreshed} |

### 9.2 Authorization

| Resource | Permission Model | Enforcement Point |
|----------|------------------|-------------------|
| {resource} | {RBAC/ABAC/etc.} | {where checked} |

### 9.3 Encryption

| Data Type | At Rest | In Transit | Key Management |
|-----------|---------|------------|----------------|
| {data type} | {algorithm} | {TLS version} | {how keys managed} |

### 9.4 Input Validation

| Input | Validation Rules | Sanitization |
|-------|------------------|--------------|
| {input type} | {rules} | {how sanitized} |

### 9.5 Threat Model (Basic)

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| {threat} | {H/M/L} | {H/M/L} | {how mitigated} |

---

## 10. Performance & Scalability

### 10.1 Expected Load

| Metric | Normal | Peak | Burst |
|--------|--------|------|-------|
| Requests/sec | {value} | {value} | {value} |
| Concurrent users | {value} | {value} | {value} |
| Data volume | {value} | {value} | {value} |

### 10.2 Bottlenecks

| Bottleneck | Trigger Condition | Symptom | Mitigation |
|------------|-------------------|---------|------------|
| {bottleneck} | {when it occurs} | {how to detect} | {how to fix} |

### 10.3 Caching Strategy

| Cache | Hit Rate Target | Eviction Policy | Warming Strategy |
|-------|-----------------|-----------------|------------------|
| {cache name} | {percentage} | {LRU/TTL/etc.} | {how warmed} |

### 10.4 Concurrency Handling

| Resource | Concurrency Model | Lock Strategy | Deadlock Prevention |
|----------|-------------------|---------------|---------------------|
| {resource} | {async/threaded/etc.} | {optimistic/pessimistic} | {how prevented} |

### 10.5 Scaling Strategy

| Dimension | Trigger | Target | Cooldown |
|-----------|---------|--------|----------|
| Horizontal (pods) | {metric > threshold} | {min-max} | {duration} |
| Vertical (resources) | {metric > threshold} | {limits} | {duration} |

---

## 11. Error Handling & Logging

### 11.1 Error Classification

| Category | Severity | Retry | Alert |
|----------|----------|-------|-------|
| Validation errors | Low | No | No |
| Transient failures | Medium | Yes | After N failures |
| System failures | High | No | Immediately |

### 11.2 Retry Strategy

| Error Type | Max Retries | Backoff | Circuit Breaker |
|------------|-------------|---------|-----------------|
| {error type} | {count} | {exponential/linear} | {threshold} |

### 11.3 Logging Standards

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Development troubleshooting | {example} |
| INFO | Business events | {example} |
| WARNING | Recoverable issues | {example} |
| ERROR | Failures requiring attention | {example} |

### 11.4 Observability

| Signal | Tool | Retention | Alert Threshold |
|--------|------|-----------|-----------------|
| Metrics | {Prometheus/etc.} | {duration} | {threshold} |
| Traces | {Tempo/Jaeger/etc.} | {duration} | {sampling rate} |
| Logs | {Loki/etc.} | {duration} | {patterns} |

---

## 12. Deployment & Infrastructure

### 12.1 Deployment Topology

```
{Diagram showing deployment architecture}
```

### 12.2 Container Specification

| Property | Value |
|----------|-------|
| Base Image | {image} |
| Resource Requests | CPU: {value}, Memory: {value} |
| Resource Limits | CPU: {value}, Memory: {value} |
| Health Checks | Liveness: {path}, Readiness: {path} |

### 12.3 CI/CD Pipeline

| Stage | Trigger | Actions | Rollback |
|-------|---------|---------|----------|
| Build | {trigger} | {what happens} | N/A |
| Test | {trigger} | {what happens} | N/A |
| Deploy | {trigger} | {what happens} | {how to rollback} |

### 12.4 Rollback Strategy

| Scenario | Detection | Rollback Method | Recovery Time |
|----------|-----------|-----------------|---------------|
| {scenario} | {how detected} | {how rolled back} | {expected time} |

---

## 13. Testing Strategy

### 13.1 Unit Tests

| Module | Coverage Target | Mocking Strategy |
|--------|-----------------|------------------|
| {module} | {percentage} | {what's mocked} |

### 13.2 Integration Tests

| Integration | Test Approach | Environment |
|-------------|---------------|-------------|
| {integration} | {approach} | {where run} |

### 13.3 Edge Case Coverage

| Edge Case | Test | Expected Behavior |
|-----------|------|-------------------|
| {edge case} | {test name/description} | {what should happen} |

### 13.4 Performance Tests

| Test | Metric | Threshold | Frequency |
|------|--------|-----------|-----------|
| {test name} | {what measured} | {pass/fail value} | {when run} |

---

## 14. Limitations & Future Enhancements

### 14.1 Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| {limitation} | {what's affected} | {temporary solution} |

### 14.2 Technical Debt

| Item | Priority | Effort | Tracking |
|------|----------|--------|----------|
| {debt item} | {H/M/L} | {estimate} | {ticket link} |

### 14.3 Planned Improvements

| Enhancement | Rationale | Target Version |
|-------------|-----------|----------------|
| {enhancement} | {why needed} | {when planned} |

---

## 15. Appendix

### 15.1 Glossary

| Term | Definition |
|------|------------|
| {term} | {definition} |

### 15.2 Design Alternatives Considered

| Alternative | Pros | Cons | Why Not Chosen |
|-------------|------|------|----------------|
| {alternative} | {pros} | {cons} | {rationale} |
