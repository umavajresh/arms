from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMINISTRATOR)
        return super().create_superuser(username, email, password, **extra_fields)

    def find_by_login_identifier(self, identifier):
        return (
            self.filter(member_id=identifier).first()
            or self.filter(username=identifier).first()
        )
