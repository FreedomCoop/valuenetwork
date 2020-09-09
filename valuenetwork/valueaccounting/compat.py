try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey  # noqa

try:
    from urllib.parse import quote
except ImportError:
    from urllib.parse import quote  # noqa

try:
    from threading import get_ident
except ImportError:
    from _thread import get_ident  # noqa

try:
    from account.decorators import login_required
except ImportError:
    from django.contrib.auth.decorators import login_required  # noqa

try:
    from django.apps import apps as django_apps
    get_model = django_apps.get_model
except ImportError:
    from django.db.models import get_model as old_get_model  # noqa

    def get_model(path):
        return old_get_model(*path.split("."))
