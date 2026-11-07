from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.TravelChatView.as_view(), name="chat"),
    path("api/", views.TravelChatApiView.as_view(), name="chat-api"),
]
