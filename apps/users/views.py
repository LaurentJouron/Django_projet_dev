import random
from django.views import View
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.http import HttpResponse
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from utils.mixins import PostSortingMixin, HTMXTemplateMixin
from utils.emails.services import send_email_async
from django.db.models import Count
from django.contrib import messages
from .forms import (
    ProfileForm,
    EmailAddress,
    BirthdayForm,
    EmailForm,
)

User = get_user_model()


class IndexView(TemplateView):
    template_name = "users/index.html"
    login_url = "posts:home"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_title(self):
        return "Index"


class ProfileView(
    LoginRequiredMixin, PostSortingMixin, HTMXTemplateMixin, View
):
    """
    View for displaying user profiles with various filtering options.

    Handles different types of profile content including posts, reposts,
    liked posts, and bookmarked posts. Supports HTMX partial rendering.
    """

    template_name = "users/profile.html"
    partial_template = "users/partials/_profile.html"

    def get(self, request, username=None):
        """
        Handle GET requests for profile view.

        Args:
            request: The HTTP request object
            username: Optional username for the profile to display

        Returns:
            HttpResponse: Rendered profile page or partial
        """
        # Redirect if no username provided
        if not username:
            return redirect("users:profile", request.user.username)

        # Get the profile user
        profile_user = get_object_or_404(User, username=username)

        # Handle different GET parameters
        if request.GET.get("link"):
            return self._render_profile_link(request, username)

        if request.GET.get("reposted"):
            return self._render_reposts(request, profile_user)

        if request.GET.get("liked"):
            return self._render_liked_posts(request, profile_user)

        if request.GET.get("bookmarked"):
            return self._render_bookmarked_posts(request)

        # Prepare main context
        context = self._get_main_context(request, profile_user)

        # Render based on request type
        if request.GET.get("sort"):
            return render(
                request, "users/partials/_profile_posts.html", context
            )

        # Use HTMXTemplateMixin for template selection
        template = (
            self.get_template_names()[0]
            if request.htmx
            else self.template_name
        )
        return render(request, template, context)

    def _render_profile_link(self, request, username):
        """
        Render the profile link partial.

        Args:
            request: The HTTP request object
            username: Username for generating the profile URL

        Returns:
            HttpResponse: Rendered profile link partial
        """
        urlpath = reverse("users:profile", kwargs={"username": username})
        return render(
            request, "users/partials/_profile_link.html", {"urlpath": urlpath}
        )

    def _render_reposts(self, request, profile_user):
        """
        Render the reposted posts partial.

        Args:
            request: The HTTP request object
            profile_user: User whose reposts to display

        Returns:
            HttpResponse: Rendered reposts partial
        """
        profile_reposts = profile_user.repostedposts.order_by(
            "-repost__created_at"
        )
        return render(
            request,
            "users/partials/_profile_posts_reposted.html",
            {"profile_reposts": profile_reposts},
        )

    def _render_liked_posts(self, request, profile_user):
        """
        Render the liked posts partial.

        Args:
            request: The HTTP request object
            profile_user: User whose liked posts to display

        Returns:
            HttpResponse: Rendered liked posts partial
        """
        profile_posts_liked = profile_user.likedposts.all().order_by(
            "-likedpost__created_at"
        )
        return render(
            request,
            "users/partials/_profile_posts_liked.html",
            {"profile_posts_liked": profile_posts_liked},
        )

    def _render_bookmarked_posts(self, request):
        """
        Render the bookmarked posts partial for the current user.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered bookmarked posts partial
        """
        profile_posts_bookmarked = request.user.bookmarkedposts.all().order_by(
            "-bookmarkedpost__created_at"
        )
        return render(
            request,
            "users/partials/_profile_posts_bookmarked.html",
            {"profile_posts_bookmarked": profile_posts_bookmarked},
        )

    def _get_main_context(self, request, profile_user):
        """
        Prepare the main context for the profile view.

        Args:
            request: The HTTP request object
            profile_user: User whose profile to display

        Returns:
            dict: Context dictionary with profile data
        """
        # Use PostSortingMixin method
        profile_posts = self.get_sorted_posts(profile_user)
        profile_user_likes = profile_user.posts.aggregate(
            total_likes=Count("likes")
        )["total_likes"]

        return {
            "page": "Profile",
            "profile_user": profile_user,
            "profile_user_likes": profile_user_likes,
            "profile_posts": profile_posts,
        }


