## Context

This repository already provides Telegram, WhatsApp, and local-web entrypoints for a local agent workflow, including voice transcription, chat history, and channel-aware sessions. It does not yet provide a structured construction-operations domain model, dispatch engine, or durable business memory for employees, sites, vehicles, and scheduling decisions.

The requested MVP is not a generic chatbot. It is a construction dispatch control system that must help an owner or dispatcher manage roughly 20 employees, 10 vehicles, and 10 active sites every day. The system must preserve the strengths of the current bridge as the conversational ingress layer while adding a new business layer for structured operations, deterministic planning, and explainable answers.

Primary stakeholders are the owner, dispatcher, foreman/team leads, and office staff. The main operational constraints are incomplete source data, frequent mid-day changes, the need for auditable manual overrides, and the requirement that AI support understanding and explanation without becoming the source of scheduling truth.

## Goals / Non-Goals

**Goals:**
- Add a construction-domain data model for employees, sites, vehicles, daily requirements, observations, rules, and override reasons.
- Produce explainable daily scheduling recommendations that combine hard constraints with weighted scoring for pairing, site fit, and vehicle fit.
- Let operators capture spoken or typed operational notes and convert them into structured memory that can be queried later.
- Support morning brief generation, mid-day replanning, and evening recap workflows across the existing chat and local-web surfaces.
- Keep all business decisions traceable so the system can explain recommendations and preserve learning signals from manual changes.

**Non-Goals:**
- Replacing the existing Telegram/WhatsApp/local bridge with a separate communications stack.
- Building payroll, procurement, accounting, ERP replacement, BIM integration, or customer-facing portals.
- Shipping a globally optimal operations-research solver in v1.
- Letting AI automatically rewrite rules or auto-confirm production dispatch plans without operator review.
- Solving multi-company or multi-branch tenancy in the first iteration.

## Decisions

### 1. Add a construction domain service behind the existing bridge

The current bridge will remain the interaction shell for Telegram, WhatsApp, and local web. The new work will introduce a construction-domain layer, likely grouped under a new package such as `construction_agent/`, that owns business entities, scheduling workflows, and operator-facing commands or intents.

Why this over building a separate standalone app first:
- The repository already has working multi-channel ingress, voice handling, and conversation state.
- The owner explicitly wants to record ideas and evaluations in natural language at any time, which the existing bridge already supports operationally.
- Keeping the bridge as ingress reduces time-to-MVP and avoids duplicating message transport logic.

Alternative considered:
- Create a separate web application and integrate chat channels later. Rejected for v1 because it delays the highest-value workflow: capturing dispatch decisions and notes directly from the field.

### 2. Use SQLite as the MVP source of truth for construction operations

The business layer will store structured operational data in a dedicated SQLite database file, separate from the bridge's existing JSON session/chat state. Core tables will include employees, site projects, vehicles, daily requirements, schedule plans, observation logs, rules, and schedule overrides.

Why this over JSON files or an immediate Postgres dependency:
- SQLite is available through Python's standard library and matches the repository's current low-dependency posture.
- The target scale for v1 is modest and single-instance friendly.
- Structured joins and transactions are required for explainable scheduling and audit trails; JSON blobs are too brittle for that.

Alternative considered:
- Continue using JSON-backed storage for business data. Rejected because the dispatch engine needs relational queries, history, and transactional updates.
- Introduce Postgres immediately. Rejected for v1 because it raises deployment and operational complexity before product fit is validated.

### 3. Implement scheduling as a deterministic constraint engine plus weighted scoring

Daily scheduling will run in two stages:
1. Hard-constraint filtering removes invalid combinations based on availability, certificates, mandatory team leads, vehicle status, maximum hours, and blocked pairings.
2. Weighted scoring ranks valid employee pairs or teams against site requirements using factors such as skill complementarity, certification coverage, historical collaboration quality, commute reasonableness, urgency, and growth opportunities.

The planner should produce both the chosen assignments and the explanation trace that names the factors used. A greedy assignment plus repair pass is sufficient for v1 as long as it is deterministic and auditable.

Why this over end-to-end LLM planning or an exact optimizer first:
- The PRD requires that AI not directly "guess" schedules.
- Deterministic filters plus score breakdowns are easier to explain to an owner and easier to debug.
- Heuristic assignment is implementable quickly for the target scale and can be evolved toward stronger optimization later.

Alternative considered:
- Let the LLM generate full schedules directly. Rejected because it is difficult to guarantee hard constraints and explanation fidelity.
- Adopt a heavier exact solver from day one. Rejected because it increases algorithmic and dependency complexity before baseline data quality is proven.

### 4. Restrict AI responsibilities to extraction, grounding, and explanation

