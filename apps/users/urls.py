from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("@<username>/", views.ProfileView.as_view(), name="profile"),
    path("login/", views.IndexView.as_view(), name="index"),
]
