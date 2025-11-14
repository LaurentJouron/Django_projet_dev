from django.urls import path

from .views import (
    HomeView,
    ExploreView,
    UploadView,
    PostPageView,
    PostEditView,
    PostLikeView,
    BookmarkPostView,
    CommentView,
    CommentDeleteView,
    LikeCommentView,
    SharePostView,
)

app_name = "posts"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
    path("upload/", UploadView.as_view(), name="upload"),
    path("post/<uuid:pk>/", PostPageView.as_view(), name="post_page"),
    path("post/", PostPageView.as_view()),
    path("post/<uuid:pk>/edit/", PostEditView.as_view(), name="post_edit"),
    path("like/<uuid:pk>/", PostLikeView.as_view(), name="post_like"),
    path(
        "bookmark/<uuid:pk>/", BookmarkPostView.as_view(), name="bookmark_post"
    ),
    path("comment/<uuid:pk>/", CommentView.as_view(), name="comment"),
    path(
        "comment/<uuid:pk>/delete/",
        CommentDeleteView.as_view(),
        name="comment_delete",
    ),
    path(
        "like-comment/<uuid:pk>/",
        LikeCommentView.as_view(),
        name="like_comment",
    ),
    path("share/<uuid:pk>/", SharePostView.as_view(), name="share_post"),
]
