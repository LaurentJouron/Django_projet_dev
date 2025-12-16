from django.db import models
from django.conf import settings


class Visit(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits",
        verbose_name="Utilisateur",
    )
    path = models.TextField(blank=True, null=True, verbose_name="Chemin")
    timestamp = models.DateTimeField(
        auto_now_add=True, verbose_name="Date et heure"
    )
    is_authenticated = models.BooleanField(
        default=False, verbose_name="Connecté"
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Visite"
        verbose_name_plural = "Visites"

    def __str__(self):
        user_info = self.user.username if self.user else "Anonyme"
        return f"{user_info} - {self.path} - {self.timestamp}"
