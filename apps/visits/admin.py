from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib.sites.models import Site

from .models import Visit
from .services import VisitStatsService


class PathTypeFilter(admin.SimpleListFilter):
    title = _("Type de page")
    parameter_name = "path_type"

    def lookups(self, request, model_admin):
        return (
            ("home", _("Accueil")),
            ("admin", _("Administration")),
            ("visits", _("Visit")),
            ("other", _("Autre")),
        )

    def queryset(self, request, queryset):
        value = self.value()

        if value == "home":
            return queryset.filter(path__in=["/", ""])
        if value == "admin":
            return queryset.filter(path__contains="/admin")
        if value == "visits":
            return queryset.filter(path__contains="/visit")
        if value == "other":
            return (
                queryset.exclude(path__contains="/admin")
                .exclude(path__contains="/visit")
                .exclude(path__in=["/", ""])
            )
        return queryset


class AuthenticationFilter(admin.SimpleListFilter):
    title = _("Statut d'authentification")
    parameter_name = "auth_status"

    def lookups(self, request, model_admin):
        return (
            ("authenticated", _("Connecté")),
            ("anonymous", _("Anonyme")),
        )

    def queryset(self, request, queryset):
        if self.value() == "authenticated":
            return queryset.filter(is_authenticated=True)
        if self.value() == "anonymous":
            return queryset.filter(is_authenticated=False)
        return queryset


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "colored_user",
        "colored_path",
        "formatted_timestamp",
        "time_ago",
        "day_of_week",
        "auth_badge",
    )

    list_display_links = ("id", "colored_path")

    list_filter = (
        ("timestamp", admin.DateFieldListFilter),
        PathTypeFilter,
        AuthenticationFilter,
        "user",
    )

    search_fields = ("id", "path", "user__username", "user__email")
    ordering = ("-timestamp",)

    list_per_page = 50
    list_max_show_all = 1000

    actions = ("export_as_json",)

    readonly_fields = (
        "id",
        "user",
        "path",
        "timestamp",
        "is_authenticated",
        "formatted_timestamp",
        "full_url_display",
    )

    fieldsets = (
        (_("Utilisateur"), {"fields": ("user", "is_authenticated")}),
        (
            _("Informations de visite"),
            {"fields": ("id", "path", "full_url_display")},
        ),
        (
            _("Horodatage"),
            {
                "fields": ("timestamp", "formatted_timestamp", "time_ago"),
                "description": _("Date et heure de la visite"),
            },
        ),
    )

    stats_service = VisitStatsService()

    # ========= Permissions =========

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # ========= Changelist =========

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(self.stats_service.get_stats())
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description="Il y a")
    def time_ago(self, obj):
        from django.utils.timezone import now

        if not obj.timestamp:
            return "-"

        diff = now() - obj.timestamp

        if diff.days > 365:
            years = diff.days // 365
            return f"il y a {years} an{'s' if years > 1 else ''}"
        if diff.days > 30:
            months = diff.days // 30
            return f"il y a {months} mois"
        if diff.days > 0:
            return f"il y a {diff.days} jour{'s' if diff.days > 1 else ''}"
        if diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"il y a {hours} heure{'s' if hours > 1 else ''}"
        if diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"il y a {minutes} minute{'s' if minutes > 1 else ''}"

        return "à l’instant"

    # ========= Display =========

    @admin.display(description=_("Utilisateur"), ordering="user__username")
    def colored_user(self, obj):
        if obj.user:
            return format_html(
                '<span style="background:#e3f2fd;color:#1976d2;padding:3px 8px;'
                'border-radius:12px;font-size:12px;">👤 {}</span>',
                obj.user.username,
            )
        return format_html('<span style="color:#999;">👻 Anonyme</span>')

    @admin.display(description=_("Statut"))
    def auth_badge(self, obj):
        color = "#4caf50" if obj.is_authenticated else "#9e9e9e"
        label = "✓ Connecté" if obj.is_authenticated else "○ Anonyme"
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            color,
            label,
        )

    @admin.display(description=_("Chemin"), ordering="path")
    def colored_path(self, obj):
        if not obj.path:
            return "-"

        color = "#0066cc"
        if "/admin" in obj.path:
            color = "#dc3545"
        elif "/api" in obj.path:
            color = "#28a745"
        elif obj.path in ("", "/"):
            color = "#6c757d"

        display_path = (
            obj.path if len(obj.path) <= 60 else f"{obj.path[:57]}..."
        )

        return format_html(
            '<code style="color:{};background:#f5f5f5;padding:2px 6px;'
            'border-radius:4px;">{}</code>',
            color,
            display_path,
        )

    @admin.display(description=_("Date et heure"), ordering="timestamp")
    def formatted_timestamp(self, obj):
        return (
            obj.timestamp.strftime("%d/%m/%Y à %H:%M:%S")
            if obj.timestamp
            else "-"
        )

    @admin.display(description=_("Jour"))
    def day_of_week(self, obj):
        days = {
            0: "Lundi",
            1: "Mardi",
            2: "Mercredi",
            3: "Jeudi",
            4: "Vendredi",
            5: "Samedi",
            6: "Dimanche",
        }
        return days.get(obj.timestamp.weekday(), "-") if obj.timestamp else "-"

    @admin.display(description=_("URL complète"))
    def full_url_display(self, obj):
        if not obj.path:
            return "-"

        try:
            domain = Site.objects.get_current().domain
        except Exception:
            domain = "localhost:8000"

        url = f"https://{domain}{obj.path}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

    # ========= Actions =========

    @admin.action(description=_("Exporter en JSON"))
    def export_as_json(self, request, queryset):
        from django.http import JsonResponse

        data = list(
            queryset.values(
                "id",
                "path",
                "timestamp",
                "user__username",
                "is_authenticated",
            )
        )

        for item in data:
            if item["timestamp"]:
                item["timestamp"] = item["timestamp"].isoformat()

        response = JsonResponse(
            data, safe=False, json_dumps_params={"indent": 2}
        )
        response["Content-Disposition"] = 'attachment; filename="visits.json"'
        return response
