#
# Agent Relationship: An ongoing voluntary association between 2 Agents of any kind.
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.valueaccounting.models import AgentAssociation, AgentAssociationType
from valuenetwork.api.models import formatAgent, Person, Organization


class AgentRelationshipCategory(graphene.Enum):
    NONE = None
    MEMBER = "member"
    PART = "part"
    PEER = "peer"
    TRADINGPARTNER = "trading partner"
    LEGALPARTNER = "legal partner"


class AgentRelationshipRole(DjangoObjectType):
    category = graphene.Field(lambda: AgentRelationshipCategory)

    class Meta:
        model = AgentAssociationType
        fields = ('id', 'label', 'inverse_label', 'name', 'plural_name')

    def resolve_category(self, args, *rargs):
        return self.category


class AgentRelationship(DjangoObjectType):
    subject = graphene.Field(lambda: types.Agent)
    object = graphene.Field(lambda: types.Agent)
    relationship = graphene.Field(lambda: AgentRelationshipRole)
    note = graphene.String(source='description')
    join_request_date = graphene.String(source='join_request_date')

    class Meta:
        model = AgentAssociation
        fields = ('id',)

    def resolve_subject(self, args, *rargs):
        return formatAgent(self.subject)

    def resolve_object(self, args, *rargs):
        return formatAgent(self.object)

    def resolve_relationship(self, args, *rargs):
        return self.relationship
