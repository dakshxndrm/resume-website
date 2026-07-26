from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine

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
    except Exception as exc:
        print(f"ERROR: could not create tables - check DATABASE_URL in backend/.env: {exc}")


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception as exc:
        # 503 so uptime checks actually see the failure, not a green 200.
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)
