from typing import Dict, List, Optional

import requests

from .models import GapInput, RecommendationRequestBody


def build_skill_requests(gaps: List[GapInput]) -> List[Dict[str, object]]:
    requests_body: List[Dict[str, object]] = []
    for gap in gaps:
        tokens = [part.strip() for part in gap.match.replace(";", ",").replace("/", ",").split(",") if part.strip()]
        preferences = [
            "priority-high" if gap.priority.lower() == "high" else "priority-medium",
            *tokens,
        ][:12]
        requests_body.append(
            {
                "skill": " ".join(gap.name.lower().split()),
                "preferences": preferences or ["general"],
            }
        )
    return requests_body


def fetch_batch_recommendations(
    api_url: str,
    gaps: List[GapInput],
    recommendation_request: Optional[RecommendationRequestBody] = None,
) -> Dict[str, object]:
    body = (
        recommendation_request.model_dump()
        if recommendation_request
        else {
            "skills": build_skill_requests(gaps),
            "max_results": 10,
            "language": "en",
        }
    )
    if not body.get("skills"):
        return {"results": [], "metadata": {"total_skills": 0}}
    response = requests.post(api_url, json=body, timeout=20)
    response.raise_for_status()
    return response.json()


def normalize_recommendations(api_response: Dict[str, object]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    seen = set()
    results = api_response.get("results", [])
    if not isinstance(results, list):
        return normalized

    for skill_block in results:
        if not isinstance(skill_block, dict):
            continue
        skill = str(skill_block.get("skill") or "Recommended")
        recommendations = skill_block.get("recommendations", [])
        if not isinstance(recommendations, list):
            continue
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            course_id = str(rec.get("id") or "")
            if not course_id or course_id in seen:
                continue
            seen.add(course_id)
            relevance = float(rec.get("relevance_score") or 0.2)
            normalized.append(
                {
                    "course_id": course_id,
                    "title": str(rec.get("title") or "Untitled resource"),
                    "url": str(rec.get("url") or ""),
                    "provider": str(rec.get("provider") or "Resource"),
                    "provider_detail": str(rec.get("channel_name") or rec.get("org_login") or rec.get("provider") or "Resource"),
                    "description": str(rec.get("description") or ""),
                    "target_skill": skill,
                    "relevance_score": relevance,
                    "xp": max(40, round(relevance * 200)),
                }
            )

    return normalized
