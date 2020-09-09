#
# Commitment: A planned economic event or transfer that has been promised by an agent to another agent.
#

import jwt
import graphene
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from graphene_django.types import DjangoObjectType


import valuenetwork.api.types as types
from valuenetwork.api.types.QuantityValue import Unit, QuantityValue
from valuenetwork.api.schemas.Auth import _authUser
from valuenetwork.valueaccounting.models import Commitment as CommitmentProxy, AgentUser
from valuenetwork.api.models import formatAgent, Person, Organization, QuantityValue as QuantityValueProxy, Fulfillment as FulfillmentProxy


class Commitment(DjangoObjectType):
    action = graphene.String(source='action')
    #process = graphene.Field(lambda: types.Process)
    input_of = graphene.Field(lambda: types.Process)
    output_of = graphene.Field(lambda: types.Process)
    provider = graphene.Field(lambda: types.Agent)
    receiver = graphene.Field(lambda: types.Agent)
    scope = graphene.Field(lambda: types.Agent)
    resource_classified_as = graphene.Field(lambda: types.ResourceClassification)
    involves = graphene.Field(lambda: types.EconomicResource)
    committed_quantity = graphene.Field(QuantityValue)
    committed_on = graphene.String(source='committed_on')
    planned_start = graphene.String(source='planned_start')
    due = graphene.String(source='due')
    is_finished = graphene.Boolean(source='is_finished')
    plan = graphene.Field(lambda: types.Plan)
    is_plan_deliverable = graphene.Boolean(source='is_plan_deliverable')
    for_plan_deliverable = graphene.Field(lambda: Commitment)
    note = graphene.String(source='note')

    class Meta:
        model = CommitmentProxy
        fields = ('id', 'url')

    fulfilled_by = graphene.List(lambda: types.Fulfillment,
                                 request_distribution=graphene.Boolean())

    involved_agents = graphene.List(lambda: types.Agent)

    is_deletable = graphene.Boolean()

    user_is_authorized_to_update = graphene.Boolean()

    user_is_authorized_to_delete = graphene.Boolean()

    #def resolve_process(self, args, *rargs):
    #    return self.process

    def resolve_input_of(self, context, **args): #args, *rargs):
        return self.input_of

    def resolve_output_of(self, context, **args): #args, *rargs):
        return self.output_of

    def resolve_provider(self, context, **args): #args, *rargs):
        return formatAgent(self.provider)

    def resolve_receiver(self, context, **args): #args, *rargs):
        return formatAgent(self.receiver)

    def resolve_scope(self, context, **args): #args, *rargs):
        return formatAgent(self.scope)

    def resolve_involves(self, context, **args): #args, *rargs):
        return self.involves

    def resolve_resource_classified_as(self, context, **args): #args, *rargs):
        return self.resource_classified_as

    def resolve_committed_quantity(self, context, **args): #args, *rargs):
        return QuantityValueProxy(numeric_value=self.quantity, unit=self.unit_of_quantity)

    def resolve_plan(self, context, **args): #args, *rargs):
        return self.independent_demand

    def resolve_for_plan_deliverable(self, context, **args): #args, *rargs):
        return self.order_item

    def resolve_fulfilled_by(self, context, **args): #args, context, info):
        events = self.fulfillment_events.all()
        request_distribution = args.get('request_distribution')
        if request_distribution != None:
            events = events.filter(is_contribution=request_distribution)
        fulfillments = []
        for event in events:
            fulfill = FulfillmentProxy(
                fulfilled_by=event,
                fulfills=self,
                fulfilled_quantity=QuantityValueProxy(numeric_value=event.quantity, unit=event.unit_of_quantity),
                )
            fulfillments.append(fulfill)
        return fulfillments

    def resolve_involved_agents(self, context, **args): #args, context, info):
        involved = []
        if self.provider:
            involved.append(formatAgent(self.provider))
        events = self.fulfillment_events.all()
        for event in events:
            if event.provider:
                involved.append(formatAgent(event.provider))
        return list(set(involved))

    def resolve_is_deletable(self, context, **args): #args, *rargs):
        return self.is_deletable()

    def resolve_user_is_authorized_to_update(self, context, **args): #args, context, *rargs):
        token = args[0].variable_values['token']
        context.user = _authUser(token)
        user_agent = AgentUser.objects.get(user=context.user).agent
        return user_agent.is_authorized(object_to_mutate=self)

    def resolve_user_is_authorized_to_delete(self, context, **args): #args, context, *rargs):
        token = args[0].variable_values['token']
        context.user = _authUser(token)
        user_agent = AgentUser.objects.get(user=context.user).agent
        return user_agent.is_authorized(object_to_mutate=self)
