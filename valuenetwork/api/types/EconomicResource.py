#
# EconomicResource:
#

import graphene
from graphene_django.types import DjangoObjectType

import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import EconomicResource as EconomicResourceProxy, EconomicResourceType, Facet as FacetProxy, FacetValue as FacetValueProxy
from valuenetwork.api.models import QuantityValue as QuantityValueProxy, formatAgentList
from valuenetwork.api.types.QuantityValue import Unit, QuantityValue


class EconomicResourceCategory(graphene.Enum):
    NONE = None
    CURRENCY = "currency"
    INVENTORY = "inventory"
    WORK = "work"
    #SERVICE = "service" TODO: work this in, might need a new event type in VF


class EconomicResourceProcessCategory(graphene.Enum):
    NONE = None
    CONSUMED = "consumed"
    USED = "used"
    CITED = "cited"
    PRODUCED = "produced"


class Facet(DjangoObjectType):

    class Meta:
        model = FacetProxy
        fields = ('id', 'name', 'description')

    facet_values = graphene.List(lambda: FacetValue)

    def resolve_facet_values(self, context, **args): #args, context, info):
        return self.values.all()

class FacetValue(DjangoObjectType):
    facet = graphene.List(lambda: types.Facet)

    class Meta:
        model = FacetValueProxy
        fields = ('id', 'value', 'description')


class ResourceClassification(DjangoObjectType):
    image = graphene.String(source='image')
    note = graphene.String(source='note')
    category = graphene.String(source='category')
    process_category = graphene.String(source='process_category')

    class Meta:
        model = EconomicResourceType
        fields = ('id', 'name', 'unit')

    classification_resources = graphene.List(lambda: EconomicResource)

    #classification_facet_values = graphene.List(lambda: FacetValue)

    def resolve_classification_resources(self, context, **args): #args, context, info):
        return self.resources.all()

    #def resolve_classification_facet_values(self, args, context, info):
    #    return self.facets.all() #TODO in process, not working yet

class EconomicResource(DjangoObjectType):
    resource_classified_as = graphene.Field(ResourceClassification)
    tracking_identifier = graphene.String(source='tracking_identifier')
    image = graphene.String(source='image')
    current_quantity = graphene.Field(QuantityValue)
    note = graphene.String(source='note')
    category = graphene.String(source='category')
    current_location = graphene.Field(lambda: types.Place)
    created_date = graphene.String(source='created_date')

    class Meta:
        model = EconomicResourceProxy
        fields = ('id', 'url')

    transfers = graphene.List(lambda: types.Transfer)

    resource_contacts = graphene.List(lambda: types.Agent)

    owners = graphene.List(lambda: types.Agent)

    def resolve_current_quantity(self, context, **args): #args, *rargs):
        return QuantityValueProxy(numeric_value=self.quantity, unit=self.unit)

    def resolve_resource_classified_as(self, context, **args): #args, *rargs):
        return self.resource_type

    def resolve_current_location(self, context, **args): #args, *rargs):
        return self.current_location

    def resolve_transfers(self, context, **args): #args, context, info):
        return self.transfers()

    def resolve_resource_contacts(self, context, **args): #args, context, info):
        return formatAgentList(self.all_contact_agents())

    def resolve_owners(self, context, **args): #args, context, info):
        return formatAgentList(self.owners())
