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

## Tests

```bash
pytest
```
