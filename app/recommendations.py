from typing import Dict, List

import requests


def fetch_user_recommendations(
    api_url: str,
    user_id: str,
    analysis_id: str,
    max_results: int = 10,
) -> Dict[str, object]:
    body = {
        "user_id": user_id,
        "analysis_id": analysis_id,
        "max_results": max_results,
        "language": "en",
    }
    response = requests.post(api_url, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def normalize_user_recommendations(api_response: Dict[str, object]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    seen: set = set()

    recommendations = api_response.get("recommendations", [])
    if not isinstance(recommendations, list):
        return normalized

    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        course_id = str(rec.get("recommendation_id") or "")
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)
        relevance = float(rec.get("relevance_score") or 0.2)
        xp = int(rec.get("xp_value") or 0)
        normalized.append(
            {
                "course_id": course_id,
                "title": str(rec.get("title") or "Untitled resource"),
                "url": str(rec.get("url") or ""),
                "provider": str(rec.get("provider") or "Resource"),
                "provider_detail": str(rec.get("provider") or "Resource"),
                "description": str(rec.get("description") or ""),
                "target_skill": str(rec.get("linked_gap") or "General"),
                "relevance_score": relevance,
                "xp": max(40, xp),
            }
        )

    return normalized
