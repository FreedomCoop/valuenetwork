#
# Agent relationship entity schema def
#
# @package: OCP
#

import graphene
from graphene_django.types import DjangoObjectType

from valuenetwork.api.types.AgentRelationship import AgentRelationship, AgentRelationshipRole
from valuenetwork.valueaccounting.models import EconomicAgent, AgentAssociation, AgentAssociationType, AgentUser
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError

# define public query API

class Query(object): #graphene.AbstractType):

    agent_relationship = graphene.Field(AgentRelationship,
                                        id=graphene.Int())

    all_agent_relationships = graphene.List(AgentRelationship)

    def resolve_agent_relationship(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            ar = AgentAssociation.objects.get(pk=id)
            if ar:
                return ar
        return None

    def resolve_all_agent_relationships(self, context, **args): #args, context, info):
        return AgentAssociation.objects.all()


class CreateAgentRelationship(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        subject_id = graphene.Int(required=True)
        object_id = graphene.Int(required=True)
        relationship_id = graphene.Int(required=True)
        note=graphene.String(required=False)

    agent_relationship = graphene.Field(lambda: AgentRelationship)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        subject_id = args.get('subject_id')
        object_id = args.get('object_id')
        relationship_id = args.get('relationship_id')
        note = args.get('note')

        subject = EconomicAgent.objects.get(pk=subject_id)
        object = EconomicAgent.objects.get(pk=object_id)
        relationship = AgentAssociationType.objects.get(pk=relationship_id)
        agent_relationship = AgentAssociation(
            is_associate=subject,
            has_associate=object,
            association_type=relationship,
            description=note,
        )

        user_agent = AgentUser.objects.get(user=info.context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=agent_relationship)
        if is_authorized:
            agent_relationship.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateAgentRelationship(agent_relationship=agent_relationship)


class UpdateAgentRelationship(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        subject_id = graphene.Int(required=False)
        object_id = graphene.Int(required=False)
        relationship_id = graphene.Int(required=False)
        note=graphene.String(required=False)

    agent_relationship = graphene.Field(lambda: AgentRelationship)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        subject_id = args.get('subject_id')
        object_id = args.get('object_id')
        relationship_id = args.get('relationship_id')
        note = args.get('note')

        agent_relationship = AgentAssociation.objects.get(pk=id)
        if agent_relationship:
            if subject_id:
                agent_relationship.is_associate = EconomicAgent.objects.get(pk=subject_id)
            if object_id:
                agent_relationship.has_associate = EconomicAgent.objects.get(pk=object_id)
            if relationship_id:
                agent_relationship.association_type = AgentAssociationType.objects.get(pk=relationship_id)
            if note:
                agent_relationship.description = note

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=agent_relationship)
            if is_authorized:
                agent_relationship.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdateAgentRelationship(agent_relationship=agent_relationship)

'''
# TODO: Need to create an is_deletable method in models, which checks for any usage of this.  Else makes it inactivated.
class DeleteAgentRelationship(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    agent_relationship = graphene.Field(lambda: AgentRelationship)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        agent_relationship = AgentAssociation.objects.get(pk=id)
        if agent_relationship:
            if agent_relationship.is_deletable():
                user_agent = AgentUser.objects.get(user=context.user).agent
                is_authorized = user_agent.is_authorized(object_to_mutate=agent_relationship)
                if is_authorized:
                    agent_relationship.delete()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied("Process has economic events so cannot be deleted.")

        return DeleteAgentRelationship(agent_relationship=agent_relationship)
'''
