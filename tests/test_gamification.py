from app.models import GapInput
from app.recommendations import build_skill_requests, normalize_recommendations
from app.storage import Store


def test_build_skill_requests_from_gaps():
    gaps = [GapInput(name="GraphQL APIs", priority="High", match="Apollo, Backend")]

    assert build_skill_requests(gaps) == [
        {
            "skill": "graphql apis",
            "preferences": ["priority-high", "Apollo", "Backend"],
        }
    ]


def test_normalize_recommendations_dedupes_and_assigns_xp():
    response = {
        "results": [
            {
                "skill": "python",
                "recommendations": [
                    {
                        "id": "course-1",
                        "title": "Python APIs",
                        "url": "https://example.com",
                        "provider": "YouTube",
                        "description": "Build APIs",
                        "relevance_score": 0.5,
                        "channel_name": "Teacher",
                    },
                    {
                        "id": "course-1",
                        "title": "Duplicate",
                        "url": "https://example.com/2",
                        "provider": "YouTube",
                        "description": "",
                        "relevance_score": 1,
                    },
                ],
            }
        ]
    }

    courses = normalize_recommendations(response)

    assert len(courses) == 1
    assert courses[0]["course_id"] == "course-1"
    assert courses[0]["provider_detail"] == "Teacher"
    assert courses[0]["xp"] == 100


def test_completion_awards_xp_once_and_unlocks_next(tmp_path):
    store = Store(str(tmp_path / "gamify.db"))
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
    assert [course.status for course in first.courses] == ["current", "locked"]

    after = store.complete_course("user-1", "resume-1", "analysis-1", "a")
    assert after.earnedXp == 100
    assert [course.status for course in after.courses] == ["complete", "current"]

    after_again = store.complete_course("user-1", "resume-1", "analysis-1", "a")
    assert after_again.earnedXp == 100


def test_locked_course_cannot_be_completed(tmp_path):
    store = Store(str(tmp_path / "gamify.db"))
    courses = [
        {
            "course_id": "a",
            "title": "A",
            "url": "",
            "provider": "YouTube",
            "provider_detail": "A Channel",
            "description": "",
            "target_skill": "GraphQL",
            "relevance_score": 0.5,
            "xp": 100,
        },
        {
            "course_id": "b",
            "title": "B",
            "url": "",
            "provider": "GitHub",
            "provider_detail": "B Org",
            "description": "",
            "target_skill": "Docker",
            "relevance_score": 0.4,
            "xp": 80,
        },
    ]
    store.upsert_path("user-1", "resume-1", "Resume v1", "analysis-1", 72, [GapInput(name="GraphQL")], "", courses)

    try:
        store.complete_course("user-1", "resume-1", "analysis-1", "b")
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected locked course completion to fail")
