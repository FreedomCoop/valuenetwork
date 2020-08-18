#
# Agent Resource Classification: Association between an agent and a resource classification, used for person skills and agent sources for resources
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import AgentResourceType
from valuenetwork.api.models import formatAgent, Person, Organization


class AgentResourceClassification(DjangoObjectType):
    agent = graphene.Field(lambda: types.Agent)
    resource_classification = graphene.Field(lambda: types.ResourceClassification)
    action = graphene.String(source='action')

    class Meta:
        model = AgentResourceType
        fields = ('id',)

    def resolve_agent(self, context, **args): #args, *rargs):
        return formatAgent(self.agent)

    def resolve_resource_classification(self, context, **args): #args, *rargs):
        return self.resource_type
