from django.views.generic import TemplateView, FormView
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from utils.mixins import PostOrderingMixin, HTMXTemplateMixin
from .forms import PostForm, PostEditForm
from .models import Post


class HomeView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, TemplateView
):
    template_name = "posts/home.html"
    partial_template = "posts/partials/_home.html"
    paginator_partial_template = "posts/partials/_posts.html"

    @property
    def page_title(self):
        return "Home"

    @property
    def paginate_by(self):
        return 1

    def get_page_number(self):
        page_number = self.request.GET.get("page_number", 1)
        try:
            return int(page_number)
        except (TypeError, ValueError):
            return 1

    def get_paginated_posts(self):
        posts = Post.objects.order_by(self.ordering)
        paginator = Paginator(posts, self.paginate_by)
        page_number = self.get_page_number()
        posts_page = paginator.get_page(page_number)
        return {
            "posts": posts_page,
            "next_page": (
                posts_page.next_page_number()
                if posts_page.has_next()
                else None
            ),
            "page_start_index": (posts_page.number - 1) * paginator.per_page,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pagination_data = self.get_paginated_posts()
        context.update(
            {
                "page": self.page_title,
                **pagination_data,
            }
        )
        return context


class ExploreView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, TemplateView
):
    template_name = "posts/explore.html"
    partial_template = "posts/partials/_explore.html"

    @property
    def page_title(self):
        return "Explore"

    def get_posts(self):
        return Post.objects.order_by(self.ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page": self.page_title,
                "posts": self.get_posts(),
            }
        )
        return context


class UploadView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, FormView
):
    template_name = "posts/upload.html"
    partial_template = "posts/partials/_upload.html"
    form_class = PostForm
    success_url = reverse_lazy("posts:home")
    login_url = reverse_lazy("login")

    @property
    def page_title(self):
        return "Upload"

    def get_posts(self):
        return Post.objects.order_by(self.ordering)

    def form_valid(self, form):
        post = form.save(commit=False)
        post.author = self.request.user
        post.save()

        if self.request.htmx:
            context = {"posts": self.get_posts()}
            return self.render_to_response(
                context=context, template_name="posts/partials/_home.html"
            )

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = self.page_title
        return context


class PostPageView(PostOrderingMixin, HTMXTemplateMixin, TemplateView):
    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_postpage.html"
    redirect_url = "posts:home"

    @property
    def page_title(self):
        return "Post Page"

    def get(self, request, *args, **kwargs):
        if not self.kwargs.get("pk"):
            return redirect(self.redirect_url)

        post = get_object_or_404(Post, uuid=self.kwargs["pk"])

        if post.author:
            author_posts = list(
                Post.objects.filter(author=post.author).order_by(self.ordering)
            )
            index = author_posts.index(post)
            prev_post = author_posts[index - 1] if index > 0 else None
            next_post = (
                author_posts[index + 1]
                if index < len(author_posts) - 1
                else None
            )
        else:
            author_posts = [post]
            prev_post = next_post = None

        context = self.get_context_data(
            post=post,
            author_posts=author_posts,
            prev_post=prev_post,
            next_post=next_post,
        )

        # ✅ utilisation explicite de TemplateResponse pour éviter l’erreur
        if request.htmx:
            return TemplateResponse(request, self.partial_template, context)
        return TemplateResponse(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page": self.page_title,
                **kwargs,
            }
        )
        return context


class PostEditView(LoginRequiredMixin, HTMXTemplateMixin, TemplateView):
    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_post_edit.html"
    redirect_home_url_name = "posts:home"
    redirect_post_url_name = "posts:post_page"

    def dispatch(self, request, *args, **kwargs):
        self.post_obj = get_object_or_404(Post, uuid=self.kwargs["pk"])
        if self.post_obj.author != request.user:
            return redirect(self.redirect_home_url_name)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form") or PostEditForm(instance=self.post_obj)
        context.update({"form": form, "post": self.post_obj})
        return context

    def get(self, request, *args, **kwargs):
        if request.GET.get("delete"):
            self.post_obj.delete()
            return redirect("users:profile", request.user)

        context = self.get_context_data()
        if request.htmx:
            return self.render_to_response(context)
        return redirect(self.redirect_post_url_name, self.post_obj.uuid)

    def post(self, request, *args, **kwargs):
        form = PostEditForm(request.POST, instance=self.post_obj)
        if form.is_valid():
            form.save()
            return redirect(self.redirect_post_url_name, self.post_obj.uuid)

        context = self.get_context_data(form=form)
        if request.htmx:
            return self.render_to_response(context)
        return redirect(self.redirect_post_url_name, self.post_obj.uuid)
