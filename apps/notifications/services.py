from .models import Notification


def notify(user, kind, title, message):
    return Notification.objects.create(
        user=user, kind=kind, title=title, message=message
    )
