from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect
from django.utils.decorators import method_decorator

from .http import expects_json, json_failure

public_view = method_decorator(login_not_required, name="dispatch")


class PageMixin:
    page_title = ""
    topbar = True
    footer = True

    def get_page_title(self):
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", self.get_page_title())
        context["topbar"] = self.topbar
        context["footer"] = self.footer
        return context


class RoleRequiredMixin:
    denied_message = ""

    def has_role_access(self, user):
        raise NotImplementedError

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.has_role_access(request.user):
            return self.handle_role_denied(request)
        return super().dispatch(request, *args, **kwargs)

    def handle_role_denied(self, request):
        if expects_json(request):
            return json_failure(self.denied_message, http_status=403)
        messages.warning(request, self.denied_message)
        return redirect(request.user.get_dashboard_url())


class AdministratorRequiredMixin(RoleRequiredMixin):
    denied_message = (
        "That page requires administrative privileges. Redirected to user dashboard."
    )

    def has_role_access(self, user):
        return user.is_administrator


class PassengerAreaMixin(RoleRequiredMixin):
    denied_message = (
        "That page is for regular users only. Redirected to admin dashboard."
    )

    def has_role_access(self, user):
        return not user.is_administrator
