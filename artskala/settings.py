"""
Django settings for artskala.

Ambientes:
- Local: SQLite e DEBUG=True por padrão.
- Vercel: PostgreSQL/Supabase via DATABASE_URL e DEBUG=False.
- Arquivos de mídia: Cloudinary em produção.
- Arquivos estáticos: WhiteNoise.
"""

from pathlib import Path
import os
import secrets

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def add_unique(items: list[str], value: str) -> None:
    value = value.strip()

    if value and value not in items:
        items.append(value)


# ============================================================
# AMBIENTE
# ============================================================

IS_VERCEL = os.environ.get("VERCEL") == "1"
IS_PRODUCTION = IS_VERCEL

# No BUILD a Vercel só importa este arquivo para descobrir o app Django
# (WSGI, arquivos estáticos). Ali as variáveis secretas podem faltar -- num
# deploy de Preview, por exemplo -- e qualquer exceção derruba o build com
# DJANGO_SETTINGS_FAILED. As travas abaixo valem para o site no ar; no build
# entram valores provisórios que nunca atendem visitante nenhum.
# (A Vercel define CI=1 somente durante o build.)
IS_BUILD = IS_VERCEL and os.environ.get("CI", "").strip().lower() in {"1", "true"}
EXIGIR_VARIAVEIS = IS_PRODUCTION and not IS_BUILD

DEBUG = env_bool("DEBUG", default=not IS_PRODUCTION)

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-dev-key-change-me"
    elif IS_BUILD:
        SECRET_KEY = "somente-build-" + secrets.token_urlsafe(32)
    else:
        raise RuntimeError(
            "SECRET_KEY não configurada. "
            "Adicione SECRET_KEY nas Environment Variables da Vercel."
        )


# ============================================================
# HOSTS / CSRF
# ============================================================

ALLOWED_HOSTS = [
    "artskala.com.br",
    "www.artskala.com.br",
    "interno.artskala.com.br",
    "localhost",
    "127.0.0.1",
    "artskala.vercel.app",
]

CSRF_TRUSTED_ORIGINS = [
    "https://artskala.com.br",
    "https://www.artskala.com",
    "https://interno.artskala.com.br",
    "https://artskala.vercel.app",
]

# O Vercel fornece a URL específica de cada deployment.
VERCEL_URL = os.environ.get("VERCEL_URL", "").strip()

if VERCEL_URL:
    add_unique(ALLOWED_HOSTS, VERCEL_URL)
    add_unique(CSRF_TRUSTED_ORIGINS, f"https://{VERCEL_URL}")

# Permite adicionar domínio próprio sem alterar o código.
# ALLOWED_HOSTS_EXTRA=artskala.com.br,www.artskala.com.br
extra_hosts = os.environ.get("ALLOWED_HOSTS_EXTRA", "")

for host in extra_hosts.split(","):
    add_unique(ALLOWED_HOSTS, host)

# CSRF_TRUSTED_ORIGINS_EXTRA=https://artskala.com.br,https://www.artskala.com
extra_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS_EXTRA", "")

for origin in extra_csrf.split(","):
    add_unique(CSRF_TRUSTED_ORIGINS, origin)


# ============================================================
# APLICATIVOS
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "cloudinary_storage",
    "cloudinary",

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
    "core.middleware.InternalDomainMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "artskala.urls"


# ============================================================
# TEMPLATES
# ============================================================

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
                "core.context_processors.carrinho_contexto",
                "core.context_processors.enderecos_site",
                "core.context_processors.menu_site",
                "core.context_processors.gestao_acesso",
            ],
        },
    },
]


WSGI_APPLICATION = "artskala.wsgi.application"


# ============================================================
# BANCO DE DADOS
# ============================================================
#
# LOCAL:
# - Usa SQLite quando DATABASE_URL não existir.
#
# VERCEL:
# - Exige DATABASE_URL.
# - Use a URI Transaction Pooler do Supabase, porta 6543.
# - A senha fica somente nas Environment Variables da Vercel.
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    database_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0,
        ssl_require=True,
    )

    # Necessário para pool em modo Transaction.
    database_config["DISABLE_SERVER_SIDE_CURSORS"] = True

    DATABASES = {
        "default": database_config,
    }

elif EXIGIR_VARIAVEIS:
    raise RuntimeError(
        "DATABASE_URL não configurada. "
        "Adicione a URI Transaction Pooler do Supabase na Vercel."
    )

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ============================================================
# VALIDAÇÃO DE SENHAS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]


# ============================================================
# INTERNACIONALIZAÇÃO
# ============================================================

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True
USE_TZ = True


# ============================================================
# ARQUIVOS ESTÁTICOS
# ============================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = (
    [BASE_DIR / "static"]
    if (BASE_DIR / "static").exists()
    else []
)


