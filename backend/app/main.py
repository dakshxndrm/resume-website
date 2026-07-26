import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.services.scoring import warm_semantic_model

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Boot work. Everything here is best-effort: startup must always succeed."""
    # Dev convenience: create tables if the DB is reachable. Use Alembic for production.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.error("could not create tables - check DATABASE_URL in backend/.env: %s", exc)

    # Load the SBERT semantic model here, not on the first /score request. Costs
    # ~10s on CPU with a warm cache; the very first boot on a new machine also
    # downloads ~90MB of weights. That belongs in deploy time, not in a user's
    # request. Blocking on purpose - the process should not report ready until it
    # can actually score. warm_semantic_model() swallows its own failures and
    # returns False, so a broken model install degrades to BM25, never a dead app.
    try:
        ready = warm_semantic_model()
    except Exception as exc:  # belt and braces - nothing here may abort startup
        logger.warning("SBERT warm-up raised unexpectedly (%s) - continuing on BM25", exc)
        ready = False
    logger.info(
        "Semantic scoring: %s",
        "SBERT + BM25 + keyword coverage" if ready
        else "BM25 + keyword coverage only (SBERT unavailable)",
    )

    yield
    # nothing to tear down: the model dies with the process


app = FastAPI(title="ResumeAI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception as exc:
        # 503 so uptime checks actually see the failure, not a green 200.
        return JSONResponse({"db": "error", "detail": str(exc)}, status_code=503)
