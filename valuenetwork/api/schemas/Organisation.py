#
# Graphene schema for exposing organisation Agent relationships
#
# @package: OCP
# @author:  pospi <pospi@spadgos.com>
# @since:   2017-06-05
#

import graphene

from valuenetwork.valueaccounting.models import EconomicAgent

from AgentBaseQueries import AgentBase
from valuenetwork.api.types.Agent import Organization

class Query(AgentBase, graphene.AbstractType):

    # define input query params

    my_organizations = graphene.List(Organization)

    organization = graphene.Field(Organization,
                                  id=graphene.Int())

    all_organizations = graphene.List(Organization)

    # load context agents that 'me' is related to with 'member' or 'manager' behavior
    # (this gives the projects, collectives, groups that the user agent is any
    # kind of member of)

    def resolve_my_organizations(self, args, context, info):
        my_agent = self._load_own_agent() # provided by AgentBase
        return my_agent.is_member_of()

    # load any organisation

    def resolve_organization(self, args, context, info):
        id = args.get('id')
        if id is not None:
            return EconomicAgent.objects.get(pk=id, is_context=True)    # :TODO: @fosterlynn what's correct here?
        return None

    # load all organizations

    def resolve_all_organizations(self, args, context, info):
        return EconomicAgent.objects.all(is_context=True)   # :TODO: @fosterlynn what's correct here?
