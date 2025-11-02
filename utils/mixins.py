from django.db.models import Count


class PostOrderingMixin:
    ordering = "-created_at"


class PostSortingMixin(PostOrderingMixin):
    def get_sorted_posts(self, user):
        sort_order = self.request.GET.get("sort", "")
        if sort_order == "oldest":
            return user.posts.order_by("created_at")
        elif sort_order == "popular":
            return user.posts.annotate(num_likes=Count("likes")).order_by(
                "-num_likes", self.ordering
            )
        else:
            return user.posts.order_by(self.ordering)


class HTMXTemplateMixin:
    partial_template = None
    paginator_partial_template = None

    def get_template_names(self):
        request = getattr(self, "request", None)
        if request is None:
            return super().get_template_names()

        if getattr(request, "htmx", False):
            if self.request.GET.get("paginator"):
                return [self.get_paginator_partial_template()]
            return [self.get_partial_template()]

        return super().get_template_names()

    def get_partial_template(self):
        return self.partial_template or super().get_template_names()[0]

    def get_paginator_partial_template(self):
        return (
            self.paginator_partial_template or super().get_template_names()[0]
        )
