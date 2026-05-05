# skillevate-gamification

FastAPI backend for Skillevate gamification state. The service fetches learning recommendations, stores course unlock/completion state, and serves XP/progress data to the Gamification MFE.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8002
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

## Minimum MongoDB fields

When moving gamification state into the shared user MongoDB, the minimum document shape should preserve one gamified learning path per user + resume + analysis:

```ts
{
  userId: string,
  pathId: string,
  resumeId: string,
  analysisId: string,
  totalXp: number,
  level: number,

  courses: [
    {
      courseId: string,
      title: string,
      url: string,
      targetSkill: string,
      position: number,
      xp: number,
      status: "locked" | "current" | "complete",
      completedAt?: Date
    }
  ],

  activities: [
    {
      type: string,
      title: string,
      xpDelta: number,
      createdAt: Date
    }
  ],

  createdAt: Date,
  updatedAt: Date
}
```

Required uniqueness invariant:

```ts
{ userId: 1, resumeId: 1, analysisId: 1 }
```

This key should map to exactly one gamified learning path.

## Tests

```bash
pytest
```
