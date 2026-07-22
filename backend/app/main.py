from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.db import Base, engine

app = FastAPI(title="ResumeAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    """Dev convenience: create tables if DB reachable. Use Alembic migrations for production."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        print("WARNING: database unreachable — set DATABASE_URL in .env")


@app.get("/health")
def health():
    return {"status": "ok"}
