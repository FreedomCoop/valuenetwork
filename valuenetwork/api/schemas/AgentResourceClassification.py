#
# Agent resource classification entity schema def
# This is used for person's skills management.  Also can be used in the future for sources for resources to be obtained for production inputs, but will need the action added for that.
#

import graphene
from graphene_django.types import DjangoObjectType

from valuenetwork.api.types.AgentResourceClassification import AgentResourceClassification
from valuenetwork.valueaccounting.models import EconomicAgent, AgentUser, AgentResourceType, EconomicResourceType, EventType
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError


class Query(object): #graphene.AbstractType):

    agent_resource_classification = graphene.Field(AgentResourceClassification,
                                        id=graphene.Int())

    all_agent_resource_classifications = graphene.List(AgentResourceClassification)

    def resolve_agent_resource_classification(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            ar = AgentResourceType.objects.get(pk=id)
            if ar:
                return ar
        return None

    def resolve_all_agent_resource_classifications(self, context, **args): #args, context, info):
        return AgentResourceType.objects.all()


class CreateAgentResourceClassification(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        agent_id = graphene.Int(required=True)
        resource_classification_id = graphene.Int(required=True)

    agent_resource_classification = graphene.Field(lambda: AgentResourceClassification)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        agent_id = args.get('agent_id')
        resource_classification_id = args.get('resource_classification_id')

        agent = EconomicAgent.objects.get(pk=agent_id)
        rc = EconomicResourceType.objects.get(pk=resource_classification_id)
        et_work = EventType.objects.get(name="Time Contribution") #TODO: now just for skills
        agent_resource_classification = AgentResourceType.objects.filter(agent=agent, resource_type=rc, event_type=et_work)
        if agent_resource_classification:
            raise ValidationError('Resource classification already exists for this agent and action.')
        else:
            agent_resource_classification = AgentResourceType(
                agent=agent,
                resource_type=rc,
                event_type=et_work,
                created_by=info.context.user,
            )

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=agent_resource_classification)
            if is_authorized:
                agent_resource_classification.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return CreateAgentResourceClassification(agent_resource_classification=agent_resource_classification)


class DeleteAgentResourceClassification(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    agent_resource_classification = graphene.Field(lambda: AgentResourceClassification)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        agent_resource_classification = AgentResourceType.objects.get(pk=id)
        if agent_resource_classification:
            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=agent_resource_classification)
            if is_authorized:
                agent_resource_classification.delete()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return DeleteAgentResourceClassification(agent_resource_classification=agent_resource_classification)
