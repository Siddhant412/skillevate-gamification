from typing import Dict, List

BASE_XP = 1200
NEXT_LEVEL_XP = 2000


def compute_level(total_xp: int) -> int:
    if total_xp >= 1800:
        return 5
    if total_xp >= 1200:
        return 4
    if total_xp >= 600:
        return 3
    return 1


def achievements(completed_count: int, total_xp: int, match_percent: int) -> List[Dict[str, object]]:
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
    ]
