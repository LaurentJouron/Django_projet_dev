from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.utils.timezone import now

from .models import Visit


class VisitStatsService:
    """
    Service centralisant toutes les statistiques de visites.
    Utilisé par l'admin et potentiellement par l'API.
    """

    CACHE_KEY = "visit_admin_stats"
    CACHE_TIMEOUT = 300  # 5 minutes

    def get_stats(self):
        stats = cache.get(self.CACHE_KEY)

        if stats is None:
            stats = self._compute_stats()
            cache.set(self.CACHE_KEY, stats, self.CACHE_TIMEOUT)

        return stats

    def invalidate_cache(self):
        cache.delete(self.CACHE_KEY)

    # ======================
    # Internal computations
    # ======================

    def _compute_stats(self):
        today = now().date()

        return {
            "total_visits": Visit.objects.count(),
            "authenticated_visits": Visit.objects.filter(
                is_authenticated=True
            ).count(),
            "anonymous_visits": Visit.objects.filter(
                is_authenticated=False
            ).count(),
            "visits_today": Visit.objects.filter(
                timestamp__date=today
            ).count(),
            "visits_week": Visit.objects.filter(
                timestamp__gte=now() - timedelta(days=7)
            ).count(),
            "visits_month": Visit.objects.filter(
                timestamp__gte=now() - timedelta(days=30)
            ).count(),
            "top_paths": list(
                Visit.objects.values("path")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            ),
            "top_users": list(
                Visit.objects.filter(user__isnull=False)
                .values("user__username")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            ),
        }
