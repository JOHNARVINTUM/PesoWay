"""Fast, isolated test settings. PostgreSQL remains the default runtime database."""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-django-checks")
os.environ.setdefault("WEBHOOK_ENCRYPTION_KEY", "h8UrfM50iqNhwI6d5Tq2aX72OdCwERXHr6tkQ0oRiY8=")

from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
DEBUG = True

