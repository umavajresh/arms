import os

from django.core.exceptions import ImproperlyConfigured

TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def read_str(name, default=""):
    return os.environ.get(name, "").strip() or default


def read_required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured("The %s environment variable is required." % name)
    return value


def read_bool(name, default=False):
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return value.lower() in TRUTHY_VALUES


def read_int(name, default):
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ImproperlyConfigured(
            "The %s environment variable must be an integer." % name
        ) from error


def read_list(name, default=()):
    value = os.environ.get(name, "").strip()
    if not value:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def read_required_list(name):
    values = read_list(name)
    if not values:
        raise ImproperlyConfigured("The %s environment variable is required." % name)
    return values


def default_settings_module():
    if read_bool("VERCEL"):
        return "config.settings.production"
    return "config.settings.development"
