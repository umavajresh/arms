from .base import *
from .base import BASE_DIR, MIDDLEWARE

DEBUG = False

MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]

SECRET_KEY = "django-insecure-test-key"

ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test-db.sqlite3",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

MEDIA_ROOT = BASE_DIR / "test-media"

ARMS_AVIATIONSTACK_API_KEY = ""
ARMS_AI_PROVIDER_API_KEYS = {
    "openrouter": "",
    "groq": "",
    "huggingface": "",
    "openai": "",
}
ARMS_AI_FALLBACK_API_KEY = ""
ARMS_AI_MODEL = ""

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"]},
}
