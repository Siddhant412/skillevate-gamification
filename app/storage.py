import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .gamification import BASE_XP, NEXT_LEVEL_XP, achievements, compute_level
from .models import GapInput, ProgressResponse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_id_for(user_id: str, resume_id: str, analysis_id: str) -> str:
    raw = f"{user_id}|{resume_id}|{analysis_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Store:
    def __init__(self, sqlite_path: str):
        self.sqlite_path = sqlite_path
        db_parent = Path(sqlite_path).expanduser().resolve().parent
        db_parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS paths (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    resume_id TEXT NOT NULL,
                    resume_label TEXT NOT NULL,
                    analysis_id TEXT NOT NULL,
                    match_percent INTEGER NOT NULL,
                    gaps_json TEXT NOT NULL,
                    recommendation_request_json TEXT,
                    job_description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, resume_id, analysis_id)
                );

                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_detail TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target_skill TEXT NOT NULL,
                    relevance_score REAL NOT NULL,
                    xp INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY(path_id) REFERENCES paths(id) ON DELETE CASCADE,
                    UNIQUE(path_id, course_id)
                );

                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    xp INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    resume_label TEXT NOT NULL,
                    FOREIGN KEY(path_id) REFERENCES paths(id) ON DELETE CASCADE
                );
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(paths)").fetchall()}
            if "recommendation_request_json" not in columns:
                conn.execute("ALTER TABLE paths ADD COLUMN recommendation_request_json TEXT")

    def upsert_path(
        self,
        user_id: str,
        resume_id: str,
        resume_label: str,
        analysis_id: str,
        match_percent: int,
        gaps: List[GapInput],
        job_description: str,
        courses: List[Dict[str, object]],
        recommendation_request: Optional[Dict[str, object]] = None,
    ) -> str:
        pid = path_id_for(user_id, resume_id, analysis_id)
        now = utc_now()
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM paths WHERE id = ?", (pid,)).fetchone()
            conn.execute(
                """
                INSERT INTO paths (
                    id, user_id, resume_id, resume_label, analysis_id, match_percent,
                    gaps_json, recommendation_request_json, job_description, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    resume_label = excluded.resume_label,
                    match_percent = excluded.match_percent,
                    gaps_json = excluded.gaps_json,
                    recommendation_request_json = excluded.recommendation_request_json,
                    job_description = excluded.job_description,
                    updated_at = excluded.updated_at
                """,
                (
                    pid,
                    user_id,
                    resume_id,
                    resume_label,
                    analysis_id,
                    match_percent,
                    json.dumps([gap.model_dump() for gap in gaps]),
                    json.dumps(recommendation_request) if recommendation_request else None,
                    job_description or "",
                    now,
                    now,
                ),
            )

            if not existing:
                for index, course in enumerate(courses):
                    conn.execute(
                        """
                        INSERT INTO courses (
                            path_id, course_id, title, url, provider, provider_detail, description,
                            target_skill, relevance_score, xp, position, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pid,
                            course["course_id"],
                            course["title"],
                            course["url"],
                            course["provider"],
                            course["provider_detail"],
                            course["description"],
                            course["target_skill"],
                            course["relevance_score"],
                            course["xp"],
                            index,
                            "current" if index == 0 else "locked",
                        ),
                    )
            return pid

    def refresh_courses(self, user_id: str, resume_id: str, analysis_id: str, courses: List[Dict[str, object]]) -> str:
        pid = path_id_for(user_id, resume_id, analysis_id)
        with self.connect() as conn:
            path = conn.execute("SELECT id FROM paths WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not path:
                raise KeyError("Path not found")
            completed = {
                row["course_id"]: row["completed_at"]
                for row in conn.execute("SELECT course_id, completed_at FROM courses WHERE path_id = ? AND status = 'complete'", (pid,))
            }
            conn.execute("DELETE FROM courses WHERE path_id = ?", (pid,))
            first_open_assigned = False
            for index, course in enumerate(courses):
                course_id = str(course["course_id"])
                completed_at = completed.get(course_id)
                if completed_at:
                    status = "complete"
                elif not first_open_assigned:
                    status = "current"
                    first_open_assigned = True
                else:
                    status = "locked"
                conn.execute(
                    """
                    INSERT INTO courses (
                        path_id, course_id, title, url, provider, provider_detail, description,
                        target_skill, relevance_score, xp, position, status, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        course_id,
                        course["title"],
                        course["url"],
                        course["provider"],
                        course["provider_detail"],
                        course["description"],
                        course["target_skill"],
                        course["relevance_score"],
                        course["xp"],
                        index,
                        status,
                        completed_at,
                    ),
                )
            conn.execute("UPDATE paths SET updated_at = ? WHERE id = ?", (utc_now(), pid))
        return pid

    def path_gaps(self, user_id: str, resume_id: str, analysis_id: str) -> List[GapInput]:
        pid = path_id_for(user_id, resume_id, analysis_id)
        with self.connect() as conn:
            path = conn.execute("SELECT gaps_json FROM paths WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not path:
                raise KeyError("Path not found")
            raw_gaps = json.loads(path["gaps_json"] or "[]")
            return [GapInput(**gap) for gap in raw_gaps]

    def path_recommendation_context(
        self,
        user_id: str,
        resume_id: str,
        analysis_id: str,
    ) -> tuple[List[GapInput], Optional[Dict[str, object]]]:
        pid = path_id_for(user_id, resume_id, analysis_id)
        with self.connect() as conn:
            path = conn.execute(
                "SELECT gaps_json, recommendation_request_json FROM paths WHERE id = ? AND user_id = ?",
                (pid, user_id),
            ).fetchone()
            if not path:
                raise KeyError("Path not found")
            raw_gaps = json.loads(path["gaps_json"] or "[]")
            raw_request = path["recommendation_request_json"]
            recommendation_request = json.loads(raw_request) if raw_request else None
            return [GapInput(**gap) for gap in raw_gaps], recommendation_request

    def complete_course(self, user_id: str, resume_id: str, analysis_id: str, course_id: str) -> ProgressResponse:
        pid = path_id_for(user_id, resume_id, analysis_id)
        now = utc_now()
        with self.connect() as conn:
            path = conn.execute("SELECT * FROM paths WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not path:
                raise KeyError("Path not found")
            course = conn.execute(
                "SELECT * FROM courses WHERE path_id = ? AND course_id = ?",
                (pid, course_id),
            ).fetchone()
            if not course:
                raise KeyError("Course not found")
            if course["status"] == "locked":
                raise PermissionError("Course is locked")
            if course["status"] != "complete":
                conn.execute(
                    "UPDATE courses SET status = 'complete', completed_at = ? WHERE id = ?",
                    (now, course["id"]),
                )
                conn.execute(
                    """
                    INSERT INTO activities (path_id, course_id, title, xp, completed_at, resume_label)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (pid, course["course_id"], course["title"], course["xp"], now, path["resume_label"]),
                )
                next_course = conn.execute(
                    """
                    SELECT id FROM courses
                    WHERE path_id = ? AND status = 'locked'
                    ORDER BY position ASC
                    LIMIT 1
                    """,
                    (pid,),
                ).fetchone()
                if next_course:
                    conn.execute("UPDATE courses SET status = 'current' WHERE id = ?", (next_course["id"],))
        return self.progress(user_id, resume_id, analysis_id)

    def progress(self, user_id: str, resume_id: str, analysis_id: str) -> ProgressResponse:
        pid = path_id_for(user_id, resume_id, analysis_id)
        with self.connect() as conn:
            path = conn.execute("SELECT * FROM paths WHERE id = ? AND user_id = ?", (pid, user_id)).fetchone()
            if not path:
                raise KeyError("Path not found")
            course_rows = conn.execute(
                "SELECT * FROM courses WHERE path_id = ? ORDER BY position ASC",
                (pid,),
            ).fetchall()
            activity_rows = conn.execute(
                "SELECT * FROM activities WHERE path_id = ? ORDER BY completed_at DESC LIMIT 10",
                (pid,),
            ).fetchall()

        earned_xp = sum(int(row["xp"]) for row in course_rows if row["status"] == "complete")
        total_xp = BASE_XP + earned_xp
        completed_count = sum(1 for row in course_rows if row["status"] == "complete")
        match_percent = int(path["match_percent"])

        return ProgressResponse(
            userId=user_id,
            resumeId=resume_id,
            resumeLabel=str(path["resume_label"]),
            analysisId=analysis_id,
            matchPercent=match_percent,
            earnedXp=earned_xp,
            baseXp=BASE_XP,
            totalXp=total_xp,
            level=compute_level(total_xp),
            nextLevelXp=NEXT_LEVEL_XP,
            courses=[
                {
                    "courseId": row["course_id"],
                    "title": row["title"],
                    "url": row["url"],
                    "provider": row["provider"],
                    "providerDetail": row["provider_detail"],
                    "description": row["description"],
                    "targetSkill": row["target_skill"],
                    "relevanceScore": float(row["relevance_score"]),
                    "xp": int(row["xp"]),
                    "position": int(row["position"]),
                    "status": row["status"],
                    "completedAt": row["completed_at"],
                }
                for row in course_rows
            ],
            achievements=achievements(completed_count, total_xp, match_percent),
            recentActivity=[
                {
                    "courseId": row["course_id"],
                    "title": row["title"],
                    "xp": int(row["xp"]),
                    "completedAt": row["completed_at"],
                    "resumeLabel": row["resume_label"],
                }
                for row in activity_rows
            ],
        )
