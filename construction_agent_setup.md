# Construction Agent Setup

This guide covers the domain-specific construction scheduling mode added on top of the existing Telegram / WhatsApp / local-web bridge.

## 1. What It Adds

When `CONSTRUCTION_AGENT_ENABLED=true`, the bot gets a dedicated construction-operations business layer with:

- a SQLite source of truth for employees, sites, vehicles, daily requirements, notes, plans, overrides, and briefings
- built-in demo seed data for 20 employees, 10 vehicles, and 10 active sites when the database is empty
- natural-language dispatch queries and note capture in chat
- a local operator console at `/construction`

This mode is opt-in. Existing generic bridge bots keep working unchanged when the flag is off.

## 2. Required Environment

Add these settings for the bot/profile that should run the construction workflow:

```env
CONSTRUCTION_AGENT_ENABLED=true
CONSTRUCTION_AGENT_DB_PATH=/absolute/path/to/construction_agent.sqlite3
CONSTRUCTION_AGENT_AUTO_SEED=true
CONSTRUCTION_AGENT_SEED_PATH=/absolute/path/to/custom_seed.json
```

Notes:

- `CONSTRUCTION_AGENT_DB_PATH` defaults to `construction_agent.sqlite3`.
- In multi-bot mode, an unset `CONSTRUCTION_AGENT_DB_PATH` automatically falls back to `data/<bot-name>/construction_agent.sqlite3`.
- `CONSTRUCTION_AGENT_SEED_PATH` is optional.
- If `CONSTRUCTION_AGENT_AUTO_SEED=true` and the database is empty:
  - the file at `CONSTRUCTION_AGENT_SEED_PATH` is loaded when it exists
  - otherwise the built-in demo dataset is inserted

## 3. Startup Flow

1. Start the bridge normally.
   - If you only want the local operator console, set `WEB_ONLY_MODE=true` and start the env-aware entry point instead of Telegram polling.
2. Open the local status page.
3. If construction mode is enabled, open `/construction`.
4. Generate today’s draft plan from the console or by chat.

The construction database is separate from:

- `sessions.json`
- `chat_log.json`
- `chat_workdirs.json`
- `approval_prefs.json`

That separation is deliberate so rollback does not affect chat/session state.

## 4. Data Onboarding Expectations

The MVP works best when these fields are present:

- Employees:
  - `name`
  - `role_type` or `primary_skill`
  - `availability_status`
  - `can_lead_team`
  - `can_drive`
  - `secondary_skills`
  - `certificates`
  - `home_area`
- Sites:
  - `name`
  - `address`
  - `required_headcount`
  - `required_skills`
  - `required_certificates`
  - `risk_level`
  - `requires_team_lead`
- Daily requirements:
  - `site_id` or `site_name`
  - `work_date`
  - `required_headcount`
  - `required_skills`
  - `required_certificates`
  - `required_vehicle_type`
  - `priority`
- Vehicles:
  - `vehicle_code`
  - `plate_number`
  - `vehicle_type`
  - `seat_capacity`
  - `current_status`

Incomplete data is allowed, but missing skills/certificates/availability reduce plan quality and increase unresolved gaps.

## 5. Operator Workflows

### Chat

Supported examples:

- `今天简报`
- `谁最适合和老王一起工作`
- `哪两个人最适合去 3号工地`
- `为什么没安排老王去 6号工地`
- `记录一下，7号车今天刹车不对，先别跑远`
- `/construction overview`
- `/construction plan`
- `/construction brief`
- `/construction recap`
- `/construction replan 老王今天请假，7号车故障`
- `/construction notes`
- `/construction confirm <note_id>`

### Local Web

Open `/construction` and use:

- `Refresh Overview` for current counts and latest plan
- `Load` / `Save Resource` to inspect and upsert employees, sites, requirements, vehicles, and rules
- `Generate Today Plan` to create a fresh draft
- `Replan From Reason` to apply an exception and rebuild the draft
- `Load Pending` / `Confirm Note` for low-confidence or scheduling-critical notes
- `Apply Override` to replace a recommended assignment and log the reason

## 6. Pilot Guidance

Recommended first pilot:

1. Start with one dedicated bot/profile instead of enabling construction mode everywhere.
2. Verify the built-in seed data and replace it gradually with real employees, real sites, and real vehicles.
3. Generate the morning plan from `/construction` or `/construction brief`.
4. Record field notes by voice or text during the day.
5. Confirm only the notes that should change scheduling-critical data.
6. Apply manual overrides with explicit reasons.
7. Run `/construction recap` at the end of the day and review repeated override patterns.

What to watch during the pilot:

- missing employee certificates
- stale availability states
- sites without daily requirements
- vehicles with seat/type mismatches
- notes left in `pending_review` too long

## 7. Rollback

Rollback is intentionally simple:

1. Set `CONSTRUCTION_AGENT_ENABLED=false`.
2. Restart the bridge.
3. Keep the SQLite file in place.

Effects:

- Telegram / WhatsApp / local chat continue to work as generic bridge frontends.
- Construction-specific APIs and `/construction` UI disappear.
- Existing construction data remains intact in the SQLite file for later re-enable.

## 8. Storage Summary

The construction-mode SQLite database stores:

- employees
- sites
- site daily requirements
- vehicles
- rule configs
- raw notes
- observation logs
- schedule plans
- schedule assignments
- schedule override logs
- daily briefings

The bridge JSON stores remain responsible for session transport concerns only.
