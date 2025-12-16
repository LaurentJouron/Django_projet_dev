from django.contrib import admin
from .models import (
    Post,
    LikedPost,
    BookmarkedPost,
    Comment,
    LikedComment,
    Repost,
    Tag,
)

# ==========================
# 🔹 Inlines
# ==========================


class CommentInline(admin.TabularInline):
    """Display the comments directly in the page of a post"""

    model = Comment
    extra = 0
    readonly_fields = ("author", "body", "created_at")
    fields = ("author", "body", "created_at")
    show_change_link = True


# ==========================
# 🔹 Post
# ==========================


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Configuration of the administration for the Posts"""

    list_display = (
        "uuid",
        "author",
        "short_body",
        "display_tags",
        "created_at",
        "like_count",
        "bookmark_count",
        "comment_count",
    )
    list_filter = ("author", "tags", "created_at")
    search_fields = ("author__username", "body", "tags__name")
    ordering = ("-created_at",)
    readonly_fields = ("uuid", "created_at")
    inlines = [CommentInline]

    @admin.display(description="Body")
    def short_body(self, obj):
        return (
            (obj.body[:50] + "...")
            if obj.body and len(obj.body) > 50
            else obj.body
        )

    @admin.display(description="Tags")
    def display_tags(self, obj):
        """Display tags as comma-separated list"""
        tags = obj.tags.all()
        if tags:
            return ", ".join([f"#{tag.name}" for tag in tags[:5]])
        return "-"

    @admin.display(description="Likes")
    def like_count(self, obj):
        return obj.likes.count()

    @admin.display(description="Bookmarks")
    def bookmark_count(self, obj):
        return obj.bookmarks.count()

    @admin.display(description="Comments")
    def comment_count(self, obj):
        return obj.comments.count()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Optimization of queries to reduce SQL hits
        return qs.select_related("author").prefetch_related(
            "tags", "likes", "bookmarks", "comments"
        )


# ==========================
# 🔹 Comment
# ==========================


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Display and management of comments"""

    list_display = (
        "uuid",
        "author",
        "post",
        "short_body",
        "is_reply",
        "created_at",
    )
    list_filter = ("author", "created_at")
    search_fields = ("author__username", "body", "post__body")
    ordering = ("-created_at",)
    readonly_fields = ("uuid", "created_at")

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:60] + "...") if len(obj.body) > 60 else obj.body

    @admin.display(boolean=True, description="Is reply")
    def is_reply(self, obj):
        return bool(obj.parent_comment or obj.parent_reply)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("author", "post")


# ==========================
# 🔹 Users relations / post
# ==========================


class BaseUserPostRelationAdmin(admin.ModelAdmin):
    """Base class for LikedPost, BookmarkedPost and Repost models"""

    list_display = ("user", "post", "created_at")
    list_filter = ("user", "post", "created_at")
    search_fields = ("user__username", "post__body")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "post")


@admin.register(LikedPost)
class LikedPostAdmin(BaseUserPostRelationAdmin):
    """Display of liked posts"""

    pass


@admin.register(BookmarkedPost)
class BookmarkedPostAdmin(BaseUserPostRelationAdmin):
    """Display of saved posts"""

    pass


@admin.register(Repost)
class RepostAdmin(BaseUserPostRelationAdmin):
    """Display of reposts"""

    pass


# ==========================
# 🔹 Liked Comment
# ==========================


@admin.register(LikedComment)
class LikedCommentAdmin(admin.ModelAdmin):
    """Display of likes on comments"""

    list_display = ("user", "comment", "created_at")
    list_filter = ("user", "comment", "created_at")
    search_fields = ("user__username", "comment__body")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "comment")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "count")
