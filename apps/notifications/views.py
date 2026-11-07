from django.views import View

from apps.core.http import json_failure, json_success

from .models import Notification


class MarkNotificationReadView(View):
    http_method_names = ["post"]

    def post(self, request, pk):
        notification = Notification.objects.filter(pk=pk, user=request.user).first()
        if notification is None:
            return json_failure("Notification not found.", http_status=404)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return json_success(title=notification.title, full_message=notification.message)
