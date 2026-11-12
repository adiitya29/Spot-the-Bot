"""Development and test settings."""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-in-prod")
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "backend", "testserver"],
)
MIN_HUMANS_DEFAULT = 3
