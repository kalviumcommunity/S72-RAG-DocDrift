from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str = "DocDrift API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i) for i in v]
        elif isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(i) for i in parsed]
            except Exception:
                pass
            return [v.strip()]
        raise ValueError(v)

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "docdrift_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docdrift_db"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_SSL: bool = False
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db_data"
    CHROMA_COLLECTION_NAME: str = "docdrift_chunks"

    # AI & Embeddings
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_PROVIDER: str = "gemini"  # "gemini", "openai", "local_fallback"
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    @property
    def chroma_base_url(self) -> str:
        protocol = "https" if self.CHROMA_SSL else "http"
        return f"{protocol}://{self.CHROMA_HOST}:{self.CHROMA_PORT}"


settings = Settings()
