#
# Graphene schema for exposing EconomicAgent and related models
#
# @package: OCP
# @author:  pospi <pospi@spadgos.com>
# @since:   2017-03-20
#

from django.core.exceptions import PermissionDenied

import graphene

from valuenetwork.valueaccounting.models import EconomicAgent, AgentUser

from valuenetwork.api.types.Agent import AgentType

class Query(graphene.AbstractType):

    # define input query params

    my_agent = graphene.Field(AgentType)

    agent = graphene.Field(AgentType,
                           id=graphene.Int())

    all_agents = graphene.List(AgentType)

    # load single agents

    def resolve_my_agent(self, args, *rargs):
        agent = self._load_own_agent()
        if agent:
            return agent
        raise PermissionDenied("Cannot find requested agent")

    def resolve_agent(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            agent = EconomicAgent.objects.get(pk=id)
            if agent:
                return agent
        raise PermissionDenied("Cannot find requested agent")

    # load all agent lists

    def resolve_all_agents(self, args, context, info):
        return EconomicAgent.objects.all()

    # internals

    def _load_own_agent(self):
        agentUser = AgentUser.objects.filter(user=self.user).first()
        return agentUser.agent
