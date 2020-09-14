import os, sys
from django.utils.translation import ugettext_lazy as _
from decimal import Decimal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PACKAGE_ROOT = os.path.abspath(os.path.dirname(__file__))
#BASE_DIR = PACKAGE_ROOT
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DEBUG = True

# settings.TESTING will be True in a testing enviroment.
TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "ocp.sqlite",
    }
}

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "UTC"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en" # was: en-us


LOCALE_PATHS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', "locale")),
]
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


SITE_ID = int(os.environ.get("SITE_ID", 1))

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "site_media", "media") # was PACKAGE_ROOT

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "/site_media/media/"

# Absolute path to the directory static files should be collected to.
# Don"t put anything in this directory yourself; store your static files
# in apps" "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "site_media", "static") # was PACKAGE_ROOT

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/site_media/static/"

# Additional locations of static files
STATICFILES_DIRS = [
    os.path.join(PROJECT_ROOT, "static", "dist"),
]

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = "2)b@zm=x_@o*hcxr8v^poy=3j-a#3ywncrh^kza6_y#l5p9evu"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(PACKAGE_ROOT, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": DEBUG,
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "account.context_processors.account",
                "ocp.context_processors.settings",
                "fobi.context_processors.theme",
                "pinax_theme_bootstrap.context_processors.theme",
            ],
        },
    },
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    'account.middleware.LocaleMiddleware',
    'django.middleware.security.SecurityMiddleware',
    #'valuenetwork.login_required_middleware.LoginRequiredMiddleware',
    'account.middleware.TimezoneMiddleware',
]

ROOT_URLCONF = "ocp.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "ocp.wsgi.application"

INSTALLED_APPS = [
    'modeltranslation', # to provide translations of model fields

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",

    "django.contrib.humanize",
    "django_comments",

    # templates
    "bootstrapform",
    "pinax.templates",

    'pinax_theme_bootstrap',
    "django_forms_bootstrap",

    # external
    "account",
    "django_jsonfield_backport",
    "pinax.eventlog",
    "pinax.webanalytics",

    'pinax.notifications',
    'corsheaders',
    #'django_extensions',
    'easy_thumbnails',
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
    "ocp",

    'valuenetwork.valueaccounting.apps.ValueAccountingAppConfig',
    'valuenetwork.equipment',
    'valuenetwork.board',
    'validation',
    'work.apps.WorkAppConfig',
    'multicurrency',
    'valuenetwork.api',
    'valuenetwork.api.types.apps.ApiTypesAppConfig',

    'faircoin',

    # general
    'general',
    'mptt', # This provide Tree management in a 'nested set' style
]

ADMIN_URL = "admin:index"
CONTACT_EMAIL = "support@example.com"

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse"
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s %(pathname)s %(funcName)s : %(message)s'
        },
    },
    "handlers": {
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler"
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
    "loggers": {
        "django.request": {
            "handlers": ["mail_admins"],
            "level": "ERROR",
            "propagate": True,
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
    }
}

FIXTURE_DIRS = [
    os.path.join(PROJECT_ROOT, "fixtures"),
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ACCOUNT_OPEN_SIGNUP = True
ACCOUNT_EMAIL_UNIQUE = True
ACCOUNT_EMAIL_CONFIRMATION_REQUIRED = False
ACCOUNT_LOGIN_REDIRECT_URL = "/work/home" # was: home
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 2
ACCOUNT_USE_AUTH_AUTHENTICATE = True
ACCOUNT_PASSWORD_RESET_REDIRECT_URL = "profile"
ACCOUNT_PASSWORD_CHANGE_REDIRECT_URL = "profile"
#ACCOUNT_SIGNUP_REDIRECT_URL = ""

#ACCOUNT_USE_OPENID = False
#ACCOUNT_REQUIRED_EMAIL = False
#ACCOUNT_EMAIL_VERIFICATION = False
#ACCOUNT_EMAIL_AUTHENTICATION = False
WORKER_LOGIN_REDIRECT_URL = "/work/home/"
WORKER_LOGOUT_REDIRECT_URL = "/work/work-home/"

AUTH_USER_MODEL = "auth.User"
LOGIN_URL = '/account/login/'
LOGIN_EXEMPT_URLS = [
    r"^$",
    #r'^membership/',
    #r'^membershipthanks/',
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


CORS_URLS_REGEX = r'^/api/.*$'
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True

BROADCAST_FAIRCOINS_LOCK_WAIT_TIMEOUT = None

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

AUTHENTICATION_BACKENDS = [
    "account.auth_backends.UsernameAuthenticationBackend",
]


GRAPHENE = {
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ],
    'SCHEMA': 'valuenetwork.api.schema',
}

THEME_ADMIN_URL = ADMIN_URL
THEME_CONTACT_EMAIL = CONTACT_EMAIL

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'PAGINATE_BY': 10,
    'URL_FIELD_NAME': 'api_url',
}

PINAX_NOTIFICATIONS_QUEUE_ALL = True
PINAX_NOTIFICATIONS_BACKENDS = [
        ("email", "work.email.EmailBackend", 1), # pinax.notifications.backends.email.EmailBackend
    ]

THUMBNAIL_DEBUG = True

FOBI_DEBUG = DEBUG

INTERNAL_IPS = ('127.0.0.1',)

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
}

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

# valueaccounting settings
# Set this with your specific data in local_settings.py
USE_WORK_NOW = True
SUBSTITUTABLE_DEFAULT = True
MAP_LATITUDE = 45.5601062
MAP_LONGITUDE = -73.7120832
MAP_ZOOM = 11

RANDOM_PASSWORD_LENGHT = 20

# multicurrency settings
MULTICURRENCY = {} #Fill the dict in local_settings.py with private data.

# payment gateways settings
PAYMENT_GATEWAYS = {} # Fill the object in local_settings.py with custom gateways data by project

CRYPTOS = () # Fill the list in local_settings.py with flexible price crypto units
CRYPTO_LAPSUS = 600 # How many seconds is valid a crypto price ticker (default 10 minutes), tuned in local_settings
CRYPTO_DECIMALS = 9
DECIMALS = Decimal('0.000000000') # same 9 decimals, used for formating cryptos

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
