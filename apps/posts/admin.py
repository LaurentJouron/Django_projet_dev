from django.contrib import admin
from .models import Post, LikedPost, BookmarkedPost


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("uuid", "author", "body", "tags", "created_at")
    list_filter = ("author", "tags", "created_at")
    search_fields = ("author__username", "body", "tags")
    ordering = ("-created_at",)


@admin.register(LikedPost)
class LikedPostAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "post")
    list_filter = ("user", "post")
    search_fields = ("user__username", "post__body")
    ordering = ("-created_at",)


@admin.register(BookmarkedPost)
class BookmarkedPostAdmin(admin.ModelAdmin):
    list_display = ("user", "post")
    list_filter = ("user", "post")
    search_fields = ("user__username", "post__body")
    ordering = ("-created_at",)
