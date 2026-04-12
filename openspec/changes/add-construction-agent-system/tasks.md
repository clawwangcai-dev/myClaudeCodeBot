## 1. Construction profile and data foundation

- [x] 1.1 Add a construction-agent configuration/profile that enables the new domain workflows without changing generic bridge behavior
- [x] 1.2 Create the SQLite schema and repository layer for employees, site projects, daily requirements, vehicles, rules, observations, schedule plans, and override logs
- [x] 1.3 Add database bootstrap and seed-loading support so a dedicated construction bot/profile can start with usable baseline data

## 2. Resource registry workflows

- [x] 2.1 Implement CRUD services and validation for employee records, including skills, certificates, availability, partner preferences, and fatigue-related fields
- [x] 2.2 Implement CRUD services and validation for site projects and daily requirements, including headcount, required skills, certificates, urgency, and risk fields
- [x] 2.3 Implement CRUD services and validation for vehicle readiness and structured dispatch rules with audit metadata
- [x] 2.4 Extend the local web/operator surface to create, edit, and inspect construction registry data

## 3. Explainable scheduling engine

- [x] 3.1 Implement hard-constraint validation for availability, qualifications, team-lead requirements, blocked pairings, headcount, hours, and vehicle readiness
- [x] 3.2 Implement weighted scoring for employee pairing, team-to-site fit, and vehicle-to-site fit using configurable scoring factors and historical signals
- [x] 3.3 Build the daily draft-plan generator with assignment output, unresolved gaps, risk/conflict reporting, and deterministic explanation traces
- [x] 3.4 Add grounded question-answering flows that explain chosen and rejected assignments from stored planning data

## 4. Voice-driven field memory

- [x] 4.1 Route typed and transcribed voice notes into a construction-note ingestion pipeline with source metadata and timestamps
- [x] 4.2 Implement note classification and entity resolution for employees, sites, vehicles, scheduling instructions, risks, and idea memos
- [x] 4.3 Add review/confirmation handling for low-confidence or scheduling-critical notes before they become active planning inputs
- [x] 4.4 Persist classified observations as queryable learning signals and expose retrieval flows for recent employee and site history

## 5. Briefing, replanning, and learning workflows

- [x] 5.1 Implement the morning brief workflow that summarizes attendance, active sites, available vehicles, draft assignments, gaps, and risks
- [x] 5.2 Implement exception-driven replanning for absences, vehicle faults, weather/material changes, and urgent site-demand changes
- [x] 5.3 Add manual override workflows that capture original assignment, final assignment, actor, reason, and learnable status
- [x] 5.4 Implement the evening recap workflow that compares planned versus changed assignments and highlights candidate learning patterns

## 6. Verification and rollout

- [x] 6.1 Add test fixtures and scenario coverage for the target MVP scale of 20 employees, 10 vehicles, and 10 concurrent sites
- [x] 6.2 Verify chat and local-web flows for note capture, dispatch suggestions, explanation queries, replanning, and summaries under the construction profile
- [x] 6.3 Document setup, data onboarding expectations, rollback steps, and pilot-operation guidance for the construction-agent deployment
