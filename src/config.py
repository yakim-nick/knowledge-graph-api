"""Application configuration loaded from environment variables."""

from enum import StrEnum

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env before instantiating Settings so env vars are available.
load_dotenv()


class Environment(StrEnum):
    """Deployment environments that influence runtime behaviour (e.g. error verbosity)."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Centralised, env-driven configuration for the API and its integrations."""

    api_key: str = ""
    openai_api_key: str = ""
    extraction_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    database_url: str = (
        "postgresql+asyncpg://kgadmin:changeme@postgres:5432/knowledge_graph"
    )

    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_concurrent_extractions: int = 5

    log_level: str = "INFO"
    environment: Environment = Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Whether the app runs in production (used to hide internal error details)."""
        return self.environment == Environment.PRODUCTION


settings = Settings()
