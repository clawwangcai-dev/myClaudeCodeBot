from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

from channel_keys import ConversationRef
from config import Settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


def _tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _coerce_int(value: Any, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        loaded = _json_loads(text, [])
        if isinstance(loaded, list):
            return [str(item).strip() for item in loaded if str(item).strip()]
    return [part.strip() for part in re.split(r"[,，;/\n]+", text) if part.strip()]


def _slugify(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value.strip())
    text = text.strip("-").lower()
    return text or uuid.uuid4().hex[:8]


def _parse_date_hint(text: str) -> str:
    clean = text.strip()
    if not clean:
        return _today_iso()
    for pattern in (r"\b(\d{4}-\d{2}-\d{2})\b", r"\b(\d{4}/\d{2}/\d{2})\b"):
        match = re.search(pattern, clean)
        if match:
            return match.group(1).replace("/", "-")
    if "明天" in clean or "tomorrow" in clean.lower():
        return _tomorrow_iso()
    return _today_iso()


def _priority_value(value: str | int | None) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "").strip().lower()
    mapping = {
        "critical": 100,
        "urgent": 90,
        "high": 75,
        "medium": 50,
        "low": 25,
        "紧急": 90,
        "高": 75,
        "中": 50,
        "低": 25,
    }
    return mapping.get(text, _coerce_int(value, default=50))


def _sentiment_score(sentiment: str) -> int:
    return {"positive": 1, "negative": -1, "neutral": 0}.get(sentiment, 0)


