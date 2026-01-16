# Feature Specification: Pipeline Event Persistence & External Integration

**Feature Branch**: `002-pipeline-event-persistence`
**Created**: 2026-01-16
**Status**: Draft
**Input**: User description: "Refactor budpipeline events flow for better external service integration: Add database persistence for pipeline state, enable progress tracking via API polling and pub/sub topics, aggregate multi-step progress updates, support both internal services and external clients via budapp gateway, and establish foundation for future pipeline SDK"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - External Service Monitors Pipeline Progress (Priority: P1)

An external service (or budapp acting as a gateway) initiates a pipeline execution and needs to monitor its progress in real-time without maintaining in-memory state or long-lived connections.

**Why this priority**: This is the foundational capability that enables external integration. Without this, external services cannot reliably use budpipeline, making all other features unusable.

**Independent Test**: Can be fully tested by having an external service start a pipeline via API, then poll for progress using the execution ID. Delivers immediate value by enabling basic external integration.

**Acceptance Scenarios**:

1. **Given** an external service has initiated a pipeline execution, **When** it polls the status endpoint with the execution ID, **Then** it receives the current execution state (PENDING/RUNNING/COMPLETED/FAILED) and overall progress percentage
2. **Given** a pipeline is executing multiple steps, **When** an external service requests detailed progress, **Then** it receives aggregated progress showing completed steps, current step, and estimated time remaining
3. **Given** a pipeline has completed execution, **When** an external service polls for status, **Then** it receives the final result including all step outputs and overall execution duration
4. **Given** a pipeline execution is running, **When** the budpipeline service restarts, **Then** external services can still query the execution state from the database without data loss

---

### User Story 2 - Internal Service Receives Real-Time Updates (Priority: P1)

An internal service (budcluster, budmodel, budsim) subscribes to pipeline events via pub/sub topics to receive immediate notifications as pipeline state changes.

**Why this priority**: Equal priority to P1 because it enables the event-driven architecture for internal services. This is essential for maintaining the current real-time notification system while adding polling capabilities.

**Independent Test**: Can be tested by having an internal service subscribe to a dedicated topic (e.g., "service-X-pipeline-events"), starting a pipeline, and verifying it receives progress events. Delivers value by maintaining current functionality while adding new capabilities.

**Acceptance Scenarios**:

1. **Given** an internal service subscribes to a callback topic, **When** a pipeline execution progresses, **Then** it receives progress events containing step completion, ETA updates, and progress percentages
2. **Given** multiple internal services request the same pipeline execution, **When** they provide different callback topics, **Then** each service receives events on its designated topic without interference
3. **Given** a pipeline step fails and retries, **When** the retry succeeds, **Then** subscribed services receive both retry notifications and success notifications
4. **Given** a pipeline completes execution, **When** all steps are done, **Then** subscribed services receive a final completion event with aggregated results

---

### User Story 3 - Client Retrieves Historical Pipeline Executions (Priority: P2)

A client (external or internal) needs to query historical pipeline executions for auditing, debugging, or analytics purposes.

**Why this priority**: Secondary priority because it's valuable for operations but not required for basic pipeline execution. Builds on P1 by leveraging the same database persistence.

**Independent Test**: Can be tested by executing several pipelines, then querying the API for executions filtered by date range, status, or pipeline name. Delivers value for operational visibility.

**Acceptance Scenarios**:

1. **Given** multiple pipeline executions have completed, **When** a client queries executions filtered by date range, **Then** it receives all executions within that timeframe with summary information
2. **Given** pipeline executions exist with various statuses, **When** a client filters by status (e.g., FAILED), **Then** it receives only executions matching that status
3. **Given** a specific pipeline execution, **When** a client requests detailed execution history, **Then** it receives complete step-by-step progression including timestamps, progress percentages, and intermediate results
4. **Given** executions older than the retention period, **When** a client queries historical data, **Then** it receives only executions within the retention window

---

### User Story 4 - Multiple Clients Track Same Pipeline (Priority: P3)

Multiple clients (e.g., budapp frontend, monitoring dashboard, external analytics service) need to independently track the same pipeline execution using different consumption patterns (polling vs. pub/sub).

**Why this priority**: Lower priority because it's an enhancement that improves scalability and flexibility rather than core functionality. Depends on P1 and P2 implementations.

**Independent Test**: Can be tested by having one client poll via API while another subscribes to events, both tracking the same execution ID. Delivers value for multi-client scenarios.

**Acceptance Scenarios**:

1. **Given** a pipeline execution is running, **When** one client polls via API and another subscribes via pub/sub, **Then** both receive consistent state information at the same logical points in execution
2. **Given** a pipeline has multiple parallel steps, **When** clients query aggregated progress, **Then** they receive a weighted average reflecting the completion state of all concurrent steps
3. **Given** clients request different levels of detail, **When** one requests summary progress and another requests step-level details, **Then** each receives information at the appropriate granularity
4. **Given** a pipeline execution completes, **When** late-joining clients query the execution, **Then** they receive the complete final state even if they weren't monitoring during execution

