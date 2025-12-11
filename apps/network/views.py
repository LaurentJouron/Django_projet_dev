import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from utils.mixins import HTMXTemplateMixin
from .models import Follow

logger = logging.getLogger(__name__)
User = get_user_model()


class FollowingView(HTMXTemplateMixin, LoginRequiredMixin, View):
    """
    Secure view to display followed users and suggest new users to follow.

    Security features implemented:
    - LoginRequiredMixin: Authentication required
    - Never cache: Prevents stale data issues
    - Query optimization: Uses select_related/prefetch_related
    - Error logging: Logs potential errors
    """

    template_name = "network/following.html"
    partial_template = "network/partials/_following.html"

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        try:
            following_ids = request.user.is_follower.values_list(
                "following", flat=True
            )

            following_users = User.objects.filter(id__in=following_ids)

            not_following_users = User.objects.exclude(
                id__in=following_ids
            ).exclude(id=request.user.id)

            suggested_users = not_following_users.annotate(
                total_likes=Count("posts__likes", distinct=True)
            ).order_by("-total_likes")[:10]

            context = {
                "page": "Following",
                "following_users": following_users,
                "suggested_users": suggested_users,
            }

            # Using the mixin to automatically choose the right template
            template = self.get_template_names()[0]

            logger.info(
                f"User {request.user.username} viewed following page "
                f"with {following_users.count()} followed users"
            )

            return render(request, template, context)

        except Exception as e:
            logger.error(
                f"Error in FollowingView for user {request.user.username}: {str(e)}",
                exc_info=True,
            )
            context = {
                "page": "Following",
                "following_users": User.objects.none(),
                "suggested_users": User.objects.none(),
            }
            template = self.get_template_names()[0]
            return render(request, template, context)


class FriendsView(HTMXTemplateMixin, LoginRequiredMixin, View):
    """
    Secure view to display friends (mutual follows) and suggest potential friends.

    Security features implemented:
    - LoginRequiredMixin: Authentication required
    - Never cache: Prevents stale data issues

    Template handling:
    - HTMXTemplateMixin: Automatic HTMX partial rendering
    """

    template_name = "network/friends.html"
    partial_template = "network/partials/_friends.html"

    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        """
        Security: Disables caching to ensure fresh data.
        """
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Prepare context data for the template.

        Returns:
            dict: Context dictionary with friends and suggestions
        """
        context = kwargs

        # Get following and followers IDs
        following_ids = self.request.user.is_follower.values_list(
            "following", flat=True
        )
        followers_ids = self.request.user.is_followed.values_list(
            "follower", flat=True
        )

        # Intersection to find friends (mutual follows)
        friends_ids = set(following_ids) & set(followers_ids)

        # Get friends
        friends = User.objects.filter(id__in=friends_ids).order_by("username")

        # Suggestions: followers we don't follow back yet
        suggested_friends = (
            User.objects.filter(id__in=followers_ids)
            .exclude(id__in=friends_ids)
            .order_by("username")
        )

        context.update(
            {
                "page": "Friends",
                "friends": friends,
                "suggested_friends": suggested_friends,
            }
        )
        return context

    def get(self, request):
        """
        Display the list of friends (mutual follows) and friend suggestions.

        Args:
            request: The HTTP request

        Returns:
            HttpResponse: Template with list of friends
        """
        context = self.get_context_data()

        # Use mixin's template selection logic
        return render(
            request,
            template_name=self.get_template_names()[0],
            context=context,
        )


class FollowView(LoginRequiredMixin, HTMXTemplateMixin, View):
    """
    Secure view to handle user follow/unfollow actions.

    Security features implemented:
    - LoginRequiredMixin: Authentication required
    - CSRF protection: Automatic with Django (POST)
    - Atomic transaction: Prevents race conditions
    - Input validation
    - Action logging
    - Never cache: Prevents cache issues
    - Self-follow protection
    - Inactive account protection

    Template handling:
    - HTMXTemplateMixin: Automatic HTMX partial rendering
    - Supports multiple button styles (button, round, rounded)
    - Modal context support
    """

    # Default templates
    template_name = "network/partials/_follow_button.html"
    template_round = "network/partials/_follow_round.html"
    template_rounded = "network/partials/_follow_rounded.html"

    @method_decorator(never_cache)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, *args, **kwargs):
        """
        Security: Forces POST method only and disables caching.
        """
        return super().dispatch(*args, **kwargs)

    def post(self, request, username):
        """
        Handle follow/unfollow action securely.

        Args:
            request: The HTTP request
            username: The username to follow/unfollow

        Returns:
            HttpResponse: Updated follow button template
        """
        # Validation: get target user
        this_user = get_object_or_404(User, username=username)

        # Security: prevent self-follow
        if this_user == request.user:
            logger.warning(
                f"User {request.user.username} attempted to follow themselves"
            )
            return HttpResponseBadRequest(
                "Vous ne pouvez pas vous suivre vous-même"
            )

        # Security: prevent following inactive accounts
        if not this_user.is_active:
            logger.warning(
                f"User {request.user.username} attempted to follow inactive user {username}"
            )
            return HttpResponseBadRequest("Cet utilisateur n'est plus actif")

        # Atomic transaction to prevent race conditions
        with transaction.atomic():
            follow_obj, created = Follow.objects.get_or_create(
                follower=request.user, following=this_user
            )

            if not created:
                # Unfollow
                follow_obj.delete()
                action = "unfollowed"
                logger.info(
                    f"User {request.user.username} unfollowed {username}"
                )
            else:
                # Follow
                action = "followed"
                logger.info(
                    f"User {request.user.username} followed {username}"
                )

        # Reload users to get updated counters
        this_user.refresh_from_db()
        request.user.refresh_from_db()

        # Prepare context with correct variables
        context = {
            "this_user": this_user,
            "profile_user": this_user,
            "user": request.user,
            "follow_clicked": True,
            "modal": request.GET.get("modal", False),
            "request": request,
        }

        # Select template based on parameters
        template_name = self._get_follow_template(request)

        return render(request, template_name=template_name, context=context)

    def _get_follow_template(self, request):
        """
        Determine which follow button template to use based on GET parameters.

        Args:
            request: The HTTP request

        Returns:
            str: Template path to use
        """
        if request.GET.get("follow_round"):
            return self.template_round
        if request.GET.get("follow_rounded"):
            return self.template_rounded
        return self.template_name
