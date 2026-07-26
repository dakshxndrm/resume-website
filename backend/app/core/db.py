from urllib.parse import urlparse, parse_qs

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_PLACEHOLDER = "postgresql://user:password@localhost:5432/resumeai"


def _normalize(url: str) -> str:
    if not url or url == _PLACEHOLDER or not url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            "DATABASE_URL is missing or still a placeholder. "
            "Paste your real Neon connection string (starts with postgresql://) "
            "into backend/.env"
        )
    # SQLAlchemy needs the "postgresql://" scheme, not Heroku-style "postgres://".
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Neon requires SSL; add sslmode=require if the URL doesn't already set it.
    if "sslmode" not in parse_qs(urlparse(url).query):
        url += ("&" if urlparse(url).query else "?") + "sslmode=require"
    return url


engine = create_engine(
    _normalize(settings.database_url),
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
