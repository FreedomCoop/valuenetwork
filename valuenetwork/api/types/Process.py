#
# Process: An activity that changes inputs into outputs.  It could transform or transport EconomicResource(s).
#

import graphene
from graphene_django.types import DjangoObjectType
import valuenetwork.api.types as types
from valuenetwork.api.schemas.Auth import _authUser
from valuenetwork.api.types.EconomicEvent import Action
from valuenetwork.valueaccounting.models import Process as ProcessProxy, EventType, ProcessType, AgentUser
from valuenetwork.api.models import formatAgent


class ProcessClassification(DjangoObjectType):
    note = graphene.String(source='note')
    scope = graphene.Field(lambda: types.Agent)
    estimated_duration = graphene.String(source='estimated_duration') #in minutes

    class Meta:
        model = ProcessType
        fields = ('id', 'name')

    def resolve_scope(self, context, **args): #args, *rargs):
        return formatAgent(self.scope)


class Process(DjangoObjectType):
    scope = graphene.Field(lambda: types.Agent)
    planned_start = graphene.String(source='planned_start')
    planned_finish = graphene.String(source='planned_finish')
    is_started = graphene.Boolean(source='is_started')
    is_finished = graphene.Boolean(source='is_finished')
    process_classified_as = graphene.Field(ProcessClassification)
    note = graphene.String(source='note')

    class Meta:
        model = ProcessProxy
        fields = ('id', 'name')

    planned_duration = graphene.String(source='planned_duration')

    is_deletable = graphene.Boolean()

    inputs = graphene.List(lambda: types.EconomicEvent,
                                        action=Action()) #VF

    outputs = graphene.List(lambda: types.EconomicEvent,
                            action=Action()) #VF

    unplanned_economic_events = graphene.List(lambda: types.EconomicEvent,
                                              action=Action())

    committed_inputs = graphene.List(lambda: types.Commitment,
                                     action=Action()) #VF

    committed_outputs = graphene.List(lambda: types.Commitment,
                                      action=Action()) #VF

    next_processes = graphene.List(lambda: types.Process)

    previous_processes = graphene.List(lambda: types.Process)

    working_agents = graphene.List(lambda: types.Agent)

    process_plan = graphene.Field(lambda: types.Plan)

    user_is_authorized_to_update = graphene.Boolean()

    user_is_authorized_to_delete = graphene.Boolean()

    #next_resource_taxonomy_items = graphene.List(lambda: types.ResourceTaxonomyItem)

    #previous_resource_taxonomy_items = graphene.List(lambda: types.ResourceTaxonomyItem)

    #resource_classifications_by_action = graphene.List(lambda: types.ResourceClassification)


    def resolve_scope(self, context, **args): #args, *rargs):
        return formatAgent(self.scope)

    def resolve_process_plan(self, context, **args): #args, *rargs):
        return self.plan  #self.independent_demand()

    def resolve_process_classified_as(self, context, **args): #args, *rargs):
        return self.process_type

    def resolve_inputs(self, context, **args): #args, context, info):
        action = args.get('action')
        events = self.incoming_events()
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
            events = events.filter(event_type=event_type)
        return events

    def resolve_outputs(self, context, **args): #args, context, info):
        action = args.get('action')
        events = self.outputs()
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
            events = events.filter(event_type=event_type)
        return events

    def resolve_committed_inputs(self, context, **args): #args, context, info):
        action = args.get('action')
        commits = self.incoming_commitments()
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
            commits = commits.filter(event_type=event_type)
        return commits

    def resolve_committed_outputs(self, context, **args): #args, context, info):
        action = args.get('action')
        commits = self.outgoing_commitments()
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
            commits = commits.filter(event_type=event_type)
        return commits

    def resolve_next_processes(self, context, **args): #args, context, info):
        return self.next_processes()

    def resolve_previous_processes(self, context, **args): #args, context, info):
        return self.previous_processes()

    def resolve_working_agents(self, context, **args): #args, context, info):
        agents = self.all_working_agents()
        formatted_agents = []
        for agent in agents:
            formatted_agents.append(formatAgent(agent))
        return formatted_agents

    def resolve_unplanned_economic_events(self, context, **args): #args, context, info):
        action = args.get('action')
        unplanned_events = self.uncommitted_events()
        if action:
            event_type = EventType.objects.convert_action_to_event_type(action)
            unplanned_events = unplanned_events.filter(event_type=event_type)
        return unplanned_events

    def resolve_is_deletable(self, context, **args): #args, *rargs):
        return self.is_deletable()

    def resolve_user_is_authorized_to_update(self, context, **args): #args, context, *rargs):
        token = args[0].variable_values['token']
        context.user = _authUser(token)
        user_agent = AgentUser.objects.get(user=context.user).agent
        return user_agent.is_authorized(object_to_mutate=self)

    def resolve_user_is_authorized_to_delete(self, context, **args): #args, context, *rargs):
        token = args[0].variable_values['token']
        context.user = _authUser(token)
        user_agent = AgentUser.objects.get(user=context.user).agent
        return user_agent.is_authorized(object_to_mutate=self)

    #def resolve_next_resource_taxonomy_items(self, args, context, info):
    #    return self.output_resource_types()

    #def resolve_previous_resource_taxonomy_items(self, args, context, info):
    #    return self.

    #def resolve_resource_classifications_by_action(self, args, context, info): #TODO not completed
    #    action = args.get('action')
    #    if action:
    #        event_type = action._convert_action_to_event_type()
    #        return self.get_rts_by_action(event_type)
    #    return None
