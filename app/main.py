from functools import lru_cache

import requests
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import current_user_id
from .config import get_settings
from .models import CompleteCourseRequest, ProgressResponse, RefreshRecommendationsRequest, SyncAnalysisRequest
from .recommendations import fetch_batch_recommendations, normalize_recommendations
from .storage import Store

settings = get_settings()

app = FastAPI(
    title="Skillevate Gamification",
    description="Stores XP, course unlock state, and achievements for Skillevate users.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store(settings.sqlite_path)


def _fetch_normalized_courses(gaps):
    try:
        api_response = fetch_batch_recommendations(settings.recommendation_api_url, gaps)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Recommendation API request failed: {exc}",
        ) from exc
    return normalize_recommendations(api_response)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/gamification/sync-analysis", response_model=ProgressResponse)
def sync_analysis(
    request: SyncAnalysisRequest,
    user_id: str = Depends(current_user_id),
    store: Store = Depends(get_store),
):
    courses = _fetch_normalized_courses(request.gaps)
    store.upsert_path(
        user_id=user_id,
        resume_id=request.resumeId,
        resume_label=request.resumeLabel,
        analysis_id=request.analysisId,
        match_percent=request.matchPercent,
        gaps=request.gaps,
        job_description=request.jobDescription or "",
        courses=courses,
    )
    return store.progress(user_id, request.resumeId, request.analysisId)


@app.get("/api/gamification/progress", response_model=ProgressResponse)
def progress(
    resumeId: str,
    analysisId: str,
    user_id: str = Depends(current_user_id),
    store: Store = Depends(get_store),
):
    try:
        return store.progress(user_id, resumeId, analysisId)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gamification path not found") from exc


@app.post("/api/gamification/courses/{course_id}/complete", response_model=ProgressResponse)
def complete_course(
    course_id: str,
    request: CompleteCourseRequest,
    user_id: str = Depends(current_user_id),
    store: Store = Depends(get_store),
):
    try:
        return store.complete_course(user_id, request.resumeId, request.analysisId, course_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post("/api/gamification/refresh-recommendations", response_model=ProgressResponse)
def refresh_recommendations(
    request: RefreshRecommendationsRequest,
    user_id: str = Depends(current_user_id),
    store: Store = Depends(get_store),
):
    try:
        gaps = store.path_gaps(user_id, request.resumeId, request.analysisId)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gamification path not found") from exc

    courses = _fetch_normalized_courses(gaps)
    store.refresh_courses(user_id, request.resumeId, request.analysisId, courses)
    return store.progress(user_id, request.resumeId, request.analysisId)
