#
# Graphene schema for exposing ProcessClassification model
#

import graphene

from valuenetwork.valueaccounting.models import ProcessType
from valuenetwork.api.types.Process import ProcessClassification
from valuenetwork.api.types.EconomicEvent import Action
from django.db.models import Q


class Query(object): #graphene.AbstractType):

    process_classification = graphene.Field(ProcessClassification,
                                            id=graphene.Int())

    all_process_classifications = graphene.List(ProcessClassification)

    def resolve_process_classification(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            pt = ProcessType.objects.get(pk=id)
            if pt:
                return pt
        return None

    def resolve_all_process_classifications(self, context, **args): #args, context, info):
        return ProcessType.objects.all()
