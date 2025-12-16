from pathlib import Path

from config import BASE_DIR
from config import env

APPS_DIR = BASE_DIR / "apps"
PROJECT_DIR = BASE_DIR / "config"
FRONTEND_DIR = BASE_DIR / "frontend"

# https://docs.djangoproject.com/fr/5.1/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)

# https://docs.djangoproject.com/fr/5.1/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []

DJANGO_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
]

THIRD_PARTY_APPS = [
    # Additional apps
    "jazzmin",
    "django_cleanup.apps.CleanupConfig",
    "django_extensions",
    "django_vite",
    "crispy_forms",
    "crispy_tailwind",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "admin_honeypot",
    "django_htmx",
    "widget_tweaks",
]

LOCAL_APPS = [
    # Local apps
    "apps.posts.apps.PostsConfig",
    "apps.users.apps.UsersConfig",
    "apps.network.apps.NetworkConfig",
    "apps.search.apps.SearchConfig",
    "apps.visits.apps.VisitsConfig",
]

# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.visits.middleware.VisitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# ==========================
# Cache Configuration
# ==========================
# https://docs.djangoproject.com/en/dev/ref/settings/#caches

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# https://docs.djangoproject.com/fr/5.1/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation" ".MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".NumericPasswordValidator"
        ),
    },
]

# https://docs.djangoproject.com/fr/5.1/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/fr/5.1/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Internationalization
# https://docs.djangoproject.com/fr/5.1/topics/i18n/
# http://www.i18nguy.com/unicode/language-identifiers.html
# https://docs.djangoproject.com/fr/5.1/ref/settings/#std-setting-LANGUAGE_CODE
LANGUAGE_CODE = "fr-FR"

# https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIME_ZONE = "UTC"

# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True

# https://docs.djangoproject.com/fr/4.2/ref/settings/#std-setting-USE_L10N
USE_L10N = True

# https://docs.djangoproject.com/fr/5.1/ref/settings/#std-setting-USE_TZ
USE_TZ = True

# https://docs.djangoproject.com/fr/5.1/topics/auth/customizing/#other-authentication-sources
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# https://docs.djangoproject.com/fr/5.1/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = "users.CustomUser"

# https://docs.djangoproject.com/fr/5.1/ref/settings/#login-url
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/"

# https://docs.djangoproject.com/fr/5.1/howto/static-files/
# https://docs.djangoproject.com/fr/5.1/ref/settings/#static-root
STATIC_ROOT = Path(
    env("DJANGO_STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
)

# https://docs.djangoproject.com/fr/5.1/ref/settings/#static-url
STATIC_URL = "static/"

# https://docs.djangoproject.com/fr/5.1/ref/settings/#media-root
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", default=str(BASE_DIR / "media")))

# https://docs.djangoproject.com/fr/5.1/ref/settings/#media-url
MEDIA_URL = "/media/"

# https://docs.djangoproject.com/fr/5.1/ref/settings/#staticfiles-dirs
STATICFILES_DIRS = [BASE_DIR / "static"]

# https://docs.djangoproject.com/fr/5.1/ref/settings/#storages
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# https://docs.djangoproject.com/fr/5.1/ref/settings/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# https://docs.djangoproject.com/fr/5.1/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True

# https://docs.djangoproject.com/fr/5.1/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = False

# https://docs.djangoproject.com/fr/5.1/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# https://docs.djangoproject.com/fr/5.1/ref/settings/
EMAIL_CONFIG = env.email(
    "DJANGO_EMAIL_URL",
    default="consolemail://",
)
globals().update(**EMAIL_CONFIG)

# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# https://docs.djangoproject.com/fr/5.1/ref/settings/#admins
ADMINS = [("""Laurent Jouron""", "jouronlaurent@hotmail.com")]

# https://docs.djangoproject.com/fr/5.1/ref/settings/#managers
MANAGERS = ADMINS

# https://github.com/django/django/blob/main/django/utils/log.py
# https://docs.djangoproject.com/fr/5.1/ref/settings/#logging
# https://docs.djangoproject.com/fr/5.1/topics/logging/
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "%(levelname)s %(asctime)s %(module)s "
                "%(process)d %(thread)d %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_FORMS = {"signup": "apps.users.forms.CustomSignupForm"}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

ACCOUNT_USERNAME_BLACKLIST = [
    "admin",
    "superuser",
    "root",
    "webmaster",
    "theboss",
]