---

### Edge Cases

- **What happens when a pipeline execution is interrupted mid-execution?**
  System must persist the last known state and mark execution as INTERRUPTED. Clients polling or subscribing should receive clear status indicating the interruption and last completed step.

- **How does the system handle progress events arriving out of order?**
  Database persistence layer must use timestamps and sequence numbers to reconstruct correct order. Aggregated progress calculations must be eventually consistent.

- **What happens when an external client provides an invalid callback topic?**
  System validates topic accessibility before execution starts. If validation fails, execution request is rejected with clear error message indicating topic configuration issue.

- **How does the system handle database failures during pipeline execution?**
  In-memory state is maintained for resilience. Database writes are queued and retried. Clients using pub/sub continue receiving events; polling clients receive stale data until database recovers.

- **What happens when progress percentage calculations result in backwards movement?**
  Progress percentage is monotonically increasing - system never reports lower progress than previously reported, even if step estimation changes.

- **How does the system handle callback topics that become unavailable mid-execution?**
  Event publishing failures are logged but don't stop execution. Failed events are queued for retry. Clients can fall back to polling API if pub/sub fails.

## Requirements *(mandatory)*

### Functional Requirements

#### Database Persistence

- **FR-001**: System MUST persist all pipeline executions to database including execution ID, pipeline definition, start time, end time, status, and final outputs
- **FR-002**: System MUST persist step-level execution state for each pipeline including step ID, step name, status, start time, end time, outputs, and error messages
- **FR-003**: System MUST persist progress events during execution including progress percentage, ETA seconds, current step description, and timestamp
- **FR-004**: System MUST support querying execution state by execution ID without requiring in-memory cache
- **FR-005**: System MUST maintain execution history for a configurable retention period (default: 30 days)

#### API-Based Progress Tracking

- **FR-006**: System MUST provide REST API endpoint to query execution status by execution ID returning current state and overall progress percentage
- **FR-007**: System MUST provide REST API endpoint to retrieve detailed step-by-step execution progress including all completed, running, and pending steps
- **FR-008**: System MUST provide REST API endpoint to list pipeline executions with filtering by date range, status, pipeline name, and initiator
- **FR-009**: System MUST calculate aggregated progress percentage across multiple concurrent steps using weighted averaging based on estimated step durations
- **FR-010**: API responses MUST include timestamps in ISO 8601 format with timezone information for all temporal data

#### Event-Driven Updates (Pub/Sub)

- **FR-011**: System MUST support clients providing callback topics when initiating pipeline execution
- **FR-012**: System MUST publish progress events to specified callback topics including workflow_progress, step_completed, eta_update, and workflow_completed event types
- **FR-013**: System MUST support multiple callback topics per execution enabling multi-client subscription
- **FR-014**: System MUST continue pipeline execution even if event publishing to callback topics fails
- **FR-015**: System MUST include correlation IDs in all published events to enable event ordering and de-duplication

#### Progress Aggregation

- **FR-016**: System MUST aggregate progress from multiple downstream service events (budapp, budcluster, budmodel, budsim) into unified pipeline-level progress percentage
- **FR-017**: System MUST calculate weighted progress based on estimated vs. actual duration of completed steps
- **FR-018**: System MUST provide ETA estimation based on historical execution times for similar pipeline configurations
- **FR-019**: System MUST update progress in real-time as downstream services publish step completion events
- **FR-020**: System MUST ensure progress percentage is monotonically increasing (never decreases during execution)

#### External Service Integration

- **FR-021**: System MUST provide initialization endpoint for external clients to create pipeline execution returning unique execution ID
- **FR-022**: System MUST validate callback topics are accessible before accepting execution request
- **FR-023**: System MUST support both synchronous (polling) and asynchronous (pub/sub) consumption patterns for the same execution
- **FR-024**: System MUST include execution metadata in responses (initiator, creation time, pipeline definition) to support client context
- **FR-025**: System MUST enforce authentication and authorization for external clients accessing pipeline APIs

#### SDK Foundation

- **FR-026**: API design MUST follow RESTful conventions with consistent resource naming, HTTP methods, and status codes
- **FR-027**: API responses MUST use standardized schema structures enabling auto-generation of client libraries
- **FR-028**: System MUST provide OpenAPI/Swagger specification documenting all endpoints, request/response schemas, and authentication requirements
- **FR-029**: System MUST version API endpoints to support future SDK evolution without breaking existing clients
- **FR-030**: System MUST provide webhook-style callbacks as alternative to pub/sub for clients without message broker access

### Key Entities

- **PipelineExecution**: Represents a single execution instance of a pipeline DAG, containing execution ID (UUID), pipeline definition (JSON), initiator identity, start timestamp, end timestamp, status (PENDING/RUNNING/COMPLETED/FAILED/INTERRUPTED), overall progress percentage, final outputs, error information, and callback topics list

