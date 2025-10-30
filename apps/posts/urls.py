from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("explore/", views.ExploreView.as_view(), name="explore"),
    path("upload/", views.UploadView.as_view(), name="upload"),
    path("post/<uuid:pk>/", views.PostPageView.as_view(), name="post_page"),
    path("post/", views.PostPageView.as_view()),
]
