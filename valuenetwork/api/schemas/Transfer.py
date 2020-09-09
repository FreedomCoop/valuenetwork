#
# Graphene schema for exposing Transfer model

import graphene

from valuenetwork.valueaccounting.models import Transfer as TransferProxy
from valuenetwork.api.types.Exchange import Transfer


class Query(object): #graphene.AbstractType):

    # define input query params

    transfer = graphene.Field(Transfer,
                              id=graphene.Int())

    all_transfers = graphene.List(Transfer)

    # load single item

    def resolve_transfer(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            transfer = TransferProxy.objects.get(pk=id)
            if transfer:
                return transfer
        return None

    # load all items

    def resolve_all_transfers(self, args, context, info):
        return TransferProxy.objects.all()
