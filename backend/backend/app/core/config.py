from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ROOT_DIR = _BACKEND_DIR.parent
_ENV_FILES = [
    str(_ROOT_DIR / ".env"),
    ".env",
    str(_BACKEND_DIR / ".env"),
]
if os.getenv("ENV_FILE"):
    _ENV_FILES.append(os.getenv("ENV_FILE"))

class Settings(BaseSettings):
    PROJECT_NAME: str = "LearnSphere AI"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/learnsphere",
        description="PostgreSQL connection string. Can fallback to sqlite:///./learnsphere.db if needed."
    )

    # Authentication & JWT (Phase 6A)
    JWT_SECRET_KEY: str = Field(
        default="learnsphere-secure-random-jwt-secret-key-phase6a-super-secret-key-32b",
        description="Secret key for signing JWT access tokens"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm for JWT signing and verification"
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        description="Token expiration time in minutes"
    )

    # Qdrant Vector DB
    QDRANT_URL: str = Field(default="http://localhost:6333", description="Qdrant service URL")
    QDRANT_API_KEY: Optional[str] = Field(default=None, description="Qdrant API key if using cloud")
    QDRANT_COLLECTION: str = Field(default="learnsphere_chunks", description="Collection name")
    QDRANT_STORAGE_PATH: Optional[str] = Field(default="./qdrant_storage", description="Embedded storage path if remote not reachable")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="openai", description="Provider: openai, groq, gemini, ollama")
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="LLM model identifier")
    LLM_API_KEY: Optional[str] = Field(default=None, description="API key for LLM provider")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="Custom base URL for OpenAI-compatible LLM endpoints")
    LLM_MAX_CONCURRENCY: int = Field(default=1, description="Maximum concurrent Groq LLM generation requests")
    LLM_MIN_INTERVAL_SECONDS: float = Field(default=2.0, description="Minimum delay between successive Groq LLM requests")
    LLM_MAX_RETRIES: int = Field(default=2, description="Maximum retry attempts on 429 rate limit")
    LLM_MAX_RETRY_DELAY_SECONDS: float = Field(default=3.0, description="Maximum wait delay per retry in seconds")
    LLM_MAX_CUMULATIVE_RETRY_WAIT_SECONDS: float = Field(default=5.0, description="Maximum cumulative wait time across all retries in seconds")

    # Vision & Multimodal Settings (Phase 4A)
    VISION_PROVIDER: str = Field(default="groq", description="Vision provider: groq, openai, ollama")
    VISION_MODEL: str = Field(default="qwen/qwen3.6-27b", description="Vision model identifier for diagram/image understanding")
    VISION_API_KEY: Optional[str] = Field(default=None, description="API key for vision model (falls back to LLM_API_KEY if not set)")
    VISION_BASE_URL: Optional[str] = Field(default=None, description="Custom base URL for vision model API")
    VISION_ENABLED: bool = Field(default=True, description="Enable visual extraction and vision model descriptions")

    # Speech-to-Text Transcription Settings (Phase 4B)
    TRANSCRIPTION_PROVIDER: str = Field(default="groq", description="Transcription provider: groq, openai")
    TRANSCRIPTION_MODEL: str = Field(default="whisper-large-v3-turbo", description="Whisper model identifier: whisper-large-v3-turbo, whisper-large-v3")
    TRANSCRIPTION_LANGUAGE: Optional[str] = Field(default=None, description="Optional language code (e.g. 'en')")
    TRANSCRIPTION_API_KEY: Optional[str] = Field(default=None, description="API key for transcription (falls back to LLM_API_KEY)")
    TRANSCRIPTION_BASE_URL: Optional[str] = Field(default=None, description="Custom base URL for transcription API")
    TRANSCRIPTION_ENABLED: bool = Field(default=True, description="Enable video audio transcription")
    TRANSCRIPTION_MAX_FILE_MB: int = Field(default=25, description="Max direct file size in MB for speech-to-text API before extraction/chunking")
    TRANSCRIPTION_CHUNK_SECONDS: int = Field(default=600, description="Duration in seconds for chunking long audio")
    TRANSCRIPTION_OVERLAP_SECONDS: int = Field(default=5, description="Overlap in seconds for audio chunking")

    # Embedding Settings
    EMBEDDING_PROVIDER: str = Field(default="fastembed", description="Provider: fastembed, openai")
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-small-en-v1.5", description="Embedding model identifier")
    EMBEDDING_API_KEY: Optional[str] = Field(default=None, description="API key for embedding provider if required")

    # Environment & Deployment
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment mode: 'development' or 'production'"
    )

    # Frontend & CORS
    FRONTEND_URL: str = Field(default="http://localhost:5173", description="Allowed frontend origin for CORS")
    CORS_ORIGINS: Optional[str] = Field(
        default=None,
        description="Comma-separated additional allowed origins for CORS (e.g., 'http://localhost:5173,http://localhost:5174')"
    )
    CORS_ALLOW_METHODS: Optional[str] = Field(
        default=None,
        description="Comma-separated allowed HTTP methods for CORS"
    )
    CORS_ALLOW_HEADERS: Optional[str] = Field(
        default=None,
        description="Comma-separated allowed headers for CORS, or '*' to allow all headers"
    )

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        if self.ENVIRONMENT.lower() != "production":
            origins.extend([
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ])
        for s in (self.FRONTEND_URL, self.CORS_ORIGINS):
            if s:
                for item in s.split(","):
                    clean = item.strip().rstrip("/")
                    if clean and clean not in origins:
                        origins.append(clean)
        return origins

    @property
    def cors_allow_methods(self) -> list[str]:
        if self.CORS_ALLOW_METHODS:
            methods = [m.strip().upper() for m in self.CORS_ALLOW_METHODS.split(",") if m.strip()]
            if methods:
                return methods
        return ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    @property
    def cors_allow_headers(self) -> list[str]:
        if self.CORS_ALLOW_HEADERS:
            headers = [h.strip() for h in self.CORS_ALLOW_HEADERS.split(",") if h.strip()]
            if headers:
                return headers
        return ["*"]

    # Uploads & Storage
    UPLOAD_DIR: str = Field(default="./uploads", description="Directory to store uploaded files")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, description="Maximum allowed file size in MB")

    # RAG Retrieval & Grounding
    RAG_TOP_K: int = Field(default=5, description="Number of top chunks to retrieve")
    RAG_SCORE_THRESHOLD: float = Field(default=0.55, description="Minimum cosine similarity score threshold for grounding")

    # Learner Model & Mastery Thresholds
    MASTERY_WEAK_THRESHOLD: float = Field(default=0.60, description="Score threshold below which a topic is considered weak")
    MASTERY_STRONG_THRESHOLD: float = Field(default=0.75, description="Score threshold at or above which a topic is considered strong")

    # Evaluation Settings (Demo Safe & Live Hackathon Bounding)
    EVALUATION_MAX_CASES_LIVE: int = Field(
        default=3,
        description="Maximum test cases for quick/live evaluation mode to protect LLM quota"
    )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
