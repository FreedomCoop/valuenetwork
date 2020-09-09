#
# Place: A geo-mappable location.
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import Location
from valuenetwork.api.models import formatAgentList


class Place(DjangoObjectType):
    note = graphene.String(source='note')

    class Meta:
        model = Location
        fields = ('id', 'name', 'address', 'latitude', 'longitude')

    place_resources = graphene.List(lambda: types.EconomicResource)

    place_agents = graphene.List(lambda: types.Agent)

    def resolve_place_resources(self, args, context, info):
        return self.resources()

    def resolve_place_agents(self, args, context, info):
        return formatAgentList(self.agents())
