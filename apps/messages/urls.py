from django.urls import path
from .views import (
    MessagesView,
    ConversationsView,
    ChatView,
    SendMessageView,
    DeleteMessageView,
)

app_name = "messages"

urlpatterns = [
    path("", MessagesView.as_view(), name="messages"),
    path("conversations/", ConversationsView.as_view(), name="conversations"),
    path("chat/<int:receiver_id>/", ChatView.as_view(), name="chat"),
    path(
        "send_message/<int:receiver_id>/",
        SendMessageView.as_view(),
        name="send_message",
    ),
    path(
        "delete_message/<int:message_id>/",
        DeleteMessageView.as_view(),
        name="delete_message",
    ),
]
