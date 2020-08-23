from django.conf import settings

from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import TemplateView

from django.contrib import admin


import work.views


urlpatterns = [
    #path("", TemplateView.as_view(template_name="homepage.html"), name="home"),
    path("", work.views.home, name="home"),
    path("accounting/", include("valuenetwork.valueaccounting.urls")),
    path("notifications/", include("pinax.notifications.urls", namespace="pinax_notifications")),
    path("equipment/", include("valuenetwork.equipment.urls")),
    path("board/", include("valuenetwork.board.urls")),
    path("work/", include("work.urls")),
    path("api/", include("valuenetwork.api.urls")),

    path("admin/", admin.site.urls),
    path("account/", include("account.urls")),

    path('comments/', include('django_comments.urls')),
    #path('membership/', work.views.membership_request, name="membership_request"),
    path('membershipthanks/', TemplateView.as_view(template_name='work/membership_thanks.html'), name='membership_thanks'),
    path('captcha/', include('captcha.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('robots.txt', lambda r: HttpResponse("User-agent: *\nAllow: /$\nDisallow: /", content_type="text/plain")),

    # api special endpoints
    path("total-shares/<project_slug>/", work.views.project_total_shares, name="project_total_shares"),
    path("update-share-payment/<project_slug>/", work.views.project_update_payment_status, name="project_update_payment_status"),
    path("member-shares/", work.views.member_total_shares, name="member_total_shares"),

    # View URLs
    path('fobi/', include('fobi.urls.view')),

    # Edit URLs
    path('fobi/', include('fobi.urls.edit')),

    # DB Store plugin URLs
    path('fobi/plugins/form-handlers/db-store/',
    include('fobi.contrib.plugins.form_handlers.db_store.urls')),

    # basic ocp login+join
    path('<form_slug>/', work.views.project_login, name="project_login"),
    path('joinaproject/<form_slug>/', work.views.joinaproject_request, name="joinaproject_request"),
    path('join/<form_slug>/', work.views.joinaproject_request, name="join_request"),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if 'multicurrency' in settings.INSTALLED_APPS:
    urlpatterns += [path('multicurrency/', include('multicurrency.urls')),]

if 'faircoin' in settings.INSTALLED_APPS:
    urlpatterns += [path('faircoin/', include('faircoin.urls')),]


