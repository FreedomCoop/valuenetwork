#
# Graphene schema for exposing EconomicResource model
#

import graphene
from valuenetwork.valueaccounting.models import EconomicResource as EconomicResourceProxy, EconomicResourceType, AgentUser, Location, EconomicAgent
from valuenetwork.api.types.EconomicResource import EconomicResource
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError


class Query(object): #graphene.AbstractType):

    # define input query params

    economic_resource = graphene.Field(EconomicResource,
                                       id=graphene.Int())

    all_economic_resources = graphene.List(EconomicResource)

    agent_economic_resources = graphene.List(EconomicResource, agent_id=graphene.Int())

    #not implementing this yet, unclear if we ever will want everything in an instance, instead of by agent
    #search_economic_resources = graphene.List(EconomicResource,
    #                                          agent_id=graphene.Int(),
    #                                          search_string=graphene.String())


    def resolve_economic_resource(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            resource = EconomicResourceProxy.objects.get(pk=id)
            if resource:
                #resource.current_quantity = self._current_quantity(quantity=resource.quantity, unit=resource.unit)
                return resource
        return None

    def resolve_all_economic_resources(self, context, **args): #args, context, info):
        print("resolve_all_economic_resources?")
        resources = EconomicResourceProxy.objects.agent_economic_resources(context)
        #for resource in resources:
            #resource.current_quantity = self._current_quantity(quantity=resource.quantity, unit=resource.unit)
        return resources

    def resolve_agent_economic_resources(self, context, **args): #args, context, info):
        print("resolve_agent_economic_resources?")
        id = args.get('agent_id')
        resources = None
        if id is not None:
            agent = EconomicAgent.objects.get(pk=id)
            if agent:
                resources = agent.agent_resource_roles.values('resource') #EconomicResourceProxy.objects.agent_economic_resources(context)
                                # .resource_relationships.
        #for resource in resources:
            #resource.current_quantity = self._current_quantity(quantity=resource.quantity, unit=resource.unit)
        return resources

    #def resolve_search_economic_resources(self, args, context, info):
    #    agent_id = args.get('agent_id', None)
    #    search_string = args.get('search_string', "")
    #    if search_string == "":
    #        raise ValidationError("A search string is required.")
    #    return EconomicResourceProxy.objects.search(agent_id=agent_id, search_string=search_string)

'''
class CreateEconomicResource(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        resource_classified_as_id = graphene.Int(required=True)
        tracking_identifier = graphene.String(required=False)
        image = graphene.String(required=False)
        note = graphene.String(required=False)
        #current_location #TODO
        #current_quantity is not creatable or updatable directly, it always is derived from economic events

    economic_resource = graphene.Field(lambda: EconomicResource)

    @classmethod
    def mutate(cls, root, args, context, info):
        resource_classified_as_id = args.get('resource_classified_as_id')
        tracking_identifier = args.get('tracking_identifier')
        image = args.get('image')
        note = args.get('note')

        if not note:
            note = ""
        if not image:
            image = ""
        if not tracking_identifier:
            tracking_identifier = ""
        resource_classified_as = EconomicResourceType.objects.get(pk=resource_classified_as_id)
        economic_resource = EconomicResourceProxy(
            resource_type=resource_classified_as,
            photo_url=image,
            identifier=tracking_identifier,
            notes=note,
            created_by=info.context.user,
            #location
        )
        economic_resource.save()

        return CreateEconomicResource(economic_resource=economic_resource)
'''

class UpdateEconomicResource(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        resource_classified_as_id = graphene.Int(required=False)
        tracking_identifier = graphene.String(required=False)
        image = graphene.String(required=False)
        note = graphene.String(required=False)
        current_location_id = graphene.Int(required=False)
        url = graphene.String(required=False)

    economic_resource = graphene.Field(lambda: EconomicResource)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        resource_classified_as_id = args.get('resource_classified_as_id')
        tracking_identifier = args.get('tracking_identifier')
        image = args.get('image')
        current_location_id = args.get('current_location_id')
        note = args.get('note')
        url = args.get('url')
        economic_resource = EconomicResourceProxy.objects.get(pk=id)
        if economic_resource:
            if tracking_identifier:
                economic_resource.identifier = tracking_identifier
            if note:
                economic_resource.notes=note
            if url:
                economic_resource.url=url
            if image:
                economic_resource.photo_url=image
            if resource_classified_as_id:
                economic_resource.resource_type=EconomicResourceType.objects.get(pk=resource_classified_as_id)
            if current_location_id:
                economic_resource.current_location=Location.objects.get(pk=current_location_id)
            economic_resource.changed_by=info.context.user

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=economic_resource)
            if is_authorized:
                economic_resource.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdateEconomicResource(economic_resource=economic_resource)


class DeleteEconomicResource(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    economic_resource = graphene.Field(lambda: EconomicResource)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        economic_resource = EconomicResourceProxy.objects.get(pk=id)
        if economic_resource:
            if economic_resource.is_deletable():
                is_authorized = user_agent.is_authorized(object_to_mutate=economic_resource)
                if is_authorized:
                    economic_resource.delete()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied("Economic resource has related events or quantity > 0 and cannot be deleted.")

        return DeleteEconomicResource(economic_resource=economic_resource)
