from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/resumeai"
    firebase_credentials: str = "./firebase-service-account.json"
    # Prod (Render/Railway etc.): base64 of the whole service-account JSON, since
    # those hosts don't give you a real filesystem to drop a secret file into.
    # Takes priority over firebase_credentials when set. See app/core/auth.py.
    firebase_credentials_b64: str = ""
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # change with GROQ_MODEL in .env when Groq retires a model — no code edit needed
    groq_model: str = "llama-3.3-70b-versatile"

    # --- LLM cost control (see app/services/llm_cache.py) ---
    # Daily LLM calls per signed-in user. 30 is roughly a full editing session's
    # worth of genuinely different resumes; the cache absorbs the repeats.
    llm_daily_limit_user: int = 30
    # Anonymous callers share a bucket per IP, so this is intentionally small:
    # it protects the shared free-tier quota from a single unauthenticated source.
    llm_daily_limit_anon: int = 5
    # How long cached suggestions stay valid. 30 days.
    suggestion_cache_ttl_hours: int = 720

    class Config:
        env_file = ".env"


settings = Settings()
