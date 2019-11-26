from django.conf import settings
from django.utils.translation import ugettext_noop as _

def create_notice_types(sender, **kwargs):
    if "pinax.notifications" in settings.INSTALLED_APPS:
        from pinax.notifications.models import NoticeType
        NoticeType.create("valnet_join_task", _("Join Task"), _("a colleaque wants to help with this task"), default=0)
        NoticeType.create("valnet_help_wanted", _("Help Wanted"), _("a colleague requests help that fits your skills"), default=0)
        NoticeType.create("valnet_new_task", _("New Task"), _("a new task was posted that fits your skills"), default=0)
        NoticeType.create("valnet_new_todo", _("New Todo"), _("a new todo was posted that is assigned to you"), default=0)
        NoticeType.create("valnet_deleted_todo", _("Deleted Todo"), _("a todo that was assigned to you has been deleted"), default=0)
        NoticeType.create("valnet_distribution", _("New Distribution"), _("you have received a new income distribution"), default=0)
        NoticeType.create("valnet_payout_request", _("Payout Request"), _("you have received a new payout request"), default=0)
        NoticeType.create("work_membership_request", _("Freedom Coop Membership Request"), _("we have received a new membership request"), default=0)
        NoticeType.create("work_join_request", _("Project Join Request"), _("we have received a new join request"), default=1)
        NoticeType.create("work_new_account", _("Project New OCP Account"), _("a new OCP account details"), default=1)
        NoticeType.create("comment_membership_request", _("Comment in Freedom Coop Membership Request"), _("we have received a new comment in a membership request"), default=0)
        NoticeType.create("comment_join_request", _("Comment in Project Join Request"), _("we have received a new comment in a join request"), default=1)
        NoticeType.create("work_skill_suggestion", _("Skill suggestion"), _("we have received a new skill suggestion"), default=0)
        print("created valueaccounting notice types")
    else:
        print("Skipping creation of valueaccounting NoticeTypes as notification app not found")

