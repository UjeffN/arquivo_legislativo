
"""
Configurações do Sistema de Arquivo Digital - Câmara Municipal de Parauapebas
"""

import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
IS_TEST_ENV = 'test' in sys.argv

def _env_bool(var_name, default=False):
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(var_name, required=False):
    raw_value = os.getenv(var_name, '')
    values = [item.strip() for item in raw_value.split(',') if item.strip()]
    if values:
        return values
    if required:
        raise ImproperlyConfigured(
            f'A variável de ambiente {var_name} é obrigatória e não foi definida.'
        )
    return []


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY deve ser definida no ambiente.')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _env_bool('DEBUG', False)

# Configuração de path (lido do .env)
USE_X_FORWARDED_HOST = _env_bool('USE_X_FORWARDED_HOST', True)
FORCE_SCRIPT_NAME = os.getenv('FORCE_SCRIPT_NAME', '/arquivo')
if IS_TEST_ENV:
    FORCE_SCRIPT_NAME = None
URL_PREFIX = FORCE_SCRIPT_NAME or ''

# Configuração de redirecionamento de login/logout
LOGIN_REDIRECT_URL = f'{URL_PREFIX}/dashboard/'
LOGOUT_REDIRECT_URL = f'{URL_PREFIX}/accounts/login/'
LOGIN_URL = f'{URL_PREFIX}/accounts/login/'
LOGOUT_URL = f'{URL_PREFIX}/accounts/logout/'

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', required=True)
if IS_TEST_ENV:
    for test_host in ('testserver', 'localhost', '127.0.0.1'):
        if test_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(test_host)

# Configurações de CSRF para produção (Proxy Reverso)
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS', required=False)
if IS_TEST_ENV and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = ['http://testserver', 'http://localhost', 'http://127.0.0.1']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps do projeto
    'apps.core',
    'apps.documentos',
    'apps.caixas',
    'apps.departamentos',
    'apps.auditoria',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.auditoria.signals.AuditoriaMiddleware',
]

ROOT_URLCONF = 'config.urls'

# Configurações de Sessão
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 horas em segundos
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_DOMAIN = None  # Permitir todos os domínios permitidos
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'Lax'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Belem'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = f'{URL_PREFIX}/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (Uploads)
# https://docs.djangoproject.com/en/4.2/howto/media-files/
MEDIA_URL = f'{URL_PREFIX}/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Limites de Upload do Django
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 524288000  # 500MB

# Configurações específicas do Sistema de Arquivo Digital
ARQUIVO_DIGITAL_CONFIG = {
    # Tipos de documento padrão
    'TIPOS_DOCUMENTO': [
        'Lei',
        'Portaria',
        'Moção',
        'Memorando',
        'Ofício',
        'Requerimento',
        'Decreto',
        'Resolução',
        'Parecer',
        'Contrato',
    ],

    # Configurações de upload
    'MAX_UPLOAD_SIZE': 500 * 1024 * 1024,  # 500MB por arquivo
    'ALLOWED_EXTENSIONS': ['.pdf'],

    # Configurações de OCR
    'OCR_ENABLED': True,
    'OCR_LANGUAGE': 'por',

    # Configurações de etiquetas
    'ETIQUETA_DIMENSAO': '100mm x 150mm',
    'ETIQUETA_DPI': 300,
}

# Configurações de logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'auditoria': {
            'format': '{asctime} - {name} - {levelname} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'auditoria_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'auditoria.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 10,
            'formatter': 'auditoria',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'auditoria': {
            'handlers': ['auditoria_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# Configurações específicas dos módulos
AUDITORIA_CONFIG = {
    'ATIVO': True,
    'NIVEL_LOG_PADRAO': 'INFO',
    'REGISTRAR_TODOS_ACESSOS': True,
    'LIMPEZA_AUTOMATICA': True,
    'DIAS_RETENCAO_PADRAO': 365,
    'MAX_LOGS_POR_LIMPEZA': 10000,
}

# Configurações de segurança para produção
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', not DEBUG)

# Headers de segurança
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
X_FRAME_OPTIONS = 'DENY'
# Servir arquivos estáticos em produção (via Whitenoise)
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    # Adicionar middleware Whitenoise
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Criar diretório de logs
os.makedirs(BASE_DIR / 'logs', exist_ok=True)
