"""
Django settings for artskala project.
Configuração segura para LOCAL + RENDER.

Pontos corrigidos:
- Não quebra se DATABASE_URL não existir localmente.
- Em produção usa PostgreSQL do Render quando DATABASE_URL existir.
- Evita erro 500 de ManifestStaticFilesStorage quando um arquivo static citado não foi coletado.
- ALLOWED_HOSTS e CSRF por variável de ambiente.
- Mantém WhiteNoise para servir static em produção.
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# AMBIENTE
# ============================================================

IS_RENDER = os.environ.get("RENDER") is not None

DEBUG = os.environ.get(
    "DEBUG",
    "False" if IS_RENDER else "True"
).strip().lower() in ("1", "true", "yes", "on")

SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-dev-key-change-in-production"
    else:
        raise RuntimeError("SECRET_KEY não configurada no ambiente de produção.")

# ============================================================
# HOSTS / CSRF
# ============================================================

DEBUG=False
DATABASE_URL=sua_url_do_postgresql

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".onrender.com",
]

RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()

if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Permite adicionar hosts manualmente:
# ALLOWED_HOSTS_EXTRA=seudominio.com,www.seudominio.com
extra_hosts = os.environ.get("ALLOWED_HOSTS_EXTRA", "")
for host in [h.strip() for h in extra_hosts.split(",") if h.strip()]:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = []

if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Permite adicionar origens manualmente:
# CSRF_TRUSTED_ORIGINS_EXTRA=https://seudominio.com,https://www.seudominio.com
extra_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS_EXTRA", "")
for origin in [o.strip() for o in extra_csrf.split(",") if o.strip()]:
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# ============================================================
# APPS
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "artskala.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "artskala.wsgi.application"

# ============================================================
# BANCO DE DADOS
# ============================================================
# LOCAL: SQLite automático.
# PRODUÇÃO/RENDER: PostgreSQL quando DATABASE_URL existir.
#
# IMPORTANTE:
# Configure DATABASE_URL nas variáveis de ambiente do Web Service no Render.
# Não coloque usuário/senha direto no settings.py.
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback seguro para desenvolvimento/local.
    # Em produção, use apenas temporariamente se realmente quiser rodar sem Postgres.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ============================================================
# SENHAS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================================================
# I18N
# ============================================================

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC / MEDIA
# ============================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Evita erro 500 em produção quando algum arquivo static citado no template
# não entrou no manifest do collectstatic. É mais tolerante que Manifest.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Em Render, uploads locais em MEDIA_ROOT somem quando o serviço reinicia,
# a menos que você use Persistent Disk ou serviço externo como Cloudinary/S3.

# ============================================================
# LOGIN
# ============================================================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# SEGURANÇA PRODUÇÃO
# ============================================================

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
