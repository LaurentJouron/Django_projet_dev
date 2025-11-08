from django import forms
from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["image", "body", "tags", "author"]


class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["body", "tags"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "input-field resize-none",
                    "rows": 2,
                    "placeholder": "Ajoutez une légende ici...",
                    "maxlength": "80",
                }
            ),
            "tags": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "#tags - séparés par un espace",
                    "maxlength": "80",
                }
            ),
        }
