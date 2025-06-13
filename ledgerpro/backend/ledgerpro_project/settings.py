# Placeholder for Django project settings.py
import os
from pathlib import Path
from datetime import timedelta  # Moved E402

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-placeholder-key'  # Replace in production
DEBUG = True
ALLOWED_HOSTS = ['0.0.0.0', 'localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'api',  # Our app
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'ledgerpro_project.urls'
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
WSGI_APPLICATION = 'ledgerpro_project.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # Placeholder, will use PostgreSQL
    }
}
# Password validation (kept for now, might be handled by other auth systems later)
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'api.User'

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

# Simple JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Adjust as needed
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

# SendGrid Configuration
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', 'YOUR_SENDGRID_API_KEY_PLACEHOLDER')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@ledgerpro.example.com')

# Plaid Configuration (Section 7.3)
PLAID_CLIENT_ID = os.environ.get('PLAID_CLIENT_ID', 'YOUR_PLAID_CLIENT_ID')
PLAID_SECRET_SANDBOX = os.environ.get('PLAID_SECRET_SANDBOX', 'YOUR_PLAID_SECRET_SANDBOX')  # For Sandbox
PLAID_SECRET_DEVELOPMENT = os.environ.get('PLAID_SECRET_DEVELOPMENT', 'YOUR_PLAID_SECRET_DEVELOPMENT')  # For Development
PLAID_ENV = os.environ.get('PLAID_ENV', 'sandbox')  # e.g., 'sandbox', 'development', 'production'
PLAID_PRODUCTS = os.environ.get('PLAID_PRODUCTS', 'transactions').split(',')  # e.g., ['transactions']
PLAID_COUNTRY_CODES = os.environ.get('PLAID_COUNTRY_CODES', 'US').split(',')  # e.g., ['US']
# Redirect URI for Plaid Link (OAuth) - often handled by frontend, but backend might need to be aware
PLAID_REDIRECT_URI = os.environ.get('PLAID_REDIRECT_URI', None)