class VerificationCodeView(View):
    """
    View for generating and sending email verification codes.

    Generates a 6-digit verification code, stores it in cache for 5 minutes,
    and sends it asynchronously to the provided email address.
    """

    CODE_LENGTH = 6
    CODE_MIN = 100000
    CODE_MAX = 999999
    CODE_TIMEOUT = 300  # 5 minutes in seconds
    CACHE_KEY_PREFIX = "verification_code_"

    # Email configuration
    EMAIL_SUBJECT = "Votre code de vérification ProjetDev"
    EMAIL_SENDER = "no-reply@ProjetDev.com"

    # Response messages
    MSG_EMAIL_REQUIRED = '<p class="error">Email est nécessaire.</p>'
    MSG_INVALID_EMAIL = '<p class="error">Adresse e-mail non valide.</p>'
    MSG_SUCCESS = (
        '<p class="success">Code de vérification envoyé à votre email !</p>'
    )

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for verification code generation.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Success or error message
        """
        email = request.GET.get("email")

        # Validate email presence
        if not email:
            return self._error_response(self.MSG_EMAIL_REQUIRED)

        # Validate email format
        if not self._is_valid_email(email):
            return self._error_response(self.MSG_INVALID_EMAIL)

        # Generate and store verification code
        code = self._generate_code()
        self._store_code(email, code)

        # Send verification email
        self._send_verification_email(email, code)

        return self._success_response()

    def _is_valid_email(self, email):
        """
        Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            bool: True if email is valid, False otherwise
        """
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def _generate_code(self):
        """
        Generate a random 6-digit verification code.

        Returns:
            str: Generated verification code
        """
        return str(random.randint(self.CODE_MIN, self.CODE_MAX))

    def _store_code(self, email, code):
        """
        Store verification code in cache with expiration.

        Args:
            email: Email address associated with the code
            code: Verification code to store
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}{email}"
        cache.set(cache_key, code, timeout=self.CODE_TIMEOUT)

    def _send_verification_email(self, email, code):
        """
        Send verification code via email asynchronously.

        Args:
            email: Recipient email address
            code: Verification code to send
        """
        subject = self.EMAIL_SUBJECT
        message = self._get_email_message(code)
        sender = self.EMAIL_SENDER
        recipients = [email]

        send_email_async(subject, message, sender, recipients)

    def _get_email_message(self, code):
        """
        Generate the email message body.

        Args:
            code: Verification code to include in message

        Returns:
            str: Formatted email message
        """
        timeout_minutes = self.CODE_TIMEOUT // 60
        return (
            f"Utilisez ce code pour vous inscrire: {code}. "
            f"Il expire dans {timeout_minutes} minutes."
        )

    def _error_response(self, message):
        """
        Generate an error HTTP response.

        Args:
            message: Error message to display

        Returns:
            HttpResponse: Error response
        """
        return HttpResponse(message)

    def _success_response(self):
        """
        Generate a success HTTP response.

        Returns:
            HttpResponse: Success response
        """
        return HttpResponse(self.MSG_SUCCESS)


