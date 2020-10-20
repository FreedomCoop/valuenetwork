from django import template
from account.utils import get_current_site_name

register = template.Library()

@register.filter
def ocp_sitename(str, request):
    return get_current_site_name(request)
