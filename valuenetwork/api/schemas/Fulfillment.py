#
# Graphene schema for exposing Fulfillment
#

import graphene
from valuenetwork.api.models import QuantityValue as FulfillmentProxy
from valuenetwork.api.types.EconomicEvent import Fulfillment


class Query(object): #graphene.AbstractType):

    # define input query params

    fulfillment = graphene.Field(Fulfillment,
                                id=graphene.Int())

    # resolvers

    def resolve_fulfillment(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            ff = FulfillmentProxy.objects.get(pk=id)
            if ff:
                return ff
        return None
