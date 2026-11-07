from django.contrib.auth.hashers import make_password

from apps.accounts.models import User

DEFAULT_PASSWORD = "Valid-test-password-42"


def make_user(username="passenger", password=DEFAULT_PASSWORD, **fields):
    fields.setdefault("email", "%s@example.com" % username)
    return User.objects.create_user(username=username, password=password, **fields)


def make_administrator(username="administrator", password=DEFAULT_PASSWORD, **fields):
    return make_user(
        username=username, password=password, role=User.Role.ADMINISTRATOR, **fields
    )


def make_recoverable_user(answer, date_of_birth, **fields):
    return make_user(
        security_question=User.SecurityQuestion.PET,
        security_answer=make_password(answer),
        date_of_birth=date_of_birth,
        **fields,
    )
