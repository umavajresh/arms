from django.contrib.auth import middleware

from .http import expects_json, json_failure


class LoginRequiredMiddleware(middleware.LoginRequiredMiddleware):
    def handle_no_permission(self, request, view_func):
        if expects_json(request):
            return json_failure("Please sign in to continue.", http_status=401)
        return super().handle_no_permission(request, view_func)
