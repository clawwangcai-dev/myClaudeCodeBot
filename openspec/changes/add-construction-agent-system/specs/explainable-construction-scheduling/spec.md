## ADDED Requirements

### Requirement: Daily draft schedule generation
The system SHALL generate a draft daily dispatch plan from the current employee availability, site requirements, vehicle readiness, and active rules.

#### Scenario: Generate a daily plan
- **WHEN** the operator requests today's dispatch suggestion after employees, sites, vehicles, and rules are loaded
- **THEN** the system returns a draft plan containing recommended employee assignments, site assignments, vehicle assignments, and unresolved gaps

### Requirement: Hard constraint enforcement in scheduling
The scheduling engine SHALL reject assignments that violate mandatory safety, qualification, availability, or pairing constraints.

#### Scenario: Exclude unavailable workers and unavailable vehicles
- **WHEN** a planning run encounters an employee marked unavailable or a vehicle marked out of service
- **THEN** the draft plan does not assign that employee or vehicle

#### Scenario: Enforce mandatory certifications and crew structure
- **WHEN** a site requires a certificate, a minimum headcount, a team lead, or a mandatory two-person crew
- **THEN** the draft plan only marks the assignment valid if those hard constraints are satisfied

### Requirement: Pairing and team-to-site scoring
The scheduling engine SHALL compute ranking scores for employee pairings and team-to-site matches using configured scoring factors and stored historical signals.

#### Scenario: Rank the best partner for an employee
- **WHEN** the operator asks which coworker is the strongest partner for a named employee on a given day
- **THEN** the system returns ranked pairing candidates with their score contribution factors

#### Scenario: Rank the best crew for a site
- **WHEN** the operator asks which available two-person team best fits a specific site requirement
- **THEN** the system returns ranked crew recommendations based on skill coverage, certificate fit, collaboration history, and other configured scoring inputs

### Requirement: Risk and conflict surfacing
The scheduling engine SHALL report unresolved gaps, constraint conflicts, and operational risks alongside each draft plan.

#### Scenario: Surface a staffing or qualification gap
- **WHEN** the available workforce cannot fully satisfy a site's headcount or qualification requirements
- **THEN** the system flags the site as at risk and explains which requirement could not be satisfied

#### Scenario: Surface vehicle coverage conflict
- **WHEN** more sites require a specific vehicle type than the available fleet can cover
- **THEN** the system reports the affected sites and the uncovered vehicle constraint in the planning output

### Requirement: Explainable dispatch answers
The system SHALL answer scheduling questions using structured planning data, observation history, and explicit explanation factors rather than unsupported freeform assertions.

#### Scenario: Explain a chosen assignment
- **WHEN** the operator asks why a specific employee pair was assigned to a specific site
- **THEN** the system responds with the recommendation decision and the stored factors that supported it, such as skill fit, certificate coverage, collaboration history, and commute suitability

#### Scenario: Explain why an expected assignment was not chosen
- **WHEN** the operator asks why a named employee was not sent to a named site
- **THEN** the system responds with the blocking constraint, lower score, or conflicting higher-priority need that prevented that assignment
