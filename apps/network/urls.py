from django.urls import path
from .views import FollowView, FollowingView, FriendsView

app_name = "network"

urlpatterns = [
    path("", FollowingView.as_view(), name="following"),
    path("user/<str:username>/", FollowView.as_view(), name="follow"),
    path("friends/", FriendsView.as_view(), name="friends"),
]
