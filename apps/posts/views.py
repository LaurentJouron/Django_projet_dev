from django.views import View
from django.views.generic import TemplateView, FormView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from utils.mixins import PostOrderingMixin, HTMXTemplateMixin
from django.db.models import Count
from .forms import PostForm, PostEditForm
from .models import Post


class HomeView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, TemplateView
):
    """
    Home view displaying paginated posts.

    Displays a feed of posts with pagination support and HTMX
    partial rendering for infinite scroll functionality.
    """

    template_name = "posts/home.html"
    partial_template = "posts/partials/_home.html"
    paginator_partial_template = "posts/partials/_posts.html"

    # Pagination configuration
    PAGINATE_BY = 1
    DEFAULT_PAGE_NUMBER = 1

    # Page configuration
    PAGE_TITLE = "Home"

    def get_context_data(self, **kwargs):
        """
        Add posts and pagination data to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with posts and pagination info
        """
        context = super().get_context_data(**kwargs)
        pagination_data = self._get_paginated_posts()

        context.update(
            {
                "page": self.PAGE_TITLE,
                "partial": self._is_htmx_request(),
                **pagination_data,
            }
        )

        return context

    def _is_htmx_request(self):
        """
        Check if the current request is an HTMX request.

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(self.request, "htmx", False)

    def _get_page_number(self):
        """
        Get the requested page number from query parameters.

        Returns:
            int: Page number (defaults to 1 if invalid)
        """
        page_number = self.request.GET.get(
            "page_number", self.DEFAULT_PAGE_NUMBER
        )

        try:
            return int(page_number)
        except (TypeError, ValueError):
            return self.DEFAULT_PAGE_NUMBER

    def _get_paginated_posts(self):
        """
        Get paginated posts with pagination metadata.

        Returns:
            dict: Dictionary containing posts, next_page, and page_start_index
        """
        posts = self._get_posts_queryset()
        paginator = Paginator(posts, self.PAGINATE_BY)
        page_number = self._get_page_number()
        posts_page = paginator.get_page(page_number)

        return {
            "posts": posts_page,
            "next_page": self._get_next_page_number(posts_page),
            "page_start_index": self._calculate_page_start_index(
                posts_page, paginator
            ),
        }

    def _get_posts_queryset(self):
        """
        Get the base queryset for posts.

        Returns:
            QuerySet: Posts ordered by the configured ordering
        """
        return Post.objects.order_by(self.ordering)

    def _get_next_page_number(self, posts_page):
        """
        Get the next page number if available.

        Args:
            posts_page: Page object from paginator

        Returns:
            int or None: Next page number or None if no next page
        """
        if posts_page.has_next():
            return posts_page.next_page_number()
        return None

    def _calculate_page_start_index(self, posts_page, paginator):
        """
        Calculate the starting index for the current page.

        Args:
            posts_page: Page object from paginator
            paginator: Paginator instance

        Returns:
            int: Starting index for the current page
        """
        return (posts_page.number - 1) * paginator.per_page


class ExploreView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, TemplateView
):
    """
    Explore view displaying all posts.

    Displays a feed of all posts ordered by the configured ordering.
    Supports HTMX partial rendering for seamless navigation.
    """

    template_name = "posts/explore.html"
    partial_template = "posts/partials/_explore.html"

    # Page configuration
    PAGE_TITLE = "Explore"

    def get_context_data(self, **kwargs):
        """
        Add posts and HTMX status to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with posts and partial flag
        """
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "page": self.PAGE_TITLE,
                "partial": self._is_htmx_request(),
                "posts": self._get_posts(),
            }
        )

        return context

    def _is_htmx_request(self):
        """
        Check if the current request is an HTMX request.

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(self.request, "htmx", False)

    def _get_posts(self):
        """
        Get all posts ordered by the configured ordering.

        Returns:
            QuerySet: Posts ordered by self.ordering
        """
        return Post.objects.order_by(self.ordering)


