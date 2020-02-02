
import graphene

from maps.models import UseFaircoin # note small c
from valuenetwork.api.types.UseFairCoin import UseFairCoin # note big C


class Query(graphene.AbstractType):

    ufc = graphene.Field(UseFairCoin,
                              id=graphene.Int())

    all_ufcs = graphene.List(UseFairCoin)

    def resolve_ufc(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            ufc = UseFaircoin.objects.get(pk=id)
            if ufc:
                return ufc
        return None

    def resolve_all_ufcs(self, args, context, info):
        return UseFaircoin.objects.all()
