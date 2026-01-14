from django.contrib import admin
from django.utils.html import format_html
from django.utils.timesince import timesince

from .models import Conversation, ConvUser, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "participants_display",
        "last_message_preview",
        "updated_at",
    )
    list_filter = ("updated_at",)
    search_fields = ("participants__username",)
    ordering = ("-updated_at",)
    date_hierarchy = "updated_at"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("participants", "messages")

    def participants_display(self, obj):
        return ", ".join(user.username for user in obj.participants.all())

    participants_display.short_description = "Participants"

    def last_message_preview(self, obj):
        last_message = obj.messages.order_by("-created_at").first()
        if not last_message:
            return "-"
        return f"{last_message.sender}: {last_message.body[:30]}"

    last_message_preview.short_description = "Dernier message"


@admin.register(ConvUser)
class ConvUserAdmin(admin.ModelAdmin):
    list_display = (
        "conversation",
        "user",
        "unread_count",
        "last_seen_relative",
    )
    list_filter = ("unread_count",)
    search_fields = ("user__username",)
    raw_id_fields = ("conversation", "user")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("conversation", "user")

    def last_seen_relative(self, obj):
        if not obj.last_seen_at:
            return "Jamais"
        return f"Il y a {timesince(obj.last_seen_at)}"

    last_seen_relative.short_description = "Dernière vue"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "short_body",
        "has_image",
        "emoji_only",
        "created_at",
    )
    list_filter = (
        "created_at",
        "sender",
    )
    search_fields = (
        "body",
        "sender__username",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    raw_id_fields = ("conversation", "sender")
    readonly_fields = ("created_at",)

    def short_body(self, obj):
        return obj.body[:50]

    short_body.short_description = "Message"

    def has_image(self, obj):
        if obj.image:
            return format_html("📷")
        return "—"

    has_image.short_description = "Image"

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