class UploadView(
    LoginRequiredMixin, PostOrderingMixin, HTMXTemplateMixin, FormView
):
    """
    Upload view for creating new posts.

    Allows authenticated users to create new posts with a form.
    Supports HTMX partial rendering for seamless post creation
    without full page reload.
    """

    template_name = "posts/upload.html"
    partial_template = "posts/partials/_upload.html"
    form_class = PostForm
    success_url = reverse_lazy("posts:home")
    login_url = reverse_lazy("login")

    # Page configuration
    PAGE_TITLE = "Upload"

    # Template for HTMX response after successful upload
    HTMX_SUCCESS_TEMPLATE = "posts/partials/_home.html"

    def get_context_data(self, **kwargs):
        """
        Add page title to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with page title
        """
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page": self.PAGE_TITLE,
                "partial": self._is_htmx_request(),
            }
        )
        return context

    def form_valid(self, form):
        """
        Handle valid form submission.

        Saves the post with the current user as author and returns
        either an HTMX partial response or a standard redirect.

        Args:
            form: Valid form instance

        Returns:
            HttpResponse: HTMX partial or redirect response
        """
        # Save post with author
        post = self._save_post(form)

        # Handle HTMX request
        if self._is_htmx_request():
            return self._render_htmx_response()

        # Standard redirect
        return super().form_valid(form)

    def _save_post(self, form):
        """
        Save the post with the current user as author.

        Args:
            form: Valid form instance

        Returns:
            Post: Saved post instance
        """
        post = form.save(commit=False)
        post.author = self.request.user
        post.save()
        return post

    def _is_htmx_request(self):
        """
        Check if the current request is an HTMX request.

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(self.request, "htmx", False)

    def _render_htmx_response(self):
        """
        Render the HTMX partial response with updated posts.

        Returns:
            HttpResponse: Rendered HTMX partial
        """
        context = {"posts": self._get_posts()}
        return render(self.request, self.HTMX_SUCCESS_TEMPLATE, context)

    def _get_posts(self):
        """
        Get all posts ordered by the configured ordering.

        Returns:
            QuerySet: Posts ordered by self.ordering
        """
        return Post.objects.order_by(self.ordering)


class PostPageView(PostOrderingMixin, HTMXTemplateMixin, TemplateView):
    """
    Post detail view with navigation.

    Displays a single post with navigation to previous and next posts
    from the same author. Supports HTMX partial rendering for seamless
    navigation between posts.
    """

    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_postpage.html"

    # Configuration
    PAGE_TITLE = "Post Page"
    REDIRECT_URL = "posts:home"

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for post detail page.

        Args:
            request: The HTTP request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments (includes 'pk')

        Returns:
            HttpResponse: Rendered post page or redirect
        """
        # Validate post UUID
        if not self._has_valid_pk():
            return self._redirect_to_home()

        # Get post and navigation data
        post = self._get_post()
        navigation_data = self._get_navigation_data(post)

        # Prepare context
        context = self.get_context_data(post=post, **navigation_data)

        # Render appropriate template
        return self._render_response(request, context)

    def get_context_data(self, **kwargs):
        """
        Add page title and post data to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with page and post data
        """
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page": self.PAGE_TITLE,
                **kwargs,
            }
        )
        return context

    def _has_valid_pk(self):
        """
        Check if a valid post UUID is provided.

        Returns:
            bool: True if pk exists in kwargs, False otherwise
        """
        return bool(self.kwargs.get("pk"))

    def _redirect_to_home(self):
        """
        Redirect to home page.

        Returns:
            HttpResponseRedirect: Redirect to home
        """
        return redirect(self.REDIRECT_URL)

    def _get_post(self):
        """
        Get the post object or raise 404.

        Returns:
            Post: Post instance

        Raises:
            Http404: If post doesn't exist
        """
        return get_object_or_404(Post, uuid=self.kwargs["pk"])

    def _get_navigation_data(self, post):
        """
        Get navigation data (author posts, prev/next posts).

        Args:
            post: Current post instance

        Returns:
            dict: Dictionary with author_posts, prev_post, next_post
        """
        if not post.author:
            return self._get_empty_navigation(post)

        author_posts = self._get_author_posts(post.author)
        prev_post, next_post = self._get_adjacent_posts(post, author_posts)

        return {
            "author_posts": author_posts,
            "prev_post": prev_post,
            "next_post": next_post,
        }

    def _get_empty_navigation(self, post):
        """
        Get navigation data for posts without an author.

        Args:
            post: Current post instance

        Returns:
            dict: Dictionary with single post and no navigation
        """
        return {
            "author_posts": [post],
            "prev_post": None,
            "next_post": None,
        }

    def _get_author_posts(self, author):
        """
        Get all posts from the same author.

        Args:
            author: Author user instance

        Returns:
            list: List of posts ordered by self.ordering
        """
        return list(Post.objects.filter(author=author).order_by(self.ordering))

    def _get_adjacent_posts(self, current_post, author_posts):
        """
        Get previous and next posts for navigation.

        Args:
            current_post: Current post instance
            author_posts: List of all posts from the author

        Returns:
            tuple: (prev_post, next_post) or (None, None) if not found
        """
        try:
            index = author_posts.index(current_post)
        except ValueError:
            return None, None

        prev_post = author_posts[index - 1] if index > 0 else None
        next_post = (
            author_posts[index + 1] if index < len(author_posts) - 1 else None
        )

        return prev_post, next_post

    def _render_response(self, request, context):
        """
        Render the appropriate template based on request type.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            TemplateResponse: Rendered template
        """
        template = (
            self.partial_template
            if self._is_htmx_request(request)
            else self.template_name
        )
        return TemplateResponse(request, template, context)

    def _is_htmx_request(self, request):
        """
        Check if the current request is an HTMX request.

        Args:
            request: The HTTP request object

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(request, "htmx", False)


class PostEditView(LoginRequiredMixin, HTMXTemplateMixin, TemplateView):
    """
    Post edit view for updating or deleting posts.

    Allows post authors to edit their post content or delete posts.
    Supports HTMX partial rendering for inline editing without page reload.
    """

    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_post_edit.html"

    # URL configuration
    REDIRECT_HOME_URL_NAME = "posts:home"
    REDIRECT_POST_URL_NAME = "posts:post_page"
    REDIRECT_PROFILE_URL_NAME = "users:profile"

    def dispatch(self, request, *args, **kwargs):
        """
        Check permissions before processing the request.

        Args:
            request: The HTTP request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            HttpResponse: Redirect if unauthorized, otherwise continues
        """
        self.post_obj = self._get_post()

        if not self._is_post_author(request.user):
            return self._redirect_unauthorized()

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for post editing or deletion.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered edit form or redirect after deletion
        """
        # Handle post deletion
        if self._is_delete_request(request):
            return self._handle_delete(request)

        # Render edit form
        context = self.get_context_data()

        if self._is_htmx_request(request):
            return self.render_to_response(context)

        return self._redirect_to_post()

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for post updates.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        form = self._get_form(data=request.POST)

        if form.is_valid():
            return self._form_valid(form)

        return self._form_invalid(request, form)

    def get_context_data(self, **kwargs):
        """
        Add form and post to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with form and post
        """
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form") or self._get_form()

        context.update(
            {
                "form": form,
                "post": self.post_obj,
            }
        )

        return context

    def _get_post(self):
        """
        Get the post object or raise 404.

        Returns:
            Post: Post instance
        """
        return get_object_or_404(Post, uuid=self.kwargs["pk"])

    def _is_post_author(self, user):
        """
        Check if the user is the post author.

        Args:
            user: User instance

        Returns:
            bool: True if user is the author, False otherwise
        """
        return self.post_obj.author == user

    def _redirect_unauthorized(self):
        """
        Redirect unauthorized users to home.

        Returns:
            HttpResponseRedirect: Redirect to home page
        """
        return redirect(self.REDIRECT_HOME_URL_NAME)

    def _is_delete_request(self, request):
        """
        Check if this is a delete request.

        Args:
            request: The HTTP request object

        Returns:
            bool: True if delete parameter exists
        """
        return bool(request.GET.get("delete"))

    def _handle_delete(self, request):
        """
        Delete the post and redirect to user profile.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponseRedirect: Redirect to user profile
        """
        self.post_obj.delete()
        return redirect(self.REDIRECT_PROFILE_URL_NAME, request.user.username)

    def _is_htmx_request(self, request):
        """
        Check if the current request is an HTMX request.

        Args:
            request: The HTTP request object

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(request, "htmx", False)

    def _get_form(self, data=None):
        """
        Instantiate the edit form.

        Args:
            data: POST data (optional)

        Returns:
            PostEditForm: Form instance
        """
        return PostEditForm(data=data, instance=self.post_obj)

    def _form_valid(self, form):
        """
        Handle valid form submission.

        Args:
            form: Valid form instance

        Returns:
            HttpResponseRedirect: Redirect to post page
        """
        form.save()
        return self._redirect_to_post()

    def _form_invalid(self, request, form):
        """
        Handle invalid form submission.

        Args:
            request: The HTTP request object
            form: Invalid form instance with errors

        Returns:
            HttpResponse: Rendered form with errors or redirect
        """
        context = self.get_context_data(form=form)

        if self._is_htmx_request(request):
            return self.render_to_response(context)

        return self._redirect_to_post()

    def _redirect_to_post(self):
        """
        Redirect to the post detail page.

        Returns:
            HttpResponseRedirect: Redirect to post page
        """
        return redirect(self.REDIRECT_POST_URL_NAME, self.post_obj.uuid)


class PostLikeView(LoginRequiredMixin, View):
    """
    Post like/unlike view.

    Handles toggling likes on posts with HTMX support for different
    rendering contexts (home page, post page). Updates like counts
    and returns appropriate partials.
    """

    # URL configuration
    REDIRECT_POST_URL_NAME = "posts:post_page"

    # Template configuration
    TEMPLATE_LIKE_HOME = "posts/partials/_like_home.html"
    TEMPLATE_LIKE_POSTPAGE = "posts/partials/_like_postpage.html"

    def get(self, request, pk):
        """
        Handle GET requests for like/unlike actions.

        Args:
            request: The HTTP request object
            pk: Post UUID

        Returns:
            HttpResponse: Rendered partial or redirect
        """
        post = self._get_post(pk)

        # Toggle like if HTMX request
        if self._is_htmx_request(request):
            self._toggle_like(post, request.user)

        # Prepare context
        context = self._get_context_data(post)

        # Render appropriate template based on source
        if request.GET.get("home"):
            return self._render_home_partial(request, context)

        if request.GET.get("postpage"):
            return self._render_postpage_partial(request, context)

        # Fallback redirect
        return self._redirect_to_post(pk)

    def _get_post(self, pk):
        """
        Get the post object or raise 404.

        Args:
            pk: Post UUID

        Returns:
            Post: Post instance
        """
        return get_object_or_404(Post, uuid=pk)

    def _is_htmx_request(self, request):
        """
        Check if the current request is an HTMX request.

        Args:
            request: The HTTP request object

        Returns:
            bool: True if HTMX request, False otherwise
        """
        return getattr(request, "htmx", False)

    def _toggle_like(self, post, user):
        """
        Toggle like status for the user on the post.

        Args:
            post: Post instance
            user: User instance
        """
        if post.likes.filter(id=user.id).exists():
            post.likes.remove(user)
        else:
            post.likes.add(user)

    def _get_context_data(self, post):
        """
        Prepare context data with post and author likes.

        Args:
            post: Post instance

        Returns:
            dict: Context dictionary
        """
        profile_user_likes = self._get_author_total_likes(post.author)

        return {
            "post": post,
            "profile_user_likes": profile_user_likes,
        }

    def _get_author_total_likes(self, author):
        """
        Get total likes for all posts by the author.

        Args:
            author: User instance

        Returns:
            int: Total number of likes across all author's posts
        """
        return author.posts.aggregate(total_likes=Count("likes"))[
            "total_likes"
        ]

    def _render_home_partial(self, request, context):
        """
        Render the home page like partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered home partial
        """
        return render(request, self.TEMPLATE_LIKE_HOME, context)

    def _render_postpage_partial(self, request, context):
        """
        Render the post page like partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered post page partial
        """
        return render(request, self.TEMPLATE_LIKE_POSTPAGE, context)

    def _redirect_to_post(self, pk):
        """
        Redirect to the post detail page.

        Args:
            pk: Post UUID

        Returns:
            HttpResponseRedirect: Redirect to post page
        """
        return redirect(self.REDIRECT_POST_URL_NAME, pk)
