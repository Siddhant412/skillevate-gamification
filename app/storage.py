import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

from .gamification import BASE_XP, NEXT_LEVEL_XP, achievements, compute_level
from .models import GapInput, ProgressResponse


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_id_for(user_id: str, resume_id: str, analysis_id: str) -> str:
    raw = f"{user_id}|{resume_id}|{analysis_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_course_doc(
    course: Dict[str, object],
    position: int,
    status: str,
    completed_at: Optional[str] = None,
) -> Dict:
    return {
        "course_id": str(course["course_id"]),
        "title": str(course["title"]),
        "url": str(course["url"]),
        "provider": str(course["provider"]),
        "provider_detail": str(course["provider_detail"]),
        "description": str(course["description"]),
        "target_skill": str(course["target_skill"]),
        "relevance_score": float(course["relevance_score"]),
        "xp": int(course["xp"]),
        "position": position,
        "status": status,
        "completed_at": completed_at,
    }


class Store:
    def __init__(self, mongodb_uri: str, mongodb_database: str, _client=None) -> None:
        if _client is not None:
            self._client = _client
        else:
            if not mongodb_uri:
                raise RuntimeError("MONGODB_URI is not configured")
            self._client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command("ping")
        self._paths: Collection = self._client[mongodb_database]["gamification_paths"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._paths.create_index(
            [("user_id", ASCENDING), ("resume_id", ASCENDING), ("analysis_id", ASCENDING)],
            unique=True,
            name="user_resume_analysis_unique",
        )
        self._paths.create_index(
            [("user_id", ASCENDING), ("updated_at", ASCENDING)],
            name="user_updated_at",
        )

    def close(self) -> None:
        self._client.close()

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
    ) -> str:
        pid = path_id_for(user_id, resume_id, analysis_id)
        now = utc_now()

        existing = self._paths.find_one({"_id": pid}, {"courses": 1})
        existing_course_count = len(existing.get("courses", [])) if existing else 0

        update: Dict = {
            "$set": {
                "user_id": user_id,
                "resume_id": resume_id,
                "resume_label": resume_label,
                "analysis_id": analysis_id,
                "match_percent": match_percent,
                "gaps": [gap.model_dump() for gap in gaps],
                "job_description": job_description or "",
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "activities": [],
            },
        }

        if not existing or existing_course_count == 0:
            update["$set"]["courses"] = [
                _build_course_doc(course, index, "current" if index == 0 else "locked")
                for index, course in enumerate(courses)
            ]

        self._paths.update_one({"_id": pid}, update, upsert=True)
        return pid

    def refresh_courses(
        self, user_id: str, resume_id: str, analysis_id: str, courses: List[Dict[str, object]]
    ) -> str:
        pid = path_id_for(user_id, resume_id, analysis_id)
        doc = self._paths.find_one({"_id": pid, "user_id": user_id}, {"courses": 1})
        if not doc:
            raise KeyError("Path not found")

        completed: Dict[str, str] = {
            c["course_id"]: c["completed_at"]
            for c in doc.get("courses", [])
            if c.get("status") == "complete"
        }

        first_open_assigned = False
        course_docs = []
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
            course_docs.append(_build_course_doc(course, index, status, completed_at))

        self._paths.update_one(
            {"_id": pid},
            {"$set": {"courses": course_docs, "updated_at": utc_now()}},
        )
        return pid

    def path_gaps(self, user_id: str, resume_id: str, analysis_id: str) -> List[GapInput]:
        pid = path_id_for(user_id, resume_id, analysis_id)
        doc = self._paths.find_one({"_id": pid, "user_id": user_id}, {"gaps": 1})
        if not doc:
            raise KeyError("Path not found")
        return [GapInput(**gap) for gap in doc.get("gaps", [])]

    def path_recommendation_context(
        self,
        user_id: str,
        resume_id: str,
        analysis_id: str,
    ) -> Tuple[List[GapInput], Optional[Dict[str, object]]]:
        pid = path_id_for(user_id, resume_id, analysis_id)
        doc = self._paths.find_one(
            {"_id": pid, "user_id": user_id},
            {"gaps": 1, "recommendation_request": 1},
        )
        if not doc:
            raise KeyError("Path not found")
        gaps = [GapInput(**gap) for gap in doc.get("gaps", [])]
        return gaps, doc.get("recommendation_request")

    def complete_course(
        self, user_id: str, resume_id: str, analysis_id: str, course_id: str
    ) -> ProgressResponse:
        pid = path_id_for(user_id, resume_id, analysis_id)
        now = utc_now()

        doc = self._paths.find_one({"_id": pid, "user_id": user_id})
        if not doc:
            raise KeyError("Path not found")

        courses: List[Dict] = doc.get("courses", [])
        course = next((c for c in courses if c["course_id"] == course_id), None)
        if not course:
            raise KeyError("Course not found")
        if course["status"] == "locked":
            raise PermissionError("Course is locked")

        if course["status"] != "complete":
            activity = {
                "course_id": course["course_id"],
                "title": course["title"],
                "xp": course["xp"],
                "completed_at": now,
                "resume_label": doc["resume_label"],
            }

            self._paths.update_one(
                {"_id": pid, "courses.course_id": course_id},
                {
                    "$set": {
                        "courses.$.status": "complete",
                        "courses.$.completed_at": now,
                        "updated_at": now,
                    },
                    "$push": {
                        "activities": {
                            "$each": [activity],
                            "$position": 0,
                            "$slice": 50,
                        }
                    },
                },
            )

            next_locked = next(
                (
                    c for c in sorted(courses, key=lambda x: x["position"])
                    if c["status"] == "locked"
                ),
                None,
            )
            if next_locked:
                self._paths.update_one(
                    {"_id": pid, "courses.course_id": next_locked["course_id"]},
                    {"$set": {"courses.$.status": "current"}},
                )

        return self.progress(user_id, resume_id, analysis_id)

    def progress(self, user_id: str, resume_id: str, analysis_id: str) -> ProgressResponse:
        pid = path_id_for(user_id, resume_id, analysis_id)
        doc = self._paths.find_one({"_id": pid, "user_id": user_id})
        if not doc:
            raise KeyError("Path not found")

        courses = sorted(doc.get("courses", []), key=lambda c: c["position"])
        activities = doc.get("activities", [])[:10]  # newest-first via $position:0 on push

        earned_xp = sum(int(c["xp"]) for c in courses if c["status"] == "complete")
        total_xp = BASE_XP + earned_xp
        completed_count = sum(1 for c in courses if c["status"] == "complete")
        match_percent = int(doc["match_percent"])

        return ProgressResponse(
            userId=user_id,
            resumeId=doc["resume_id"],
            resumeLabel=str(doc["resume_label"]),
            analysisId=analysis_id,
            matchPercent=match_percent,
            earnedXp=earned_xp,
            baseXp=BASE_XP,
            totalXp=total_xp,
            level=compute_level(total_xp),
            nextLevelXp=NEXT_LEVEL_XP,
            courses=[
                {
                    "courseId": c["course_id"],
                    "title": c["title"],
                    "url": c["url"],
                    "provider": c["provider"],
                    "providerDetail": c["provider_detail"],
                    "description": c["description"],
                    "targetSkill": c["target_skill"],
                    "relevanceScore": float(c["relevance_score"]),
                    "xp": int(c["xp"]),
                    "position": int(c["position"]),
                    "status": c["status"],
                    "completedAt": c.get("completed_at"),
                }
                for c in courses
            ],
            achievements=achievements(completed_count, total_xp, match_percent),
            recentActivity=[
                {
                    "courseId": a["course_id"],
                    "title": a["title"],
                    "xp": int(a["xp"]),
                    "completedAt": a["completed_at"],
                    "resumeLabel": a["resume_label"],
                }
                for a in activities
            ],
        )
