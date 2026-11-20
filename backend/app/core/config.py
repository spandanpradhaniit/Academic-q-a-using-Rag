import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root:rootpassword@127.0.0.1:3306/academic_rag"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_cookie_secure: bool = True
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "none"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ocr_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    vector_store: str = "faiss"
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    celery_broker_url: str = ""
    rate_limit_enabled: bool = False
    llama_model: str = "openai/gpt-oss-120b"
    embedding_model: str = "text-embedding-3-small"
    upload_dir: Path = Path("/tmp/academic-qa/uploads") if os.getenv("VERCEL") else Path("data/uploads")
    faiss_dir: Path = Path("/tmp/academic-qa/faiss") if os.getenv("VERCEL") else Path("data/faiss")
    bm25_dir: Path = Path("/tmp/academic-qa/bm25") if os.getenv("VERCEL") else Path("data/bm25")
    max_file_size_mb: int = 4 if os.getenv("VERCEL") else 20
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k_semantic: int = 10
    top_k_keyword: int = 10
    top_k_candidates: int = 30
    top_k_final: int = 5
    rrf_k: int = 60
    use_weighted_rrf: bool = True
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3
    min_relevance: float = 0.2
    rewrite_model: str = "gpt-4o-mini"
    rewrite_timeout_seconds: int = 2
    reranker: str = "none"
    rerank_top_k: int = 5
    rerank_timeout_seconds: int = 5
    cohere_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    testing: bool = False

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