# ============================================================
# CLOUDINARY / ARQUIVOS DE MÍDIA
# ============================================================

CLOUDINARY_CLOUD_NAME = os.environ.get(
    "CLOUDINARY_CLOUD_NAME",
    "",
).strip()

CLOUDINARY_API_KEY = os.environ.get(
    "CLOUDINARY_API_KEY",
    "",
).strip()

CLOUDINARY_API_SECRET = os.environ.get(
    "CLOUDINARY_API_SECRET",
    "",
).strip()

USE_CLOUDINARY = all(
    [
        CLOUDINARY_CLOUD_NAME,
        CLOUDINARY_API_KEY,
        CLOUDINARY_API_SECRET,
    ]
)

if USE_CLOUDINARY:
    import cloudinary

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "API_KEY": CLOUDINARY_API_KEY,
        "API_SECRET": CLOUDINARY_API_SECRET,
    }

    STORAGES = {
        "default": {
            "BACKEND": (
                "cloudinary_storage.storage."
                "MediaCloudinaryStorage"
            ),
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage."
                "CompressedStaticFilesStorage"
            ),
        },
    }

    MEDIA_URL = "/media/"

elif EXIGIR_VARIAVEIS:
    raise RuntimeError(
        "Cloudinary não configurado. Adicione "
        "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY e "
        "CLOUDINARY_API_SECRET nas Environment Variables da Vercel."
    )

else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage."
                "CompressedStaticFilesStorage"
            ),
        },
    }

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# LOGIN
# ============================================================

LOGIN_URL = "login"

# E-mail oficial de atendimento (rodapé, home e contato).
EMAIL_CONTATO = os.environ.get("EMAIL_CONTATO", "artskala@gmail.com").strip()

# Endereço da ArtSkala: ponto de partida da distância calculada nos orçamentos.
# ORIGEM_LAT/ORIGEM_LNG são opcionais (sem elas o navegador acha o ponto pelo endereço).
ENDERECO_LOJA = os.environ.get("ENDERECO_LOJA", "Rua Eduardo Zumkeller, 170, São Paulo - SP").strip()
ORIGEM_LAT = os.environ.get("ORIGEM_LAT", "").strip()
ORIGEM_LNG = os.environ.get("ORIGEM_LNG", "").strip()

# Área interna (gestão): fica em /interno/ no próprio site, sem depender de
# subdomínio. Se um dia o DNS de INTERNAL_HOST for apontado para a Vercel, ele
# também abre a gestão (sem o prefixo); o endereço antigo segue aceito.
INTERNAL_HOST = os.environ.get("INTERNAL_HOST", "interno.artskala.com.br").strip().lower()
INTERNAL_HOSTS = {INTERNAL_HOST, "interno.artskala.com.br", "innterno.artskala.com"}

# Site público: por padrão o domínio do interno sem o "interno."
_dominio_site = INTERNAL_HOST.split(".", 1)[1] if INTERNAL_HOST.startswith("interno.") else "artskala.com.br"
SITE_URL = os.environ.get("SITE_URL", f"https://{_dominio_site}").rstrip("/")

for _host in sorted(INTERNAL_HOSTS) + ["artskala.com", "www.artskala.com", _dominio_site, "www." + _dominio_site]:
    add_unique(ALLOWED_HOSTS, _host)
    add_unique(CSRF_TRUSTED_ORIGINS, "https://" + _host)

# Erros 500 e avisos vão para o log da Vercel (Deployments > Logs). Sem
# isto o Django em produção não mostra o motivo de um erro em lugar nenhum.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# Instagram automático (core/instagram.py): token da "Instagram API com login
# do Instagram" e o segredo que o agendador da Vercel envia (CRON_SECRET).
INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN", "").strip()
CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()

# Aplica migrações pendentes quando o site sobe (core/auto_migracao.py).
MIGRAR_AO_INICIAR = env_bool("MIGRAR_AO_INICIAR", EXIGIR_VARIAVEIS and bool(DATABASE_URL))
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# ============================================================
# PADRÕES DO DJANGO
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# SEGURANÇA EM PRODUÇÃO
# ============================================================

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if GOOGLE_LOGIN_ENABLED:
    INSTALLED_APPS += ["allauth", "allauth.account", "allauth.socialaccount", "allauth.socialaccount.providers.google"]
    MIDDLEWARE += ["allauth.account.middleware.AccountMiddleware"]
    AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]
    SOCIALACCOUNT_PROVIDERS = {"google": {"APP": {"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}, "SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}, "OAUTH_PKCE_ENABLED": True}}
    SOCIALACCOUNT_LOGIN_ON_GET = False
    SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
    SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
    ACCOUNT_LOGIN_METHODS = {"username", "email"}
    ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
    LOGIN_REDIRECT_URL = "/"
