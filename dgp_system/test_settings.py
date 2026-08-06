"""Test settings: run suite against local SQLite so the live MSSQL DB is never touched.

Usage: manage.py test --settings=dgp_system.test_settings requests_app
"""
from pathlib import Path
from .settings import *  # noqa: F401,F403

_TEST_DIR = Path(__file__).resolve().parent.parent / "test_artifacts"
_TEST_DIR.mkdir(exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(_TEST_DIR / "test_db.sqlite3"),
    }
}

ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = str(_TEST_DIR / "media")

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
