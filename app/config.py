import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    recommendation_api_url: str
    mongodb_uri: str
    mongodb_database: str
    auth0_domain: str
    auth0_audience: str
    cors_origins: List[str]


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def get_settings() -> Settings:
    return Settings(
        recommendation_api_url=os.getenv(
            "RECOMMENDATION_API_URL",
            "http://localhost:8001/api/batch-recommendations",
        ),
        mongodb_uri=os.getenv("MONGODB_URI", ""),
        mongodb_database=os.getenv("MONGODB_DATABASE", "skillevate_user"),
        auth0_domain=os.getenv("AUTH0_DOMAIN", "skillevate.us.auth0.com"),
        auth0_audience=os.getenv("AUTH0_AUDIENCE", ""),
        cors_origins=_split_csv(
            os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3002")
        ),
    )
