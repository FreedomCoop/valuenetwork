#
# Economic Event: An inflow or outflow of an economic resource in relation to a process and/or exchange. This could reflect a change in the quantity of a EconomicResource. It is also defined by its behavior in relation to the EconomicResource and a Process (consume, use, produce, etc.)" .
#

#from django.core.exceptions import PermissionDenied

import graphene
from graphene_django.types import DjangoObjectType

import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import EconomicEvent as EconomicEventProxy
from valuenetwork.api.models import formatAgent, Person, Organization


class Action(graphene.Enum):
    NONE = None
    WORK = "work"
    CONSUME = "consume"
    USE = "use"
    CITE = "cite"
    PRODUCE = "produce"
    CHANGE = "change"


class EconomicEvent(DjangoObjectType):
    action = graphene.String(source='action')
    process = graphene.Field(lambda: types.Process)
    provider = graphene.Field(lambda: types.Agent)
    receiver = graphene.Field(lambda: types.Agent)
    scope = graphene.Field(lambda: types.Agent)
    affected_resource = graphene.Field(lambda: types.EconomicResource)
    numeric_value = graphene.Float(source='numeric_value') #need to implement as quantity-value with unit
    unit = graphene.String(source='unit')
    start = graphene.String(source='start')
    work_category = graphene.String(source='work_category')
    note = graphene.String(source='note')

    class Meta:
        model = EconomicEventProxy
        only_fields = ('id')

    def resolve_process(self, args, *rargs):
        return self.process

    def resolve_provider(self, args, *rargs):
        return formatAgent(self.provider)

    def resolve_receiver(self, args, *rargs):
        return formatAgent(self.receiver)

    def resolve_scope(self, args, *rargs):
        return formatAgent(self.scope)

    def resolve_affected_resource(self, args, *rargs):
        return self.affected_resource


