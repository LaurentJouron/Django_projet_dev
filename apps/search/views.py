from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.views.generic import TemplateView

from utils.mixins import HTMXTemplateMixin

User = get_user_model()


class SearchView(HTMXTemplateMixin, TemplateView):
    """
    View for searching users.

    Allows searching users by username, name or bio.
    Supports HTMX requests for partial rendering.
    """

    template_name = "search/search_page.html"
    partial_template = "search/partials/_search_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")

        users = User.objects.none()

        if query and len(query) >= 2:
            users = User.objects.filter(
                Q(username__icontains=query)
                | Q(name__icontains=query)
                | Q(bio__icontains=query)
            ).order_by("username")

        context["users"] = users
        return context


class SearchSuggestionsView(TemplateView):
    """
    View for search suggestions.

    Returns the top 5 most followed users matching the query.
    Intended only for HTMX requests.
    """

    template_name = "search/partials/_search_suggestions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")

        user_suggestions = User.objects.none()

        if query and len(query) >= 2:
            user_suggestions = (
                User.objects.filter(
                    Q(username__icontains=query)
                    | Q(name__icontains=query)
                    | Q(bio__icontains=query)
                )
                .annotate(followers_count=Count("is_followed", distinct=True))
                .order_by("-followers_count")[:5]
            )

        context["user_suggestions"] = user_suggestions
        return context