class ConstructionAgentService:
    RESOURCE_KINDS = {"employees", "sites", "requirements", "vehicles", "rules"}

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = settings.construction_agent_enabled
        self._db_path = settings.construction_agent_db_path
        self._seed_path = settings.construction_agent_seed_path
        self._lock = threading.RLock()
        if not self._enabled:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._managed_connection() as conn:
            self._bootstrap(conn)
        if settings.construction_agent_auto_seed:
            self._seed_if_needed()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _managed_connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                employee_code TEXT UNIQUE NOT NULL,
                name TEXT UNIQUE NOT NULL,
                phone TEXT DEFAULT '',
                role_type TEXT NOT NULL,
                level TEXT DEFAULT '',
                primary_skill TEXT DEFAULT '',
                secondary_skills_json TEXT NOT NULL DEFAULT '[]',
                certificates_json TEXT NOT NULL DEFAULT '[]',
                can_drive INTEGER NOT NULL DEFAULT 0,
                can_lead_team INTEGER NOT NULL DEFAULT 0,
                can_work_alone INTEGER NOT NULL DEFAULT 0,
                home_area TEXT DEFAULT '',
                availability_status TEXT NOT NULL DEFAULT 'available',
                max_daily_hours REAL NOT NULL DEFAULT 8,
                fatigue_score REAL NOT NULL DEFAULT 0,
                performance_score REAL NOT NULL DEFAULT 50,
                safety_score REAL NOT NULL DEFAULT 50,
                communication_score REAL NOT NULL DEFAULT 50,
                learning_score REAL NOT NULL DEFAULT 50,
                preferred_partners_json TEXT NOT NULL DEFAULT '[]',
                avoided_partners_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                site_code TEXT UNIQUE NOT NULL,
                name TEXT UNIQUE NOT NULL,
                address TEXT DEFAULT '',
                gps_location TEXT DEFAULT '',
                distance_from_base REAL NOT NULL DEFAULT 0,
                start_time TEXT DEFAULT '08:00',
                required_headcount INTEGER NOT NULL DEFAULT 2,
                required_skills_json TEXT NOT NULL DEFAULT '[]',
                required_certificates_json TEXT NOT NULL DEFAULT '[]',
                risk_level TEXT DEFAULT 'medium',
                requires_team_lead INTEGER NOT NULL DEFAULT 0,
                equipment_needs_json TEXT NOT NULL DEFAULT '[]',
                material_needs_json TEXT NOT NULL DEFAULT '[]',
                urgency_level INTEGER NOT NULL DEFAULT 50,
                customer_priority INTEGER NOT NULL DEFAULT 50,
                weather_sensitive INTEGER NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS site_daily_requirements (
                id TEXT PRIMARY KEY,
                site_id TEXT NOT NULL,
                work_date TEXT NOT NULL,
                start_time TEXT DEFAULT '08:00',
                required_headcount INTEGER NOT NULL DEFAULT 2,
                required_skills_json TEXT NOT NULL DEFAULT '[]',
                required_certificates_json TEXT NOT NULL DEFAULT '[]',
                required_vehicle_type TEXT DEFAULT '',
                required_tools_json TEXT NOT NULL DEFAULT '[]',
                priority INTEGER NOT NULL DEFAULT 50,
                urgency_level INTEGER NOT NULL DEFAULT 50,
                task_description TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(site_id, work_date),
                FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                id TEXT PRIMARY KEY,
                vehicle_code TEXT UNIQUE NOT NULL,
                plate_number TEXT UNIQUE NOT NULL,
                vehicle_type TEXT DEFAULT '',
                seat_capacity INTEGER NOT NULL DEFAULT 2,
                load_type TEXT DEFAULT '',
                current_status TEXT NOT NULL DEFAULT 'available',
                maintenance_status TEXT DEFAULT 'ok',
                preferred_use_case TEXT DEFAULT '',
                assigned_driver_constraints_json TEXT NOT NULL DEFAULT '[]',
                current_location TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rule_configs (
                id TEXT PRIMARY KEY,
                rule_name TEXT UNIQUE NOT NULL,
                rule_type TEXT NOT NULL,
                rule_description TEXT DEFAULT '',
                rule_priority INTEGER NOT NULL DEFAULT 50,
                active_status INTEGER NOT NULL DEFAULT 1,
                condition_json TEXT NOT NULL DEFAULT '{}',
                action_json TEXT NOT NULL DEFAULT '{}',
                created_by TEXT DEFAULT 'system',
                updated_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS raw_notes (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                source_conversation_key TEXT NOT NULL,
                source_user TEXT NOT NULL,
                work_date TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                audio_path TEXT DEFAULT '',
                classification_type TEXT NOT NULL,
                target_type TEXT DEFAULT '',
                target_id TEXT DEFAULT '',
                target_name TEXT DEFAULT '',
                sentiment TEXT NOT NULL DEFAULT 'neutral',
                tags_json TEXT NOT NULL DEFAULT '[]',
                parsed_payload_json TEXT NOT NULL DEFAULT '{}',
                impacts_scheduling INTEGER NOT NULL DEFAULT 0,
                action_required INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'applied',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS observation_logs (
                id TEXT PRIMARY KEY,
                note_id TEXT,
                created_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_user TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT DEFAULT '',
                target_name TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                sentiment TEXT NOT NULL DEFAULT 'neutral',
                tags_json TEXT NOT NULL DEFAULT '[]',
                content TEXT NOT NULL,
                impacts_scheduling INTEGER NOT NULL DEFAULT 0,
                action_required INTEGER NOT NULL DEFAULT 0,
                resolved_status TEXT NOT NULL DEFAULT 'open',
                confidence REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(note_id) REFERENCES raw_notes(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS schedule_plans (
                id TEXT PRIMARY KEY,
                work_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_reason TEXT DEFAULT 'manual',
                created_by TEXT DEFAULT 'system',
                previous_plan_id TEXT DEFAULT '',
                summary_json TEXT NOT NULL DEFAULT '{}',
                generated_at TEXT NOT NULL,
                confirmed_by TEXT DEFAULT '',
                confirmed_at TEXT DEFAULT '',
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS schedule_assignments (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                site_name TEXT NOT NULL,
                employee_ids_json TEXT NOT NULL DEFAULT '[]',
                employee_names_json TEXT NOT NULL DEFAULT '[]',
                vehicle_id TEXT DEFAULT '',
                vehicle_label TEXT DEFAULT '',
                score REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'draft',
                explanation_json TEXT NOT NULL DEFAULT '{}',
                risk_flags_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES schedule_plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS schedule_override_logs (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                assignment_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                original_assignment_json TEXT NOT NULL,
                new_assignment_json TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                reason_type TEXT NOT NULL,
                reason_text TEXT NOT NULL,
                should_learn INTEGER NOT NULL DEFAULT 0,
                learned_status TEXT NOT NULL DEFAULT 'recorded',
                FOREIGN KEY(plan_id) REFERENCES schedule_plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS daily_briefings (
                id TEXT PRIMARY KEY,
                work_date TEXT NOT NULL,
                briefing_type TEXT NOT NULL,
                content TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def _seed_if_needed(self) -> None:
        with self._lock, self._managed_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
            if count:
                return
            payload = self._load_seed_payload()
            self._apply_seed(conn, payload)

    def _load_seed_payload(self) -> dict[str, list[dict[str, Any]]]:
        if self._seed_path and self._seed_path.exists():
            return json.loads(self._seed_path.read_text(encoding="utf-8"))
        return self._build_demo_seed()

    def _apply_seed(self, conn: sqlite3.Connection, payload: dict[str, list[dict[str, Any]]]) -> None:
        now = _utc_now_iso()
        for record in payload.get("employees", []):
            self._upsert_employee(conn, record, timestamp=now)
        for record in payload.get("sites", []):
            self._upsert_site(conn, record, timestamp=now)
        for record in payload.get("requirements", []):
            self._upsert_requirement(conn, record, timestamp=now)
        for record in payload.get("vehicles", []):
            self._upsert_vehicle(conn, record, timestamp=now)
        for record in payload.get("rules", []):
            self._upsert_rule(conn, record, timestamp=now)
        conn.commit()

    def _build_demo_seed(self) -> dict[str, list[dict[str, Any]]]:
        names = [
            "老周",
            "老王",
            "小刘",
            "小王",
            "老刘",
            "张强",
            "王建",
            "陈涛",
            "赵兵",
            "孙雷",
            "李军",
            "阿杰",
            "老马",
            "许峰",
            "吴健",
            "小张",
            "小陈",
            "小赵",
            "老何",
            "小孙",
        ]
        primary_skills = [
            "木工",
            "泥瓦",
            "焊工",
            "电工",
            "防水",
            "看图纸",
            "钢筋",
            "油漆",
            "安装",
            "普工",
        ]
        areas = ["城北", "城东", "城南", "城西", "开发区"]
        employees: list[dict[str, Any]] = []
        for index, name in enumerate(names, start=1):
            primary_skill = primary_skills[(index - 1) % len(primary_skills)]
            secondary = [primary_skills[index % len(primary_skills)], "安全作业"]
            certificates = ["高处作业证"] if index % 3 == 0 else []
            if primary_skill in {"电工", "焊工"}:
                certificates.append(f"{primary_skill}证")
            employees.append(
                {
                    "id": f"emp-{index:02d}",
                    "employee_code": f"E{index:03d}",
                    "name": name,
                    "role_type": primary_skill,
                    "level": "高级" if index <= 6 else "中级" if index <= 14 else "初级",
                    "primary_skill": primary_skill,
                    "secondary_skills": secondary,
                    "certificates": certificates,
                    "can_drive": index % 4 == 0,
                    "can_lead_team": index <= 8,
                    "can_work_alone": index <= 10,
                    "home_area": areas[(index - 1) % len(areas)],
                    "availability_status": "available",
                    "max_daily_hours": 9 if index <= 10 else 8,
                    "fatigue_score": 15 + (index % 5) * 6,
                    "performance_score": 65 + (index % 6) * 5,
                    "safety_score": 70 + (index % 4) * 6,
                    "communication_score": 60 + (index % 5) * 7,
                    "learning_score": 55 + (index % 6) * 6,
                    "preferred_partners": [names[index % len(names)]] if index % 5 == 0 else [],
                    "avoided_partners": ["小赵"] if name == "老王" else ["老王"] if name == "小赵" else [],
                    "notes": "内置演示数据",
                }
            )

        sites: list[dict[str, Any]] = []
        requirements: list[dict[str, Any]] = []
        site_skill_map = [
            ("1号工地", "城北", ["木工", "看图纸"], ["高处作业证"], "high"),
            ("2号工地", "城东", ["泥瓦", "防水"], [], "medium"),
            ("3号工地", "城南", ["焊工", "安装"], ["焊工证"], "critical"),
            ("4号工地", "城西", ["电工", "看图纸"], ["电工证"], "high"),
            ("5号工地", "开发区", ["木工", "带队"], [], "high"),
            ("6号工地", "城北", ["钢筋", "安装"], [], "medium"),
            ("7号工地", "城东", ["油漆", "普工"], [], "low"),
            ("8号工地", "城南", ["防水", "高处作业"], ["高处作业证"], "high"),
            ("9号工地", "城西", ["电工", "安装"], ["电工证"], "medium"),
            ("10号工地", "开发区", ["普工", "看图纸"], [], "low"),
        ]
        for index, (name, area, skills, certs, risk) in enumerate(site_skill_map, start=1):
            site_id = f"site-{index:02d}"
            sites.append(
                {
                    "id": site_id,
                    "site_code": f"S{index:03d}",
                    "name": name,
                    "address": f"{area}施工点{index}",
                    "distance_from_base": 8 + index * 2,
                    "start_time": "08:00",
                    "required_headcount": 2 if index <= 7 else 3,
                    "required_skills": skills,
                    "required_certificates": certs,
                    "risk_level": risk,
                    "requires_team_lead": index in {1, 3, 4, 5, 8},
                    "equipment_needs": ["基础工具箱"],
                    "material_needs": ["常规材料"],
                    "urgency_level": _priority_value("critical" if index in {3, 5} else "high" if index in {1, 4, 8} else "medium"),
                    "customer_priority": 80 if index in {3, 5} else 60,
                    "weather_sensitive": index in {2, 7, 8},
                    "notes": "内置演示工地",
                }
            )
            requirements.append(
                {
                    "id": f"req-{index:02d}",
                    "site_id": site_id,
                    "work_date": _today_iso(),
                    "start_time": "08:00",
                    "required_headcount": 2 if index <= 7 else 3,
                    "required_skills": skills,
                    "required_certificates": certs,
                    "required_vehicle_type": "货车" if index in {3, 6} else "面包车",
                    "required_tools": ["基础工具箱"],
                    "priority": 90 if index in {3, 5} else 75 if index in {1, 4, 8} else 50,
                    "urgency_level": 90 if index in {3, 5} else 70,
                    "task_description": f"{name} 当日作业",
                    "notes": "自动生成的演示需求",
                }
            )

        vehicles = []
        for index in range(1, 11):
            vehicles.append(
                {
                    "id": f"veh-{index:02d}",
                    "vehicle_code": f"V{index:02d}",
                    "plate_number": f"沪A{index:04d}",
                    "vehicle_type": "货车" if index in {3, 6, 9} else "面包车",
                    "seat_capacity": 5 if index not in {3, 6, 9} else 3,
                    "load_type": "heavy" if index in {3, 6, 9} else "light",
                    "current_status": "available",
                    "maintenance_status": "ok",
                    "preferred_use_case": "远距离工地" if index in {3, 6, 9} else "市内工地",
                    "assigned_driver_constraints": [],
                    "current_location": areas[(index - 1) % len(areas)],
                    "notes": "内置演示车辆",
                }
            )

        rules = [
            {
                "id": "rule-must-cert",
                "rule_name": "证照必须覆盖",
                "rule_type": "hard_constraint",
                "rule_description": "工地要求的关键证照必须由班组覆盖",
                "rule_priority": 100,
                "active_status": True,
                "condition": {"type": "required_certificates"},
                "action": {"type": "reject_if_missing"},
                "created_by": "seed",
                "updated_by": "seed",
            },
            {
                "id": "rule-avoid-bad-pair",
                "rule_name": "禁配搭档不允许同组",
                "rule_type": "hard_constraint",
                "rule_description": "存在 avoided_partners 的员工不得安排在同一班组",
                "rule_priority": 95,
                "active_status": True,
                "condition": {"type": "avoided_partners"},
                "action": {"type": "reject_pair"},
                "created_by": "seed",
                "updated_by": "seed",
            },
            {
                "id": "rule-prefer-mentor",
                "rule_name": "优先老带新",
                "rule_type": "scoring_bonus",
                "rule_description": "带队员工搭配学习分较高员工时加分",
                "rule_priority": 60,
                "active_status": True,
                "condition": {"type": "mentor_pair"},
                "action": {"type": "score_bonus", "points": 8},
                "created_by": "seed",
                "updated_by": "seed",
            },
        ]
        return {
            "employees": employees,
            "sites": sites,
            "requirements": requirements,
            "vehicles": vehicles,
            "rules": rules,
        }

    def overview(self, *, work_date: str | None = None) -> dict[str, Any]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            counts = {
                "employees": conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0],
                "sites": conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0],
                "requirements": conn.execute("SELECT COUNT(*) FROM site_daily_requirements WHERE work_date = ?", (target_date,)).fetchone()[0],
                "vehicles": conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0],
                "pending_notes": conn.execute("SELECT COUNT(*) FROM raw_notes WHERE status = 'pending_review'").fetchone()[0],
            }
            latest_plan = self._latest_plan(conn, target_date)
            overview = {
                "enabled": True,
                "work_date": target_date,
                "counts": counts,
                "latest_plan": latest_plan,
                "pending_notes": self.list_notes(status="pending_review", limit=10),
            }
            return overview

    def list_resources(self, kind: str) -> list[dict[str, Any]]:
        self._ensure_enabled()
        kind = kind.strip().lower()
        with self._lock, self._managed_connection() as conn:
            if kind == "employees":
                rows = conn.execute("SELECT * FROM employees ORDER BY employee_code").fetchall()
                return [self._employee_row_to_dict(row) for row in rows]
            if kind == "sites":
                rows = conn.execute("SELECT * FROM sites ORDER BY site_code").fetchall()
                return [self._site_row_to_dict(row) for row in rows]
            if kind == "requirements":
                rows = conn.execute(
                    """
                    SELECT r.*, s.name AS site_name
                    FROM site_daily_requirements r
                    JOIN sites s ON s.id = r.site_id
                    ORDER BY r.work_date DESC, s.site_code ASC
                    """
                ).fetchall()
                return [self._requirement_row_to_dict(row) for row in rows]
            if kind == "vehicles":
                rows = conn.execute("SELECT * FROM vehicles ORDER BY vehicle_code").fetchall()
                return [self._vehicle_row_to_dict(row) for row in rows]
            if kind == "rules":
                rows = conn.execute("SELECT * FROM rule_configs ORDER BY rule_priority DESC, rule_name ASC").fetchall()
                return [self._rule_row_to_dict(row) for row in rows]
            if kind == "plans":
                rows = conn.execute("SELECT * FROM schedule_plans ORDER BY generated_at DESC").fetchall()
                return [self._plan_row_to_dict(row) for row in rows]
            if kind == "notes":
                return self.list_notes(limit=100)
            if kind == "overrides":
                rows = conn.execute("SELECT * FROM schedule_override_logs ORDER BY changed_at DESC").fetchall()
                return [self._override_row_to_dict(row) for row in rows]
        raise ValueError(f"Unsupported resource kind: {kind}")

    def save_resource(self, kind: str, record: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        kind = kind.strip().lower()
        with self._lock, self._managed_connection() as conn:
            now = _utc_now_iso()
            if kind == "employees":
                saved = self._upsert_employee(conn, record, timestamp=now)
            elif kind == "sites":
                saved = self._upsert_site(conn, record, timestamp=now)
            elif kind == "requirements":
                saved = self._upsert_requirement(conn, record, timestamp=now)
            elif kind == "vehicles":
                saved = self._upsert_vehicle(conn, record, timestamp=now)
            elif kind == "rules":
                saved = self._upsert_rule(conn, record, timestamp=now)
            else:
                raise ValueError(f"Unsupported resource kind: {kind}")
            conn.commit()
            return saved

    def list_notes(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        self._ensure_enabled()
        query = "SELECT * FROM raw_notes"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        if limit > 0:
            query += f" LIMIT {int(limit)}"
        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._note_row_to_dict(row) for row in rows]

    def confirm_note(self, note_id: str, *, actor: str = "operator") -> dict[str, Any]:
        self._ensure_enabled()
        with self._lock, self._managed_connection() as conn:
            row = conn.execute("SELECT * FROM raw_notes WHERE id = ?", (note_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown note id: {note_id}")
            note = self._note_row_to_dict(row)
            payload = note["parsed_payload"]
            if note["status"] == "applied":
                return {"note": note, "applied": False, "message": "Note already applied."}
            self._apply_note_payload(conn, note, payload, actor=actor)
            conn.execute(
                "UPDATE raw_notes SET status = 'applied', updated_at = ? WHERE id = ?",
                (_utc_now_iso(), note_id),
            )
            observation = self._create_observation_from_note(conn, note_id)
            conn.commit()
            refreshed = conn.execute("SELECT * FROM raw_notes WHERE id = ?", (note_id,)).fetchone()
            return {
                "note": self._note_row_to_dict(refreshed) if refreshed is not None else note,
                "observation": observation,
                "applied": True,
            }

    def generate_plan(
        self,
        *,
        work_date: str | None = None,
        created_reason: str = "manual",
        created_by: str = "system",
        previous_plan_id: str = "",
    ) -> dict[str, Any]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            resources = self._load_planning_resources(conn, target_date)
            plan = self._build_plan(
                conn,
                work_date=target_date,
                resources=resources,
                created_reason=created_reason,
                created_by=created_by,
                previous_plan_id=previous_plan_id,
            )
            conn.commit()
            return plan

    def morning_brief(self, *, work_date: str | None = None) -> dict[str, Any]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            latest = self._latest_plan(conn, target_date)
            if latest is None:
                latest = self._build_plan(
                    conn,
                    work_date=target_date,
                    resources=self._load_planning_resources(conn, target_date),
                    created_reason="morning-brief",
                    created_by="system",
                    previous_plan_id="",
                )
            payload = self._build_brief_payload(conn, latest, briefing_type="morning")
            conn.execute(
                """
                INSERT INTO daily_briefings (id, work_date, briefing_type, content, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    target_date,
                    "morning",
                    payload["text"],
                    _json_dumps(payload),
                    _utc_now_iso(),
                ),
            )
            conn.commit()
            return payload

    def replan(self, *, reason: str, work_date: str | None = None, actor: str = "operator") -> dict[str, Any]:
        self._ensure_enabled()
        target_date = work_date or _parse_date_hint(reason)
        with self._lock, self._managed_connection() as conn:
            before = self._latest_plan(conn, target_date)
            event_note = self._capture_note(
                conn,
                conversation_key="construction:replan",
                channel="construction",
                source_user=actor,
                source_type="system",
                text=reason,
                audio_path=None,
                force_review=False,
            )
            if event_note["status"] == "pending_review":
                self._apply_note_payload(conn, event_note, event_note["parsed_payload"], actor=actor)
                conn.execute(
                    "UPDATE raw_notes SET status = 'applied', updated_at = ? WHERE id = ?",
                    (_utc_now_iso(), event_note["id"]),
                )
                self._create_observation_from_note(conn, event_note["id"])
            after = self._build_plan(
                conn,
                work_date=target_date,
                resources=self._load_planning_resources(conn, target_date),
                created_reason="replan",
                created_by=actor,
                previous_plan_id=before["id"] if before else "",
            )
            diff = self._diff_plans(before, after)
            conn.commit()
            return {"note": event_note, "plan": after, "diff": diff}

    def apply_override(
        self,
        *,
        plan_id: str,
        assignment_id: str,
        new_employee_names: list[str] | None,
        new_vehicle_code: str | None,
        changed_by: str,
        reason_type: str,
        reason_text: str,
        should_learn: bool,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        with self._lock, self._managed_connection() as conn:
            assignment_row = conn.execute(
                "SELECT * FROM schedule_assignments WHERE id = ? AND plan_id = ?",
                (assignment_id, plan_id),
            ).fetchone()
            if assignment_row is None:
                raise ValueError("Assignment not found.")
            assignment = self._assignment_row_to_dict(assignment_row)
            original = dict(assignment)

            employee_names = new_employee_names or assignment["employee_names"]
            employees = [self._find_employee_by_name(conn, name) for name in employee_names]
            if any(employee is None for employee in employees):
                missing = [name for name, employee in zip(employee_names, employees) if employee is None]
                raise ValueError(f"Unknown employees in override: {', '.join(missing)}")
            employee_rows = [employee for employee in employees if employee is not None]

            vehicle_row = assignment["vehicle"]
            if new_vehicle_code:
                vehicle = self._find_vehicle_by_code(conn, new_vehicle_code)
                if vehicle is None:
                    raise ValueError(f"Unknown vehicle code: {new_vehicle_code}")
                vehicle_row = self._vehicle_row_to_dict(vehicle)

            updated = {
                "employee_ids_json": _json_dumps([row["id"] for row in employee_rows]),
                "employee_names_json": _json_dumps([row["name"] for row in employee_rows]),
                "vehicle_id": vehicle_row["id"] if vehicle_row else "",
                "vehicle_label": vehicle_row["vehicle_code"] if vehicle_row else "",
            }
            conn.execute(
                """
                UPDATE schedule_assignments
                SET employee_ids_json = ?, employee_names_json = ?, vehicle_id = ?, vehicle_label = ?
                WHERE id = ?
                """,
                (
                    updated["employee_ids_json"],
                    updated["employee_names_json"],
                    updated["vehicle_id"],
                    updated["vehicle_label"],
                    assignment_id,
                ),
            )
            log_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO schedule_override_logs (
                    id, plan_id, assignment_id, site_id, original_assignment_json, new_assignment_json,
                    changed_by, changed_at, reason_type, reason_text, should_learn, learned_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    plan_id,
                    assignment_id,
                    assignment["site_id"],
                    _json_dumps(original),
                    _json_dumps(
                        {
                            **original,
                            "employee_names": [row["name"] for row in employee_rows],
                            "vehicle": vehicle_row,
                        }
                    ),
                    changed_by,
                    _utc_now_iso(),
                    reason_type,
                    reason_text,
                    1 if should_learn else 0,
                    "pending_review" if should_learn else "recorded",
                ),
            )
            conn.commit()
            refreshed = conn.execute("SELECT * FROM schedule_assignments WHERE id = ?", (assignment_id,)).fetchone()
            return {
                "override_id": log_id,
                "assignment": self._assignment_row_to_dict(refreshed) if refreshed is not None else original,
            }

    def evening_recap(self, *, work_date: str | None = None) -> dict[str, Any]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            latest = self._latest_plan(conn, target_date)
            if latest is None:
                latest = self._build_plan(
                    conn,
                    work_date=target_date,
                    resources=self._load_planning_resources(conn, target_date),
                    created_reason="recap-bootstrap",
                    created_by="system",
                    previous_plan_id="",
                )
            observations = self._observations_for_date(conn, target_date)
            overrides = self._overrides_for_date(conn, target_date)
            payload = self._build_recap_payload(latest, observations, overrides)
            conn.execute(
                """
                INSERT INTO daily_briefings (id, work_date, briefing_type, content, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    target_date,
                    "evening",
                    payload["text"],
                    _json_dumps(payload),
                    _utc_now_iso(),
                ),
            )
            conn.commit()
            return payload

    def explain_assignment(self, *, work_date: str | None = None, site_name: str | None = None, employee_name: str | None = None) -> str:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            plan = self._latest_plan(conn, target_date)
            if plan is None:
                return "今天还没有生成排班方案。"
            assignments = plan["assignments"]
            selected = None
            for item in assignments:
                if site_name and item["site_name"] != site_name:
                    continue
                if employee_name and employee_name not in item["employee_names"]:
                    continue
                selected = item
                break
            if selected is None:
                selected = assignments[0] if assignments else None
            if selected is None:
                return "当前方案里没有可解释的排班明细。"
            explanation = selected["explanation"]
            factors = explanation.get("factors", [])
            factor_text = "\n".join(f"- {item}" for item in factors) or "- 无详细因子"
            return (
                f"{selected['site_name']} 的安排是：{', '.join(selected['employee_names']) or '无人'}"
                f"{'，车辆 ' + selected['vehicle']['vehicle_code'] if selected['vehicle'] else ''}。\n"
                f"综合评分：{selected['score']:.1f}\n"
                f"原因：\n{factor_text}"
            )

    def explain_rejection(self, employee_name: str, site_name: str, *, work_date: str | None = None) -> str:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            employee_row = self._find_employee_by_name(conn, employee_name)
            site_row = self._find_site_by_name(conn, site_name)
            if employee_row is None or site_row is None:
                return "没有找到对应的员工或工地。"
            employee = self._employee_row_to_dict(employee_row)
            site = self._site_row_to_dict(site_row)
            plan = self._latest_plan(conn, target_date)
            if plan is None:
                return "今天还没有排班方案。"
            requirement = self._requirement_for_site(conn, site["id"], target_date)
            if requirement is None:
                return f"{site_name} 今天没有单独需求记录。"
            if employee["availability_status"] != "available":
                return f"{employee_name} 当前状态为 {employee['availability_status']}，因此没有进入今日可排班池。"
            current_assignment = next(
                (item for item in plan["assignments"] if employee_name in item["employee_names"]),
                None,
            )
            chosen_for_site = next((item for item in plan["assignments"] if item["site_id"] == site["id"]), None)
            if current_assignment and current_assignment["site_id"] != site["id"]:
                return (
                    f"{employee_name} 已被安排到 {current_assignment['site_name']}，"
                    f"因为该工地优先级或匹配分更高。"
                )
            reasons = []
            employee_skills = {employee["primary_skill"], *employee["secondary_skills"]}
            missing_skills = [skill for skill in requirement["required_skills"] if skill not in employee_skills]
            missing_certs = [cert for cert in requirement["required_certificates"] if cert not in employee["certificates"]]
            if missing_skills:
                reasons.append(f"缺少关键技能：{', '.join(missing_skills)}")
            if missing_certs:
                reasons.append(f"缺少关键资质：{', '.join(missing_certs)}")
            if chosen_for_site:
                reasons.append(
                    f"{site_name} 当前选择的班组为 {', '.join(chosen_for_site['employee_names'])}，"
                    f"综合评分 {chosen_for_site['score']:.1f}"
                )
            if not reasons:
                reasons.append("当前没有发现硬性阻塞，主要原因是替代组合评分更高。")
            return f"没有安排 {employee_name} 去 {site_name}，原因如下：\n- " + "\n- ".join(reasons)

    def recommend_partners(self, employee_name: str, *, work_date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            employee_row = self._find_employee_by_name(conn, employee_name)
            if employee_row is None:
                raise ValueError(f"Unknown employee: {employee_name}")
            employee = self._employee_row_to_dict(employee_row)
            employees = self._available_employee_rows(conn, target_date)
            results = []
            for candidate in employees:
                if candidate["id"] == employee["id"]:
                    continue
                valid, score, factors = self._pair_score(employee, candidate)
                if not valid:
                    continue
                results.append(
                    {
                        "employee": candidate["name"],
                        "score": score,
                        "factors": factors,
                    }
                )
            return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def recommend_team_for_site(self, site_name: str, *, work_date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_enabled()
        target_date = work_date or _today_iso()
        with self._lock, self._managed_connection() as conn:
            site_row = self._find_site_by_name(conn, site_name)
            if site_row is None:
                raise ValueError(f"Unknown site: {site_name}")
            site = self._site_row_to_dict(site_row)
            requirement = self._requirement_for_site(conn, site["id"], target_date)
            if requirement is None:
                raise ValueError(f"No requirement for {site_name} on {target_date}")
            employees = self._available_employee_rows(conn, target_date)
            team_size = max(2 if site["requires_team_lead"] else 1, requirement["required_headcount"])
            candidates = []
            if team_size == 1:
                for employee in employees:
                    valid, score, factors, risks = self._team_site_score([employee], site, requirement)
                    if not valid:
                        continue
                    candidates.append(
                        {
                            "team": [employee["name"]],
                            "score": score,
                            "factors": factors,
                            "risks": risks,
                        }
                    )
            else:
                for pair in combinations(employees, 2):
                    valid, score, factors, risks = self._team_site_score(list(pair), site, requirement)
                    if not valid:
                        continue
                    candidates.append(
                        {
                            "team": [pair[0]["name"], pair[1]["name"]],
                            "score": score,
                            "factors": factors,
                            "risks": risks,
                        }
                    )
            return sorted(candidates, key=lambda item: item["score"], reverse=True)[:limit]

    def recent_observations(self, target_name: str, *, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_enabled()
        with self._lock, self._managed_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observation_logs
                WHERE target_name = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (target_name, limit),
            ).fetchall()
            return [self._observation_row_to_dict(row) for row in rows]

    def top_performers(self, *, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure_enabled()
        with self._lock, self._managed_connection() as conn:
            rows = [self._employee_row_to_dict(row) for row in conn.execute("SELECT * FROM employees").fetchall()]
            results = []
            for employee in rows:
                observations = self.recent_observations(employee["name"], limit=10)
                signal = sum(_sentiment_score(item["sentiment"]) for item in observations)
                score = (
                    employee["performance_score"] * 0.45
                    + employee["safety_score"] * 0.2
                    + employee["communication_score"] * 0.2
                    + employee["learning_score"] * 0.15
                    + signal * 3
                )
                results.append({"employee": employee["name"], "score": round(score, 1)})
            return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def help_text(self) -> str:
        return (
            "建筑调度指令：\n"
            "/construction overview\n"
            "/construction plan [YYYY-MM-DD]\n"
            "/construction brief [YYYY-MM-DD]\n"
            "/construction recap [YYYY-MM-DD]\n"
            "/construction replan <原因>\n"
            "/construction partners <员工名>\n"
            "/construction site <工地名>\n"
            "/construction notes\n"
            "/construction confirm <note_id>\n"
            "也支持自然语言，例如：\n"
            "谁最适合和老王一起工作\n"
            "哪两个人最适合去 3号工地\n"
            "为什么没安排老王去 6号工地\n"
            "记录一下，7号车今天刹车不对"
        )

    def handle_text(
        self,
        conversation: ConversationRef,
        text: str,
        *,
        source_type: str = "text",
        audio_path: str | None = None,
    ) -> str | None:
        if not self._enabled:
            return None
        clean = text.strip()
        if not clean:
            return None
        if clean.startswith("/construction"):
            return self._handle_command(conversation, clean, source_type=source_type, audio_path=audio_path)
        if "重新排班" in clean or clean.lower().startswith("replan"):
            result = self.replan(reason=clean, actor=conversation.key)
            return self._format_replan_result(result)
        if any(token in clean for token in ("今日简报", "今天简报", "morning brief", "today brief", "今日总览")):
            return self.morning_brief()["text"]
        if any(token in clean for token in ("晚间复盘", "今日复盘", "evening recap", "daily recap")):
            return self.evening_recap()["text"]
        if re.search(r"(谁).*(适合).*(一起|搭班)", clean):
            employee_name = self._extract_known_name(clean, resource_kind="employees")
            if employee_name:
                partners = self.recommend_partners(employee_name)
                if not partners:
                    return f"目前没有找到 {employee_name} 的合适搭档。"
                lines = [f"{employee_name} 的推荐搭档："]
                for item in partners:
                    lines.append(f"- {item['employee']}：{item['score']:.1f} 分")
                return "\n".join(lines)
        if re.search(r"(哪|谁).*(两个人|班组).*(工地|site)", clean) or re.search(r"最适合去.+工地", clean):
            site_name = self._extract_known_name(clean, resource_kind="sites")
            if site_name:
                teams = self.recommend_team_for_site(site_name)
                if not teams:
                    return f"目前没有找到适合 {site_name} 的候选班组。"
                lines = [f"{site_name} 的推荐班组："]
                for item in teams:
                    lines.append(f"- {', '.join(item['team'])}：{item['score']:.1f} 分")
                return "\n".join(lines)
        if "最近谁表现最好" in clean or "top performer" in clean.lower():
            lines = ["最近表现最稳的员工："]
            for item in self.top_performers():
                lines.append(f"- {item['employee']}：{item['score']:.1f} 分")
            return "\n".join(lines)
        if ("评价" in clean or "观察" in clean or "要求" in clean or "history" in clean.lower()) and self._extract_known_name(clean, resource_kind="employees"):
            target_name = self._extract_known_name(clean, resource_kind="employees")
            observations = self.recent_observations(target_name)
            if not observations:
                return f"{target_name} 目前还没有最近观察记录。"
            lines = [f"{target_name} 最近记录："]
            for item in observations:
                lines.append(f"- {item['created_at']}: {item['event_type']} / {item['content']}")
            return "\n".join(lines)
        if ("评价" in clean or "要求" in clean or "history" in clean.lower()) and self._extract_known_name(clean, resource_kind="sites"):
            target_name = self._extract_known_name(clean, resource_kind="sites")
            observations = self.recent_observations(target_name)
            if not observations:
                return f"{target_name} 目前还没有最近要求记录。"
            lines = [f"{target_name} 最近记录："]
            for item in observations:
                lines.append(f"- {item['created_at']}: {item['event_type']} / {item['content']}")
            return "\n".join(lines)
        if clean.startswith("为什么") or clean.lower().startswith("why"):
            employee_name = self._extract_known_name(clean, resource_kind="employees")
            site_name = self._extract_known_name(clean, resource_kind="sites")
            if "没安排" in clean or "not" in clean.lower():
                if employee_name and site_name:
                    return self.explain_rejection(employee_name, site_name)
            return self.explain_assignment(work_date=_parse_date_hint(clean), site_name=site_name, employee_name=employee_name)
        if source_type == "voice" or clean.startswith(("记录", "记一下", "note", "memo", "备忘")):
            note = self.capture_note(
                conversation=conversation,
                text=clean,
                source_type=source_type,
                audio_path=audio_path,
            )
            return self._format_note_ack(note)
        return None

    def capture_note(
        self,
        *,
        conversation: ConversationRef,
        text: str,
        source_type: str,
        audio_path: str | None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        with self._lock, self._managed_connection() as conn:
            note = self._capture_note(
                conn,
                conversation_key=conversation.key,
                channel=conversation.channel,
                source_user=conversation.chat_id,
                source_type=source_type,
                text=text,
                audio_path=audio_path,
                force_review=False,
            )
            if note["status"] == "applied":
                self._create_observation_from_note(conn, note["id"])
            conn.commit()
            return note

    def _capture_note(
        self,
        conn: sqlite3.Connection,
        *,
        conversation_key: str,
        channel: str,
        source_user: str,
        source_type: str,
        text: str,
        audio_path: str | None,
        force_review: bool,
    ) -> dict[str, Any]:
        analysis = self._classify_note(conn, text, source_type=source_type)
        status = "pending_review" if force_review or analysis["needs_review"] else "applied"
        note_id = uuid.uuid4().hex
        now = _utc_now_iso()
        conn.execute(
            """
            INSERT INTO raw_notes (
                id, source_type, source_channel, source_conversation_key, source_user, work_date,
                raw_text, audio_path, classification_type, target_type, target_id, target_name,
                sentiment, tags_json, parsed_payload_json, impacts_scheduling, action_required,
                confidence, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                source_type,
                channel,
                conversation_key,
                source_user,
                analysis["work_date"],
                text,
                audio_path or "",
                analysis["event_type"],
                analysis["target_type"],
                analysis["target_id"],
                analysis["target_name"],
                analysis["sentiment"],
                _json_dumps(analysis["tags"]),
                _json_dumps(analysis["payload"]),
                1 if analysis["impacts_scheduling"] else 0,
                1 if analysis["action_required"] else 0,
                analysis["confidence"],
                status,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM raw_notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist note.")
        return self._note_row_to_dict(row)

    def _classify_note(self, conn: sqlite3.Connection, text: str, *, source_type: str) -> dict[str, Any]:
        clean = text.strip()
        work_date = _parse_date_hint(clean)
        employee_name = self._extract_known_name(clean, resource_kind="employees", conn=conn)
        site_name = self._extract_known_name(clean, resource_kind="sites", conn=conn)
        vehicle_name = self._extract_known_name(clean, resource_kind="vehicles", conn=conn)
        target_type = ""
        target_id = ""
        target_name = ""
        event_type = "idea_memo"
        sentiment = "neutral"
        tags: list[str] = []
        payload: dict[str, Any] = {"raw_text": clean}
        confidence = 0.55
        impacts_scheduling = False
        action_required = False
        needs_review = False

        positive_markers = ["不错", "很好", "稳定", "配合好", "good", "strong", "适合"]
        negative_markers = ["慢", "问题", "故障", "风险", "不行", "差", "bad", "delay", "fault"]
        if any(marker in clean for marker in positive_markers):
            sentiment = "positive"
        if any(marker in clean for marker in negative_markers):
            sentiment = "negative"

        if employee_name and any(token in clean for token in ("请假", "病假", "休息", "不来", "leave", "sick")):
            row = self._find_employee_by_name(conn, employee_name)
            target_type = "employee"
            target_id = row["id"] if row else ""
            target_name = employee_name
            event_type = "employee_absence"
            impacts_scheduling = True
            action_required = True
            needs_review = True
            confidence = 0.92
            tags.extend(["absence", "availability"])
            payload.update({"action": "set_employee_availability", "employee_id": target_id, "value": "leave"})
        elif vehicle_name and any(token in clean for token in ("故障", "坏", "维修", "刹车", "repair", "fault")):
            row = self._find_vehicle_by_code(conn, vehicle_name) or self._find_vehicle_by_name(conn, vehicle_name)
            target_type = "vehicle"
            target_id = row["id"] if row else ""
            target_name = vehicle_name
            event_type = "vehicle_issue"
            impacts_scheduling = True
            action_required = True
            needs_review = True
            confidence = 0.9
            tags.extend(["vehicle", "risk"])
            payload.update({"action": "set_vehicle_status", "vehicle_id": target_id, "value": "repair"})
        elif site_name and any(token in clean for token in ("一定要", "需要", "必须", "带", "工地", "site")):
            row = self._find_site_by_name(conn, site_name)
            target_type = "site"
            target_id = row["id"] if row else ""
            target_name = site_name
            event_type = "site_requirement"
            impacts_scheduling = True
            action_required = True
            needs_review = True
            confidence = 0.82
            extracted_skills = []
            for skill in ("看图纸", "木工", "泥瓦", "焊工", "电工", "防水", "安装", "高处作业"):
                if skill in clean:
                    extracted_skills.append(skill)
            tags.extend(extracted_skills or ["site"])
            payload.update(
                {
                    "action": "update_site_requirement",
                    "site_id": target_id,
                    "work_date": work_date,
                    "add_required_skills": extracted_skills,
                }
            )
        elif employee_name and any(token in clean for token in ("沟通", "动作", "收尾", "配合", "表现", "评价", "带新人")):
            row = self._find_employee_by_name(conn, employee_name)
            target_type = "employee"
            target_id = row["id"] if row else ""
            target_name = employee_name
            event_type = "employee_observation"
            impacts_scheduling = any(token in clean for token in ("带新人", "尽量跟", "安排"))
            action_required = impacts_scheduling
            needs_review = False
            confidence = 0.88
            if "沟通" in clean:
                tags.append("沟通")
            if "动作" in clean or "慢" in clean:
                tags.append("速度")
            if "带新人" in clean:
                tags.append("带教")
            payload.update({"action": "log_observation"})
        elif any(token in clean for token in ("风险", "下雨", "材料", "延误", "客户要求")):
            target_type = "site" if site_name else ""
            if site_name:
                row = self._find_site_by_name(conn, site_name)
                target_id = row["id"] if row else ""
                target_name = site_name
            event_type = "risk_alert"
            impacts_scheduling = True
            action_required = True
            needs_review = not bool(site_name)
            confidence = 0.75 if site_name else 0.58
            tags.extend(["risk"])
            payload.update({"action": "log_risk"})
        elif employee_name and any(token in clean for token in ("尽量跟", "一起", "搭班", "安排")):
            row = self._find_employee_by_name(conn, employee_name)
            target_type = "employee"
            target_id = row["id"] if row else ""
            target_name = employee_name
            event_type = "scheduling_instruction"
            impacts_scheduling = True
            action_required = True
            needs_review = True
            confidence = 0.7
            tags.extend(["dispatch"])
            payload.update({"action": "dispatch_instruction"})

        if target_name:
            confidence = max(confidence, 0.72)
        if source_type == "voice" and event_type == "idea_memo":
            confidence = 0.68
        if event_type == "idea_memo":
            payload.update({"action": "memo"})
            if source_type == "voice":
                tags.append("voice")

        return {
            "work_date": work_date,
            "target_type": target_type,
            "target_id": target_id,
            "target_name": target_name,
            "event_type": event_type,
            "sentiment": sentiment,
            "tags": tags,
            "payload": payload,
            "confidence": round(confidence, 2),
            "impacts_scheduling": impacts_scheduling,
            "action_required": action_required,
            "needs_review": needs_review,
        }

    def _apply_note_payload(self, conn: sqlite3.Connection, note: dict[str, Any], payload: dict[str, Any], *, actor: str) -> None:
        action = payload.get("action")
        now = _utc_now_iso()
        if action == "set_employee_availability" and payload.get("employee_id"):
            conn.execute(
                "UPDATE employees SET availability_status = ?, updated_at = ? WHERE id = ?",
                (payload.get("value", "leave"), now, payload["employee_id"]),
            )
        elif action == "set_vehicle_status" and payload.get("vehicle_id"):
            conn.execute(
                "UPDATE vehicles SET current_status = ?, updated_at = ? WHERE id = ?",
                (payload.get("value", "repair"), now, payload["vehicle_id"]),
            )
        elif action == "update_site_requirement" and payload.get("site_id"):
            existing = self._requirement_for_site(conn, payload["site_id"], payload.get("work_date", note["work_date"]))
            current_skills = existing["required_skills"] if existing else []
            merged_skills = list(dict.fromkeys([*current_skills, *payload.get("add_required_skills", [])]))
            record = {
                "id": existing["id"] if existing else "",
                "site_id": payload["site_id"],
                "work_date": payload.get("work_date", note["work_date"]),
                "required_headcount": existing["required_headcount"] if existing else 2,
                "required_skills": merged_skills,
                "required_certificates": existing["required_certificates"] if existing else [],
                "required_vehicle_type": existing["required_vehicle_type"] if existing else "",
                "required_tools": existing["required_tools"] if existing else [],
                "priority": existing["priority"] if existing else 70,
                "urgency_level": existing["urgency_level"] if existing else 70,
                "task_description": existing["task_description"] if existing else "",
                "notes": f"{existing['notes'] if existing else ''}\n[confirmed note by {actor}] {note['raw_text']}".strip(),
            }
            self._upsert_requirement(conn, record, timestamp=now)

    def _create_observation_from_note(self, conn: sqlite3.Connection, note_id: str) -> dict[str, Any]:
        existing = conn.execute("SELECT * FROM observation_logs WHERE note_id = ?", (note_id,)).fetchone()
        if existing is not None:
            return self._observation_row_to_dict(existing)
        note_row = conn.execute("SELECT * FROM raw_notes WHERE id = ?", (note_id,)).fetchone()
        if note_row is None:
            raise ValueError(f"Unknown note id: {note_id}")
        note = self._note_row_to_dict(note_row)
        observation_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO observation_logs (
                id, note_id, created_at, source_type, source_user, target_type, target_id,
                target_name, event_type, sentiment, tags_json, content, impacts_scheduling,
                action_required, resolved_status, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                note_id,
                note["created_at"],
                note["source_type"],
                note["source_user"],
                note["target_type"] or "memo",
                note["target_id"],
                note["target_name"],
                note["classification_type"],
                note["sentiment"],
                _json_dumps(note["tags"]),
                note["raw_text"],
                1 if note["impacts_scheduling"] else 0,
                1 if note["action_required"] else 0,
                "open",
                note["confidence"],
            ),
        )
        row = conn.execute("SELECT * FROM observation_logs WHERE id = ?", (observation_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create observation.")
        return self._observation_row_to_dict(row)

    def _load_planning_resources(self, conn: sqlite3.Connection, work_date: str) -> dict[str, Any]:
        employees = self._available_employee_rows(conn, work_date)
        vehicles = [
            self._vehicle_row_to_dict(row)
            for row in conn.execute("SELECT * FROM vehicles WHERE current_status = 'available' ORDER BY vehicle_code").fetchall()
        ]
        requirements = [
            self._requirement_row_to_dict(row)
            for row in conn.execute(
                """
                SELECT r.*, s.name AS site_name
                FROM site_daily_requirements r
                JOIN sites s ON s.id = r.site_id
                WHERE r.work_date = ?
                ORDER BY r.priority DESC, r.urgency_level DESC, s.site_code ASC
                """,
                (work_date,),
            ).fetchall()
        ]
        if not requirements:
            for row in conn.execute("SELECT * FROM sites ORDER BY urgency_level DESC, site_code ASC").fetchall():
                site = self._site_row_to_dict(row)
                requirements.append(
                    {
                        "id": f"site-default-{site['id']}-{work_date}",
                        "site_id": site["id"],
                        "site_name": site["name"],
                        "work_date": work_date,
                        "start_time": site["start_time"],
                        "required_headcount": site["required_headcount"],
                        "required_skills": site["required_skills"],
                        "required_certificates": site["required_certificates"],
                        "required_vehicle_type": "",
                        "required_tools": [],
                        "priority": site["urgency_level"],
                        "urgency_level": site["urgency_level"],
                        "task_description": "",
                        "notes": site["notes"],
                    }
                )
        sites = {site["id"]: site for site in self.list_resources("sites")}
        rules = self.list_resources("rules")
        return {
            "employees": employees,
            "vehicles": vehicles,
            "requirements": requirements,
            "sites": sites,
            "rules": rules,
        }

    def _available_employee_rows(self, conn: sqlite3.Connection, work_date: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM employees WHERE availability_status = 'available' ORDER BY can_lead_team DESC, performance_score DESC, employee_code ASC"
        ).fetchall()
        return [self._employee_row_to_dict(row) for row in rows]

    def _build_plan(
        self,
        conn: sqlite3.Connection,
        *,
        work_date: str,
        resources: dict[str, Any],
        created_reason: str,
        created_by: str,
        previous_plan_id: str,
    ) -> dict[str, Any]:
        plan_id = uuid.uuid4().hex
        generated_at = _utc_now_iso()
        used_employees: set[str] = set()
        used_vehicles: set[str] = set()
        assignments: list[dict[str, Any]] = []
        risks: list[str] = []
        gaps: list[str] = []
        pair_scores_cache: dict[tuple[str, str], tuple[bool, float, list[str]]] = {}

        for requirement in resources["requirements"]:
            site = resources["sites"].get(requirement["site_id"])
            if site is None:
                continue
            team_result = self._pick_team_for_requirement(
                resources["employees"],
                requirement,
                site,
                used_employees,
                pair_scores_cache,
            )
            vehicle_result = self._pick_vehicle_for_requirement(
                resources["vehicles"],
                requirement,
                site,
                used_vehicles,
                team_result["team"],
            )
            used_employees.update(item["id"] for item in team_result["team"])
            if vehicle_result is not None:
                used_vehicles.add(vehicle_result["id"])

            assignment_risks = list(team_result["risks"])
            if vehicle_result is None and requirement["required_vehicle_type"]:
                assignment_risks.append(f"{site['name']} 缺少匹配车辆 {requirement['required_vehicle_type']}")
            if assignment_risks:
                risks.extend(assignment_risks)
            if team_result["gap"]:
                gaps.append(f"{site['name']}: {team_result['gap']}")

            assignment = {
                "id": uuid.uuid4().hex,
                "plan_id": plan_id,
                "site_id": site["id"],
                "site_name": site["name"],
                "employee_ids": [item["id"] for item in team_result["team"]],
                "employee_names": [item["name"] for item in team_result["team"]],
                "vehicle": vehicle_result,
                "score": round(team_result["score"] + (vehicle_result["score"] if vehicle_result else 0), 1),
                "status": "draft",
                "explanation": {
                    "pair_score": team_result["pair_score"],
                    "site_score": team_result["site_score"],
                    "vehicle_score": vehicle_result["score"] if vehicle_result else 0,
                    "factors": [*team_result["factors"], *(vehicle_result["factors"] if vehicle_result else ["无车辆加分"])],
                },
                "risk_flags": assignment_risks,
                "created_at": generated_at,
            }
            assignments.append(assignment)

        summary = {
            "assignment_count": len(assignments),
            "risk_count": len(risks),
            "gap_count": len(gaps),
            "risks": risks,
            "gaps": gaps,
        }
        conn.execute(
            """
            INSERT INTO schedule_plans (
                id, work_date, status, created_reason, created_by, previous_plan_id, summary_json, generated_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                work_date,
                "draft",
                created_reason,
                created_by,
                previous_plan_id,
                _json_dumps(summary),
                generated_at,
                "",
            ),
        )
        for assignment in assignments:
            conn.execute(
                """
                INSERT INTO schedule_assignments (
                    id, plan_id, site_id, site_name, employee_ids_json, employee_names_json,
                    vehicle_id, vehicle_label, score, status, explanation_json, risk_flags_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment["id"],
                    plan_id,
                    assignment["site_id"],
                    assignment["site_name"],
                    _json_dumps(assignment["employee_ids"]),
                    _json_dumps(assignment["employee_names"]),
                    assignment["vehicle"]["id"] if assignment["vehicle"] else "",
                    assignment["vehicle"]["vehicle_code"] if assignment["vehicle"] else "",
                    assignment["score"],
                    assignment["status"],
                    _json_dumps(assignment["explanation"]),
                    _json_dumps(assignment["risk_flags"]),
                    assignment["created_at"],
                ),
            )
        return {
            "id": plan_id,
            "work_date": work_date,
            "status": "draft",
            "created_reason": created_reason,
            "created_by": created_by,
            "generated_at": generated_at,
            "summary": summary,
            "assignments": assignments,
        }

    def _pick_team_for_requirement(
        self,
        employees: list[dict[str, Any]],
        requirement: dict[str, Any],
        site: dict[str, Any],
        used_employees: set[str],
        pair_scores_cache: dict[tuple[str, str], tuple[bool, float, list[str]]],
    ) -> dict[str, Any]:
        team_size = max(1, requirement["required_headcount"])
        available = [employee for employee in employees if employee["id"] not in used_employees]
        if not available:
            return {"team": [], "score": 0.0, "pair_score": 0.0, "site_score": 0.0, "factors": ["无可用员工"], "risks": [f"{site['name']} 无可用员工"], "gap": "无人可派"}
        best_team: list[dict[str, Any]] = []
        best_score = -1.0
        best_pair_score = 0.0
        best_site_score = 0.0
        best_factors: list[str] = []
        best_risks: list[str] = []

        if team_size == 1:
            for employee in available:
                valid, site_score, factors, risks = self._team_site_score([employee], site, requirement)
                if not valid:
                    continue
                if site_score > best_score:
                    best_team = [employee]
                    best_score = site_score
                    best_pair_score = 0.0
                    best_site_score = site_score
                    best_factors = factors
                    best_risks = risks
        else:
            for pair in combinations(available, 2):
                key = tuple(sorted([pair[0]["id"], pair[1]["id"]]))
                valid_pair, pair_score, pair_factors = pair_scores_cache.get(key, (False, 0.0, []))
                if key not in pair_scores_cache:
                    valid_pair, pair_score, pair_factors = self._pair_score(pair[0], pair[1])
                    pair_scores_cache[key] = (valid_pair, pair_score, pair_factors)
                if not valid_pair:
                    continue
                team = list(pair)
                remaining = [employee for employee in available if employee["id"] not in {pair[0]["id"], pair[1]["id"]}]
                while len(team) < team_size and remaining:
                    additions = []
                    for candidate in remaining:
                        valid, site_score, factors, risks = self._team_site_score([*team, candidate], site, requirement)
                        if valid:
                            additions.append((site_score, candidate, factors, risks))
                    if not additions:
                        break
                    additions.sort(key=lambda item: item[0], reverse=True)
                    chosen_score, chosen_candidate, _chosen_factors, _chosen_risks = additions[0]
                    team.append(chosen_candidate)
                    remaining = [employee for employee in remaining if employee["id"] != chosen_candidate["id"]]
                valid, site_score, factors, risks = self._team_site_score(team, site, requirement)
                if not valid:
                    continue
                total_score = pair_score + site_score
                if total_score > best_score:
                    best_team = team
                    best_score = total_score
                    best_pair_score = pair_score
                    best_site_score = site_score
                    best_factors = [*pair_factors, *factors]
                    best_risks = risks

        if not best_team:
            risk = self._coverage_gap(available, requirement, site)
            return {
                "team": [],
                "score": 0.0,
                "pair_score": 0.0,
                "site_score": 0.0,
                "factors": ["未找到满足约束的班组"],
                "risks": [risk],
                "gap": risk,
            }
        gap = ""
        if len(best_team) < requirement["required_headcount"]:
            gap = f"人数不足，需要 {requirement['required_headcount']} 人，实际 {len(best_team)} 人"
        return {
            "team": best_team,
            "score": best_score,
            "pair_score": best_pair_score,
            "site_score": best_site_score,
            "factors": best_factors,
            "risks": best_risks,
            "gap": gap,
        }

    def _pick_vehicle_for_requirement(
        self,
        vehicles: list[dict[str, Any]],
        requirement: dict[str, Any],
        site: dict[str, Any],
        used_vehicles: set[str],
        team: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        available = [vehicle for vehicle in vehicles if vehicle["id"] not in used_vehicles]
        if not available:
            return None
        best: dict[str, Any] | None = None
        best_score = -1.0
        for vehicle in available:
            valid, score, factors = self._vehicle_score(vehicle, requirement, site, team)
            if not valid:
                continue
            if score > best_score:
                best = {**vehicle, "score": round(score, 1), "factors": factors}
                best_score = score
        return best

    def _pair_score(self, employee_a: dict[str, Any], employee_b: dict[str, Any]) -> tuple[bool, float, list[str]]:
        if employee_b["name"] in employee_a["avoided_partners"] or employee_a["name"] in employee_b["avoided_partners"]:
            return False, 0.0, ["禁配搭档"]
        factors: list[str] = []
        score = 40.0
        skills_a = {employee_a["primary_skill"], *employee_a["secondary_skills"]}
        skills_b = {employee_b["primary_skill"], *employee_b["secondary_skills"]}
        skill_union = len(skills_a | skills_b)
        skill_overlap = len(skills_a & skills_b)
        score += min(skill_union * 4, 20)
        factors.append(f"技能互补 {skill_union} 项")
        if skill_overlap:
            score += 4
            factors.append(f"共同技能 {skill_overlap} 项")
        cert_union = len(set(employee_a["certificates"]) | set(employee_b["certificates"]))
        score += min(cert_union * 3, 12)
        if cert_union:
            factors.append(f"证照覆盖 {cert_union} 项")
        comm = (employee_a["communication_score"] + employee_b["communication_score"]) / 20
        perf = (employee_a["performance_score"] + employee_b["performance_score"]) / 25
        safety = (employee_a["safety_score"] + employee_b["safety_score"]) / 25
        fatigue_penalty = max(employee_a["fatigue_score"], employee_b["fatigue_score"]) / 12
        score += comm + perf + safety - fatigue_penalty
        factors.append("综合表现与安全评分加成")
        if employee_b["name"] in employee_a["preferred_partners"] or employee_a["name"] in employee_b["preferred_partners"]:
            score += 12
            factors.append("命中偏好搭档")
        if employee_a["can_lead_team"] != employee_b["can_lead_team"]:
            score += 6
            factors.append("带队与执行角色互补")
        if employee_a["home_area"] == employee_b["home_area"] and employee_a["home_area"]:
            score += 5
            factors.append("出发区域一致")
        return True, round(max(0.0, min(score, 100.0)), 1), factors

    def _team_site_score(
        self,
        team: list[dict[str, Any]],
        site: dict[str, Any],
        requirement: dict[str, Any],
    ) -> tuple[bool, float, list[str], list[str]]:
        if not team:
            return False, 0.0, [], ["空班组"]
        if len(team) < min(1, requirement["required_headcount"]):
            return False, 0.0, [], ["人数不足"]
        if requirement["required_headcount"] > len(team):
            return False, 0.0, [], [f"需要 {requirement['required_headcount']} 人，只有 {len(team)} 人"]
        if site["requires_team_lead"] and not any(item["can_lead_team"] for item in team):
            return False, 0.0, [], ["缺少带队人"]
        union_skills = set()
        union_certs = set()
        home_areas = set()
        for item in team:
            union_skills.add(item["primary_skill"])
            union_skills.update(item["secondary_skills"])
            union_certs.update(item["certificates"])
            if item["home_area"]:
                home_areas.add(item["home_area"])
            if item["availability_status"] != "available":
                return False, 0.0, [], [f"{item['name']} 不可用"]
        missing_skills = [skill for skill in requirement["required_skills"] if skill not in union_skills]
        missing_certs = [cert for cert in requirement["required_certificates"] if cert not in union_certs]
        if missing_skills:
            return False, 0.0, [], [f"缺少技能 {', '.join(missing_skills)}"]
        if missing_certs:
            return False, 0.0, [], [f"缺少证照 {', '.join(missing_certs)}"]

        skill_score = 25 + len(requirement["required_skills"]) * 4
        cert_score = 10 + len(requirement["required_certificates"]) * 6
        lead_score = 10 if site["requires_team_lead"] and any(item["can_lead_team"] for item in team) else 4
        commute_score = 8 if any(area and area in site["address"] for area in home_areas) else max(2, 12 - site["distance_from_base"] / 4)
        growth_score = 6 if any(item["learning_score"] >= 75 for item in team) and any(item["can_lead_team"] for item in team) else 2
        fatigue_penalty = sum(item["fatigue_score"] for item in team) / 18
        score = skill_score + cert_score + lead_score + commute_score + growth_score - fatigue_penalty
        factors = [
            f"工种匹配满足 {len(requirement['required_skills'])} 项",
            f"资质覆盖满足 {len(requirement['required_certificates'])} 项",
            "满足带队要求" if site["requires_team_lead"] else "无需带队人",
            "通勤更合理" if commute_score >= 7 else "通勤一般",
        ]
        risks = []
        if site["weather_sensitive"]:
            risks.append(f"{site['name']} 对天气较敏感")
        if site["risk_level"] in {"critical", "high"}:
            risks.append(f"{site['name']} 风险等级 {site['risk_level']}")
        return True, round(max(0.0, min(score, 100.0)), 1), factors, risks

    def _vehicle_score(
        self,
        vehicle: dict[str, Any],
        requirement: dict[str, Any],
        site: dict[str, Any],
        team: list[dict[str, Any]],
    ) -> tuple[bool, float, list[str]]:
        if requirement["required_vehicle_type"] and requirement["required_vehicle_type"] not in {vehicle["vehicle_type"], vehicle["load_type"]}:
            return False, 0.0, [f"车型不匹配 {requirement['required_vehicle_type']}"]
        if team and vehicle["seat_capacity"] < len(team):
            return False, 0.0, ["座位数不足"]
        if vehicle["current_status"] != "available":
            return False, 0.0, ["车辆不可用"]
        score = 25.0
        factors = []
        if requirement["required_vehicle_type"] and requirement["required_vehicle_type"] == vehicle["vehicle_type"]:
            score += 25
            factors.append("车型完全匹配")
        else:
            score += 10
            factors.append("车辆可用")
        if any(member["can_drive"] for member in team):
            score += 15
            factors.append("班组中有人可驾驶")
        if vehicle["preferred_use_case"] and site["name"]:
            score += 5
            factors.append("适配工地用途")
        score += max(0, 10 - abs(vehicle["seat_capacity"] - max(2, len(team))) * 2)
        return True, round(max(0.0, min(score, 100.0)), 1), factors

    def _coverage_gap(self, available: list[dict[str, Any]], requirement: dict[str, Any], site: dict[str, Any]) -> str:
        if not available:
            return f"{site['name']} 无可用员工"
        union_skills = {skill for employee in available for skill in [employee["primary_skill"], *employee["secondary_skills"]]}
        union_certs = {cert for employee in available for cert in employee["certificates"]}
        missing_skills = [skill for skill in requirement["required_skills"] if skill not in union_skills]
        missing_certs = [cert for cert in requirement["required_certificates"] if cert not in union_certs]
        if missing_skills:
            return f"缺少技能 {', '.join(missing_skills)}"
        if missing_certs:
            return f"缺少资质 {', '.join(missing_certs)}"
        if site["requires_team_lead"] and not any(employee["can_lead_team"] for employee in available):
            return "缺少带队人"
        return "可用班组组合不足"

    def _build_brief_payload(self, conn: sqlite3.Connection, plan: dict[str, Any], *, briefing_type: str) -> dict[str, Any]:
        employees = self.list_resources("employees")
        vehicles = self.list_resources("vehicles")
        available_employees = [item for item in employees if item["availability_status"] == "available"]
        available_vehicles = [item for item in vehicles if item["current_status"] == "available"]
        lines = [
            f"{plan['work_date']} {briefing_type} brief",
            f"- 今日可出勤员工：{len(available_employees)} 人",
            f"- 今日工地需求：{len(plan['assignments'])} 个",
            f"- 今日可用车辆：{len(available_vehicles)} 台",
            f"- 风险数量：{len(plan['summary']['risks'])}",
            f"- 缺口数量：{len(plan['summary']['gaps'])}",
        ]
        for assignment in plan["assignments"]:
            lines.append(
                f"- {assignment['site_name']}：{', '.join(assignment['employee_names']) or '待补位'}"
                f"{' / ' + assignment['vehicle']['vehicle_code'] if assignment['vehicle'] else ''}"
            )
        if plan["summary"]["gaps"]:
            lines.append("待处理缺口：")
            lines.extend(f"- {gap}" for gap in plan["summary"]["gaps"][:5])
        text = "\n".join(lines)
        return {
            "type": briefing_type,
            "work_date": plan["work_date"],
            "plan_id": plan["id"],
            "text": text,
            "plan": plan,
        }

    def _build_recap_payload(self, plan: dict[str, Any], observations: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> dict[str, Any]:
        pattern_counter: dict[str, int] = {}
        for item in overrides:
            pattern_counter[item["reason_type"]] = pattern_counter.get(item["reason_type"], 0) + 1
        lines = [
            f"{plan['work_date']} 晚间复盘",
            f"- 原始建议工地数：{len(plan['assignments'])}",
            f"- 手动改排次数：{len(overrides)}",
            f"- 观察记录：{len(observations)}",
        ]
        if overrides:
            lines.append("关键改排：")
            for item in overrides[:5]:
                lines.append(f"- {item['reason_type']}：{item['reason_text']}")
        if observations:
            lines.append("关键现场记录：")
            for item in observations[:5]:
                lines.append(f"- {item['target_name'] or item['target_type']}：{item['content']}")
        if pattern_counter:
            lines.append("候选学习模式：")
            for reason_type, count in sorted(pattern_counter.items(), key=lambda item: item[1], reverse=True)[:3]:
                lines.append(f"- {reason_type}：{count} 次")
        return {
            "type": "evening",
            "work_date": plan["work_date"],
            "plan_id": plan["id"],
            "override_count": len(overrides),
            "observation_count": len(observations),
            "patterns": pattern_counter,
            "text": "\n".join(lines),
        }

    def _latest_plan(self, conn: sqlite3.Connection, work_date: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM schedule_plans WHERE work_date = ? ORDER BY generated_at DESC LIMIT 1",
            (work_date,),
        ).fetchone()
        if row is None:
            return None
        plan = self._plan_row_to_dict(row)
        assignment_rows = conn.execute(
            "SELECT * FROM schedule_assignments WHERE plan_id = ? ORDER BY site_name ASC",
            (plan["id"],),
        ).fetchall()
        plan["assignments"] = [self._assignment_row_to_dict(item) for item in assignment_rows]
        return plan

    def _diff_plans(self, before: dict[str, Any] | None, after: dict[str, Any]) -> dict[str, Any]:
        if before is None:
            return {"changed_sites": [], "summary": "这是第一版方案。"}
        before_map = {item["site_id"]: item for item in before["assignments"]}
        after_map = {item["site_id"]: item for item in after["assignments"]}
        changed = []
        for site_id, assignment in after_map.items():
            previous = before_map.get(site_id)
            if previous is None:
                changed.append(f"{assignment['site_name']} 新增安排")
                continue
            if previous["employee_names"] != assignment["employee_names"] or previous["vehicle"] != assignment["vehicle"]:
                changed.append(
                    f"{assignment['site_name']}：{', '.join(previous['employee_names']) or '无人'} -> "
                    f"{', '.join(assignment['employee_names']) or '无人'}"
                )
        return {
            "changed_sites": changed,
            "summary": "无明显变化" if not changed else "\n".join(f"- {item}" for item in changed),
        }

    def _observations_for_date(self, conn: sqlite3.Connection, work_date: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT o.*
            FROM observation_logs o
            LEFT JOIN raw_notes n ON n.id = o.note_id
            WHERE COALESCE(n.work_date, substr(o.created_at, 1, 10)) = ?
            ORDER BY o.created_at DESC
            """,
            (work_date,),
        ).fetchall()
        return [self._observation_row_to_dict(row) for row in rows]

    def _overrides_for_date(self, conn: sqlite3.Connection, work_date: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT l.*
            FROM schedule_override_logs l
            JOIN schedule_plans p ON p.id = l.plan_id
            WHERE p.work_date = ?
            ORDER BY l.changed_at DESC
            """,
            (work_date,),
        ).fetchall()
        return [self._override_row_to_dict(row) for row in rows]

    def _handle_command(
        self,
        conversation: ConversationRef,
        text: str,
        *,
        source_type: str,
        audio_path: str | None,
    ) -> str:
        parts = text.split(maxsplit=2)
        command = parts[1].lower() if len(parts) > 1 else "help"
        arg = parts[2].strip() if len(parts) > 2 else ""
        if command == "help":
            return self.help_text()
        if command == "overview":
            overview = self.overview()
            return (
                "建筑调度总览：\n"
                f"- 日期：{overview['work_date']}\n"
                f"- 员工：{overview['counts']['employees']}\n"
                f"- 工地：{overview['counts']['sites']}\n"
                f"- 今日需求：{overview['counts']['requirements']}\n"
                f"- 车辆：{overview['counts']['vehicles']}\n"
                f"- 待复核语音/记录：{overview['counts']['pending_notes']}"
            )
        if command == "plan":
            plan = self.generate_plan(work_date=arg or None, created_reason="chat-plan", created_by=conversation.key)
            return self._format_plan_text(plan)
        if command == "brief":
            return self.morning_brief(work_date=arg or None)["text"]
        if command == "recap":
            return self.evening_recap(work_date=arg or None)["text"]
        if command == "replan":
            if not arg:
                return "用法：/construction replan <原因>"
            return self._format_replan_result(self.replan(reason=arg, actor=conversation.key))
        if command == "partners":
            if not arg:
                return "用法：/construction partners <员工名>"
            items = self.recommend_partners(arg)
            if not items:
                return f"没有找到 {arg} 的候选搭档。"
            return "\n".join([f"{arg} 的推荐搭档：", *[f"- {item['employee']}：{item['score']:.1f}" for item in items]])
        if command == "site":
            if not arg:
                return "用法：/construction site <工地名>"
            items = self.recommend_team_for_site(arg)
            if not items:
                return f"没有找到 {arg} 的候选班组。"
            return "\n".join([f"{arg} 的推荐班组：", *[f"- {', '.join(item['team'])}：{item['score']:.1f}" for item in items]])
        if command == "notes":
            notes = self.list_notes(status="pending_review", limit=10)
            if not notes:
                return "当前没有待确认的记录。"
            return "\n".join(
                ["待确认记录："]
                + [
                    f"- {item['id']} | {item['classification_type']} | {item['target_name'] or '未识别对象'} | {item['raw_text']}"
                    for item in notes
                ]
            )
        if command == "confirm":
            if not arg:
                return "用法：/construction confirm <note_id>"
            result = self.confirm_note(arg, actor=conversation.key)
            return f"已确认记录 {result['note']['id']} 并写入业务数据。"
        if command == "note":
            if not arg:
                return "用法：/construction note <内容>"
            return self._format_note_ack(self.capture_note(conversation=conversation, text=arg, source_type=source_type, audio_path=audio_path))
        return self.help_text()

    def _extract_known_name(
        self,
        text: str,
        *,
        resource_kind: str,
        conn: sqlite3.Connection | None = None,
    ) -> str | None:
        if resource_kind not in {"employees", "sites", "vehicles"}:
            return None
        close_conn = False
        if conn is None:
            if not self._enabled:
                return None
            conn = self._connect()
            close_conn = True
        try:
            if resource_kind == "employees":
                rows = conn.execute("SELECT name FROM employees").fetchall()
                names = [str(row["name"]) for row in rows]
            elif resource_kind == "sites":
                rows = conn.execute("SELECT name FROM sites").fetchall()
                names = [str(row["name"]) for row in rows]
            else:
                rows = conn.execute("SELECT vehicle_code, plate_number FROM vehicles").fetchall()
                names = []
                for row in rows:
                    vehicle_code = str(row["vehicle_code"])
                    plate_number = str(row["plate_number"])
                    names.append(vehicle_code)
                    names.append(plate_number)
                    digits = re.search(r"(\d+)$", vehicle_code)
                    if digits:
                        names.append(f"{int(digits.group(1))}号车")
            matches = [name for name in names if name and name in text]
            if not matches:
                return None
            return sorted(matches, key=len, reverse=True)[0]
        finally:
            if close_conn:
                conn.close()

    def _find_employee_by_name(self, conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM employees WHERE name = ?", (name,)).fetchone()

    def _find_site_by_name(self, conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM sites WHERE name = ?", (name,)).fetchone()

    def _find_vehicle_by_code(self, conn: sqlite3.Connection, code: str) -> sqlite3.Row | None:
        alias_match = re.fullmatch(r"(\d+)号车", code.strip())
        aliases = [code]
        if alias_match:
            aliases.append(f"V{int(alias_match.group(1)):02d}")
        return conn.execute(
            "SELECT * FROM vehicles WHERE vehicle_code IN ({}) OR plate_number IN ({})".format(
                ",".join("?" for _ in aliases),
                ",".join("?" for _ in aliases),
            ),
            [*aliases, *aliases],
        ).fetchone()

    def _find_vehicle_by_name(self, conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
        return self._find_vehicle_by_code(conn, name)

    def _requirement_for_site(self, conn: sqlite3.Connection, site_id: str, work_date: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT r.*, s.name AS site_name
            FROM site_daily_requirements r
            JOIN sites s ON s.id = r.site_id
            WHERE r.site_id = ? AND r.work_date = ?
            """,
            (site_id, work_date),
        ).fetchone()
        return self._requirement_row_to_dict(row) if row is not None else None

    def _upsert_employee(self, conn: sqlite3.Connection, record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
        clean = {
            "id": str(record.get("id") or "").strip() or f"emp-{uuid.uuid4().hex[:8]}",
            "employee_code": str(record.get("employee_code") or "").strip() or f"E-{uuid.uuid4().hex[:6]}",
            "name": str(record.get("name") or "").strip(),
            "phone": str(record.get("phone") or "").strip(),
            "role_type": str(record.get("role_type") or record.get("primary_skill") or "普工").strip(),
            "level": str(record.get("level") or "").strip(),
            "primary_skill": str(record.get("primary_skill") or record.get("role_type") or "普工").strip(),
            "secondary_skills": _coerce_list(record.get("secondary_skills")),
            "certificates": _coerce_list(record.get("certificates")),
            "can_drive": _coerce_bool(record.get("can_drive")),
            "can_lead_team": _coerce_bool(record.get("can_lead_team")),
            "can_work_alone": _coerce_bool(record.get("can_work_alone")),
            "home_area": str(record.get("home_area") or "").strip(),
            "availability_status": str(record.get("availability_status") or "available").strip(),
            "max_daily_hours": _coerce_float(record.get("max_daily_hours"), default=8),
            "fatigue_score": _coerce_float(record.get("fatigue_score"), default=0),
            "performance_score": _coerce_float(record.get("performance_score"), default=50),
            "safety_score": _coerce_float(record.get("safety_score"), default=50),
            "communication_score": _coerce_float(record.get("communication_score"), default=50),
            "learning_score": _coerce_float(record.get("learning_score"), default=50),
            "preferred_partners": _coerce_list(record.get("preferred_partners")),
            "avoided_partners": _coerce_list(record.get("avoided_partners")),
            "notes": str(record.get("notes") or "").strip(),
        }
        if not clean["name"]:
            raise ValueError("Employee name is required.")
        existing = conn.execute("SELECT created_at FROM employees WHERE id = ? OR name = ?", (clean["id"], clean["name"])).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else timestamp
        conn.execute(
            """
            INSERT INTO employees (
                id, employee_code, name, phone, role_type, level, primary_skill, secondary_skills_json, certificates_json,
                can_drive, can_lead_team, can_work_alone, home_area, availability_status, max_daily_hours,
                fatigue_score, performance_score, safety_score, communication_score, learning_score,
                preferred_partners_json, avoided_partners_json, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                employee_code=excluded.employee_code,
                name=excluded.name,
                phone=excluded.phone,
                role_type=excluded.role_type,
                level=excluded.level,
                primary_skill=excluded.primary_skill,
                secondary_skills_json=excluded.secondary_skills_json,
                certificates_json=excluded.certificates_json,
                can_drive=excluded.can_drive,
                can_lead_team=excluded.can_lead_team,
                can_work_alone=excluded.can_work_alone,
                home_area=excluded.home_area,
                availability_status=excluded.availability_status,
                max_daily_hours=excluded.max_daily_hours,
                fatigue_score=excluded.fatigue_score,
                performance_score=excluded.performance_score,
                safety_score=excluded.safety_score,
                communication_score=excluded.communication_score,
                learning_score=excluded.learning_score,
                preferred_partners_json=excluded.preferred_partners_json,
                avoided_partners_json=excluded.avoided_partners_json,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                clean["id"],
                clean["employee_code"],
                clean["name"],
                clean["phone"],
                clean["role_type"],
                clean["level"],
                clean["primary_skill"],
                _json_dumps(clean["secondary_skills"]),
                _json_dumps(clean["certificates"]),
                1 if clean["can_drive"] else 0,
                1 if clean["can_lead_team"] else 0,
                1 if clean["can_work_alone"] else 0,
                clean["home_area"],
                clean["availability_status"],
                clean["max_daily_hours"],
                clean["fatigue_score"],
                clean["performance_score"],
                clean["safety_score"],
                clean["communication_score"],
                clean["learning_score"],
                _json_dumps(clean["preferred_partners"]),
                _json_dumps(clean["avoided_partners"]),
                clean["notes"],
                created_at,
                timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM employees WHERE id = ?", (clean["id"],)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist employee.")
        return self._employee_row_to_dict(row)

    def _upsert_site(self, conn: sqlite3.Connection, record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
        clean = {
            "id": str(record.get("id") or "").strip() or f"site-{uuid.uuid4().hex[:8]}",
            "site_code": str(record.get("site_code") or "").strip() or f"S-{uuid.uuid4().hex[:6]}",
            "name": str(record.get("name") or "").strip(),
            "address": str(record.get("address") or "").strip(),
            "gps_location": str(record.get("gps_location") or "").strip(),
            "distance_from_base": _coerce_float(record.get("distance_from_base"), default=0),
            "start_time": str(record.get("start_time") or "08:00").strip(),
            "required_headcount": max(1, _coerce_int(record.get("required_headcount"), default=2)),
            "required_skills": _coerce_list(record.get("required_skills")),
            "required_certificates": _coerce_list(record.get("required_certificates")),
            "risk_level": str(record.get("risk_level") or "medium").strip(),
            "requires_team_lead": _coerce_bool(record.get("requires_team_lead")),
            "equipment_needs": _coerce_list(record.get("equipment_needs")),
            "material_needs": _coerce_list(record.get("material_needs")),
            "urgency_level": _priority_value(record.get("urgency_level")),
            "customer_priority": _priority_value(record.get("customer_priority")),
            "weather_sensitive": _coerce_bool(record.get("weather_sensitive")),
            "notes": str(record.get("notes") or "").strip(),
        }
        if not clean["name"]:
            raise ValueError("Site name is required.")
        existing = conn.execute("SELECT created_at FROM sites WHERE id = ? OR name = ?", (clean["id"], clean["name"])).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else timestamp
        conn.execute(
            """
            INSERT INTO sites (
                id, site_code, name, address, gps_location, distance_from_base, start_time, required_headcount,
                required_skills_json, required_certificates_json, risk_level, requires_team_lead, equipment_needs_json,
                material_needs_json, urgency_level, customer_priority, weather_sensitive, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                site_code=excluded.site_code,
                name=excluded.name,
                address=excluded.address,
                gps_location=excluded.gps_location,
                distance_from_base=excluded.distance_from_base,
                start_time=excluded.start_time,
                required_headcount=excluded.required_headcount,
                required_skills_json=excluded.required_skills_json,
                required_certificates_json=excluded.required_certificates_json,
                risk_level=excluded.risk_level,
                requires_team_lead=excluded.requires_team_lead,
                equipment_needs_json=excluded.equipment_needs_json,
                material_needs_json=excluded.material_needs_json,
                urgency_level=excluded.urgency_level,
                customer_priority=excluded.customer_priority,
                weather_sensitive=excluded.weather_sensitive,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                clean["id"],
                clean["site_code"],
                clean["name"],
                clean["address"],
                clean["gps_location"],
                clean["distance_from_base"],
                clean["start_time"],
                clean["required_headcount"],
                _json_dumps(clean["required_skills"]),
                _json_dumps(clean["required_certificates"]),
                clean["risk_level"],
                1 if clean["requires_team_lead"] else 0,
                _json_dumps(clean["equipment_needs"]),
                _json_dumps(clean["material_needs"]),
                clean["urgency_level"],
                clean["customer_priority"],
                1 if clean["weather_sensitive"] else 0,
                clean["notes"],
                created_at,
                timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM sites WHERE id = ?", (clean["id"],)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist site.")
        return self._site_row_to_dict(row)

    def _upsert_requirement(self, conn: sqlite3.Connection, record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
        site_id = str(record.get("site_id") or "").strip()
        if not site_id and record.get("site_name"):
            site = self._find_site_by_name(conn, str(record["site_name"]))
            site_id = str(site["id"]) if site is not None else ""
        if not site_id:
            raise ValueError("Requirement site_id or site_name is required.")
        clean = {
            "id": str(record.get("id") or "").strip() or f"req-{uuid.uuid4().hex[:8]}",
            "site_id": site_id,
            "work_date": str(record.get("work_date") or _today_iso()).strip(),
            "start_time": str(record.get("start_time") or "08:00").strip(),
            "required_headcount": max(1, _coerce_int(record.get("required_headcount"), default=2)),
            "required_skills": _coerce_list(record.get("required_skills")),
            "required_certificates": _coerce_list(record.get("required_certificates")),
            "required_vehicle_type": str(record.get("required_vehicle_type") or "").strip(),
            "required_tools": _coerce_list(record.get("required_tools")),
            "priority": _priority_value(record.get("priority")),
            "urgency_level": _priority_value(record.get("urgency_level")),
            "task_description": str(record.get("task_description") or "").strip(),
            "notes": str(record.get("notes") or "").strip(),
        }
        existing = conn.execute(
            "SELECT created_at FROM site_daily_requirements WHERE site_id = ? AND work_date = ?",
            (clean["site_id"], clean["work_date"]),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else timestamp
        conn.execute(
            """
            INSERT INTO site_daily_requirements (
                id, site_id, work_date, start_time, required_headcount, required_skills_json,
                required_certificates_json, required_vehicle_type, required_tools_json, priority,
                urgency_level, task_description, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_id, work_date) DO UPDATE SET
                start_time=excluded.start_time,
                required_headcount=excluded.required_headcount,
                required_skills_json=excluded.required_skills_json,
                required_certificates_json=excluded.required_certificates_json,
                required_vehicle_type=excluded.required_vehicle_type,
                required_tools_json=excluded.required_tools_json,
                priority=excluded.priority,
                urgency_level=excluded.urgency_level,
                task_description=excluded.task_description,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                clean["id"],
                clean["site_id"],
                clean["work_date"],
                clean["start_time"],
                clean["required_headcount"],
                _json_dumps(clean["required_skills"]),
                _json_dumps(clean["required_certificates"]),
                clean["required_vehicle_type"],
                _json_dumps(clean["required_tools"]),
                clean["priority"],
                clean["urgency_level"],
                clean["task_description"],
                clean["notes"],
                created_at,
                timestamp,
            ),
        )
        row = conn.execute(
            """
            SELECT r.*, s.name AS site_name
            FROM site_daily_requirements r
            JOIN sites s ON s.id = r.site_id
            WHERE r.site_id = ? AND r.work_date = ?
            """,
            (clean["site_id"], clean["work_date"]),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist requirement.")
        return self._requirement_row_to_dict(row)

    def _upsert_vehicle(self, conn: sqlite3.Connection, record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
        clean = {
            "id": str(record.get("id") or "").strip() or f"veh-{uuid.uuid4().hex[:8]}",
            "vehicle_code": str(record.get("vehicle_code") or "").strip() or f"V-{uuid.uuid4().hex[:6]}",
            "plate_number": str(record.get("plate_number") or "").strip() or f"PLATE-{uuid.uuid4().hex[:6]}",
            "vehicle_type": str(record.get("vehicle_type") or "").strip(),
            "seat_capacity": max(1, _coerce_int(record.get("seat_capacity"), default=2)),
            "load_type": str(record.get("load_type") or "").strip(),
            "current_status": str(record.get("current_status") or "available").strip(),
            "maintenance_status": str(record.get("maintenance_status") or "ok").strip(),
            "preferred_use_case": str(record.get("preferred_use_case") or "").strip(),
            "assigned_driver_constraints": _coerce_list(record.get("assigned_driver_constraints")),
            "current_location": str(record.get("current_location") or "").strip(),
            "notes": str(record.get("notes") or "").strip(),
        }
        existing = conn.execute("SELECT created_at FROM vehicles WHERE id = ? OR vehicle_code = ?", (clean["id"], clean["vehicle_code"])).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else timestamp
        conn.execute(
            """
            INSERT INTO vehicles (
                id, vehicle_code, plate_number, vehicle_type, seat_capacity, load_type, current_status,
                maintenance_status, preferred_use_case, assigned_driver_constraints_json, current_location,
                notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                vehicle_code=excluded.vehicle_code,
                plate_number=excluded.plate_number,
                vehicle_type=excluded.vehicle_type,
                seat_capacity=excluded.seat_capacity,
                load_type=excluded.load_type,
                current_status=excluded.current_status,
                maintenance_status=excluded.maintenance_status,
                preferred_use_case=excluded.preferred_use_case,
                assigned_driver_constraints_json=excluded.assigned_driver_constraints_json,
                current_location=excluded.current_location,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                clean["id"],
                clean["vehicle_code"],
                clean["plate_number"],
                clean["vehicle_type"],
                clean["seat_capacity"],
                clean["load_type"],
                clean["current_status"],
                clean["maintenance_status"],
                clean["preferred_use_case"],
                _json_dumps(clean["assigned_driver_constraints"]),
                clean["current_location"],
                clean["notes"],
                created_at,
                timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (clean["id"],)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist vehicle.")
        return self._vehicle_row_to_dict(row)

    def _upsert_rule(self, conn: sqlite3.Connection, record: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
        clean = {
            "id": str(record.get("id") or "").strip() or f"rule-{uuid.uuid4().hex[:8]}",
            "rule_name": str(record.get("rule_name") or "").strip(),
            "rule_type": str(record.get("rule_type") or "custom").strip(),
            "rule_description": str(record.get("rule_description") or "").strip(),
            "rule_priority": _priority_value(record.get("rule_priority")),
            "active_status": _coerce_bool(record.get("active_status"), default=True),
            "condition": record.get("condition") if isinstance(record.get("condition"), dict) else record.get("condition_json") or {},
            "action": record.get("action") if isinstance(record.get("action"), dict) else record.get("action_json") or {},
            "created_by": str(record.get("created_by") or "system").strip(),
            "updated_by": str(record.get("updated_by") or record.get("created_by") or "system").strip(),
        }
        if not clean["rule_name"]:
            raise ValueError("Rule name is required.")
        existing = conn.execute("SELECT created_at FROM rule_configs WHERE id = ? OR rule_name = ?", (clean["id"], clean["rule_name"])).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else timestamp
        conn.execute(
            """
            INSERT INTO rule_configs (
                id, rule_name, rule_type, rule_description, rule_priority, active_status,
                condition_json, action_json, created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                rule_name=excluded.rule_name,
                rule_type=excluded.rule_type,
                rule_description=excluded.rule_description,
                rule_priority=excluded.rule_priority,
                active_status=excluded.active_status,
                condition_json=excluded.condition_json,
                action_json=excluded.action_json,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            (
                clean["id"],
                clean["rule_name"],
                clean["rule_type"],
                clean["rule_description"],
                clean["rule_priority"],
                1 if clean["active_status"] else 0,
                _json_dumps(clean["condition"]),
                _json_dumps(clean["action"]),
                clean["created_by"],
                clean["updated_by"],
                created_at,
                timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM rule_configs WHERE id = ?", (clean["id"],)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist rule.")
        return self._rule_row_to_dict(row)

    def _employee_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "employee_code": row["employee_code"],
            "name": row["name"],
            "phone": row["phone"],
            "role_type": row["role_type"],
            "level": row["level"],
            "primary_skill": row["primary_skill"],
            "secondary_skills": _json_loads(row["secondary_skills_json"], []),
            "certificates": _json_loads(row["certificates_json"], []),
            "can_drive": bool(row["can_drive"]),
            "can_lead_team": bool(row["can_lead_team"]),
            "can_work_alone": bool(row["can_work_alone"]),
            "home_area": row["home_area"],
            "availability_status": row["availability_status"],
            "max_daily_hours": row["max_daily_hours"],
            "fatigue_score": row["fatigue_score"],
            "performance_score": row["performance_score"],
            "safety_score": row["safety_score"],
            "communication_score": row["communication_score"],
            "learning_score": row["learning_score"],
            "preferred_partners": _json_loads(row["preferred_partners_json"], []),
            "avoided_partners": _json_loads(row["avoided_partners_json"], []),
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _site_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "site_code": row["site_code"],
            "name": row["name"],
            "address": row["address"],
            "gps_location": row["gps_location"],
            "distance_from_base": row["distance_from_base"],
            "start_time": row["start_time"],
            "required_headcount": row["required_headcount"],
            "required_skills": _json_loads(row["required_skills_json"], []),
            "required_certificates": _json_loads(row["required_certificates_json"], []),
            "risk_level": row["risk_level"],
            "requires_team_lead": bool(row["requires_team_lead"]),
            "equipment_needs": _json_loads(row["equipment_needs_json"], []),
            "material_needs": _json_loads(row["material_needs_json"], []),
            "urgency_level": row["urgency_level"],
            "customer_priority": row["customer_priority"],
            "weather_sensitive": bool(row["weather_sensitive"]),
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _requirement_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "site_name": row["site_name"],
            "work_date": row["work_date"],
            "start_time": row["start_time"],
            "required_headcount": row["required_headcount"],
            "required_skills": _json_loads(row["required_skills_json"], []),
            "required_certificates": _json_loads(row["required_certificates_json"], []),
            "required_vehicle_type": row["required_vehicle_type"],
            "required_tools": _json_loads(row["required_tools_json"], []),
            "priority": row["priority"],
            "urgency_level": row["urgency_level"],
            "task_description": row["task_description"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _vehicle_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "vehicle_code": row["vehicle_code"],
            "plate_number": row["plate_number"],
            "vehicle_type": row["vehicle_type"],
            "seat_capacity": row["seat_capacity"],
            "load_type": row["load_type"],
            "current_status": row["current_status"],
            "maintenance_status": row["maintenance_status"],
            "preferred_use_case": row["preferred_use_case"],
            "assigned_driver_constraints": _json_loads(row["assigned_driver_constraints_json"], []),
            "current_location": row["current_location"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _rule_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "rule_name": row["rule_name"],
            "rule_type": row["rule_type"],
            "rule_description": row["rule_description"],
            "rule_priority": row["rule_priority"],
            "active_status": bool(row["active_status"]),
            "condition": _json_loads(row["condition_json"], {}),
            "action": _json_loads(row["action_json"], {}),
            "created_by": row["created_by"],
            "updated_by": row["updated_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _plan_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "work_date": row["work_date"],
            "status": row["status"],
            "created_reason": row["created_reason"],
            "created_by": row["created_by"],
            "previous_plan_id": row["previous_plan_id"],
            "summary": _json_loads(row["summary_json"], {}),
            "generated_at": row["generated_at"],
            "confirmed_by": row["confirmed_by"],
            "confirmed_at": row["confirmed_at"],
            "notes": row["notes"],
        }

    def _assignment_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        vehicle = None
        if row["vehicle_id"]:
            vehicle = {
                "id": row["vehicle_id"],
                "vehicle_code": row["vehicle_label"],
            }
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "site_id": row["site_id"],
            "site_name": row["site_name"],
            "employee_ids": _json_loads(row["employee_ids_json"], []),
            "employee_names": _json_loads(row["employee_names_json"], []),
            "vehicle": vehicle,
            "score": row["score"],
            "status": row["status"],
            "explanation": _json_loads(row["explanation_json"], {}),
            "risk_flags": _json_loads(row["risk_flags_json"], []),
            "created_at": row["created_at"],
        }

    def _note_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "source_channel": row["source_channel"],
            "source_conversation_key": row["source_conversation_key"],
            "source_user": row["source_user"],
            "work_date": row["work_date"],
            "raw_text": row["raw_text"],
            "audio_path": row["audio_path"],
            "classification_type": row["classification_type"],
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "target_name": row["target_name"],
            "sentiment": row["sentiment"],
            "tags": _json_loads(row["tags_json"], []),
            "parsed_payload": _json_loads(row["parsed_payload_json"], {}),
            "impacts_scheduling": bool(row["impacts_scheduling"]),
            "action_required": bool(row["action_required"]),
            "confidence": row["confidence"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _observation_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "note_id": row["note_id"],
            "created_at": row["created_at"],
            "source_type": row["source_type"],
            "source_user": row["source_user"],
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "target_name": row["target_name"],
            "event_type": row["event_type"],
            "sentiment": row["sentiment"],
            "tags": _json_loads(row["tags_json"], []),
            "content": row["content"],
            "impacts_scheduling": bool(row["impacts_scheduling"]),
            "action_required": bool(row["action_required"]),
            "resolved_status": row["resolved_status"],
            "confidence": row["confidence"],
        }

    def _override_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "assignment_id": row["assignment_id"],
            "site_id": row["site_id"],
            "original_assignment": _json_loads(row["original_assignment_json"], {}),
            "new_assignment": _json_loads(row["new_assignment_json"], {}),
            "changed_by": row["changed_by"],
            "changed_at": row["changed_at"],
            "reason_type": row["reason_type"],
            "reason_text": row["reason_text"],
            "should_learn": bool(row["should_learn"]),
            "learned_status": row["learned_status"],
        }

    def _format_plan_text(self, plan: dict[str, Any]) -> str:
        lines = [f"{plan['work_date']} 排班建议："]
        for assignment in plan["assignments"]:
            lines.append(
                f"- {assignment['site_name']}：{', '.join(assignment['employee_names']) or '待补位'}"
                f"{' / ' + assignment['vehicle']['vehicle_code'] if assignment['vehicle'] else ''}"
                f" / {assignment['score']:.1f} 分"
            )
        if plan["summary"]["gaps"]:
            lines.append("缺口：")
            lines.extend(f"- {item}" for item in plan["summary"]["gaps"])
        if plan["summary"]["risks"]:
            lines.append("风险：")
            lines.extend(f"- {item}" for item in plan["summary"]["risks"][:6])
        return "\n".join(lines)

    def _format_note_ack(self, note: dict[str, Any]) -> str:
        lines = [
            f"已记录：{note['classification_type']}",
            f"- 对象：{note['target_name'] or '未识别对象'}",
            f"- 置信度：{note['confidence']:.2f}",
            f"- 调度影响：{'是' if note['impacts_scheduling'] else '否'}",
            f"- 状态：{note['status']}",
        ]
        if note["status"] == "pending_review":
            lines.append(f"- 请用 /construction confirm {note['id']} 确认后生效")
        return "\n".join(lines)

    def _format_replan_result(self, result: dict[str, Any]) -> str:
        plan = result["plan"]
        lines = [f"已根据异常重新计算 {plan['work_date']} 排班。", self._format_plan_text(plan)]
        diff = result["diff"]["changed_sites"]
        if diff:
            lines.append("与上一版差异：")
            lines.extend(f"- {item}" for item in diff)
        return "\n".join(lines)

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise RuntimeError("Construction agent is not enabled for this bot.")