class ProfileEditView(LoginRequiredMixin, HTMXTemplateMixin, TemplateView):
    """
    View for editing user profile information.

    Allows authenticated users to update their profile details including
    personal information and profile picture. Supports HTMX partial rendering.
    """

    template_name = "users/profile_edit.html"
    partial_template = "users/partials/_profile_edit.html"
    form_class = ProfileForm

    def get_context_data(self, **kwargs):
        """
        Add profile form to the template context.

        Args:
            **kwargs: Additional context data

        Returns:
            dict: Context dictionary with form
        """
        context = super().get_context_data(**kwargs)
        context["form"] = self._get_form()
        return context

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for profile updates.

        Args:
            request: The HTTP request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        form = self._get_form(data=request.POST, files=request.FILES)

        if form.is_valid():
            return self._form_valid(form)

        return self._form_invalid(form)

    def _get_form(self, data=None, files=None):
        """
        Instantiate the profile form.

        Args:
            data: POST data (optional)
            files: Uploaded files (optional)

        Returns:
            ProfileForm: Form instance
        """
        return self.form_class(
            data=data, files=files, instance=self.request.user
        )

    def _form_valid(self, form):
        """
        Handle valid form submission.

        Args:
            form: Valid form instance

        Returns:
            HttpResponseRedirect: Redirect to profile page
        """
        form.save()
        return redirect("users:profile", self.request.user.username)

    def _form_invalid(self, form):
        """
        Handle invalid form submission.

        Args:
            form: Invalid form instance with errors

        Returns:
            HttpResponse: Rendered template with form errors
        """
        context = {"form": form}
        return self.render_to_response(context)


class SettingsView(LoginRequiredMixin, View):
    """
    View for managing user settings.

    Handles email updates, email verification, birthday settings,
    dark mode toggle, and notification preferences. Supports HTMX
    partial rendering for a seamless user experience.
    """

    template_name = "users/settings.html"
    partial_template = "users/partials/_settings.html"

    # Template paths for partials
    TEMPLATE_EMAIL = "users/partials/_settings_email.html"
    TEMPLATE_VERIFICATION = "users/partials/_settings_verification.html"
    TEMPLATE_BIRTHDAY = "users/partials/_settings_birthday.html"

    # Cache configuration
    CACHE_KEY_PREFIX = "verification_code_"

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for settings page and partials.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered settings page or partial
        """
        # Email form partial
        if request.GET.get("email"):
            return self._render_email_form(request)

        # Verification partial
        if request.GET.get("verification"):
            return self._render_verification_form(request)

        # Birthday form partial
        if request.GET.get("birthday"):
            return self._render_birthday_form(request)

        # Dark mode toggle
        if request.GET.get("darkmode"):
            return self._toggle_darkmode(request)

        # HTMX partial or full page
        return self._render_main_page(request)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for settings updates.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect or rendered template with errors
        """
        # Email update
        if request.POST.get("email"):
            return self._handle_email_update(request)

        # Verification code
        if request.POST.get("code"):
            return self._handle_verification_code(request)

        # Birthday update
        if request.POST.get("birthday"):
            return self._handle_birthday_update(request)

        # Notifications toggle
        if request.POST.get("notifications"):
            return self._toggle_notifications(request)

        # Default behavior
        return self._render_main_page(request)

    # ========== GET Methods ==========

    def _render_email_form(self, request):
        """
        Render the email form partial.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered email form partial
        """
        form = EmailForm(instance=request.user)
        return render(request, self.TEMPLATE_EMAIL, {"form": form})

    def _render_verification_form(self, request):
        """
        Render the verification form partial.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered verification form partial
        """
        return render(request, self.TEMPLATE_VERIFICATION)

    def _render_birthday_form(self, request):
        """
        Render the birthday form partial.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered birthday form partial
        """
        form = BirthdayForm(instance=request.user)
        return render(request, self.TEMPLATE_BIRTHDAY, {"form": form})

    def _toggle_darkmode(self, request):
        """
        Toggle dark mode preference for the user.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Empty response
        """
        dark_value = request.GET.get("darkmode") == "true"
        request.user.darkmode = dark_value
        request.user.save()
        return HttpResponse("")

    def _render_main_page(self, request):
        """
        Render the main settings page or HTMX partial.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered settings page
        """
        form = EmailForm(instance=request.user)
        template = (
            self.partial_template if request.htmx else self.template_name
        )
        return render(request, template, {"form": form})

    # ========== POST Methods ==========

    def _handle_email_update(self, request):
        """
        Handle email update submission.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        form = EmailForm(request.POST, instance=request.user)
        current_email = request.user.email

        if form.is_valid():
            new_email = form.cleaned_data["email"]

            if new_email != current_email:
                form.save()
                self._update_email_address(request.user, new_email)
                return redirect("users:settings")

        return render(request, self.TEMPLATE_EMAIL, {"form": form})

    def _update_email_address(self, user, new_email):
        """
        Update the EmailAddress object and mark as unverified.

        Args:
            user: User instance
            new_email: New email address
        """
        email_obj = EmailAddress.objects.get(user=user, primary=True)
        email_obj.email = new_email
        email_obj.verified = False
        email_obj.save()

    def _handle_verification_code(self, request):
        """
        Handle email verification code submission.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        code = request.POST.get("code", "").strip()
        email = request.user.email
        cached_code = cache.get(f"{self.CACHE_KEY_PREFIX}{email}")

        if cached_code and cached_code == code:
            self._verify_email(request.user)
            return redirect("users:settings")

        # Return error if code is invalid
        return render(
            request,
            self.TEMPLATE_VERIFICATION,
            {"error": "Code de vérification invalide ou expiré."},
        )

    def _verify_email(self, user):
        """
        Mark user's email as verified.

        Args:
            user: User instance
        """
        email_obj = EmailAddress.objects.get(user=user, primary=True)
        email_obj.verified = True
        email_obj.save()

    def _handle_birthday_update(self, request):
        """
        Handle birthday update submission.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Redirect on success or form with errors
        """
        form = BirthdayForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            return redirect("users:settings")

        return render(request, self.TEMPLATE_BIRTHDAY, {"form": form})

    def _toggle_notifications(self, request):
        """
        Toggle notification preferences for the user.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Empty response
        """
        request.user.notifications = request.POST.get("notifications") == "on"
        request.user.save()
        return HttpResponse("")


