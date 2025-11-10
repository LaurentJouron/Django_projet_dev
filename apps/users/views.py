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

        profile_posts_liked = profile_user.likedposts.all().order_by(
            "-likedpost__created_at"
        )
        profile_user_likes = profile_user.posts.aggregate(
            total_likes=Count("likes")
        )["total_likes"]

        context.update(
            {
                "page": self.page_title,
                "profile_user": profile_user,
                "profile_user_likes": profile_user_likes,
                "profile_posts": profile_posts,
                "profile_posts_liked": profile_posts_liked,
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        if request.GET.get("link"):
            username = self.kwargs.get("username")
            urlpath = reverse("users:profile", kwargs={"username": username})
            return render(
                request,
                "users/partials/_profile_link.html",
                {"urlpath": urlpath},
            )

        if request.GET.get("liked"):
            return render(
                request,
                "users/partials/_profile_posts_liked.html",
                context=context,
            )

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


class VerificationCodeView(View):
    def get(self, request, *args, **kwargs):
        email = request.GET.get("email")
        if not email:
            return HttpResponse('<p class="error">Email est nécessaire.</p>')

        # Email validation
        try:
            validate_email(email)
        except ValidationError:
            return HttpResponse(
                '<p class="error">Adresse e-mail non valide.</p>'
            )

        # Code generation
        code = str(random.randint(100000, 999999))
        cache.set(f"verification_code_{email}", code, timeout=300)

        # Preparation of the email
        subject = "Votre code de vérification ProjetDev"
        message = f"Utilisez ce code pour vous inscrire: {code}. Il expire dans 5 minutes."
        sender = "no-reply@ProjetDev.com"
        recipients = [email]

        # Envoi asynchrone
        send_email_async(subject, message, sender, recipients)

        return HttpResponse(
            '<p class="success">Code de vérification envoyé à votre email !</p>'
        )


class ProfileEditView(LoginRequiredMixin, HTMXTemplateMixin, TemplateView):
    template_name = "users/profile_edit.html"
    partial_template = "users/partials/_profile_edit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ProfileForm(instance=self.request.user)
        context["form"] = form
        return context

    def post(self, request, *args, **kwargs):
        form = ProfileForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            form.save()
            return redirect("users:profile", request.user.username)

        context = {"form": form}
        return self.render_to_response(context)


class SettingsView(LoginRequiredMixin, View):
    template_name = "users/settings.html"
    partial_template = "users/partials/_settings.html"

    def get(self, request, *args, **kwargs):
        form = EmailForm(instance=request.user)

        # --- Email form (GET)
        if request.GET.get("email"):
            return render(
                request,
                "users/partials/_settings_email.html",
                {"form": form},
            )

        # --- Verification view (GET)
        if request.GET.get("verification"):
            return render(
                request, "users/partials/_settings_verification.html"
            )

        # --- Birthday form (GET)
        if request.GET.get("birthday"):
            birthdayform = BirthdayForm(instance=request.user)
            return render(
                request,
                "users/partials/_settings_birthday.html",
                {"form": birthdayform},
            )

        # --- Darkmode toggle (GET)
        if request.GET.get("darkmode"):
            dark_value = request.GET.get("darkmode") == "true"
            request.user.darkmode = dark_value
            request.user.save()
            return HttpResponse("")

        # --- HTMX Partial (GET)
        if request.htmx:
            return render(request, self.partial_template, {"form": form})

        # --- Full Page
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        # --- Email update (POST)
        if request.POST.get("email"):
            form = EmailForm(request.POST, instance=request.user)
            current_email = request.user.email

            if form.is_valid():
                new_email = form.cleaned_data["email"]
                if new_email != current_email:
                    form.save()
                    email_obj = EmailAddress.objects.get(
                        user=request.user, primary=True
                    )
                    email_obj.email = new_email
                    email_obj.verified = False
                    email_obj.save()
                    return redirect("users:settings")

        # --- Verification code (POST)
        if request.POST.get("code"):
            code = request.POST.get("code").strip()
            email = request.user.email
            cached_code = cache.get(f"verification_code_{email}")
            if cached_code and cached_code == code:
                email_obj = EmailAddress.objects.get(
                    user=request.user, primary=True
                )
                email_obj.verified = True
                email_obj.save()
                return redirect("users:settings")

        # --- Birthday form (POST)
        if request.POST.get("birthday"):
            birthdayform = BirthdayForm(request.POST, instance=request.user)
            if birthdayform.is_valid():
                birthdayform.save()
                return redirect("users:settings")

        # --- Notifications toggle (POST)
        if request.POST.get("notifications"):
            request.user.notifications = (
                request.POST.get("notifications") == "on"
            )
            request.user.save()
            return HttpResponse("")

        # Default behavior
        form = EmailForm(instance=request.user)
        return render(request, self.template_name, {"form": form})


class DeleteAccountView(LoginRequiredMixin, View):
    template_name = "users/profile_delete.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        user = request.user
        logout(request)
        user.delete()
        return redirect("posts:home")
