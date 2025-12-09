import logging
from django.views import View
from django.views.generic import TemplateView, FormView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.urls import reverse_lazy
from django.http import HttpResponse, HttpResponseForbidden
from django.db import transaction
from django.db.models import Count, Prefetch
from utils.mixins import PostOrderingMixin, HTMXTemplateMixin
from itertools import chain
from operator import attrgetter
from .forms import PostForm, PostEditForm
from .models import Post, Comment, Repost

logger = logging.getLogger(__name__)


class BasePostView(PostOrderingMixin):
    """Base view with common post operations and security measures."""

    REDIRECT_URL = "posts:home"

    def get_posts(self):
        """
        Get all posts with optimized queries to avoid N+1 problems.

        Returns:
            QuerySet: Optimized posts queryset
        """
        return (
            Post.objects.select_related("author")
            .prefetch_related(
                "likes",
                "bookmarks",
                "reposts",
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("author"),
                ),
            )
            .order_by(self.ordering)
        )

    def get_post(self, pk):
        """
        Get a single post with optimized queries.

        Args:
            pk: Post UUID

        Returns:
            Post: Post instance with related data
        """
        return get_object_or_404(
            Post.objects.select_related("author").prefetch_related(
                "likes", "bookmarks", "comments__author", "comments__likes"
            ),
            uuid=pk,
        )

    def redirect_to_home(self):
        """
        Redirect to home page.

        Returns:
            HttpResponseRedirect: Redirect to home
        """
        return redirect(self.REDIRECT_URL)

    def check_rate_limit(self, request, action, limit=50, window=60):
        """
        Check rate limiting for user actions.

        Args:
            request: HTTP request object
            action: Action name (e.g., 'like', 'comment')
            limit: Maximum actions per window
            window: Time window in seconds

        Returns:
            bool: True if within limit, False otherwise
        """
        cache_key = f"{action}_{request.user.id}"
        action_count = cache.get(cache_key, 0)

        if action_count >= limit:
            logger.warning(
                f"Rate limit exceeded for user {request.user.id} "
                f"on action {action}"
            )
            return False

        cache.set(cache_key, action_count + 1, window)
        return True


