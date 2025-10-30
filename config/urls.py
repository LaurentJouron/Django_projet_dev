from django.contrib import admin
from django.conf import settings
from django.urls import path, include

urlpatterns = [
    # URLs of the applications
    path("", include("apps.posts.urls", namespace="posts")),
    path("users/", include("apps.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
]

# DEBUG mode specific configuration
if settings.DEBUG:
    from django.conf.urls.static import static
    from debug_toolbar.toolbar import debug_toolbar_urls
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Django administration interface development
    urlpatterns += [
        path("admin/", admin.site.urls),
    ]
    # Static files and media
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
    # Development tools
    urlpatterns += debug_toolbar_urls()
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

else:
    # Django administration interface production
    urlpatterns += [
        path(
            "admin/",
            include("admin_honeypot.urls", namespace="admin_honeypot"),
        ),
        path("secret/", admin.site.urls),
    ]
