import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Settings:
    recommendation_api_url: str
    database_url: str
    auth0_domain: str
    auth0_audience: str
    cors_origins: List[str]

    @property
    def sqlite_path(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// DATABASE_URL values are supported for v1")
        return self.database_url[len(prefix) :]


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def get_settings() -> Settings:
    return Settings(
        recommendation_api_url=os.getenv(
            "RECOMMENDATION_API_URL",
            "http://localhost:8000/api/batch-recommendations",
        ),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./skillevate_gamification.db"),
        auth0_domain=os.getenv("AUTH0_DOMAIN", "skillevate.us.auth0.com"),
        auth0_audience=os.getenv("AUTH0_AUDIENCE", ""),
        cors_origins=_split_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3002")),
    )