class HomeView(
    BasePostView,
    LoginRequiredMixin,
    HTMXTemplateMixin,
    TemplateView,
):
    """
    Home view displaying paginated posts and reposts.

    Displays a feed of posts and reposts from followed users with pagination
    support and HTMX partial rendering for infinite scroll functionality.
    """

    template_name = "posts/home.html"
    partial_template = "posts/partials/_home.html"
    paginator_partial_template = "posts/partials/_posts.html"

    # Pagination configuration
    PAGINATE_BY = 10
    DEFAULT_PAGE_NUMBER = 1
    ORPHANS = 2

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

        try:
            pagination_data = self._get_paginated_posts()
            context.update(
                {
                    "page": self.PAGE_TITLE,
                    "partial": self.is_htmx_request(),
                    **pagination_data,
                }
            )
        except Exception as e:
            logger.error(f"Error in HomeView context: {e}", exc_info=True)
            context.update(
                {
                    "page": self.PAGE_TITLE,
                    "partial": self.is_htmx_request(),
                    "posts": [],
                    "next_page": None,
                    "page_start_index": 0,
                    "error": "Une erreur est survenue lors du chargement des posts.",
                }
            )

        return context

    def _get_following_user_ids(self):
        """
        Get the list of user IDs that the current user follows, plus the user themselves.

        Returns:
            list: List of user IDs (followers + current user)
        """
        following_user_ids = self.request.user.is_follower.values_list(
            "following", flat=True
        )
        user_ids = list(following_user_ids) + [self.request.user.id]
        return user_ids

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
            page = int(page_number)
            return page if page > 0 else self.DEFAULT_PAGE_NUMBER
        except (TypeError, ValueError):
            logger.warning(f"Invalid page number: {page_number}")
            return self.DEFAULT_PAGE_NUMBER

    def _get_paginated_posts(self):
        """
        Get paginated posts with pagination metadata.

        Returns:
            dict: Dictionary containing posts, next_page, and page_start_index
        """
        feed = self._get_combined_feed()
        paginator = Paginator(feed, self.PAGINATE_BY, orphans=self.ORPHANS)
        page_number = self._get_page_number()
        posts_page = paginator.get_page(page_number)

        return {
            "posts": posts_page,
            "next_page": self._get_next_page_number(posts_page),
            "page_start_index": self._calculate_page_start_index(
                posts_page, paginator
            ),
        }

    def _get_filtered_posts(self):
        """
        Get posts from followed users with optimized queries.

        Returns:
            QuerySet: Filtered posts queryset
        """
        user_ids = self._get_following_user_ids()

        return (
            Post.objects.filter(author__in=user_ids)
            .select_related("author")
            .prefetch_related(
                "likes",
                "bookmarks",
                "reposts",
                Prefetch(
                    "comments",
                    queryset=Comment.objects.select_related("author"),
                ),
            )
            .order_by(self.ordering)
        )

    def _get_reposts_queryset(self):
        """
        Get the base queryset for reposts from followed users with optimized related data.

        Returns:
            QuerySet: Optimized reposts queryset
        """
        user_ids = self._get_following_user_ids()

        return (
            Repost.objects.filter(user__in=user_ids)
            .select_related("post__author", "user")
            .prefetch_related(
                "post__likes", "post__bookmarks", "post__comments"
            )
        )

    def _prepare_reposted_posts(self):
        """
        Prepare reposted posts with repost metadata.

        Returns:
            list: List of posts with repost information
        """
        reposts = self._get_reposts_queryset()
        reposted_posts = []

        for repost in reposts:
            post = repost.post
            post.created_at = repost.created_at
            post.repost_author = repost.user
            post.is_repost = True
            reposted_posts.append(post)

        return reposted_posts

    def _get_combined_feed(self):
        """
        Combine posts and reposts from followed users into a single sorted feed.

        Returns:
            list: Combined and sorted feed of posts and reposts
        """
        # Use cache for feed if available
        cache_key = f"home_feed_{self.request.user.id}_{self.ordering}"
        feed = cache.get(cache_key)

        if feed is None:
            posts = self._get_filtered_posts()
            reposted_posts = self._prepare_reposted_posts()

            feed = sorted(
                chain(posts, reposted_posts),
                key=attrgetter("created_at"),
                reverse=True,
            )
            # Cache for 2 minutes
            cache.set(cache_key, feed, 120)

        return feed

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
    BasePostView,
    LoginRequiredMixin,
    HTMXTemplateMixin,
    TemplateView,
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

        try:
            context.update(
                {
                    "page": self.PAGE_TITLE,
                    "partial": self.is_htmx_request(),
                    "posts": self.get_posts(),
                }
            )
        except Exception as e:
            logger.error(f"Error in ExploreView: {e}", exc_info=True)
            context.update(
                {
                    "page": self.PAGE_TITLE,
                    "partial": self.is_htmx_request(),
                    "posts": [],
                    "error": "Une erreur est survenue.",
                }
            )

        return context


class UploadView(
    LoginRequiredMixin,
    BasePostView,
    HTMXTemplateMixin,
    FormView,
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

    # Rate limiting
    MAX_POSTS_PER_HOUR = 20

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
                "partial": self.is_htmx_request(),
            }
        )
        return context

    @transaction.atomic
    def form_valid(self, form):
        """
        Handle valid form submission with rate limiting and transaction.

        Args:
            form: Valid form instance

        Returns:
            HttpResponse: HTMX partial or redirect response
        """
        # Check rate limit using parent method
        if not super().check_rate_limit(
            self.request,
            "post_creation",
            limit=self.MAX_POSTS_PER_HOUR,
            window=3600,
        ):
            if self.is_htmx_request():
                return HttpResponseForbidden(
                    "Limite de posts atteinte. Veuillez réessayer plus tard."
                )
            form.add_error(None, "Trop de posts créés. Attendez un peu.")
            return self.form_invalid(form)

        try:
            # Save post with author
            post = self._save_post(form)
            logger.info(
                f"Post created: {post.uuid} by user {self.request.user.id}"
            )

            # Invalidate cache
            cache_key = f"home_feed_{self.request.user.id}_{self.ordering}"
            cache.delete(cache_key)

            # Handle HTMX request
            if self.is_htmx_request():
                return self._render_htmx_response()

            # Standard redirect
            return super().form_valid(form)

        except Exception as e:
            logger.error(f"Error creating post: {e}", exc_info=True)
            form.add_error(
                None, "Une erreur est survenue lors de la création du post."
            )
            return self.form_invalid(form)

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

    def _render_htmx_response(self):
        """
        Render the HTMX partial response with updated posts.

        Returns:
            HttpResponse: Rendered HTMX partial
        """
        context = {"posts": self.get_posts()}
        return render(
            self.request, self.HTMX_SUCCESS_TEMPLATE, context=context
        )


