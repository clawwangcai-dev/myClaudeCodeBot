## ADDED Requirements

### Requirement: Voice and text note capture
The system SHALL accept spoken or typed operational notes and normalize them into a stored note record with source, timestamp, and raw content.

#### Scenario: Capture a spoken field note
- **WHEN** the owner or dispatcher sends a voice message describing an employee, vehicle, site, or scheduling concern
- **THEN** the system stores the note together with its transcription and source metadata

#### Scenario: Capture a typed note
- **WHEN** the owner or dispatcher sends the same kind of observation as text
- **THEN** the system stores the note without requiring a separate manual transcription step

### Requirement: Structured note classification
The system SHALL classify each captured note into an operational category and resolve any referenced employees, sites, vehicles, schedules, or reminders.

#### Scenario: Classify an employee evaluation
- **WHEN** the note says that a named employee communicated well but moved slowly
- **THEN** the system classifies the note as an employee observation and extracts the employee target plus positive and negative tags

#### Scenario: Classify a site requirement note
- **WHEN** the note says that a named site must have someone who can read drawings tomorrow
- **THEN** the system classifies the note as a site requirement and links it to the referenced site and scheduling date when that information is available

### Requirement: Review and confirmation for ambiguous or high-impact notes
The system SHALL support operator review before a captured note is allowed to influence planning when extraction confidence is low or when the note changes scheduling-critical data.

#### Scenario: Hold a low-confidence note for review
- **WHEN** the extraction step cannot confidently resolve the intended target or note category
- **THEN** the system marks the note as pending review instead of silently applying it to the structured record store

#### Scenario: Confirm a scheduling-critical note
- **WHEN** a captured note would change availability, mandatory qualifications, or site requirements
- **THEN** the system requires confirmation or edit before the note becomes active scheduling input

### Requirement: Observation logs as queryable learning signals
The system SHALL persist classified notes as observation records that can be queried by target, type, sentiment, scheduling impact, and resolution state.

#### Scenario: Create a scheduling-impacting observation
- **WHEN** a note is classified as affecting future scheduling decisions
- **THEN** the resulting observation log records that it impacts scheduling and whether follow-up action is required

#### Scenario: Query recent observations for an employee or site
- **WHEN** the operator asks for recent evaluations or special requirements tied to a named employee or site
- **THEN** the system can retrieve the matching observation records from the structured memory store
