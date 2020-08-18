#
# Validation: Confirmation that a claim/commitment related to economic events is valid.
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import EconomicEvent, EconomicAgent
from validation.models import Validation as ValidationProxy
from valuenetwork.api.models import formatAgent


class Validation(DjangoObjectType):
    validated_by = graphene.Field(lambda: types.Agent)
    economic_event = graphene.Field(lambda: types.EconomicEvent)

    class Meta:
        model = ValidationProxy
        fields = ('id', 'validation_date', 'note')


    def resolve_validated_by(self, context, **args): #args, *rargs):
        return formatAgent(self.validated_by)

    def resolve_economic_event(self, context, **args): #args, *rargs):
        return self.event
