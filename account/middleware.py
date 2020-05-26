from django.utils import translation, timezone
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

from account.models import Account


class LocaleMiddleware(MiddlewareMixin):
    """
    This is a very simple middleware that parses a request
    and decides what translation object to install in the current
    thread context depending on the user's account. This allows pages
    to be dynamically translated to the language the user desires
    (if the language is available, of course).
    """
    
    def get_language_for_user(self, request):
        if request.user.is_authenticated:
            try:
                account = Account.objects.get(user=request.user)
                return account.language
            except Account.DoesNotExist:
                pass
        return translation.get_language_from_request(request)
    
    def process_request(self, request):
        translation.activate(self.get_language_for_user(request))
        request.LANGUAGE_CODE = translation.get_language()
    
    def process_response(self, request, response):
        patch_vary_headers(response, ("Accept-Language",))
        response["Content-Language"] = translation.get_language()
        translation.deactivate()
        return response


class TimezoneMiddleware(MiddlewareMixin):
    """
    This middleware sets the timezone used to display dates in
    templates to the user's timezone.
    """
    
    def process_request(self, request):
        account = getattr(request.user, "account", None)
        if account:
            timezone.activate(account.timezone)
