import mongomock
from datetime import datetime, timedelta, timezone

from app.gamification import compute_streak
from app.models import GapInput
from app.recommendations import fetch_user_recommendations, normalize_user_recommendations
from app.storage import Store


def make_store() -> Store:
    return Store("", "test_db", _client=mongomock.MongoClient())


def test_normalize_user_recommendations_dedupes_and_assigns_xp():
    response = {
        "recommendations": [
            {
                "recommendation_id": "course-1",
                "title": "GraphQL APIs",
                "url": "https://example.com",
                "provider": "YouTube",
                "description": "Build APIs with GraphQL",
                "tags": ["graphql"],
                "relevance_score": 0.5,
                "status": "recommended",
                "xp_value": 50,
                "linked_gap": "GraphQL",
            },
            {
                "recommendation_id": "course-1",
                "title": "Duplicate",
                "url": "https://example.com/2",
                "provider": "YouTube",
                "description": "",
                "tags": [],
                "relevance_score": 0.8,
                "status": "recommended",
                "xp_value": 80,
                "linked_gap": "GraphQL",
            },
        ]
    }

    courses = normalize_user_recommendations(response)

    assert len(courses) == 1
    assert courses[0]["course_id"] == "course-1"
    assert courses[0]["target_skill"] == "GraphQL"
    assert courses[0]["xp"] == 50


def test_normalize_user_recommendations_applies_xp_minimum():
    response = {
        "recommendations": [
            {
                "recommendation_id": "course-low",
                "title": "Low relevance course",
                "url": "https://example.com",
                "provider": "Dev.to",
                "description": "",
                "tags": [],
                "relevance_score": 0.1,
                "status": "recommended",
                "xp_value": 10,
                "linked_gap": "Docker",
            }
        ]
    }

    courses = normalize_user_recommendations(response)

    assert courses[0]["xp"] == 40


def test_normalize_user_recommendations_empty():
    assert normalize_user_recommendations({}) == []
    assert normalize_user_recommendations({"recommendations": []}) == []


def test_fetch_user_recommendations_sends_correct_body(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"recommendations": [], "cached": False}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return Response()

    monkeypatch.setattr("app.recommendations.requests.post", fake_post)

    fetch_user_recommendations("https://recommend.example/api/user-recommendations", "user-1", "analysis-1")

    assert captured["url"] == "https://recommend.example/api/user-recommendations"
    assert captured["json"]["user_id"] == "user-1"
    assert captured["json"]["analysis_id"] == "analysis-1"


def test_completion_awards_xp_once_and_unlocks_next():
    store = make_store()
    courses = [
        {
            "course_id": "a",
            "title": "A",
            "url": "https://a.example",
            "provider": "YouTube",
            "provider_detail": "A Channel",
            "description": "A course",
            "target_skill": "GraphQL",
            "relevance_score": 0.5,
            "xp": 100,
        },
        {
            "course_id": "b",
            "title": "B",
            "url": "https://b.example",
            "provider": "GitHub",
            "provider_detail": "B Org",
            "description": "B course",
            "target_skill": "Docker",
            "relevance_score": 0.4,
            "xp": 80,
        },
    ]
    store.upsert_path("user-1", "resume-1", "Resume v1", "analysis-1", 72, [GapInput(name="GraphQL")], "", courses)

    first = store.progress("user-1", "resume-1", "analysis-1")
    assert [c.status for c in first.courses] == ["current", "locked"]

    after = store.complete_course("user-1", "resume-1", "analysis-1", "a")
    assert after.earnedXp == 100
    assert [c.status for c in after.courses] == ["complete", "current"]

    after_again = store.complete_course("user-1", "resume-1", "analysis-1", "a")
    assert after_again.earnedXp == 100


def test_upsert_backfills_courses_for_existing_empty_path():
    store = make_store()
    gaps = [GapInput(name="GraphQL", priority="High", match="Apollo")]
    courses = [
        {
            "course_id": "a",
            "title": "A",
            "url": "https://a.example",
            "provider": "YouTube",
            "provider_detail": "A Channel",
            "description": "A course",
            "target_skill": "GraphQL",
            "relevance_score": 0.5,
            "xp": 100,
        },
        {
            "course_id": "b",
            "title": "B",
            "url": "https://b.example",
            "provider": "GitHub",
            "provider_detail": "B Org",
            "description": "B course",
            "target_skill": "Docker",
            "relevance_score": 0.4,
            "xp": 80,
        },
    ]

    store.upsert_path("user-1", "resume-1", "Resume v1", "analysis-1", 72, gaps, "", [])
    assert store.progress("user-1", "resume-1", "analysis-1").courses == []

    store.upsert_path("user-1", "resume-1", "Resume v1", "analysis-1", 72, gaps, "", courses)
    backfilled = store.progress("user-1", "resume-1", "analysis-1")
    assert [c.courseId for c in backfilled.courses] == ["a", "b"]
    assert [c.status for c in backfilled.courses] == ["current", "locked"]


def test_locked_course_cannot_be_completed():
    store = make_store()
    courses = [
        {"course_id": "a", "title": "A", "url": "", "provider": "YouTube",
         "provider_detail": "A Channel", "description": "", "target_skill": "GraphQL",
         "relevance_score": 0.5, "xp": 100},
        {"course_id": "b", "title": "B", "url": "", "provider": "GitHub",
         "provider_detail": "B Org", "description": "", "target_skill": "Docker",
         "relevance_score": 0.4, "xp": 80},
    ]
    store.upsert_path("user-1", "resume-1", "Resume v1", "analysis-1", 72, [GapInput(name="GraphQL")], "", courses)

    try:
        store.complete_course("user-1", "resume-1", "analysis-1", "b")
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected locked course completion to fail")


def _activity(days_ago: int) -> dict:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"course_id": f"c-{days_ago}", "title": "X", "xp": 50, "completed_at": dt.isoformat(), "resume_label": "R"}


def test_streak_consecutive_days():
    activities = [_activity(0), _activity(1), _activity(2)]
    assert compute_streak(activities) == 3


def test_streak_multiple_completions_same_day():
    activities = [_activity(0), _activity(0), _activity(1)]
    assert compute_streak(activities) == 2


def test_streak_broken_by_gap():
    activities = [_activity(0), _activity(2)]
    assert compute_streak(activities) == 1


def test_streak_zero_when_last_completion_too_old():
    activities = [_activity(3), _activity(4)]
    assert compute_streak(activities) == 0


def test_streak_empty():
    assert compute_streak([]) == 0
