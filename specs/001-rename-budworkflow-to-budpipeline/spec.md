# Feature Specification: Rename BudWorkflow to BudPipeline

**Feature Branch**: `001-rename-budworkflow-to-budpipeline`
**Created**: 2026-01-15
**Status**: Draft
**Input**: User description: "The current budworkflow module need to rename to budpipeline. This name should be updated everywhere relevant."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Service Core Rename (Priority: P1)

As a developer or DevOps engineer, I need the budworkflow service to be renamed to budpipeline across all internal components, so that the codebase reflects the correct terminology and service purpose without breaking existing functionality.

**Why this priority**: This is the foundational change that all other updates depend on. The internal service must be renamed first before external interfaces can be updated. Without this, the system cannot function.

**Independent Test**: Deploy the renamed service in isolation with new Dapr app ID and verify it starts successfully, responds to health checks, and can execute a simple pipeline/workflow without errors.

**Acceptance Scenarios**:

1. **Given** the service code exists in `services/budworkflow/`, **When** the directory and Python package are renamed to `budpipeline`, **Then** all internal imports resolve correctly and the service starts without errors
2. **Given** Dapr configuration uses app-id "budworkflow", **When** the app-id is changed to "budpipeline", **Then** Dapr sidecar initializes successfully and service mesh communication works
3. **Given** the service uses pub/sub topic "budworkflowEvents", **When** the topic is renamed to "budpipelineEvents", **Then** event publishing and subscription work without message loss
4. **Given** environment variables reference "BUDWORKFLOW", **When** they are renamed to "BUDPIPELINE", **Then** configuration loads correctly with appropriate defaults
5. **Given** Docker images are tagged as "budworkflow", **When** they are retagged as "budpipeline", **Then** Helm deployments use the correct image and containers start successfully

---

### User Story 2 - API Interface Updates (Priority: P2)

As an API consumer (internal service or external client), I need API endpoints to be updated from `/budworkflow` to `/budpipeline`, so that I can access pipeline functionality using the correct terminology while maintaining backward compatibility during transition.

**Why this priority**: API endpoints are the primary integration point for other services. This must be done after core service rename (P1) but before frontend updates (P3) to ensure the backend is ready when UI changes roll out.

**Independent Test**: Make API requests to the new `/budpipeline` endpoints and verify all 22 operations (create, list, execute, schedules, webhooks, triggers, etc.) return correct responses with proper status codes.

**Acceptance Scenarios**:

1. **Given** budapp proxies requests to budworkflow service, **When** the proxy routes are updated to `/budpipeline`, **Then** all API operations complete successfully
2. **Given** other services publish events to "budworkflowEvents" topic, **When** they switch to "budpipelineEvents", **Then** pipeline service receives and processes events correctly
3. **Given** Dapr service invocation uses app-id "budworkflow", **When** it is updated to "budpipeline", **Then** inter-service calls succeed with proper retry and circuit breaking
4. **Given** API documentation references budworkflow, **When** it is updated to budpipeline, **Then** developers can discover and use endpoints correctly

---

### User Story 3 - Frontend User Interface Updates (Priority: P3)

As a platform user accessing the web dashboard, I need the workflow management UI to be updated to reflect "Pipelines" terminology, so that the interface is consistent with the renamed service and I can continue managing my pipelines without disruption.

**Why this priority**: Frontend updates are last because they depend on backend API changes being complete. Users should experience a seamless transition where the UI terminology changes but functionality remains identical.

**Independent Test**: Navigate to the pipelines section in budadmin, create a new pipeline, execute it, view execution history, and manage schedules—all operations should work with the new URL structure and terminology.

**Acceptance Scenarios**:

1. **Given** users navigate to `/workflows` URLs, **When** they are redirected to `/pipelines` URLs, **Then** the correct pages load without 404 errors
2. **Given** the UI displays "Workflows" in navigation and page titles, **When** text is updated to "Pipelines", **Then** all user-facing text reflects the new terminology
3. **Given** the frontend makes API calls to `/budworkflow` endpoints, **When** calls are updated to `/budpipeline`, **Then** all CRUD operations, executions, and schedule management work correctly
4. **Given** users have bookmarks to workflow pages, **When** old URLs redirect to new URLs, **Then** bookmarks continue to work
5. **Given** React components and stores reference "workflow" names, **When** they are renamed to "pipeline" equivalents, **Then** the UI renders correctly with no console errors

---

### Edge Cases

