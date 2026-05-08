from datetime import datetime, timedelta, timezone
from typing import Dict, List

BASE_XP = 1200
NEXT_LEVEL_XP = 2000


def compute_streak(activities: List[Dict]) -> int:
    dates = set()
    for a in activities:
        completed_at = a.get("completed_at")
        if completed_at:
            dates.add(datetime.fromisoformat(completed_at).date())

    if not dates:
        return 0

    today = datetime.now(timezone.utc).date()
    sorted_dates = sorted(dates, reverse=True)

    # streak is dead if nothing completed today or yesterday
    if sorted_dates[0] < today - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i - 1] - sorted_dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def compute_level(total_xp: int) -> int:
    if total_xp >= 1800:
        return 5
    if total_xp >= 1200:
        return 4
    if total_xp >= 600:
        return 3
    return 1


def achievements(completed_count: int, total_xp: int, match_percent: int, streak: int = 0) -> List[Dict[str, object]]:
    return [
        {
            "id": "first-gap-closed",
            "title": "First Gap Closed",
            "description": "Completed a course to fill a missing skill",
            "unlocked": completed_count >= 1,
        },
        {
            "id": "fast-learner",
            "title": "Fast Learner",
            "description": "Completed 3 courses",
            "unlocked": completed_count >= 3,
        },
        {
            "id": "perfect-match",
            "title": "Perfect Match",
            "description": "Reached 90% JD match",
            "unlocked": match_percent >= 90,
        },
        {
            "id": "knowledge-seeker",
            "title": "Knowledge Seeker",
            "description": "Completed 5 courses",
            "unlocked": completed_count >= 5,
        },
        {
            "id": "on-a-roll",
            "title": "On a Roll",
            "description": "Completed courses 3 days in a row",
            "unlocked": streak >= 3,
        },
    ]