class PostPageView(BasePostView, HTMXTemplateMixin, TemplateView):
    """
    Post detail view with navigation.

    Displays a single post with navigation to previous and next posts
    from the same author. Supports HTMX partial rendering for seamless
    navigation between posts.
    """

    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_postpage.html"
    comment_partial = "posts/partials/comments/_comment_loop.html"

    # Configuration
    PAGE_TITLE = "Post Page"
    MAX_COMMENT_LENGTH = 5000
    MAX_COMMENTS_PER_MINUTE = 10

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
            return self.redirect_to_home()

        try:
            # Get post and navigation data
            post = self._get_post()
            navigation_data = self._get_navigation_data(post=post)

            # Prepare context
            context = self.get_context_data(post=post, **navigation_data)

            # Render appropriate template
            return self._render_response(request, context=context)

        except Exception as e:
            logger.error(f"Error in PostPageView GET: {e}", exc_info=True)
            return self.redirect_to_home()

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for adding a new comment to a post.

        Args:
            request: The HTTP request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments (includes 'pk')

        Returns:
            TemplateResponse: Rendered comment loop partial with the updated
            comment list for the current post.
        """
        pk = self.kwargs.get("pk")
        if not pk:
            return redirect(self.REDIRECT_URL)

        # Check rate limit
        if not self.check_rate_limit(
            request,
            "comment_creation",
            limit=self.MAX_COMMENTS_PER_MINUTE,
            window=60,
        ):
            return HttpResponseForbidden(
                "Trop de commentaires. Veuillez ralentir."
            )

        try:
            post = self.get_post(pk)
            body = request.POST.get("comment", "").strip()

            # Validate comment
            if body and len(body) <= self.MAX_COMMENT_LENGTH:
                Comment.objects.create(
                    author=request.user, post=post, body=body
                )
                logger.info(
                    f"Comment created on post {pk} by user {request.user.id}"
                )

                # Invalidate cache
                cache.delete(f"post_comments_{pk}")
            elif len(body) > self.MAX_COMMENT_LENGTH:
                logger.warning(f"Comment too long: {len(body)} chars")

            # Limited context to refresh comments section via HTMX
            context = {"post": post}
            return TemplateResponse(
                request, self.comment_partial, context=context
            )

        except Exception as e:
            logger.error(f"Error creating comment: {e}", exc_info=True)
            return HttpResponse(
                "Erreur lors de la création du commentaire", status=500
            )

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

    def _get_post(self):
        """
        Get the post object or raise 404.

        Returns:
            Post: Post instance with optimized queries

        Raises:
            Http404: If post doesn't exist
        """
        return self.get_post(self.kwargs["pk"])

    def _get_navigation_data(self, post):
        """
        Get navigation data (author posts, prev/next posts).

        Args:
            post: Current post instance

        Returns:
            dict: Dictionary with author_posts, prev_post, next_post
        """
        if not post.author:
            return self._get_empty_navigation(post=post)

        author_posts = self._get_author_posts(author=post.author)
        prev_post, next_post = self._get_adjacent_posts(
            current_post=post, author_posts=author_posts
        )

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
        Get all posts from the same author with caching.

        Args:
            author: Author user instance

        Returns:
            list: List of posts ordered by self.ordering
        """
        cache_key = f"author_posts_{author.id}_{self.ordering}"
        posts = cache.get(cache_key)

        if posts is None:
            posts = list(
                Post.objects.filter(author=author)
                .select_related("author")
                .order_by(self.ordering)
            )
            cache.set(cache_key, posts, 300)  # Cache 5 minutes

        return posts

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
            if self.is_htmx_request()
            else self.template_name
        )
        return TemplateResponse(request, template=template, context=context)


