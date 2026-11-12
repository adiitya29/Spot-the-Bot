"""Base Django settings shared across all environments."""

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    REDIS_URL=(str, ""),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/1"),
    LLM_PROVIDER=(str, "fake"),
    LLM_API_KEY=(str, ""),
    LLM_MODEL=(str, "fake"),
    BOT_ENABLED=(bool, True),
    BOT_MAX_CALLS_PER_ROUND=(int, 25),
    BOT_DAILY_CALLS_PER_IP=(int, 200),
    SENTRY_DSN=(str, ""),
    FRONTEND_ORIGIN=(str, "http://localhost:5173"),
)

env_file = REPO_ROOT / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-placeholder-override-in-env")
DEBUG: bool = env("DJANGO_DEBUG")
ALLOWED_HOSTS: list[str] = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "apps.common",
    "apps.rooms",
    "apps.game",
    "apps.bot",
    "apps.replays",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

REDIS_URL: str = env("REDIS_URL")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# Celery
CELERY_BROKER_URL: str = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND: str = env("CELERY_BROKER_URL")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

# Spot the Bot settings
FRONTEND_ORIGIN: str = env("FRONTEND_ORIGIN")
LLM_PROVIDER: str = env("LLM_PROVIDER")
LLM_API_KEY: str = env("LLM_API_KEY")
LLM_MODEL: str = env("LLM_MODEL")
BOT_ENABLED: bool = env("BOT_ENABLED")
BOT_MAX_CALLS_PER_ROUND: int = env("BOT_MAX_CALLS_PER_ROUND")
BOT_DAILY_CALLS_PER_IP: int = env("BOT_DAILY_CALLS_PER_IP")
SENTRY_DSN: str = env("SENTRY_DSN")
MIN_HUMANS_DEFAULT = 4
MAX_HUMANS_DEFAULT = 7
