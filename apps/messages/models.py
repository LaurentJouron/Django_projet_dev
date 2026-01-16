from django.db import models
from django.conf import settings


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConvUser",
        related_name="conversations",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation #{self.id}"


class ConvUser(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    unread_count = models.IntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    is_live = models.BooleanField(default=False)

    class Meta:
        unique_together = ("conversation", "user")

    def __str__(self):
        return f"{self.user.username} in Conv #{self.conversation.id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"

    @property
    def emoji_only(self):
        if not self.body:
            return False
        message = self.body.strip()
        for character in message:
            if character.isalnum():
                return False
        return True
