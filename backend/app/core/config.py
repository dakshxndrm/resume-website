from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/resumeai"
    firebase_credentials: str = "./firebase-service-account.json"
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # change with GROQ_MODEL in .env when Groq retires a model — no code edit needed
    groq_model: str = "llama-3.3-70b-versatile"

    class Config:
        env_file = ".env"


settings = Settings()
