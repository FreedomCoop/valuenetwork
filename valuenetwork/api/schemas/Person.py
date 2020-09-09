#
# Graphene schema for exposing individual agent query endpoints ("Person" in VF terms)
#
# @package: OCP
# @author:  pospi <pospi@spadgos.com>
# @since:   2017-06-20
#

import graphene
from valuenetwork.valueaccounting.models import EconomicAgent
from valuenetwork.api.types.Agent import Person
from valuenetwork.api.models import formatAgent, formatAgentList

class Query(object): #graphene.AbstractType):

    # define input query params

    person = graphene.Field(Person,
                           id=graphene.Int())

    all_people = graphene.List(Person)

    # load any person

    def resolve_person(self, args, context, info):
        id = args.get('id')
        if id is not None:
            person = EconomicAgent.objects.get(pk=id)
            if person:
                if person.agent_type.party_type == "individual":
                    return formatAgent(person)
        return None

    # load all people

    def resolve_all_people(self, args, context, info):
        people = EconomicAgent.objects.filter(agent_type__party_type="individual")
        return formatAgentList(people)

