"""
Configuración del proyecto TejeArte – Escuela de Tejido.
Guía Práctica Semana 12 – Desarrollo de Aplicaciones Web (IS093A).

Los valores sensibles se leen de variables de entorno (ver .env.example).
"""
import os
from pathlib import Path

from django.contrib.messages import constants as messages_constants

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).strip().lower() in {"1", "true", "yes", "si"}


# --------------------------------------------------------------------------
# Seguridad básica
# --------------------------------------------------------------------------
# En producción SECRET_KEY DEBE venir del entorno y rotarse periódicamente.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-inseguro-tejearte-cambiar-en-produccion-0123456789abcdefghijklmnop",
)
DEBUG = env_bool("DJANGO_DEBUG", True)  # Nunca True en producción
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",  # shell_plus, show_urls
    "academia.apps.AcademiaConfig",
]

# --------------------------------------------------------------------------
# Middleware
# En el REQUEST se ejecutan de arriba hacia abajo; en el RESPONSE de abajo
# hacia arriba (orden inverso, tipo "cebolla"/LIFO).
# Los middleware propios van DESPUÉS de AuthenticationMiddleware para poder
# leer request.user.
# --------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # --- Middleware personalizados TejeArte ---
    "academia.middleware.CabecerasSeguridadMiddleware",
    "academia.middleware.AuditoriaMiddleware",
    "academia.middleware.MantenimientoMiddleware",
    "academia.middleware.InactividadSesionMiddleware",
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
                "academia.context_processors.datos_escuela",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Autenticación
# --------------------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "academia:inicio"
LOGOUT_REDIRECT_URL = "academia:inicio"

# --------------------------------------------------------------------------
# Sesiones
# --------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # cookie firmada + tabla django_session
SESSION_COOKIE_AGE = 60 * 30  # 30 minutos
SESSION_COOKIE_NAME = "tejearte_sid"
SESSION_COOKIE_HTTPONLY = True  # JS no puede leer la cookie
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False  # sólo se guarda si session.modified = True

# Inactividad (middleware propio): cierra sesión tras N segundos sin actividad
TEJEARTE_INACTIVIDAD_SEGUNDOS = int(os.environ.get("TEJEARTE_INACTIVIDAD_SEGUNDOS", 15 * 60))
TEJEARTE_MODO_MANTENIMIENTO = env_bool("TEJEARTE_MODO_MANTENIMIENTO", False)

# --------------------------------------------------------------------------
# CSRF y cabeceras de seguridad
# --------------------------------------------------------------------------
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "academia.views.csrf_fallido"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Content-Security-Policy aplicada por CabecerasSeguridadMiddleware.
# Las imágenes de los cursos se cargan por enlace (Unsplash).
TEJEARTE_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://images.unsplash.com; "
    "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
)

# Cuando DEBUG=False (producción, detrás de HTTPS) se endurece todo:
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = 0 if DEBUG else 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Mensajes con clases de Bootstrap
MESSAGE_TAGS = {messages_constants.ERROR: "danger"}

# --------------------------------------------------------------------------
# Logging: auditoría del middleware y de autenticación
# --------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "auditoria": {"format": "{asctime} | {levelname:<7} | {name} | {message}", "style": "{"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "auditoria"},
        "archivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "auditoria.log",
            "maxBytes": 1024 * 1024,
            "backupCount": 3,
            "formatter": "auditoria",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "tejearte.auditoria": {"handlers": ["consola", "archivo"], "level": "INFO", "propagate": False},
        "tejearte.auth": {"handlers": ["consola", "archivo"], "level": "INFO", "propagate": False},
    },
}
