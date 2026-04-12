## ADDED Requirements

### Requirement: Morning dispatch brief
The system SHALL generate a morning brief that summarizes attendance, active sites, available vehicles, recommended assignments, staffing gaps, and notable risks for the current day.

#### Scenario: Request today's morning brief
- **WHEN** the owner or dispatcher asks for today's brief after the daily planning inputs are available
- **THEN** the system returns a structured summary of resources, recommended dispatch assignments, and unresolved issues that require attention

### Requirement: Exception-driven replanning
The system SHALL support replanning when an operational exception changes the viability of the current draft or confirmed plan.

#### Scenario: Replan after an employee absence
- **WHEN** a scheduled employee reports sick or otherwise becomes unavailable after the original draft was created
- **THEN** the system recomputes the affected assignments and returns a revised recommendation together with the impacted sites and workers

#### Scenario: Replan after a vehicle or site disruption
- **WHEN** a vehicle fault, weather issue, material delay, or urgent site demand change is recorded
- **THEN** the system recalculates the plan and describes how the updated recommendation differs from the prior plan

### Requirement: Manual override logging
The system SHALL record every manual change from a recommended assignment to a final assignment together with the reason for the change.

#### Scenario: Log a dispatcher override
- **WHEN** the operator replaces a recommended worker, vehicle, or site assignment in the draft plan
- **THEN** the system stores the original assignment, new assignment, actor, timestamp, and reason text as an override record

#### Scenario: Preserve override records for later learning review
- **WHEN** the operator marks an override as a useful learning example
- **THEN** the system stores that override as a retained learning signal for later analysis

### Requirement: Evening recap and learning summary
The system SHALL generate an end-of-day recap that compares recommended plans, actual changes, key exceptions, notable observations, and candidate learning signals.

#### Scenario: Generate an evening recap
- **WHEN** the owner or dispatcher requests the daily recap after the workday ends
- **THEN** the system summarizes what was planned, what changed, and which issues or performance notes were captured during execution

#### Scenario: Highlight repeated adjustment patterns
- **WHEN** multiple overrides or observations point to the same recurring issue or preference
- **THEN** the recap identifies that pattern as a candidate rule or coaching signal for future review
