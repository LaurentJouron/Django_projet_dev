from django.urls import path

from .views import (
    ProfileView,
    IndexView,
    VerificationCodeView,
    ProfileEditView,
    SettingsView,
    DeleteAccountView,
)

app_name = "users"

urlpatterns = [
    path("@<username>/", ProfileView.as_view(), name="profile"),
    path("login/", IndexView.as_view(), name="index"),
    path(
        "verification_code/",
        VerificationCodeView.as_view(),
        name="verification_code",
    ),
    path("profile/edit/", ProfileEditView.as_view(), name="profile_edit"),
    path("settings/", SettingsView.as_view(), name="settings"),
    path(
        "delete_account/", DeleteAccountView.as_view(), name="delete_account"
    ),
]
