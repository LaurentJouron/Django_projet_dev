from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import NotificationTracker


@admin.register(NotificationTracker)
class NotificationTrackerAdmin(admin.ModelAdmin):
    """Administration avancée pour le suivi des notifications"""

    # Configuration de la liste
    list_display = [
        "user_link",
        "activity_status",
        "last_seen_display",
        "time_since_last_seen",
        "has_pending_notifications",
    ]

    list_filter = [
        "activity_last_seen",
        ("activity_last_seen", admin.EmptyFieldListFilter),
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]

    readonly_fields = [
        "user",
        "activity_last_seen",
        "detailed_info",
        "notification_summary",
    ]

    fieldsets = (
        ("Informations utilisateur", {"fields": ("user", "detailed_info")}),
        (
            "Suivi d'activité",
            {"fields": ("activity_last_seen", "notification_summary")},
        ),
    )

    # Configuration
    date_hierarchy = "activity_last_seen"
    list_per_page = 25
    show_full_result_count = True

    # Permissions
    def has_add_permission(self, request):
        """Désactive l'ajout manuel (créé automatiquement)"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Permet la suppression seulement aux superusers"""
        return request.user.is_superuser

    # Colonnes personnalisées
    @admin.display(description="Utilisateur", ordering="user__username")
    def user_link(self, obj):
        """Lien cliquable vers l'utilisateur"""
        from django.contrib.contenttypes.models import ContentType

        # Obtenir le ContentType du modèle User utilisé
        user_content_type = ContentType.objects.get_for_model(obj.user)

        # Construire l'URL en utilisant app_label et model
        try:
            url = reverse(
                f"admin:{user_content_type.app_label}_{user_content_type.model}_change",
                args=[obj.user.id],
            )
            return format_html(
                '<a href="{}" style="font-weight: 500;">{}</a>',
                url,
                obj.user.username,
            )
        except:
            # Fallback si le reverse échoue
            return format_html(
                '<span style="font-weight: 500;">{}</span>', obj.user.username
            )

    @admin.display(description="Statut", ordering="activity_last_seen")
    def activity_status(self, obj):
        """Badge de statut avec couleur"""
        if obj.activity_last_seen is None:
            return format_html(
                '<span style="padding: 4px 8px; background-color: #6c757d; color: white; '
                'border-radius: 4px; font-size: 11px; font-weight: 600;">NOUVEAU</span>'
            )

        now = timezone.now()
        time_diff = now - obj.activity_last_seen

        if time_diff.days == 0 and time_diff.seconds < 3600:  # < 1 heure
            color = "#28a745"
            status = "ACTIF"
        elif time_diff.days == 0:  # < 24 heures
            color = "#17a2b8"
            status = "RÉCENT"
        elif time_diff.days < 7:  # < 1 semaine
            color = "#ffc107"
            status = "INACTIF"
        else:
            color = "#dc3545"
            status = "DORMANT"

        return format_html(
            '<span style="padding: 4px 8px; background-color: {}; color: white; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            status,
        )

    @admin.display(
        description="Dernière visite", ordering="activity_last_seen"
    )
    def last_seen_display(self, obj):
        """Affichage formaté de la dernière visite"""
        if obj.activity_last_seen is None:
            return format_html('<em style="color: #6c757d;">Jamais</em>')

        return format_html(
            '<span style="color: #495057;">{}</span>',
            obj.activity_last_seen.strftime("%d/%m/%Y à %H:%M"),
        )

    @admin.display(description="Il y a", ordering="activity_last_seen")
    def time_since_last_seen(self, obj):
        """Temps écoulé depuis la dernière visite"""
        if obj.activity_last_seen is None:
            return "—"

        now = timezone.now()
        time_diff = now - obj.activity_last_seen

        if time_diff.days > 0:
            if time_diff.days == 1:
                return "1 jour"
            return f"{time_diff.days} jours"

        hours = time_diff.seconds // 3600
        if hours > 0:
            if hours == 1:
                return "1 heure"
            return f"{hours} heures"

        minutes = time_diff.seconds // 60
        if minutes > 0:
            if minutes == 1:
                return "1 minute"
            return f"{minutes} minutes"

        return "À l'instant"

    @admin.display(description="Notif. en attente", boolean=True)
    def has_pending_notifications(self, obj):
        """Indique si l'utilisateur a des notifications non vues"""
        if obj.activity_last_seen is None:
            return False

        from apps.network.models import Follow
        from apps.posts.models import LikedPost, LikedComment, Comment, Repost

        return (
            Follow.objects.filter(
                following=obj.user, created_at__gt=obj.activity_last_seen
            ).exists()
            or LikedPost.objects.filter(
                post__author=obj.user, created_at__gt=obj.activity_last_seen
            )
            .exclude(user=obj.user)
            .exists()
            or LikedComment.objects.filter(
                comment__author=obj.user, created_at__gt=obj.activity_last_seen
            )
            .exclude(user=obj.user)
            .exists()
            or Comment.objects.filter(
                Q(post__author=obj.user)
                | Q(parent_comment__author=obj.user)
                | Q(parent_reply__author=obj.user),
                created_at__gt=obj.activity_last_seen,
            )
            .exclude(author=obj.user)
            .exists()
            or Repost.objects.filter(
                post__author=obj.user, created_at__gt=obj.activity_last_seen
            )
            .exclude(user=obj.user)
            .exists()
        )

    # Champs readonly personnalisés
    @admin.display(description="Informations détaillées")
    def detailed_info(self, obj):
        """Affiche des informations détaillées sur l'utilisateur"""
        user = obj.user
        info = f"""
        <div style="padding: 10px; background-color: #f8f9fa; border-radius: 4px;">
            <p style="margin: 5px 0;"><strong>Email:</strong> {user.email or '—'}</p>
            <p style="margin: 5px 0;"><strong>Nom complet:</strong> {user.get_full_name() or '—'}</p>
            <p style="margin: 5px 0;"><strong>Date d'inscription:</strong> {user.date_joined.strftime('%d/%m/%Y')}</p>
            <p style="margin: 5px 0;"><strong>Actif:</strong> {'✅ Oui' if user.is_active else '❌ Non'}</p>
        </div>
        """
        return format_html(info)

    @admin.display(description="Résumé des notifications")
    def notification_summary(self, obj):
        """Affiche un résumé des notifications de l'utilisateur"""
        if obj.activity_last_seen is None:
            return format_html("<em>Aucune activité enregistrée</em>")

        from a_network.models import Follow
        from a_posts.models import LikedPost, LikedComment, Comment, Repost

        last_seen = obj.activity_last_seen

        new_followers = Follow.objects.filter(
            following=obj.user, created_at__gt=last_seen
        ).count()

        new_likes_posts = (
            LikedPost.objects.filter(
                post__author=obj.user, created_at__gt=last_seen
            )
            .exclude(user=obj.user)
            .count()
        )

        new_likes_comments = (
            LikedComment.objects.filter(
                comment__author=obj.user, created_at__gt=last_seen
            )
            .exclude(user=obj.user)
            .count()
        )

        new_comments = (
            Comment.objects.filter(
                Q(post__author=obj.user)
                | Q(parent_comment__author=obj.user)
                | Q(parent_reply__author=obj.user),
                created_at__gt=last_seen,
            )
            .exclude(author=obj.user)
            .count()
        )

        new_reposts = (
            Repost.objects.filter(
                post__author=obj.user, created_at__gt=last_seen
            )
            .exclude(user=obj.user)
            .count()
        )

        total = (
            new_followers
            + new_likes_posts
            + new_likes_comments
            + new_comments
            + new_reposts
        )

        if total == 0:
            return format_html(
                '<span style="color: #6c757d;">Aucune nouvelle notification</span>'
            )

        summary = f"""
        <div style="padding: 10px; background-color: #e7f3ff; border-left: 4px solid #007bff; border-radius: 4px;">
            <p style="margin: 5px 0; font-weight: 600; color: #007bff;">
                📬 {total} nouvelle{'s' if total > 1 else ''} notification{'s' if total > 1 else ''}
            </p>
            <ul style="margin: 10px 0; padding-left: 20px;">
                {f'<li>👥 {new_followers} nouveau{"x" if new_followers > 1 else ""} abonné{"s" if new_followers > 1 else ""}</li>' if new_followers else ''}
                {f'<li>❤️ {new_likes_posts} like{"s" if new_likes_posts > 1 else ""} sur vos posts</li>' if new_likes_posts else ''}
                {f'<li>💙 {new_likes_comments} like{"s" if new_likes_comments > 1 else ""} sur vos commentaires</li>' if new_likes_comments else ''}
                {f'<li>💬 {new_comments} commentaire{"s" if new_comments > 1 else ""}</li>' if new_comments else ''}
                {f'<li>🔄 {new_reposts} repost{"s" if new_reposts > 1 else ""}</li>' if new_reposts else ''}
            </ul>
        </div>
        """
        return format_html(summary)

    # Actions personnalisées
    actions = ["reset_last_seen", "mark_as_seen_now"]

    @admin.action(description="🔄 Réinitialiser la dernière visite")
    def reset_last_seen(self, request, queryset):
        """Réinitialise la dernière visite à None"""
        count = queryset.update(activity_last_seen=None)
        self.message_user(
            request,
            f'{count} tracker{"s" if count > 1 else ""} réinitialisé{"s" if count > 1 else ""}.',
        )

    @admin.action(description="✅ Marquer comme vu maintenant")
    def mark_as_seen_now(self, request, queryset):
        """Met à jour la dernière visite à maintenant"""
        count = queryset.update(activity_last_seen=timezone.now())
        self.message_user(
            request, f'{count} tracker{"s" if count > 1 else ""} mis à jour.'
        )
