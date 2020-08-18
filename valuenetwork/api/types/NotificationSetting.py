#
# NotificationSetting: user defined setting for receiving (or not) a type of notification
#

import graphene
from graphene_django.types import DjangoObjectType
from valuenetwork.api.models import formatAgent
import valuenetwork.api.types as types
from pinax.notifications.models import NoticeSetting, NoticeType

class NotificationType(DjangoObjectType):

    class Meta:
        model = NoticeType
        fields = ('id', 'label', 'display', 'description')


class NotificationSetting(DjangoObjectType):
    agent = graphene.Field(lambda: types.Agent)
    notification_type = graphene.Field(NotificationType)

    class Meta:
        model = NoticeSetting
        fields = ('id', 'send')

    def resolve_agent(self, context, **args): #args, *rargs):
        return formatAgent(self.user.agent.agent)

    def resolve_notification_type(self, context, **args): #args, *rargs):
        return self.notice_type
