# Long-term Memory

Curated, persistent knowledge that remains true across sessions.
Entries are promoted here from daily learnings via `/budmem promote`.

---

## Architecture Decisions

- **budnotify `CloudEventBase` uses `extra="forbid"`**: Any unknown top-level fields in the notification payload cause 422 errors. The publisher payload must only contain declared fields (`notification_type`, `name`, `subscriber_ids`, `actor`, `topic_keys`, `payload`) plus Dapr envelope fields. Put extra data inside the nested `payload` dict. *(2026-02-24)*

- **budpipeline EventPublisher sends ONE payload to ALL topics**: The same dict from `_build_event_payload` goes to callback topics (e.g. `budAppMessages`) AND `notificationMessages` (Novu). You cannot add fields one consumer needs but another rejects. Service-specific data must go inside the nested `payload` dict. *(2026-02-24)*

- **budpipeline `subscriber_ids` auto-set enables Novu for ALL flows**: `BudPipelineService.run_ephemeral_execution()` and `execute_pipeline()` auto-set `subscriber_ids=user_id` when `user_id` is provided. ALL pipeline executions with a user_id will dual-publish to Novu. Changes to the publisher payload format affect guardrails, usecases, and any future pipeline flow. *(2026-02-24)*

## Coding Preferences

<!-- Style and pattern preferences -->

## Project Conventions

<!-- Team standards and practices -->

## Service-Specific

### budapp
<!-- Main API service learnings -->

### budadmin
<!-- Frontend dashboard learnings -->

### budcluster
<!-- Cluster management learnings -->

### budsim
<!-- Simulation service learnings -->

### budgateway
<!-- API gateway learnings -->

## Anti-patterns

<!-- Things to avoid -->
