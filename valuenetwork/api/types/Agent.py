#
# EconomicAgent:A person or group or organization with economic agency.
#

import graphene
from graphene_django.types import DjangoObjectType
from django.db.models import Q
from valuenetwork.valueaccounting.models import EconomicAgent, EconomicResourceType, AgentType, EventTypeManager, EventType, AgentResourceType, EconomicResourceType
import valuenetwork.api.types as types
from valuenetwork.api.types.AgentRelationship import AgentRelationship, AgentRelationshipCategory, AgentRelationshipRole
from valuenetwork.api.models import Organization as OrganizationModel, Person as PersonModel, formatAgentList
from django.core.exceptions import ValidationError
import datetime


def _load_identified_agent(self):
    return EconomicAgent.objects.get(pk=self.id)


class OrganizationClassification(DjangoObjectType):
    note = graphene.String(source='note')

    class Meta:
        model = AgentType
        fields = ('id', 'name')


class Agent(graphene.Interface):
    id = graphene.String()
    name = graphene.String()
    type = graphene.String(source='type')
    image = graphene.String(source='image')
    note = graphene.String(source='note')
    primary_location = graphene.Field(lambda: types.Place)
    primary_phone = graphene.String(source='primary_phone')
    email = graphene.String(source='email')

    owned_economic_resources = graphene.List(lambda: types.EconomicResource,
                                             category=types.EconomicResourceCategory(),
                                             resourceClassificationId=graphene.Int(),
                                             page=graphene.Int())

    search_owned_inventory_resources = graphene.List(lambda: types.EconomicResource,
                                              search_string=graphene.String())

    agent_defined_resource_classifications = graphene.List(lambda: types.ResourceClassification,
                                                   action=graphene.String())

    agent_processes = graphene.List(lambda: types.Process,
                                    is_finished=graphene.Boolean())

    search_agent_processes = graphene.List(lambda: types.Process,
                                              search_string=graphene.String(),
                                              is_finished=graphene.Boolean())

    agent_plans = graphene.List(lambda: types.Plan,
                                is_finished=graphene.Boolean(),
                                year=graphene.Int(),
                                month=graphene.Int(),
                                sort_desc=graphene.Boolean())

    search_agent_plans = graphene.List(lambda: types.Plan,
                                              search_string=graphene.String(),
                                              is_finished=graphene.Boolean())

    agent_economic_events = graphene.List(lambda: types.EconomicEvent,
                                          latest_number_of_days=graphene.Int(),
                                          request_distribution=graphene.Boolean(),
                                          action=graphene.String(),
                                          year=graphene.Int(),
                                          month=graphene.Int())

    agent_commitments = graphene.List(lambda: types.Commitment,
                                      #latest_number_of_days=graphene.Int(),
                                      finished=graphene.Boolean(),
                                      page=graphene.Int(),
                                      also_search_children=graphene.Boolean(),
                                      sort_desc=graphene.Boolean())

    search_agent_commitments = graphene.List(lambda: types.Commitment,
                                              search_string=graphene.String(),
                                              finished=graphene.Boolean(),
                                              page=graphene.Int(),
                                              also_search_children=graphene.Boolean(),
                                              sort_desc=graphene.Boolean())

    agent_relationships = graphene.List(AgentRelationship,
                                        role_id=graphene.Int(),
                                        category=AgentRelationshipCategory())

    agent_relationships_as_subject = graphene.List(AgentRelationship,
                                        role_id=graphene.Int(),
                                        category=AgentRelationshipCategory())

    agent_relationships_as_object = graphene.List(AgentRelationship,
                                        role_id=graphene.Int(),
                                        category=AgentRelationshipCategory())

    is_member_of = graphene.Boolean(agent_id=graphene.Int())

    agent_roles = graphene.List(AgentRelationshipRole)

    agent_recipes = graphene.List(lambda: types.ResourceClassification)

    #agent_recipe_bundles = graphene.List(ResourceClassification)

    faircoin_address = graphene.String()

    agent_notification_settings = graphene.List(lambda: types.NotificationSetting)

    member_relationships = graphene.List(AgentRelationship)

    agent_skills = graphene.List(lambda: types.ResourceClassification)

    agent_skill_relationships = graphene.List(lambda: types.AgentResourceClassification)

    commitments_matching_skills = graphene.List(lambda: types.Commitment,
                                                page=graphene.Int())

    validated_events_count = graphene.Int(month=graphene.Int(), year=graphene.Int())

    events_count = graphene.Int(year=graphene.Int(), month=graphene.Int())

    event_hours_count = graphene.Int(year=graphene.Int(), month=graphene.Int())

    event_people_count = graphene.Int(year=graphene.Int(), month=graphene.Int())

    def resolve_primary_location(self, context, **kwargs): #args, *rargs):
        return self.primary_location

    def resolve_owned_economic_resources(self, context, **args): #args, context, info):
        type = args.get('category', types.EconomicResourceCategory.NONE)
        resource_class_id = args.get('resourceClassificationId', None)
        page = args.get('page', None)
        org = _load_identified_agent(self)
        resources = None
        if org:
            if type == types.EconomicResourceCategory.CURRENCY:
                resources = org.owned_currency_resources()
            elif type == types.EconomicResourceCategory.INVENTORY:
                resources = org.owned_inventory_resources_with_subs() #TODO: include sub-agents, is this OK for LearnDeep?
            else:
                resources = org.owned_resources()
            if resource_class_id:
                rc = EconomicResourceType.objects.get(pk=resource_class_id)
                resources_temp = []
                for res in resources:
                    if res.resource_type == rc:
                        resources_temp.append(res)
                resources = resources_temp
            if page:
                from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
                paginator = Paginator(resources, 25)
                try:
                    resources = paginator.page(page)
                except PageNotAnInteger:
                    # If page is not an integer, deliver first page.
                    resources = paginator.page(1)
                except EmptyPage:
                    # If page is out of range (e.g. 9999), deliver last page of results.
                    resources = paginator.page(paginator.num_pages)
        return resources

    def resolve_search_owned_inventory_resources(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        search_string = args.get('search_string', "")
        if search_string == "":
            raise ValidationError("A search string is required.")
        return agent.search_owned_resources(search_string=search_string)

    def resolve_agent_defined_resource_classifications(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        action = args.get('action', None)
        rts = agent.defined_resource_types()
        if action == None:
            return rts
        else:
            filtered_rts = []
            if action == "work":
                for rt in rts:
                    if rt.behavior == "work":
                        filtered_rts.append(rt)
            if action == "use":
                for rt in rts:
                    if rt.behavior == "used":
                        filtered_rts.append(rt)
            if action == "consume":
                for rt in rts:
                    if rt.behavior == "consumed":
                        filtered_rts.append(rt)
            if action == "cite":
                for rt in rts:
                    if rt.behavior == "cited":
                        filtered_rts.append(rt)
            if action == "produce" or action == "improve" or action == "accept":
                for rt in rts:
                    if rt.behavior == "produced" or rt.behavior == "used" or rt.behavior == "cited" or rt.behavior == "consumed":
                        filtered_rts.append(rt)
            return filtered_rts


    # if an organization, this returns processes done in that context
    # if a person, this returns proceses the person has worked on
    def resolve_agent_processes(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            agent_processes = agent.all_processes()
            finished = args.get('is_finished', None)
            if finished != None:
                if not finished:
                    return agent_processes.filter(finished=False)
                else:
                    return agent_processes.filter(finished=True)
            else:
                return agent_processes
        return None

    def resolve_search_agent_processes(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        finished = args.get('is_finished', None)
        search_string = args.get('search_string', "")
        if search_string == "":
            raise ValidationError("A search string is required.")
        if agent:
            return agent.search_processes(search_string=search_string, finished=finished)
        return None

    # if an organization, this returns plans from that context
    # if a person, this returns plans the person has worked on
    def resolve_agent_plans(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            finished = args.get('is_finished', None)
            year = args.get('year', None)
            month = args.get('month', None)
            sort_desc = args.get('sort_desc', False)
            if finished != None:
                if not finished:
                    plans = agent.unfinished_plans()
                else:
                    plans = agent.finished_plans()
            else:
                plans = agent.all_plans()
            if year and month:
                dated_plans = []
                for plan in plans:
                    if plan.worked_in_month(year=year, month=month):
                        dated_plans.append(plan)
                plans = dated_plans
            if sort_desc:
                plans.sort(key=lambda x: x.created_date, reverse=True)
            return plans
        return None

    def resolve_search_agent_plans(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        finished = args.get('is_finished', None)
        search_string = args.get('search_string', "")
        if search_string == "":
            raise ValidationError("A search string is required.")
        if agent:
            return agent.search_plans(search_string=search_string, finished=finished)
        return None

    # returns events where an agent is a provider, receiver, or scope agent, excluding exchange related events
    def resolve_agent_economic_events(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            days = args.get('latest_number_of_days', 0)
            request_distribution = args.get('request_distribution')
            action = args.get('action')
            year = args.get('year')
            month = args.get('month')
            if days > 0:
                events = agent.involved_in_events().filter(event_date__gte=(datetime.date.today() - datetime.timedelta(days=days)))
            elif year and month:
                events = agent.involved_in_events().filter(event_date__year=year).filter(event_date__month=month)
            else:
                events = agent.involved_in_events()
            events = events.exclude(event_type__name="Give").exclude(event_type__name="Receive")
            if action != None:
                events = events.filter(event_type=EventType.objects.convert_action_to_event_type(action))
            if request_distribution != None:
                events = events.filter(is_contribution=request_distribution)
            return events
        return None

    # returns commitments where an agent is a provider, receiver, or scope agent, excluding exchange related events
    def resolve_agent_commitments(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        page = args.get('page', None)
        finished = args.get('finished', None)
        sort_desc = args.get('sort_desc', False)
        also_search_children=args.get('also_search_children', False)
        if agent:
            commits = agent.agent_commitments(finished=finished, sort_desc=sort_desc, also_search_children=also_search_children)
            if page:
                from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
                paginator = Paginator(commits, 25)
                try:
                    commits = paginator.page(page)
                except PageNotAnInteger:
                    # If page is not an integer, deliver first page.
                    commits = paginator.page(1)
                except EmptyPage:
                    # If page is out of range (e.g. 9999), deliver last page of results.
                    commits = paginator.page(paginator.num_pages)
            return commits
        return None

    def resolve_search_agent_commitments(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        page = args.get('page', None)
        finished = args.get('finished', None)
        search_string = args.get('search_string', "")
        sort_desc = args.get('sort_desc', False)
        also_search_children=args.get('also_search_children', False)
        if search_string == "":
            raise ValidationError("A search string is required.")
        if agent:
            commits = agent.search_commitments(search_string=search_string, finished=finished, sort_desc=sort_desc, also_search_children=also_search_children)
            if page:
                from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
                paginator = Paginator(commits, 25)
                try:
                    commits = paginator.page(page)
                except PageNotAnInteger:
                    # If page is not an integer, deliver first page.
                    commits = paginator.page(1)
                except EmptyPage:
                    # If page is out of range (e.g. 9999), deliver last page of results.
                    commits = paginator.page(paginator.num_pages)
            return commits
        return None

    def resolve_agent_relationships(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        cat = args.get('category')
        role_id = args.get('role_id')
        if cat and role_id:
            raise ValidationError('Please do not submit both category and role.')
        if agent:
            assocs = agent.all_active_associations()
            filtered_assocs = []
            if role_id:
                for assoc in assocs:
                    if assoc.association_type.id == role_id:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            if cat:
                for assoc in assocs:
                    if assoc.association_type.category == cat:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            else:
                return assocs
        return None

    def resolve_agent_relationships_as_subject(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        cat = args.get('category')
        role_id = args.get('role_id')
        if cat and role_id:
            raise ValidationError('Please do not submit both category and role.')
        if agent:
            assocs = agent.active_associates_as_subject()
            filtered_assocs = []
            if role_id:
                for assoc in assocs:
                    if assoc.association_type.id == role_id:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            if cat:
                for assoc in assocs:
                    if assoc.association_type.category == cat:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            else:
                return assocs
        return None

    def resolve_agent_relationships_as_object(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        cat = args.get('category')
        role_id = args.get('role_id')
        if cat and role_id:
            raise ValidationError('Please do not submit both category and role.')
        if agent:
            assocs = agent.active_associates_as_object()
            filtered_assocs = []
            if role_id:
                for assoc in assocs:
                    if assoc.association_type.id == role_id:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            if cat:
                for assoc in assocs:
                    if assoc.association_type.category == cat:
                        filtered_assocs.append(assoc)
                return filtered_assocs
            else:
                return assocs
        return None

    def resolve_is_member_of(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        group_agent_id = args.get('agent_id')
        if agent and group_agent_id:
            return agent.is_member_of_agent(agent_id=group_agent_id)
        return False

    def resolve_agent_roles(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            return agent.active_association_types()
        return None

    def resolve_agent_recipes(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            return agent.recipes()
        return None

    def resolve_faircoin_address(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        return agent.faircoin_address()

    def resolve_agent_notification_settings(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        return agent.notification_settings()

    #Returns member type associations ordered by the type (hard-coded manager then member).
    def resolve_member_relationships(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        if agent:
            assocs = agent.all_active_associations()
            filtered_assocs = []
            for assoc in assocs:
                if assoc.association_type.association_behavior == "manager":
                    filtered_assocs.append(assoc)
            for assoc in assocs:
                if assoc.association_type.association_behavior == "member":
                    filtered_assocs.append(assoc)
            return filtered_assocs
        return None

    def resolve_agent_skills(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        return agent.skills()

    def resolve_agent_skill_relationships(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        return agent.skill_relationships()

    def resolve_commitments_matching_skills(self, context, **args): #args, context, info):
        agent = _load_identified_agent(self)
        page = args.get('page', None)
        if agent:
            commits = agent.commitments_with_my_skills()
            if page:
                from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
                paginator = Paginator(commits, 25)
                try:
                    commits = paginator.page(page)
                except PageNotAnInteger:
                    # If page is not an integer, deliver first page.
                    commits = paginator.page(1)
                except EmptyPage:
                    # If page is out of range (e.g. 9999), deliver last page of results.
                    commits = paginator.page(paginator.num_pages)
            return commits
        return None

    def resolve_validated_events_count(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        month = args.get('month')
        year = args.get('year')
        val_month = False
        if month and year:
            val_month=True
        if agent:
            events = agent.involved_in_events().exclude(event_type__name="Give").exclude(event_type__name="Receive")
            count = 0
            for event in events:
                if val_month:
                    if event.event_date.year == year and event.event_date.month == month:
                        if event.is_double_validated():
                            count = count + 1
                else:
                    count = count + 1
            return count
        return None

    def resolve_events_count(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        if agent:
            year = args.get('year')
            month = args.get('month')
            count_month = False
            if year and month:
                count_month = True
            events = agent.involved_in_events().exclude(event_type__name="Give").exclude(event_type__name="Receive")
            count = 0
            for event in events:
                if count_month:
                    if event.event_date.year == year and event.event_date.month == month:
                        count = count + 1
                else:
                    count = count + 1
            return count
        return None

    def resolve_event_hours_count(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        if agent:
            year = args.get('year')
            month = args.get('month')
            count_month = False
            if year and month:
                count_month = True
            events = agent.involved_in_events().exclude(event_type__name="Give").exclude(event_type__name="Receive")
            count = 0
            for event in events:
                if count_month:
                    if event.event_date.year == year and event.event_date.month == month:
                        count = count + event.quantity
                else:
                    count = count + event.quantity
            return count
        return None

    def resolve_event_people_count(self, context, **args): #args, *rargs):
        agent = _load_identified_agent(self)
        if agent:
            year = args.get('year')
            month = args.get('month')
            count_month = False
            if year and month:
                count_month = True
            events = agent.involved_in_events().exclude(event_type__name="Give").exclude(event_type__name="Receive")
            people = []
            for event in events:
                if count_month:
                    if event.event_date.year == year and event.event_date.month == month:
                        if event.from_agent not in people:
                            people.append(event.from_agent)
                else:
                    if event.from_agent not in people:
                        people.append(event.from_agent)
            return len(people)
        return None

    # returns resource classifications that have a recipe, for this and parent agents
    #def resolve_agent_recipe_bundles(self, args, context, info):
    #    agent = _load_identified_agent(self)
    #    if agent:
    #        return agent.get_resource_type_lists()
    #    return None


# ValueFlows type for a Person (singular) Agent.
# In OCP there are no different properties, but some different behavior/filtering.

class Person(DjangoObjectType):
    class Meta:
        interfaces = (Agent, )
        model = PersonModel #EconomicAgent
        fields = ('id', 'name', 'image', 'note', 'primary_location', 'email')


# Organization - an Agent which is not a Person, and can be further classified from there

class Organization(DjangoObjectType):

    class Meta:
        interfaces = (Agent, )
        model = OrganizationModel #EconomicAgent
        fields = ('id', 'name', 'image', 'note', 'primary_location', 'email')
