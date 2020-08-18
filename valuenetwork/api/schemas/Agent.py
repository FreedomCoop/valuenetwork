#
# Graphene schema for exposing EconomicAgent and related models
#
# @package: OCP
# @author:  pospi <pospi@spadgos.com>
# @since:   2017-03-20
#

import graphene
from valuenetwork.valueaccounting.models import EconomicAgent, AgentUser, Location, AgentType
from valuenetwork.api.models import formatAgent, formatAgentList, Person, Organization
from valuenetwork.api.types.Agent import Agent, Person, Organization
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError

class Query(object): #graphene.AbstractType):

    my_agent = graphene.Field(Agent)

    agent = graphene.Field(Agent,
                           id=graphene.Int())

    all_agents = graphene.List(Agent)

    user_is_authorized_to_create = graphene.Boolean(scope_id=graphene.Int())


    def resolve_my_agent(self, context, **args): #args, *rargs):
        agentUser = AgentUser.objects.filter(user=self.user).first()
        agent = agentUser.agent
        if agent:
            return formatAgent(agent)
        raise PermissionDenied("Cannot find requested agent")

    def resolve_agent(self, context, **args): #args, *rargs):
        id = args.get('id') #ide.id
        print('ID: '+str(self.agent))

        if id is not None:
            agent = EconomicAgent.objects.get(pk=id)
            if agent:
                return formatAgent(agent)
        raise PermissionDenied("Cannot find requested agent")

    def resolve_all_agents(self, context, **args): #args, context, info):
        return formatAgentList(EconomicAgent.objects.all())

    def resolve_user_is_authorized_to_create(self, context, **args): #args, context, info):
        context_agent_id = args.get('contest_agent_id')
        user_agent = AgentUser.objects.filter(user=self.user).first().agent
        return user_agent.is_authorized(context_agent_id=context_agent_id)


class CreateOrganization(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        name = graphene.String(required=True)
        image = graphene.String(required=False)
        primary_location_id = graphene.Int(required=False)
        primary_phone = graphene.String(required=False)
        email = graphene.String(required=False)
        note = graphene.String(required=False)
        type = graphene.String(required=True)

    organization = graphene.Field(lambda: Organization)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        #import pdb; pdb.set_trace()
        name = args.get('name')
        image = args.get('image')
        note = args.get('note')
        primary_location_id = args.get('primary_location_id')
        primary_phone = args.get('primary_phone')
        email = args.get('email')
        type = args.get('type')

        if not note:
            note = ""
        if not image:
            image = ""
        if primary_location_id:
            location = Location.objects.get(pk=primary_location_id)
        else:
            location = None
        get_type = None
        if type:
            get_type = AgentType.objects.get(name=type)
        if not type:
            get_types = AgentType.objects.get(party_type="org")
            if get_types:
                get_type = get_types[0]

        agent = EconomicAgent(
            name = name,
            nick = name,
            agent_type = get_type,
            photo_url = image,
            description = note,
            primary_location = location,
            phone_primary = primary_phone,
            email = email,
            created_by=info.context.user,
        )

        user_agent = AgentUser.objects.get(user=info.context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=agent)
        if is_authorized:
            agent.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateOrganization(organization=formatAgent(agent))

class CreatePerson(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        name = graphene.String(required=True)
        image = graphene.String(required=False)
        primary_location_id = graphene.Int(required=False)
        primary_phone = graphene.String(required=False)
        email = graphene.String(required=False)
        note = graphene.String(required=False)
        type = graphene.String(required=False)

    person = graphene.Field(lambda: Person)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        #import pdb; pdb.set_trace()
        name = args.get('name')
        image = args.get('image')
        note = args.get('note')
        primary_location_id = args.get('primary_location_id')
        primary_phone = args.get('primary_phone')
        email = args.get('email')
        type = args.get('type')

        if not note:
            note = ""
        if not image:
            image = ""
        if primary_location_id:
            location = Location.objects.get(pk=primary_location_id)
        else:
            location = None
        if type:
            get_type = AgentType.objects.get(name=type)
        if not type:
            get_types = AgentType.objects.filter(party_type="individual")
            get_type = get_types[0]

        agent = EconomicAgent(
            name = name,
            nick = name,
            agent_type = get_type,
            photo_url = image,
            description = note,
            primary_location = location,
            phone_primary = primary_phone,
            email = email,
            created_by=info.context.user,
        )

        user_agent = AgentUser.objects.get(user=info.context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=agent)
        if is_authorized:
            agent.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreatePerson(person=formatAgent(agent))

class UpdatePerson(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        name = graphene.String(required=False)
        image = graphene.String(required=False)
        primary_location_id = graphene.Int(required=False)
        email = graphene.String(required=False)
        note = graphene.String(required=False)

    person = graphene.Field(lambda: Person)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        name = args.get('name')
        image = args.get('image')
        note = args.get('note')
        primary_location_id = args.get('primary_location_id')
        email = args.get('email')

        agent = EconomicAgent.objects.get(pk=id)
        if agent:
            if note:
                agent.description = note
            if image:
                agent.photo_url = image
            if name:
                agent.name = name
            if primary_location_id:
                agent.primary_location = Location.objects.get(pk=primary_location_id)
            if email:
                agent.email = email

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=agent)
            if is_authorized:
                agent.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdatePerson(person=formatAgent(agent))

class UpdateOrganization(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        name = graphene.String(required=False)
        image = graphene.String(required=False)
        primary_location_id = graphene.Int(required=False)
        email = graphene.String(required=False)
        note = graphene.String(required=False)

    organization = graphene.Field(lambda: Organization)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        name = args.get('name')
        image = args.get('image')
        note = args.get('note')
        primary_location_id = args.get('primary_location_id')
        email = args.get('email')

        agent = EconomicAgent.objects.get(pk=id)
        if agent:
            if note:
                agent.description = note
            if image:
                agent.photo_url = image
            if name:
                agent.name = name
            if primary_location_id:
                agent.primary_location = Location.objects.get(pk=primary_location_id)
            if email:
                agent.email = email

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=agent)
            if is_authorized:
                agent.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdateOrganization(organization=formatAgent(agent))


class DeletePerson(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    person = graphene.Field(lambda: Person)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        agent = EconomicAgent.objects.get(pk=id)
        if agent:
            if agent.is_deletable():
                user_agent = AgentUser.objects.get(user=info.context.user).agent
                #is_authorized = user_agent.is_authorized(context_agent_id=agent.id) TODO: what should be the rule?
                #if is_authorized:
                agent.delete()
                #else:
                #    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied("Person has activity or relationships and cannot be deleted.")

        return DeletePerson(person=formatAgent(agent))

class DeleteOrganization(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    organization = graphene.Field(lambda: Organization)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        agent = EconomicAgent.objects.get(pk=id)
        if agent:
            if agent.is_deletable():
                user_agent = AgentUser.objects.get(user=info.context.user).agent
                #is_authorized = user_agent.is_authorized(context_agent_id=agent.id) TODO: what should be the rule?
                #if is_authorized:
                agent.delete()
                #else:
                #    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied("Organization has activity or relationships and cannot be deleted.")

        return DeleteOrganization(organization=formatAgent(agent))
