from django.urls import path
from .views import NotificationsView, NewNotificationsView

app_name = "notifications"

urlpatterns = [
    path("", NotificationsView.as_view(), name="notifications"),
    path(
        "new_notifications/",
        NewNotificationsView.as_view(),
        name="new_notifications",
    ),
]
