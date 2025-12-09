import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.views import View
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.db import transaction
from .models import Follow

logger = logging.getLogger(__name__)
User = get_user_model()


class FollowView(LoginRequiredMixin, View):
    """
    Vue sécurisée pour gérer le follow/unfollow d'utilisateurs.

    Sécurités implémentées:
    - LoginRequiredMixin: Authentification obligatoire
    - CSRF protection: Automatique avec Django (POST)
    - Transaction atomique: Évite les race conditions
    - Validation des entrées
    - Logging des actions
    - Never cache: Évite les problèmes de cache
    - Protection contre auto-follow
    - Protection contre les comptes inactifs
    """

    template_button = "network/partials/_follow_button.html"
    template_round = "network/partials/_follow_round.html"

    @method_decorator(never_cache)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, *args, **kwargs):
        """
        Sécurité: Force la méthode POST uniquement et désactive le cache
        """
        return super().dispatch(*args, **kwargs)

    def post(self, request, username):
        """
        Gère le follow/unfollow d'un utilisateur de manière sécurisée.

        Args:
            request: La requête HTTP
            username: Le nom d'utilisateur à follow/unfollow

        Returns:
            HttpResponse: Template du bouton follow mis à jour
        """
        # Validation: récupération de l'utilisateur cible
        this_user = get_object_or_404(User, username=username)

        # Sécurité: empêcher de se suivre soi-même
        if this_user == request.user:
            logger.warning(
                f"User {request.user.username} attempted to follow themselves"
            )
            return HttpResponseBadRequest(
                "Vous ne pouvez pas vous suivre vous-même"
            )

        # Sécurité: empêcher de suivre un compte inactif
        if not this_user.is_active:
            logger.warning(
                f"User {request.user.username} attempted to follow inactive user {username}"
            )
            return HttpResponseBadRequest("Cet utilisateur n'est plus actif")

        # Transaction atomique pour éviter les race conditions
        with transaction.atomic():
            follow_obj, created = Follow.objects.get_or_create(
                follower=request.user, following=this_user
            )

            if not created:
                # Unfollow
                follow_obj.delete()
                action = "unfollowed"
                logger.info(
                    f"User {request.user.username} unfollowed {username}"
                )
            else:
                # Follow
                action = "followed"
                logger.info(
                    f"User {request.user.username} followed {username}"
                )
        # Recharger les utilisateurs pour avoir les compteurs à jour
        this_user.refresh_from_db()
        request.user.refresh_from_db()

        # Préparation du contexte avec les bonnes variables
        context = {
            "this_user": this_user,
            "profile_user": this_user,
            "user": request.user,
            "follow_clicked": True,
            "request": request,
        }

        # Sélection du template en fonction du paramètre
        template_name = (
            self.template_round
            if request.GET.get("follow_round")
            else self.template_button
        )

        return render(request, template_name=template_name, context=context)
