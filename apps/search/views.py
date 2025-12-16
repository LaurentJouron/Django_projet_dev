from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.views.generic import TemplateView

from utils.mixins import HTMXTemplateMixin
from apps.posts.models import Post, Tag


User = get_user_model()


class SearchView(HTMXTemplateMixin, TemplateView):
    """
    View for searching users and posts.

    Allows searching posts by body content or tags.
    Displays the authors of the found posts.
    Supports HTMX requests for partial rendering.
    """

    template_name = "search/search_page.html"
    partial_template = "search/partials/_search_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q")

        users = User.objects.none()
        posts = Post.objects.none()

        if query and len(query) >= 2:
            # Chercher les posts correspondant à la recherche
            posts = (
                Post.objects.filter(
                    Q(body__icontains=query) | Q(tags__name__icontains=query)
                )
                .select_related("author")  # Optimisation
                .distinct()
                .order_by("-created_at")
            )

            # Récupérer les auteurs des posts trouvés (sans doublons)
            if posts.exists():
                author_ids = posts.values_list(
                    "author_id", flat=True
                ).distinct()
                users = User.objects.filter(id__in=author_ids).order_by(
                    "username"
                )

        context["users"] = users
        context["posts"] = posts

        return context


class SearchSuggestionsView(TemplateView):
    """
    View for search suggestions.

    Returns the top 5 most followed users, top 5 tags, and top 5 posts matching the query.
    Supports hashtag suggestions when uploading content.
    Intended only for HTMX requests.
    """

    template_name = "search/partials/_search_suggestions.html"

    def get_template_names(self):
        """
        Get the appropriate template based on request type.

        Returns hashtag suggestions template if tags parameter is present,
        otherwise returns default search suggestions template.
        """
        hashtags_upload = self.request.GET.get("tags")
        if hashtags_upload:
            return ["search/partials/_hashtag_suggestions.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q")

        hashtags_upload = self.request.GET.get("tags")
        if hashtags_upload:
            if hashtags_upload.endswith(" "):
                query = ""
            else:
                query = hashtags_upload.split()[-1].lstrip("#")

        user_suggestions = User.objects.none()
        tag_suggestions = Tag.objects.none()

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

            tag_suggestions = Tag.objects.filter(name__istartswith=query)[:5]

        context["user_suggestions"] = user_suggestions
        context["tag_suggestions"] = tag_suggestions

        return context
