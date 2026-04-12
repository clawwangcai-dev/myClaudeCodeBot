## ADDED Requirements

### Requirement: Structured employee registry
The system SHALL maintain employee records with the scheduling attributes required for dispatch decisions, including role, skills, certificates, leadership capability, driving capability, availability state, fatigue-related fields, and partner preferences.

#### Scenario: Save an employee profile
- **WHEN** an operator creates or updates an employee with role, skills, certificates, and availability details
- **THEN** the system stores the employee as a schedulable resource record that future planning runs can query

#### Scenario: Mark an employee unavailable for dispatch
- **WHEN** an operator records leave, sickness, or another unavailability state for an employee on a given day
- **THEN** the registry preserves that state so scheduling workflows can exclude the employee from that day's recommendation set

### Requirement: Structured site project requirements
The system SHALL maintain site-project records and daily requirement records that describe required headcount, required skills, certificates, urgency, risk level, lead-worker needs, vehicle needs, and notes relevant to dispatch.

#### Scenario: Save a site's daily requirement
- **WHEN** an operator records that a site needs a specific headcount, skill mix, and certificate coverage for a date
- **THEN** the system stores that requirement as an input to the daily scheduling engine

#### Scenario: Record a site with lead or risk constraints
- **WHEN** an operator marks a site as requiring a team lead, special certificate, or elevated risk handling
- **THEN** the registry exposes those constraints to schedule validation and explanation flows

### Requirement: Vehicle readiness registry
The system SHALL maintain vehicle records with capacity, use-case fit, assigned-driver constraints, availability state, and maintenance status for dispatch planning.

#### Scenario: Save a vehicle profile
- **WHEN** an operator creates or updates a vehicle with seating capacity, load type, and maintenance metadata
- **THEN** the system stores that vehicle as a dispatchable asset for assignment workflows

#### Scenario: Mark a vehicle unavailable
- **WHEN** an operator records that a vehicle is under maintenance or otherwise out of service
- **THEN** the registry marks the vehicle unavailable so scheduling workflows cannot assign it to a draft plan

### Requirement: Configurable dispatch rules with audit metadata
The system SHALL store dispatch rules as structured, prioritized, and activatable records with creator and update metadata.

#### Scenario: Activate a dispatch rule
- **WHEN** an operator creates or enables a rule describing a scheduling constraint or preference
- **THEN** the system stores the rule with its priority and activation state so future schedule runs can apply it

#### Scenario: Audit a rule change
- **WHEN** an operator changes a rule definition or disables a rule
- **THEN** the system records who changed it and when so later reviews can understand why dispatch behavior changed
