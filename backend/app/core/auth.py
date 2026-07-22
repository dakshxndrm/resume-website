"""Firebase ID token verification.

The frontend sends `Authorization: Bearer <firebase-id-token>` on every request.
We verify it with firebase-admin and return the decoded claims (uid, email, name).
Postgres rows are keyed by the Firebase UID — Firebase = identity, Postgres = data.
"""
import os

import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def _init_firebase() -> bool:
    if firebase_admin._apps:
        return True
    if os.path.exists(settings.firebase_credentials):
        firebase_admin.initialize_app(credentials.Certificate(settings.firebase_credentials))
        return True
    return False  # not configured yet — auth endpoints will 503


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if not _init_firebase():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Firebase not configured on server")
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return fb_auth.verify_id_token(cred.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict | None:
    """Score-check works without login (frictionless landing flow)."""
    if cred is None or not _init_firebase():
        return None
    try:
        return fb_auth.verify_id_token(cred.credentials)
    except Exception:
        return None
