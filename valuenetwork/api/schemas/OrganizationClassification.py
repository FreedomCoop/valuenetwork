#
# Graphene schema for exposing OrganizationClassification model
#

import graphene
from valuenetwork.valueaccounting.models import AgentType
from valuenetwork.api.types.Agent import OrganizationClassification


class Query(object): #graphene.AbstractType):

    # define input query params

    organization_classification = graphene.Field(OrganizationClassification,
                                                id=graphene.Int())

    all_organization_classifications = graphene.List(OrganizationClassification)


    def resolve_organization_classification(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            oc = AgentType.objects.get(pk=id)
            if oc:
                return oc
        return None

    def resolve_all_organization_classifications(self, args, context, info):
        return AgentType.objects.exclude(party_type="individual")
