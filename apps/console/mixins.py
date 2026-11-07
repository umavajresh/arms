from django.contrib import messages
from django.views import View
from django.views.generic import CreateView, UpdateView

from apps.core.http import format_form_errors, json_failure, json_success
from apps.core.mixins import AdministratorRequiredMixin, PageMixin


class ConsoleMixin(AdministratorRequiredMixin, PageMixin):
    pass


class ModalFormMixin(ConsoleMixin):
    created_message = ""
    updated_message = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_action"] = self.request.path
        return context

    def form_valid(self, form):
        is_new = form.instance.pk is None
        self.object = form.save()
        message = self.created_message if is_new else self.updated_message
        messages.success(self.request, message)
        return json_success(message)

    def form_invalid(self, form):
        return json_failure(format_form_errors(form))


class ModalCreateView(ModalFormMixin, CreateView):
    pass


class ModalUpdateView(ModalFormMixin, UpdateView):
    pass


class ArchiveView(ConsoleMixin, View):
    http_method_names = ["post"]
    model = None
    label = ""

    def post(self, request, pk):
        archived = self.model.objects.filter(pk=pk, is_archived=False).update(
            is_archived=True
        )
        if not archived:
            return json_failure("%s not found." % self.label, http_status=404)
        message = "%s has been archived successfully." % self.label
        messages.success(request, message)
        return json_success(message)
