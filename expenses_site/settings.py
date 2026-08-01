"""
Django settings for expenses_site project.
"""

import decouple # type: ignore
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING
SECRET_KEY = decouple.config("DJANGO_SECRET_KEY")
DEBUG = True

ALLOWED_HOSTS = [
    ".ngrok-free.app",
    "127.0.0.1",
    "localhost",
]

# Application definition
INSTALLED_APPS = [
    "channels",
    "daphne",
    "dashboard",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "whitenoise.runserver_nostatic",   # <— Added for dev static serving
    "crispy_forms",
    "crispy_bootstrap5",
    "bootstrap5",
    "expense_upload",
    "webhooks",
    "corsheaders",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",   # <— REQUIRED for WhiteNoise
    "whitenoise.middleware.WhiteNoiseMiddleware",      # <— WhiteNoise middleware
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    #"django.middleware.csrf.CsrfViewMiddleware",      # Your choice to disable
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CSRF_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = [
    "https://script.google.com/macros/s/AKfycbwiKKXNs7-UzXcf1eq7_9BoSSCMKuq86ZkrO_EYwSBDWJTTtSplu6P5k-rycpg_wRM7/exec"
]

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "expenses_site.urls"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',        # ✅ required
                'django.contrib.messages.context_processors.messages', # ✅ required
                'django.template.context_processors.static',
            ],
        },
    },
]


WSGI_APPLICATION = "expenses_site.wsgi.application"
ASGI_APPLICATION = "expenses_site.asgi.application"

# Channels / Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": { "hosts": [(REDIS_HOST, 6379)] },
    }
}

# Supabase Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": decouple.config("SUPABASE_DB_PASSWORD"),
        "HOST": decouple.config("SUPABASE_LINK"),
        "PORT": "5432",
    }
}

# Password validators
AUTH_PASSWORD_VALIDATORS = [
    { "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator" },
    { "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator" },
    { "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator" },
    { "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator" },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = False


# Static files
BASE_DIR = Path(__file__).resolve().parent.parent  # goes up two levels

# URL to access static files
STATIC_URL = "/static/"

# Where Django looks for "manual" static files (outside apps)
STATICFILES_DIRS = [
    BASE_DIR / "static",   # ~/expenses_site/static
]

# Where collectstatic copies everything
STATIC_ROOT = BASE_DIR / "staticfiles"  # ~/expenses_site/staticfiles

# Receipt uploads are pipeline state and are kept outside static assets.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
RECEIPT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# WhiteNoise storage (for production + gzip + hashed files)
# Development-friendly storage (copy everything, ignore missing references)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'



DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