- **StepExecution**: Represents execution state of a single step within a pipeline, containing step ID, step name, execution ID (foreign key), status (PENDING/RUNNING/COMPLETED/FAILED/SKIPPED/RETRYING), start timestamp, end timestamp, progress percentage, step outputs (JSON), error message, retry count, and sequence number for ordering

- **ProgressEvent**: Represents a progress update event during execution, containing event ID (UUID), execution ID (foreign key), event type (workflow_progress/step_completed/eta_update/workflow_completed), progress percentage, ETA seconds, current step description, event details (JSON), timestamp, and sequence number

- **ExecutionSubscription**: Represents a client's subscription to execution events, containing subscription ID (UUID), execution ID (foreign key), callback topic name, subscription timestamp, expiry timestamp, and delivery status (active/expired/failed)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: External services can retrieve pipeline execution status via API with response times under 200ms for 95% of requests
- **SC-002**: Pipeline execution state persists across service restarts with zero data loss for running or completed executions
- **SC-003**: Clients receive progress updates within 5 seconds of actual step state changes in downstream services
- **SC-004**: Aggregated progress percentage accurately reflects multi-step execution state with variance under 5% from actual completion
- **SC-005**: System supports at least 100 concurrent pipeline executions with independent progress tracking per execution
- **SC-006**: Historical execution queries return results within 500ms for date ranges up to 30 days
- **SC-007**: Event publication to callback topics succeeds for 99.9% of events under normal operating conditions
- **SC-008**: External clients can poll execution status continuously without degrading system performance (supports 1000 requests/minute)
- **SC-009**: SDK-friendly API design enables client library generation with 100% endpoint coverage from OpenAPI spec
- **SC-010**: Multiple clients tracking same execution via different methods (polling/pub/sub) observe consistent state within 1-second convergence window

### Qualitative Outcomes

- **SC-011**: External service developers can integrate pipeline execution monitoring without understanding internal budpipeline architecture
- **SC-012**: Operational teams can debug failed pipeline executions using persistent execution history without reproducing failures
- **SC-013**: API design patterns are consistent enough that client SDK can be auto-generated for multiple programming languages

## Assumptions

- **A-001**: PostgreSQL database is already provisioned and available for budpipeline service
- **A-002**: Dapr pub/sub infrastructure with Redis/Kafka is available for event publishing
- **A-003**: Downstream services (budapp, budcluster, budmodel, budsim) will continue publishing events to budpipelineEvents topic as designed in current architecture
- **A-004**: External clients have network access to budpipeline API endpoints (either directly or via budapp gateway)
- **A-005**: bud-microframe publish_to_topic enhancement (multi-topic support) is completed before this feature implementation
- **A-006**: Execution retention period of 30 days provides sufficient historical data for operational needs
- **A-007**: Estimated step durations for ETA calculation can be derived from historical execution data or configured defaults
- **A-008**: Authentication/authorization mechanism (likely Dapr-based with API tokens) is already available for budpipeline APIs
- **A-009**: Maximum concurrent executions of 100 is sufficient for current and near-term usage patterns
- **A-010**: Clients consuming via pub/sub have access to the same Dapr pub/sub infrastructure as budpipeline

## Dependencies

- **D-001**: bud-microframe multi-topic pub/sub support (Union[str, List[str]] for target_topic_name)
- **D-002**: PostgreSQL database with sufficient storage and IOPS for persistence layer
- **D-003**: Dapr pub/sub component configured with appropriate topics
- **D-004**: budapp integration updates to forward callback_topics when proxying pipeline execution requests
- **D-005**: Authentication/authorization framework for external API access
- **D-006**: OpenAPI documentation generation tooling for SDK foundation

## Constraints

- **C-001**: Database schema changes must support migration from current in-memory storage without execution data loss
- **C-002**: API response times must not degrade as historical execution data grows (requires efficient indexing strategy)
- **C-003**: Event publishing must not block pipeline execution (asynchronous with retry queue)
- **C-004**: Progress aggregation algorithm must scale to pipelines with 50+ steps without performance degradation
- **C-005**: External API endpoints must enforce rate limiting to prevent abuse (1000 requests/minute per client)

## Out of Scope

- **OS-001**: Full-featured SDK implementation (only API design foundation is in scope)
- **OS-002**: Real-time WebSocket-based streaming (polling and pub/sub are sufficient)
- **OS-003**: GraphQL API (REST API only for initial implementation)
- **OS-004**: Pipeline execution control (pause/resume/cancel) via API
- **OS-005**: Advanced analytics or visualization dashboards
- **OS-006**: Multi-tenancy or workspace isolation features
- **OS-007**: Event replay or time-travel debugging capabilities
- **OS-008**: Automated ETA learning/optimization based on execution history
