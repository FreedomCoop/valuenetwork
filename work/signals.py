# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger("ocp")

def comment_notification(sender, comment=None, **kwargs):
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.contrib.sites.models import Site
    from work.utils import set_user_notification_by_type
    from django.core.exceptions import ValidationError

    ct_commented = comment.content_type

    logger.info("About to send a comment related the object: "+str(ct_commented.model)) #+" name:"+str(comment.name))

    if ct_commented.model == 'membershiprequest':
        msr_creator_username = comment.content_object.requested_username

        if "pinax.notifications" in settings.INSTALLED_APPS:
            from pinax.notifications import models as notification
            users = User.objects.filter(is_staff=True) | User.objects.filter(username=msr_creator_username)

            if users:
                site_name = Site.objects.get_current().name
                domain = Site.objects.get_current().domain
                membership_url= "https://" + domain +\
                    "/work/membership-discussion/" + str(comment.content_object.id) + "/"
                notification.send(
                    users,
                    "comment_membership_request",
                    {"name": comment.name,
                    "comment": comment.comment,
                    "site_name": site_name,
                    "membership_url": membership_url,
                    "current_site": domain,
                    }
                )

    elif ct_commented.model == 'joinrequest':
        jr_creator = comment.content_object.agent.user()
        jr_managers = comment.content_object.project.agent.managers()

        if "pinax.notifications" in settings.INSTALLED_APPS:
            from pinax.notifications import models as notification

            users = []
            if jr_creator:
                users.append(jr_creator.user)

            sett = set_user_notification_by_type(jr_creator.user, "comment_join_request", True)

            for manager in jr_managers:
                if manager.user():
                    users.append(manager.user().user)

            if users:
                site_name = Site.objects.get_current().name
                domain = kwargs['request'].get_host()
                try:
                    slug = comment.content_object.project.fobi_slug
                    if settings.PROJECTS_LOGIN:
                        obj = settings.PROJECTS_LOGIN
                        for pro in obj:
                            if pro == slug:
                                site_name = comment.content_object.project.agent.name
                except:
                    pass

                joinrequest_url= "https://" + domain +\
                    "/work/agent/" + str(comment.content_object.project.agent.id) +\
                    "/feedback/" + str(comment.content_object.id) + "/"
                #logger.debug("Ready to send comment notification at jr_url: "+str(joinrequest_url))
                notification.send(
                    users,
                    "comment_join_request",
                    {"name": comment.name,
                    "comment": comment.comment,
                    "site_name": comment.content_object.project.agent.nick, #site_name,
                    "joinrequest_url": joinrequest_url,
                    "jn_req": comment.content_object,
                    "current_site": domain,
                    "context_agent": comment.content_object.project.agent,
                    "request_host": domain,
                    }
                )
    else:
        logger.error("The comment is related an unknown model: "+str(ct_commented.model))
        raise ValidationError("The comment is related an unknown model: "+str(ct_commented.model))


# This don't work anymore! now the connection is at work/apps.py ... but seems not enough? connect here too

# Connecting signal "comment_was_posted" to comment_notification()
from django_comments.models import Comment
from django_comments.signals import comment_was_posted#, comment_will_be_posted
comment_was_posted.connect(comment_notification, sender=Comment)
#logger.debug("Connect comment_was_posted signal with Comment sender")
