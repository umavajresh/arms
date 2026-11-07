from config.environment import read_list, read_str

from .base import *

DEBUG = True

SECRET_KEY = read_str(
    "SECRET_KEY", "django-insecure-development-key-never-use-in-production"
)

ALLOWED_HOSTS = read_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