- What happens when a pipeline execution is in progress during the deployment of the rename?
- How does the system handle Dapr state store keys that contain the old "budworkflow" prefix?
- What if external webhooks are still configured to call the old `/budworkflow` API endpoints?
- How are Docker images handled if both old and new tags exist simultaneously during transition?
- What happens to scheduled pipeline executions (cron jobs) during the service rename?
- How does the system handle cached frontend builds that reference old workflow URLs?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST rename the Python service package from "budworkflow" to "budpipeline" while preserving all internal module structure and functionality
- **FR-002**: System MUST update all Dapr configuration to use app-id "budpipeline" instead of "budworkflow" for service mesh communication
- **FR-003**: System MUST rename the pub/sub topic from "budworkflowEvents" to "budpipelineEvents" and update all publishers and subscribers
- **FR-004**: System MUST update API routes from `/budworkflow/*` to `/budpipeline/*` while maintaining all 22 endpoint operations
- **FR-005**: System MUST rename environment variables from "BUD_WORKFLOW_*" pattern to "BUD_PIPELINE_*" pattern
- **FR-006**: System MUST update Helm chart values from "budworkflow:" to "budpipeline:" with correct image references
- **FR-007**: System MUST update Docker image tags from "budworkflow" to "budpipeline" for all container registries
- **FR-008**: System MUST rename frontend routes from `/workflows` to `/pipelines` with URL redirects for backward compatibility
- **FR-009**: System MUST update all frontend components, stores, and pages to use "pipeline" terminology instead of "workflow"
- **FR-010**: System MUST update all Python imports throughout the codebase from "budworkflow" to "budpipeline"
- **FR-011**: System MUST update Helm template files to reference the renamed service and Dapr components
- **FR-012**: System MUST NOT migrate existing Dapr state store data (existing state with old "budworkflow" keys will be ignored, only new state will use "budpipeline" prefix)
- **FR-013**: System MUST drain or cancel all in-flight pipeline executions before deployment to ensure clean cutover to renamed service
- **FR-014**: System MUST remove all `/budworkflow` API endpoints immediately as a breaking change, requiring all external consumers to migrate to `/budpipeline` endpoints

### Key Entities

- **Pipeline Service**: Renamed from budworkflow, orchestrates DAG execution, scheduling, and webhook management across the platform
- **Pipeline Definition**: Configuration specifying DAG structure, steps, dependencies, and execution parameters
- **Pipeline Execution**: Running or completed instance of a pipeline with execution state, logs, and results
- **Schedule**: Cron-based trigger for automated pipeline execution
- **Webhook**: HTTP endpoint that triggers pipeline execution from external events
- **Event Trigger**: Dapr pub/sub subscription that starts pipeline execution when specific events occur

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All automated tests pass after the rename, demonstrating that functionality is preserved (100% test success rate)
- **SC-002**: The service starts successfully in all environments (dev, staging, production) with new naming within 2 minutes of deployment
- **SC-003**: All in-flight pipeline executions are successfully drained or cancelled before deployment begins (zero executions in "running" state)
- **SC-004**: External API consumers receive advance notification (minimum 7 days) before the breaking change deployment
- **SC-005**: All 70+ affected files are updated consistently with no remaining references to "budworkflow" in active code paths
- **SC-006**: Frontend users can access and use pipeline features without noticing any functional differences (same operations, same performance)
- **SC-007**: Documentation and configuration files reflect the new "budpipeline" terminology within one day of deployment
- **SC-008**: Platform performance metrics (API latency, throughput, execution time) remain within 5% of pre-rename baselines

## Assumptions

1. **Breaking change accepted**: This is a breaking change with planned downtime for draining in-flight executions before deployment
2. **State data loss acceptable**: Existing Dapr state store data with "budworkflow" key prefixes will be abandoned (pipelines, executions, schedules start fresh)
3. **Semantic equivalence**: "Pipeline" and "workflow" are conceptually equivalent in this context—no functional changes beyond naming
4. **Container registry access**: DevOps has permissions to push new Docker images with "budpipeline" tags
5. **Helm chart versioning**: Helm chart version will be bumped to reflect this breaking change (likely MAJOR version bump)
6. **Frontend build process**: Next.js frontend will be rebuilt and redeployed as part of this change
7. **External integrations**: External webhook callers and API consumers will be notified of the breaking change and must migrate to new endpoints before deployment
8. **Testing coverage**: Existing test suites provide adequate coverage to verify the rename doesn't break functionality
9. **Deployment coordination**: Deployment will be coordinated to drain/cancel in-flight executions before cutover
10. **Communication plan**: Stakeholders and external API consumers will be notified in advance of the breaking changes and migration requirements

## Dependencies

- Git repository access for renaming directories and updating references
- Docker registry access for pushing renamed images
- Kubernetes cluster access for deploying updated Helm charts
- Dapr runtime properly configured for updated app-id and pub/sub topics
- Database/state store access remains unchanged (PostgreSQL, Valkey/Redis)
- Build and CI/CD pipelines updated to reflect new service name
