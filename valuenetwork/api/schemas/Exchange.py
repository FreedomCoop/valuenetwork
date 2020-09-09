#
# Graphene schema for exposing Exchange model

import graphene

from valuenetwork.valueaccounting.models import Exchange
from valuenetwork.api.types.Exchange import ExchangeAgreement


class Query(object): #graphene.AbstractType):

    # define input query params

    exchange_agreement = graphene.Field(ExchangeAgreement,
                                        id=graphene.Int())

    all_exchange_agreements = graphene.List(ExchangeAgreement)

    # load single item

    def resolve_exchange_agreement(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            exchange = Exchange.objects.get(pk=id)
            if exchange:
                return exchange
        return None

    # load all items

    def resolve_all_exchange_agreements(self, args, context, info):
        return Exchange.objects.all()
