from django.urls import path

from .views import (
    HomeView,
    ExploreView,
    UploadView,
    PostPageView,
)

app_name = "posts"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
    path("upload/", UploadView.as_view(), name="upload"),
    path("post/<uuid:pk>/", PostPageView.as_view(), name="post_page"),
    path("post/", PostPageView.as_view()),
]
