from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/resumeai"
    firebase_credentials: str = "./firebase-service-account.json"
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str = ""
    groq_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
