from django.db.models import Count


class PostOrderingMixin:
    """
    Mixin providing default ordering for post queries.

    Defines the default ordering field for posts, which can be
    overridden in child classes.
    """

    ordering = "-created_at"


class PostSortingMixin(PostOrderingMixin):
    """
    Mixin providing post sorting functionality.

    Extends PostOrderingMixin to provide dynamic sorting based on
    query parameters (newest, oldest, popular).
    """

    # Sort parameter values
    SORT_OLDEST = "oldest"
    SORT_POPULAR = "popular"
    SORT_PARAM = "sort"

    def get_sorted_posts(self, user):
        """
        Get user's posts sorted according to query parameters.

        Args:
            user: User instance whose posts to retrieve

        Returns:
            QuerySet: Sorted posts queryset
        """
        sort_order = self._get_sort_order()

        if sort_order == self.SORT_OLDEST:
            return self._get_oldest_posts(user)
        elif sort_order == self.SORT_POPULAR:
            return self._get_popular_posts(user)
        else:
            return self._get_default_posts(user)

    def _get_sort_order(self):
        """
        Get the sort order from query parameters.

        Returns:
            str: Sort order parameter value
        """
        return self.request.GET.get(self.SORT_PARAM, "")

    def _get_oldest_posts(self, user):
        """
        Get posts ordered by oldest first.

        Args:
            user: User instance

        Returns:
            QuerySet: Posts ordered by created_at ascending
        """
        return user.posts.order_by("created_at")

    def _get_popular_posts(self, user):
        """
        Get posts ordered by popularity (number of likes).

        Args:
            user: User instance

        Returns:
            QuerySet: Posts with likes, ordered by like count descending
        """
        return (
            user.posts.annotate(num_likes=Count("likes"))
            .filter(num_likes__gt=0)
            .order_by("-num_likes", self.ordering)
        )

    def _get_default_posts(self, user):
        """
        Get posts with default ordering.

        Args:
            user: User instance

        Returns:
            QuerySet: Posts ordered by self.ordering
        """
        return user.posts.order_by(self.ordering)


class HTMXTemplateMixin:
    """
    Mixin for handling HTMX partial template rendering.

    Automatically selects the appropriate template based on whether
    the request is an HTMX request and whether pagination is active.

    Compatible with both View and TemplateView classes.
    """

    partial_template = None
    paginator_partial_template = None

    # Query parameter names
    PAGINATOR_PARAM = "paginator"

    def get_template_names(self):
        """
        Get the appropriate template name(s) based on request type.

        Returns:
            list: List of template names to use
        """
        request = self._get_request()

        if request is None:
            return self._get_default_template_names()

        if self._is_htmx_request(request):
            return [self._get_htmx_template()]

        return self._get_default_template_names()

    def get_partial_template(self):
        """
        Get the partial template name.

        Returns:
            str: Partial template name or default template
        """
        if self.partial_template:
            return self.partial_template
        return self._get_default_template_names()[0]

    def get_paginator_partial_template(self):
        """
        Get the paginator partial template name.

        Returns:
            str: Paginator partial template name or default template
        """
        if self.paginator_partial_template:
            return self.paginator_partial_template
        return self._get_default_template_names()[0]

    def is_htmx_request(self):
        """
        Check if the current request is an HTMX request.

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return self._is_htmx_request(self.request)

    def _get_request(self):
        """
        Get the request object from the view instance.

        Returns:
            HttpRequest or None: Request object if available
        """
        return getattr(self, "request", None)

    def _is_htmx_request(self, request):
        """
        Check if a request is an HTMX request.

        Args:
            request: HttpRequest object

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(request, "htmx", False)

    def _get_htmx_template(self):
        """
        Get the appropriate HTMX template based on pagination.

        Returns:
            str: Template name for HTMX response
        """
        if self._is_paginator_request():
            return self.get_paginator_partial_template()
        return self.get_partial_template()

    def _is_paginator_request(self):
        """
        Check if this is a paginator request.

        Returns:
            bool: True if paginator parameter exists
        """
        return bool(self.request.GET.get(self.PAGINATOR_PARAM))

    def _get_default_template_names(self):
        """
        Get default template names.

        Checks if parent class has get_template_names (TemplateView)
        or falls back to template_name attribute (View).

        Returns:
            list: List of template names
        """
        # Try to call parent's get_template_names if it exists (TemplateView)
        if hasattr(super(), "get_template_names"):
            return super().get_template_names()

        # Fallback for View class - use template_name attribute
        if hasattr(self, "template_name") and self.template_name:
            return [self.template_name]

        # Last resort
        raise AttributeError(
            f"{self.__class__.__name__} must define 'template_name' attribute "
            "or inherit from TemplateView"
        )
