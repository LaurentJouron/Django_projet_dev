from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from apps.constants.mixins import PostSortingMixin, HTMXTemplateMixin

User = get_user_model()


class IndexView(TemplateView):
    template_name = "users/index.html"

    @property
    def page_title(self):
        return "Index"


class ProfileView(
    LoginRequiredMixin, PostSortingMixin, HTMXTemplateMixin, TemplateView
):
    template_name = "users/profile.html"
    partial_template = "users/partials/_profile.html"
    posts_partial_template = "users/partials/_profile_posts.html"

    @property
    def page_title(self):
        return "Profile"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        username = self.kwargs.get("username")
        profile_user = get_object_or_404(User, username=username)
        profile_posts = self.get_sorted_posts(profile_user)

        context.update(
            {
                "page": self.page_title,
                "profile_user": profile_user,
                "profile_posts": profile_posts,
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.GET.get("sort"):
            return self.render_to_response(
                context, self.posts_partial_template
            )
        if request.htmx:
            return self.render_to_response(context, self.partial_template)
        return self.render_to_response(context)

    def render_to_response(self, context, template_name=None):
        if template_name is None:
            template_name = self.template_name
        return render(self.request, template_name, context)
