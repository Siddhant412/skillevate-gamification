from typing import List, Optional

from pydantic import BaseModel, Field


class GapInput(BaseModel):
    name: str
    priority: str = "Medium"
    match: str = ""


class RecommendationSkillRequest(BaseModel):
    skill: str
    preferences: List[str] = Field(default_factory=list)


class RecommendationRequestBody(BaseModel):
    skills: List[RecommendationSkillRequest] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=50)
    language: Optional[str] = "en"


class SyncAnalysisRequest(BaseModel):
    userId: str
    resumeId: str
    resumeLabel: str
    analysisId: str
    matchPercent: int = Field(ge=0, le=100)
    gaps: List[GapInput]
    jobDescription: Optional[str] = ""
    recommendationRequest: Optional[RecommendationRequestBody] = None


class RefreshRecommendationsRequest(BaseModel):
    userId: str
    resumeId: str
    analysisId: str


class CompleteCourseRequest(BaseModel):
    userId: str
    resumeId: str
    analysisId: str


class CourseProgress(BaseModel):
    courseId: str
    title: str
    url: str
    provider: str
    providerDetail: str
    description: str
    targetSkill: str
    relevanceScore: float
    xp: int
    position: int
    status: str
    completedAt: Optional[str] = None


class Achievement(BaseModel):
    id: str
    title: str
    description: str
    unlocked: bool


class Activity(BaseModel):
    courseId: str
    title: str
    xp: int
    completedAt: str
    resumeLabel: str


class ProgressResponse(BaseModel):
    userId: str
    resumeId: str
    resumeLabel: str
    analysisId: str
    matchPercent: int
    earnedXp: int
    baseXp: int
    totalXp: int
    level: int
    nextLevelXp: int
    courses: List[CourseProgress]
    achievements: List[Achievement]
    recentActivity: List[Activity]
