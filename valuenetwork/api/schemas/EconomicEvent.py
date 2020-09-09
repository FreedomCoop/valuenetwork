#
# Graphene schema for exposing EconomicEvent
#

import graphene
import datetime
from decimal import Decimal
from valuenetwork.valueaccounting.models import EconomicEvent as EconomicEventProxy, Commitment, EventType, EconomicAgent, Process, EconomicResourceType, EconomicResource as EconomicResourceProxy, Unit, AgentUser, Location, AgentResourceRoleType, AgentResourceRole
from valuenetwork.api.types.EconomicEvent import EconomicEvent, Action
from valuenetwork.api.models import Fulfillment
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError


class Query(object): #graphene.AbstractType):

    economic_event = graphene.Field(EconomicEvent,
                                    id=graphene.Int())

    all_economic_events = graphene.List(EconomicEvent)

    filtered_economic_events = graphene.List(EconomicEvent,
                                             provider_id=graphene.Int(),
                                             receiver_id=graphene.Int(),
                                             resource_classified_as_id=graphene.Int(),
                                             action=graphene.String(),
                                             start_date=graphene.String(),
                                             end_date=graphene.String())

    def resolve_economic_event(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            event = EconomicEventProxy.objects.get(pk=id)
            if event:
                return event
        return None

    def resolve_all_economic_events(self, args, context, info):
        return EconomicEventProxy.objects.all()

    def resolve_filtered_economic_events(self, args, context, info):
        provider_id = args.get('provider_id')
        receiver_id = args.get('receiver_id')
        resource_classified_as_id = args.get('resource_classified_as_id')
        action = args.get('action')
        start_date = args.get('start_date')
        end_date = args.get('end_date')
        events = EconomicEventProxy.objects.all()
        if provider_id:
            events = EconomicEventProxy.objects.filter(from_agent=EconomicAgent.objects.get(pk=provider_id))
        if receiver_id:
            events = events.filter(to_agent=EconomicAgent.objects.get(pk=receiver_id))
        if action:
            events = events.filter(event_type=EventType.objects.convert_action_to_event_type(action))
        if resource_classified_as_id:
            events = events.filter(resource_type=EconomicResourceType.objects.get(pk=resource_classified_as_id))
        if start_date:
            events = events.filter(event_date__gte=start_date)
        if end_date:
            events = events.filter(event_date__lte=end_date)
        return events


class CreateEconomicEvent(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        action = graphene.String(required=False) #but then must have a commitment
        input_of_id = graphene.Int(required=False)
        output_of_id = graphene.Int(required=False)
        provider_id = graphene.Int(required=False)
        receiver_id = graphene.Int(required=False)
        scope_id = graphene.Int(required=False) #but then must have a commitment
        affects_id = graphene.Int(required=False)
        affected_resource_classified_as_id = graphene.Int(required=False) #but then must have a commitment
        affected_numeric_value = graphene.String(required=True)
        affected_unit_id = graphene.Int(required=False) #but then must have a commitment
        start = graphene.String(required=False)
        fulfills_commitment_id = graphene.Int(required=False)
        url = graphene.String(required=False)
        note = graphene.String(required=False)
        request_distribution = graphene.Boolean(required=False)
        create_resource = graphene.Boolean(required=False)
        resource_tracking_identifier = graphene.String(required=False)
        resource_image = graphene.String(required=False)
        resource_note = graphene.String(required=False)
        resource_current_location_id = graphene.Int(required=False)
        resource_url = graphene.String(required=False)

    economic_event = graphene.Field(lambda: EconomicEvent)

    @classmethod
    def mutate(cls, root, args, context, info):
        action = args.get('action')
        input_of_id = args.get('input_of_id')
        output_of_id = args.get('output_of_id')
        provider_id = args.get('provider_id')
        receiver_id = args.get('receiver_id')
        scope_id = args.get('scope_id')
        affects_id = args.get('affects_id')
        affected_resource_classified_as_id = args.get('affected_resource_classified_as_id')
        affected_numeric_value = args.get('affected_numeric_value')
        affected_unit_id = args.get('affected_unit_id')
        start = args.get('start')
        fulfills_commitment_id = args.get('fulfills_commitment_id') #TODO see if this needs fixing for multiples when doing exchanges
        url = args.get('url')
        request_distribution = args.get('request_distribution')
        note = args.get('note')
        create_resource = args.get('create_resource')
        resource_tracking_identifier = args.get('resource_tracking_identifier')
        resource_image = args.get('resource_image')
        resource_current_location_id = args.get('resource_current_location_id')
        resource_note = args.get('resource_note')
        resource_url = args.get('resource_url')

        if fulfills_commitment_id:
            commitment = Commitment.objects.get(pk=fulfills_commitment_id)
        else:
            commitment = None
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
        elif commitment:
            event_type = commitment.event_type
        else:
            raise ValidationError("Must provide an action in either economic event or its commitment")
        if not note:
            note = ""
        if start:
            start = datetime.datetime.strptime(start, '%Y-%m-%d').date()
        else:
            start = datetime.date.today()
        if scope_id:
            scope = EconomicAgent.objects.get(pk=scope_id)
        elif commitment:
            scope = commitment.context_agent
        else:
            raise ValidationError("Must provide a scope in either economic event or its commitment")
        if provider_id:
            provider = EconomicAgent.objects.get(pk=provider_id)
        elif action == "work":
            user_agent = AgentUser.objects.get(user=context.user)
            provider = user_agent.agent
        elif commitment:
            provider = commitment.from_agent
        else:
            provider = scope
        if receiver_id:
            receiver = EconomicAgent.objects.get(pk=receiver_id)
        elif commitment:
            receiver = commitment.to_agent
        else:
            receiver = scope
        if input_of_id:
            process = Process.objects.get(pk=input_of_id)
        elif output_of_id:
            process = Process.objects.get(pk=output_of_id)
        elif commitment:
            process = commitment.process
        else:
            process = None
        if affects_id:
            affects = EconomicResourceProxy.objects.get(pk=affects_id)
        else:
            affects = None
        if affected_resource_classified_as_id:
            affected_resource_classification = EconomicResourceType.objects.get(pk=affected_resource_classified_as_id)
        elif affects:
            affected_resource_classification = EconomicResourceType.objects.get(pk=affects.resource_type.id)
        elif commitment:
            affected_resource_classification = EconomicResourceType.objects.get(pk=commitment.resource_type.id)
        else:
            raise ValidationError("Must provide a resource classification in either economic event or its commitment")
        if affected_unit_id:
            affected_unit = Unit.objects.get(pk=affected_unit_id)
        elif commitment:
            affected_unit = Unit.objects.get(pk=commitment.unit_of_quantity__id)
        else:
            raise ValidationError("Must provide a unit in either economic event or its commitment")
        if not url:
            url = ""
        if not request_distribution:
            request_distribution = False
        current_location = None
        if resource_current_location_id:
            current_location = Location.objects.get(pk=resource_current_location_id)
        arr = None
        if not affects:
            if create_resource:
                if not resource_note:
                    resource_note = ""
                if not resource_image:
                    resource_image = ""
                if not resource_tracking_identifier:
                    resource_tracking_identifier = ""
                if not resource_url:
                    resource_url = ""
                affects = EconomicResourceProxy(
                    resource_type=affected_resource_classification,
                    quantity=Decimal(affected_numeric_value),
                    photo_url=resource_image,
                    identifier=resource_tracking_identifier,
                    current_location=current_location,
                    notes=resource_note,
                    url=resource_url,
                    created_by=context.user,
                    #location
                )

        economic_event = EconomicEventProxy(
            event_type = event_type,
            process = process,
            from_agent = provider,
            to_agent = receiver,
            resource_type = affected_resource_classification,
            resource = affects,
            quantity = Decimal(affected_numeric_value),
            unit_of_quantity = affected_unit,
            event_date = start,
            description=note,
            context_agent=scope,
            url=url,
            commitment=commitment,
            is_contribution=request_distribution,
            created_by=context.user,
        )

        user_agent = AgentUser.objects.get(user=context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=economic_event)
        if is_authorized:
            economic_event.save_api(user=context.user, create_resource=create_resource)
            #find the first "owner" type resource-agent role, use it for a relationship so inventory will show up #TODO: make more coherent when VF does so
            if create_resource:
                roles = AgentResourceRoleType.objects.filter(is_owner=True)
                if roles and receiver:
                    owner_role = roles[0]
                    arr = AgentResourceRole(
                        agent=receiver,
                        resource=affects,
                        role=owner_role,
                    )
                    arr.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateEconomicEvent(economic_event=economic_event)


class UpdateEconomicEvent(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        action = graphene.String(required=False)
        input_of_id = graphene.Int(required=False)
        output_of_id = graphene.Int(required=False)
        provider_id = graphene.Int(required=False)
        receiver_id = graphene.Int(required=False)
        scope_id = graphene.Int(required=False)
        affected_resource_classified_as_id = graphene.Int(required=False)
        affects_id = graphene.Int(required=False)
        affected_numeric_value = graphene.String(required=False)
        affected_unit_id = graphene.Int(required=False)
        start = graphene.String(required=False)
        fulfills_commitment_id = graphene.Int(required=False)
        url = graphene.String(required=False)
        request_distribution = graphene.Boolean(required=False)
        note = graphene.String(required=False)

    economic_event = graphene.Field(lambda: EconomicEvent)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        action = args.get('action')
        input_of_id = args.get('input_of_id')
        output_of_id = args.get('output_of_id')
        provider_id = args.get('provider_id')
        receiver_id = args.get('receiver_id')
        scope_id = args.get('scope_id')
        affected_resource_classified_as_id = args.get('affected_resource_classified_as_id')
        affects_id = args.get('affects_id')
        affected_numeric_value = args.get('affected_numeric_value')
        affected_unit_id = args.get('affected_unit_id')
        start = args.get('start')
        fulfills_commitment_id = args.get('fulfills_commitment_id') #TODO see if this needs fixing for multiples when doing exchanges
        url = args.get('url')
        request_distribution = args.get('request_distribution')
        note = args.get('note')

        economic_event = EconomicEventProxy.objects.get(pk=id)
        if economic_event:
            old_resource = economic_event.resource
            old_quantity = economic_event.quantity
            if action:
                economic_event.event_type = EventType.objects.convert_action_to_event_type(action)
            if note:
                economic_event.description = note
            if start:
                economic_event.event_date = datetime.datetime.strptime(start, '%Y-%m-%d').date()
            if scope_id:
                economic_event.context_agent = EconomicAgent.objects.get(pk=scope_id)
            if provider_id:
                economic_event.from_agent = EconomicAgent.objects.get(pk=provider_id)
            if receiver_id:
                economic_event.to_agent = EconomicAgent.objects.get(pk=receiver_id)
            if input_of_id:
                economic_event.process = Process.objects.get(pk=input_of_id)
            elif output_of_id:
                economic_event.process = Process.objects.get(pk=output_of_id)
            if affected_resource_classified_as_id:
                economic_event.resource_type = EconomicResourceType.objects.get(pk=affected_resource_classified_as_id)
            if affects_id:
                economic_event.resource = EconomicResourceProxy.objects.get(pk=affects_id)
            if affected_numeric_value:
                economic_event.quantity = Decimal(affected_numeric_value)
            if affected_unit_id:
                economic_event.unit_of_quantity = Unit.objects.get(pk=affected_unit_id)
            if request_distribution != None:
                economic_event.is_contribution = request_distribution
            if request_distribution is False:
                economic_event.is_contribution = False
            if url:
                economic_event.url = url
            if fulfills_commitment_id:
                economic_event.commitment = Commitment.objects.get(pk=fulfills_commitment_id)
            economic_event.changed_by = context.user

            user_agent = AgentUser.objects.get(user=context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=economic_event)
            if is_authorized:
                economic_event.save_api(user=context.user, old_quantity=old_quantity, old_resource=old_resource)
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdateEconomicEvent(economic_event=economic_event)


class DeleteEconomicEvent(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    economic_event = graphene.Field(lambda: EconomicEvent)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        economic_event = EconomicEventProxy.objects.get(pk=id)
        if economic_event:
            user_agent = AgentUser.objects.get(user=context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=economic_event)
            if is_authorized:
                economic_event.delete_api()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return DeleteEconomicEvent(economic_event=economic_event)
