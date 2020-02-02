import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from maps.models import UseFaircoin


class UseFairCoin(DjangoObjectType): #note big C

    class Meta:
        model = UseFaircoin
        only_fields = ('id', 'title', 'tagline', 'description', 'address', 'hours', 'phone', 'website', 'twitter', 'faircoin_address', 'lat', 'lng', 'image')

