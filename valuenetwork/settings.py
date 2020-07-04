#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, sys
from django.utils.translation import ugettext_lazy as _
from decimal import Decimal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PACKAGE_ROOT = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DEBUG = True

# settings.TESTING will be True in a testing enviroment.
TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

ADMINS = (
    # ("Your Name", "your_email@example.com"),
)

MANAGERS = ADMINS

ALLOWED_HOSTS = ['127.0.0.1', 'localhost'] # Set the allowed host domains list at local_settings.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "valuenetwork.sqlite",
    }
}

TIME_ZONE = "UTC"

SITE_ID = 1

USE_TZ = True

MEDIA_ROOT = os.path.join(PACKAGE_ROOT, "site_media", "media")

MEDIA_URL = "/site_media/media/"

STATIC_ROOT = os.path.join(PACKAGE_ROOT, "site_media", "static")

STATIC_URL = "/site_media/static/"

STATICFILES_DIRS = [
    os.path.join(PACKAGE_ROOT, "static"),
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = "use ./manage.py generate_secret_key to make this"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PACKAGE_ROOT, "templates"),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                #'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                "django.template.context_processors.request",
                'django.contrib.messages.context_processors.messages',
                "pinax_utils.context_processors.settings",
                "account.context_processors.account",
                "fobi.context_processors.theme",
            ],
            'debug': DEBUG,
        },
    },
]

LOGIN_URL = '/account/login/'

LOGIN_EXEMPT_URLS = [
    r"^$",
    r'^membership/',
    r'^membershipthanks/',
    r'^joinaproject/',
    r'^join/',
    r'^joinaproject-thanks/',
    r'^work/payment-url/',
    r'^account/password/reset/',
    r'^account/password_reset_sent/',
    r'^captcha/image/',
    r'^i18n/',
    r'^robots.txt$',
]


# projects login settings
PROJECTS_LOGIN = {} # Fill the object in local_settings.py with custom login data by project


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    #'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'valuenetwork.login_required_middleware.LoginRequiredMiddleware',
    'account.middleware.LocaleMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
]

ROOT_URLCONF = "valuenetwork.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "valuenetwork.wsgi.application"

INSTALLED_APPS = [
    'modeltranslation', # to provide translations of model fields
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_comments",

    # theme
    "pinax_theme_bootstrap_account",
    "pinax_theme_bootstrap",

     # internalized pinax_forms_bootstrap v2.0.3.post1
     # to solve Django > 1.10 compatibility
    "forms_bootstrap2",

    # external
    #'debug_toolbar',
    'django_extensions',
    'easy_thumbnails',
    #'report_builder',
    'pinax.notifications',
    'corsheaders',
    #'django_filters',
    'rest_framework',
    'graphene_django',
    'captcha',

    # `django-fobi` core
    'fobi',

    # `django-fobi` themes
    'fobi.contrib.themes.bootstrap3', # Bootstrap 3 theme
    'fobi.contrib.themes.foundation5', # Foundation 5 theme
    'fobi.contrib.themes.simple', # Simple theme

    # `django-fobi` form elements - fields
    'fobi.contrib.plugins.form_elements.fields.boolean',
    'fobi.contrib.plugins.form_elements.fields.checkbox_select_multiple',
    'fobi.contrib.plugins.form_elements.fields.date',
    'fobi.contrib.plugins.form_elements.fields.date_drop_down',
    'fobi.contrib.plugins.form_elements.fields.datetime',
    'fobi.contrib.plugins.form_elements.fields.decimal',
    'fobi.contrib.plugins.form_elements.fields.email',
    'fobi.contrib.plugins.form_elements.fields.file',
    'fobi.contrib.plugins.form_elements.fields.float',
    'fobi.contrib.plugins.form_elements.fields.hidden',
    'fobi.contrib.plugins.form_elements.fields.input',
    'fobi.contrib.plugins.form_elements.fields.integer',
    'fobi.contrib.plugins.form_elements.fields.ip_address',
    'fobi.contrib.plugins.form_elements.fields.null_boolean',
    'fobi.contrib.plugins.form_elements.fields.password',
    'fobi.contrib.plugins.form_elements.fields.radio',
    #'fobi.contrib.plugins.form_elements.fields.regex',
    'fobi.contrib.plugins.form_elements.fields.select',
    'fobi.contrib.plugins.form_elements.fields.select_model_object',
    'fobi.contrib.plugins.form_elements.fields.select_multiple',
    'fobi.contrib.plugins.form_elements.fields.select_multiple_model_objects',
    'fobi.contrib.plugins.form_elements.fields.slug',
    'fobi.contrib.plugins.form_elements.fields.text',
    'fobi.contrib.plugins.form_elements.fields.textarea',
    'fobi.contrib.plugins.form_elements.fields.time',
    'fobi.contrib.plugins.form_elements.fields.url',

    # `django-fobi` form elements - content elements
    'fobi.contrib.plugins.form_elements.test.dummy',
    'fobi.contrib.plugins.form_elements.content.content_image',
    'fobi.contrib.plugins.form_elements.content.content_text',
    'fobi.contrib.plugins.form_elements.content.content_video',

    # `django-fobo` form handlers
    'fobi.contrib.plugins.form_handlers.db_store',
    'fobi.contrib.plugins.form_handlers.http_repost',
    'fobi.contrib.plugins.form_handlers.mail',

    #'work.fobi_form_callbacks',

    # project
    'valuenetwork.valueaccounting.apps.ValueAccountingAppConfig',
    'valuenetwork.equipment',
    'valuenetwork.board',
    'validation',
    'account',
    'work.apps.WorkAppConfig',
    'multicurrency',
    'valuenetwork.api',
    #'valuenetwork.api.apps.ApiAppConfig',
    #'valuenetwork.api.schemas.apps.ApiSchemasAppConfig',
    'valuenetwork.api.types.apps.ApiTypesAppConfig',
    #'valuenetwork.api.schemas',
    #'valuenetwork.api.types',

    'faircoin',

    # general
    'general',
    'mptt', # This provide Tree management in a 'nested set' style
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'PAGINATE_BY': 10,
    'URL_FIELD_NAME': 'api_url',
}

