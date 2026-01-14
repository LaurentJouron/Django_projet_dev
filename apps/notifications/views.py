from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from itertools import chain
from operator import attrgetter
from django.db.models import Q
from django.utils import timezone

from apps.network.models import Follow
from apps.posts.models import LikedPost, LikedComment, Comment, Repost
from apps.messages.models import Message, ConvUser
from .models import NotificationTracker


class NotificationsView(LoginRequiredMixin, View):
    template_name = "notifications/notifications.html"

    def get(self, request):
        tracker, created = NotificationTracker.objects.get_or_create(
            user=request.user
        )

        # Message de bienvenue pour les nouveaux utilisateurs
        if tracker.activity_last_seen is None:
            welcome_message = "👋 Bienvenue ! C’est ici que vous verrez les likes, commentaires et suiveurs."
        else:
            welcome_message = None

        # Mise à jour du timestamp de dernière visite
        tracker.activity_last_seen = timezone.now()
        tracker.save(update_fields=["activity_last_seen"])

        # Récupération des différents types de notifications
        followers = (
            Follow.objects.filter(following=request.user)
            .select_related("follower")
            .order_by("-created_at")[:10]
        )

        liked_posts = (
            LikedPost.objects.filter(post__author=request.user)
            .exclude(user=request.user)
            .select_related("user", "post")
            .order_by("-created_at")[:10]
        )

        liked_comments = (
            LikedComment.objects.filter(comment__author=request.user)
            .exclude(user=request.user)
            .select_related("user", "comment", "comment__post")
            .order_by("-created_at")[:10]
        )

        comments = (
            Comment.objects.filter(
                post__author=request.user, parent_comment__isnull=True
            )
            .exclude(author=request.user)
            .select_related("author", "post")
            .order_by("-created_at")[:10]
        )

        replies = (
            Comment.objects.filter(
                Q(parent_comment__author=request.user)
                | Q(parent_reply__author=request.user)
            )
            .exclude(author=request.user)
            .select_related("author", "post", "parent_comment", "parent_reply")
            .order_by("-created_at")[:10]
        )

        reposts = (
            Repost.objects.filter(post__author=request.user)
            .exclude(user=request.user)
            .select_related("user", "post")
            .order_by("-created_at")[:10]
        )

        # Combinaison et tri de toutes les notifications
        combined_notifications = sorted(
            chain(
                followers,
                liked_posts,
                liked_comments,
                comments,
                replies,
                reposts,
            ),
            key=attrgetter("created_at"),
            reverse=True,
        )
        notifications = combined_notifications[:20]

        context = {
            "notifications": notifications,
            "welcome_message": welcome_message,
        }

        return render(request, self.template_name, context=context)


class NewNotificationsView(LoginRequiredMixin, View):
    template_name = "notifications/notify_dot.html"

    def get(self, request):
        tracker, created = NotificationTracker.objects.get_or_create(
            user=request.user
        )
        last_seen = tracker.activity_last_seen
        has_new_notifications = True

        if last_seen:
            has_new_notifications = (
                Follow.objects.filter(
                    following=request.user, created_at__gt=last_seen
                ).exists()
                or LikedPost.objects.filter(
                    post__author=request.user, created_at__gt=last_seen
                )
                .exclude(user=request.user)
                .exists()
                or LikedComment.objects.filter(
                    comment__author=request.user, created_at__gt=last_seen
                )
                .exclude(user=request.user)
                .exists()
                or Comment.objects.filter(
                    Q(post__author=request.user)
                    | Q(parent_comment__author=request.user)
                    | Q(parent_reply__author=request.user),
                    created_at__gt=last_seen,
                )
                .exclude(author=request.user)
                .exists()
                or Repost.objects.filter(
                    post__author=request.user, created_at__gt=last_seen
                )
                .exclude(user=request.user)
                .exists()
            )

        has_new_messages = ConvUser.objects.filter(
            user=request.user, unread_count__gt=0
        ).exists()

        context = {
            "has_new_notifications": has_new_notifications,
            "has_new_messages": has_new_messages,
        }

        return render(request, self.template_name, context)
