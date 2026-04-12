## Why

Construction dispatch decisions are currently trapped in the owner's head, phone calls, and ad hoc messages, which makes daily planning slow, fragile, and hard to explain when conditions change. The company now needs a usable MVP that can coordinate 20 employees, 10 vehicles, and 10 concurrent sites while preserving the owner's scheduling experience as structured operational memory.

## What Changes

- Introduce a structured construction operations registry for employees, sites, vehicles, certificates, availability, and dispatch rules.
- Add an explainable scheduling engine that recommends employee pairings, site assignments, and vehicle allocations using hard constraints plus weighted scoring.
- Add a voice-first memory pipeline that captures natural-language notes, classifies them into operational records, and links them to employees, sites, vehicles, and future dispatch decisions.
- Add a dispatch control workflow for morning planning, daytime replanning, manual override reasons, and end-of-day learning signals.
- Add operator-facing question answering and summaries grounded in structured scheduling data and operational memory rather than freeform generation.

## Capabilities

### New Capabilities
- `construction-resource-registry`: Manage the structured source of truth for employees, site projects, vehicles, qualifications, attendance, and scheduling rules.
- `explainable-construction-scheduling`: Generate daily dispatch recommendations, pairing scores, team-to-site matches, vehicle assignments, and explanation output from deterministic rules plus weighted scoring.
- `voice-driven-field-memory`: Capture spoken or typed operational notes, classify them into structured observations, and persist learning signals that can influence future dispatch review.
- `dispatch-replanning-and-briefing`: Support morning brief generation, exception-triggered replanning, manual override logging, traceable decision reasons, and end-of-day summaries.

### Modified Capabilities
- None.

## Impact

- Affected code: new domain models, persistence layer, scheduling engine, AI extraction/query services, operator workflows, and notification/summary delivery paths.
- Affected APIs: CRUD and query endpoints for employees/sites/vehicles/rules, scheduling and replanning endpoints, observation ingestion APIs, and question-answering/briefing endpoints.
- External systems: speech-to-text, LLM-based extraction and explanation services, optional messaging channels for summaries and alerts.
- Operational impact: dispatch quality will depend on baseline data completeness, audit logging of manual overrides, and an explicit review loop before recommended plans are confirmed.