# valueaccounting settings
# Set this with your specific data in local_settings.py
MAIN_ORGANIZATION = "Freedom Coop"
USE_WORK_NOW = True
SUBSTITUTABLE_DEFAULT = True
MAP_LATITUDE = 45.5601062
MAP_LONGITUDE = -73.7120832
MAP_ZOOM = 11

RANDOM_PASSWORD_LENGHT = 20

ACCOUNT_EMAIL_UNIQUE = True
ACCOUNT_NOTIFY_ON_PASSWORD_CHANGE = False

# multicurrency settings
MULTICURRENCY = {} #Fill the dict in local_settings.py with private data.

# payment gateways settings
PAYMENT_GATEWAYS = {} # Fill the object in local_settings.py with custom gateways data by project

CRYPTOS = () # Fill the list in local_settings.py with flexible price crypto units
CRYPTO_LAPSUS = 600 # How many seconds is valid a crypto price ticker (default 10 minutes), tuned in local_settings
CRYPTO_DECIMALS = 9
DECIMALS = Decimal('0.000000000') # same 9 decimals, used for formating cryptos

PINAX_NOTIFICATIONS_QUEUE_ALL = True
PINAX_NOTIFICATIONS_BACKENDS = [
        ("email", "work.email.EmailBackend", 1), # pinax.notifications.backends.email.EmailBackend
    ]

THUMBNAIL_DEBUG = True

FOBI_DEBUG = DEBUG

#SOUTH_MIGRATION_MODULES = {
#    'easy_thumbnails': 'easy_thumbnails.south_migrations',
#}

INTERNAL_IPS = ('127.0.0.1',)

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
}

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s %(pathname)s %(funcName)s : %(message)s'
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'applogfile': {
            'level':'DEBUG',
            'class':'logging.FileHandler', # was logging.handlers.RotatingFileHandler
            'filename': 'ocp_debug.log', # put the log file in your desired directory
            #'maxBytes': 1024*1024*15, # 15MB
            #'backupCount': 10,
            'formatter': 'verbose'
        },
        'fairlogfile': {
            'level': 'DEBUG',
            'class':'logging.FileHandler',
            'filename': 'fair_debug.log',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'ocp': {
            'handlers': ['applogfile',],
            'level': 'DEBUG',
            'propagate': True,
        },
        'fair': {
            'handlers': ['fairlogfile',],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

GRAPHENE = {
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ]
}

#LOGGING_CONFIG = None

FIXTURE_DIRS = [
    os.path.join(PROJECT_ROOT, "fixtures"),
]


ACCOUNT_OPEN_SIGNUP = False
ACCOUNT_USE_OPENID = False
ACCOUNT_REQUIRED_EMAIL = False
ACCOUNT_EMAIL_VERIFICATION = False
ACCOUNT_EMAIL_AUTHENTICATION = False
ACCOUNT_LOGIN_REDIRECT_URL = "/work/home/" #"/accounting/start/"
WORKER_LOGIN_REDIRECT_URL = "/work/home/"
WORKER_LOGOUT_REDIRECT_URL = "/work/work-home/"
ACCOUNT_LOGOUT_REDIRECT_URL = "home"
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 2
LOGIN_URL = '/account/login/'
AUTH_USER_MODEL = "auth.User"

CORS_URLS_REGEX = r'^/api/.*$'
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True

BROADCAST_FAIRCOINS_LOCK_WAIT_TIMEOUT = None

#id of the group to send payments to
SEND_MEMBERSHIP_PAYMENT_TO = "Freedom Coop"

import re
IGNORABLE_404_URLS = (
    re.compile(r'\.(php|cgi)$'),
    re.compile(r'^/phpmyadmin/'),
    re.compile(r'^/apple-touch-icon.*\.png$'),
    re.compile(r'^/favicon\.ico$'),
    re.compile(r'^/robots\.txt$'),
    re.compile(r'^/accounting/timeline/__history__.html\?0$'),
    re.compile(r'^/accounting/timeline/__history__.html$')
)

ALL_WORK_PAGE = "/accounting/work/"


# updating to django 1.5
USE_TZ = True

# updating to prep for django 1.8
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Translations and localization settings
USE_I18N = True
USE_L10N = True
LOCALE_PATHS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', "locale")),
]
LANGUAGE_CODE = 'en'
LANGUAGES = [
  ('en', _('English')),
  ('es', _('Spanish')),
  ('ca', _('Catalan')),
]
DEFAULT_LANGUAGE = LANGUAGE_CODE
ACCOUNT_LANGUAGES = LANGUAGES
MODELTRANSLATION_DEFAULT_LANGUAGE = 'en' # can be diferent
MODELTRANSLATION_FALLBACK_LANGUAGES = ('es','en') # if empty, try 'es', then 'en'...

MODELTRANSLATION_AUTO_POPULATE = 'default'

# Captcha settings
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.math_challenge'
CAPTCHA_LETTER_ROTATION = (-15,15)
CAPTCHA_MATH_CHALLENGE_OPERATOR = 'x'
CAPTCHA_NOISE_FUNCTIONS = (
  'captcha.helpers.noise_dots',
  'captcha.helpers.noise_dots',
)
if 'test' in sys.argv:
    CAPTCHA_TEST_MODE = True

# ----put all other settings above this line----
try:
    from local_settings import *
except ImportError:
    pass