AI will be used for three jobs:
- Convert spoken or freeform text notes into structured records with targets, tags, and possible scheduling impact.
- Answer operator questions by grounding responses in the structured schedule and observation store.
- Render human-readable explanations and summaries from deterministic outputs.

AI will not be the authority for hard constraints, final schedule validity, or automatic rule mutation.

Why this split:
- It follows the PRD principle that rules decide and AI explains.
- It reduces hallucination risk for operational decisions.
- It keeps the owner's trust by ensuring that every recommendation can be traced to stored facts and scoring logic.

Alternative considered:
- Manual-only note entry and no AI structuring. Rejected because the core value proposition includes voice-first capture in the field.
- AI-managed rules and fully automatic learning. Rejected because it is too risky for first deployment.

### 5. Persist override reasons and execution feedback as learning signals, not auto-applied rules

Every manual adjustment to a suggested plan will be stored with the original assignment, new assignment, actor, reason type, and free-text explanation. Observation logs, exception events, and outcome feedback will also be preserved as learning signals that later versions can analyze.

Why this over immediate rule rewriting:
- The first operational need is to capture the owner's thinking, not to automate it away.
- Separating signal capture from rule mutation avoids hidden behavioral drift.
- Reviewable signals make it easier to add recommendation tuning later.

Alternative considered:
- Automatically rewrite weights or rule tables after each override. Rejected because early data will be noisy and context-dependent.

### 6. Deliver the first operator workflow through the existing local web UI plus chat-driven actions

The first version should reuse the repository's current local status/chat surface as the operational console, extended with construction-specific pages or endpoints for registry maintenance, daily plans, observation review, and recap views. Chat channels remain the quickest entrypoint for ad hoc notes, questions, and summary retrieval.

Why this over a brand-new frontend stack:
- It keeps the MVP compact and aligned with the current codebase.
- Local web already exists for inspection and operator interaction.
- Chat remains the best interface for on-the-road voice and text capture.

Alternative considered:
- Build a fully separate SPA before exposing the workflows. Rejected because it front-loads UI infrastructure instead of the core dispatch behavior.

### 7. Gate the new business system behind explicit configuration

Construction-domain workflows should be enabled only when a dedicated profile or config flag is set. Existing generic bridge bots must continue to function without construction-specific data stores or prompts.

Why this over changing default bridge behavior:
- The repository already supports multiple usage modes.
- A domain-specific rollout should not break existing operator workflows in unrelated bots.
- A dedicated configuration surface also creates a clean rollback path.

Alternative considered:
- Make all bridge sessions construction-aware by default. Rejected because it would couple the generic bridge too tightly to one domain.

## Risks / Trade-offs

- [Operational data starts incomplete or inconsistent] → Mitigation: support unknown/default states, require minimal mandatory fields, and surface missing-data warnings in planning output.
- [Heuristic scheduling is explainable but not globally optimal] → Mitigation: keep score breakdowns visible, log overrides, and leave room for future solver upgrades after real usage data exists.
- [AI misclassifies field notes] → Mitigation: add confidence-based review/edit flows before high-impact records are committed as scheduling inputs.
- [SQLite and a single local service limit scale and concurrency] → Mitigation: keep the database isolated behind repository/service modules so a later move to Postgres does not rewrite business logic.
- [Construction workflows could leak into generic bridge behavior] → Mitigation: use explicit configuration gating and dedicated routing for construction intents.
- [Notification noise can reduce adoption] → Mitigation: start with on-demand briefs and high-priority exception alerts before enabling broader automated pushes.

## Migration Plan

1. Add construction-agent configuration, a dedicated SQLite schema, and repository/service modules for core entities.
2. Implement CRUD and import flows for employees, sites, vehicles, rules, and daily requirements.
3. Implement the scheduling engine v1 with hard-constraint validation, weighted scoring, and explanation traces.
4. Wire voice/text note capture into structured observation extraction, review, and persistence.
5. Extend local web and chat workflows for morning briefs, replanning, manual override logging, and evening recap.
6. Pilot with one dedicated construction bot/profile, tune weights and rules from real overrides, then widen usage.

Rollback strategy:
- Disable the construction-agent config/profile and leave the existing bridge channels running in generic mode.
- Preserve the SQLite business database as a separate artifact so rollback does not corrupt bridge chat/session state.

## Open Questions

- Which provider will handle production-grade speech-to-text and extraction prompts: the current local toolchain, a remote LLM API, or a hybrid?
- Should initial operator data entry support CSV import for employees, vehicles, and sites to accelerate onboarding?
- How will commute distance be calculated in v1: static zones/manual distance fields or map-service integration?
- How will end-of-day "actual execution" data be collected: manual dispatcher entry, foreman feedback, or chat-driven check-ins?
