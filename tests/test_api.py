from fastapi.testclient import TestClient

from app.auth import current_user_id
from app.main import app, get_store
from app.storage import Store


def _courses():
    return [
        {
            "course_id": "course-1",
            "title": "Course 1",
            "url": "https://example.com",
            "provider": "YouTube",
            "provider_detail": "Teacher",
            "description": "Learn a skill",
            "target_skill": "graphql",
            "relevance_score": 0.5,
            "xp": 100,
        }
    ]


def test_progress_requires_auth():
    app.dependency_overrides = {}
    client = TestClient(app)

    response = client.get("/api/gamification/progress?resumeId=r1&analysisId=a1")

    assert response.status_code == 401


def test_sync_and_complete_course(monkeypatch, tmp_path):
    store = Store(str(tmp_path / "api.db"))
    app.dependency_overrides[current_user_id] = lambda: "auth0|user"
    app.dependency_overrides[get_store] = lambda: store
    monkeypatch.setattr("app.main._fetch_normalized_courses", lambda gaps: _courses())
    client = TestClient(app)

    sync_response = client.post(
        "/api/gamification/sync-analysis",
        json={
            "resumeId": "resume-1",
            "resumeLabel": "Resume v1",
            "analysisId": "analysis-1",
            "matchPercent": 70,
            "gaps": [{"name": "GraphQL", "priority": "High", "match": "0%"}],
            "jobDescription": "GraphQL role",
        },
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["courses"][0]["status"] == "current"

    complete_response = client.post(
        "/api/gamification/courses/course-1/complete",
        json={"resumeId": "resume-1", "analysisId": "analysis-1"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["earnedXp"] == 100
    assert complete_response.json()["courses"][0]["status"] == "complete"

    app.dependency_overrides = {}
