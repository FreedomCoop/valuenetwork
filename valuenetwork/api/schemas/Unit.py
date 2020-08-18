#
# Graphene schema for exposing Unit model
#

import graphene

from valuenetwork.valueaccounting.models import Process as ProcessProxy
from valuenetwork.api.types.QuantityValue import Unit
from valuenetwork.valueaccounting.models import Unit as UnitProxy


class Query(object): #graphene.AbstractType):

    unit = graphene.Field(Unit,
                          id=graphene.Int())

    all_units = graphene.List(Unit)

    def resolve_unit(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            unit = UnitProxy.objects.get(pk=id)
            if unit:
                return unit
        return None

    # load all items

    def resolve_all_units(self, context, **args): #args, context, info):
        return UnitProxy.objects.all()