class AuthorRequiredMixin:
    """Mixin to ensure user is the author of the post."""

    def dispatch(self, request, *args, **kwargs):
        """Check if user is the post author before processing request."""
        try:
            self.post_obj = self._get_post()
        except Exception as e:
            logger.error(f"Error fetching post: {e}", exc_info=True)
            return redirect(self.REDIRECT_URL)

        if not self._is_post_author(request.user):
            logger.warning(
                f"Unauthorized edit attempt by user {request.user.id} "
                f"on post {self.post_obj.uuid}"
            )
            return redirect(self.REDIRECT_URL)

        return super().dispatch(request, *args, **kwargs)


class PostEditView(
    AuthorRequiredMixin,
    BasePostView,
    LoginRequiredMixin,
    HTMXTemplateMixin,
    TemplateView,
):
    """
    Post edit view for updating or deleting posts.

    Allows post authors to edit their post content or delete posts.
    Supports HTMX partial rendering for inline editing without page reload.
    """

    template_name = "posts/postpage.html"
    partial_template = "posts/partials/_post_edit.html"

    # URL configuration
    REDIRECT_POST_URL_NAME = "posts:post_page"
    REDIRECT_PROFILE_URL_NAME = "users:profile"

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for post editing or deletion.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered edit form or redirect after deletion
        """
        try:
            # Handle post deletion
            if self._is_delete_request(request):
                return self._handle_delete(request)

            # Render edit form
            context = self.get_context_data()

            if self.is_htmx_request():
                return self.render_to_response(context=context)

            return self._redirect_to_post()

        except Exception as e:
            logger.error(f"Error in PostEditView GET: {e}", exc_info=True)
            return self.redirect_to_home()

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for post updates.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        try:
            form = self._get_form(data=request.POST)

            if form.is_valid():
                return self._form_valid(form=form)

            return self._form_invalid(request, form=form)

        except Exception as e:
            logger.error(f"Error updating post: {e}", exc_info=True)
            return self.redirect_to_home()

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
        username = request.user.username
        post_uuid = self.post_obj.uuid
        self.post_obj.delete()

        # Invalidate caches
        cache.delete(f"home_feed_{request.user.id}_{self.ordering}")
        cache.delete(f"author_posts_{request.user.id}_{self.ordering}")

        logger.info(f"Post {post_uuid} deleted by user {request.user.id}")
        return redirect(self.REDIRECT_PROFILE_URL_NAME, username)

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

        # Invalidate caches
        cache.delete(f"home_feed_{self.request.user.id}_{self.ordering}")
        cache.delete(f"author_posts_{self.post_obj.author.id}_{self.ordering}")

        logger.info(
            f"Post {self.post_obj.uuid} updated by user {self.request.user.id}"
        )
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

        if self.is_htmx_request():
            return self.render_to_response(context=context)

        return self._redirect_to_post()

    def _redirect_to_post(self):
        """
        Redirect to the post detail page.

        Returns:
            HttpResponseRedirect: Redirect to post page
        """
        return redirect(self.REDIRECT_POST_URL_NAME, self.post_obj.uuid)


class PostLikeView(LoginRequiredMixin, BasePostView, HTMXTemplateMixin, View):
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
        post = self.get_post(pk)

        # Toggle like if HTMX request
        if self.is_htmx_request():
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


class BookmarkPostView(
    BasePostView, LoginRequiredMixin, HTMXTemplateMixin, View
):
    """
    Bookmark/unbookmark post view.

    Handles toggling bookmarks on posts with HTMX support for different
    rendering contexts (home page, post page).

    Note: Uses GET for backwards compatibility with existing templates.
    """

    # URL configuration
    REDIRECT_POST_URL_NAME = "posts:post_page"

    # Template configuration
    TEMPLATE_BOOKMARK_HOME = "posts/partials/_bookmark_home.html"
    TEMPLATE_BOOKMARK_POSTPAGE = "posts/partials/_bookmark_postpage.html"

    # Rate limiting
    MAX_BOOKMARKS_PER_MINUTE = 30

    def get(self, request, pk):
        """
        Handle GET requests for bookmark/unbookmark actions.

        Args:
            request: The HTTP request object
            pk: Post UUID

        Returns:
            HttpResponse: Rendered partial or redirect
        """
        # Check rate limit
        if not super().check_rate_limit(
            request,
            "bookmark_action",
            limit=self.MAX_BOOKMARKS_PER_MINUTE,
            window=60,
        ):
            return HttpResponseForbidden(
                "Trop de bookmarks. Veuillez ralentir."
            )

        try:
            post = self.get_post(pk=pk)

            # Toggle bookmark if HTMX request
            if self.is_htmx_request():
                self._toggle_bookmark(post=post, user=request.user)

            # Prepare context
            context = self._get_context_data(post=post)

            # Render appropriate template based on source
            if request.GET.get("home"):
                return self._render_home_partial(request, context=context)

            if request.GET.get("postpage"):
                return self._render_postpage_partial(request, context=context)

            # Fallback redirect
            return self._redirect_to_post(pk=pk)

        except Exception as e:
            logger.error(f"Error in BookmarkPostView: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    @transaction.atomic
    def _toggle_bookmark(self, post, user):
        """
        Toggle bookmark status for the user on the post.

        Args:
            post: Post instance
            user: User instance
        """
        if post.bookmarks.filter(id=user.id).exists():
            post.bookmarks.remove(user)
            logger.info(
                f"User {user.id} removed bookmark from post {post.uuid}"
            )
        else:
            post.bookmarks.add(user)
            logger.info(f"User {user.id} bookmarked post {post.uuid}")

    def _get_context_data(self, post):
        """
        Prepare context data with post.

        Args:
            post: Post instance

        Returns:
            dict: Context dictionary
        """
        return {"post": post}

    def _render_home_partial(self, request, context):
        """
        Render the home page bookmark partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered home partial
        """
        return render(request, self.TEMPLATE_BOOKMARK_HOME, context=context)

    def _render_postpage_partial(self, request, context):
        """
        Render the post page bookmark partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered post page partial
        """
        return render(
            request, self.TEMPLATE_BOOKMARK_POSTPAGE, context=context
        )

    def _redirect_to_post(self, pk):
        """
        Redirect to the post detail page.

        Args:
            pk: Post UUID

        Returns:
            HttpResponseRedirect: Redirect to post page
        """
        return redirect(self.REDIRECT_POST_URL_NAME, pk)


class CommentView(BasePostView, LoginRequiredMixin, HTMXTemplateMixin, View):
    """
    Comment reply view.

    Handles adding replies to comments and rendering comment-related
    partials. Requires HTMX requests.
    """

    # Template configuration
    TEMPLATE_VIEW_REPLIES = "posts/partials/comments/_button_view_replies.html"
    TEMPLATE_REPLY_FORM = "posts/partials/comments/_form_add_reply.html"
    TEMPLATE_REPLY_LOOP = "posts/partials/comments/_reply_loop.html"

    # Rate limiting
    MAX_REPLIES_PER_MINUTE = 10

    def get(self, request, pk):
        """
        Handle GET requests for comment-related actions.

        Args:
            request: The HTTP request object
            pk: Comment UUID

        Returns:
            HttpResponse: Rendered partial or redirect
        """
        # HTMX required
        if not self.is_htmx_request():
            return self.redirect_to_home()

        try:
            comment = self._get_comment(pk=pk)
            parent_comment = self._get_parent_comment(comment=comment)

            context = self._get_context_data(
                comment=comment, parent_comment=parent_comment
            )

            # Render appropriate template based on action
            if request.GET.get("hide_replies"):
                return self._render_view_replies_button(
                    request, context=context
                )

            if request.GET.get("reply_form"):
                return self._render_reply_form(request, context=context)

            return self._render_reply_loop(request, context=context)

        except Exception as e:
            logger.error(f"Error in CommentView GET: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    @transaction.atomic
    def post(self, request, pk):
        """
        Handle POST requests for creating replies.

        Args:
            request: The HTTP request object
            pk: Comment UUID

        Returns:
            HttpResponse: Rendered reply loop partial
        """
        # HTMX required
        if not self.is_htmx_request():
            return self.redirect_to_home()

        # Check rate limit
        if not super().check_rate_limit(
            request,
            "reply_creation",
            limit=self.MAX_REPLIES_PER_MINUTE,
            window=60,
        ):
            return HttpResponseForbidden(
                "Trop de réponses. Veuillez ralentir."
            )

        try:
            comment = self._get_comment(pk=pk)
            parent_comment = self._get_parent_comment(comment=comment)
            parent_reply = self._get_parent_reply(comment=comment)

            # Create reply if body is provided
            body = request.POST.get("reply", "").strip()
            if body and len(body) <= 5000:
                self._create_reply(
                    user=request.user,
                    comment=comment,
                    parent_comment=parent_comment,
                    parent_reply=parent_reply,
                    body=body,
                )
                logger.info(
                    f"Reply created on comment {pk} by user {request.user.id}"
                )

            context = self._get_context_data(
                comment=comment, parent_comment=parent_comment
            )
            return self._render_reply_loop(request, context=context)

        except Exception as e:
            logger.error(f"Error creating reply: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    def _get_comment(self, pk):
        """
        Get the comment object or raise 404.

        Args:
            pk: Comment UUID

        Returns:
            Comment: Comment instance
        """
        return get_object_or_404(
            Comment.objects.select_related("author", "post"), uuid=pk
        )

    def _get_parent_comment(self, comment):
        """
        Get the root parent comment by traversing up the tree.

        Args:
            comment: Comment instance

        Returns:
            Comment: Root parent comment
        """
        parent_comment = comment
        while parent_comment.parent_comment is not None:
            parent_comment = parent_comment.parent_comment
        return parent_comment

    def _get_parent_reply(self, comment):
        """
        Get the direct parent reply if comment is a reply.

        Args:
            comment: Comment instance

        Returns:
            Comment or None: Parent reply or None if top-level comment
        """
        return comment if comment.parent_comment else None

    def _create_reply(self, user, comment, parent_comment, parent_reply, body):
        """
        Create a new reply to a comment.

        Args:
            user: User creating the reply
            comment: Comment being replied to
            parent_comment: Root parent comment
            parent_reply: Direct parent reply
            body: Reply text content

        Returns:
            Comment: Created reply instance
        """
        return Comment.objects.create(
            author=user,
            post=comment.post,
            parent_comment=parent_comment,
            parent_reply=parent_reply,
            body=body,
        )

    def _get_context_data(self, comment, parent_comment):
        """
        Prepare context data with comment information.

        Args:
            comment: Current comment instance
            parent_comment: Root parent comment instance

        Returns:
            dict: Context dictionary
        """
        return {
            "comment": parent_comment,
            "current_comment": comment,
        }

    def _render_view_replies_button(self, request, context):
        """
        Render the view replies button partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered partial
        """
        return render(request, self.TEMPLATE_VIEW_REPLIES, context=context)

    def _render_reply_form(self, request, context):
        """
        Render the reply form partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered partial
        """
        return render(request, self.TEMPLATE_REPLY_FORM, context=context)

    def _render_reply_loop(self, request, context):
        """
        Render the reply loop partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered partial
        """
        return render(request, self.TEMPLATE_REPLY_LOOP, context=context)


class CommentDeleteView(
    BasePostView, LoginRequiredMixin, HTMXTemplateMixin, View
):
    """
    Comment deletion view.

    Handles comment deletion with authorization check and HTMX
    out-of-band swap for updating comment count.
    """

    # Template configuration
    TEMPLATE_DELETE_FORM = "posts/partials/comments/_form_delete_comment.html"

    def get(self, request, pk):
        """
        Handle GET requests for showing delete confirmation.

        Args:
            request: The HTTP request object
            pk: Comment UUID

        Returns:
            HttpResponse: Rendered delete form or redirect
        """
        # HTMX required
        if not self.is_htmx_request():
            return self.redirect_to_home()

        try:
            comment = self._get_comment(pk=pk)

            # Check authorization
            if not self._is_comment_author(comment=comment, user=request.user):
                logger.warning(
                    f"Unauthorized delete attempt by user {request.user.id} "
                    f"on comment {pk}"
                )
                return HttpResponse()

            context = self._get_context_data(comment)
            return self._render_delete_form(request, context=context)

        except Exception as e:
            logger.error(f"Error in CommentDeleteView GET: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    @transaction.atomic
    def post(self, request, pk):
        """
        Handle POST requests for deleting comments.

        Args:
            request: The HTTP request object
            pk: Comment UUID

        Returns:
            HttpResponse: OOB swap response with updated comment count
        """
        # HTMX required
        if not self.is_htmx_request():
            return self.redirect_to_home()

        try:
            comment = self._get_comment(pk=pk)

            # Check authorization
            if not self._is_comment_author(comment=comment, user=request.user):
                logger.warning(
                    f"Unauthorized delete by user {request.user.id} "
                    f"on comment {pk}"
                )
                return HttpResponse()

            # Delete comment and return OOB response
            post = comment.post
            comment.delete()
            logger.info(f"Comment {pk} deleted by user {request.user.id}")

            return self._render_oob_response(post=post)

        except Exception as e:
            logger.error(f"Error deleting comment: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    def _get_comment(self, pk):
        """
        Get the comment object or raise 404.

        Args:
            pk: Comment UUID

        Returns:
            Comment: Comment instance
        """
        return get_object_or_404(
            Comment.objects.select_related("author", "post"), uuid=pk
        )

    def _is_comment_author(self, comment, user):
        """
        Check if the user is the comment author.

        Args:
            comment: Comment instance
            user: User instance

        Returns:
            bool: True if user is the author, False otherwise
        """
        return comment.author == user

    def _get_context_data(self, comment):
        """
        Prepare context data with comment.

        Args:
            comment: Comment instance

        Returns:
            dict: Context dictionary
        """
        return {"comment": comment}

    def _render_delete_form(self, request, context):
        """
        Render the delete confirmation form.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered delete form
        """
        return render(request, self.TEMPLATE_DELETE_FORM, context=context)

    def _render_oob_response(self, post):
        """
        Render HTMX out-of-band swap response with updated comment count.

        Args:
            post: Post instance

        Returns:
            HttpResponse: OOB swap HTML
        """
        comment_count = post.comments.count()
        response = (
            f"<div hx-swap-oob='innerHTML' id='comment_count'>"
            f"{comment_count}</div>"
        )
        return HttpResponse(response)


class LikeCommentView(
    BasePostView, LoginRequiredMixin, HTMXTemplateMixin, View
):
    """
    Comment like/unlike view.

    Handles toggling likes on comments. Requires HTMX requests.
    """

    # Template configuration
    TEMPLATE_BUTTON_LIKE_COMMENT = (
        "posts/partials/comments/_button_like_comment.html"
    )

    # Rate limiting
    MAX_COMMENT_LIKES_PER_MINUTE = 30

    def get(self, request, pk):
        """
        Handle GET requests for like/unlike actions.

        Args:
            request: The HTTP request object
            pk: Comment UUID

        Returns:
            HttpResponse: Rendered like button partial or redirect
        """
        # HTMX required
        if not self.is_htmx_request():
            return self.redirect_to_home()

        # Check rate limit
        if not super().check_rate_limit(
            request,
            "comment_like",
            limit=self.MAX_COMMENT_LIKES_PER_MINUTE,
            window=60,
        ):
            return HttpResponseForbidden("Trop de likes. Veuillez ralentir.")

        try:
            comment = self._get_comment(pk=pk)
            self._toggle_like(comment=comment, user=request.user)

            context = self._get_context_data(comment=comment)
            return self._render_like_button(request, context=context)

        except Exception as e:
            logger.error(f"Error in LikeCommentView: {e}", exc_info=True)
            return HttpResponse("Erreur", status=500)

    def _get_comment(self, pk):
        """
        Get the comment object or raise 404.

        Args:
            pk: Comment UUID

        Returns:
            Comment: Comment instance
        """
        return get_object_or_404(
            Comment.objects.prefetch_related("likes"), uuid=pk
        )

    @transaction.atomic
    def _toggle_like(self, comment, user):
        """
        Toggle like status for the user on the comment.

        Args:
            comment: Comment instance
            user: User instance
        """
        if comment.likes.filter(id=user.id).exists():
            comment.likes.remove(user)
            logger.info(f"User {user.id} unliked comment {comment.uuid}")
        else:
            comment.likes.add(user)
            logger.info(f"User {user.id} liked comment {comment.uuid}")

    def _get_context_data(self, comment):
        """
        Prepare context data with comment.

        Args:
            comment: Comment instance

        Returns:
            dict: Context dictionary
        """
        return {"comment": comment}

    def _render_like_button(self, request, context):
        """
        Render the like button partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered like button
        """
        return render(
            request, self.TEMPLATE_BUTTON_LIKE_COMMENT, context=context
        )


class SharePostView(BasePostView, LoginRequiredMixin, View):
    """
    Post share/repost view.

    Handles reposting posts and displaying the share modal.
    """

    # Template configuration
    TEMPLATE_POST_SHARE_MODAL = "posts/partials/_post_share.html"

    # Rate limiting
    MAX_REPOSTS_PER_MINUTE = 10

    def get(self, request, pk):
        """
        Handle GET requests for share/repost actions.

        Args:
            request: The HTTP request object
            pk: Post UUID

        Returns:
            HttpResponse: Rendered share modal or redirect
        """
        try:
            post = self.get_post(pk=pk)

            # Handle repost action
            if request.GET.get("repost"):
                # Check rate limit
                if not super().check_rate_limit(
                    request,
                    "repost_action",
                    limit=self.MAX_REPOSTS_PER_MINUTE,
                    window=60,
                ):
                    return HttpResponseForbidden(
                        "Trop de reposts. Veuillez ralentir."
                    )

                self._toggle_repost(post=post, user=request.user)

                # Invalidate cache
                cache_key = f"home_feed_{request.user.id}_{self.ordering}"
                cache.delete(cache_key)

                return self.redirect_to_home()

            # Show share modal
            context = self._get_context_data(post=post)
            return self._render_share_modal(request, context=context)

        except Exception as e:
            logger.error(f"Error in SharePostView: {e}", exc_info=True)
            return self.redirect_to_home()

    @transaction.atomic
    def _toggle_repost(self, post, user):
        """
        Toggle repost status for the user on the post.

        Args:
            post: Post instance
            user: User instance
        """
        if post.reposts.filter(id=user.id).exists():
            post.reposts.remove(user)
            logger.info(f"User {user.id} removed repost of post {post.uuid}")
        else:
            post.reposts.add(user)
            logger.info(f"User {user.id} reposted post {post.uuid}")

    def _get_context_data(self, post):
        """
        Prepare context data with post.

        Args:
            post: Post instance

        Returns:
            dict: Context dictionary
        """
        return {"post": post}

    def _render_share_modal(self, request, context):
        """
        Render the share modal partial.

        Args:
            request: The HTTP request object
            context: Context dictionary

        Returns:
            HttpResponse: Rendered share modal
        """
        return render(request, self.TEMPLATE_POST_SHARE_MODAL, context=context)