class DeleteAccountView(LoginRequiredMixin, View):
    """
    View for deleting user accounts.

    Displays a confirmation page and handles permanent account deletion.
    User is logged out before account deletion for security purposes.
    """

    template_name = "users/profile_delete.html"
    success_url_name = "posts:home"

    # Confirmation message
    DELETION_SUCCESS_MESSAGE = "Votre compte a été supprimé avec succès."

    def get(self, request, *args, **kwargs):
        """
        Display the account deletion confirmation page.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponse: Rendered confirmation page
        """
        context = self._get_context_data()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handle account deletion request.

        Args:
            request: The HTTP request object

        Returns:
            HttpResponseRedirect: Redirect to home page after deletion
        """
        user = request.user

        # Perform account deletion
        self._delete_account(request, user)

        # Add success message
        self._add_success_message(request)

        # Redirect to home page
        return self._get_success_redirect()

    def _get_context_data(self):
        """
        Prepare context data for the template.

        Returns:
            dict: Context dictionary
        """
        return {
            "page_title": "Supprimer le compte",
        }

    def _delete_account(self, request, user):
        """
        Delete the user account after logging out.

        Args:
            request: The HTTP request object
            user: User instance to delete
        """
        # Logout user before deletion for security
        logout(request)

        # Permanently delete the account
        user.delete()

    def _add_success_message(self, request):
        """
        Add a success message to be displayed after deletion.

        Args:
            request: The HTTP request object
        """
        messages.success(request, self.DELETION_SUCCESS_MESSAGE)

    def _get_success_redirect(self):
        """
        Get the redirect response after successful deletion.

        Returns:
            HttpResponseRedirect: Redirect to home page
        """
        return redirect(self.success_url_name)
