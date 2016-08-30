# -*- coding: utf-8 -*-

# Connecting signal "comment_was_posted" to comment_notification()
def comment_notification(sender, comment, **kwargs):
    #import pdb; pdb.set_trace()
    ct_commented = comment.content_type
    if ct_commented.model == 'membershiprequest':
        msr = comment.content_object

        if msr.agent:
            msr_owner_name = msr.agent.name
        else:
            msr_owner_name = msr.name

        from django.conf import settings
        if "notification" in settings.INSTALLED_APPS:
            from notification import models as notification
            from django.contrib.auth.models import User
            users = User.objects.filter(is_staff=True)
            if users:
                from django.contrib.sites.models import Site
                site_name = Site.objects.get_current().name
                membership_url= "https://" + Site.objects.get_current().domain + "/accounting/membership-request/" + str(msr.id) + "/"
                notification.send(
                    users,
                    "comment_membership_request",
                    {"name": comment.name,
                    "comment": comment.comment,
                    "site_name": site_name,
                    "membership_url": membership_url,
                    }
)

    #TODO: other content types where comments are attached to.
    elif ct_commented.model == 'joinrequest':
        pass

from django_comments.models import Comment
from django_comments.signals import comment_was_posted
comment_was_posted.connect(comment_notification, sender=Comment)
