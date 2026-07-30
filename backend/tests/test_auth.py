import base64
import json

from app.core import auth
from app.core.config import settings


def test_init_firebase_decodes_base64_credentials(monkeypatch):
    """Prod path: FIREBASE_CREDENTIALS_B64 decodes to the same dict
    credentials.Certificate() would get from a file, no temp file involved."""
    info = {"type": "service_account", "project_id": "demo"}
    encoded = base64.b64encode(json.dumps(info).encode()).decode()
    monkeypatch.setattr(settings, "firebase_credentials_b64", encoded)
    monkeypatch.setattr(auth.firebase_admin, "_apps", [])

    seen = {}
    monkeypatch.setattr(auth.credentials, "Certificate", lambda arg: seen.setdefault("arg", arg))
    monkeypatch.setattr(auth.firebase_admin, "initialize_app", lambda cred: None)

    assert auth._init_firebase() is True
    assert seen["arg"] == info


def test_init_firebase_prefers_base64_over_file_path(monkeypatch, tmp_path):
    """If both are set, the env-var path wins — that's the one prod actually uses."""
    info = {"type": "service_account", "project_id": "demo"}
    encoded = base64.b64encode(json.dumps(info).encode()).decode()
    monkeypatch.setattr(settings, "firebase_credentials_b64", encoded)
    monkeypatch.setattr(settings, "firebase_credentials", str(tmp_path / "unused.json"))
    monkeypatch.setattr(auth.firebase_admin, "_apps", [])

    calls = []
    monkeypatch.setattr(auth.credentials, "Certificate", lambda arg: calls.append(arg) or arg)
    monkeypatch.setattr(auth.firebase_admin, "initialize_app", lambda cred: None)

    auth._init_firebase()
    assert calls == [info]
