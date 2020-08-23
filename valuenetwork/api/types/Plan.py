#
# Plan: A set of one or more connected processes. (Note there is currently no corresponding ValueFlows concept, although something like it will probably need to be added.  But for now, this is not VF vocabulary compliant.)
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.api.types.EconomicEvent import Action
from valuenetwork.valueaccounting.models import Order
from valuenetwork.api.models import formatAgent, formatAgentList


class Plan(DjangoObjectType):
    planned_on = graphene.String(source='planned')
    due = graphene.String(source='due')
    note = graphene.String(source='note')
    name = graphene.String(source='plan_name')

    class Meta:
        model = Order
        fields = ('id',)


    created_by = graphene.Field(lambda: types.Agent)

    scope = graphene.List(lambda: types.Agent)

    plan_processes = graphene.List(lambda: types.Process,
                                year=graphene.Int(),
                                month=graphene.Int())

    working_agents = graphene.List(lambda: types.Agent)

    planned_non_work_inputs = graphene.List(lambda: types.Commitment)

    planned_outputs = graphene.List(lambda: types.Commitment)

    non_work_inputs = graphene.List(lambda: types.EconomicEvent)

    outputs = graphene.List(lambda: types.EconomicEvent)

    kanban_state = graphene.String()

    is_deletable = graphene.Boolean()

    def resolve_scope(self, context, **args): #args, *rargs):
        return formatAgentList(self.plan_context_agents())

    def resolve_created_by(self, context, **args): #args, *rargs):
        return formatAgent(self.created_by_agent)

    def resolve_plan_processes(self, context, **args): #args, context, info):
        year = args.get('year', None)
        month = args.get('month', None)
        if year and month:
            procs = self.all_processes()
            worked_procs = []
            for proc in procs:
                if proc.worked_in_month(year=year,month=month):
                    worked_procs.append(proc)
            return worked_procs
        return self.all_processes()

    def resolve_working_agents(self, context, **args): #args, context, info):
        return formatAgentList(self.all_working_agents())

    def resolve_planned_non_work_inputs(self, context, **args): #args, context, info):
        return self.non_work_incoming_commitments()

    def resolve_planned_outputs(self, context, **args): #args, context, info):
        return self.all_outgoing_commitments()

    def resolve_non_work_inputs(self, context, **args): #args, context, info):
        return self.non_work_incoming_events()

    def resolve_outputs(self, context, **args): #args, context, info):
        return self.all_outgoing_events()

    # returns "planned", "doing", "done"
    def resolve_kanban_state(self, context, **args): #args, *rargs):
        return self.kanban_state()

    def resolve_is_deletable(self, context, **args): #args, *rargs):
        return self.is_deletable()
