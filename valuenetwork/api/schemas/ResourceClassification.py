#
# Graphene schema for exposing ResourceClassification model
#

import graphene

from valuenetwork.valueaccounting.models import EconomicResourceType, Facet as FacetProxy, FacetValue as FacetValueProxy
from valuenetwork.api.types.EconomicResource import ResourceClassification, EconomicResourceProcessCategory, Facet, FacetValue
from valuenetwork.api.types.EconomicEvent import Action
from django.db.models import Q


class Query(object): #graphene.AbstractType):

    # define input query params

    resource_classification = graphene.Field(ResourceClassification,
                                            id=graphene.Int())

    all_resource_classifications = graphene.List(ResourceClassification)

    resource_classifications_by_process_category = graphene.List(ResourceClassification,
                                                               category=EconomicResourceProcessCategory())

    resource_classifications_by_action = graphene.List(ResourceClassification,
                                                      action=Action())

    all_recipes = graphene.List(ResourceClassification)

    #returns resource classifications filtered by facet values in a string of comma delimited name:value,
    #with some resource quantity > 0, for use in inventory filtering
    resource_classifications_by_facet_values = graphene.List(ResourceClassification,
                                                       facet_values=graphene.String())

    facet = graphene.Field(Facet,
                           id=graphene.Int())

    all_facets = graphene.List(Facet)


    def resolve_resource_classification(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            rt = EconomicResourceType.objects.get(pk=id)
            if rt:
                return rt
        return None

    def resolve_all_resource_classifications(self, context, **args): #args, context, info):
        return EconomicResourceType.objects.all()

    def resolve_resource_classifications_by_process_category(self, context, **args): #args, context, info):
        cat = args.get('category')
        return EconomicResourceType.objects.filter(behavior=cat)

    def resolve_resource_classifications_by_action(self, context, **args): #args, context, info):
        action = args.get('action')
        if action == Action.WORK:
            return EconomicResourceType.objects.filter(behavior="work")
        if action == Action.USE:
            return EconomicResourceType.objects.filter(behavior="used")
        if action == Action.CONSUME:
            return EconomicResourceType.objects.filter(behavior="consumed")
        if action == Action.CITE:
            return EconomicResourceType.objects.filter(behavior="cited")
        if action == Action.PRODUCE:
            return EconomicResourceType.objects.filter(Q(behavior="produced")|Q(behavior="used")|Q(behavior="cited")|Q(behavior="consumed"))
        if action == Action.IMPROVE or action == Action.ACCEPT:
            return EconomicResourceType.objects.filter(Q(behavior="produced")|Q(behavior="used")|Q(behavior="cited")|Q(behavior="consumed"))
        return None

    def resolve_resource_classifications_by_facet_values(self, context, **args): #args, context, info):
        fvs = args.get('facet_values')
        return EconomicResourceType.objects.resource_types_by_facet_values(fvs)

    def resolve_facet(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id:
            facet = FacetProxy.objects.get(pk=id)
            if facet:
                return facet
        return None

    def resolve_all_facets(self, context, **args): #args, context, info):
        return FacetProxy.objects.all()

    def resolve_all_recipes(self, context, **args): #args, context, info):
        return EconomicResourceType.objects.resource_types_with_recipes()

