#
# Graphene schema for exposing Notification models

import graphene

from pinax.notifications.models import NoticeSetting, NoticeType
from valuenetwork.api.types.NotificationSetting import NotificationSetting, NotificationType
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied


class Query(graphene.AbstractType):

    notification_setting = graphene.Field(NotificationSetting,
                                          id=graphene.Int())

    all_notification_settings = graphene.List(NotificationSetting)

    notification_type = graphene.Field(NotificationType,
                                       id=graphene.Int())

    all_notification_types = graphene.List(NotificationType)

    def resolve_notification_setting(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            notice = NoticeSetting.objects.get(pk=id)
            if notice:
                return notice
        return None

    def resolve_all_notification_settings(self, args, context, info):
        return NoticeSetting.objects.all()

    def resolve_notification_type(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            notice = NoticeType.objects.get(pk=id)
            if notice:
                return notice
        return None

    def resolve_all_notification_types(self, args, context, info):
        return NoticeType.objects.all()


class CreateNotificationSetting(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        agent_id = graphene.Int(required=False) #if none, will use the agent of the logged on user
        notification_type_id = graphene.Int(required=True)
        send = graphene.Boolean(required=True)

    notification_setting = graphene.Field(lambda: NotificationSetting)

    @classmethod
    def mutate(cls, root, args, context, info):
        agent_id = args.get('agent_id')
        notification_type_id = args.get('notification_type_id')
        send = args.get('send')

        if agent_id:
            agent = EconomicAgent.objects.get(pk=agent_id)
            user = agent.my_user()
        else:
            user = context.user
        notification_type = NotificationType.objects.get(pk=notification_type_id)
        notification_setting = NotificationSetting(
            send=send,
            notification_type=notification_type,
            user=user,
        )

        #non-standard auth
        user_agent = AgentUser.objects.get(user=context.user).agent
        is_authorized = False
        if user_agent.is_superuser():
            is_authorized = True
        if user == context.user:
            is_authorized = True
        if is_authorized:
            notification_setting.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateNotificationSetting(notification_setting=notification_setting)


class UpdateNotificationSetting(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        send = graphene.Boolean(required=False)

    notification_setting = graphene.Field(lambda: NotificationSetting)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        send = args.get('send')

        notification_setting = Order.objects.get(pk=id)
        if notification_setting:
            if send:
                notification_setting.send = send

                #non-standard auth
                user_agent = AgentUser.objects.get(user=context.user).agent
                is_authorized = False
                if user_agent.is_superuser():
                    is_authorized = True
                if user == context.user:
                    is_authorized = True
                if is_authorized:
                    notification_setting.save()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')

        return UpdateNotificationSetting(notification_setting=notification_setting)
