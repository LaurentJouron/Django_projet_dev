from allauth.account.forms import SignupForm
from django import forms
from django.core.cache import cache
from allauth.account.models import EmailAddress
from .models import CustomUser


class CustomSignupForm(SignupForm):
    birthday = forms.DateField()
    code = forms.CharField()

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip()
        email = self.cleaned_data.get("email")
        cached_code = cache.get(f"verification_code_{email}")
        if not cached_code or cached_code != code:
            self.add_error("code", "Code de vérification invalide ou expiré.")

    def save(self, request):
        user = super().save(request)
        user.birthday = self.cleaned_data.get("birthday")
        user.username = user.username.lower()
        user.email = user.email.lower()
        user.save()
        EmailAddress.objects.filter(user=user, email=user.email).update(
            verified=True
        )
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["image", "username", "name", "bio", "website"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Nom d'utilisateur",
                }
            ),
            "name": forms.TextInput(
                attrs={"class": "input-field", "placeholder": "Nom"}
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "input-field resize-none",
                    "rows": 2,
                    "placeholder": "Biographie",
                    "maxlength": "250",
                }
            ),
            "website": forms.TextInput(
                attrs={"class": "input-field", "placeholder": "Site web"}
            ),
        }


class EmailForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["email"]
        widgets = {
            "email": forms.TextInput(
                attrs={"class": "input-field w-full", "placeholder": "Email"}
            ),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if (
            CustomUser.objects.exclude(id=self.instance.id)
            .filter(email=email)
            .exists()
        ):
            raise forms.ValidationError("Cet email est déjà pris.")
        return email


class BirthdayForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["birthday"]
        widgets = {
            "birthday": forms.DateInput(
                attrs={"type": "date", "class": "input-field w-full"}
            ),
        }
