"""
monitoring/settings.py
Configuración Django para BITE.co Sprint 3
Stack: Django + PostgreSQL + MongoDB + RabbitMQ + Auth0
"""
import os
import logging.handlers  # noqa: F401 — requerido para RotatingFileHandler en LOGGING dict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-bite-sprint3-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

# ── Aplicaciones ───────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    # Apps Sprint 2 (migradas de FastAPI)
    'reports',          # Reportes de consumo cloud (+ caché Redis)
    'extractor',        # Extracción de métricas AWS/GCP (Celery + RabbitMQ)
    # Apps Sprint 3
    'credentials',      # ASR29: Vault de credenciales
    'detector',         # ASR29: Detección de anomalías
    'revoker',          # ASR29: Revocación de credenciales
    'notifier',         # ASR29: Notificaciones de seguridad
    'log_handlers',     # ASR30: Enmascaramiento de logs
    'places',           # Disponibilidad: App del Lab 9
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'monitoring.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'monitoring.wsgi.application'

# ── Base de datos PostgreSQL ───────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'monitoring_db'),
        'USER': os.environ.get('DB_USER', 'monitoring_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'isis2503'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# ── MongoDB (Experimento Disponibilidad) ───────────────────
MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb://localhost:27017/bite_db'
)

# ── RabbitMQ ───────────────────────────────────────────────
RABBITMQ = {
    'HOST':              os.environ.get('RABBITMQ_HOST', 'localhost'),
    'PORT':              int(os.environ.get('RABBITMQ_PORT', 5672)),
    'USER':              os.environ.get('RABBITMQ_USER', 'monitoring_user'),
    'PASSWORD':          os.environ.get('RABBITMQ_PASSWORD', 'isis2503'),
    'EXCHANGE_SECURITY': 'security_events',   # ASR29: uso, revocación y alertas
    'EXCHANGE_LOGS':     'logs',              # ASR30: logs enmascarados
}

# ── Vault de credenciales (ASR29) ──────────────────────────
# Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_vault_key_str = os.environ.get('VAULT_KEY', '')
VAULT_KEY = _vault_key_str.encode() if _vault_key_str else None

# ── Auth0 (reutilizado del Lab 8) ─────────────────────────
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN', '')
AUTH0_CLIENT_ID = os.environ.get('AUTH0_CLIENT_ID', '')
AUTH0_CLIENT_SECRET = os.environ.get('AUTH0_CLIENT_SECRET', '')
AUTH0_MGMT_TOKEN = os.environ.get('AUTH0_MGMT_TOKEN', '')

AUTHENTICATION_BACKENDS = [
    'monitoring.auth0backend.Auth0Backend',
    'django.contrib.auth.backends.ModelBackend',
]

SOCIAL_AUTH_AUTH0_DOMAIN = AUTH0_DOMAIN
SOCIAL_AUTH_AUTH0_KEY = AUTH0_CLIENT_ID
SOCIAL_AUTH_AUTH0_SECRET = AUTH0_CLIENT_SECRET

# ── Logging con enmascaramiento (ASR30) ────────────────────
AMBIENTE = os.environ.get('AMBIENTE', 'dev')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'sanitize': {
            '()': 'monitoring.log_filters.SensitiveDataFilter',
        },
    },
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'filters': ['sanitize'],
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Agregar file handler sólo si el directorio de logs existe (producción)
_log_dir = f'/var/log/bite/{AMBIENTE}'
if os.path.isdir(_log_dir):
    LOGGING['handlers']['file'] = {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': f'{_log_dir}/app.log',
        'maxBytes': 10 * 1024 * 1024,
        'backupCount': 5,
        'filters': ['sanitize'],
        'formatter': 'standard',
    }
    LOGGING['root']['handlers'].append('file')

# ── Redis (caché para reportes — ASR Latencia) ────────────
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/0',
        'OPTIONS': {
            'socket_connect_timeout': 2,
            'socket_timeout': 2,
        },
    }
}

# ── Celery (extractor de métricas) ────────────────────────
# Por defecto usa Redis como broker (deploy básico sin RabbitMQ).
# Si RABBITMQ_HOST está configurado, usa RabbitMQ (experimentos ASR29/ASR30).
_rb = RABBITMQ
_default_broker = f'redis://{REDIS_HOST}:{REDIS_PORT}/1'
_rabbit_broker   = f"amqp://{_rb['USER']}:{_rb['PASSWORD']}@{_rb['HOST']}:{_rb.get('PORT', 5672)}//"

CELERY_BROKER_URL     = os.environ.get('CELERY_BROKER_URL',
                            _rabbit_broker if os.environ.get('RABBITMQ_HOST') else _default_broker)
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/2'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT  = ['json']
CELERY_TASK_ACKS_LATE  = True

# ── Internacionalización ───────────────────────────────────
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True
