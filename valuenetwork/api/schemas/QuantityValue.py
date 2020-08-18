#
# Graphene schema for exposing QuantityValue model
#   Note: QuantityValue does not stand on its own, it is a bundling of number and unit for handling quantities in other classes
#

import graphene
from graphene_django.types import DjangoObjectType

from valuenetwork.api.models import QuantityValue as QuantityValueProxy
from valuenetwork.api.types.QuantityValue import QuantityValue


class Query(object): #graphene.AbstractType):

    # define input query params

    quantity_value = graphene.Field(QuantityValue,
                                    id=graphene.Int())

    # resolve methods

    def resolve_quantity_value(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            qv = QuantityValueProxy.objects.get(pk=id)
            if qv:
                return qv
        return None
