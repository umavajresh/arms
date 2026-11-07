from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrMemberIdBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        user_model = get_user_model()
        user = user_model._default_manager.find_by_login_identifier(username)
        if user is None:
            user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
