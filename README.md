# skillevate-gamification

FastAPI backend for Skillevate gamification state. The service fetches learning recommendations, stores course unlock/completion state, and serves XP/progress data to the Gamification MFE.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8003
```

Required production auth config:

- `AUTH0_DOMAIN`
- `AUTH0_AUDIENCE`

The MFE must send `Authorization: Bearer <Auth0 access token>` for all `/api/gamification/*` endpoints.

## Endpoints

- `GET /health`
- `POST /api/gamification/sync-analysis`
- `GET /api/gamification/progress?resumeId=...&analysisId=...`
- `POST /api/gamification/courses/{courseId}/complete`
- `POST /api/gamification/refresh-recommendations`

`POST /api/gamification/sync-analysis` accepts an optional `recommendationRequest` field with the exact body used by the Recommendation MFE for `/api/batch-recommendations`. When present, the backend uses and stores that request instead of rebuilding a recommendation request from gaps only. If omitted, the backend falls back to the gap-based request builder. The local default expects the recommendation service at `http://localhost:8001/api/batch-recommendations`.

## MongoDB document shape

Collection: `gamification_paths` inside the `skillevate_user` database.

`_id` is a SHA-256 hex digest of `{user_id}|{resume_id}|{analysis_id}` for O(1) keyed lookup.

XP, level, and achievements are **not stored** — they are computed at read time from the `courses` array so they are always consistent with actual completion state.

```json
{
  "_id": "<sha256 hex>",
  "user_id": "auth0|...",
  "resume_id": "string",
  "resume_label": "string",
  "analysis_id": "string",
  "match_percent": 82,
  "job_description": "string",
  "gaps": [
    { "skill": "string", "priority": "high" | "medium" | "low" }
  ],
  "recommendation_request": { },
  "courses": [
    {
      "course_id": "string",
      "title": "string",
      "url": "string",
      "provider": "string",
      "provider_detail": "string",
      "description": "string",
      "target_skill": "string",
      "relevance_score": 0.95,
      "xp": 100,
      "position": 0,
      "status": "locked" | "current" | "complete",
      "completed_at": "ISO8601 string | null"
    }
  ],
  "activities": [
    {
      "course_id": "string",
      "title": "string",
      "xp": 100,
      "completed_at": "ISO8601 string",
      "resume_label": "string"
    }
  ],
  "created_at": "ISO8601 string",
  "updated_at": "ISO8601 string"
}
```

Indexes:

| Name | Fields | Options |
|---|---|---|
| `user_resume_analysis_unique` | `(user_id, resume_id, analysis_id)` | unique |
| `user_updated_at` | `(user_id, updated_at)` | — |

Activities are capped at 50 entries (newest first) via `$push $position:0 $slice:50`.

## Tests

```bash
pytest
```
