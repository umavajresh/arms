import dj_database_url

from config.environment import (
    read_bool,
    read_int,
    read_list,
    read_required,
    read_required_list,
    read_str,
)

from .base import *

DEBUG = False

SECRET_KEY = read_required("SECRET_KEY")
SECRET_KEY_FALLBACKS = read_list("SECRET_KEY_FALLBACKS")

ALLOWED_HOSTS = read_required_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = read_list("CSRF_TRUSTED_ORIGINS")

DATABASES = {
    "default": dj_database_url.parse(
        read_required("DATABASE_URL"),
        conn_max_age=read_int("DATABASE_CONN_MAX_AGE", 600),
        conn_health_checks=True,
    ),
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = read_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = read_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = read_bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = read_int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = read_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = read_bool("SECURE_HSTS_PRELOAD", False)
SECURE_REFERRER_POLICY = "same-origin"

EMAIL_BACKEND = read_str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = read_str("EMAIL_HOST", "localhost")
EMAIL_PORT = read_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = read_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = read_str("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = read_bool("EMAIL_USE_TLS", True)

ADMINS = [("ARMS Operations", address) for address in read_list("DJANGO_ADMINS")]
