import logging

from django.core.cache import cache
from django.views import View

from .models import Visit
from .services import VisitStatsService

logger = logging.getLogger(__name__)


class BaseVisitView(View):
    """
    Base view used to record page visits and expose visit statistics.
    """

    stats_service = VisitStatsService()

    def record_page_visit(self, request):
        """
        Record a page visit and invalidate related caches.
        """
        try:
            Visit.objects.create(
                path=request.path,
                user=request.user if request.user.is_authenticated else None,
                is_authenticated=request.user.is_authenticated,
            )
            self._invalidate_visit_cache(request.path)
        except Exception as exc:
            logger.error(
                "Failed to record page visit",
                exc_info=exc,
            )

    # ======================
    # Cache invalidation
    # ======================

    def _invalidate_visit_cache(self, path):
        """
        Invalidate all visit-related caches.
        """
        cache.delete_many(
            [
                "total_visit_count",
                f"page_visit_count_{path}",
                f"page_visit_percentage_{path}",
            ]
        )

        # Admin / analytics cache
        self.stats_service.invalidate_cache()

    # ======================
    # Page-level statistics
    # ======================

    def get_total_visit_count(self):
        cache_key = "total_visit_count"
        count = cache.get(cache_key)

        if count is None:
            count = Visit.objects.count()
            cache.set(cache_key, count, 300)

        return count

    def get_page_visit_count(self, path):
        cache_key = f"page_visit_count_{path}"
        count = cache.get(cache_key)

        if count is None:
            count = Visit.objects.filter(path=path).count()
            cache.set(cache_key, count, 300)

        return count

    def get_page_visit_percentage(self, path):
        cache_key = f"page_visit_percentage_{path}"
        percentage = cache.get(cache_key)

        if percentage is None:
            total_count = self.get_total_visit_count()

            if total_count == 0:
                percentage = 0.0
            else:
                page_count = self.get_page_visit_count(path)
                percentage = round((page_count / total_count) * 100, 2)

            cache.set(cache_key, percentage, 300)

        return percentage
