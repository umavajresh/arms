from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as message_constants

from config.environment import read_int, read_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "config.apps.ArmsAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.core",
    "apps.pages",
    "apps.accounts",
    "apps.flights",
    "apps.bookings",
    "apps.notifications",
    "apps.assistant",
    "apps.tracking",
    "apps.console",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        read_str("DATABASE_URL", "sqlite:///%s" % (BASE_DIR / "db.sqlite3")),
        conn_max_age=read_int("DATABASE_CONN_MAX_AGE", 600),
        conn_health_checks=True,
    ),
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.UsernameOrMemberIdBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

LOGIN_URL = "accounts:login"
LOGOUT_REDIRECT_URL = "pages:landing"
SESSION_COOKIE_AGE = 60 * 60 * 24

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_FROM_EMAIL = read_str("DEFAULT_FROM_EMAIL", "no-reply@arms.local")
SERVER_EMAIL = read_str("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": read_str("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": read_str("ARMS_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

ARMS_SITE_URL = read_str("SITE_URL", "http://localhost:8000")
ARMS_AVIATIONSTACK_API_KEY = read_str("AVIATIONSTACK_API_KEY")
ARMS_AI_PROVIDER_API_KEYS = {
    "openrouter": read_str("OPENROUTER_API_KEY"),
    "groq": read_str("GROQ_API_KEY"),
    "huggingface": read_str("HUGGINGFACE_API_KEY"),
    "openai": read_str("OPENAI_API_KEY"),
}
ARMS_AI_FALLBACK_API_KEY = read_str("AI_API_KEY")
