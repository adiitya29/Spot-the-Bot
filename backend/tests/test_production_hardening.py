"""Tests verifying production security hardening, settings, and logging configuration."""

from __future__ import annotations

import logging
import os
from unittest import mock

from django.conf import settings


def test_production_settings_hardening() -> None:
    """Verify production settings enforce strict security invariants."""
    mock_env = {
        "DJANGO_SECRET_KEY": "production-very-secret-key-12345",
        "ALLOWED_HOSTS": "spotthebot.app,api.spotthebot.app",
        "DATABASE_URL": "postgres://user:pass@localhost:5432/proddb",
        "REDIS_URL": "redis://localhost:6379/0",
        "FRONTEND_ORIGIN": "https://spotthebot.app",
        "CSRF_TRUSTED_ORIGINS": "https://spotthebot.app",
        "SECURE_SSL_REDIRECT": "True",
        "SECURE_HSTS_SECONDS": "31536000",
        "NUM_PROXIES": "1",
    }

    with mock.patch.dict(os.environ, mock_env):
        from config.settings import prod

        assert prod.DEBUG is False
        assert prod.SECRET_KEY == "production-very-secret-key-12345"
        assert "spotthebot.app" in prod.ALLOWED_HOSTS
        assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert prod.SESSION_COOKIE_SECURE is True
        assert prod.CSRF_COOKIE_SECURE is True
        assert prod.SESSION_COOKIE_HTTPONLY is True
        assert prod.CSRF_COOKIE_HTTPONLY is True
        assert prod.SECURE_BROWSER_XSS_FILTER is True
        assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert prod.X_FRAME_OPTIONS == "DENY"
        assert prod.SECURE_HSTS_SECONDS == 31536000
        assert prod.REST_FRAMEWORK.get("NUM_PROXIES") == 1
        assert "json" in prod.LOGGING["formatters"]


def test_json_logging_formatter() -> None:
    """Verify python-json-logger produces valid JSON output for logs."""
    from pythonjsonlogger.json import JsonFormatter

    formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(module)s %(message)s")
    record = logging.LogRecord(
        name="spot_the_bot.security",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Player joined with secure token",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert '"message": "Player joined with secure token"' in output
    assert '"levelname": "INFO"' in output
    assert '"name": "spot_the_bot.security"' in output


def test_active_environment_security_headers() -> None:
    """Ensure base settings have proper X-Frame and CSRF origins configured."""
    assert hasattr(settings, "CSRF_TRUSTED_ORIGINS")
    assert "django.middleware.security.SecurityMiddleware" in settings.MIDDLEWARE
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
    assert "django.middleware.clickjacking.XFrameOptionsMiddleware" in settings.MIDDLEWARE
