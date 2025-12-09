from django.urls import path
from .views import FollowView

app_name = "network"

urlpatterns = [
    path("user/<str:username>/", FollowView.as_view(), name="follow")
]
