import datetime
import time
import csv
import copy
from operator import itemgetter, attrgetter, methodcaller

from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import validators
from django.forms.models import formset_factory, modelformset_factory, inlineformset_factory, BaseModelFormSet
from django.forms import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json as simplejson
from collections import OrderedDict
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings
from django.contrib.sites.models import Site
from django_comments.models import Comment, CommentFlag
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import send_mail

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.forms import *
from valuenetwork.valueaccounting.service import ExchangeService
from valuenetwork.valueaccounting.utils import *
from work.models import MembershipRequest, SkillSuggestion, Ocp_Artwork_Type
from work.forms import ContextTransferForm, ContextTransferCommitmentForm, ResourceRoleContextAgentForm
from work.utils import *
#from account.utils import password_generator # TODO find another

import string
from random import *
def password_generator():
    characters = string.ascii_letters + string.punctuation  + string.digits
    password =  "".join(choice(characters) for x in range(randint(8, 16)))
    return password

if "pinax.notifications" in settings.INSTALLED_APPS:
    from pinax.notifications import models as notification
else:
    notification = None

def get_agent(request):
    agent = None
    try:
        au = request.user.agent
        agent = au.agent
    except:
        pass
    return agent

def get_help(page_name):
    try:
        return Help.objects.get(page=page_name)
    except Help.DoesNotExist:
        return None

#def get_site_name():
#    return Site.objects.get_current().name

def get_site_name(request=None):
    if request:
        domain = request.get_host()
        try:
            obj = settings.PROJECTS_LOGIN
            for pro in obj:
                if obj[pro]['domains']:
                    if domain in obj[pro]['domains']:
                        proj = get_object_or_404(Project, fobi_slug=pro)
                        if proj:
                            return proj.agent.name
        except:
            pass
    return Site.objects.get_current().name


def home(request):
    layout = None
    try:
        layout = HomePageLayout.objects.get(id=1)
    except HomePageLayout.DoesNotExist:
        pass
    template_params = {
        "layout": layout,
        "photo_size": (128, 128),
        "help": get_help("home"),
    }
    if layout:
        if layout.use_work_panel:
            template_params = work_to_do(template_params)
        if layout.use_needs_panel:
            #todo: reqs needs a lot of work
            reqs = Commitment.objects.to_buy()
            stuff = OrderedDict()
            for req in reqs:
                if req.resource_type not in stuff:
                    stuff[req.resource_type] = Decimal("0")
                stuff[req.resource_type] += req.purchase_quantity
            template_params["stuff_to_buy"] = stuff
        if layout.use_creations_panel:
            vcs = Commitment.objects.filter(event_type__relationship="out")
            value_creations = []
            rts = []
            for vc in vcs:
                if vc.fulfilling_events():
                    if vc.resource_type not in rts:
                        rts.append(vc.resource_type)
                        value_creations.append(vc)
            template_params["value_creations"] = value_creations
    return render(request, "homepage.html",
        template_params)

def work_to_do(template_params):
    template_params["work_to_do"] = Commitment.objects.unfinished().filter(
        from_agent=None,
        event_type__relationship="work")
    return template_params

@login_required
def create_agent(request):
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'valueaccounting/no_permission.html')
    if request.method == "POST":
        form = AgentCreateForm(request.POST)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.created_by=request.user
            agent.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/agent', agent.id))
    return HttpResponseRedirect("/accounting/agents/")

@login_required
def create_user(request, agent_id):
    if not request.user.is_staff:
        return render(request, 'valueaccounting/no_permission.html')
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    if request.method == "POST":
        user_form = UserCreationForm(data=request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.email = agent.email
            is_staff = request.POST.get("is_staff")
            if is_staff == 'on':
                user.is_staff = True
            #user.last_login = datetime.datetime.now()
            user.save()
            au = AgentUser(
                agent = agent,
                user = user)
            au.save()
            agent.request_faircoin_address()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/agent', agent.id))


@login_required
def create_user_and_agent(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    user_form = UserCreationForm(data=request.POST or None)
    agent_form = AgentForm(data=request.POST or None)
    agent_selection_form = AgentSelectionForm()
    if request.method == "POST":
        sa_id = request.POST.get("selected_agent")
        agent = None
        if sa_id:
            agent = EconomicAgent.objects.get(id=sa_id)
        if agent_form.is_valid():
            nick = request.POST.get("nick")
            description = request.POST.get("description")
            url = request.POST.get("url")
            address = request.POST.get("address")
            email = request.POST.get("email")
            agent_type_id = request.POST.get("agent_type")
            errors = False
            password1 = request.POST.get("password1")
            password2 = request.POST.get("password2")
            username = request.POST.get("username")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")  or ""
            if password1:
                if password1 != password2:
                    errors = True
                if not username:
                    errors = True
                user_form.is_valid()
            if not errors:
                if agent:
                    agent.description = description
                    agent.url = url
                    agent.address = address
                    if agent_type_id:
                        if agent.agent_type.id != agent_type_id:
                            agent_type = AgentType.objects.get(id=agent_type_id)
                            agent.agent_type = agent_type
                    if not agent.email:
                        agent.email = email
                else:
                    if nick and first_name:
                        try:
                            agent = EconomicAgent.objects.get(nick=nick)
                            errors = True
                        except EconomicAgent.DoesNotExist:
                            pass
                    else:
                        errors = True
                    if not errors:
                        name = " ".join([first_name, last_name])
                        agent_type = AgentType.objects.get(id=agent_type_id)
                        agent = EconomicAgent(
                            nick = nick,
                            name = name,
                            description = description,
                            url = url,
                            address = address,
                            agent_type = agent_type,
                        )
                if not errors:
                    if user_form.is_valid():
                        agent.created_by=request.user
                        agent.save()
                        user = user_form.save(commit=False)
                        user.first_name = request.POST.get("first_name")
                        user.last_name = request.POST.get("last_name")
                        user.email = request.POST.get("email")
                        user.save()
                        au = AgentUser(
                            agent = agent,
                            user = user)
                        au.save()
                        return HttpResponseRedirect('/%s/%s/'
                            % ('accounting/agent', agent.id))

    return render(request, "valueaccounting/create_user_and_agent.html", {
        "user_form": user_form,
        "agent_form": agent_form,
        "agent_selection_form": agent_selection_form,
    })

def projects(request):
    page = request.GET.get('page', 1)
    project_name = request.POST.get('project_name', '')

    projects = EconomicAgent.objects.context_agents()
    if project_name:
        projects = projects.filter(name__icontains=project_name)

    paginator = Paginator(projects, 25)

    try:
        projects = paginator.page(page)
        print(projects)
        roots = [p for p in projects if p.is_root()]
        for root in roots:
            root.nodes = root.child_tree()
            annotate_tree_properties(root.nodes)
            for node in root.nodes:
                aats = []
                for aat in node.agent_association_types():
                    if aat.association_behavior != "child":
                        aat.assoc_count = node.associate_count_of_type(aat.identifier)
                        assoc_list = node.all_has_associates_by_type(aat.identifier)
                        for assoc in assoc_list:
                            associations = AgentAssociation.objects.filter(is_associate=assoc, has_associate=node, association_type=aat)
                            if associations:
                                association = associations[0]
                                assoc.state = association.get_state_display()
                        aat.assoc_list = assoc_list
                        aats.append(aat)
                node.aats = aats
        agent = get_agent(request)
        agent_form = AgentCreateForm()
        nicks = '~'.join([
            agt.nick for agt in EconomicAgent.objects.all()])
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        projects = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        projects = paginator.page(paginator.num_pages)
    except Exception as e:
        print("EXCEPT: ", str(e))


    return render(request, "valueaccounting/projects.html", {
        "roots": roots,
        "projects": projects,
        "agent": agent,
        "help": get_help("projects"),
        "agent_form": agent_form,
        "nicks": nicks,
    })

'''
@login_required
def create_project(request):
    agent = get_agent(request)
    if not agent:
        return render(request, 'valueaccounting/no_permission.html')
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.nick = project.name
            ats = AgentType.objects.filter(party_type="team")
            if ats:
                project.agent_type = ats[0]
            else:
                return HttpResponseNotFound('<h1>No project AgentTypes</h1>')
            project.created_by=request.user
            project.save()
    return HttpResponseRedirect("/accounting/projects/")

'''

def locations(request):
    agent = get_agent(request)
    locations = Location.objects.all()
    nolocs = Location.objects.filter(latitude=0.0)
    latitude = settings.MAP_LATITUDE
    longitude = settings.MAP_LONGITUDE
    zoom = settings.MAP_ZOOM
    return render(request, "valueaccounting/locations.html", {
        "agent": agent,
        "locations": locations,
        "nolocs": nolocs,
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
        "help": get_help("locations"),
    })

@login_required
def create_location(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'valueaccounting/no_permission.html')
    if agent:
        init= {
            "name": agent.name,
            "address": agent.address,
        }
        location_form = LocationForm(initial=init, data=request.POST or None)
    else:
        location_form = LocationForm(data=request.POST or None)
    latitude = settings.MAP_LATITUDE
    longitude = settings.MAP_LONGITUDE
    zoom = settings.MAP_ZOOM
    if request.method == "POST":
        if location_form.is_valid():
            location = location_form.save()
            agent_id = request.POST.get("agentId")
            if agent_id:
                agent.primary_location = location
                agent.save()
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/agent', agent.id))
            else:
                return HttpResponseRedirect("/accounting/locations/")
    return render(request, "valueaccounting/create_location.html", {
        "agent": agent,
        "location_form": location_form,
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
    })

"""@login_required
def request_faircoin_address(request, agent_id=None):
    if request.method == "POST":
        agent = None
        if agent_id:
            agent = get_object_or_404(EconomicAgent, id=agent_id)
        user_agent = get_agent(request)
        if not user_agent:
            return render(request, 'valueaccounting/no_permission.html')
        if agent:
            agent.request_faircoin_address()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))
"""

@login_required
def change_location(request, location_id, agent_id=None):
    agent = None
    location = get_object_or_404(Location, id=location_id)
    locationAddress = location.address
    location_agents = None
    if location.agents():
        location_agents = ", ".join([agt.name for agt in location.agents()])
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'valueaccounting/no_permission.html')
    location_form = ChangeLocationForm(instance=location, data=request.POST or None)
    latitude = settings.MAP_LATITUDE
    longitude = settings.MAP_LONGITUDE
    zoom = settings.MAP_ZOOM
    if request.method == "POST":
        if location_form.is_valid():
            data = location_form.cleaned_data
            agents_to_add = data["agents"]
            agents_to_remove = data["remove_agents"]
            location = location_form.save()
            for agt in agents_to_add:
                if not agt.primary_location:
                    agt.primary_location = location
                    agt.save()
            for agt in agents_to_remove:
                agt.primary_location = None
                agt.save()
            if agent:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/agent', agent.id))
            else:
                return HttpResponseRedirect("/accounting/locations/")
    return render(request, "valueaccounting/change_location.html", {
        "agent": agent,
        "locationAddress": locationAddress,
        "location_agents": location_agents,
        "location_form": location_form,
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
    })

@login_required
def add_agent_to_location(request, location_id, agent_id=None):
    location = get_object_or_404(Location, id=location_id)
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    agent.primary_location = location
    agent.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/agent', agent.id))

@login_required
def change_agent(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'valueaccounting/no_permission.html')
    change_form = AgentCreateForm(instance=agent, data=request.POST or None)
    if request.method == "POST":
        if change_form.is_valid():
            agent = change_form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/agent', agent.id))

def agents(request):
    user_agent = get_agent(request)
    agents = EconomicAgent.objects.all().order_by("agent_type__name", "name")
    agent_form = AgentCreateForm()
    nicks = '~'.join([
        agt.nick for agt in EconomicAgent.objects.all()])

    return render(request, "valueaccounting/agents.html", {
        "agents": agents,
        "agent_form": agent_form,
        "user_agent": user_agent,
        "help": get_help("agents"),
        "nicks": nicks,
    })

def radial_graph(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    agents = agent.with_all_associations()
    connections = {}
    for agnt in agents:
        if agnt not in connections:
            connections[agnt] = 0
        cxs = [assn.is_associate for assn in agnt.all_has_associates()]
        for cx in cxs:
            if cx not in connections:
                connections[cx] = 0
            connections[cx] += 1

    return render(request, "valueaccounting/radial_graph.html", {
        "agents": agents,
        "root": agent,
    })

def agent(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True
    change_form = AgentCreateForm(instance=agent)
    nav_form = InternalExchangeNavForm(data=request.POST or None)
    if agent:
        if request.method == "POST":
            if nav_form.is_valid():
                data = nav_form.cleaned_data
                ext = data["exchange_type"]
            return HttpResponseRedirect('/%s/%s/%s/%s/'
                % ('accounting/exchange', ext.id, 0, agent.id))
    user_form = None
    #if agent.is_individual():
    if not agent.username():
        # TODO inactive until we find another 'password_generator'...
        password1 = password2 = password_generator()
        init = {"username": agent.nick, "password1": password1, "password2": password2,}
        user_form = UserCreationForm(initial=init)
        user_form.fields['password1'].widget.render_value = True
        user_form.fields['password2'].widget.render_value = True
    has_associations = agent.all_has_associates()
    is_associated_with = agent.all_is_associates()

    headings = []
    member_hours_recent = []
    member_hours_stats = []
    individual_stats = []
    member_hours_roles = []
    roles_height = 400

    membership_request = agent.membership_request()

    if agent.is_individual():
        contributions = agent.given_events.filter(is_contribution=True)
        agents_stats = {}
        for ce in contributions:
            agents_stats.setdefault(ce.resource_type, Decimal("0"))
            agents_stats[ce.resource_type] += ce.quantity
        for key, value in list(agents_stats.items()):
            individual_stats.append((key, value))
        individual_stats.sort(key=lambda x: x[1], reverse=True)

    elif agent.is_context_agent():

        subs = agent.with_all_sub_agents()
        end = datetime.date.today()
        #end = end - datetime.timedelta(days=77)
        start =  end - datetime.timedelta(days=60)
        events = EconomicEvent.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs,
            event_date__range=(start, end))

        if events:
            agents_stats = {}
            for event in events:
                agents_stats.setdefault(event.from_agent.name, Decimal("0"))
                agents_stats[event.from_agent.name] += event.quantity
            for key, value in list(agents_stats.items()):
                member_hours_recent.append((key, value))
            member_hours_recent.sort(key=lambda x: x[1], reverse=True)


        ces = CachedEventSummary.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs)

        if ces.count():
            agents_stats = {}
            for ce in ces:
                agents_stats.setdefault(ce.agent.name, Decimal("0"))
                agents_stats[ce.agent.name] += ce.quantity
            for key, value in list(agents_stats.items()):
                member_hours_stats.append((key, value))
            member_hours_stats.sort(key=lambda x: x[1], reverse=True)

            agents_roles = {}
            roles = [ce.quantity_label() for ce in ces]
            roles = list(set(roles))
            for ce in ces:
                if ce.quantity:
                    name = ce.agent.name
                    row = [name, ]
                    for i in range(0, len(roles)):
                        row.append(Decimal("0.0"))
                        key = ce.agent.name
                    agents_roles.setdefault(key, row)
                    idx = roles.index(ce.quantity_label()) + 1
                    agents_roles[key][idx] += ce.quantity
            headings = ["Member",]
            headings.extend(roles)
            for row in list(agents_roles.values()):
                member_hours_roles.append(row)
            member_hours_roles.sort(key=lambda x: x[0])
            roles_height = len(member_hours_roles) * 20

    return render(request, "valueaccounting/agent.html", {
        "agent": agent,
        "membership_request": membership_request,
        "photo_size": (128, 128),
        "change_form": change_form,
        "user_form": user_form,
        "nav_form": nav_form,
        "user_agent": user_agent,
        "user_is_agent": user_is_agent,
        "has_associations": has_associations,
        "is_associated_with": is_associated_with,
        "headings": headings,
        "member_hours_recent": member_hours_recent,
        "member_hours_stats": member_hours_stats,
        "member_hours_roles": member_hours_roles,
        "individual_stats": individual_stats,
        "roles_height": roles_height,
        "help": get_help("agent"),
        "use_faircoin": True if 'faircoin' in settings.INSTALLED_APPS else False,
    })

def accounting(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    accounts = agent.events_by_event_type()


    return render(request, "valueaccounting/accounting.html", {
        "agent": agent,
        "accounts": accounts,
    })

@login_required
def test_patterns(request):
    pattern_form = PatternSelectionForm(data=request.POST or None)
    pattern = None
    slots = []
    if request.method == "POST":
        if pattern_form.is_valid():
            pattern = pattern_form.cleaned_data["pattern"]
            slots = pattern.event_types()
            for slot in slots:
                slot.resource_types = pattern.get_resource_types(slot)
                slot.facets = pattern.facets_for_event_type(slot)

    return render(request, "valueaccounting/test_patterns.html", {
        "pattern_form": pattern_form,
        "pattern": pattern,
        "slots": slots,
    })

@login_required
def maintain_patterns(request, use_case_id=None):
    patterns = []
    pattern_form = None
    if use_case_id:
        use_case = get_object_or_404(UseCase, id=use_case_id)
        init = {"use_case": use_case,}
        use_case_form = UseCaseSelectionForm(initial=init, data=request.POST or None)
        patterns = [puc.pattern for puc in use_case.patterns.all()] #patterns assigned to this use case
        pattern_ids = [p.id for p in patterns]
        if use_case.allows_more_patterns():
            allowed_patterns = use_case.allowed_patterns()
            allowed_pattern_ids = [p.id for p in allowed_patterns]
            qs = ProcessPattern.objects.filter(id__in=allowed_pattern_ids).exclude(id__in=pattern_ids)
            pattern_form = PatternSelectionForm(queryset=qs)
    else:
        use_case=None
        use_case_form = UseCaseSelectionForm(data=request.POST or None)
    if request.method == "POST":
        if use_case_form.is_valid():
            use_case = use_case_form.cleaned_data["use_case"]
            patterns = [puc.pattern for puc in use_case.patterns.all()]
            pattern_ids = [p.id for p in patterns]
            if use_case.allows_more_patterns():
                allowed_patterns = use_case.allowed_patterns()
                allowed_pattern_ids = [p.id for p in allowed_patterns]
                qs = ProcessPattern.objects.filter(id__in=allowed_pattern_ids).exclude(id__in=pattern_ids)
                pattern_form = PatternSelectionForm(queryset=qs)

    return render(request, "valueaccounting/maintain_patterns.html", {
        "use_case_form": use_case_form,
        "use_case": use_case,
        "patterns": patterns,
        "pattern_form": pattern_form,
    })

@login_required
def exchange_types(request):
    if request.method == "POST":
        new_form = NewExchangeTypeForm(data=request.POST)
        if new_form.is_valid():
            ext = new_form.save(commit=False)
            ext.created_by = request.user
            ext.save()

    supply_exchange_types = ExchangeType.objects.supply_exchange_types()
    demand_exchange_types = ExchangeType.objects.demand_exchange_types()
    internal_exchange_types = ExchangeType.objects.internal_exchange_types()
    new_form = NewExchangeTypeForm()

    return render(request, "valueaccounting/exchange_types.html", {
        "supply_exchange_types": supply_exchange_types,
        "demand_exchange_types": demand_exchange_types,
        "internal_exchange_types": internal_exchange_types,
        "new_form": new_form,
    })

@login_required
def change_exchange_type(request, exchange_type_id):
    exchange_type = get_object_or_404(ExchangeType, id=exchange_type_id)
    slots = exchange_type.slots()
    change_ext_form = ExchangeTypeForm(instance=exchange_type, data=request.POST or None)
    add_tt_form = TransferTypeForm(data=request.POST or None)
    for slot in slots:
        FacetValueFormSet = modelformset_factory(
            TransferTypeFacetValue,
            form=TransferTypeFacetValueForm,
            can_delete=True,
            extra=2,
            )
        facet_value_formset = FacetValueFormSet(
            queryset=slot.facet_values.all(),
            prefix=str(slot.id))
        slot.formset = facet_value_formset
        slot.rts = ResourceTypeSelectionForm(
            qs=slot.get_resource_types(),
            prefix=str(slot.id))

    if request.method == "POST":
        save_ext = request.POST.get("save_ext")
        #add_tt = request.POST.get("add_tt")
        if save_ext:
            if change_ext_form.is_valid():
                ext = change_ext_form.save(commit=False)
                ext.changed_by = request.user
                ext.save()

        else: #save transfer type facet values
            for slot in slots:
                FacetValueFormSet = modelformset_factory(
                    TransferTypeFacetValue,
                    form=TransferTypeFacetValueForm,
                    can_delete=True,
                    extra=2,
                    )
                facet_value_formset = FacetValueFormSet(
                    queryset=slot.facet_values.all(),
                    data=request.POST or None,
                    prefix=str(slot.id))
                slot.formset = facet_value_formset
                slot.rts = ResourceTypeSelectionForm(
                    qs=slot.get_resource_types(),
                    prefix=str(slot.id))
            for slot in slots:
                for form in slot.formset:
                    if form.is_valid():
                        data = form.cleaned_data
                        old_value = data.get("id")
                        new_value = data.get("facet_value")
                        if old_value:
                            if data["DELETE"]:
                                old_value.delete()
                            elif old_value.facet_value != new_value:
                                if new_value:
                                    form.save()
                        elif new_value:
                            if not data["DELETE"]:
                                fv = TransferTypeFacetValue(
                                    transfer_type=slot,
                                    facet_value=new_value)
                                fv.save()

            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/change-exchange-type', exchange_type.id))


    return render(request, "valueaccounting/change_exchange_type.html", {
        "exchange_type": exchange_type,
        "change_ext_form": change_ext_form,
        "add_tt_form": add_tt_form,
        "slots": slots,
    })

@login_required
def add_transfer_type(request, exchange_type_id):
    exchange_type = get_object_or_404(ExchangeType, pk=exchange_type_id)
    if request.method == "POST":
        form = TransferTypeForm(data=request.POST or None)
        if form.is_valid():
            tt = form.save(commit=False)
            tt.created_by = request.user
            tt.exchange_type = exchange_type
            tt.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/change-exchange-type', exchange_type.id))

@login_required
def change_transfer_type(request, transfer_type_id):
    tt = get_object_or_404(TransferType, pk=transfer_type_id)
    if request.method == "POST":
        form = TransferTypeForm(instance=tt, data=request.POST, prefix=tt.form_prefix())
        if form.is_valid():
            tt = form.save(commit=False)
            tt.changed_by = request.user
            tt.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/change-exchange-type', tt.exchange_type.id))

@login_required
def delete_transfer_type(request, transfer_type_id):
    tt = get_object_or_404(TransferType, id=transfer_type_id)
    if request.method == "POST":
        if tt.is_deletable():
            tt.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/change-exchange-type', tt.exchange_type.id))


class AddFacetValueFormFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.qs = kwargs.pop('qs', None)
        super(AddFacetValueFormFormSet, self).__init__(*args, **kwargs)

    def _construct_forms(self):
        self.forms = []
        for i in range(self.total_form_count()):
            self.forms.append(self._construct_form(i, qs=self.qs))


@login_required
def change_pattern(request, pattern_id, use_case_id):
    pattern = get_object_or_404(ProcessPattern, id=pattern_id)
    use_case = get_object_or_404(UseCase, id=use_case_id)
    slots = use_case.allowed_event_types()
    for slot in slots:
        slot.resource_types = pattern.get_resource_types(slot)
        slot.facets = pattern.facets_for_event_type(slot)
        FacetValueFormSet = modelformset_factory(
            PatternFacetValue,
            form=PatternFacetValueForm,
            can_delete=True,
            extra=2,
            )
        facet_value_formset = FacetValueFormSet(
            queryset=slot.facets,
            data=request.POST or None,
            prefix=slot.slug)
        slot.formset = facet_value_formset
        slot.rts = ResourceTypeSelectionForm(
            qs=slot.resource_types,
            prefix=slot.slug)
    slot_ids = [slot.id for slot in slots]

    if request.method == "POST":
        for slot in slots:
            for form in slot.formset:
                if form.is_valid():
                    data = form.cleaned_data
                    old_value = data.get("id")
                    new_value = data.get("facet_value")
                    if old_value:
                        if data["DELETE"]:
                            old_value.delete()
                        elif old_value.facet_value != new_value:
                            if new_value:
                                form.save()
                    elif new_value:
                        if not data["DELETE"]:
                            fv = PatternFacetValue(
                                pattern=pattern,
                                event_type=slot,
                                facet_value=new_value)
                            fv.save()

        return HttpResponseRedirect('/%s/%s/%s/'
            % ('accounting/change-pattern', pattern.id, use_case.id))

    return render(request, "valueaccounting/change_pattern.html", {
        "pattern": pattern,
        "slots": slots,
        "use_case": use_case,
    })

@login_required
def change_pattern_name(request):
    if request.method == "POST":
        pattern_id = request.POST.get("patternId")
        try:
            pattern = ProcessPattern.objects.get(id=pattern_id)
        except ProcessPattern.DoesNotExist:
            pattern = None
        if pattern:
            name = request.POST.get("name")
            pattern.name = name
            pattern.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def add_pattern_to_use_case(request, use_case_id):
    if request.method == "POST":
        use_case = get_object_or_404(UseCase, id=use_case_id)
        add_pattern = request.POST.get("add-pattern")
        new_pattern = request.POST.get("new-pattern")
        if add_pattern:
            form = PatternSelectionForm(data=request.POST)
            if form.is_valid():
                pattern = form.cleaned_data["pattern"]
                puc = PatternUseCase(
                    pattern=pattern,
                    use_case=use_case)
                puc.save()
        if new_pattern:
            pattern_name = request.POST.get("pattern-name")
            if pattern_name:
                pattern = ProcessPattern(name=pattern_name)
                pattern.save()
                puc = PatternUseCase(
                    pattern=pattern,
                    use_case=use_case)
                puc.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/maintain-patterns', use_case_id))

@login_required
def remove_pattern_from_use_case(request, use_case_id, pattern_id):
    if request.method == "POST":
        puc = get_object_or_404(PatternUseCase, use_case__id=use_case_id, pattern__id=pattern_id)
        puc.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/maintain-patterns', use_case_id))


@login_required
def delete_exchange_type(request, exchange_type_id):
    if request.method == "POST":
        ext = get_object_or_404(ExchangeType, id=exchange_type_id)
        if ext.is_deletable():
            ext.delete()
    return HttpResponseRedirect('/%s/'
        % ('accounting/exchange-types'))

@login_required
def sessions(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    from django.contrib.sessions.models import Session
    sessions = Session.objects.all().order_by('-expire_date')[0:20]
    for session in sessions:
        data = session.get_decoded()
        try:
            session.user = User.objects.get(id=data['_auth_user_id'])
        except:
            session.user = "guest"
    selected_session = None
    if request.method == "POST":
        spk = request.POST.get("session")
        if spk:
            try:
                ss = Session.objects.get(pk=spk)
                selected_session = ss
                data = selected_session.get_decoded()
                try:
                    selected_session.user = User.objects.get(id=data['_auth_user_id'])
                except:
                    selected_session.user = "guest"
            except Session.DoesNotExist:
                pass

    return render(request, "valueaccounting/sessions.html", {
        "sessions": sessions,
        "selected_session": selected_session,
    })

def select_resource_types(facet_values):
    """ Logic:
        Facet values in different Facets are ANDed.
        Ie, a resource type must have all of those facet values.
        Facet values in the same Facet are ORed.
        Ie, a resource type must have at least one of those facet values.
    """
    fv_ids = [fv.id for fv in facet_values]
    rt_facet_values = ResourceTypeFacetValue.objects.filter(facet_value__id__in=fv_ids)
    rts = [rtfv.resource_type for rtfv in rt_facet_values]
    answer = []
    singles = [] #Facets with only one facet_value in the Pattern
    multis = []  #Facets with more than one facet_value in the Pattern
    aspects = {}
    for fv in facet_values:
        if fv.facet not in aspects:
            aspects[fv.facet] = []
        aspects[fv.facet].append(fv)
    for facet, facet_values in list(aspects.items()):
        if len(facet_values) > 1:
            for fv in facet_values:
                multis.append(fv)
        else:
            singles.append(facet_values[0])
    single_ids = [s.id for s in singles]
    for rt in rts:
        rt_singles = [rtfv.facet_value for rtfv in rt.facets.filter(facet_value_id__in=single_ids)]
        rt_multis = [rtfv.facet_value for rtfv in rt.facets.exclude(facet_value_id__in=single_ids)]
        if set(rt_singles) == set(singles):
            if not rt in answer:
                if multis:
                    # if multis intersect
                    if set(rt_multis) & set(multis):
                        answer.append(rt)
                else:
                    answer.append(rt)
    answer_ids = [a.id for a in answer]
    return list(EconomicResourceType.objects.filter(id__in=answer_ids))

def resource_types(request):
    roots = EconomicResourceType.objects.all()
    resource_names = '~'.join([
        res.name for res in roots])
    create_form = EconomicResourceTypeForm()
    create_formset = create_facet_formset()
    facets = Facet.objects.all()
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        selected_values = request.POST["categories"]
        if selected_values:
            vals = selected_values.split(",")
            if vals[0] == "all":
                select_all = True
                roots = EconomicResourceType.objects.all()
            else:
                select_all = False
                fvs = []
                for val in vals:
                    val_split = val.split(":")
                    fname = val_split[0]
                    fvalue = val_split[1].strip()
                    fvs.append(FacetValue.objects.get(facet__name=fname,value=fvalue))
                roots = select_resource_types(fvs)
                roots.sort(key=lambda rt: rt.label())
    return render(request, "valueaccounting/resource_types.html", {
        "roots": roots,
        "facets": facets,
        "select_all": select_all,
        "selected_values": selected_values,
        "create_form": create_form,
        "create_formset": create_formset,
        "photo_size": (128, 128),
        "help": get_help("resource_types"),
        "resource_names": resource_names,
    })


def resource_type(request, resource_type_id):
    resource_type = get_object_or_404(EconomicResourceType, id=resource_type_id)
    create_form = []
    resource_names = []
    create_role_formset = None
    agent = get_agent(request)
    if agent:
        names = EconomicResourceType.objects.values_list('name', flat=True).exclude(id=resource_type_id)
        resource_names = '~'.join(names)
        init = {"unit_of_quantity": resource_type.unit,}
        create_form = CreateEconomicResourceForm(
            data=request.POST or None,
            files=request.FILES or None,
            initial=init)
        create_role_formset = resource_role_agent_formset(prefix="resource")
        if request.method == "POST":
            if create_form.is_valid():
                resource = create_form.save(commit=False)
                resource.resource_type = resource_type
                resource.created_by = request.user
                resource.save()
                role_formset =  resource_role_agent_formset(prefix="resource", data=request.POST)
                for form_rra in role_formset.forms:
                    if form_rra.is_valid():
                        data_rra = form_rra.cleaned_data
                        if data_rra:
                            role = data_rra["role"]
                            agent = data_rra["agent"]
                            if role and agent:
                                rra = AgentResourceRole()
                                rra.agent = agent
                                rra.role = role
                                rra.resource = resource
                                rra.is_contact = data_rra["is_contact"]
                                rra.save()
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/resource', resource.id))

    return render(request, "valueaccounting/resource_type.html", {
        "resource_type": resource_type,
        "photo_size": (128, 128),
        "resource_names": resource_names,
        "agent": agent,
        "create_form": create_form,
        "create_role_formset": create_role_formset,
        "help": get_help("resource_type"),
    })

def inventory(request):
    #resources = EconomicResource.objects.select_related().filter(quantity__gt=0).order_by('resource_type')
    rts = EconomicResourceType.objects.all()
    resource_types = []
    facets = Facet.objects.all()
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        selected_values = request.POST["categories"]
        if selected_values:
            vals = selected_values.split(",")
            if vals[0] == "all":
                select_all = True
                #resources = EconomicResource.objects.select_related().filter(quantity__gt=0).order_by('resource_type')
                for rt in rts:
                    if rt.onhand_qty()>0:
                        resource_types.append(rt)
            else:
                select_all = False
                #resources = EconomicResource.objects.select_related().filter(quantity__gt=0, resource_type__category__name__in=vals).order_by('resource_type')
                fvs = []
                for val in vals:
                    val_split = val.split(":")
                    fname = val_split[0]
                    fvalue = val_split[1].strip()
                    fvs.append(FacetValue.objects.get(facet__name=fname,value=fvalue))
                rts = select_resource_types(fvs)
                for rt in rts:
                    if rt.onhand_qty()>0:
                        resource_types.append(rt)
                resource_types.sort(key=lambda rt: rt.label())
    else:
        for rt in rts:
            if rt.onhand_qty()>0:
                resource_types.append(rt)
    return render(request, "valueaccounting/inventory.html", {
        #"resources": resources,
        "resource_types": resource_types,
        "facets": facets,
        "select_all": select_all,
        "selected_values": selected_values,
        "photo_size": (128, 128),
        "help": get_help("inventory"),
    })

def resource_flow_report(request, resource_type_id):
    #todo: this report is dependent on DHEN's specific work flow, will need to be generalized
    if settings.ALL_WORK_PAGE != "/board/dhen-board/":
        return render(request, 'valueaccounting/no_permission.html')
    rt = get_object_or_404(EconomicResourceType, id=resource_type_id)
    #redo: need exchange_types as well as process_types
    #this next stmt is obsolete until we get mixed process-exchange recipes
    #pts, inheritance = rt.staged_process_type_sequence_beyond_workflow()
    # also, shd this be only onhand or all resources?
    # or onhand + sold?
    # if all, any other filters?
    if rt.direct_children():
        #lot_list = EconomicResource.objects.onhand().filter(resource_type__parent=rt)
        lot_list = EconomicResource.objects.filter(resource_type__parent=rt)
        lot_list = [lot for lot in lot_list if lot.quantity > 0 or lot.sales()]
    else:
        #lot_list = rt.resources.filter(quantity__gt=0)
        lot_list = rt.resources.all()
        lot_list = [lot for lot in lot_list if lot.quantity > 0 or lot.sales()]
    #hack to get a full set of stages upfront
    #otherwise new ones incorrectly arrive at the end of the flow
    #would be better to figure out how to insert in the correct place
    stages = []
    stages.append(ExchangeType.objects.get(id=3))
    stages.append(ExchangeType.objects.get(id=2))
    stages.append(ProcessType.objects.get(id=4))
    stages.append(ExchangeType.objects.get(id=1))
    stages.append(ProcessType.objects.get(id=5))
    sales = []
    for lot in lot_list:
        #if lot.identifier == "direct345345": #70314
        lot_process_exchange_flow = lot.process_exchange_flow()
        if lot_process_exchange_flow:
            lot_process_exchange_flow.reverse()
        lot_receipt = lot.receipt()
        lot.lot_receipt = lot_receipt
        #redo: need exchange_types as well as process_types
        #lot_pts, inheritance = rt.staged_process_type_sequence_beyond_workflow()

        #this next is obsolete, I think
        #actually, it shd map lot_process_exchange_flow to stages
        #51515 has lots of pex, which now caused lots of extra columns
        #add lot stages to common stages
        lot_pts = lot_process_exchange_flow
        for pex in lot_process_exchange_flow:
            if pex.stage:
                if pex.stage not in stages:
                    stages.append(pex.stage)
                #this makes no sense to me
                #if pex.stage not in lot_pts:
                #    lot_pts.append(pex.stage)
        #assign lot processes and exchanges to stages?
        lot_stages = copy.deepcopy(stages)
        for stage in lot_stages:
            stage_pex = []
            for pex in lot_process_exchange_flow:
                if pex.stage == stage:
                    stage_pex.append(pex)
            stage.stage_pex = stage_pex
        #if lot.identifier == "92714": #70314 AHtest
        lot.lot_stages = lot_stages
        lot.lot_process_exchange_flow = lot_process_exchange_flow
        lot_sales = []

        lot_sales = lot.sales()
        if lot_sales:
            sales.extend(lot_sales)
        lot.sales = lot_sales

    # just commented out next section because I don't understand it yet
    """
    for lot in lot_list:
        for stage in stages:
            if ptype not in lot.lot_pts:
                lot.lot_pts.append(ptype)
    """

    paginator = Paginator(lot_list, 500)
    page = request.GET.get('page')
    try:
        lots = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        lots = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        lots = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/resource_flow_report.html", {
        "lots": lots,
        "stages": stages,
        "rt": rt,
        #"sort_form": sort_form,
    })

def adjust_resource(request, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    form = ResourceAdjustmentForm(data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        if event.quantity != resource.quantity:
            new_quantity = event.quantity
            event.resource = resource
            et = EventType.objects.get(relationship="adjust")
            event.event_type = et
            event.quantity = event.quantity - resource.quantity
            event.from_agent = agent
            event.created_by = request.user
            event.event_date = datetime.date.today()
            event.unit_of_quantity = resource.resource_type.unit
            event.resource_type = resource.resource_type
            event.save()
            resource.quantity = new_quantity
            resource.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/event-history', resource.id))

def event_history(request, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    event_list = resource.events.all()
    agent = get_agent(request)
    init = {"quantity": resource.quantity,}
    adjustment_form = ResourceAdjustmentForm(initial=init)
    unit = resource.resource_type.unit

    paginator = Paginator(event_list, 25)

    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/event_history.html", {
        "resource": resource,
        "agent": agent,
        "adjustment_form": adjustment_form,
        "unit": unit,
        "events": events,
    })

@login_required
def send_faircoins(request, resource_id):
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, id=resource_id)
        agent = get_agent(request)
        send_coins_form = SendFairCoinsForm(data=request.POST)
        if send_coins_form.is_valid():
            data = send_coins_form.cleaned_data
            address_end = data["to_address"]
            quantity = data["quantity"]
            address_origin = resource.faircoin_address.address
            if address_origin and address_end:
                from_agent = resource.owner()
                exchange_service = ExchangeService.get()
                exchange_service.send_faircoins(
                    from_agent,
                    address_end,
                    quantity,
                    resource,
                )

                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/event-history', resource.id))

        return HttpResponseRedirect('/%s/%s/'
                % ('accounting/resource', resource.id))

def validate_faircoin_address(request):
    from faircoin.utils import is_valid
    data = request.GET
    address = data["to_address"]
    answer = is_valid(address)
    if answer == False:
        answer = "Invalid FairCoin address"
    response = simplejson.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")

def all_contributions(request):
    event_list = EconomicEvent.objects.filter(is_contribution=True)
    paginator = Paginator(event_list, 25)

    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/all_contributions.html", {
        "events": events,
    })

def contributions(request, project_id):
    project = get_object_or_404(EconomicAgent, pk=project_id)
    agent = get_agent(request)
    event_list = project.contribution_events()
    agent_ids = {event.from_agent.id for event in event_list if event.from_agent}
    agents = EconomicAgent.objects.filter(id__in=agent_ids)
    filter_form = ProjectContributionsFilterForm(agents=agents, data=request.POST or None)
    if request.method == "POST":
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            #event_type = data["event_type"]
            from_agents = data["from_agents"]
            start = data["start_date"]
            end = data["end_date"]
            if from_agents:
                event_list = event_list.filter(from_agent__in=from_agents)
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
    event_ids = ",".join([str(event.id) for event in event_list])
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/project_contributions.html", {
        "project": project,
        "events": events,
        "filter_form": filter_form,
        "agent": agent,
        "event_ids": event_ids,
    })

def project_wip(request, project_id):
    project = get_object_or_404(EconomicAgent, pk=project_id)
    process_list = project.wip()
    paginator = Paginator(process_list, 25)

    page = request.GET.get('page')
    try:
        processes = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        processes = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        processes = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/project_wip.html", {
        "project": project,
        "processes": processes,
    })

def finished_processes(request, agent_id):
    project = get_object_or_404(EconomicAgent, pk=agent_id)
    process_list = project.finished_processes()
    paginator = Paginator(process_list, 25)

    page = request.GET.get('page')
    try:
        processes = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        processes = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        processes = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/finished_processes.html", {
        "project": project,
        "processes": processes,
    })

@login_required
def contribution_history(request, agent_id):
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    user_agent = get_agent(request)
    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True
    event_list = agent.contributions()
    event_types = {e.event_type for e in event_list}
    filter_form = EventTypeFilterForm(event_types=event_types, data=request.POST or None)
    if request.method == "POST":
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            et_ids = data["event_types"]
            start = data["start_date"]
            end = data["end_date"]
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
            #belt and suspenders: if no et_ids, form is not valid
            if et_ids:
                event_list = event_list.filter(event_type__id__in=et_ids)
    event_ids = ",".join([str(event.id) for event in event_list])
    paginator = Paginator(event_list, 25)

    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/agent_contributions.html", {
        "agent": agent,
        "user_is_agent": user_is_agent,
        "events": events,
        "filter_form": filter_form,
        "event_ids": event_ids,
    })

@login_required
def agent_value_accounting(request, agent_id):
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    user_agent = get_agent(request)
    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True
    event_list = agent.contributions()
    no_bucket = 0
    with_bucket = 0
    event_value = Decimal("0.0")
    claim_value = Decimal("0.0")
    outstanding_claims = Decimal("0.0")
    claim_distributions = Decimal("0.0")
    claim_distro_events = []
    for event in event_list:
        if event.bucket_rule_for_context_agent():
            with_bucket += 1
        else:
            no_bucket += 1
        for claim in event.claims():
            claim_value += claim.original_value
            outstanding_claims += claim.value
            for de in claim.distribution_events():
                claim_distributions += de.value
                claim_distro_events.append(de.event)
    et = EventType.objects.get(name="Distribution")
    all_distro_evts = EconomicEvent.objects.filter(to_agent=agent, event_type=et)
    other_distro_evts = [d for d in all_distro_evts if d not in claim_distro_events]
    other_distributions = sum(de.quantity for de in other_distro_evts)

    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/agent_value_accounting.html", {
        "agent": agent,
        "events": events,
        "no_bucket": no_bucket,
        "with_bucket": with_bucket,
        "claim_value": format(claim_value, ",.2f"),
        "outstanding_claims": format(outstanding_claims, ",.2f"),
        "claim_distributions": format(claim_distributions, ",.2f"),
        "other_distributions": format(other_distributions, ",.2f"),
    })

@login_required
def unscheduled_time_contributions(request):
    member = get_agent(request)
    if not member:
        return HttpResponseRedirect('/%s/'
            % ('accounting/work'))

    TimeFormSet = modelformset_factory(
        EconomicEvent,
        form=CasualTimeContributionForm,
        can_delete=False,
        extra=8,
        max_num=8,
        )
    init = []
    for i in range(0, 8):
        init.append({"is_contribution": True,})
    time_formset = TimeFormSet(
        queryset=EconomicEvent.objects.none(),
        initial = init,
        data=request.POST or None)
    if request.method == "POST":
        keep_going = request.POST.get("keep-going")
        just_save = request.POST.get("save")
        if time_formset.is_valid():
            events = time_formset.save(commit=False)
            pattern = None
            patterns = PatternUseCase.objects.filter(use_case__identifier='non_prod')
            if patterns:
                pattern = patterns[0].pattern
            else:
                raise ValidationError("no non-production ProcessPattern")
            if pattern:
                unit = Unit.objects.filter(
                    unit_type="time",
                    name__icontains="Hour")[0]
                for event in events:
                    if event.event_date and event.quantity:
                        event.from_agent=member
                        event.to_agent = event.context_agent.default_agent()
                        #event.is_contribution=True
                        rt = event.resource_type
                        event_type = pattern.event_type_for_resource_type("work", rt)
                        event.event_type=event_type
                        event.unit_of_quantity=unit
                        event.created_by=request.user
                        event.save()
            if keep_going:
                return HttpResponseRedirect('/%s/'
                    % ('accounting/unscheduled-time'))
            else:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/contributionhistory', member.id))

    return render(request, "valueaccounting/unscheduled_time_contributions.html", {
        "member": member,
        "time_formset": time_formset,
        "help": get_help("non_production"),
    })

@login_required
def agent_associations(request, agent_id):
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    HasAssociatesFormSet = inlineformset_factory(
        EconomicAgent,
        AgentAssociation,
        fk_name = "has_associate",
        form=HasAssociateForm,
        extra=3,
        )
    has_associates_formset = HasAssociatesFormSet(
        instance=agent,
        queryset=agent.all_has_associates(),
        prefix = "has",
        data=request.POST or None)
    IsAssociatesFormSet = inlineformset_factory(
        EconomicAgent,
        AgentAssociation,
        fk_name = "is_associate",
        form=IsAssociateForm,
        extra=3,
        )
    is_associates_formset = IsAssociatesFormSet(
        instance=agent,
        queryset=agent.all_is_associates(),
        prefix = "is",
        data=request.POST or None)
    if request.method == "POST":
        keep_going = request.POST.get("keep-going")
        just_save = request.POST.get("save")
        for form in has_associates_formset:
            if form.is_valid():
                deleteme = form.cleaned_data['DELETE']
                if deleteme:
                    association = form.save(commit=False)
                    if association.id:
                        association.delete()
                else:
                    form.save()
        for form in is_associates_formset:
            if form.is_valid():
                deleteme = form.cleaned_data['DELETE']
                if deleteme:
                    association = form.save(commit=False)
                    if association.id:
                        association.delete()
                else:
                    form.save()
        if just_save:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/agent', agent.id))
        elif keep_going:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/agent-associations', agent.id))
    return render(request, "valueaccounting/agent_associations.html", {
        "agent": agent,
        "has_associates_formset": has_associates_formset,
        "is_associates_formset": is_associates_formset,
        "help": get_help("associations"),
    })

def json_resource_type_resources(request, resource_type_id):
    json = serializers.serialize("json", EconomicResource.objects.filter(resource_type=resource_type_id), fields=('identifier'))
    return HttpResponse(json, content_type='application/json')

def json_resource_type_stages(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    json = serializers.serialize("json", rt.all_stages(), fields=('name'))
    return HttpResponse(json, content_type='application/json')

def json_resource_type_resources_with_locations(request, resource_type_id):
    rs = EconomicResource.objects.filter(resource_type=resource_type_id)
    resources = []
    for r in rs:
        loc = ""
        if r.current_location:
            loc = r.current_location.name
        fields = {
            "pk": r.pk,
            "identifier": r.identifier,
            "location": loc,
        }
        resources.append({"fields": fields})
    data = simplejson.dumps(resources, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_resource(request, resource_id):
    r = get_object_or_404(EconomicResource, pk=resource_id)
    loc = ""
    if r.current_location:
        loc = r.current_location.name
    rdict = {
        "class": "EconomicResource",
        "id": r.id,
        "identifier": r.identifier,
        "location": loc,
        "quantity": str(r.quantity),
        "unit": r.resource_type.unit.name,
        "access_rules": r.access_rules,
    }
    assignments = {}
    for item in r.agent_resource_roles.all():
        assignments[item.role.name] = item.agent.name
    rdict["assignments"] = assignments
    data = simplejson.dumps(rdict)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_organization(request):
    agent_types = AgentType.objects.all()
    at_dict = {}
    for at in agent_types:
        fields = {
            "name": at.name,
            "is_context": at.is_context,
        }
        at_dict[at.name] = fields
    agents = EconomicAgent.objects.all()
    agent_dict = {}
    for agent in agents:
        fields = {
            "class": "EconomicAgent",
            "pk": agent.pk,
            "id": agent.nick,
            "name": agent.name,
            "agent_type": agent.agent_type.name,
        }
        agent_dict[agent.nick] = fields
    aa_types = AgentAssociationType.objects.all()
    aat_dict = {}
    for aat in aa_types:
        fields = {
            "name": aat.name,
            "plural_name": aat.plural_name,
            "label": aat.label,
            "inverse_label": aat.inverse_label,
            "description": aat.description,
        }
        aat_dict[aat.name] = fields
    associations = AgentAssociation.objects.all()
    assoc_dict = {}
    for a in associations:
        fields = {
            "pk": a.pk,
            "is_associate": a.is_associate.nick,
            "has_associate": a.has_associate.nick,
            "association_type": a.association_type.name,
        }
        assoc_dict[a.pk] = fields
    big_d = {
        "agentTypes": at_dict,
        "agents": agent_dict,
        "agentAssociationTypes": aat_dict,
        "agentAssociations": assoc_dict,
    }
    data = simplejson.dumps(big_d)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_distribution_related_shipment(request, distribution_id):
    d = get_object_or_404(EconomicEvent, pk=distribution_id)
    ship = d.get_shipment_for_distribution()
    sd = {}
    if ship:
        sd = {
            "ship_id": ship.id,
            "ship_description": ship.__unicode__(),
        }
    data = simplejson.dumps(sd)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_distribution_related_order(request, distribution_id):
    d = get_object_or_404(EconomicEvent, pk=distribution_id)
    order = d.get_order_for_distribution()
    od = {}
    if order:
        od = {
                "order_id": order.id,
                "order_description": order.__unicode__(),
            }
    data = simplejson.dumps(od)
    return HttpResponse(data, content_type="text/json-comment-filtered")

class EventSummary(object):
    def __init__(self, agent, role, quantity, value=Decimal('0.0')):
        self.agent = agent
        self.role = role
        self.quantity = quantity
        self.value=value

    def key(self):
        return "-".join([str(self.agent.id), str(self.role.id)])

    def quantity_formatted(self):
        return self.quantity.quantize(Decimal('.01'), rounding=ROUND_UP)


class AgentSummary(object):
    def __init__(self,
        agent,
        value=Decimal('0.0'),
        percentage=Decimal('0.0'),
        amount=Decimal('0.0'),
    ):
        self.agent = agent
        self.value=value
        self.percentage=percentage
        self.amount=amount

#obsolete
def value_equation(request, project_id):
    return render(request, 'valueaccounting/no_permission.html')
    project = get_object_or_404(EconomicAgent, pk=project_id)
    all_subs = project.with_all_sub_agents()
    summaries = CachedEventSummary.objects.select_related(
        'agent', 'context_agent', 'resource_type').filter(context_agent__in=all_subs).order_by(
        'agent__name', 'context_agent__name', 'resource_type__name')
    total = 0
    agent_totals = []
    init = {"equation": "( hours * ( rate + importance + reputation ) ) + seniority"}
    form = EquationForm(data=request.POST or None,
        initial=init)
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            equation = data["equation"]
            amount = data["amount"]
            if amount:
                amount = Decimal(amount)
            eq = equation.split(" ")
            for i, x in enumerate(eq):
                try:
                    y = Decimal(x)
                    eq[i] = "".join(["Decimal('", x, "')"])
                except InvalidOperation:
                    continue
            s = " "
            equation = s.join(eq)
            agent_sums = {}
            total = Decimal("0.00")
            safe_list = ['math',]
            safe_dict = dict([ (k, locals().get(k, None)) for k in safe_list ])
            safe_dict['Decimal'] = Decimal
            for summary in summaries:
                safe_dict['hours'] = summary.quantity
                safe_dict['rate'] = summary.resource_type_rate
                safe_dict['importance'] = summary.importance
                safe_dict['reputation'] = summary.reputation
                safe_dict['seniority'] = Decimal(summary.agent.seniority())
                summary.value = eval(equation, {"__builtins__":None}, safe_dict)
                agent = summary.agent
                if not agent.id in agent_sums:
                    agent_sums[agent.id] = AgentSummary(agent)
                agent_sums[agent.id].value += summary.value
                total += summary.value
            agent_totals = list(agent_sums.values())
            for at in agent_totals:
               pct = at.value / total
               at.value = at.value.quantize(Decimal('.01'), rounding=ROUND_UP)
               at.percentage = ( pct * 100).quantize(Decimal('.01'), rounding=ROUND_UP)
               if amount:
                   at.amount = (amount * pct).quantize(Decimal('.01'), rounding=ROUND_UP)

    paginator = Paginator(summaries, 50)
    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/value_equation.html", {
        "project": project,
        "events": events,
        "form": form,
        "agent_totals": agent_totals,
        "total": total,
    })

def extended_bill(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    output_ctype, inheritance = rt.main_producing_process_type_relationship()
    select_all = True
    facets = Facet.objects.all()
    if request.method == "POST":
        nodes = rt.generate_xbill()
        depth = 1
        for node in nodes:
            depth = max(depth, node.depth)
        selected_vals = request.POST["categories"]
        vals = selected_vals.split(",")
        selected_depth = int(request.POST['depth'])
        if vals[0]:
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                fvs = []
                for val in vals:
                    val_split = val.split(":")
                    fname = val_split[0]
                    fvalue = val_split[1].strip()
                    fvs.append(FacetValue.objects.get(facet__name=fname,value=fvalue))
        for node in nodes:
            node.show = False
            if node.depth <= selected_depth:
                if select_all:
                    node.show = True
                else:
                    if node.xbill_class == "economic-resource-type":
                        if node.xbill_object().matches_filter(fvs):
                            node.show = True
                    else:
                        node.show = True
    else:
        nodes = rt.generate_xbill()
        depth = 1
        for node in nodes:
            depth = max(depth, node.depth)
            node.show = True
        selected_depth = depth
        select_all = True
        selected_vals = "all"
    return render(request, "valueaccounting/extended_bill.html", {
        "resource_type": rt,
        "output_ctype": output_ctype,
        "nodes": nodes,
        "depth": depth,
        "selected_depth": selected_depth,
        "facets": facets,
        "select_all": select_all,
        "selected_vals": selected_vals,
        "photo_size": (128, 128),
        "big_photo_size": (200, 200),
        "help": get_help("recipes"),
    })

@login_required
def edit_extended_bill(request, resource_type_id):

    #start_time = time.time()
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    output_ctype, inheritance = rt.main_producing_process_type_relationship()
    nodes = rt.generate_xbill()
    resource_type_form = EconomicResourceTypeChangeForm(instance=rt)
    feature_form = FeatureForm()
    names = EconomicResourceType.objects.values_list('name', flat=True)
    resource_names = '~'.join(names)
    #end_time = time.time()
    #print("edit_extended_bill view elapsed time was %g seconds" % (end_time - start_time))
    return render(request, "valueaccounting/edit_xbill.html", {
        "resource_type": rt,
        "output_ctype": output_ctype,
        "nodes": nodes,
        "photo_size": (128, 128),
        "big_photo_size": (200, 200),
        "resource_type_form": resource_type_form,
        "feature_form": feature_form,
        "resource_names": resource_names,
        "help": get_help("ed_asmbly_recipe"),
    })

@login_required
def edit_stream_recipe(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    process_types, inheritance = rt.staged_process_type_sequence()
    resource_type_form = EconomicResourceTypeChangeForm(instance=rt)
    names = EconomicResourceType.objects.values_list('name', flat=True)
    resource_names = '~'.join(names)
    return render(request, "valueaccounting/edit_stream_recipe.html", {
        "resource_type": rt,
        "process_types": process_types,
        "resource_names": resource_names,
        "photo_size": (128, 128),
        "resource_type_form": resource_type_form,
        "help": get_help("ed_wf_recipe"),
    })


def view_stream_recipe(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    process_types, inheritance = rt.staged_process_type_sequence()
    names = EconomicResourceType.objects.values_list('name', flat=True)
    resource_names = '~'.join(names)
    agent = get_agent(request)
    return render(request, "valueaccounting/view_stream_recipe.html", {
        "resource_type": rt,
        "agent": agent,
        "process_types": process_types,
        "resource_names": resource_names,
        "photo_size": (128, 128),
        "help": get_help("ed_wf_recipe"),
    })


@login_required
def change_resource_type(request, resource_type_id):
    if request.method == "POST":
        rtype = get_object_or_404(EconomicResourceType, pk=resource_type_id)
        form = EconomicResourceTypeChangeForm(request.POST, request.FILES, instance=rtype)
        if form.is_valid():
            data = form.cleaned_data
            rt = form.save(commit=False)
            rt.changed_by=request.user
            rt.save()
            next = request.POST.get("next")
            if next:
                return HttpResponseRedirect(next)
            else:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/edit-xbomfg', resource_type_id))
        else:
            raise ValidationError(form.errors)

@login_required
def delete_resource_type_confirmation(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    side_effects = False
    if rt.process_types.all():
        side_effects = True
        return render(request, 'valueaccounting/resource_type_delete_confirmation.html', {
            "resource_type": rt,
            "side_effects": side_effects,
            })
    else:
        rt.delete()
        return HttpResponseRedirect('/%s/'
            % ('accounting/resources'))

@login_required
def delete_resource_type(request, resource_type_id):
    if request.method == "POST":
        rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
        pts = rt.producing_process_types()
        rt.delete()
        for pt in pts:
            pt.delete()
        next = request.POST.get("next")
        if next:
            if next == "cleanup-resourcetypes":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/cleanup-resourcetypes'))
            else:
                return HttpResponseRedirect(next)
        else:
            return HttpResponseRedirect('/%s/'
                % ('accounting/resources'))

@login_required
def delete_resource(request, resource_id):
    if request.method == "POST":
        er = get_object_or_404(EconomicResource, pk=resource_id)
        er.delete()
        next = request.POST.get("next")
        if next:
            if next == "cleanup-resources":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/cleanup-resources'))
            else:
                return HttpResponseRedirect(next)
        else:
            return HttpResponseRedirect('/%s/'
                % ('accounting/cleanup-resources'))

@login_required
def delete_agent(request, agent_id):
    if request.method == "POST":
        agt = get_object_or_404(EconomicAgent, pk=agent_id)
        agt.delete()
        return HttpResponseRedirect('/%s/'
            % ('accounting/agents'))

@login_required
def delete_order_confirmation(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    pcs = order.producing_commitments()
    sked = []
    reqs = []
    work = []
    tools = []
    next = request.POST.get("next")
    if pcs:
        visited_resources = set()
        for ct in pcs:
            #visited_resources.add(ct.resource_type)
            schedule_commitment(ct, sked, reqs, work, tools, visited_resources, 0)
        return render(request, 'valueaccounting/order_delete_confirmation.html', {
            "order": order,
            "sked": sked,
            "reqs": reqs,
            "work": work,
            "tools": tools,
            "next": next,
        })
    else:
        commitments = Commitment.objects.filter(independent_demand=order)
        if commitments:
            for ct in commitments:
                sked.append(ct)
                if ct.process not in sked:
                    sked.append(ct.process)
            return render(request, 'valueaccounting/order_delete_confirmation.html', {
                "order": order,
                "sked": sked,
                "reqs": reqs,
                "work": work,
                "tools": tools,
                "next": next,
            })
        else:
            order.delete()
            if next == "demand":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/demand'))
            if next == "closed_work_orders":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/closed-work-orders'))

@login_required
def delete_order(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, pk=order_id)
        next = request.POST.get("next")
        trash = []
        visited_resources = set()
        pcs = order.producing_commitments()
        if pcs:
            for ct in pcs:
                ct.delete_dependants()
            order.delete()
            for item in trash:
                item.delete()
        else:
            commitments = Commitment.objects.filter(independent_demand=order)
            if commitments:
                processes = []
                for ct in commitments:
                    if ct.process:
                        if ct.process not in processes:
                            processes.append(ct.process)
                    for event in ct.fulfillment_events.all():
                        event.commitment = None
                        event.save()
                    ct.delete()
                for process in processes:
                    process.delete()
            order.delete()
        #next = request.POST.get("next")
        #if next:
        #    return HttpResponseRedirect(next)
        #else:
        #    return HttpResponseRedirect('/%s/'
        #        % ('accounting/demand'))
        if next == "demand":
            return HttpResponseRedirect('/%s/'
                % ('accounting/demand'))
        if next == "closed_work_orders":
            return HttpResponseRedirect('/%s/'
                % ('accounting/closed-work-orders'))
        if next == "order-list":
            return HttpResponseRedirect('/%s/'
                % ('work/order-list'))

@login_required
def delete_process_input(request,
        process_input_id, resource_type_id):
    pi = get_object_or_404(ProcessTypeResourceType, pk=process_input_id)
    pi.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-xbomfg', resource_type_id))

@login_required
def delete_process_type_input(request,
        process_input_id, resource_type_id):
    pi = get_object_or_404(ProcessTypeResourceType, pk=process_input_id)
    pi.delete()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)


@login_required
def delete_source(request,
        source_id, resource_type_id):
    s = get_object_or_404(AgentResourceType, pk=source_id)
    s.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-xbomfg', resource_type_id))

@login_required
def delete_process_type_confirmation(request,
        process_type_id, resource_type_id):
    pt = get_object_or_404(ProcessType, pk=process_type_id)
    side_effects = False
    next = request.POST.get("next")
    if next == None:
        next = '/%s/%s/' % ('accounting/edit-xbomfg', resource_type_id)
    if pt.resource_types.all():
        side_effects = True
        return render(request, 'valueaccounting/process_type_delete_confirmation.html', {
            "process_type": pt,
            "resource_type_id": resource_type_id,
            "side_effects": side_effects,
            "next": next,
            })
    else:
        pt.delete()
        return HttpResponseRedirect(next)

@login_required
def delete_feature_confirmation(request,
        feature_id, resource_type_id):
    ft = get_object_or_404(Feature, pk=feature_id)
    side_effects = False
    if ft.options.all():
        side_effects = True
        return render(request, 'valueaccounting/feature_delete_confirmation.html', {
            "feature": ft,
            "resource_type_id": resource_type_id,
            "side_effects": side_effects,
            })
    else:
        ft.delete()
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/edit-xbomfg', resource_type_id))


@login_required
def delete_process_type(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        rt = pt.main_produced_resource_type()
        if rt:
            if rt.recipe_is_staged():
                pts, inheritance = rt.staged_process_type_sequence()
                index = pts.index(pt)
                if index < len(pts) - 1:
                    if index == 0:
                        stage = None
                    else:
                        stage = pts[index - 1]
                    next_pt = pts[index + 1]
                    next_input_ptrt = next_pt.input_stream_resource_type_relationship()[0]
                    next_input_ptrt.stage = stage
                    next_input_ptrt.save()
        pt.delete()
        next = request.POST.get("next")
        if next:
            return HttpResponseRedirect(next)
        else:
            return HttpResponseRedirect('/%s/'
                % ('accounting/resources'))

@login_required
def delete_feature(request, feature_id):
    if request.method == "POST":
        ft = get_object_or_404(Feature, pk=feature_id)
        ft.delete()
        next = request.POST.get("next")
        return HttpResponseRedirect(next)

@login_required
def create_resource_type(request):
    if request.method == "POST":
        form = EconomicResourceTypeForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            rt = form.save(commit=False)
            rt.created_by=request.user
            rt.save()
            formset = create_facet_formset(data=request.POST)
            for form_rtfv in formset.forms:
                if form_rtfv.is_valid():
                    data_rtfv = form_rtfv.cleaned_data
                    fv = FacetValue.objects.get(id=data_rtfv["value"])
                    if fv:
                        rtfv = ResourceTypeFacetValue()
                        rtfv.resource_type = rt
                        rtfv.facet_value = fv
                        rtfv.save()

            next = request.POST.get("next")
            if next:
                return HttpResponseRedirect(next)
            else:
                return HttpResponseRedirect('/%s/'
                    % ('accounting/resources'))
        else:
            raise ValidationError(form.errors)

@login_required
def create_resource_type_ajax(request):
    slot = request.POST.get("slot")
    pt_id = int(request.POST.get("pt-id").replace("ProcessType-",""))
    process_type = ProcessType.objects.get(id=pt_id)
    if slot == "cite":
        rt_prefix = process_type.xbill_citable_rt_prefix()
        rtf_prefix = process_type.xbill_citable_rt_facet_prefix()
    elif slot == "use":
        rt_prefix = process_type.xbill_usable_rt_prefix()
        rtf_prefix = process_type.xbill_usable_rt_facet_prefix()
    else:
        rt_prefix = process_type.xbill_consumable_rt_prefix()
        rtf_prefix = process_type.xbill_consumable_rt_facet_prefix()
    form = EconomicResourceTypeAjaxForm(request.POST, request.FILES, prefix=rt_prefix)
    if form.is_valid():
        data = form.cleaned_data
        rt = form.save(commit=False)
        rt.created_by=request.user
        rt.save()
        formset = process_type.create_facet_formset_filtered(data=request.POST, pre=rtf_prefix, slot=slot)
        for form_rtfv in formset.forms:
            if form_rtfv.is_valid():
                data_rtfv = form_rtfv.cleaned_data
                fv = FacetValue.objects.get(id=data_rtfv["value"])
                if fv:
                    rtfv = ResourceTypeFacetValue()
                    rtfv.resource_type = rt
                    rtfv.facet_value = fv
                    rtfv.save()
        return_data = serializers.serialize("json", EconomicResourceType.objects.filter(id=rt.id), fields=('id','name',))
        return HttpResponse(return_data, content_type="text/json-comment-filtered")
    else:
        return HttpResponse(form.errors, content_type="text/json-comment-filtered")

@login_required
def create_resource_type_simple_patterned_ajax(request):
    form = EconomicResourceTypeAjaxForm(request.POST, request.FILES)
    if form.is_valid():
        data = form.cleaned_data
        rt = form.save(commit=False)
        rt.created_by=request.user
        rt.save()
        slot = request.POST["slot"]
        pattern_id = request.POST["pattern"]
        pattern = ProcessPattern.objects.get(id=pattern_id)
        formset = create_patterned_facet_formset(pattern, slot, data=request.POST)
        for form_rtfv in formset.forms:
            if form_rtfv.is_valid():
                data_rtfv = form_rtfv.cleaned_data
                fv = FacetValue.objects.get(id=data_rtfv["value"])
                if fv:
                    rtfv = ResourceTypeFacetValue()
                    rtfv.resource_type = rt
                    rtfv.facet_value = fv
                    rtfv.save()
        return_data = serializers.serialize("json", EconomicResourceType.objects.filter(id=rt.id), fields=('id','name',))
        return HttpResponse(return_data, content_type="text/json-comment-filtered")
    else:
        return HttpResponse(form.errors, content_type="text/json-comment-filtered")

@login_required
def create_process_type_input(request, process_type_id, slot):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        if slot == "c":
            et_rel = "consume"
            prefix = pt.xbill_consumable_prefix()
            form = ProcessTypeConsumableForm(data=request.POST, process_type=pt, prefix=prefix)
        elif slot == "u":
            et_rel = "use"
            prefix = pt.xbill_usable_prefix()
            form = ProcessTypeUsableForm(data=request.POST, process_type=pt, prefix=prefix)
        if form.is_valid():
            ptrt = form.save(commit=False)
            rt = form.cleaned_data["resource_type"]
            ptrt.process_type=pt
            pattern = pt.process_pattern
            event_type = pattern.event_type_for_resource_type(et_rel, rt)
            ptrt.event_type = event_type
            ptrt.created_by=request.user
            ptrt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_process_type_citable(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        prefix = pt.xbill_citable_prefix()
        form = ProcessTypeCitableForm(data=request.POST, process_type=pt, prefix=prefix)
        if form.is_valid():
            ptrt = form.save(commit=False)
            ptrt.quantity = Decimal("1.0")
            rt = form.cleaned_data["resource_type"]
            ptrt.unit_of_quantity = rt.unit
            ptrt.process_type=pt
            pattern = pt.process_pattern
            event_type = pattern.event_type_for_resource_type("cite", rt)
            ptrt.event_type = event_type
            ptrt.created_by=request.user
            ptrt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_process_type_work(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        prefix = pt.xbill_work_prefix()
        form = ProcessTypeWorkForm(data=request.POST, process_type=pt, prefix=prefix)
        if form.is_valid():
            ptrt = form.save(commit=False)
            rt = form.cleaned_data["resource_type"]
            ptrt.process_type=pt
            pattern = pt.process_pattern
            event_type = pattern.event_type_for_resource_type("work", rt)
            ptrt.event_type = event_type
            ptrt.created_by=request.user
            ptrt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_process_type_feature(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        form = FeatureForm(request.POST)
        if form.is_valid():
            feature = form.save(commit=False)
            feature.process_type=pt
            rts = pt.produced_resource_types()
            #todo: assumes the feature applies to the first
            # produced_resource_type, which might be wrong
            if rts:
                rt = rts[0]
                feature.product=rt
                pattern = pt.process_pattern
                event_type = pattern.event_type_for_resource_type("in", rt)
                feature.event_type = event_type
            else:
                #todo: when will we get here? It's a hack.
                ets = EventType.objects.filter(
                    resource_effect="-")
                event_type = ets[0]
                feature.event_type = event_type
            feature.created_by=request.user
            feature.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_options_for_feature(request, feature_id):
    if request.method == "POST":
        ft = get_object_or_404(Feature, pk=feature_id)
        form = OptionsForm(feature=ft, data=request.POST)
        if form.is_valid():
            options = eval(form.cleaned_data["options"])
            for option in options:
                rt = EconomicResourceType.objects.get(pk=int(option))
                opt = Option(
                    feature=ft,
                    component=rt)
                opt.created_by=request.user
                opt.save()

            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_options_for_feature(request, feature_id):
    if request.method == "POST":
        ft = get_object_or_404(Feature, pk=feature_id)
        form = OptionsForm(feature=ft, data=request.POST)
        if form.is_valid():
            options = form.cleaned_data["options"]
            selected_options = []
            if options:
                selected_options = eval(form.cleaned_data["options"])
                selected_options = [int(opt) for opt in selected_options]
            previous_options = ft.options.all()
            previous_ids = ft.options.values_list('component__id', flat=True)
            for option in previous_options:
                if not option.component.id in selected_options:
                    option.delete()
            for option in selected_options:
                if not option in previous_ids:
                    rt = EconomicResourceType.objects.get(pk=int(option))
                    opt = Option(
                        feature=ft,
                        component=rt)
                    opt.created_by=request.user
                    opt.save()

            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_process_type_input(request, input_id):
    if request.method == "POST":
        ptrt = get_object_or_404(ProcessTypeResourceType, pk=input_id)
        prefix = ptrt.xbill_change_prefix()
        if ptrt.event_type.relationship == "work":
            form = ProcessTypeWorkForm(
                data=request.POST,
                instance=ptrt,
                process_type=ptrt.process_type,
                prefix=prefix)
        elif ptrt.event_type.relationship == "cite":
            form = ProcessTypeCitableForm(
                data=request.POST,
                instance=ptrt,
                process_type=ptrt.process_type,
                prefix=prefix)
        else:
            form = ProcessTypeInputForm(
                data=request.POST,
                instance=ptrt,
                process_type=ptrt.process_type,
                prefix=prefix)
        if form.is_valid():
            inp = form.save(commit=False)
            inp.changed_by=request.user
            inp.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_agent_resource_type(request, agent_resource_type_id):
    if request.method == "POST":
        art = get_object_or_404(AgentResourceType, pk=agent_resource_type_id)
        prefix = art.xbill_change_prefix()
        form = AgentResourceTypeForm(data=request.POST, instance=art, prefix=prefix)
        if form.is_valid():
            art = form.save(commit=False)
            art.changed_by=request.user
            art.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_feature(request, feature_id):
    if request.method == "POST":
        ft = get_object_or_404(Feature, pk=feature_id)
        #prefix = ft.xbill_change_prefix()
        #form = FeatureForm(data=request.POST, instance=ft, prefix=prefix)
        form = FeatureForm(data=request.POST, instance=ft)
        if form.is_valid():
            feature = form.save(commit=False)
            feature.changed_by=request.user
            feature.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)


@login_required
def create_agent_resource_type(request, resource_type_id):
    if request.method == "POST":
        rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
        prefix = rt.source_create_prefix()
        form = AgentResourceTypeForm(request.POST, prefix=prefix)
        if form.is_valid():
            art = form.save(commit=False)
            art.resource_type=rt
            #todo: this is a hack
            #shd be rethought and encapsulated
            ets = EventType.objects.filter(
                related_to="agent",
                relationship="out",
                resource_effect="=")
            event_type = ets[0]
            art.event_type = event_type
            art.created_by=request.user
            art.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_process_type(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        prefix = pt.xbill_change_prefix()
        form = ChangeProcessTypeForm(request.POST, instance=pt, prefix=prefix)
        if form.is_valid():
            pt = form.save(commit=False)
            pt.changed_by=request.user
            pt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def change_mfg_process_type(request, process_type_id):
    if request.method == "POST":
        pt = get_object_or_404(ProcessType, pk=process_type_id)
        prefix = pt.xbill_change_prefix()
        form = XbillProcessTypeForm(request.POST, instance=pt, prefix=prefix)
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            prtr = pt.main_produced_resource_type_relationship()
            if prtr:
                if qty != prtr.quantity:
                    prtr.quantity = qty
                    prtr.save()
            pt = form.save(commit=False)
            pt.changed_by=request.user
            pt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_process_type_for_resource_type(request, resource_type_id):
    if request.method == "POST":
        rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
        prefix = rt.process_create_prefix()
        form = XbillProcessTypeForm(request.POST, prefix=prefix)
        if form.is_valid():
            data = form.cleaned_data
            pt = form.save(commit=False)
            pt.created_by=request.user
            pt.changed_by=request.user
            pt.save()
            quantity = data["quantity"]
            pattern = pt.process_pattern
            event_type = pattern.event_type_for_resource_type("out", rt)
            unit = rt.unit
            quantity = Decimal(quantity)
            ptrt = ProcessTypeResourceType(
                process_type=pt,
                resource_type=rt,
                event_type=event_type,
                unit_of_quantity=unit,
                quantity=quantity,
                created_by=request.user,
            )
            ptrt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)

@login_required
def create_process_type_for_streaming(request, resource_type_id, process_type_id=None):
    if request.method == "POST":
        rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
        existing_process_type = None
        if process_type_id:
            next_process_type = ProcessType.objects.get(id=process_type_id)
            prefix = next_process_type.stream_process_type_create_prefix()
        else:
            prefix = rt.process_create_prefix()
        form = RecipeProcessTypeForm(request.POST, prefix=prefix)
        if form.is_valid():
            data = form.cleaned_data
            pt = form.save(commit=False)
            pt.created_by=request.user
            pt.changed_by=request.user
            pt.save()
            #quantity = data["quantity"]
            pattern = pt.process_pattern
            ets = pattern.change_event_types()
            unit = rt.unit
            #quantity = Decimal(quantity)
            for et in ets:
                if et.relationship == "out":
                    stage = pt
                else: #assumes only one input of stream/change type (or possibly none)
                    pts, inheritance = rt.staged_process_type_sequence()
                    if process_type_id:
                        next_input_ptrt = next_process_type.input_stream_resource_type_relationship()[0]
                        stage = next_input_ptrt.stage
                        next_input_ptrt.stage = pt
                        next_input_ptrt.save()
                    else:
                        if pts:
                            stage = pts[-1]
                        else:
                            stage = None
                ptrt = ProcessTypeResourceType(
                    process_type=pt,
                    resource_type=rt,
                    event_type=et,
                    stage=stage,
                    unit_of_quantity=unit,
                    quantity=1,
                    created_by=request.user,
                )
                ptrt.save()
            next = request.POST.get("next")
            return HttpResponseRedirect(next)
        else:
            raise ValidationError(form.errors)


def network(request, resource_type_id):
    rt = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    nodes, edges = graphify(rt, 3)
    return render(request, "valueaccounting/network.html", {
        "resource_type": rt,
        "photo_size": (128, 128),
        "nodes": nodes,
        "edges": edges,
    })

def project_network(request):
    producers = [p for p in ProcessType.objects.all() if p.produced_resource_types()]
    nodes, edges = project_graph(producers)
    return render(request, "valueaccounting/network.html", {
        "photo_size": (128, 128),
        "nodes": nodes,
        "edges": edges,
    })

def timeline(request, from_date, to_date, context_id):
    try:
        from_date_date = datetime.datetime(*time.strptime(from_date, '%Y_%m_%d')[0:5]).date()
        to_date_date = datetime.datetime(*time.strptime(to_date, '%Y_%m_%d')[0:5]).date()
    except ValueError:
        raise Http404
    context_id = int(context_id)
    if context_id:
        context_agent = get_object_or_404(EconomicAgent, pk=context_id)
    timeline_date = datetime.date.today().strftime("%b %e %Y 00:00:00 GMT-0600")
    unassigned = Commitment.objects.unfinished().filter(
        from_agent=None,
        event_type__relationship="work").order_by("due_date")
    return render(request, "valueaccounting/timeline.html", {
        "orderId": 0,
        "context_id": context_id,
        "useContextId": 0,
        "from_date": from_date,
        "to_date": to_date,
        "timeline_date": timeline_date,
        "unassigned": unassigned,
    })

def json_timeline(request, from_date, to_date, context_id):
    try:
        start = datetime.datetime(*time.strptime(from_date, '%Y_%m_%d')[0:5]).date()
        end = datetime.datetime(*time.strptime(to_date, '%Y_%m_%d')[0:5]).date()
    except ValueError:
        raise Http404
    context_id = int(context_id)
    context_agent = None
    if context_id:
        context_agent = get_object_or_404(EconomicAgent, pk=context_id)
    events = {'dateTimeFormat': 'Gregorian','events':[]}
    processes = Process.objects.unfinished().filter(
        Q(start_date__range=(start, end)) | Q(end_date__range=(start, end)) |
        Q(start_date__lt=start, end_date__gt=end))
    if context_agent:
        processes = processes.filter(context_agent=context_agent)
    orders = [p.independent_demand() for p in processes if p.independent_demand()]
    orders = list(set(orders))
    create_events(orders, processes, events)
    data = simplejson.dumps(events, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def context_timeline(request, context_id):
    context_agent = get_object_or_404(EconomicAgent, pk=context_id)
    timeline_date = datetime.date.today().strftime("%b %e %Y 00:00:00 GMT-0600")

    unassigned = Commitment.objects.unfinished().filter(
        context_agent=context_agent,
        from_agent=None,
        event_type__relationship="work").order_by("due_date")
    return render(request, "valueaccounting/timeline.html", {
        "orderId": 0,
        "context_id": context_id,
        "useContextId": 1,
        "timeline_date": timeline_date,
        "unassigned": unassigned,
    })

def json_context_timeline(request, context_id):
    events = {'dateTimeFormat': 'Gregorian','events':[]}
    context_agent = get_object_or_404(EconomicAgent, pk=context_id)
    processes = Process.objects.unfinished().filter(context_agent=context_agent)
    orders = [p.independent_demand() for p in processes if p.independent_demand()]
    orders = list(set(orders))
    create_events(orders, processes, events)
    data = simplejson.dumps(events, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def order_timeline(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    first_process = order.first_process_in_order()
    timeline_date = datetime.date.today().strftime("%b %e %Y 00:00:00 GMT-0600")
    if first_process:
        if first_process.start_date:
            timeline_date = first_process.start_date.strftime("%b %e %Y 00:00:00 GMT-0600")
    unassigned = Commitment.objects.unfinished().filter(
        independent_demand=order,
        from_agent=None,
        event_type__relationship="work").order_by("due_date")
    return render(request, "valueaccounting/timeline.html", {
        "orderId": order.id,
        "context_id": 0,
        "useContextId": 0,
        "timeline_date": timeline_date,
        "unassigned": unassigned,
    })

def json_order_timeline(request, order_id):
    events = {'dateTimeFormat': 'Gregorian','events':[]}
    order = get_object_or_404(Order, pk=order_id)
    processes = order.all_processes()
    orders = [order,]
    create_events(orders, processes, events)
    data = simplejson.dumps(events, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")


def json_processes(request, order_id=None):
    if order_id:
        order = get_object_or_404(Order, pk=order_id)
        processes = order.all_processes()
    else:
        processes = Process.objects.unfinished()
    graph = process_graph(processes)
    data = simplejson.dumps(graph)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_project_processes(request, object_type=None, object_id=None):
    #todo: needs to change
    # project and agent are now both agents
    # active_processes has been fixed, though...
    if object_type:
        if object_type == "P":
            project = get_object_or_404(EconomicAgent, pk=object_id)
            processes = project.active_processes()
            projects = [project,]
        elif object_type == "O":
            order = get_object_or_404(Order, pk=object_id)
            processes = order.all_processes()
            projects = [p.context_agent for p in processes if p.context_agent]
            projects = list(set(projects))
        elif object_type == "A":
            agent = get_object_or_404(EconomicAgent, pk=object_id)
            processes = agent.active_processes()
            projects = [p.context_agent for p in processes if p.context_agent]
            projects = list(set(projects))
    else:
        processes = Process.objects.unfinished()
        projects = [p.context_agent for p in processes if p.context_agent]
        projects = list(set(projects))
    graph = project_process_resource_agent_graph(projects, processes)
    data = simplejson.dumps(graph)
    return HttpResponse(data, content_type="text/json-comment-filtered")


def json_resource_type_unit(request, resource_type_id):
    data = serializers.serialize("json", EconomicResourceType.objects.filter(id=resource_type_id), fields=('unit',))
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_agent(request, agent_id):
    data = serializers.serialize("json", EconomicAgent.objects.filter(id=agent_id))
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_resource_type_citation_unit(request, resource_type_id):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    direction = "use"
    defaults = {
        "unit": ert.directional_unit(direction).name,
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_directional_unit(request, resource_type_id, direction):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    defaults = {
        "unit": ert.directional_unit(direction).id,
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_default_equation(request, event_type_id):
    et = get_object_or_404(EventType, pk=event_type_id)
    equation = et.default_event_value_equation()
    data = simplejson.dumps(equation, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_directional_unit_and_rule(request, resource_type_id, direction):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    defaults = {
        "unit": ert.directional_unit(direction).id,
        "rule": ert.inventory_rule
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_resource_type_defaults(request, resource_type_id):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    defaults = {
        "unit": ert.unit.id,
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

def json_context_agent_suppliers(request, agent_id):
    agent = EconomicAgent.objects.get(id=agent_id)
    json = serializers.serialize("json", agent.all_suppliers(), fields=('pk', 'nick'))
    return HttpResponse(json, content_type='application/json')

def json_context_agent_customers(request, agent_id):
    agent = EconomicAgent.objects.get(id=agent_id)
    json = serializers.serialize("json", agent.all_customers(), fields=('pk', 'nick'))
    return HttpResponse(json, content_type='application/json')

def json_order_customer(request, order_id, agent_id):
    if order_id == '0':
        agent = EconomicAgent.objects.get(id=agent_id)
        json = serializers.serialize("json", agent.all_customers(), fields=('pk', 'nick'))
    else:
        customers = []
        order = Order.objects.get(id=order_id)
        if order.provider:
            customers.append(order.provider)
        json = serializers.serialize("json", customers, fields=('pk', 'nick'))
    return HttpResponse(json, content_type='application/json')

def json_customer_orders(request, customer_id):
    if customer_id == '0':
        os = Order.objects.customer_orders()
    else:
        customer = EconomicAgent.objects.get(id=customer_id)
        os = customer.sales_orders.all()
    orders = []
    for order in os:
        fields = {
            "pk": order.pk,
            "name": str(order)
        }
        orders.append({"fields": fields})
    data = simplejson.dumps(orders, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")


def explore(request):
    return render(request, "valueaccounting/explore.html", {
    })

def unfold_commitment(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    return render(request, "valueaccounting/unfold.html", {
        "commitment": commitment,
        "process": process,
    })

def unfold_process(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    commitment = None
    return render(request, "valueaccounting/unfold.html", {
        "commitment": commitment,
        "process": process,
    })

@login_required
def cleanup(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')

    return render(request, "valueaccounting/cleanup.html", {
    })

@login_required
def misc(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')

    context_agent = None
    context_agents = EconomicAgent.objects.context_agents()
    if context_agents:
        context_agent = context_agents[0]
        for ca in context_agents:
            if ca.events.all().count() > context_agent.events.all().count():
                context_agent = ca

    ca_form = ContextAgentSelectionForm()
    if request.method == "POST":
        form = ContextAgentSelectionForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            agent = data["selected_agent"]
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/create-distribution', agent.id))

    return render(request, "valueaccounting/misc.html", {
        "context_agent": context_agent,
        "ca_form": ca_form,
    })

@login_required
def cleanup_processes(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    orphans = [p for p in Process.objects.all() if p.is_orphan()]

    return render(request, "valueaccounting/cleanup_processes.html", {
        "orphans": orphans,
    })

@login_required
def cleanup_old_processes(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    old_date = datetime.date.today() - datetime.timedelta(days=30)
    orphans = Process.objects.unfinished().filter(
        end_date__lt=old_date).order_by("end_date")

    return render(request, "valueaccounting/cleanup_old_processes.html", {
        "orphans": orphans,
    })

@login_required
def cleanup_resourcetypes(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    orphans = [rt for rt in EconomicResourceType.objects.all() if rt.is_orphan()]

    return render(request, "valueaccounting/cleanup_resourcetypes.html", {
        "orphans": orphans,
    })

@login_required
def cleanup_work_resourcetypes(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    suspects = [rt for rt in EconomicResourceType.objects.all() if rt.work_without_value()]

    return render(request, "valueaccounting/cleanup_work_resourcetypes.html", {
        "suspects": suspects,
    })

@login_required
def cleanup_resources(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    orphans = [er for er in EconomicResource.objects.all() if er.is_orphan()]

    return render(request, "valueaccounting/cleanup_resources.html", {
        "orphans": orphans,
    })

@login_required
def cleanup_unsourced_resources(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    suspects = [er for er in EconomicResource.objects.all() if er.unsourced_consumption()]

    return render(request, "valueaccounting/cleanup_unsourced_resources.html", {
        "suspects": suspects,
    })

@login_required
def cleanup_unvalued_resources(request):
    if not request.user.is_superuser:
        return render(request, 'valueaccounting/no_permission.html')
    suspects = [er for er in EconomicResource.objects.all() if er.used_without_value()]

    return render(request, "valueaccounting/cleanup_unvalued_resources.html", {
        "suspects": suspects,
    })

@login_required
def create_order(request):
    patterns = PatternUseCase.objects.filter(use_case__identifier='cust_orders')
    if patterns:
        pattern = patterns[0].pattern
    else:
        raise ValidationError("no Customer Order ProcessPattern")
    rts = pattern.all_resource_types()
    item_forms = []
    data = request.POST or None
    order_form = OrderForm(data=data)
    for rt in rts:
        prefix1 = "-".join(['RT', str(rt.id)])
        init = {'resource_type_id': rt.id,}
        form = OrderItemForm(data=data, prefix=prefix1, resource_type=rt, initial=init)
        form.features = []
        for ft in rt.features.all():
            prefix2 = "-".join(['FT', str(ft.id)])
            form.features.append(OrderItemOptionsForm(data=data, prefix=prefix2, feature=ft))
        item_forms.append(form)
    if request.method == "POST":
        if order_form.is_valid():
            order = order_form.save(commit=False)
            order.created_by=request.user
            order.order_type = "customer"
            order.save()
            uc = UseCase.objects.get(identifier="demand_xfer")
            ext_id = request.POST["exchange_type"]
            exchange_type = ExchangeType.objects.get(id=ext_id)
            exchange = Exchange(
                name=exchange_type.name + " for customer order " + str(order.id),
                exchange_type=exchange_type,
                use_case=uc,
                context_agent=order.provider,
                start_date=order.due_date,
                order=order,
                created_by= request.user,
            )
            exchange.save()
            for form in item_forms:
                if form.is_valid():
                    data = form.cleaned_data
                    qty = data["quantity"]
                    if qty:
                        rt_id = data["resource_type_id"]
                        description = data["description"]
                        rt = EconomicResourceType.objects.get(id=rt_id)
                        #refactored for new customer_order_item logic
                        commitment = order.add_customer_order_item(
                            resource_type=rt,
                            quantity=qty,
                            description=description,
                            user=request.user)

                        for ftr in form.features:
                            #todo: shd be refactored as above
                            if ftr.is_valid():
                                option_id = ftr.cleaned_data["options"]
                                option = Option.objects.get(id=option_id)
                                component = option.component
                                feature = ftr.feature
                                #todo:
                                #see comment above about hack
                                #didn't add transfer creation to this because feature is not being used right now (01/2016)
                                commitment = Commitment(
                                    order=order,
                                    independent_demand=order,
                                    event_type=feature.event_type,
                                    due_date=process.start_date,
                                    from_agent=order.provider,
                                    to_agent=order.provider,
                                    resource_type=component,
                                    context_agent=pt.context_agent,
                                    quantity=qty * feature.quantity,
                                    unit_of_quantity=component.unit,
                                    created_by=request.user,
                                )
                                commitment.save()
                                commitment.order_item = commitment
                                commitment.save()
                                commitment.generate_producing_process(request.user, [], explode=True)

            oi_commitments = Commitment.objects.filter(order=order)
            tts = exchange.exchange_type.transfer_types_non_reciprocal()
            tt = None
            if tts:
                tt = tts[0]
            for commit in oi_commitments:
                xfer = Transfer(
                    exchange=exchange,
                    name=tt.name + " of " + commit.resource_type.name,
                    transfer_type=tt,
                    context_agent=exchange.context_agent,
                    transfer_date=commit.commitment_date,
                    created_by=request.user,
                )
                xfer.save()
                commit.exchange = exchange
                commit.transfer = xfer
                commit.save()

            #todo: this should be able to figure out $ owed, including tax, etc.
            rec_tts = exchange.exchange_type.transfer_types_reciprocal()
            rec_tt = None
            if rec_tts:
                rec_tt = rec_tts[0]
            from_name = "Unknown"
            receiver = order.receiver
            if receiver:
                from_name = receiver.nick
            cr_xfer = Transfer(
                exchange=exchange,
                name=rec_tt.name + " from " + from_name,
                transfer_type=rec_tt,
                context_agent=exchange.context_agent,
                transfer_date=commit.commitment_date,
                created_by=request.user,
            )
            cr_xfer.save()
            cr_commit = Commitment(
                event_type=EventType.objects.get(name="Receive"),
                exchange=exchange,
                transfer=cr_xfer,
                due_date=exchange.start_date,
                from_agent=order.receiver,
                to_agent=order.provider,
                context_agent=exchange.context_agent,
                quantity=1,
                created_by=request.user
            )
            cr_commit.save()

            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/order-schedule', order.id))

    return render(request, "valueaccounting/create_order.html", {
        "order_form": order_form,
        "item_forms": item_forms,
    })

#todo: s/b refactored in a commitment method
#flow todo: shd order_item be used here?
#I think not. Used only in delete_order_confirmation.
def schedule_commitment(
        commitment,
        schedule,
        reqs,
        work,
        tools,
        visited_resources,
        depth):
    order = commitment.independent_demand
    commitment.depth = depth * 2
    schedule.append(commitment)
    process = commitment.process
    if process:
        process.depth = depth * 2
        if process in schedule:
            return schedule
        schedule.append(process)
        for inp in process.schedule_requirements():
            inp.depth = depth * 2
            schedule.append(inp)
            #if inp.event_type.resource_effect != "-":
            #    continue
            resource_type = inp.resource_type
            if resource_type not in visited_resources:
                #visited_resources.add(resource_type)
                pcs = inp.associated_producing_commitments()
                if pcs:
                    for pc in pcs:
                        if pc.independent_demand == order:
                            schedule_commitment(pc, schedule, reqs, work, tools, visited_resources, depth+1)
                elif inp.independent_demand == order:
                    #might want to keep, but treat differently in template
                    if inp.event_type.relationship != "work":
                        reqs.append(inp)
                        #for art in resource_type.producing_agent_relationships():
                        for art in inp.sources():
                            art.depth = (depth + 1) * 2
                            schedule.append(art)

    return schedule

def orders(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    orders = agent.active_orders()
    for order in orders:
        order_items = order.order_items()
        order.items = order_items
        visited = set()
        for order_item in order_items:
            order_item.processes = order_item.unique_processes_for_order_item(visited)
    return render(request, "valueaccounting/orders.html", {
        "agent": agent,
        "orders": orders,
    })


def order_schedule(request, order_id):
    agent = get_agent(request)
    order = get_object_or_404(Order, pk=order_id)
    error_message = ""
    order_items = order.order_items()
    rts = None
    add_order_item_form = None
    if agent:
        if order.order_type == "customer":
            patterns = PatternUseCase.objects.filter(use_case__identifier='cust_orders')
            if patterns:
                pattern = patterns[0].pattern
            else:
                raise ValidationError("no Customer Order ProcessPattern")
            rts = pattern.all_resource_types()
        else:
            rts = ProcessPattern.objects.all_production_resource_types()
        if rts:
            add_order_item_form = AddOrderItemForm(resource_types=rts)
        visited = set()
        for order_item in order_items:
            order_item.processes = order_item.unique_processes_for_order_item(visited)
            if order_item.is_workflow_order_item():
                init = {'quantity': order_item.quantity,}
                order_item.resource_qty_form = ResourceQuantityForm(prefix=str(order_item.id), initial=init)
                init = {'context_agent': order_item.context_agent,}
                order_item.project_form = ProjectSelectionForm(prefix=str(order_item.id), initial=init)
                last_date = order_item.process.end_date
                next_date = last_date + datetime.timedelta(days=1)
                init = {"start_date": next_date, "end_date": next_date}
                order_item.add_process_form = WorkflowProcessForm(prefix=str(order_item.id), initial=init, order_item=order_item)
    return render(request, "valueaccounting/order_schedule.html", {
        "order": order,
        "agent": agent,
        "order_items": order_items,
        "add_order_item_form": add_order_item_form,
        "error_message": error_message,
    })

@login_required
def change_commitment_quantities(request, order_item_id):
    order_item = get_object_or_404(Commitment, pk=order_item_id)
    qty_form = ResourceQuantityForm(prefix=str(order_item.id), data=request.POST or None)
    if request.method == "POST":
        if qty_form.is_valid():
            data = qty_form.cleaned_data
            new_qty = data["quantity"]
            order_item.change_commitment_quantities(new_qty)
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def change_workflow_project(request, order_item_id):
    order_item = get_object_or_404(Commitment, pk=order_item_id)
    project_form = ProjectSelectionForm(prefix=str(order_item.id), data=request.POST or None)
    if request.method == "POST":
        if project_form.is_valid():
            data = project_form.cleaned_data
            new_proj = data["context_agent"]
            order_item.change_workflow_project(new_proj)
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def add_order_item(
    request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    rts = EconomicResourceType.objects.all()
    form = AddOrderItemForm(resource_types=rts, data=request.POST)
    if form.is_valid():
        data = form.cleaned_data
        rt = data["resource_type"]
        qty = data["quantity"]
        order.create_order_item(
            resource_type=rt,
            quantity=qty,
            user=request.user)
    next = request.POST.get("next")
    return HttpResponseRedirect(next)


@login_required
def change_process_plan(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    form = PlanProcessForm(prefix=process.plan_form_prefix(), data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            process.start_date = data["start_date"]
            process.end_date = data["end_date"]
            process.name = data["name"]
            process.changed_by = request.user
            process.save()
            for ct in process.incoming_commitments():
                if ct.due_date != process.start_date:
                    ct.due_date = process.start_date
                    ct.save()
            for ct in process.outgoing_commitments():
                if ct.due_date != process.end_date:
                    ct.due_date = process.end_date
                    ct.save()

    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def create_process_for_streaming(request, order_item_id): #at the end of the order item
    order_item = get_object_or_404(Commitment, pk=order_item_id)
    form = WorkflowProcessForm(prefix=str(order_item.id), data=request.POST or None, order_item=order_item)
    if request.method == "POST":
        if form.is_valid():
            process = form.save(commit=False)
            data = form.cleaned_data
            pt = data["process_type"]
            if not pt:
                new_pt_name = data["new_process_type_name"]
                pt = ProcessType(
                    name=new_pt_name,
                    process_pattern=process.process_pattern,
                    created_by=request.user,
                )
                pt.save()
                process.process_type=pt
            process.changed_by = request.user
            process.save()
            order_item.adjust_workflow_commitments_process_added(process=process, user=request.user)
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def insert_process_for_streaming(request, order_item_id, process_id):
    order_item = get_object_or_404(Commitment, pk=order_item_id)
    next_process = Process.objects.get(id=process_id)
    form = WorkflowProcessForm(prefix=process_id, data=request.POST or None, order_item=order_item)
    if request.method == "POST":
        if form.is_valid():
            process = form.save(commit=False)
            data = form.cleaned_data
            pt = data["process_type"]
            if not pt:
                new_pt_name = data["new_process_type_name"]
                pt = ProcessType(
                    name=new_pt_name,
                    process_pattern=process.process_pattern,
                    created_by=request.user,
                )
                pt.save()
                process.process_type=pt
            process.changed_by = request.user
            process.save()
            order_item.adjust_workflow_commitments_process_inserted(process=process, next_process=next_process, user=request.user)
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def delete_workflow_process(request, order_item_id, process_id):
    order_item = get_object_or_404(Commitment, pk=order_item_id)
    process = Process.objects.get(id=process_id)
    if request.method == "POST":
        if process.is_deletable():
            order_item.adjust_workflow_commitments_process_deleted(process=process, user=request.user)
            process.delete()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)


def demand(request):
    agent = get_agent(request)
    orders = Order.objects.customer_orders()
    rands = Order.objects.open_rand_orders()
    help = get_help("demand")
    nav_form = DemandExchangeNavForm(data=request.POST or None)
    if agent:
        if request.method == "POST":
            if nav_form.is_valid():
                data = nav_form.cleaned_data
                ext = data["exchange_type"]
            return HttpResponseRedirect('/%s/%s/%s/'
                % ('accounting/exchange', ext.id, 0))

    return render(request, "valueaccounting/demand.html", {
        "orders": orders,
        "rands": rands,
        "agent": agent,
        "nav_form": nav_form,
        "help": help,
    })

def closed_work_orders(request):
    agent = get_agent(request)
    orders = Order.objects.closed_work_orders()
    #help = get_help("demand")
    return render(request, "valueaccounting/closed_work_orders.html", {
        "rands": orders,
        "agent": agent,
        #"help": help,
    })

def resource_type_lists(request):
    agent = get_agent(request)
    rt_lists = ResourceTypeList.objects.all()
    rtl_form = ResourceTypeListForm(data=request.POST or None)
    #help = get_help("demand")
    if request.method == "POST":
        if rtl_form.is_valid():
            form_data = rtl_form.cleaned_data
            rt_list = rtl_form.save()
            rt_ids = form_data["resource_types"]
            for rt_id in rt_ids:
                rt = EconomicResourceType.objects.get(id=rt_id)
                elem = ResourceTypeListElement(
                    resource_type_list=rt_list,
                    resource_type=rt)
                elem.save()
            return HttpResponseRedirect('/%s/'
                % ('accounting/resource-type-lists'))

    return render(request, "valueaccounting/resource_type_lists.html", {
        "rt_lists": rt_lists,
        "rtl_form": rtl_form,
        "agent": agent,
        #"help": help,
    })

@login_required
def create_resource_type_list(request):
    rtl_form = ResourceTypeListForm(data=request.POST or None)
    element_forms = []
    rrts = [rt for rt in EconomicResourceType.objects.all() if rt.has_listable_recipe()]
    for rrt in rrts:
        init = {
            "resource_type_id": rrt.id,
            "resource_type_name": rrt.name,
            }
        prefix = "".join(["RT", str(rrt.id)])
        form = ResourceTypeListElementForm(prefix=prefix, initial=init, data=request.POST or None)
        element_forms.append(form)
    if request.method == "POST":
        if rtl_form.is_valid():
            rt_list = rtl_form.save()
            for form in element_forms:
                if form.is_valid():
                    elem_data = form.cleaned_data
                    added = elem_data["added"]
                    if added:
                        rt_id = elem_data["resource_type_id"]
                        rt = EconomicResourceType.objects.get(id=rt_id)
                        elem = form.save(commit=False)
                        elem.resource_type_list=rt_list
                        elem.resource_type=rt
                        elem.save()

            return HttpResponseRedirect('/%s/'
                % ('accounting/resource-type-lists'))

    return render(request, "valueaccounting/resource_type_list.html", {
        "rtl_form": rtl_form,
        "element_forms": element_forms,
        #"help": get_help("associations"),
    })

@login_required
def change_resource_type_list(request, list_id):
    rt_list = get_object_or_404(ResourceTypeList, id=list_id)
    rtl_form = ResourceTypeListForm(instance=rt_list, data=request.POST or None)
    element_forms = []
    elems = rt_list.list_elements.all()
    for elem in elems:
        init = {
            "resource_type_id": elem.resource_type.id,
            "resource_type_name": elem.resource_type.name,
            "added": True,
            }
        prefix = "".join(["ELEM", str(elem.resource_type.id)])
        form = ResourceTypeListElementForm(instance=elem, prefix=prefix, initial=init, data=request.POST or None)
        element_forms.append(form)
    list_rt_ids = [elem.resource_type.id for elem in elems]
    other_rts = EconomicResourceType.objects.exclude(id__in=list_rt_ids)
    rrts = [rt for rt in other_rts if rt.has_listable_recipe()]
    for rrt in rrts:
        init = {
            "resource_type_id": rrt.id,
            "resource_type_name": rrt.name,
            }
        prefix = "".join(["RT", str(rrt.id)])
        form = ResourceTypeListElementForm(prefix=prefix, initial=init, data=request.POST or None)
        element_forms.append(form)
    if request.method == "POST":
        if rtl_form.is_valid():
            rt_list = rtl_form.save()
            for form in element_forms:
                if form.is_valid():
                    elem_data = form.cleaned_data
                    added = elem_data["added"]
                    elem = form.save(commit=False)
                    instance = None
                    if elem.id:
                        instance = True
                    if added:
                        if instance:
                            elem.save()
                        else:
                            rt_id = elem_data["resource_type_id"]
                            rt = EconomicResourceType.objects.get(id=rt_id)
                            elem.resource_type_list=rt_list
                            elem.resource_type=rt
                            elem.save()
                    else:
                        if instance:
                            elem = form.save()
                            elem.delete()

            return HttpResponseRedirect('/%s/'
                % ('accounting/resource-type-lists'))

    return render(request, "valueaccounting/resource_type_list.html", {
        "rtl_form": rtl_form,
        "rt_list": rt_list,
        "element_forms": element_forms,
        #"help": get_help("associations"),
    })

@login_required
def delete_resource_type_list(request, list_id):
    rt_list = get_object_or_404(ResourceTypeList, id=list_id)
    rt_list.delete()
    return HttpResponseRedirect('/%s/'
        % ('accounting/resource-type-lists'))

def supply_older(request):
    mreqs = []
    #todo: needs a lot of work
    mrqs = Commitment.objects.unfinished().filter(
        event_type__resource_effect="-",
        event_type__relationship="in").order_by("resource_type__name")
    suppliers = OrderedDict()
    for commitment in mrqs:
        if not commitment.resource_type.producing_commitments():
            if not commitment.fulfilling_events():
                mreqs.append(commitment)
                sources = commitment.resource_type.producing_agent_relationships().order_by("resource_type__name")
                for source in sources:
                    agent = source.agent
                    if agent not in suppliers:
                        suppliers[agent] = OrderedDict()
                    if source not in suppliers[agent]:
                        suppliers[agent][source] = []
                    suppliers[agent][source].append(commitment)
    treqs = []
    trqs = Commitment.objects.unfinished().filter(
        event_type__resource_effect="=",
        event_type__relationship="in").order_by("resource_type__name")
    for commitment in trqs:
        if not commitment.resource_type.producing_commitments():
            if not commitment.fulfilling_events():
                treqs.append(commitment)
                sources = commitment.resource_type.producing_agent_relationships().order_by("resource_type__name")
                for source in sources:
                    agent = source.agent
                    if agent not in suppliers:
                        suppliers[agent] = OrderedDict()
                    if source not in suppliers[agent]:
                        suppliers[agent][source] = []
                    suppliers[agent][source].append(commitment)
    return render(request, "valueaccounting/supply.html", {
        "mreqs": mreqs,
        "treqs": treqs,
        "suppliers": suppliers,
        "help": get_help("supply"),
    })

def supply_old(request):
    agent = get_agent(request)
    mreqs = []
    mrqs = Commitment.objects.to_buy()
    suppliers = OrderedDict()
    #supplier_form = AgentSupplierForm(prefix="supplier")
    for commitment in mrqs:
        if not commitment.fulfilling_events():
            mreqs.append(commitment)
            sources = commitment.resource_type.producing_agent_relationships().order_by("resource_type__name")
            for source in sources:
                agent = source.agent
                if agent not in suppliers:
                    suppliers[agent] = OrderedDict()
                if source not in suppliers[agent]:
                    suppliers[agent][source] = []
                suppliers[agent][source].append(commitment)
    treqs = []
    return render(request, "valueaccounting/supply.html", {
        "mreqs": mreqs,
        "treqs": treqs,
        "suppliers": suppliers,
        "agent": agent,
        #"supplier_form": supplier_form,
        "help": get_help("supply"),
    })

def supply(request):
    agent = get_agent(request)
    mrqs = Commitment.objects.filter(
        Q(event_type__relationship='consume')|Q(event_type__relationship='use')).order_by("resource_type__name")
    suppliers = OrderedDict()
    supply = EventType.objects.get(name="Supply")
    mreqs = [ct for ct in mrqs if ct.quantity_to_buy()]
    for commitment in mreqs:
        sources = AgentResourceType.objects.filter(
            event_type=supply,
            resource_type=commitment.resource_type)
        for source in sources:
            agent = source.agent
            if agent not in suppliers:
                suppliers[agent] = OrderedDict()
            if source not in suppliers[agent]:
                suppliers[agent][source] = []
            suppliers[agent][source].append(commitment)
    #todo: separate tool reqs from material reqs
    treqs = []
    nav_form = SupplyExchangeNavForm(data=request.POST or None)
    ext = None

    if request.method == "POST":
        if nav_form.is_valid():
            data = nav_form.cleaned_data
            ext = data["exchange_type"]
            if ext:
                return HttpResponseRedirect('/%s/%s/%s/'
                    % ('accounting/exchange', ext.id, 0))

    return render(request, "valueaccounting/supply.html", {
        "mreqs": mreqs,
        "treqs": treqs,
        "suppliers": suppliers,
        "agent": agent,
        "nav_form": nav_form,
        "help": get_help("supply"),
    })

@login_required
def create_supplier(request):
    supplier_form = AgentSupplierForm(prefix="supplier", data=request.POST or None)
    if request.method == "POST":
        if supplier_form.is_valid():
            supplier = supplier_form.save(commit=False)
            supplier.agent_type = AgentType.objects.get(name="Supplier")
            supplier.save()
    return HttpResponseRedirect('/%s/'
        % ('accounting/supply'))


def assemble_schedule(start, end, context_agent=None):
    processes = Process.objects.unfinished()
    if start:
        processes = processes.filter(
            Q(start_date__range=(start, end)) | Q(end_date__range=(start, end)) |
            Q(start_date__lt=start, end_date__gt=end))
    processes = processes.order_by("context_agent__name", "end_date", "start_date")
    context_agents = OrderedDict()
    for proc in processes:
        if context_agent == None:
            if proc.context_agent not in context_agents:
                context_agents[proc.context_agent] = []
            context_agents[proc.context_agent].append(proc)
        else:
            if proc.context_agent == context_agent:
                if proc.context_agent not in context_agents:
                    context_agents[proc.context_agent] = []
                context_agents[proc.context_agent].append(proc)
    return processes, context_agents

@login_required
def change_process_sked_ajax(request):
    proc_id = request.POST["proc_id"]
    process = Process.objects.get(id=proc_id)
    form = ScheduleProcessForm(prefix=proc_id,instance=process,data=request.POST)
    if form.is_valid():
        data = form.cleaned_data
        process.start_date = data["start_date"]
        process.end_date = data["end_date"]
        process.notes = data["notes"]
        process.save()
        return_data = "OK"
        return HttpResponse(return_data, content_type="text/plain")
    else:
        return HttpResponse(form.errors, content_type="text/json-comment-filtered")

def work(request):
    next = settings.ALL_WORK_PAGE
    if next != "/accounting/work/":
        return HttpResponseRedirect(next)
    agent = get_agent(request)
    context_id = 0
    start = datetime.date.today() - datetime.timedelta(days=30)
    end = start + datetime.timedelta(days=60)
    init = {"start_date": start, "end_date": end}
    date_form = DateSelectionForm(initial=init, data=request.POST or None)
    ca_form = ProjectSelectionFormOptional(data=request.POST or None)
    chosen_context_agent = None
    patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
    if patterns:
        pattern = patterns[0].pattern
        todo_form = TodoForm(pattern=pattern)
    else:
        todo_form = TodoForm()
    if request.method == "POST":
        if date_form.is_valid():
            dates = date_form.cleaned_data
            start = dates["start_date"]
            end = dates["end_date"]
            if ca_form.is_valid():
                proj_data = ca_form.cleaned_data
                proj_id = proj_data["context_agent"]
                if proj_id.isdigit:
                    context_id = proj_id
                    chosen_context_agent = EconomicAgent.objects.get(id=proj_id)

    start_date = start.strftime('%Y_%m_%d')
    end_date = end.strftime('%Y_%m_%d')
    processes, context_agents = assemble_schedule(start, end, chosen_context_agent)
    todos = Commitment.objects.todos().filter(due_date__range=(start, end))
    work_now = settings.USE_WORK_NOW
    return render(request, "valueaccounting/work.html", {
        "agent": agent,
        "context_agents": context_agents,
        "all_processes": processes,
        "date_form": date_form,
        "start_date": start_date,
        "end_date": end_date,
        "context_id": context_id,
        "todo_form": todo_form,
        "ca_form": ca_form,
        "todos": todos,
        "work_now": work_now,
        "help": get_help("all_work"),
    })

def schedule(request, context_agent_slug=None):
    context_agent = None
    if context_agent_slug:
        context_agent = get_object_or_404(EconomicAgent, slug=context_agent_slug)
    start = datetime.date.today() - datetime.timedelta(weeks=4)
    end = datetime.date.today() + datetime.timedelta(weeks=4)
    processes, context_agents = assemble_schedule(start, end, context_agent)
    return render(request, "valueaccounting/schedule.html", {
        "context_agents": context_agents,
    })

def today(request):
    agent = get_agent(request)
    start = datetime.date.today()
    end = start
    todos = Commitment.objects.todos().filter(due_date=start)
    processes, context_agents = assemble_schedule(start, end)
    events = EconomicEvent.objects.filter(event_date=start)
    return render(request, "valueaccounting/today.html", {
        "agent": agent,
        "context_agents": context_agents,
        "todos": todos,
        "events": events,
    })


class EventProcessSummary(object):
    def __init__(self,
        agent, context_agent, resource_type, process, quantity):
        self.agent = agent
        self.context_agent = context_agent
        self.resource_type = resource_type
        self.process = process
        self.quantity = quantity

    def key(self):
        return "-".join([
            str(self.agent.id),
            str(self.resource_type.id),
            str(self.project.id),
            str(self.process.id),
            ])

    def quantity_formatted(self):
        return self.quantity.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def condense_events(event_list):
    condensed_events = []
    if event_list:
        summaries = {}
        for event in event_list:
            from_agent = event.from_agent or 0
            if from_agent:
                from_agent = from_agent.id
            context_agent = event.context_agent or 0
            if context_agent:
                context_agent = context_agent.id
            resource_type = event.resource_type or 0
            if resource_type:
                resource_type = resource_type.id
            process = event.process or 0
            if process:
                process = process.id
            key = "-".join([
                str(from_agent),
                str(context_agent),
                str(resource_type),
                str(process)
                ])
            if not key in summaries:
                summaries[key] = EventProcessSummary(
                    event.from_agent,
                    event.context_agent,
                    event.resource_type,
                    event.process,
                    Decimal('0.0'))
            summaries[key].quantity += event.quantity
        condensed_events = list(summaries.values())
    return condensed_events


def assemble_weekly_activity(event_list):
    event_summaries = condense_events(event_list)
    context_agents = {}
    for es in event_summaries:
        if es.context_agent not in context_agents:
            context_agents[es.context_agent] = {}
        processes = context_agents[es.context_agent]
        if es.process not in processes:
            processes[es.process] = []
        processes[es.process].append(es)
    return context_agents

def this_week(request):
    agent = get_agent(request)
    end = datetime.date.today()
    start = end - datetime.timedelta(days=7)
    #start = end - datetime.timedelta(days=40)

    work_events = EconomicEvent.objects.filter(
        event_type__relationship="work",
        event_date__range=(start, end))
    participants = [e.from_agent for e in work_events if e.from_agent]
    total_participants = len(list(set(participants)))
    total_hours = sum(event.quantity for event in work_events)
    context_agents = assemble_weekly_activity(work_events)
    cas = list(context_agents.keys())
    cas_ids = [ca.id for ca in cas]
    active = len(cas)
    non_active = EconomicAgent.objects.context_agents().exclude(id__in=cas_ids).count()
    return render(request, "valueaccounting/this_week.html", {
        "agent": agent,
        "start": start,
        "end": end,
        "active": active,
        "non_active": non_active,
        "total_hours": total_hours,
        "total_participants": total_participants,
        "context_agents": context_agents,
    })

@login_required
def add_todo(request):
    if request.method == "POST":
        patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
        if patterns:
            pattern = patterns[0].pattern
            form = TodoForm(data=request.POST, pattern=pattern)
        else:
            form = TodoForm(data=request.POST)
        next = request.POST.get("next")
        agent = get_agent(request)
        et = None
        ets = EventType.objects.filter(
            relationship='todo')
        if ets:
            et = ets[0]
        if et:
            if form.is_valid():
                data = form.cleaned_data
                todo = form.save(commit=False)
                todo.to_agent=agent
                todo.event_type=et
                todo.quantity = Decimal("0")
                todo.unit_of_quantity=todo.resource_type.unit
                todo.save()
                if notification:
                    if todo.from_agent:
                        if todo.from_agent != agent:
                            site_name = get_site_name(request)
                            user = todo.from_agent.user()
                            if user:
                                notification.send(
                                    [user.user,],
                                    "valnet_new_todo",
                                    {"description": todo.description,
                                    "creator": agent,
                                    "site_name": site_name,
                                    }
                                )

    return HttpResponseRedirect(next)

def create_event_from_todo(todo):
    event = EconomicEvent(
        commitment=todo,
        event_type=todo.event_type,
        event_date=datetime.date.today(),
        from_agent=todo.from_agent,
        to_agent=todo.context_agent.default_agent(),
        resource_type=todo.resource_type,
        context_agent=todo.context_agent,
        url=todo.url,
        quantity=Decimal("0"),
        unit_of_quantity=todo.resource_type.unit,
        is_contribution=True,
    )
    return event

@login_required
def todo_time(request):
    if request.method == "POST":
        todo_id = request.POST.get("todoId")
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            hours = request.POST.get("hours")
            if hours:
                qty = Decimal(hours)
            else:
                qty = Decimal("0.0")
            event = todo.todo_event()
            if event:
                event.quantity = qty
                event.save()
            else:
                event = create_event_from_todo(todo)
                event.quantity = qty
                event.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def todo_description(request):
    if request.method == "POST":
        todo_id = request.POST.get("todoId")
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            did = request.POST.get("did")
            event = todo.todo_event()
            if event:
                event.description = did
                event.save()
            else:
                event = create_event_from_todo(todo)
                event.description = did
                event.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def todo_done(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            todo.finished = True
            todo.save()
            event = todo.todo_event()
            if not event:
                event = create_event_from_todo(todo)
                event.save()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def todo_mine(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            agent = get_agent(request)
            todo.from_agent = agent
            todo.save()
    next = request.POST.get("next")
    if next:
        return HttpResponseRedirect(next)
    return HttpResponseRedirect('/%s/'
        % ('accounting/work'))

@login_required
def todo_change(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            prefix = todo.form_prefix()
            form = TodoForm(data=request.POST, instance=todo, prefix=prefix)
            if form.is_valid():
                todo = form.save()

    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def todo_decline(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            todo.from_agent=None
            todo.save()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def todo_delete(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            if notification:
                if todo.from_agent:
                    agent = get_agent(request)
                    if todo.from_agent != agent:
                        site_name = get_site_name(request)
                        user = todo.from_agent.user()
                        if user:
                            notification.send(
                                [user.user,],
                                "valnet_deleted_todo",
                                {"description": todo.description,
                                "creator": agent,
                                "site_name": site_name,
                                }
                            )
            todo.delete()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def start(request):
    my_work = []
    my_skillz = []
    other_wip = []
    agent = get_agent(request)
    if agent:
        my_work = Commitment.objects.unfinished().filter(
            event_type__relationship="work",
            from_agent=agent)
        skill_ids = agent.resource_types.values_list('resource_type__id', flat=True)
        my_skillz = Commitment.objects.unfinished().filter(
            from_agent=None,
            event_type__relationship="work",
            resource_type__id__in=skill_ids)
        other_unassigned = Commitment.objects.unfinished().filter(
            from_agent=None,
            event_type__relationship="work").exclude(resource_type__id__in=skill_ids)[:10]
    else:
        other_unassigned = Commitment.objects.unfinished().filter(
            from_agent=None,
            event_type__relationship="work")
    todos = Commitment.objects.todos().filter(from_agent=agent)
    init = {"from_agent": agent,}
    patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
    if patterns:
        pattern = patterns[0].pattern
        todo_form = TodoForm(pattern=pattern, initial=init)
    else:
        todo_form = TodoForm(initial=init)
    work_now = settings.USE_WORK_NOW
    return render(request, "valueaccounting/start.html", {
        "agent": agent,
        "my_work": my_work,
        "my_skillz": my_skillz,
        "other_unassigned": other_unassigned,
        "todos": todos,
        "todo_form": todo_form,
        "work_now": work_now,
        "help": get_help("my_work"),
    })


def agent_stats(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    scores = agent.resource_types.all()
    agents = {}
    contributions = EconomicEvent.objects.filter(is_contribution=True)
    for c in contributions:
        if c.from_agent not in agents:
            agents[c.from_agent] = Decimal("0")
        agents[c.from_agent] += c.quantity
    member_hours = []
    for key, value in list(agents.items()):
        member_hours.append((key, value))
    member_hours.sort(key=lambda x: x[1], reverse=True)
    return render(request, "valueaccounting/agent_stats.html", {
        "agent": agent,
        "scores": scores,
        "member_hours": member_hours,
    })

def project_stats(request, context_agent_slug):
    project = None
    member_hours = []
    if context_agent_slug:
        project = get_object_or_404(EconomicAgent, slug=context_agent_slug)
    if project:
        subs = project.with_all_sub_agents()
        ces = CachedEventSummary.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs)
        if ces.count():
            agents = {}
            for ce in ces:
                agents.setdefault(ce.agent, Decimal("0"))
                agents[ce.agent] += ce.quantity
            for key, value in list(agents.items()):
                member_hours.append((key, value))
            member_hours.sort(key=lambda x: x[1], reverse=True)
    return render(request, "valueaccounting/project_stats.html", {
        "member_hours": member_hours,
        "page_title": "All-time project stats",
    })

def recent_stats(request, context_agent_slug):
    project = None
    member_hours = []
    if context_agent_slug:
        project = get_object_or_404(EconomicAgent, slug=context_agent_slug)
    if project:
        subs = project.with_all_sub_agents()
        end = datetime.date.today()
        #end = end - datetime.timedelta(days=77)
        start =  end - datetime.timedelta(days=60)
        events = EconomicEvent.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs,
            event_date__range=(start, end))
        agents_stats = {}
        for event in events:
            agents_stats.setdefault(event.from_agent, Decimal("0"))
            agents_stats[event.from_agent] += event.quantity
        for key, value in list(agents_stats.items()):
            member_hours.append((key, value))
        member_hours.sort(key=lambda x: x[1], reverse=True)
    return render(request, "valueaccounting/project_stats.html", {
        "member_hours": member_hours,
        "page_title": "Last 2 months project stats",
    })


def project_roles(request, context_agent_slug):
    project = None
    headings = []
    member_hours = []
    if context_agent_slug:
        project = get_object_or_404(EconomicAgent, slug=context_agent_slug)
    if project:
        subs = project.with_all_sub_agents()
        ces = CachedEventSummary.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs)
        if ces.count():
            agents = {}
            roles = [ce.quantity_label() for ce in ces]
            roles = list(set(roles))
            for ce in ces:
                if ce.quantity:
                    nick = ce.agent.nick.capitalize()
                    row = [nick, ]
                    for i in range(0, len(roles)):
                        row.append(Decimal("0.0"))
                        key = ce.agent.name
                    agents.setdefault(key, row)
                    idx = roles.index(ce.quantity_label()) + 1
                    agents[key][idx] += ce.quantity
            headings = ["Member",]
            headings.extend(roles)
            for row in list(agents.values()):
                member_hours.append(row)
            member_hours.sort(key=lambda x: x[0])
    return render(request, "valueaccounting/project_roles.html", {
        "project": project,
        "headings": headings,
        "member_hours": member_hours,
    })

def order_graph(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "valueaccounting/order_graph.html", {
        "order_id": order_id,
    })

def processes_graph(request, object_type=None, object_id=None):
    url_extension = ""
    if object_type:
        url_extension = "".join([ object_type, "/", object_id, "/"])

    return render(request, "valueaccounting/processes_graph.html", {
        "url_extension": url_extension,
    })

@login_required
def commit_to_task(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        process = ct.process
        agent = get_agent(request)
        prefix = ct.form_prefix()
        form = CommitmentForm(data=request.POST, prefix=prefix)
        next = None
        next = request.POST.get("next")
        if form.is_valid():
            data = form.cleaned_data
            #todo: next line did not work, don't want to take time to figure out why right now
            #probly form shd have ct as instance.
            #ct = form.save(commit=False)
            start_date = data["start_date"]
            description = data["description"]
            quantity = data["quantity"]
            unit_of_quantity = data["unit_of_quantity"]
            ct.start_date=start_date
            ct.quantity=quantity
            ct.unit_of_quantity=unit_of_quantity
            ct.description=description
            ct.from_agent = agent
            ct.changed_by=request.user
            ct.save()
            #todo: commented out for now
            #might need more logic so it doesn't needlessly
            #push the next process out
            #if start_date != process.start_date:
            #    if process.work_requirements().count() == 1:
            #        if start_date > process.start_date:
            #            delta = start_date - process.start_date
            #            process.reschedule_forward(delta.days, request.user)
            #        else:
            #            process.start_date = start_date
            #            process.changed_by=request.user
            #            process.save()
            if request.POST.get("start"):
                if next == "work":
                    return HttpResponseRedirect('/%s/%s/%s/'
                        % ('work/work-timer', process.id, ct.id))
                else:
                    return HttpResponseRedirect('/%s/%s/%s/'
                        % ('accounting/work-now', process.id, ct.id))
            if request.POST.get("work-start"):
                return HttpResponseRedirect('/%s/%s/%s/'
                    % ('work/work-timer', process.id, ct.id))

        return HttpResponseRedirect(next)

@login_required
def join_task(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        process = ct.process
        agent = get_agent(request)
        '''
        prefix = ct.join_form_prefix()
        form = CommitmentForm(data=request.POST, prefix=prefix)
        next = request.POST.get("next")
        if form.is_valid():
            data = form.cleaned_data
            new_ct = form.save(commit=False)
            """
            start_date = data["start_date"]
            description = data["description"]
            quantity = data["quantity"]
            unit_of_quantity = data["unit_of_quantity"]
            ct.start_date=start_date
            ct.quantity=quantity
            ct.unit_of_quantity=unit_of_quantity
            ct.description=description
            """
            new_ct.due_date = ct.due_date
            new_ct.resource_type = ct.resource_type
            new_ct.order_item = ct.order_item
            new_ct.independent_demand = ct.independent_demand
            new_ct.event_type = ct.event_type
            new_ct.process = process
            new_ct.from_agent = agent
            new_ct.to_agent = ct.to_agent
            new_ct.context_agent = ct.context_agent
            new_ct.stage = ct.stage
            new_ct.state = ct.state
            new_ct.created_by=request.user
            new_ct.save()
        '''
        if notification:
            workers = ct.workers()
            users = []
            for worker in workers:
                worker_users = [au.user for au in worker.users.all()]
                users.extend(worker_users)
            site_name = get_site_name(request)
            if users:
                notification.send(
                    users,
                    "valnet_join_task",
                    {"resource_type": ct.resource_type,
                    "due_date": ct.due_date,
                    "hours": ct.quantity,
                    "unit": ct.resource_type.unit,
                    "description": ct.description or "",
                    "process": process,
                    "creator": agent,
                    "site_name": site_name,
                    }
                )

        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))

@login_required
def change_commitment(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        process = ct.process
        agent = get_agent(request)
        prefix = ct.form_prefix()
        if ct.event_type.relationship=="work":
            form = WorkCommitmentForm(instance=ct, data=request.POST, prefix=prefix)
        else:
            form = ChangeCommitmentForm(instance=ct, data=request.POST, prefix=prefix)
        next = request.POST.get("next")

        if form.is_valid():
            data = form.cleaned_data
            rt = ct.resource_type
            demand = ct.independent_demand
            new_qty = data["quantity"]
            old_ct = Commitment.objects.get(id=commitment_id)
            explode = handle_commitment_changes(old_ct, rt, new_qty, demand, demand)
            commitment = form.save()
            #flow todo: explode?
            #explode wd apply to rt changes, which will not happen here
            #handle_commitment_changes will propagate qty changes

        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))

@login_required
def change_exchange_commitment(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        exchange = ct.exchange
        agent = get_agent(request)
        prefix = ct.form_prefix()
        form = ChangeCommitmentForm(instance=ct, data=request.POST, prefix=prefix)
        next = request.POST.get("next")
        if form.is_valid():
            data = form.cleaned_data
            commitment = form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def uncommit(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        process = ct.process
        ct.from_agent = None
        ct.save()
    next = request.POST.get("next")
    if next == "start":
        return HttpResponseRedirect('/%s/'
            % ('accounting/start'))
    elif next == "work-start":
        return HttpResponseRedirect('/%s/'
            % ('work/my-tasks'))
    elif next == "work":
        return HttpResponseRedirect('/%s/'
            % ('work/process-logging'))
    else:
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))

@login_required
def forward_schedule_source(request, commitment_id, source_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        source = get_object_or_404(AgentResourceType, id=source_id)
        ct.reschedule_forward_from_source(source.lead_time, request.user)
        #notify_here
        next = request.POST.get("next")
        if next:
            return HttpResponseRedirect(next)
        else:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/order-schedule', ct.independent_demand.id))

def forward_schedule_process(request, process_id):
    if request.method == "POST":
        process = get_object_or_404(Process, id=process_id)
        if process.started:
            lag = datetime.date.today() - process.end_date
        else:
            lag = datetime.date.today() - process.start_date
        #munge for partial days
        delta_days = lag.days + 1
        process.reschedule_forward(delta_days, request.user)
        #notify_here
        next = request.POST.get("next")
        if next:
            return HttpResponseRedirect(next)
        else:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/order-schedule', ct.independent_demand.id))

def create_labnotes_context(
        request,
        commitment,
        was_running=0,
        was_retrying=0):
    event = None
    duration = 0
    description = ""
    prev = ""
    today = datetime.date.today()
    events = commitment.fulfillment_events.filter(event_date=today)
    if events:
        event = events[events.count() - 1]
        init = {
            "work_done": commitment.finished,
            "process_done": commitment.process.finished,
        }
        wb_form = WorkbookForm(instance=event, initial=init)
        duration = event.quantity * 60
    else:
        init = {
            "description": commitment.description,
            "work_done": commitment.finished,
            "process_done": commitment.process.finished,
        }
        wb_form = WorkbookForm(initial=init)
    prev_events = commitment.fulfillment_events.filter(event_date__lt=today)
    if prev_events:
        prev_dur = sum(prev.quantity for prev in prev_events)
        unit = ""
        if commitment.unit_of_quantity:
            unit = commitment.unit_of_quantity.abbrev
        prev = " ".join([str(prev_dur), unit])
    others_working = []
    other_work_reqs = []
    process = commitment.process
    wrqs = process.work_requirements()
    if wrqs.count() > 1:
        for wrq in wrqs:
            if wrq.from_agent != commitment.from_agent:
                if wrq.from_agent:
                    wrq.has_labnotes = wrq.agent_has_labnotes(wrq.from_agent)
                    others_working.append(wrq)
                else:
                    other_work_reqs.append(wrq)
    failure_form = FailedOutputForm()
    if process.process_pattern:
        pattern = process.process_pattern
        add_output_form = ProcessOutputForm(prefix='output', pattern=pattern)
        add_citation_form = ProcessCitationForm(prefix='citation', pattern=pattern)
        add_consumable_form = ProcessConsumableForm(prefix='consumable', pattern=pattern)
        add_usable_form = ProcessUsableForm(prefix='usable', pattern=pattern)
        add_work_form = WorkCommitmentForm(prefix='work', pattern=pattern)
        facet_formset = create_patterned_facet_formset(pattern, "out")
    else:
        add_output_form = ProcessOutputForm(prefix='output')
        add_citation_form = ProcessCitationForm(prefix='citation')
        add_consumable_form = ProcessConsumableForm(prefix='consumable')
        add_usable_form = ProcessUsableForm(prefix='usable')
        add_work_form = WorkCommitmentForm(prefix='work')
        facet_formset = create_facet_formset()
    cited_ids = [c.resource.id for c in process.citations()]
    resource_type_form = EconomicResourceTypeAjaxForm()
    names = EconomicResourceType.objects.values_list('name', flat=True)
    resource_names = '~'.join(names)
    return {
        "commitment": commitment,
        "process": process,
        "wb_form": wb_form,
        "others_working": others_working,
        "other_work_reqs": other_work_reqs,
        "today": today,
        "failure_form": failure_form,
        "add_output_form": add_output_form,
        "add_citation_form": add_citation_form,
        "add_consumable_form": add_consumable_form,
        "add_usable_form": add_usable_form,
        "add_work_form": add_work_form,
        "resource_type_form": resource_type_form,
        "facet_formset": facet_formset,
        "duration": duration,
        "prev": prev,
        "was_running": was_running,
        "was_retrying": was_retrying,
        "event": event,
        "cited_ids": cited_ids,
        "resource_names": resource_names,
        "help": get_help("labnotes"),
    }


#obsolete
def new_process_output(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    was_running = request.POST["wasRunning"]
    was_retrying = request.POST["wasRetrying"]
    event_date = request.POST.get("outputDate")
    event = None
    events = None
    event_id=0
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = commitment.fulfillment_events.filter(event_date=event_date)
    if events:
        event = events[events.count() - 1]
        event_id = event.id
    reload = request.POST["reload"]
    if request.method == "POST":
        form = ProcessOutputForm(data=request.POST, prefix='output')
        if form.is_valid():
            output_data = form.cleaned_data
            qty = output_data["quantity"]
            if qty:
                ct = form.save(commit=False)
                rt = output_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type("out", rt)
                ct.event_type = event_type
                ct.process = process
                ct.context_agent = process.context_agent
                #flow todo: add order_item
                #or is this obsolete?
                ct.independent_demand = commitment.independent_demand
                ct.due_date = process.end_date
                ct.created_by = request.user
                ct.save()
                #if process.name == "Make something":
                #    process.name = " ".join([
                #                "Make",
                #                ct.resource_type.name,
                #            ])
                #    process.save()
    if reload == 'pastwork':
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('accounting/pastwork-reload', commitment.id, event_id, was_running, was_retrying))
    else:
        return HttpResponseRedirect('/%s/%s/%s/%s/'
            % ('accounting/labnotes-reload', commitment.id, was_running, was_retrying))

#obsolete
@login_required
def new_process_input(request, commitment_id, slot):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    was_running = request.POST["wasRunning"] or 0
    was_retrying = request.POST["wasRetrying"] or 0
    event_date = request.POST.get("inputDate")
    event = None
    events = None
    event_id=0
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = commitment.fulfillment_events.filter(event_date=event_date)
    if events:
        event = events[events.count() - 1]
        event_id = event.id
    reload = request.POST["reload"]
    if request.method == "POST":
        pattern = commitment.process.process_pattern
        if slot == "c":
            form = ProcessConsumableForm(data=request.POST, pattern=pattern, prefix='consumable')
            rel = "consume"
        elif slot == "u":
            form = ProcessUsableForm(data=request.POST, pattern=pattern, prefix='usable')
            rel = "use"
        if form.is_valid():
            input_data = form.cleaned_data
            qty = input_data["quantity"]
            if qty:
                process = commitment.process
                demand = process.independent_demand()
                ct = form.save(commit=False)
                rt = input_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type(rel, rt)
                ct.event_type = event_type
                ct.process = process
                #flow todo: add order_item
                #or is this obsolete?
                ct.independent_demand = demand
                ct.due_date = process.start_date
                ct.created_by = request.user
                #todo: add stage and state as args?
                #todo pr: this shd probably use own_or_parent_recipes
                ptrt, inheritance = ct.resource_type.main_producing_process_type_relationship()
                if ptrt:
                    ct.context_agent = ptrt.process_type.context_agent
                ct.save()
                #todo: this is used in labnotes; shd it explode?
                #explode_dependent_demands(ct, request.user)
    if reload == 'pastwork':
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('accounting/pastwork-reload', commitment.id, event_id, was_running, was_retrying))
    else:
        return HttpResponseRedirect('/%s/%s/%s/%s/'
            % ('accounting/labnotes-reload', commitment.id, was_running, was_retrying))

#obsolete
@login_required
def new_process_citation(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    was_running = request.POST["wasRunning"] or 0
    was_retrying = request.POST["wasRetrying"] or 0
    event_date = request.POST.get("citationDate")
    event = None
    events = None
    event_id=0
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = commitment.fulfillment_events.filter(event_date=event_date)
    if events:
        event = events[events.count() - 1]
        event_id = event.id
    reload = request.POST["reload"]
    if request.method == "POST":
        form = ProcessCitationForm(data=request.POST, prefix='citation')
        if form.is_valid():
            input_data = form.cleaned_data
            process = commitment.process
            demand = process.independent_demand()
            quantity = Decimal("1")
            rt = input_data["resource_type"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("cite", rt)
            agent = get_agent(request)
            #todo: sub process.add_commitment()
            #flow todo: add order_item
            #but this is obsolete
            ct = Commitment(
                process=process,
                #from_agent=agent,
                independent_demand=demand,
                event_type=event_type,
                due_date=process.start_date,
                resource_type=rt,
                context_agent=process.context_agent,
                quantity=quantity,
                unit_of_quantity=rt.directional_unit("cite"),
                created_by=request.user,
            )
            ct.save()

    if reload == 'pastwork':
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('accounting/pastwork-reload', commitment.id, event_id, was_running, was_retrying))
    else:
        return HttpResponseRedirect('/%s/%s/%s/%s/'
            % ('accounting/labnotes-reload', commitment.id, was_running, was_retrying))

#obsolete
@login_required
def new_process_worker(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    was_running = request.POST["wasRunning"] or 0
    was_retrying = request.POST["wasRetrying"] or 0
    #comes from past_work
    event_date = request.POST.get("workDate")
    event = None
    events = None
    event_id=0
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = commitment.fulfillment_events.filter(event_date=event_date)
    if events:
        event = events[events.count() - 1]
        event_id = event.id
    reload = request.POST["reload"]
    if request.method == "POST":
        form = WorkCommitmentForm(data=request.POST, prefix='work')
        if form.is_valid():
            input_data = form.cleaned_data
            process = commitment.process
            demand = process.independent_demand()
            rt = input_data["resource_type"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("work", rt)
            ct = form.save(commit=False)
            ct.process=process
            #flow todo: add order_item
            #or is this obsolete?
            ct.independent_demand=demand
            ct.event_type=event_type
            ct.due_date=process.end_date
            ct.resource_type=rt
            ct.context_agent=process.context_agent
            ct.unit_of_quantity=rt.directional_unit("use")
            ct.created_by=request.user
            ct.save()
            if notification:
                agent = get_agent(request)
                users = ct.possible_work_users()
                site_name = get_site_name(request)
                if users:
                    notification.send(
                        users,
                        "valnet_help_wanted",
                        {"resource_type": ct.resource_type,
                        "due_date": ct.due_date,
                        "hours": ct.quantity,
                        "unit": ct.resource_type.unit,
                        "description": ct.description or "",
                        "process": ct.process,
                        "creator": agent,
                        "site_name": site_name,
                        }
                    )

    if reload == 'pastwork':
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('accounting/pastwork-reload', commitment.id, event_id, was_running, was_retrying))
    else:
        return HttpResponseRedirect('/%s/%s/%s/%s/'
            % ('accounting/labnotes-reload', commitment.id, was_running, was_retrying))

def add_process_output(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = ProcessOutputForm(data=request.POST, prefix='output')
        if form.is_valid():
            output_data = form.cleaned_data
            qty = output_data["quantity"]
            if qty:
                ct = form.save(commit=False)
                rt = output_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type("out", rt)
                ct.event_type = event_type
                ct.process = process
                ct.context_agent = process.context_agent
                #flow todo: add order_item? [no]
                #this is a new process output, need some analysis and testing
                # e.g. is this an order_item itself?
                # independent_demand.order_item.process == process?
                ct.independent_demand = process.independent_demand()
                ct.due_date = process.end_date
                ct.created_by = request.user
                ct.save()
                if process.name == "Make something":
                    process.name = " ".join([
                                "Make",
                                ct.resource_type.name,
                            ])
                else:
                    process.name = " and ".join([
                                process.name,
                                ct.resource_type.name,
                            ])
                if len(process.name) > 128:
                    process.name = process.name[0:128]
                process.save()
        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

def add_unplanned_output(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = UnplannedOutputForm(data=request.POST, prefix='unplannedoutput')
        if form.is_valid():
            output_data = form.cleaned_data
            qty = output_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = output_data["resource_type"]
                identifier = output_data["identifier"]
                notes = output_data["notes"]
                url = output_data["url"]
                photo_url = output_data["photo_url"]
                access_rules = output_data["access_rules"]
                demand = None
                if not rt.substitutable:
                    demand = process.independent_demand()
                    #flow todo: add order_item ? [no]
                    #N/A I think, but see also
                    #add_process_output

                resource = EconomicResource(
                    resource_type=rt,
                    identifier=identifier,
                    independent_demand=demand,
                    notes=notes,
                    url=url,
                    photo_url=photo_url,
                    quantity=event.quantity,
                    access_rules=access_rules,
                    #unit_of_quantity=event.unit_of_quantity,
                    created_by=request.user,
                )
                resource.save()

                event.resource = resource
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type("out", rt)
                event.event_type = event_type
                event.process = process
                event.context_agent = process.context_agent
                default_agent = process.default_agent()
                event.from_agent = default_agent
                event.to_agent = default_agent
                event.event_date = datetime.date.today()
                event.created_by = request.user
                event.save()
                process.set_started(event.event_date, request.user)

                next = request.POST.get("next")
                if next and next == "exchange-work":
                  role_formset =  resource_role_context_agent_formset(prefix="resource", data=request.POST)
                else:
                  role_formset =  resource_role_agent_formset(prefix="resource", data=request.POST)

                for form_rra in role_formset.forms:
                    if form_rra.is_valid():
                        data_rra = form_rra.cleaned_data
                        if data_rra:
                            role = data_rra["role"]
                            agent = data_rra["agent"]
                            if role and agent:
                                rra = AgentResourceRole()
                                rra.agent = agent
                                rra.role = role
                                rra.resource = resource
                                rra.is_contact = data_rra["is_contact"]
                                rra.save()

        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))


@login_required
def add_unordered_receipt(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern=exchange.process_pattern
        context_agent=exchange.context_agent
        form = UnorderedReceiptForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='unorderedreceipt')
        if form.is_valid():
            output_data = form.cleaned_data
            value = output_data["value"]
            if value:
                event = form.save(commit=False)
                rt = output_data["resource_type"]
                if rt.inventory_rule == "yes":
                    identifier = output_data["identifier"]
                    notes = output_data["notes"]
                    url = output_data["url"]
                    photo_url = output_data["photo_url"]
                    quantity = output_data["quantity"]
                    #unit_of_quantity = output_data["unit_of_quantity"]
                    access_rules = output_data["access_rules"]
                    location = output_data["current_location"]
                    resource = EconomicResource(
                        resource_type=rt,
                        identifier=identifier,
                        notes=notes,
                        url=url,
                        photo_url=photo_url,
                        quantity=quantity,
                        #unit_of_quantity=unit_of_quantity,
                        current_location=location,
                        access_rules=access_rules,
                        created_by=request.user,
                    )
                    resource.save()
                    event.resource = resource
                    role_formset =  resource_role_agent_formset(prefix="receiptrole", data=request.POST)
                    for form_rra in role_formset.forms:
                        if form_rra.is_valid():
                            data_rra = form_rra.cleaned_data
                            if data_rra:
                                role = data_rra["role"]
                                agent = data_rra["agent"]
                                if role and agent:
                                    rra = AgentResourceRole()
                                    rra.agent = agent
                                    rra.role = role
                                    rra.resource = resource
                                    rra.is_contact = data_rra["is_contact"]
                                    rra.save()
                event_type = pattern.event_type_for_resource_type("receive", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = context_agent
                event.to_agent = event.default_agent()
                event.created_by = request.user
                event.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

def add_receipt_to_resource(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        form = SelectResourceOfTypeForm(
            prefix='addtoresource',
            pattern=pattern,
            posting=True,
            data=request.POST)
        if form.is_valid():
            output_data = form.cleaned_data
            resource = output_data["resource"]
            if resource:
                quantity = output_data["quantity"]
                resource.quantity += quantity
                resource.save()
                value = output_data["value"]
                unit_of_value = output_data["unit_of_value"]
                description = output_data["description"]
                context_agent = exchange.context_agent
                resource_type = resource.resource_type
                event_type = pattern.event_type_for_resource_type("receive", resource_type)
                event = EconomicEvent(
                    event_type = event_type,
                    event_date = datetime.date.today(),
                    resource = resource,
                    resource_type = resource_type,
                    exchange = exchange,
                    from_agent = exchange.supplier,
                    to_agent = context_agent.default_agent(),
                    context_agent = context_agent,
                    quantity = quantity,
                    unit_of_quantity = resource_type.unit,
                    value = value,
                    unit_of_value = unit_of_value,
                    description = description,
                    created_by = request.user,
                    changed_by = request.user,
                )
                event.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

def add_contribution_to_resource(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        form = SelectContrResourceOfTypeForm(
            prefix='addtoresource',
            pattern=pattern,
            posting=True,
            data=request.POST)
        if form.is_valid():
            output_data = form.cleaned_data
            resource = output_data["resource"]
            if resource:
                quantity = output_data["quantity"]
                resource.quantity += quantity
                resource.save()
                value = output_data["value"]
                unit_of_value = output_data["unit_of_value"]
                from_agent = output_data["from_agent"]
                description = output_data["description"]
                context_agent = exchange.context_agent
                resource_type = resource.resource_type
                event_type = pattern.event_type_for_resource_type("resource", resource_type)
                event = EconomicEvent(
                    event_type = event_type,
                    event_date = datetime.date.today(),
                    resource = resource,
                    resource_type = resource_type,
                    exchange = exchange,
                    from_agent = from_agent,
                    to_agent = context_agent.default_agent(),
                    context_agent = context_agent,
                    quantity = quantity,
                    unit_of_quantity = resource_type.unit,
                    value = value,
                    unit_of_value = unit_of_value,
                    description = description,
                    created_by = request.user,
                    changed_by = request.user,
                )
                event.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))


@login_required
def add_expense(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = ExpenseEventForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='expense')
        if form.is_valid():
            expense_data = form.cleaned_data
            value = expense_data["value"]
            if value:
                event = form.save(commit=False)
                rt = expense_data["resource_type"]
                event_type = pattern.event_type_for_resource_type("expense", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.to_agent = event.default_agent()
                event.quantity = 1
                event.unit_of_quantity = rt.unit
                event.created_by = request.user
                event.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_process_expense(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        pattern = process.process_pattern
        context_agent = process.context_agent
        form = ProcessExpenseEventForm(data=request.POST, pattern=pattern, prefix='processexpense')
        if form.is_valid():
            expense_data = form.cleaned_data
            value = expense_data["value"]
            if value:
                event = form.save(commit=False)
                rt = expense_data["resource_type"]
                event_type = pattern.event_type_for_resource_type("payexpense", rt)
                event.event_type = event_type
                event.process = process
                event.context_agent = process.context_agent
                event.to_agent = event.default_agent()
                event.quantity = 1
                event.unit_of_quantity = rt.unit
                event.created_by = request.user
                event.save()
                process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def add_material_contribution(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = MaterialContributionEventForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='material')
        if form.is_valid():
            material_data = form.cleaned_data
            qty = material_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = material_data["resource_type"]
                if rt.inventory_rule == "yes":
                    identifier = material_data["identifier"]
                    notes = material_data["notes"]
                    url = material_data["url"]
                    photo_url = material_data["photo_url"]
                    quantity = material_data["quantity"]
                    #unit_of_quantity = material_data["unit_of_quantity"]
                    access_rules = material_data["access_rules"]
                    location = material_data["current_location"]
                    resource = EconomicResource(
                        resource_type=rt,
                        identifier=identifier,
                        notes=notes,
                        url=url,
                        photo_url=photo_url,
                        quantity=quantity,
                        #unit_of_quantity=unit_of_quantity,
                        current_location=location,
                        access_rules=access_rules,
                        created_by=request.user,
                    )
                    resource.save()
                    event.resource = resource
                    role_formset =  resource_role_agent_formset(prefix="materialrole", data=request.POST)
                    for form_rra in role_formset.forms:
                        if form_rra.is_valid():
                            data_rra = form_rra.cleaned_data
                            if data_rra:
                                role = data_rra["role"]
                                agent = data_rra["agent"]
                                if role and agent:
                                    rra = AgentResourceRole()
                                    rra.agent = agent
                                    rra.role = role
                                    rra.resource = resource
                                    rra.is_contact = data_rra["is_contact"]
                                    rra.save()
                event_type = pattern.event_type_for_resource_type("resource", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = context_agent
                event.to_agent = event.default_agent()
                event.is_contribution = True
                event.created_by = request.user
                event.save()


    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_cash_contribution(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = CashContributionEventForm(data=request.POST, pattern=pattern, context_agent=context_agent, posting=True, prefix='cash')
        if form.is_valid():
            cash_data = form.cleaned_data
            value = cash_data["value"]
            if value:
                event = form.save(commit=False)
                rt = cash_data["resource_type"]
                is_contr = False
                if event.event_type.name == "Cash Contribution":
                    is_contr = True
                #event_type = pattern.event_type_for_resource_type("cash", rt)
                #event.event_type = event_type
                event.exchange = exchange
                event.context_agent = context_agent
                event.to_agent = event.default_agent()
                event.quantity = value
                event.unit_of_quantity = rt.unit
                event.unit_of_value = rt.unit
                event.is_contribution = is_contr
                event.created_by = request.user
                event.save()
                resource = event.resource
                if resource:
                    resource.quantity = resource.quantity + value
                    resource.save()
                if cash_data["from_virtual_account"] == True:
                    va = event.from_agent.virtual_accounts()[0]
                    va.quantity = va.quantity - value
                    va.save()
                    from_event = EconomicEvent(
                        event_type = EventType.objects.get(name="Cash Disbursement"),
                        event_date = event.event_date,
                        resource = va,
                        resource_type = va.resource_type,
                        exchange = exchange,
                        from_agent = event.from_agent,
                        to_agent = event.from_agent,
                        context_agent = context_agent,
                        quantity = event.quantity,
                        unit_of_quantity = rt.unit,
                        value = value,
                        unit_of_value = rt.unit,
                        created_by = request.user,
                    )
                    from_event.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_cash_resource_contribution(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = CashContributionResourceEventForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='cashres')
        if form.is_valid():
            cash_data = form.cleaned_data
            value = cash_data["value"]
            if value:
                event = form.save(commit=False)
                rt = cash_data["resource_type"]
                #event_type = pattern.event_type_for_resource_type("cash", rt)
                #event.event_type = event_type
                event.exchange = exchange
                event.context_agent = context_agent
                event.to_agent = event.default_agent()
                event.quantity = value
                event.unit_of_quantity = rt.unit
                event.unit_of_value = rt.unit
                event.created_by = request.user
                resource = EconomicResource(
                    identifier=cash_data["identifier"],
                    resource_type=rt,
                    quantity=value,
                    #unit_of_quantity=event.unit_of_value,
                    notes=cash_data["notes"],
                    current_location=cash_data["current_location"],
                    created_by=request.user
                    )
                resource.save()
                event.resource = resource
                event.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_unplanned_payment(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = PaymentEventForm(data=request.POST, pattern=pattern, context_agent=context_agent, posting=True, prefix='pay')
        if form.is_valid():
            payment_data = form.cleaned_data
            qty = payment_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = payment_data["resource_type"]
                event_type = pattern.event_type_for_resource_type("pay", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.unit_of_quantity = rt.unit
                event.is_contribution = True
                event.created_by = request.user
                event.save()
                resource = event.resource
                if resource:
                    resource.quantity = resource.quantity - qty
                    resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_cash_receipt(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = CashReceiptForm(data=request.POST, pattern=pattern, context_agent=context_agent, posting=True, prefix='cr')
        if form.is_valid():
            payment_data = form.cleaned_data
            qty = payment_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = payment_data["resource_type"]
                event_type = pattern.event_type_for_resource_type("receivecash", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.unit_of_quantity = rt.unit
                event.is_contribution = False
                event.created_by = request.user
                event.save()
                resource = event.resource
                if resource:
                    resource.quantity = resource.quantity + qty
                    resource.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_cash_receipt_resource(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = CashReceiptResourceForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='crr')
        if form.is_valid():
            payment_data = form.cleaned_data
            qty = payment_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = payment_data["resource_type"]
                event_type = pattern.event_type_for_resource_type("receivecash", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.unit_of_quantity = rt.unit
                event.is_contribution = False
                event.created_by = request.user
                resource = EconomicResource(
                    identifier=payment_data["identifier"],
                    resource_type=rt,
                    quantity=qty,
                    #unit_of_quantity=event.unit_of_quantity,
                    notes=payment_data["notes"],
                    current_location=payment_data["current_location"],
                    created_by=request.user
                    )
                resource.save()
                event.resource = resource
                event.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_shipment(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = ShipmentForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='ship')
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                event = form.save(commit=False)
                resource = data["resource"]
                rt = resource.resource_type
                event_type = pattern.event_type_for_resource_type("shipment", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.resource_type = rt
                event.unit_of_quantity = rt.unit
                event.to_agent = exchange.customer
                event.is_contribution = False
                event.created_by = request.user
                event.save()
                resource.quantity = resource.quantity - qty
                if resource.quantity < 0:
                    resource.quantity = 0
                resource.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_uninventoried_shipment(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        pattern = exchange.process_pattern
        context_agent = exchange.context_agent
        form = UninventoriedShipmentForm(data=request.POST, pattern=pattern, context_agent=context_agent, prefix='shipun')
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = data["resource_type"]
                event_type = pattern.event_type_for_resource_type("shipment", rt)
                event.event_type = event_type
                event.exchange = exchange
                event.context_agent = exchange.context_agent
                event.resource_type = rt
                event.unit_of_quantity = rt.unit
                event.to_agent = exchange.customer
                event.is_contribution = False
                event.created_by = request.user
                event.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def create_production_process(request, commitment_id):
    """ this creates a production process for a shipment commitment
        on the order_schedule page (order_plan page in work app)
    """
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    if request.method == "POST":
        prefix = commitment.form_prefix()
        form = ProcessForm(data=request.POST, prefix=prefix)
        if form.is_valid():
            process = form.save()
            qty = commitment.net_for_order()
            et = EventType.objects.get(name="Resource Production")
            rt = commitment.resource_type
            production_ct = process.add_commitment(
                resource_type=rt,
                demand=commitment.independent_demand,
                quantity=qty,
                event_type=et,
                unit=rt.unit,
                user=request.user,
                description="",
                order_item=commitment.order_item,
                stage=None,
                state=None,
                from_agent=process.context_agent,
                to_agent=commitment.context_agent)

        next = request.POST.get("next")
        if next:
            if next == "order-plan":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/order-plan', commitment.order.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/order-schedule', commitment.order.id))

@login_required
def log_shipment(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    if request.method == "POST":
        et_ship = EventType.objects.get(name="Shipment")
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = datetime.date.today(),
            event_type = et_ship,
            from_agent = ct.context_agent,
            to_agent = ct.exchange.customer,
            resource_type = ct.resource_type,
            exchange = ct.exchange,
            context_agent = ct.context_agent,
            quantity = ct.quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        resource.quantity = resource.quantity - event.quantity
        if resource.quantity < 0:
            resource.quantity = 0
        resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', ct.exchange.id))

@login_required
def log_uninventoried_shipment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    if request.method == "POST":
        et_ship = EventType.objects.get(name="Shipment")
        event = EconomicEvent(
            commitment = ct,
            event_date = datetime.date.today(),
            event_type = et_ship,
            from_agent = ct.context_agent,
            to_agent = ct.exchange.customer,
            resource_type = ct.resource_type,
            exchange = ct.exchange,
            context_agent = ct.context_agent,
            quantity = ct.quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', ct.exchange.id))

def delete_shipment_event(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(EconomicEvent, pk=event_id)
        exchange = event.exchange
        if event.resource:
            resource = event.resource
            resource.quantity = resource.quantity + event.quantity
            resource.save()
        event.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def add_distribution(request, distribution_id):
    distribution = get_object_or_404(Distribution, pk=distribution_id)
    if request.method == "POST":
        pattern = distribution.process_pattern
        context_agent = distribution.context_agent
        form = DistributionEventForm(data=request.POST, pattern=pattern, posting=True, prefix='dist')
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = data["resource_type"]
                event_type = EventType.objects.get(relationship="distribute")
                event.event_type = event_type
                event.context_agent = context_agent
                event.distribution = distribution
                event.resource_type = rt
                event.unit_of_quantity = rt.unit
                event.from_agent = context_agent
                event.is_contribution = False
                event.created_by = request.user
                event.save()
                resource = event.resource
                if resource:
                    resource.quantity = resource.quantity + qty
                    resource.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/distribution', distribution.id))

@login_required
def add_disbursement(request, distribution_id):
    distribution = get_object_or_404(Distribution, pk=distribution_id)
    if request.method == "POST":
        pattern = distribution.process_pattern
        context_agent = distribution.context_agent
        form = DisbursementEventForm(data=request.POST, pattern=pattern, posting=True, prefix='disb')
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = data["resource_type"]
                event_type = EventType.objects.get(relationship="disburse")
                fa = distribution.context_agent
                if event.resource:
                    if event.resource.owner():
                        fa = event.resource.owner()
                event.event_type = event_type
                event.context_agent = context_agent
                event.distribution = distribution
                event.unit_of_quantity = rt.unit
                event.from_agent = fa
                event.to_agent = context_agent
                event.is_contribution = False
                event.created_by = request.user
                event.save()
                resource = event.resource
                if resource:
                    resource.quantity = resource.quantity - qty
                    resource.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/distribution', distribution.id))

@login_required
def add_transfer(request, exchange_id, transfer_type_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    transfer_type = get_object_or_404(TransferType, pk=transfer_type_id)
    if request.method == "POST":
        exchange_type = exchange.exchange_type
        context_agent = exchange.context_agent
        next = request.POST.get("next")
        if next and next == "exchange-work":
            form = ContextTransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ATR" + str(transfer_type.id))
        else:
            form = TransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ATR" + str(transfer_type.id))
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            res = None
            res_from = None
            et2 = None
            res_identifier = None
            if qty:
                et_give = EventType.objects.get(name="Give")
                et_receive = EventType.objects.get(name="Receive")
                event_date = data["event_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                #if not transfer_type.can_create_resource:
                res = data["resource"]
                if transfer_type.is_currency:
                    res_from = data["from_resource"]
                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None
                if transfer_type.is_contribution:
                    is_contribution = data["is_contribution"]
                else:
                    is_contribution = False
                if transfer_type.is_to_distribute:
                    is_to_distribute = data["is_to_distribute"]
                else:
                    is_to_distribute = False
                event_ref = data["event_reference"]
                if transfer_type.can_create_resource:
                    #res = data["resource"]
                    if not res:
                        res_identifier = data["identifier"]
                        if res_identifier:
                            res = EconomicResource(
                                identifier=res_identifier,
                                url=data["url"],
                                photo_url=data["photo_url"],
                                current_location=data["current_location"],
                                notes=data["notes"],
                                access_rules=data["access_rules"],
                                resource_type=rt,
                                exchange_stage=exchange_type,
                                quantity=0,
                                created_by=request.user,
                                )
                if exchange.exchange_type.use_case == UseCase.objects.get(identifier="supply_xfer"):
                    if transfer_type.is_reciprocal:
                        if res:
                            res.quantity -= qty
                        et = et_give
                    else:
                        if res:
                            res.quantity += qty
                        et = et_receive
                elif exchange.exchange_type.use_case == UseCase.objects.get(identifier="demand_xfer"):
                    if transfer_type.is_reciprocal:
                        if res:
                            res.quantity += qty
                        et = et_receive
                    else:
                        if res:
                            res.quantity -= qty
                        et = et_give
                else: #internal xfer use case
                    if transfer_type.is_reciprocal:
                        et = et_receive
                        et2 = et_give
                    else:
                        et = et_give
                        et2 = et_receive
                    if transfer_type.is_currency:
                        if res != res_from:
                            if res:
                                res.quantity += qty
                            if res_from:
                                res_from.quantity -= qty
                if res:
                    res.save()
                if res_from:
                    res_from.save()
                if res_identifier: #new resource
                    if next and next == "exchange-work":
                      create_role_formset = resource_role_context_agent_formset(prefix=str(transfer_type.id), data=request.POST)
                    else:
                      create_role_formset = resource_role_agent_formset(prefix=str(transfer_type.id), data=request.POST)
                    for form_rra in create_role_formset.forms:
                        if form_rra.is_valid():
                            data_rra = form_rra.cleaned_data
                            if data_rra:
                                data_rra = form_rra.cleaned_data
                                role = data_rra["role"]
                                agent = data_rra["agent"]
                                if role and agent:
                                    rra = AgentResourceRole()
                                    rra.agent = agent
                                    rra.role = role
                                    rra.resource = res
                                    rra.is_contact = data_rra["is_contact"]
                                    rra.save()

                xfer_name = transfer_type.name
                if transfer_type.is_reciprocal:
                    xfer_name = xfer_name + " from " + from_agent.nick
                else:
                    xfer_name = xfer_name + " of " + rt.name
                xfer = Transfer(
                    name=xfer_name,
                    transfer_type = transfer_type,
                    exchange = exchange,
                    context_agent = context_agent,
                    transfer_date = event_date,
                    notes = description,
                    created_by = request.user
                    )
                xfer.save()
                e_is_to_distribute = is_to_distribute
                if et == et_give:
                    e_is_to_distribute = False
                e_is_contribution = is_contribution
                if et == et_receive and et2:
                    e_is_contribution = False
                if et == et_give and res_from:
                    event_res = res_from
                else:
                    event_res = res
                event = EconomicEvent(
                    event_type = et,
                    event_date=event_date,
                    resource_type=rt,
                    resource=event_res,
                    transfer=xfer,
                    exchange_stage=exchange.exchange_type,
                    context_agent = context_agent,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value=unit_of_value,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    is_contribution = e_is_contribution,
                    is_to_distribute = e_is_to_distribute,
                    event_reference=event_ref,
                    created_by = request.user,
                    )
                event.save()
                if et2:
                    e2_is_to_distribute = is_to_distribute
                    if et2 == et_give:
                        e2_is_to_distribute = False
                    e2_is_contribution = is_contribution
                    if et2 == et_receive:
                        e2_is_contribution = False
                    if et2 == et_give and res_from:
                        event_res = res_from
                    else:
                        event_res = res
                    event2 = EconomicEvent(
                        event_type = et2,
                        event_date=event_date,
                        resource_type=rt,
                        resource=event_res,
                        transfer=xfer,
                        exchange_stage=exchange.exchange_type,
                        context_agent = context_agent,
                        quantity=qty,
                        unit_of_quantity = rt.unit,
                        value=value,
                        unit_of_value=unit_of_value,
                        from_agent = from_agent,
                        to_agent = to_agent,
                        is_contribution = e2_is_contribution,
                        is_to_distribute = e2_is_to_distribute,
                        event_reference=event_ref,
                        created_by = request.user,
                    )
                    event2.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))


    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def transfer_from_commitment(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    transfer_type = transfer.transfer_type
    exchange = transfer.exchange
    context_agent = transfer.context_agent
    if request.method == "POST":
        next = request.POST.get("next")
        if next and next == "exchange-work":
            form = ContextTransferForm(data=request.POST, transfer_type=transfer.transfer_type, context_agent=transfer.context_agent, posting=True, prefix=transfer.form_prefix())
        else:
            form = TransferForm(data=request.POST, transfer_type=transfer.transfer_type, context_agent=transfer.context_agent, posting=True, prefix=transfer.form_prefix())
        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            event_date = data["event_date"]
            if transfer_type.give_agent_is_context:
                from_agent = context_agent
            else:
                from_agent = data["from_agent"]
            if transfer_type.receive_agent_is_context:
                to_agent = context_agent
            else:
                to_agent = data["to_agent"]

            rt = data["resource_type"]
            if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                gen_rt = data["ocp_resource_type"]
                rt = get_rt_from_ocp_rt(gen_rt)

            #if not transfer_type.can_create_resource:
            res = data["resource"]
            description = data["description"]
            if transfer_type.is_currency:
                value = qty
                unit_of_value = rt.unit
                res_from = data["from_resource"]
            else:
                res_from = None
                value = data["value"]
                if value:
                    unit_of_value = data["unit_of_value"]
                else:
                    unit_of_value = None
            if transfer_type.is_contribution:
                is_contribution = data["is_contribution"]
            else:
                is_contribution = False
            event_ref = data["event_reference"]
            #res = None
            if transfer_type.can_create_resource:
                #res = data["resource"]
                if not res:
                    res_identifier = data["identifier"]
                    if res_identifier: #new resource
                        res = EconomicResource(
                            identifier=res_identifier,
                            url=data["url"],
                            photo_url=data["photo_url"],
                            current_location=data["current_location"],
                            notes=data["notes"],
                            access_rules=data["access_rules"],
                            resource_type=rt,
                            exchange_stage=exchange.exchange_type,
                            quantity=0,
                            created_by=request.user,
                            )
                        res.save()
                        create_role_formset = transfer.create_role_formset(data=request.POST)
                        for form_rra in create_role_formset.forms:
                            if form_rra.is_valid():
                                data_rra = form_rra.cleaned_data
                                if data_rra:
                                    role = data_rra["role"]
                                    agent = data_rra["agent"]
                                    if role and agent:
                                        rra = AgentResourceRole()
                                        rra.agent = agent
                                        rra.role = role
                                        rra.resource = res
                                        rra.is_contact = data_rra["is_contact"]
                                        rra.save()
            for commit in transfer.commitments.all():
                if commit.event_type == et_give and res_from:
                    event_res = res_from
                else:
                    event_res = res
                event = EconomicEvent(
                    event_type=commit.event_type,
                    resource_type = rt,
                    resource = event_res,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    exchange_stage=transfer.exchange.exchange_type,
                    transfer=transfer,
                    commitment=commit,
                    context_agent = transfer.context_agent,
                    event_date = event_date,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value = unit_of_value,
                    description=description,
                    event_reference=event_ref,
                    created_by = request.user,
                )
                event.save()
                if event_res:
                    if event.event_type == et_give:
                        event_res.quantity -= event.quantity
                    else:
                        event_res.quantity += event.quantity
                    event_res.save()
                commit.finished = True
                commit.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', transfer.context_agent.id, 'exchange-logging-work', 0, exchange.id))


    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def add_transfer_commitment(request, exchange_id, transfer_type_id):
    transfer_type = get_object_or_404(TransferType, pk=transfer_type_id)
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        exchange_type = exchange.exchange_type
        context_agent = exchange.context_agent
        next = request.POST.get("next")
        if next and next == "exchange-work":
            form = ContextTransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ACM" + str(transfer_type.id))
        else:
            form = TransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ACM" + str(transfer_type.id))
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            et2 = None
            if qty:
                commitment_date = data["commitment_date"]
                due_date = data["due_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None

                xfer_name = transfer_type.name
                if transfer_type.is_reciprocal:
                    xfer_name = xfer_name + " from " + from_agent.nick
                else:
                    xfer_name = xfer_name + " of " + rt.name
                xfer = Transfer(
                    name=xfer_name,
                    transfer_type = transfer_type,
                    exchange = exchange,
                    context_agent = context_agent,
                    transfer_date = commitment_date,
                    created_by = request.user
                    )
                xfer.save()

                if exchange.exchange_type.use_case == UseCase.objects.get(identifier="supply_xfer"):
                    if transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Give")
                    else:
                        et = EventType.objects.get(name="Receive")
                elif exchange.exchange_type.use_case == UseCase.objects.get(identifier="demand_xfer"):
                    if transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Receive")
                    else:
                        et = EventType.objects.get(name="Give")
                else: #internal xfer use case
                    if transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Receive")
                        et2 = EventType.objects.get(name="Give")
                    else:
                        et = EventType.objects.get(name="Give")
                        et2 = EventType.objects.get(name="Receive")
                commit = Commitment(
                    event_type = et,
                    commitment_date=commitment_date,
                    due_date=due_date,
                    resource_type=rt,
                    exchange = exchange,
                    transfer=xfer,
                    exchange_stage=exchange.exchange_type,
                    context_agent = context_agent,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value=unit_of_value,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    description=description,
                    created_by = request.user,
                    )
                commit.save()
                if et2:
                    commit2 = Commitment(
                        event_type = et2,
                        commitment_date=commitment_date,
                        due_date=due_date,
                        resource_type=rt,
                        exchange = exchange,
                        transfer=xfer,
                        exchange_stage=exchange.exchange_type,
                        context_agent = context_agent,
                        quantity=qty,
                        unit_of_quantity = rt.unit,
                        value=value,
                        unit_of_value=unit_of_value,
                        from_agent = from_agent,
                        to_agent = to_agent,
                        created_by = request.user,
                    )
                    commit2.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def change_transfer_events(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    if request.method == "POST":
        events = transfer.events.all()
        transfer_type = transfer.transfer_type
        exchange = transfer.exchange
        context_agent = transfer.context_agent
        next = request.POST.get("next")
        if next and next == "exchange-work":
            form = ContextTransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "E")
        else:
            form = TransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "E")
        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            if qty:
                event_date = data["event_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                res = data["resource"]
                res_from = None
                if transfer_type.is_currency:
                    res_from = data["from_resource"]
                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None
                if transfer_type.is_contribution:
                    is_contribution = data["is_contribution"]
                else:
                    is_contribution = False
                event_ref = data["event_reference"]

                #old_res = None
                old_qty = events[0].quantity
                old_res_from, old_res = transfer.give_and_receive_resources()
                #if events[0].resource:
                #    old_res = events[0].resource
                for event in events:
                    event.resource_type = rt
                    event.resource = res
                    if res_from and event.event_type == et_give:
                        event.resource = res_from
                    event.from_agent = from_agent
                    event.to_agent = to_agent
                    event.event_date = event_date
                    event.quantity=qty
                    event.unit_of_quantity = rt.unit
                    event.value=value
                    event.unit_of_value = unit_of_value
                    event.description=description
                    event.event_reference=event_ref
                    event.changed_by = request.user
                    event.save()
                    res_to_change = event.resource
                    if event.event_type == et_give:
                        if old_res_from:
                            old_res_to_change = old_res_from
                        else:
                            old_res_to_change = old_res
                    else:
                        old_res_to_change = old_res
                    if res_to_change:
                        if old_res_to_change:
                            if res_to_change == old_res_to_change:
                                if event.event_type == et_give:
                                    res_to_change.quantity = res_to_change.quantity + old_qty - qty
                                else:
                                    res_to_change.quantity = res_to_change.quantity - old_qty + qty
                                res_to_change.save()
                            else:
                                if event.event_type == et_give:
                                    res_to_change.quantity = res_to_change.quantity - qty
                                    old_res_to_change.quantity = old_res_to_change.quantity + qty
                                else:
                                    res_to_change.quantity = res_to_change.quantity + qty
                                    old_res_to_change.quantity = old_res_to_change.quantity - qty
                                res_to_change.save()
                                old_res_to_change.save()
                        else:
                            if event.event_type == et_give:
                                res_to_change.quantity = res_to_change.quantity - qty
                            else:
                                res_to_change.quantity = res_to_change.quantity + qty
                            res_to_change.save()
                    else:
                        if old_res_to_change:
                            if event.event_type == et_give:
                                old_res_to_change.quantity = old_res_to_change.quantity + qty
                            else:
                                old_res_to_change.quantity = old_res_to_change.quantity - qty
                            old_res_to_change.save()

                transfer.transfer_date = event_date
                transfer.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def change_transfer_commitments(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    if request.method == "POST":
        commits = transfer.commitments.all()
        transfer_type = transfer.transfer_type
        exchange = transfer.exchange
        context_agent = transfer.context_agent
        next = request.POST.get("next")
        if next and next == "exchange-work":
            form = ContextTransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "C")
        else:
            form = TransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "C")
        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            if qty:
                commitment_date = data["commitment_date"]
                due_date = data["due_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)


                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None

                for commit in commits:
                    commit.resource_type = rt
                    commit.from_agent = from_agent
                    commit.to_agent = to_agent
                    commit.commitment_date = commitment_date
                    commit.due_date = due_date
                    commit.quantity=qty
                    commit.unit_of_quantity = rt.unit
                    commit.value=value
                    commit.unit_of_value = unit_of_value
                    commit.description=description
                    commit.changed_by = request.user
                    commit.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def delete_transfer_commitments(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    exchange = transfer.exchange
    if request.method == "POST":
        for commit in transfer.commitments.all():
            if commit.is_deletable():
                commit.delete()
        if transfer.is_deletable():
             transfer.delete()
        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', transfer.context_agent.id, 'exchange-logging-work', 0, exchange.id))
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def delete_transfer_events(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    exchange = transfer.exchange
    if request.method == "POST":
        res = None
        events = transfer.events.all()
        et_give = EventType.objects.get(name="Give")
        give_res = None
        receive_res = None
        if events:
            for event in events:
                if event.event_type == et_give:
                    give_res = event.resource
                else:
                    receive_res = event.resource
                event.delete()
            if give_res != receive_res:
                if give_res:
                    give_res.quantity += event.quantity
                if receive_res:
                    receive_res.quantity -= event.quantity
            if give_res:
                if give_res.is_deletable():
                    give_res.delete()
                else:
                    give_res.save()
            if receive_res:
                if receive_res.is_deletable():
                    receive_res.delete()
                else:
                    receive_res.save()
        if transfer.is_deletable():
             transfer.delete()
        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', transfer.context_agent.id, 'exchange-logging-work', 0, exchange.id))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))


@login_required
def add_process_input(request, process_id, slot):
    process = get_object_or_404(Process, pk=process_id)

    if request.method == "POST":
        pattern = process.process_pattern
        if slot == "c":
            form = ProcessConsumableForm(data=request.POST, pattern=pattern, prefix='consumable')
            rel = "consume"
        elif slot == "u":
            form = ProcessUsableForm(data=request.POST, pattern=pattern, prefix='usable')
            rel = "use"
        if form.is_valid():
            input_data = form.cleaned_data
            qty = input_data["quantity"]
            if qty:
                demand = process.independent_demand()
                ct = form.save(commit=False)
                rt = input_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type(rel, rt)
                ct.event_type = event_type
                ct.process = process
                #ct.project = process.project
                ct.context_agent=process.context_agent
                #flow todo: test for this
                ct.order_item = process.order_item()
                ct.independent_demand = demand
                ct.due_date = process.start_date
                ct.created_by = request.user
                #todo: add stage and state as args?
                #todo pr: this shd probably use own_or_parent_recipes
                ptrt, inheritance = ct.resource_type.main_producing_process_type_relationship()
                if ptrt:
                    ct.context_agent = ptrt.process_type.context_agent
                ct.save()
                #todo: this is used in process logging; shd it explode?
                #explode_dependent_demands(ct, request.user)
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def add_process_citation(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = ProcessCitationForm(data=request.POST, prefix='citation')
        if form.is_valid():
            input_data = form.cleaned_data
            demand = process.independent_demand()
            quantity = Decimal("1")
            rt = input_data["resource_type"]
            descrip = input_data["description"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("cite", rt)
            agent = get_agent(request)
            #todo: sub process.add_commitment()
            #flow todo: test for order_item
            ct = Commitment(
                process=process,
                #from_agent=agent,
                independent_demand=demand,
                order_item = process.order_item(),
                event_type=event_type,
                due_date=process.start_date,
                resource_type=rt,
                #project=process.project,
                context_agent=process.context_agent,
                quantity=quantity,
                description=descrip,
                unit_of_quantity=rt.directional_unit("cite"),
                created_by=request.user,
            )
            ct.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def add_process_worker(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = WorkCommitmentForm(data=request.POST, prefix='work')
        if form.is_valid():
            input_data = form.cleaned_data
            demand = process.independent_demand()
            rt = input_data["resource_type"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("work", rt)
            ct = form.save(commit=False)
            ct.process=process
            #flow todo: test order_item
            ct.order_item = process.order_item()
            ct.independent_demand=demand
            ct.event_type=event_type
            #ct.due_date=process.end_date
            ct.resource_type=rt
            ct.context_agent=process.context_agent
            ct.unit_of_quantity=rt.directional_unit("use")
            ct.created_by=request.user
            ct.save()
            if notification:
                agent = get_agent(request)
                users = ct.possible_work_users()
                site_name = get_site_name(request)
                if users:
                    notification.send(
                        users,
                        "valnet_help_wanted",
                        {"resource_type": ct.resource_type,
                        "due_date": ct.due_date,
                        "hours": ct.quantity,
                        "unit": ct.resource_type.unit,
                        "description": ct.description or "",
                        "process": ct.process,
                        "creator": agent,
                        "site_name": site_name,
                        }
                    )
        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def invite_collaborator(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    if request.method == "POST":
        '''
        prefix = commitment.invite_form_prefix()
        form = InviteCollaboratorForm(data=request.POST, prefix=prefix)
        if form.is_valid():
            input_data = form.cleaned_data
            demand = process.independent_demand()
            rt = commitment.resource_type
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("work", rt)
            ct = form.save(commit=False)
            ct.process=process
            #flow todo: test order_item
            ct.order_item = process.order_item()
            ct.independent_demand=demand
            ct.event_type=event_type
            ct.resource_type=rt
            ct.context_agent=process.context_agent
            ct.unit_of_quantity=rt.unit
            ct.created_by=request.user
            ct.save()
        '''
        if notification:
            agent = get_agent(request)
            users = commitment.possible_work_users()
            site_name = get_site_name(request)
            if users:
                notification.send(
                    users,
                    "valnet_help_wanted",
                    {"resource_type": commitment.resource_type,
                    "due_date": commitment.due_date,
                    "hours": commitment.quantity,
                    "unit": commitment.resource_type.unit,
                    "description": commitment.description or "",
                    "process": commitment.process,
                    "creator": agent,
                    "site_name": site_name,
                    }
                )

        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def delete_commitment(request, commitment_id, labnotes_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    ct = get_object_or_404(Commitment, pk=labnotes_id)
    commitment.delete()
    was_running = request.POST["wasRunning"] or 0
    was_retrying = request.POST["wasRetrying"] or 0
    reload = request.POST["reload"]
    event_date = request.POST.get("eventDate")
    event = None
    events = None
    event_id=0
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = ct.fulfillment_events.filter(event_date=event_date)
    if events:
        event = events[events.count() - 1]
        event_id = event.id
    if reload == 'pastwork':
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('accounting/pastwork-reload', labnotes_id, event_id, was_running, was_retrying))
    else:
        return HttpResponseRedirect('/%s/%s/%s/%s/'
            % ('accounting/labnotes-reload', labnotes_id, was_running, was_retrying))

@login_required
def delete_process_commitment(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    #commitment.delete_dependants()
    commitment.delete()
    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', process.id))
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def change_event_date(request):
    event_id = request.POST.get("eventId")
    event = get_object_or_404(EconomicEvent, pk=event_id)
    form = EventChangeDateForm(data=request.POST, instance=event, prefix=event_id)
    if form.is_valid():
        data = form.cleaned_data
        event = form.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def change_event_qty(request):
    event_id = request.POST.get("eventId")
    event = get_object_or_404(EconomicEvent, pk=event_id)
    form = EventChangeQuantityForm(data=request.POST, instance=event, prefix=event_id)
    if form.is_valid():
        data = form.cleaned_data
        event = form.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def change_event(request, event_id):
    event = get_object_or_404(EconomicEvent, pk=event_id)
    page = request.GET.get("page")
    event_form = event.change_form(data=request.POST or None)
    if request.method == "POST":
        page = request.POST.get("page")
        if event_form.is_valid():
            event = event_form.save(commit=False)
            event.changed_by = request.user
            event.save()
        agent = event.from_agent
        if page:
            return HttpResponseRedirect('/%s/%s/?page=%s'
                % ('accounting/contributionhistory', agent.id, page))
        else:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/contributionhistory', agent.id))
    return render(request, "valueaccounting/change_event.html", {
        "event_form": event_form,
        "page": page,
    })

@login_required
def delete_event(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(EconomicEvent, pk=event_id)
        agent = event.from_agent
        process = event.process
        exchange = event.exchange
        distribution = event.distribution
        resource = event.resource
        if resource:
            if event.consumes_resources():
                resource.quantity += event.quantity
            if event.creates_resources():
                resource.quantity -= event.quantity
            if event.changes_stage():
                tbcs = process.to_be_changed_requirements()
                if tbcs:
                    tbc = tbcs[0]
                    tbc_evts = tbc.fulfilling_events()
                    if tbc_evts:
                        tbc_evt = tbc_evts[0]
                        resource.quantity = tbc_evt.quantity
                        tbc_evt.delete()
                    resource.stage = tbc.stage
                else:
                    resource.revert_to_previous_stage()
            event.delete()
            if resource.is_deletable():
                resource.delete()
            else:
                resource.save()
        else:
            event.delete()

    next = request.POST.get("next")
    if next == "process":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))
    if next == "cleanup-processes":
        return HttpResponseRedirect('/%s/'
            % ('accounting/cleanup-processes'))
    if next == "exchange":
        return HttpResponseRedirect('/%s/%s/%s/'
            % ('accounting/exchange', 0, exchange.id))
    if next == "exchange-work":
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('work/agent', event.context_agent.id, 'exchange-logging-work', 0, exchange.id))
    if next == "distribution":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/distribution', distribution.id))
    if next == "resource":
        resource_id = request.POST.get("resource_id")
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/resource', resource_id))
    elif next == "contributions":
        page = request.POST.get("page")

        if page:
            return HttpResponseRedirect('/%s/%s/?page=%s'
                % ('accounting/contributionhistory', agent.id, page))
        else:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/contributionhistory', agent.id))
    elif next == "work-contributions":
        page = request.POST.get("page")

        if page:
            return HttpResponseRedirect('/%s/?page=%s'
                % ('work/my-history', page))
        else:
            return HttpResponseRedirect('/%s/'
                % ('work/my-history'))
    elif next == "work":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/process-logging', process.id))

@login_required
def delete_citation_event(request, commitment_id, resource_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, pk=commitment_id)
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        process = ct.process
        events = ct.fulfillment_events.filter(resource=resource)
        for event in events:
            event.delete()
    next = request.POST.get("next")
    if next == "process":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))
    if next == "resource":
        resource_id = request.POST.get("resource_id")
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/resource', resource_id))


@login_required
def delete_exchange(request, exchange_id):
    #todo: Lynn needs lots of work
    if request.method == "POST":
        exchange = get_object_or_404(Exchange, pk=exchange_id)
        if exchange.is_deletable:
            exchange.delete()
        next = request.POST.get("next")
        if next == "exchanges":
            return HttpResponseRedirect('/%s/'
                % ('accounting/exchanges'))
        if next == "demand_transfers":
            return HttpResponseRedirect('/%s/'
                % ('accounting/sales-and-distributions')) #obsolete
        if next == "material_contributions":
            return HttpResponseRedirect('/%s/'
                % ('accounting/material-contributions')) #obsolete
        if next == "distributions":
            return HttpResponseRedirect('/%s/'
                % ('accounting/distributions'))
        if next == "exchanges-all":
            return HttpResponseRedirect('/%s/%s/%s/'
                % ('work/agent', exchange.context_agent.id, 'exchanges'))
       #todo: needs a fall-through if next is none of the above


@login_required
def work_done(request):
    commitment_id = int(request.POST.get("commitmentId"))
    done = int(request.POST.get("done"))
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    if done:
        if not commitment.finished:
            commitment.finished = True
            commitment.save()
    else:
        if commitment.finished:
            commitment.finished = False
            commitment.save()

    return HttpResponse("Ok", content_type="text/plain")

@login_required
def commitment_finished(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    if not commitment.finished:
        commitment.finished = True
        commitment.changed_by = request.user
        commitment.save()
    next = request.POST.get("next")
    if next:
        if next == "work-start":
            return HttpResponseRedirect('/%s/'
                % ('work/my-tasks'))
    return HttpResponseRedirect('/%s/'
            % ('accounting/start'))


@login_required
def process_done(request):
    process_id = int(request.POST.get("processId"))
    commitment_id = int(request.POST.get("commitmentId"))
    done = int(request.POST.get("done"))
    process = get_object_or_404(Process, pk=process_id)
    if process.work_requirements().count() == 1:
        commitment = get_object_or_404(Commitment, pk=commitment_id)
        if done:
            if not commitment.finished:
                commitment.finished = True
                commitment.save()
        else:
            if commitment.finished:
                commitment.finished = False
                commitment.save()
    if done:
        if not process.finished:
            process.finished = True
            process.save()
    else:
        if process.finished:
            process.finished = False
            process.save()

    return HttpResponse("Ok", content_type="text/plain")

@login_required
def process_finished(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if not process.finished:
        process.finished = True
        process.save()
    else:
        if process.finished:
            process.finished = False
            process.save()
    #todo: finish commitments? (see process_done above)
    #or refactor into process method and use for both?
    #or refactor-combine
    next = request.POST.get("next")
    if next:
        if next == "cleanup-processes":
            return HttpResponseRedirect('/%s/'
                % ('accounting/cleanup-processes'))
        if next == "cleanup-old-processes":
            return HttpResponseRedirect('/%s/'
                % ('accounting/cleanup-old-processes'))
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process_id))

@login_required
def delete_process(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    process.delete()
    next = request.POST.get("next")
    if next:
        if next == "cleanup-processes":
            return HttpResponseRedirect('/%s/'
                % ('accounting/cleanup-processes'))
        if next == "cleanup-old-processes":
            return HttpResponseRedirect('/%s/'
                % ('accounting/cleanup-old-processes'))
    return HttpResponseRedirect('/%s/'
        % ('accounting/cleanup-processes'))

@login_required
def labnotes_reload(
        request,
        commitment_id,
        was_running=0,
        was_retrying=0):
    ct = get_object_or_404(Commitment, id=commitment_id)
    template_params = create_labnotes_context(
        request,
        ct,
        was_running,
        was_retrying,
    )
    return render(request, "valueaccounting/workbook.html",
        template_params)

@login_required
def work_commitment(
        request,
        commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    agent = get_agent(request)
    if not request.user.is_superuser:
        if agent != ct.from_agent:
            return render(request, 'valueaccounting/no_permission.html')
    template_params = create_labnotes_context(
        request,
        ct,
    )
    event = template_params["event"]
    if request.method == "POST":
        today = datetime.date.today()
        wb_form = WorkbookForm(request.POST)
        if wb_form.is_valid():
            data = wb_form.cleaned_data
            if event:
                wb_form.save(commit=False)
                event.event_date = today
                event.changed_by = request.user
            else:
                process = ct.process
                if not process.started:
                    process.started = today
                    process.changed_by=request.user
                    process.save()
                event = wb_form.save(commit=False)
                event.commitment = ct
                event.is_contribution = True
                event.event_date = today
                event.event_type = ct.event_type
                event.from_agent = ct.from_agent
                event.resource_type = ct.resource_type
                event.process = process
                event.context_agent = ct.context_agent
                event.unit_of_quantity = ct.unit_of_quantity
                event.created_by = request.user
                event.changed_by = request.user

            event.save()
            description = data["description"]
            if description != ct.description:
                ct.description = description
                ct.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/labnote', ct.id))
    return render(request, "valueaccounting/workbook.html",
        template_params)

def create_worknow_context(
        request,
        process,
        agent,
        commitment):
    prev = ""
    today = datetime.date.today()
    #todo: will not now handle lack of commitment
    event = EconomicEvent(
        event_date=today,
        from_agent=agent,
        to_agent=process.default_agent(),
        process=process,
        context_agent=process.context_agent,
        quantity=Decimal("0"),
        is_contribution=True,
        created_by = request.user,
    )

    if commitment:
        event.commitment = commitment
        event.event_type = commitment.event_type
        event.resource_type = commitment.resource_type
        event.unit_of_quantity = commitment.resource_type.unit
        init = {
            "work_done": commitment.finished,
            "process_done": commitment.process.finished,
        }
        wb_form = WorkbookForm(initial=init)
        prev_events = commitment.fulfillment_events.filter(event_date__lt=today)
        if prev_events:
            prev_dur = sum(prev.quantity for prev in prev_events)
            unit = ""
            if commitment.unit_of_quantity:
                unit = commitment.unit_of_quantity.abbrev
            prev = " ".join([str(prev_dur), unit])
    else:
        wb_form = WorkbookForm()
    event.save()
    others_working = []
    other_work_reqs = []
    wrqs = process.work_requirements()
    if wrqs.count() > 1:
        for wrq in wrqs:
            if wrq.from_agent != commitment.from_agent:
                if wrq.from_agent:
                    wrq.has_labnotes = wrq.agent_has_labnotes(wrq.from_agent)
                    others_working.append(wrq)
                else:
                    other_work_reqs.append(wrq)
    return {
        "commitment": commitment,
        "process": process,
        "wb_form": wb_form,
        "others_working": others_working,
        "other_work_reqs": other_work_reqs,
        "today": today,
        "prev": prev,
        "event": event,
        "help": get_help("labnotes"),
    }

@login_required
def work_now(
        request,
        process_id,
        commitment_id=None):
    process = get_object_or_404(Process, id=process_id)
    agent = get_agent(request)
    ct = None
    if commitment_id:
        ct = get_object_or_404(Commitment, id=commitment_id)
        #if not request.user.is_superuser:
        #    if agent != ct.from_agent:
        #        return render(request, 'valueaccounting/no_permission.html')
    template_params = create_worknow_context(
        request,
        process,
        agent,
        ct,
    )
    return render(request, "valueaccounting/work_now.html",
        template_params)

def create_past_work_context(
        request,
        commitment,
        was_running=0,
        was_retrying=0,
        event=None):
    duration = 0
    description = ""
    prev = ""
    event_date=None
    if event:
        init = {
                "work_done": commitment.finished,
                "process_done": commitment.process.finished,
            }
        wb_form = PastWorkForm(instance=event, initial=init)
        duration = event.quantity * 60
        event_date=event.event_date
    else:
        init = {
            "description": commitment.description,
            "work_done": commitment.finished,
            "process_done": commitment.process.finished,
        }
        wb_form = PastWorkForm(initial=init)
    if event_date:
        prev_events = commitment.fulfillment_events.filter(event_date__lt=event_date)
    else:
        prev_events = commitment.fulfillment_events.all()
    if prev_events:
        prev_dur = sum(prev.quantity for prev in prev_events)
        unit = ""
        if commitment.unit_of_quantity:
            unit = commitment.unit_of_quantity.name
        prev = " ".join([str(prev_dur), unit])
    others_working = []
    other_work_reqs = []
    process = commitment.process
    wrqs = process.work_requirements()
    if wrqs.count() > 1:
        for wrq in wrqs:
            if wrq.from_agent != commitment.from_agent:
                if wrq.from_agent:
                    wrq.has_labnotes = wrq.agent_has_labnotes(wrq.from_agent)
                    others_working.append(wrq)
                else:
                    other_work_reqs.append(wrq)
    failure_form = FailedOutputForm()

    if process.process_pattern:
        pattern = process.process_pattern
        add_output_form = ProcessOutputForm(prefix='output', pattern=pattern)
        add_citation_form = ProcessCitationForm(prefix='citation', pattern=pattern)
        add_consumable_form = ProcessConsumableForm(prefix='consumable', pattern=pattern)
        add_usable_form = ProcessUsableForm(prefix='usable', pattern=pattern)
        add_work_form = WorkCommitmentForm(prefix='work', pattern=pattern)
        facet_formset = create_patterned_facet_formset(pattern, "out")
    else:
        add_output_form = ProcessOutputForm(prefix='output')
        add_citation_form = ProcessCitationForm(prefix='citation')
        add_consumable_form = ProcessConsumableForm(prefix='consumable')
        add_usable_form = ProcessUsableForm(prefix='usable')
        add_work_form = WorkCommitmentForm(prefix='work')
        facet_formset = create_facet_formset()
    cited_ids = [c.resource.id for c in process.citations()]
    resource_type_form = EconomicResourceTypeAjaxForm()
    names = EconomicResourceType.objects.values_list('name', flat=True)
    resource_names = '~'.join(names)
    return {
        "commitment": commitment,
        "process": process,
        "wb_form": wb_form,
        "others_working": others_working,
        "other_work_reqs": other_work_reqs,
        "failure_form": failure_form,
        "add_output_form": add_output_form,
        "add_citation_form": add_citation_form,
        "add_consumable_form": add_consumable_form,
        "add_usable_form": add_usable_form,
        "add_work_form": add_work_form,
        "resource_type_form": resource_type_form,
        "facet_formset": facet_formset,
        "duration": duration,
        "prev": prev,
        "was_running": was_running,
        "was_retrying": was_retrying,
        "event": event,
        "event_date": event_date,
        "cited_ids": cited_ids,
        "resource_names": resource_names,
        "help": get_help("labnotes"),
    }

@login_required
def pastwork_reload(
        request,
        commitment_id,
        event_id,
        was_running=0,
        was_retrying=0,
        ):
    ct = get_object_or_404(Commitment, id=commitment_id)
    agent = get_agent(request)
    if agent != ct.from_agent:
        return render(request, 'valueaccounting/no_permission.html')
    event=None
    event_id = int(event_id)
    if event_id:
        event = get_object_or_404(EconomicEvent, id=event_id)
    template_params = create_past_work_context(
        request,
        ct,
        was_running,
        was_retrying,
        event,
    )
    if request.method == "POST":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/labnote', ct.id))
    return render(request, "valueaccounting/log_past_work.html",
        template_params)

#obsolete?
@login_required
def log_past_work(
        request,
        commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    agent = get_agent(request)
    if not request.user.is_superuser:
        if agent != ct.from_agent:
            return render(request, 'valueaccounting/no_permission.html')
    template_params = create_past_work_context(
        request,
        ct,
    )
    event = template_params["event"]
    if request.method == "POST":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/labnote', ct.id))
    return render(request, "valueaccounting/log_past_work.html",
        template_params)

@login_required
def save_work_now(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(EconomicEvent, id=event_id)
        form = WorkbookForm(instance=event, data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            event = form.save(commit=False)
            event.changed_by = request.user
            process = event.process
            event.save()
            if not process.started:
                process.started = event.event_date
                process.changed_by=request.user
                process.save()
            data = "ok"
        else:
            data = form.errors
        return HttpResponse(data, content_type="text/plain")

@login_required
def save_labnotes(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        event = None
        event_date = request.POST.get("event_date")
        if event_date:
            event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        else:
            event_date = datetime.date.today()
        events = ct.fulfillment_events.filter(event_date=event_date)
        if events:
            event = events[events.count() - 1]
            form = WorkbookForm(instance=event, data=request.POST)
        else:
            form = WorkbookForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if event:
                event = form.save(commit=False)
                event.changed_by = request.user
            else:
                event = form.save(commit=False)
                if not event.event_date:
                    event.event_date = event_date
                event.commitment = ct
                event.is_contribution = True
                event.process = ct.process
                event.context_agent = ct.context_agent
                event.event_type = ct.event_type
                event.resource_type = ct.resource_type
                event.from_agent = ct.from_agent
                event.to_agent = ct.to_agent
                event.unit_of_quantity = ct.unit_of_quantity
                event.created_by = request.user
                event.changed_by = request.user
                process = ct.process
                if not process.started:
                    process.started = event_date
                    process.changed_by=request.user
                    process.save()
            event.save()
            description = data["description"]
            if description != ct.description:
                ct.description = description
                ct.save()

            data = "ok"
        else:
            data = form.errors
        return HttpResponse(data, content_type="text/plain")

@login_required
def save_past_work(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        event_date = request.POST.get("eventDate")
        if event_date:
            event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
        events = ct.fulfillment_events.filter(event_date=event_date)
        if events:
            #todo: if the past work logging form becomes accessible other ways,
            # existing events will need to be retrieved when the date is entered.
            event = events[events.count() - 1]
            form = PastWorkForm(instance=event, data=request.POST)
        else:
            form = PastWorkForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            event_id = data.get("id")
            if event_id:
                event = form.save(commit=False)
                event.event_date = event_date
                event.changed_by = request.user
            else:
                event = form.save(commit=False)
                event.event_date = event_date
                event.commitment = ct
                event.is_contribution = True
                event.process = ct.process
                event.context_agent = ct.context_agent
                event.event_type = ct.event_type
                event.resource_type = ct.resource_type
                event.from_agent = ct.from_agent
                event.to_agent = ct.to_agent
                event.unit_of_quantity = ct.unit_of_quantity
                event.created_by = request.user
                event.changed_by = request.user
                process = ct.process
                if not process.started:
                    process.started = event_date
                    process.changed_by=request.user
                    process.save()
                event.save()
                description = data["description"]
                if description != ct.description:
                    ct.description = description
                    ct.save()

            data = "ok"
        else:
            data = form.errors
        return HttpResponse(data, content_type="text/plain")


def process_details(request, process_id):
    agent = get_agent(request)
    process = get_object_or_404(Process, id=process_id)
    labnotes = False
    if process.work_events():
        labnotes = True
    cited_ids = [c.resource.id for c in process.citations()]
    return render(request, "valueaccounting/process.html", {
        "process": process,
        "labnotes": labnotes,
        "cited_ids": cited_ids,
        "agent": agent,
        "help": get_help("process"),
    })

def process_oriented_logging(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    pattern = process.process_pattern
    context_agent = process.context_agent
    agent = get_agent(request)
    user = request.user
    logger = False
    worker = False
    super_logger = False
    todays_date = datetime.date.today()
    change_process_form = ProcessForm(instance=process)
    add_output_form = None
    add_citation_form = None
    add_consumable_form = None
    add_usable_form = None
    add_work_form = None
    unplanned_work_form = None
    unplanned_cite_form = None
    unplanned_consumption_form = None
    unplanned_use_form = None
    unplanned_output_form = None
    process_expense_form = None
    role_formset = None
    slots = []
    event_types = []
    work_now = settings.USE_WORK_NOW
    to_be_changed_requirement = None
    changeable_requirement = None

    work_reqs = process.work_requirements()
    consume_reqs = process.consumed_input_requirements()
    use_reqs = process.used_input_requirements()
    unplanned_work = process.uncommitted_work_events()

    if agent and pattern:
        slots = pattern.slots()
        event_types = pattern.event_types()
        #if request.user.is_superuser or request.user == process.created_by:
        if request.user.is_staff or request.user == process.created_by:
            logger = True
            super_logger = True
        for req in work_reqs:
            req.changeform = req.change_work_form()
            if agent == req.from_agent:
                logger = True
                worker = True
            init = {"from_agent": agent,
                "event_date": todays_date,
                "is_contribution": True,}
            req.input_work_form_init = req.input_event_form_init(init=init)
        for req in consume_reqs:
            req.changeform = req.change_form()
        for req in use_reqs:
            req.changeform = req.change_form()
        for event in unplanned_work:
            event.changeform = UnplannedWorkEventForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        output_resource_types = pattern.output_resource_types()
        unplanned_output_form = UnplannedOutputForm(prefix='unplannedoutput')
        unplanned_output_form.fields["resource_type"].queryset = output_resource_types
        role_formset = resource_role_agent_formset(prefix="resource")
        produce_et = EventType.objects.get(name="Resource Production")
        change_et = EventType.objects.get(name="Change")
        if "out" in slots:
            if logger:
                if change_et in event_types:
                    to_be_changed_requirement = process.to_be_changed_requirements()
                    if to_be_changed_requirement:
                        to_be_changed_requirement = to_be_changed_requirement[0]
                    changeable_requirement = process.changeable_requirements()
                    if changeable_requirement:
                        changeable_requirement = changeable_requirement[0]
                else:
                    add_output_form = ProcessOutputForm(prefix='output')
                    add_output_form.fields["resource_type"].queryset = output_resource_types
        if "work" in slots:
            if agent:
                work_init = {
                    "from_agent": agent,
                    "is_contribution": True,
                }
                work_resource_types = pattern.work_resource_types()
                if work_resource_types:
                    work_unit = work_resource_types[0].unit
                    #work_init = {"unit_of_quantity": work_unit,}
                    work_init = {
                        "from_agent": agent,
                        "unit_of_quantity": work_unit,
                        "is_contribution": True,
                    }
                    unplanned_work_form = UnplannedWorkEventForm(prefix="unplanned", context_agent=context_agent, initial=work_init)
                    unplanned_work_form.fields["resource_type"].queryset = work_resource_types
                    #if logger:
                    #    add_work_form = WorkCommitmentForm(initial=work_init, prefix='work', pattern=pattern)
                else:
                    unplanned_work_form = UnplannedWorkEventForm(prefix="unplanned", pattern=pattern, context_agent=context_agent, initial=work_init)
                    #is this correct? see commented-out lines above
                if logger:
                    date_init = {"due_date": process.end_date,}
                    add_work_form = WorkCommitmentForm(prefix='work', pattern=pattern, initial=date_init)

        if "cite" in slots:
            unplanned_cite_form = UnplannedCiteEventForm(prefix='unplannedcite', pattern=pattern)
            if context_agent.unit_of_claim_value:
                cite_unit = context_agent.unit_of_claim_value
            if logger:
                add_citation_form = ProcessCitationForm(prefix='citation', pattern=pattern)
        if "consume" in slots:
            unplanned_consumption_form = UnplannedInputEventForm(prefix='unplannedconsumption', pattern=pattern)
            if logger:
                add_consumable_form = ProcessConsumableForm(prefix='consumable', pattern=pattern)
        if "use" in slots:
            unplanned_use_form = UnplannedInputEventForm(prefix='unplannedusable', pattern=pattern)
            if logger:
                add_usable_form = ProcessUsableForm(prefix='usable', pattern=pattern)
        if "payexpense" in slots:
            process_expense_form = ProcessExpenseEventForm(prefix='processexpense', pattern=pattern)

    cited_ids = [c.resource.id for c in process.citations()]
    citation_requirements = process.citation_requirements()
    for cr in citation_requirements:
        cr.resources = []
        for evt in cr.fulfilling_events():
            resource = evt.resource
            resource.event = evt
            cr.resources.append(resource)

    output_resource_ids = [e.resource.id for e in process.production_events() if e.resource]

    return render(request, "valueaccounting/process_oriented_logging.html", {
        "process": process,
        "change_process_form": change_process_form,
        "cited_ids": cited_ids,
        "citation_requirements": citation_requirements,
        "output_resource_ids": output_resource_ids,
        "agent": agent,
        "user": user,
        "logger": logger,
        "worker": worker,
        "super_logger": super_logger,
        "add_output_form": add_output_form,
        "add_citation_form": add_citation_form,
        "add_consumable_form": add_consumable_form,
        "add_usable_form": add_usable_form,
        "add_work_form": add_work_form,
        "unplanned_work_form": unplanned_work_form,
        "unplanned_cite_form": unplanned_cite_form,
        "unplanned_consumption_form": unplanned_consumption_form,
        "unplanned_use_form": unplanned_use_form,
        "unplanned_output_form": unplanned_output_form,
        "role_formset": role_formset,
        "process_expense_form": process_expense_form,
        "slots": slots,
        "to_be_changed_requirement": to_be_changed_requirement,
        "changeable_requirement": changeable_requirement,
        "work_reqs": work_reqs,
        "consume_reqs": consume_reqs,
        "uncommitted_consumption": process.uncommitted_consumption_events(),
        "use_reqs": use_reqs,
        "uncommitted_use": process.uncommitted_use_events(),
        "uncommitted_process_expenses": process.uncommitted_process_expense_events(),
        "unplanned_work": unplanned_work,
        "work_now": work_now,
        "help": get_help("process"),
    })

@login_required
def add_unplanned_cite_event(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        form = UnplannedCiteEventForm(
            prefix='unplannedcite',
            data=request.POST,
            pattern=pattern,
            load_resources=True)
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                agent = get_agent(request)
                agent = get_agent(request)
                rt = data["resource_type"]
                r_id = data["resource"]
                resource = EconomicResource.objects.get(id=r_id)
                #todo: rethink for citations
                default_agent = process.default_agent()
                from_agent = resource.owner() or default_agent
                event_type = pattern.event_type_for_resource_type("cite", rt)
                event = EconomicEvent(
                    event_type=event_type,
                    resource_type = rt,
                    resource = resource,
                    from_agent = from_agent,
                    to_agent = default_agent,
                    process = process,
                    #project = process.project,
                    context_agent = process.context_agent,
                    event_date = datetime.date.today(),
                    quantity=qty,
                    unit_of_quantity = rt.directional_unit("cite"),
                    created_by = request.user,
                    changed_by = request.user,
                )
                event.save()
                process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def log_stage_change_event(request, commitment_id, resource_id):
    if request.method == "POST":
        to_be_changed_commitment = get_object_or_404(Commitment, pk=commitment_id)
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        quantity = resource.quantity
        process = to_be_changed_commitment.process
        default_agent = process.default_agent()
        from_agent = default_agent
        event_date = datetime.date.today()
        prefix = resource.form_prefix()
        #shameless hack
        qty_field = prefix + "-quantity"
        if request.POST.get(qty_field):
            form = resource.transform_form(data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                quantity = data["quantity"]
                event_date = data["event_date"]
                from_agent = data["from_agent"]
        change_commitment = process.changeable_requirements()[0]
        rt = to_be_changed_commitment.resource_type
        event = EconomicEvent(
            commitment=to_be_changed_commitment,
            event_type=to_be_changed_commitment.event_type,
            resource_type = rt,
            resource = resource,
            from_agent = from_agent,
            to_agent = default_agent,
            process = process,
            context_agent = process.context_agent,
            event_date = event_date,
            quantity=resource.quantity,
            unit_of_quantity = rt.unit,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        event = EconomicEvent(
            commitment=change_commitment,
            event_type=change_commitment.event_type,
            resource_type = rt,
            resource = resource,
            from_agent = from_agent,
            to_agent = default_agent,
            process = process,
            context_agent = process.context_agent,
            event_date = event_date,
            quantity=quantity,
            unit_of_quantity = rt.unit,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        resource.stage = change_commitment.stage
        resource.quantity = quantity
        resource.save()
        process.set_started(event.event_date, request.user)
        #todo: the following not tested
        next = request.POST.get("next")
        if next:
            if next == "work":
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def add_unplanned_input_event(request, process_id, slot):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        if slot == "c":
            prefix = "unplannedconsumption"
            et = "consume"
        else:
            prefix = "unplannedusable"
            et = "use"
        form = UnplannedInputEventForm(
            prefix=prefix,
            data=request.POST,
            pattern=pattern,
            load_resources=True)
        if form.is_valid():
            agent = get_agent(request)
            data = form.cleaned_data
            agent = get_agent(request)
            rt = data["resource_type"]
            r_id = data["resource"]
            qty = data["quantity"]
            event_date = data["event_date"]
            unit = rt.unit
            if et == "use":
                unit = rt.unit_for_use()
            resource = EconomicResource.objects.get(id=r_id)
            default_agent = process.default_agent()
            from_agent = resource.owner() or default_agent
            event_type = pattern.event_type_for_resource_type(et, rt)
            event = EconomicEvent(
                event_type=event_type,
                resource_type = rt,
                resource = resource,
                from_agent = from_agent,
                to_agent = default_agent,
                process = process,
                context_agent = process.context_agent,
                event_date = event_date,
                quantity=qty,
                unit_of_quantity = unit,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()
            if event_type.consumes_resources():
                resource.quantity -= event.quantity
                resource.changed_by=request.user
                resource.save()
            process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def log_resource_for_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    #prefix = ct.form_prefix()
    #form = CreateEconomicResourceForm(prefix=prefix, data=request.POST)
    form = ct.resource_create_form(data=request.POST)
    if form.is_valid():
        resource_data = form.cleaned_data
        agent = get_agent(request)
        resource_type = ct.resource_type
        qty = resource_data["event_quantity"]
        event_type = ct.event_type
        resource = None
        if resource_type.inventory_rule == "yes":
            resource = form.save(commit=False)
            resource.quantity = qty
            resource.resource_type = resource_type
            resource.created_by=request.user
            if not ct.resource_type.substitutable:
                resource.independent_demand = ct.independent_demand
                resource.order_item = ct.order_item
            if event_type.applies_stage():
                resource.stage = ct.stage
            resource.save()
            event_date = resource_data["created_date"]
        else:
            event_date = resource_data["event_date"]
        from_agent = resource_data["from_agent"]
        default_agent = ct.process.default_agent()
        if not from_agent:
            from_agent = default_agent
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = event_type,
            from_agent = from_agent,
            to_agent = default_agent,
            resource_type = ct.resource_type,
            process = ct.process,
            context_agent = ct.process.context_agent,
            quantity = qty,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        ct.process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', ct.process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

@login_required
def add_to_resource_for_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    form = ct.select_resource_form(data=request.POST)
    if form.is_valid():
        data = form.cleaned_data
        agent = get_agent(request)
        resource = data["resource"]
        quantity = data["quantity"]
        if resource and quantity:
            resource.quantity += quantity
            resource.changed_by=request.user
            resource.save()
            event_type = ct.event_type
            default_agent = ct.process.default_agent()
            event = EconomicEvent(
                resource = resource,
                commitment = ct,
                event_date = datetime.date.today(),
                event_type = event_type,
                from_agent = default_agent,
                to_agent = default_agent,
                resource_type = ct.resource_type,
                process = ct.process,
                context_agent = ct.context_agent,
                quantity = quantity,
                unit_of_quantity = ct.unit_of_quantity,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()
            ct.process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', ct.process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

'''
@login_required
#todo: make this work for payments when we add payment commitments, check form etc.
def log_payment_for_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    prefix = ct.form_prefix()
    form = EconomicResourceForm(prefix=prefix, data=request.POST)
    if form.is_valid():
        resource_data = form.cleaned_data
        agent = get_agent(request)
        resource = form.save(commit=False)
        resource.resource_type = ct.resource_type
        resource.created_by=request.user
        resource.save()
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = resource.created_date,
            event_type = ct.event_type,
            from_agent = agent,
            resource_type = ct.resource_type,
            exchange = ct.exchange,
            project = ct.project,
            quantity = resource.quantity,
            unit_of_quantity = ct.unit_of_quantity,
            #quality = resource.quality,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', ct.exchange.id))
'''

@login_required
def add_work_event(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    form = ct.input_event_form_init(data=request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        #event.from_agent = ct.from_agent
        event.to_agent = ct.process.default_agent()
        event.resource_type = ct.resource_type
        event.process = ct.process
        event.context_agent = ct.context_agent
        event.unit_of_quantity = ct.unit_of_quantity
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', ct.process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

#todo: refactor out a testable method
#problem: event = form.save(commit=False)
#need 'event_date', 'resource_type', 'from_agent', 'quantity', 'description'
@login_required
def add_unplanned_work_event(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        form = UnplannedWorkEventForm(prefix="unplanned", data=request.POST, pattern=pattern)
        if form.is_valid():
            event = form.save(commit=False)
            rt = event.resource_type
            event.event_type = pattern.event_type_for_resource_type("work", rt)
            event.process = process
            #event.project = process.project
            event.context_agent = process.context_agent
            default_agent = process.default_agent()
            event.to_agent = default_agent
            event.unit_of_quantity = rt.unit
            event.created_by = request.user
            event.changed_by = request.user
            event.save()
            process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def add_work_for_exchange(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    context_agent = exchange.context_agent
    form = WorkEventAgentForm(data=request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        rt = event.resource_type
        event.event_type = EventType.objects.get(name="Time Contribution")
        event.exchange = exchange
        event.context_agent = context_agent
        event.to_agent = context_agent
        event.unit_of_quantity = rt.unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
    next = request.POST.get("next")
    if next:
        if next == "exchange-work":
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

@login_required
def add_use_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    unit = ct.resource_type.directional_unit("use")
    qty_help = " ".join(["unit:", unit.abbrev])
    form = InputEventForm(qty_help=qty_help, prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.from_agent = agent
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        #event.project = ct.project
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.context_agent = ct.context_agent
        event.unit_of_quantity = unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', ct.process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

@login_required
def add_citation_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    unit = ct.resource_type.directional_unit("use")
    qty_help = " ".join(["unit:", unit.abbrev])
    form = InputEventForm(qty_help=qty_help, prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.from_agent = agent
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        #event.project = ct.project
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.context_agent = ct.context_agent
        event.unit_of_quantity = unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

@login_required
def add_consumption_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    form = InputEventForm(prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        #event.project = ct.project
        event.context_agent = ct.context_agent
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.unit_of_quantity = ct.unit_of_quantity
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        if ct.consumes_resources():
            resource.quantity -= event.quantity
            resource.changed_by=request.user
            resource.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))

@login_required
def log_citation(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    if request.method == "POST":
        agent = get_agent(request)
        #todo: rethink for citations
        default_agent = ct.process.default_agent()
        from_agent = resource.owner() or default_agent
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = datetime.date.today(),
            event_type = ct.event_type,
            from_agent = from_agent,
            to_agent = default_agent,
            resource_type = ct.resource_type,
            process = ct.process,
            #project = ct.project,
            context_agent = ct.context_agent,
            quantity = Decimal("1"),
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', ct.process.id))


def labnotes_history(request):
    agent = get_agent(request)
    procs = Process.objects.all().order_by("-start_date")
    candidates = [p for p in procs if p.work_events()]
    process_list = []
    for p in candidates:
        for e in p.work_requirements():
            if e.description:
                if p not in process_list:
                    process_list.append(p)

    paginator = Paginator(process_list, 25)
    page = request.GET.get('page')
    try:
        processes = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        processes = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        processes = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/labnotes_history.html", {
        "processes": processes,
        "photo_size": (128, 128),
        "agent": agent,
    })

def todo_history(request):
    todo_list = Commitment.objects.finished_todos().order_by('-due_date',)

    paginator = Paginator(todo_list, 25)
    page = request.GET.get('page')
    try:
        todos = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        todos = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        todos = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/todo_history.html", {
        "todos": todos,
    })


def open_todos(request):
    todo_list = Commitment.objects.todos().order_by('-due_date',)

    paginator = Paginator(todo_list, 25)
    page = request.GET.get('page')
    try:
        todos = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        todos = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        todos = paginator.page(paginator.num_pages)

    return render(request, "valueaccounting/open_todos.html", {
        "todos": todos,
    })


def resource(request, resource_id, extra_context=None):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    agent = get_agent(request)
    RraFormSet = modelformset_factory(
        AgentResourceRole,
        form=ResourceRoleAgentForm,
        can_delete=True,
        extra=4,
        )
    role_formset = RraFormSet(
        prefix="role",
        queryset=resource.agent_resource_roles.all()
        )

    if not resource.is_digital_currency_resource():
        process_add_form = None
        order_form = None
        process = None
        pattern = None
        if resource.producing_events():
            process = resource.producing_events()[0].process
            pattern = None
            if process:
                pattern = process.process_pattern
        else:
            if agent:
                form_data = {'name': 'Create ' + resource.identifier, 'start_date': resource.created_date, 'end_date': resource.created_date}
                process_add_form = AddProcessFromResourceForm(form_data)
                if resource.resource_type.recipe_is_staged():
                    init={"start_date": datetime.date.today(),}
                    order_form = StartDateAndNameForm(initial=init)

    if request.method == "POST":
        process_save = request.POST.get("process-save")
        if process_save:
            process_add_form = AddProcessFromResourceForm(data=request.POST)
            if process_add_form.is_valid():
                process = process_add_form.save(commit=False)
                process.started = process.start_date
                process.finished = True
                process.created_by = request.user
                process.save()
                event = EconomicEvent()
                event.context_agent = process.context_agent
                event.event_date = process.end_date
                event.event_type = process.process_pattern.event_type_for_resource_type("out", resource.resource_type)
                event.process = process
                event.resource_type = resource.resource_type
                event.quantity = resource.quantity
                event.unit_of_quantity = resource.unit_of_quantity()
                event.resource = resource
                event.to_agent = event.context_agent
                event.from_agent = event.context_agent
                event.created_by = request.user
                event.save()
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/resource', resource.id))
    if resource.is_digital_currency_resource():
        send_coins_form = None
        is_owner=False
        limit = 0
        if agent:
            is_owner = agent.owns(resource)
            if is_owner:
                if resource.address_is_activated():
                    send_coins_form = SendFairCoinsForm()
                    limit = resource.spending_limit()
        return render(request, "valueaccounting/digital_currency_resource.html", {
            "resource": resource,
            "photo_size": (128, 128),
            "role_formset": role_formset,
            "agent": agent,
            "is_owner": is_owner,
            "send_coins_form": send_coins_form,
            "limit": limit,
        })
    else:
        return render(request, "valueaccounting/resource.html", {
            "resource": resource,
            "photo_size": (128, 128),
            "process_add_form": process_add_form,
            "order_form": order_form,
            "role_formset": role_formset,
            "agent": agent,
        })


def resource_role_agent_formset(prefix, data=None):
    RraFormSet = modelformset_factory(
        AgentResourceRole,
        form=ResourceRoleAgentForm,
        can_delete=True,
        extra=4,
        )
    formset = RraFormSet(prefix=prefix, queryset=AgentResourceRole.objects.none(), data=data)
    return formset

@login_required
def plan_work_order_for_resource(request, resource_id):
    if request.method == "POST":
        form = StartDateAndNameForm(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            start = data["start_date"]
            order_name = data["order_name"]
            if not order_name:
                order_name = resource.__unicode__()
            resource = get_object_or_404(EconomicResource, id=resource_id)
            agent = get_agent(request)
            resource_type = resource.resource_type
            order = resource_type.generate_staged_work_order_from_resource(resource, order_name, start, request.user)
            if order:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/order-schedule', order.id))
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/resource', resource_id))


def incoming_value_flows(request, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    #flows = resource.incoming_value_flows()
    flows = []
    depth = 0
    visited = set()
    ve = None
    all_ves = None
    ve_selection_form = None
    ves = resource.value_equations()
    if len(ves) > 1:
        all_ves = ves
        ve_selection_form = ValueEquationSelectionForm(
            value_equations=all_ves,
            data=request.POST or None)
    if ves:
        live_ves = [ve for ve in ves if ve.live]
        if live_ves:
            ve = live_ves[0]
        else:
            ve = ves[0]
    if request.method == "POST":
        if ve_selection_form.is_valid():
            ve = ve_selection_form.cleaned_data["value_equation"]
    value_per_unit = resource.roll_up_value(flows, depth, visited, ve)
    totals = {}
    member_hours = []
    for flow in flows:
        if flow.flow_class() == "work":
            if flow.quantity:
                if not flow.from_agent in totals:
                    totals[flow.from_agent] = Decimal("0")
                totals[flow.from_agent] += flow.quantity
    for key, value in list(totals.items()):
        member_hours.append((key, value))
    return render(request, "valueaccounting/incoming_value_flows.html", {
        "resource": resource,
        "value_equation": ve,
        "ve_selection_form": ve_selection_form,
        "flows": flows,
        "value_per_unit": value_per_unit,
        "member_hours": member_hours,
    })

@login_required
def change_resource(request, resource_id):
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        v_help = None
        if resource.resource_type.unit_of_use:
            v_help = "give me a usable widget"
        form = EconomicResourceForm(data=request.POST, instance=resource, vpu_help=v_help)
        if form.is_valid():
            data = form.cleaned_data
            resource = form.save(commit=False)
            resource.changed_by=request.user
            resource.save()
            RraFormSet = modelformset_factory(
                AgentResourceRole,
                form=ResourceRoleAgentForm,
                can_delete=True,
                extra=4,
                )
            role_formset = RraFormSet(
                prefix="role",
                queryset=resource.agent_resource_roles.all(),
                data=request.POST
                )
            if role_formset.is_valid():
                saved_formset = role_formset.save(commit=False)
                for role in saved_formset:
                    role.resource = resource
                    role.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/resource', resource_id))
        else:
            raise ValidationError(form.errors)

def get_labnote_context(commitment, request_agent):
    author = False
    agent = commitment.from_agent
    process = commitment.process
    if request_agent == agent:
        author = True
    work_events = commitment.fulfilling_events()
    outputs = []
    failures = []
    consumed = []
    used = []
    citations = []
    if agent and process:
        outputs = process.outputs_from_agent(agent)
        failures = process.failures_from_agent(agent)
        consumed = process.inputs_consumed_by_agent(agent)
        used = process.inputs_used_by_agent(agent)
        citations = process.citations_by_agent(agent)
    return {
        "commitment": commitment,
        "author": author,
        "process": process,
        "work_events": work_events,
        "outputs": outputs,
        "failures": failures,
        "consumed": consumed,
        "used": used,
        "citations": citations,
    }

def labnotes(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    agent = get_agent(request)
    work_commitments = process.work_requirements()
    if work_commitments.count() == 1:
        ct = work_commitments[0]
        template_params = get_labnote_context(ct, agent)
        return render(request, "valueaccounting/labnote.html",
            template_params)
    else:
        return render(request, "valueaccounting/labnotes.html", {
            "process": process,
            "agent": agent,
        })

def labnote(request, commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    request_agent = get_agent(request)
    template_params = get_labnote_context(ct, request_agent)
    return render(request, "valueaccounting/labnote.html",
        template_params)

@login_required
def production_event_for_commitment(request):
    id = request.POST.get("id")
    quantity = request.POST.get("quantity")
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    ct = get_object_or_404(Commitment, pk=id)
    agent = get_agent(request)
    quantity = Decimal(quantity)
    event = None
    events = ct.fulfillment_events.all()
    if events:
        event = events[events.count() - 1]
    if event:
        if event.quantity != quantity:
            event.quantity = quantity
            event.changed_by = request.user
            event.save()
            resource = event.resource
            resource.quantity = quantity
            resource.changed_by=request.user
            resource.save()
    else:
        #todo: resource creation shd depend on event_type and maybe rt
        #design docs will need special handling (url)
        #todo: add order if not RT.substitutable
        demand = None
        if not rt.substitutable:
            demand = ct.independent_demand
            order_item = ct.order_item
        resource = EconomicResource(
            resource_type = ct.resource_type,
            created_date = event_date,
            quantity = quantity,
            #unit_of_quantity = ct.unit_of_quantity,
            created_by=request.user,
            independent_demand=demand,
            order_item=order_item,
        )
        resource.save()
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = ct.event_type,
            from_agent = agent,
            resource_type = ct.resource_type,
            process = ct.process,
            #project = ct.project,
            context_agent = context_agent,
            quantity = quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()

    data = "ok"
    return HttpResponse(data, content_type="text/plain")

@login_required
def resource_event_for_commitment(request, commitment_id):
    #todo: bug: resource_event_for_commitment didn't return an HttpResponse object.
    id = request.POST.get("itemId")
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    ct = get_object_or_404(Commitment, pk=id)
    event = None
    events = ct.fulfillment_events.all()
    prefix = ct.form_prefix()
    data = str('0')
    if events:
        event = events[events.count() - 1]
        form = EconomicResourceForm(prefix=prefix, data=request.POST, instance=event.resource)
    else:
        form = EconomicResourceForm(prefix=prefix, data=request.POST)
    if form.is_valid():
        resource_data = form.cleaned_data
        #quality = resource_data["quality"] or Decimal("0")
        agent = get_agent(request)
        if event:
            resource = form.save(commit=False)
            if event.quantity != resource.quantity:
                event.quantity = resource.quantity
                event.changed_by = request.user
                event.save()
            resource.changed_by=request.user
            resource.save()
        else:
            #todo: add order if not RT.substitutable
            resource = form.save(commit=False)
            #resource.quality = quality
            rt = ct.resource_type
            resource.resource_type = rt
            if not rt.substitutable:
                resource.independent_demand = ct.independent_demand
                resource.order_item = ct.order_item
            resource.created_by=request.user
            resource.save()
            event = EconomicEvent(
                resource = resource,
                commitment = ct,
                event_date = event_date,
                event_type = ct.event_type,
                from_agent = agent,
                resource_type = ct.resource_type,
                process = ct.process,
                context_agent = ct.context_agent,
                quantity = resource.quantity,
                unit_of_quantity = ct.unit_of_quantity,
                #quality = resource.quality,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()
        data = str(resource.quantity)
    return HttpResponse(data, content_type="text/plain")

#todo: how to handle splits?
@login_required
def consumption_event_for_commitment(request):
    id = request.POST.get("id")
    resource_id = request.POST.get("resourceId")
    quantity = request.POST.get("quantity")
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    ct = get_object_or_404(Commitment, pk=id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    agent = get_agent(request)
    quantity = Decimal(quantity)
    if quantity:
        event = None
        events = ct.fulfillment_events.filter(resource=resource)
        if events:
            event = events[events.count() - 1]
        if event:
            if event.quantity != quantity:
                delta = event.quantity - quantity
                event.quantity = quantity
                event.changed_by = request.user
                event.save()
                if event.resource:
                    if ct.consumes_resources():
                        resource = event.resource
                        resource.quantity += delta
                        resource.changed_by=request.user
                        resource.save()
        else:
            if ct.consumes_resources():
                resource.quantity -= quantity
                resource.changed_by=request.user
                resource.save()
            event = EconomicEvent(
                resource = resource,
                commitment = ct,
                event_date = event_date,
                event_type = ct.event_type,
                to_agent = agent,
                resource_type = ct.resource_type,
                process = ct.process,
                #project = ct.project,
                context_agent = ct.context_agent,
                quantity = quantity,
                unit_of_quantity = ct.unit_of_quantity,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()

    data = "ok"
    return HttpResponse(data, content_type="text/plain")

@login_required
def citation_event_for_commitment(request):
    id = request.POST.get("id")
    resource_id = request.POST.get("resourceId")
    cited = int(request.POST.get("cited"))
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    ct = get_object_or_404(Commitment, pk=id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    agent = get_agent(request)
    quantity = Decimal("1")
    event = None
    events = ct.fulfillment_events.filter(resource=resource)
    if events:
        event = events[events.count() - 1]
    if event:
        if not cited:
            event.delete()
    else:
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = ct.event_type,
            from_agent = agent,
            resource_type = ct.resource_type,
            process = ct.process,
            #project = ct.project,
            context_agent = ct.context_agent,
            quantity = quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()

    data = "ok"
    return HttpResponse(data, content_type="text/plain")

@login_required
def time_use_event_for_commitment(request):
    id = request.POST.get("id")
    resource_id = request.POST.get("resourceId")
    quantity = request.POST.get("quantity")
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    ct = get_object_or_404(Commitment, pk=id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    agent = get_agent(request)
    quantity = Decimal(quantity)
    event = None
    events = ct.fulfillment_events.filter(resource=resource)
    if not event_date:
        event_date = datetime.date.today()
    #todo: is this correct?
    if events:
        event = events[events.count() - 1]
    if event:
        if event.quantity != quantity:
            delta = event.quantity - quantity
            event.quantity = quantity
            event.changed_by = request.user
            event.save()
            if event.resource:
                if ct.consumes_resources():
                    resource = event.resource
                    resource.quantity += delta
                    resource.changed_by=request.user
                    resource.save()
    else:
        if ct.consumes_resources():
            resource.quantity -= quantity
            resource.changed_by=request.user
            resource.save()
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = ct.event_type,
            from_agent = agent,
            to_agent = ct.process.default_agent(),
            resource_type = ct.resource_type,
            process = ct.process,
            #project = ct.project,
            context_agent = ct.context_agent,
            quantity = quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()

    data = "ok"
    return HttpResponse(data, content_type="text/plain")

@login_required
def failed_outputs(request, commitment_id):
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    if request.method == "POST":
        failure_form = FailedOutputForm(data=request.POST)
        if failure_form.is_valid():
            ct = get_object_or_404(Commitment, id=commitment_id)
            agent = get_agent(request)
            resource_type = ct.resource_type
            process = ct.process
            event = failure_form.save(commit=False)
            data = failure_form.cleaned_data
            quantity = data["quantity"]
            description = data["description"]
            unit_type = resource_type.unit.unit_type
            ets = EventType.objects.filter(
                resource_effect="<",
                unit_type=unit_type)
            if ets:
                event_type = ets[0]
            else:
                et_name = " ".join(["Failed", unit_type])
                event_type = EventType(
                    name=et_name,
                    resource_effect="<",
                    unit_type=unit_type)
                event_type.save()
            resource = EconomicResource(
                resource_type = ct.resource_type,
                created_date = event_date,
                quantity = quantity,
                quality = Decimal("-1"),
                #unit_of_quantity = ct.unit_of_quantity,
                notes = description,
                created_by=request.user,
            )
            resource.save()
            event.resource = resource
            event.event_date = event_date
            event.event_type = event_type
            event.from_agent = agent
            event.resource_type = ct.resource_type
            event.process = process
            #event.project = ct.project
            event.context_agent = ct.context_agent
            event.unit_of_quantity = ct.unit_of_quantity
            event.quality = Decimal("-1")
            event.created_by = request.user
            event.changed_by = request.user
            event.save()
            data = str(ct.failed_output_qty())
            return HttpResponse(data, content_type="text/plain")

#todo: obsolete
@login_required
def copy_process(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    #todo: is this correct? maybe not.
    demand = process.independent_demand()
    demand_form = DemandSelectionForm(data=request.POST or None)
    process_init = {
        "project": process.context_agent,
        "url": process.url,
        "notes": process.notes,
    }
    process_form = ProcessForm(initial=process_init, data=request.POST or None)
    output_init = []
    for op in process.outgoing_commitments():
        output_init.append({
            'resource_type': op.resource_type,
            'quantity': op.quantity,
            'description': op.description,
            'unit_of_quantity': op.unit_of_quantity,
        })
    input_init = []
    for ip in process.incoming_commitments():
        input_init.append({
            'resource_type': ip.resource_type,
            'quantity': ip.quantity,
            'description': ip.description,
            'unit_of_quantity': ip.unit_of_quantity,
        })
    OutputFormSet = modelformset_factory(
        Commitment,
        form=ProcessOutputForm,
        can_delete=True,
        extra=2,
        )
    output_formset = OutputFormSet(
        queryset=Commitment.objects.none(),
        initial=output_init,
        data=request.POST or None,
        prefix='output')
    InputFormSet = modelformset_factory(
        Commitment,
        form=ProcessInputForm,
        can_delete=True,
        extra=4,
        )
    input_formset = InputFormSet(
        queryset=Commitment.objects.none(),
        initial=input_init,
        data=request.POST or None,
        prefix='input')
    if request.method == "POST":
        keep_going = request.POST.get("keep-going")
        just_save = request.POST.get("save")
        if process_form.is_valid():
            process_data = process_form.cleaned_data
            process = process_form.save(commit=False)
            process.created_by=request.user
            process.save()
            if demand_form.is_valid():
                demand = demand_form.cleaned_data["demand"]
            for form in output_formset.forms:
                if form.is_valid():
                    output_data = form.cleaned_data
                    qty = output_data["quantity"]
                    if qty:
                        ct = form.save(commit=False)
                        rt = output_data["resource_type"]
                        #rel =
                        ct.relationship = rel
                        ct.event_type = rel.event_type
                        ct.process = process
                        ct.context_agent = process.context_agent
                        #flow todo: add order_item
                        #obsolete
                        ct.independent_demand = demand
                        ct.due_date = process.end_date
                        ct.created_by = request.user
                        ct.save()
            for form in input_formset.forms:
                if form.is_valid():
                    input_data = form.cleaned_data
                    qty = input_data["quantity"]
                    if qty:
                        ct = form.save(commit=False)
                        rt = input_data["resource_type"]
                        #rel =
                        ct.relationship = rel
                        ct.event_type = rel.event_type
                        ct.process = process
                        #flow todo: add order_item
                        #obsolete
                        ct.independent_demand = demand
                        ct.due_date = process.start_date
                        ct.created_by = request.user
                        rt = ct.resource_type
                        #todo pr: this shd probably use own_or_parent_recipes
                        #obsolete
                        ptrt, inheritance = rt.main_producing_process_type_relationship()
                        ct.save()
                        explode_dependent_demands(ct, request.user)
            if just_save:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/process', process.id))
            elif keep_going:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/change-process', process.id))
    return render(request, "valueaccounting/create_process.html", {
        "demand": demand,
        "demand_form": demand_form,
        "process_form": process_form,
        "output_formset": output_formset,
        "input_formset": input_formset,
    })

@login_required
def change_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    commitment = event.commitment
    process = event.process
    context_agent = event.context_agent
    if request.method == "POST":
        prefix = event.form_prefix()
        form = InputEventAgentForm(context_agent=context_agent, instance=event, prefix=prefix, data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            form.save()
    next = request.POST.get("next")
    if next == "process":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))
    elif next == "work":
        return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', process.id))
    else:
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/labnote', commitment.id))

@login_required
def change_unplanned_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    process = event.process
    pattern = process.process_pattern
    if pattern:
        if request.method == "POST":
            form = UnplannedWorkEventForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))

@login_required
def change_exchange_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    exchange = event.exchange
    context_agent=exchange.context_agent
    if request.method == "POST":
        form = WorkEventAgentForm(
            context_agent=context_agent,
            instance=event,
            data=request.POST,
            prefix=str(event.id))
        if form.is_valid():
            data = form.cleaned_data
            form.save()

        next = request.POST.get("next")
        if next:
            if next == "exchange-work":
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('accounting/exchange', 0, exchange.id))

#obsolete?
@login_required
def change_unplanned_payment_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    old_resource = event.resource
    old_qty = event.quantity
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = PaymentEventForm(
                pattern=pattern,
                instance=event,
                posting=True,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                form.save(commit=False)
                event.unit_of_quantity = event.resource_type.unit
                form.save()
                if event.resource:
                    resource = event.resource
                    if old_resource:
                        if resource != old_resource:
                            old_resource.quantity = old_resource.quantity + old_qty
                            old_resource.save()
                            resource.quantity = resource.quantity - event.quantity
                        else:
                            changed_qty = event.quantity - old_qty
                            if changed_qty != 0:
                                resource.quantity = resource.quantity - changed_qty
                    else:
                        resource.quantity = resource.quantity - event.quantity
                    resource.save()
                else:
                    if old_resource:
                        old_resource.quantity = old_resource.quantity + old_qty
                        old_resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

#obsolete?
@login_required
def change_receipt_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = UnorderedReceiptForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

#obsolete?
@login_required
def change_cash_receipt_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    old_resource = event.resource
    old_qty = event.quantity
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = CashReceiptForm(
                pattern=pattern,
                instance=event,
                posting=True,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                form.save(commit=False)
                event.unit_of_quantity = event.resource_type.unit
                form.save()
                if event.resource:
                    resource = event.resource
                    if old_resource:
                        if resource != old_resource:
                            old_resource.quantity = old_resource.quantity - old_qty
                            old_resource.save()
                            resource.quantity = resource.quantity + event.quantity
                        else:
                            changed_qty = event.quantity - old_qty
                            if changed_qty != 0:
                                resource.quantity = resource.quantity + changed_qty
                    else:
                        resource.quantity = resource.quantity + event.quantity
                    resource.save()
                else:
                    if old_resource:
                        old_resource.quantity = old_resource.quantity - old_qty
                        old_resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

#obsolete?
@login_required
def change_shipment_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    old_resource = event.resource
    old_qty = event.quantity
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = ShipmentForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()
                if event.resource:
                    resource = event.resource
                    if resource != old_resource:
                        old_resource.quantity = old_resource.quantity + old_qty
                        old_resource.save()
                        resource.quantity = resource.quantity - event.quantity
                    else:
                        changed_qty = event.quantity - old_qty
                        if changed_qty != 0:
                            resource.quantity = resource.quantity - changed_qty
                    if resource.quantity < 0:
                        resource.quantity = 0
                    resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

#obsolete?
@login_required
def change_uninventoried_shipment_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = UninventoriedShipmentForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

@login_required
def change_distribution_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    old_resource = event.resource
    old_qty = event.quantity
    distribution = event.distribution
    pattern = distribution.process_pattern
    if request.method == "POST":
        form = DistributionEventForm(
            pattern=pattern,
            instance=event,
            posting=True,
            prefix=event.form_prefix(),
            data=request.POST)
        if form.is_valid():
            form.save(commit=False)
            event.unit_of_quantity = event.resource_type.unit
            event.changed_by = request.user
            event.save()
            if event.resource:
                resource = event.resource
                if old_resource:
                    if resource != old_resource:
                        old_resource.quantity = old_resource.quantity - old_qty
                        old_resource.save()
                        resource.quantity = resource.quantity + event.quantity
                    else:
                        changed_qty = event.quantity - old_qty
                        if changed_qty != 0:
                            resource.quantity = resource.quantity + changed_qty
                else:
                    resource.quantity = resource.quantity + event.quantity
                resource.save()
            else:
                if old_resource:
                    old_resource.quantity = old_resource.quantity - old_qty
                    old_resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/distribution', distribution.id))

@login_required
def change_disbursement_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    old_resource = event.resource
    old_qty = event.quantity
    distribution = event.distribution
    pattern = distribution.process_pattern
    if request.method == "POST":
        form = DisbursementEventForm(
            pattern=pattern,
            instance=event,
            posting=True,
            prefix=event.form_prefix(),
            data=request.POST)
        if form.is_valid():
            form.save(commit=False)
            event.unit_of_quantity = event.resource_type.unit
            event.changed_by = request.user
            event.save()
            if event.resource:
                resource = event.resource
                if old_resource:
                    if resource != old_resource:
                        old_resource.quantity = old_resource.quantity + old_qty
                        old_resource.save()
                        resource.quantity = resource.quantity - event.quantity
                    else:
                        changed_qty = event.quantity - old_qty
                        if changed_qty != 0:
                            resource.quantity = resource.quantity - changed_qty
                else:
                    resource.quantity = resource.quantity - event.quantity
                resource.save()
            else:
                if old_resource:
                    old_resource.quantity = old_resource.quantity + old_qty
                    old_resource.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/distribution', distribution.id))

#obsolete?
@login_required
def change_expense_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    exchange = event.exchange
    pattern = exchange.process_pattern
    if pattern:
        if request.method == "POST":
            form = ExpenseEventForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/exchange', exchange.id))

#this has been duplicated in models in class Commitment, to support the api
def handle_commitment_changes(old_ct, new_rt, new_qty, old_demand, new_demand):
    propagators = []
    explode = True
    if old_ct.event_type.relationship == "out":
        dependants = old_ct.process.incoming_commitments()
        propagators.append(old_ct)
        if new_qty != old_ct.quantity:
            explode = False
    else:
        dependants = old_ct.associated_producing_commitments()
    old_rt = old_ct.resource_type
    order_item = old_ct.order_item

    if not propagators:
        for dep in dependants:
            if order_item:
                if dep.order_item == order_item:
                    propagators.append(dep)
                    explode = False
            else:
                if dep.due_date == old_ct.process.start_date:
                    if dep.quantity == old_ct.quantity:
                        propagators.append(dep)
                        explode = False
    if new_rt != old_rt:
        for ex_ct in old_ct.associated_producing_commitments():
            if ex_ct.order_item == order_item:
                ex_ct.delete_dependants()
        old_ct.delete()
        explode = True
    elif new_qty != old_ct.quantity:
        delta = new_qty - old_ct.quantity
        for pc in propagators:
            if new_demand != old_demand:
                propagate_changes(pc, delta, old_demand, new_demand, [])
            else:
                propagate_qty_change(pc, delta, [])
    else:
        if new_demand != old_demand:
            #this is because we are just changing the order
            delta = Decimal("0")
            for pc in propagators:
                propagate_changes(pc, delta, old_demand, new_demand, [])
            explode = False

    return explode

class ProcessOutputFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.pattern = kwargs.pop('pattern', None)
        super(ProcessOutputFormSet, self).__init__(*args, **kwargs)

    def _construct_forms(self):
        self.forms = []
        for i in range(self.total_form_count()):
            self.forms.append(self._construct_form(i, pattern=self.pattern))


class ProcessInputFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.pattern = kwargs.pop('pattern', None)
        super(ProcessInputFormSet, self).__init__(*args, **kwargs)

    def _construct_forms(self):
        self.forms = []
        for i in range(self.total_form_count()):
            self.forms.append(self._construct_form(i, pattern=self.pattern))


class ProcessCitationFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.pattern = kwargs.pop('pattern', None)
        super(ProcessCitationFormSet, self).__init__(*args, **kwargs)

    def _construct_forms(self):
        self.forms = []
        for i in range(self.total_form_count()):
            self.forms.append(self._construct_form(i, pattern=self.pattern))


class ProcessWorkFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.pattern = kwargs.pop('pattern', None)
        super(ProcessWorkFormSet, self).__init__(*args, **kwargs)

    def _construct_forms(self):
        self.forms = []
        for i in range(self.total_form_count()):
            self.forms.append(self._construct_form(i, pattern=self.pattern))


@login_required
def change_process(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    if request.method == "POST":
        form = ProcessForm(
            instance=process,
            data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            form.save()
            next = request.POST.get("next")
            if next:
                return HttpResponseRedirect('/%s/%s/'
                    % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/process', process.id))
    '''
    process = get_object_or_404(Process, id=process_id)
    original_start = process.start_date
    original_end = process.end_date
    demand = process.independent_demand()
    order_item = process.order_item()
    existing_demand = demand
    if demand:
        if demand.order_type != "holder":
            init = {}
            if not demand.receiver:
                init = {'create_order': True,}
            rand_form = RandOrderForm(
                instance=demand,
                data=request.POST or None,
                initial=init)
            demand_init = {"demand": demand,}
            demand_form = DemandSelectionForm(
                data=request.POST or None,
                initial=demand_init)
        else:
            demand_form = DemandSelectionForm(data=request.POST or None)
            rand_form = RandOrderForm(data=request.POST or None)
    else:
        demand_form = DemandSelectionForm(data=request.POST or None)
        rand_form = RandOrderForm(data=request.POST or None)
    process_form = ProcessForm(instance=process, data=request.POST or None)
    pattern = None
    if process.process_pattern:
        pattern = process.process_pattern
    OutputFormSet = modelformset_factory(
        Commitment,
        form=ProcessOutputForm,
        formset=ProcessOutputFormSet,
        can_delete=True,
        extra=1,
        )
    output_formset = OutputFormSet(
        queryset=process.outgoing_commitments(),
        data=request.POST or None,
        prefix='output',
        pattern=pattern)
    CitationFormSet = modelformset_factory(
        Commitment,
        form=ProcessCitationCommitmentForm,
        formset=ProcessCitationFormSet,
        can_delete=True,
        extra=2,
        )
    citation_formset = CitationFormSet(
        queryset=process.citation_requirements(),
        data=request.POST or None,
        prefix='citation',
        pattern=pattern)
    WorkFormSet = modelformset_factory(
        model=Commitment,
        form=ProcessWorkForm,
        formset=ProcessWorkFormSet,
        can_delete=True,
        extra=2,
        )
    work_formset = WorkFormSet(
        queryset=process.work_requirements(),
        data=request.POST or None,
        prefix='work',
        pattern=pattern)
    ConsumableFormSet = modelformset_factory(
        Commitment,
        form=ProcessConsumableForm,
        formset=ProcessInputFormSet,
        can_delete=True,
        extra=2,
        )
    consumable_formset = ConsumableFormSet(
        queryset=process.consumed_input_requirements(),
        data=request.POST or None,
        prefix='consumable',
        pattern=pattern)
    UsableFormSet = modelformset_factory(
        Commitment,
        form=ProcessUsableForm,
        formset=ProcessInputFormSet,
        can_delete=True,
        extra=2,
        )
    usable_formset = UsableFormSet(
        queryset=process.used_input_requirements(),
        data=request.POST or None,
        prefix='usable',
        pattern=pattern)

    if request.method == "POST":
        keep_going = request.POST.get("keep-going")
        just_save = request.POST.get("save")
        if process_form.is_valid():
            process_data = process_form.cleaned_data
            new_end = process_data["end_date"]
            new_start = process_data["start_date"]
            process = process_form.save(commit=False)
            process.changed_by=request.user
            process.save()
            if original_end:
                if new_end > original_end:
                    delta = new_end - original_end
                    #todo: revive using Problems and Solutions
                    #process.reschedule_connections(delta.days, request.user)
            else:
                if new_start > original_start:
                    delta = new_start - original_start
                    process.end_date = new_start
                    process.save()
                    #todo: revive using Problems and Solutions
                    #process.reschedule_connections(delta.days, request.user)
            pattern = process.process_pattern
            #todo: always creates a rand. the form is always valid.
            if rand_form.is_valid():
                rand_data = rand_form.cleaned_data
                receiver = rand_data['receiver']
                provider = rand_data['provider']
                create_order = rand_data['create_order']
                if create_order or demand or receiver or provider:
                    demand = rand_form.save(commit=False)
                    if existing_demand:
                        if create_order:
                            demand.order_type = 'rand'
                        demand.changed_by = request.user
                    else:
                        demand.order_type = 'rand'
                        demand.created_by = request.user
                    demand.due_date = process.end_date
                    demand.save()
            if demand_form:
                if demand_form.is_valid():
                    selected_demand = demand_form.cleaned_data["demand"]
                    if selected_demand:
                        demand = selected_demand
            for form in output_formset.forms:
                #flow todo: output changes shd propagate to dependants too
                if form.is_valid():
                    output_data = form.cleaned_data
                    qty = output_data["quantity"]
                    ct_from_id = output_data["id"]
                    if qty:
                        ct = form.save(commit=False)
                        #this was wrong. Would it ever be correct?
                        #ct.order = demand
                        ct.order_item = order_item
                        ct.independent_demand = demand
                        ct.context_agent = process.context_agent
                        ct.due_date = process.end_date
                        if ct_from_id:
                            ct.changed_by = request.user
                            old_ct = Commitment.objects.get(id=ct_from_id.id)
                            explode = handle_commitment_changes(old_ct, ct.resource_type, qty, existing_demand, demand)
                        else:
                            ct.process = process
                            ct.created_by = request.user
                            rt = output_data["resource_type"]
                            event_type = pattern.event_type_for_resource_type("out", rt)
                            ct.event_type = event_type
                        ct.save()
                        if process.name == "Make something":
                            process.name = " ".join([
                                        "Make",
                                        rt.name,
                                    ])
                            process.save()
                    elif ct_from_id:
                        ct = form.save()
                        #flow todo: shd this delete_dependants?
                        ct.delete()
            for form in citation_formset.forms:
                if form.is_valid():
                    citation_data = form.cleaned_data
                    if citation_data:
                        cited = citation_data["quantity"]
                        ct_from_id = citation_data["id"]
                        if cited:
                            rt = citation_data["resource_type"]
                            if rt:
                                ct = form.save(commit=False)
                                ct.order_item = order_item
                                ct.independent_demand = demand
                                ct.context_agent = process.context_agent
                                ct.due_date = process.end_date
                                ct.quantity = Decimal("1")
                                if ct_from_id:
                                    old_ct = Commitment.objects.get(id=ct_from_id.id)
                                    old_rt = old_ct.resource_type
                                    if not old_rt == rt:
                                        event_type = pattern.event_type_for_resource_type("cite", rt)
                                        ct.event_type = event_type
                                        unit = rt.unit
                                        ct.unit_of_quantity = unit
                                        ct.changed_by = request.user
                                else:
                                    ct.process = process
                                    ct.created_by = request.user
                                    event_type = pattern.event_type_for_resource_type("cite", rt)
                                    ct.event_type = event_type
                                    unit = rt.unit
                                    ct.unit_of_quantity = unit
                                ct.save()
                        elif ct_from_id:
                            ct = form.save()
                            ct.delete()

            for form in work_formset.forms:
                if form.is_valid():
                    work_data = form.cleaned_data
                    if work_data:
                        hours = work_data["quantity"]
                        ct_from_id = work_data["id"]
                        if hours:
                            rt = work_data["resource_type"]
                            if rt:
                                ct = form.save(commit=False)
                                ct.order_item = order_item
                                ct.independent_demand = demand
                                ct.context_agent = process.context_agent
                                ct.due_date = process.end_date
                                if ct_from_id:
                                    old_ct = Commitment.objects.get(id=ct_from_id.id)
                                    old_rt = old_ct.resource_type
                                    if not old_rt == rt:
                                        event_type = pattern.event_type_for_resource_type("work", rt)
                                        ct.event_type = event_type
                                        unit = rt.unit
                                        ct.unit_of_quantity = unit
                                        ct.changed_by = request.user
                                else:
                                    ct.process = process
                                    ct.created_by = request.user
                                    event_type = pattern.event_type_for_resource_type("work", rt)
                                    ct.event_type = event_type
                                    unit = rt.unit
                                    ct.unit_of_quantity = unit
                                ct.save()
                                if not ct_from_id:
                                    if notification:
                                        agent = get_agent(request)
                                        users = ct.possible_work_users()
                                        site_name = get_site_name()
                                        if users:
                                            notification.send(
                                                users,
                                                "valnet_new_task",
                                                {"resource_type": ct.resource_type,
                                                "due_date": ct.due_date,
                                                "hours": ct.quantity,
                                                "unit": ct.resource_type.unit,
                                                "description": ct.description or "",
                                                "process": ct.process,
                                                "creator": agent,
                                                "site_name": site_name,
                                                }
                                            )
                        elif ct_from_id:
                            ct = form.save()
                            ct.delete()

            for form in consumable_formset.forms:
                if form.is_valid():
                    explode = False
                    input_data = form.cleaned_data
                    qty = input_data["quantity"]
                    ct_from_id = input_data["id"]
                    #refactor out
                    if not qty:
                        if ct_from_id:
                            ct = form.save()
                            ct.delete_dependants()
                            ct.delete()
                    else:
                        ct = form.save(commit=False)
                        ct.due_date = process.start_date
                        ct.order_item = order_item
                        ct.independent_demand = demand
                        if ct_from_id:
                            old_ct = Commitment.objects.get(id=ct_from_id.id)
                            explode = handle_commitment_changes(old_ct, ct.resource_type, qty, existing_demand, demand)
                            ct.changed_by = request.user
                            rt = input_data["resource_type"]
                            event_type = pattern.event_type_for_resource_type("consume", rt)
                            ct.event_type = event_type
                        else:
                            explode = True
                            rt = input_data["resource_type"]
                            event_type = pattern.event_type_for_resource_type("consume", rt)
                            ct.event_type = event_type
                            ct.process = process
                            ct.order_item = order_item
                            ct.independent_demand = demand
                            ct.created_by = request.user
                            #todo: add stage and state as args?
                            #todo pr: this shd probably use own_or_parent_recipes
                            ptrt, inheritance = ct.resource_type.main_producing_process_type_relationship()
                            if ptrt:
                                ct.context_agent = process.context_agent
                        ct.save()
                        if explode:
                            #todo: use new commitment.generate_producing_process(request.user, explode=True)
                            #or process.explode_demands?
                            explode_dependent_demands(ct, request.user)
            for form in usable_formset.forms:
                if form.is_valid():
                    #probly not needed for usables
                    explode = False
                    input_data = form.cleaned_data
                    qty = input_data["quantity"]
                    ct_from_id = input_data["id"]
                    if not qty:
                        if ct_from_id:
                            ct = form.save()
                            ct.delete_dependants()
                            ct.delete()
                    else:
                        ct = form.save(commit=False)
                        ct.due_date = process.start_date
                        ct.order_item = order_item
                        ct.independent_demand = demand
                        if ct_from_id:
                            old_ct = Commitment.objects.get(id=ct_from_id.id)
                            explode = handle_commitment_changes(old_ct, ct.resource_type, qty, existing_demand, demand)
                            ct.changed_by = request.user
                            rt = input_data["resource_type"]
                            event_type = pattern.event_type_for_resource_type("use", rt)
                            ct.event_type = event_type
                        else:
                            explode = True
                            rt = input_data["resource_type"]
                            event_type = pattern.event_type_for_resource_type("use", rt)
                            ct.event_type = event_type
                            ct.process = process
                            ct.order_item = order_item
                            ct.independent_demand = demand
                            ct.due_date = process.start_date
                            ct.created_by = request.user
                            #todo: add stage and state as args
                            #todo pr: this shd probably use own_or_parent_recipes
                            ptrt, inheritance = ct.resource_type.main_producing_process_type_relationship()
                            if ptrt:
                                ct.context_agent = process.context_agent
                        ct.save()
                        #probly not needed for usables
                        #if explode:
                        #    explode_dependent_demands(ct, request.user)


            if just_save:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/process', process.id))
            elif keep_going:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/change-process', process.id))
    return render(request, "valueaccounting/change_process.html", {
        "process": process,
        "rand_form": rand_form,
        "demand_form": demand_form,
        "process_form": process_form,
        "output_formset": output_formset,
        "citation_formset": citation_formset,
        "consumable_formset": consumable_formset,
        "usable_formset": usable_formset,
        "work_formset": work_formset,
    })
    '''

#todo: soon to be obsolete (is it obsolete now?)
def explode_dependent_demands(commitment, user):
    """This method assumes an input commitment"""

    qty_to_explode = commitment.net()
    if qty_to_explode:
        rt = commitment.resource_type
        #todo: add stage and state as args?
        #todo pr: this shd probably use own_or_parent_recipes
        ptrt, inheritance = rt.main_producing_process_type_relationship()
        demand = commitment.independent_demand
        if ptrt:
            pt = ptrt.process_type
            start_date = commitment.due_date - datetime.timedelta(minutes=pt.estimated_duration)
            feeder_process = Process(
                name=pt.name,
                process_type=pt,
                process_pattern=pt.process_pattern,
                context_agent=pt.context_agent,
                url=pt.url,
                end_date=commitment.due_date,
                plan=demand,
                start_date=start_date,
                created_by=user,
            )
            feeder_process.save()
            #todo: sub process.add_commitment()
            output_commitment = Commitment(
                independent_demand=demand,
                order_item = commitment.order_item,
                event_type=ptrt.event_type,
                due_date=commitment.due_date,
                resource_type=rt,
                process=feeder_process,
                context_agent=pt.context_agent,
                quantity=qty_to_explode,
                unit_of_quantity=rt.unit,
                description=ptrt.description,
                created_by=user,
            )
            output_commitment.save()
            recursively_explode_demands(feeder_process, demand, user, [])

def propagate_qty_change(commitment, delta, visited):
    process = commitment.process
    if commitment not in visited:
        visited.append(commitment)
        for ic in process.incoming_commitments():
            if ic.event_type.relationship != "cite":
                input_ctype = ic.commitment_type()
                output_ctype = commitment.commitment_type()
                ratio = input_ctype.quantity / output_ctype.quantity
                new_delta = (delta * ratio).quantize(Decimal('.01'), rounding=ROUND_UP)

                ic.quantity += new_delta
                ic.save()
                rt = ic.resource_type
                pcs = ic.associated_producing_commitments()
                if pcs:
                    oh_qty = 0
                    if rt.substitutable:
                        if ic.event_type.resource_effect == "-":
                            oh_qty = rt.onhand_qty_for_commitment(ic)
                    if oh_qty:
                        delta_delta = ic.quantity - oh_qty
                        new_delta = delta_delta
                order_item = ic.order_item
                for pc in pcs:
                    if pc.order_item == order_item:
                        propagate_qty_change(pc, new_delta, visited)
    commitment.quantity += delta
    commitment.save()

def propagate_changes(commitment, delta, old_demand, new_demand, visited):
    process = commitment.process
    order_item = commitment.order_item
    if process not in visited:
        visited.append(process)
        for ic in process.incoming_commitments():
            ratio = ic.quantity / commitment.quantity
            new_delta = (delta * ratio).quantize(Decimal('.01'), rounding=ROUND_UP)
            ic.quantity += new_delta
            ic.order_item = order_item
            ic.save()
            rt = ic.resource_type
            for pc in ic.associated_producing_commitments():
                if pc.order_item == order_item:
                    propagate_changes(pc, new_delta, old_demand, new_demand, visited)
    commitment.quantity += delta
    commitment.independent_demand = new_demand
    commitment.save()

@login_required
def change_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_form = OrderChangeForm(instance=order, data=request.POST or None)
    if request.method == "POST":
        next = request.POST.get("next")
        if order_form.is_valid():
            order = order_form.save()
            if next == "demand":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/demand'))
            if next == "closed_work_orders":
                return HttpResponseRedirect('/%s/'
                    % ('accounting/closed-work-orders'))
    else:
        next = request.GET.get("next")

    return render(request, "valueaccounting/change_order.html", {
        "order_form": order_form,
        "order": order,
        "next": next,
    })

class ResourceType_EventType(object):
    def __init__(self, resource_type, event_type):
        self.resource_type = resource_type
        self.event_type = event_type

@login_required
def process_selections(request, rand=0):
    slots = []
    resource_types = []
    selected_pattern = None
    selected_context_agent = None
    pattern_form = PatternProdSelectionForm()
    ca_form = ProjectSelectionForm()
    init = {"start_date": datetime.date.today(), "end_date": datetime.date.today()}
    process_form = DateAndNameForm(data=request.POST or None)
    demand_form = DemandSelectionForm(data=request.POST or None)
    if request.method == "POST":
        input_resource_types = []
        input_process_types = []
        done_process = request.POST.get("create-process")
        add_another = request.POST.get("add-another")
        edit_process = request.POST.get("edit-process")
        labnotes = request.POST.get("labnotes")
        get_related = request.POST.get("get-related")
        if get_related:
            selected_pattern = ProcessPattern.objects.get(id=request.POST.get("pattern"))
            selected_context_agent = EconomicAgent.objects.get(id=request.POST.get("context_agent"))
            if selected_pattern:
                slots = selected_pattern.event_types()
                for slot in slots:
                    slot.resource_types = selected_pattern.get_resource_types(slot)
            process_form = DateAndNameForm(initial=init)
        else:
            rp = request.POST
            today = datetime.date.today()
            if process_form.is_valid():
                start_date = process_form.cleaned_data["start_date"]
                end_date = process_form.cleaned_data["end_date"]
                process_name = process_form.cleaned_data["process_name"]
            else:
                start_date = today
                end_date = today
            demand = None
            added_to_order = False
            if demand_form.is_valid():
                demand = demand_form.cleaned_data["demand"]
                if demand:
                    added_to_order = True
            produced_rts = []
            cited_rts = []
            consumed_rts = []
            used_rts = []
            work_rts = []
            for key, value in list(dict(rp).items()):
                if "selected-context-agent" in key:
                    context_agent_id = key.split("~")[1]
                    selected_context_agent = EconomicAgent.objects.get(id=context_agent_id)
                    continue
                if "selected-pattern" in key:
                    pattern_id = key.split("~")[1]
                    selected_pattern = ProcessPattern.objects.get(id=pattern_id)
                    continue
                et = None
                action = ""
                try:
                    et_name = key.split("~")[0]
                    et = EventType.objects.get(name=et_name)
                    action = et.relationship
                except EventType.DoesNotExist:
                    pass
                if action == "consume":
                    consumed_id = int(value[0])
                    consumed_rt = EconomicResourceType.objects.get(id=consumed_id)
                    consumed_rts.append(consumed_rt)
                    continue
                if action == "use":
                    used_id = int(value[0])
                    used_rt = EconomicResourceType.objects.get(id=used_id)
                    used_rts.append(used_rt)
                    continue
                if action == "cite":
                    cited_id = int(value[0])
                    cited_rt = EconomicResourceType.objects.get(id=cited_id)
                    cited_rts.append(cited_rt)
                    continue
                if action == "out":
                    produced_id = int(value[0])
                    produced_rt = EconomicResourceType.objects.get(id=produced_id)
                    produced_rts.append(produced_rt)
                    continue
                if action == "work":
                    work_id = int(value[0])
                    work_rt = EconomicResourceType.objects.get(id=work_id)
                    work_rts.append(work_rt)
                    continue

            if rand:
                if not demand:
                    demand = Order(
                        order_type="rand",
                        order_date=today,
                        due_date=end_date,
                        created_by=request.user)
                    demand.save()
            if not process_name:
                process_name = "Make something"
                if produced_rts:
                    process_name = " ".join([
                        "Make",
                        produced_rts[0].name,
                    ])

            process = Process(
                name=process_name,
                end_date=end_date,
                start_date=start_date,
                process_pattern=selected_pattern,
                created_by=request.user,
                context_agent=selected_context_agent,
                plan=demand,
            )
            process.save()

            for rt in produced_rts:
                resource_types.append(rt)
                et = selected_pattern.event_type_for_resource_type("out", rt)
                if et:
                    commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        description="",
                        user=request.user)
                    if rand:
                        if not added_to_order:
                            commitment.order = demand
                            commitment.order_item = commitment
                            commitment.save()
                        '''
                        #use recipe
                        #todo: add stage and state as args
                        pt = rt.main_producing_process_type()
                        process.process_type=pt
                        process.save()
                        if pt:
                            for xrt in pt.cited_resource_types():
                                if xrt not in resource_types:
                                    resource_types.append(xrt)
                            for xrt in pt.used_resource_types():
                                if xrt not in resource_types:
                                    resource_types.append(xrt)
                            for xrt in pt.consumed_resource_types():
                                if xrt not in resource_types:
                                    resource_types.append(xrt)
                            for xrt in pt.work_resource_types():
                                if xrt not in resource_types:
                                    resource_types.append(xrt)
                            process.explode_demands(demand, request.user, [])
                        '''
            for rt in cited_rts:
                et = selected_pattern.event_type_for_resource_type("cite", rt)
                if et:
                    commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        order_item = process.order_item(),
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        description="",
                        user=request.user)
            for rt in used_rts:
                if rt not in resource_types:
                    resource_types.append(rt)
                    et = selected_pattern.event_type_for_resource_type("use", rt)
                    if et:
                        commitment = process.add_commitment(
                            resource_type= rt,
                            demand=demand,
                            order_item = process.order_item(),
                            quantity=Decimal("1"),
                            event_type=et,
                            unit=rt.unit,
                            description="",
                            user=request.user)

            for rt in consumed_rts:
                if rt not in resource_types:
                    resource_types.append(rt)
                    et = selected_pattern.event_type_for_resource_type("consume", rt)
                    if et:
                        commitment = process.add_commitment(
                            resource_type= rt,
                            demand=demand,
                            order_item = process.order_item(),
                            quantity=Decimal("1"),
                            event_type=et,
                            unit=rt.unit,
                            description="",
                            user=request.user)

            for rt in work_rts:
                agent = None
                if labnotes:
                    agent = get_agent(request)
                et = selected_pattern.event_type_for_resource_type("work", rt)
                if et:
                    work_commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        order_item = process.order_item(),
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        from_agent=agent,
                        description="",
                        user=request.user)
                    if notification:
                        if not work_commitment.from_agent:
                            agent = get_agent(request)
                            users = work_commitment.possible_work_users()
                            site_name = get_site_name(request)
                            if users:
                                notification.send(
                                    users,
                                    "valnet_new_task",
                                    {"resource_type": work_commitment.resource_type,
                                    "due_date": work_commitment.due_date,
                                    "hours": work_commitment.quantity,
                                    "unit": work_commitment.resource_type.unit,
                                    "description": work_commitment.description or "",
                                    "process": work_commitment.process,
                                    "creator": agent,
                                    "site_name": site_name,
                                    }
                                )

            if done_process:
                #if demand:
                #    return HttpResponseRedirect('/%s/%s/'
                #        % ('accounting/order-schedule', demand.id))
                #else:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/process', process.id))
            if add_another:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/process-selections', rand))
            if edit_process:
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/change-process', process.id))
            if labnotes:
                return HttpResponseRedirect('/%s/%s/%s/'
                    % ('accounting/work-now', process.id, work_commitment.id))

    return render(request, "valueaccounting/process_selections.html", {
        "slots": slots,
        "selected_pattern": selected_pattern,
        "selected_context_agent": selected_context_agent,
        "ca_form": ca_form,
        "pattern_form": pattern_form,
        "process_form": process_form,
        "demand_form": demand_form,
        "rand": rand,
        "help": get_help("process_select"),
    })

@login_required
def plan_from_recipe(request):
    resource_types = []
    resource_type_lists = []
    selected_context_agent = None
    forward_schedule = False
    resource_driven = False
    ca_form = ProjectSelectionForm()
    init = {"date": datetime.date.today(),}
    date_name_form = OrderDateAndNameForm(data=request.POST or None)
    if request.method == "POST":
        create_order = request.POST.get("create-order")
        get_related = request.POST.get("get-related")
        if get_related:
            selected_context_agent = EconomicAgent.objects.get(id=request.POST.get("context_agent"))
            date_name_form = OrderDateAndNameForm(initial=init)
            if selected_context_agent:
                resource_type_lists = selected_context_agent.get_resource_type_lists()
                candidate_resource_types = selected_context_agent.get_resource_types_with_recipe()
                for rt in candidate_resource_types:
                    if rt.recipe_needs_starting_resource():
                        rt.onhand_resources = []
                        onhand = rt.onhand_for_resource_driven_recipe()
                        if onhand:
                            resource_types.append(rt)
                            for oh in onhand:
                                rt.onhand_resources.append(oh)
                    else:
                        resource_types.append(rt)
        else:
            rp = request.POST
            today = datetime.date.today()
            order_name = ""
            if date_name_form.is_valid():
                due_date = date_name_form.cleaned_data["date"]
                order_name = date_name_form.cleaned_data["order_name"]
                start_or_due = date_name_form.cleaned_data["start_date_or_due_date"]
            else:
                due_date = today
            for key, value in list(dict(rp).items()):
                if "selected-context-agent" in key:
                    context_agent_id = key.split("~")[1]
                    selected_context_agent = EconomicAgent.objects.get(id=context_agent_id)
                    continue
                if key == "rt":
                    value = value[0]
                    if "list" in value:
                        list_id = value.split("-")[1]
                        rt_list = ResourceTypeList.objects.get(id=list_id)
                        if rt_list.recipe_class() == "workflow":
                            forward_schedule = True
                        rts_to_produce = [elem.resource_type for elem in rt_list.list_elements.all()]
                        item_number = 1
                    else:
                        produced_id = int(value)
                        produced_rt = EconomicResourceType.objects.get(id=produced_id)
                        rts_to_produce = [produced_rt,]
                        if produced_rt.recipe_is_staged():
                            forward_schedule = True
                            if produced_rt.recipe_needs_starting_resource():
                                resource_driven = True
                if "resourcesFor" in key:
                    resource_id = int(value[0])
                    resource = EconomicResource.objects.get(id=resource_id)
            if forward_schedule:
                if start_or_due == "start":
                    start_date = due_date
                else:
                    forward_schedule = False

            if not forward_schedule:
                demand = Order(
                    order_type="rand",
                    order_date=today,
                    due_date=due_date,
                    name=order_name,
                    created_by=request.user)
                demand.save()

            for produced_rt in rts_to_produce:
                if forward_schedule:
                    #Todo: apply selected_context_agent to all of the above generators
                    if resource_driven:
                        demand = produced_rt.generate_staged_work_order_from_resource(resource, order_name, start_date, request.user)
                    else:
                        if len(rts_to_produce) == 1:
                            demand = produced_rt.generate_staged_work_order(order_name, start_date, request.user)
                        else:
                            if item_number == 1:
                                item_number += 1
                                demand = produced_rt.generate_staged_work_order(order_name, start_date, request.user)
                            else:
                                demand = produced_rt.generate_staged_order_item(demand, start_date, request.user)
                else:
                    ptrt, inheritance = produced_rt.main_producing_process_type_relationship()
                    et = ptrt.event_type
                    if et:
                        commitment = demand.add_commitment(
                            resource_type=produced_rt,
                            #Todo: apply selected_context_agent here? Only if inheritance?
                            context_agent=ptrt.process_type.context_agent,
                            quantity=ptrt.quantity,
                            event_type=et,
                            unit=produced_rt.unit,
                            description=ptrt.description or "",
                            stage=ptrt.stage,
                            state=ptrt.state,
                            )
                        commitment.created_by=request.user
                        commitment.save()

                        #Todo: apply selected_context_agent here?
                        process = commitment.generate_producing_process(request.user, [], inheritance=inheritance, explode=True)

            if notification:
                agent = get_agent(request)
                work_cts = Commitment.objects.filter(
                    independent_demand=demand,
                    event_type__relationship="work")
                for ct in work_cts:
                    users = ct.possible_work_users()
                    site_name = get_site_name(request)
                    if users:
                        notification.send(
                            users,
                            "valnet_new_task",
                            {"resource_type": ct.resource_type,
                            "due_date": ct.due_date,
                            "hours": ct.quantity,
                            "unit": ct.resource_type.unit,
                            "description": ct.description or "",
                            "process": ct.process,
                            "creator": agent,
                            "site_name": site_name,
                            }
                        )

            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/order-schedule', demand.id))

    return render(request, "valueaccounting/plan_from_recipe.html", {
        "selected_context_agent": selected_context_agent,
        "ca_form": ca_form,
        "date_name_form": date_name_form,
        "resource_types": resource_types,
        "resource_type_lists": resource_type_lists,
        "help": get_help("plan_from_recipe"),
    })

@login_required
def plan_from_rt(request, resource_type_id):
    resource_type = EconomicResourceType.objects.get(id=resource_type_id)
    name = "Make " + resource_type.name
    init = {"start_date": datetime.date.today(), "end_date": datetime.date.today(), "name": name}
    form = AddProcessFromResourceForm(initial=init, data=request.POST or None)
    if request.method == "POST":
        form = AddProcessFromResourceForm(data=request.POST)
        if form.is_valid():
            process = form.save(commit=False)
            process.created_by = request.user
            process.save()

            demand = Order(
                order_type="rand",
                order_date=datetime.date.today(),
                due_date=process.end_date,
                name=resource_type.name,
                created_by=request.user)
            demand.save()
            com = Commitment()
            com.context_agent = process.context_agent
            com.independent_demand = demand
            com.order_item = process.order_item()
            com.order = demand
            com.commitment_date = datetime.date.today()
            com.event_type = process.process_pattern.event_type_for_resource_type("out", resource_type)
            com.process = process
            com.due_date = process.end_date
            com.resource_type = resource_type
            com.quantity = Decimal("1")
            com.unit_of_quantity = resource_type.unit
            com.created_by = request.user
            com.save()
            #todo: if demand.add_commitment gets further developed, could use it instead of the above

            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/process', process.id))

    return render(request, "valueaccounting/plan_from_rt.html", {
        "form": form,
        "resource_type": resource_type,
        "help": get_help("plan_from_rt"),
    })

@login_required
def plan_from_rt_recipe(request, resource_type_id):
    resource_type = EconomicResourceType.objects.get(id=resource_type_id)
    resource_required = False
    recipe_type = "assembly"
    if resource_type.recipe_is_staged():
        recipe_type = "workflow"
        if resource_type.recipe_needs_starting_resource():
            recipe_type = "resource_driven"
    if recipe_type == "workflow":
        init = {"date": datetime.date.today(), "order_name": resource_type.name}
        date_name_form = OrderDateAndNameForm(initial=init, data=request.POST or None)
    elif recipe_type == "resource_driven":
        init = {"start_date": datetime.date.today(), "order_name": resource_type.name}
        date_name_form = StartDateAndNameForm(initial=init, data=request.POST or None)
        resource_required = True
    else:
        init = {"due_date": datetime.date.today(), "order_name": resource_type.name}
        date_name_form = DueDateAndNameForm(initial=init, data=request.POST or None)
    if request.method == "POST":
        if date_name_form.is_valid():
            schedule = True
            order_name = date_name_form.cleaned_data["order_name"]
            if recipe_type == "workflow":
                order_date = date_name_form.cleaned_data["date"]
                start_or_due = date_name_form.cleaned_data["start_date_or_due_date"]
                if start_or_due == "start":
                    demand = resource_type.generate_staged_work_order(order_name, order_date, request.user)
                    schedule = False
                else:
                    due_date = order_date
            elif recipe_type == "resource_driven":
                start_date = date_name_form.cleaned_data["start_date"]
                rid = request.POST.get("resource")
                if rid:
                    resource_id = int(rid)
                    resource = EconomicResource.objects.get(id=resource_id)
                    demand = resource_type.generate_staged_work_order_from_resource(resource, order_name, start_date, request.user)
                schedule = False
            else:
                due_date = date_name_form.cleaned_data["due_date"]
            if schedule:
                demand = Order(
                    order_type="rand",
                    order_date=datetime.date.today(),
                    due_date=due_date,
                    name=order_name,
                    created_by=request.user)
                demand.save()

                ptrt, inheritance = resource_type.main_producing_process_type_relationship()

                et = ptrt.event_type
                if et:
                    commitment = demand.add_commitment(
                        resource_type=resource_type,
                        context_agent=ptrt.process_type.context_agent,
                        quantity=ptrt.quantity,
                        event_type=et,
                        unit=resource_type.unit,
                        description=ptrt.description or "",
                        stage=ptrt.stage,
                        state=ptrt.state,)
                    commitment.created_by=request.user
                    commitment.save()
                    process = commitment.generate_producing_process(request.user, [], explode=True)
            if notification:
                agent = get_agent(request)
                work_cts = Commitment.objects.filter(
                    independent_demand=demand,
                    event_type__relationship="work")
                for ct in work_cts:
                    users = ct.possible_work_users()
                    site_name = get_site_name(request)
                    if users:
                        notification.send(
                            users,
                            "valnet_new_task",
                            {"resource_type": ct.resource_type,
                            "due_date": ct.due_date,
                            "hours": ct.quantity,
                            "unit": ct.resource_type.unit,
                            "description": ct.description or "",
                            "process": ct.process,
                            "creator": agent,
                            "site_name": site_name,
                            }
                        )

            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/order-schedule', demand.id))

    return render(request, "valueaccounting/plan_from_rt_recipe.html", {
        "date_name_form": date_name_form,
        "resource_type": resource_type,
        "resource_required": resource_required,
        "recipe_type": recipe_type,
        "help": get_help("plan_fr_rt_rcpe"),
    })


@login_required
def resource_facet_table(request):
    headings = ["Resource Type"]
    rows = []
    facets = Facet.objects.all()
    for facet in facets:
        headings.append(facet)
    for rt in EconomicResourceType.objects.all():
        row = [rt, ]
        for i in range(0, facets.count()):
            row.append("")
        for rf in rt.facets.all():
            cell = headings.index(rf.facet_value.facet)
            row[cell] = rf
        rows.append(row)
    return render(request, "valueaccounting/resource_facets.html", {
        "headings": headings,
        "rows": rows,
    })

@login_required
def comments(request):
    comments = Comment.objects.all().order_by("-submit_date")

    paginator = Paginator(comments, 25)
    page = request.GET.get('page')
    try:
        comment_list = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        comment_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        comment_list = paginator.page(paginator.num_pages)
    return render(request, "valueaccounting/comments.html", {
        "comment_list": comment_list,
    })

@login_required
def change_resource_facet_value(request):
    if request.method == "POST":
        #resource_type_label = request.POST.get("resourceType")
        #rt_name = resource_type_label.split("-", 1)[1].lstrip()
        rt_name = request.POST.get("resourceType")
        facet_name = request.POST.get("facet")
        value = request.POST.get("facetValue")
        rt = EconomicResourceType.objects.get(name=rt_name)
        facet = Facet.objects.get(name=facet_name)
        facet_value = None
        if value:
            facet_value = FacetValue.objects.get(facet=facet, value=value)
        rtfv = None
        try:
            rtfv = ResourceTypeFacetValue.objects.get(
                resource_type=rt,
                facet_value__facet=facet)
        except ResourceTypeFacetValue.DoesNotExist:
            pass
        if rtfv:
            if rtfv.facet_value != facet_value:
                rtfv.delete()
                rtfv = None
        if not rtfv:
            if value:
                rtfv = ResourceTypeFacetValue(
                    resource_type=rt,
                    facet_value=facet_value)
                rtfv.save()

    return HttpResponse("Ok", content_type="text/plain")

def create_facet_formset(data=None):
    RtfvFormSet = formset_factory(ResourceTypeFacetValueForm, extra=0)
    init = []
    facets = Facet.objects.all()
    for facet in facets:
        d = {"facet_id": facet.id,}
        init.append(d)
    formset = RtfvFormSet(initial=init, data=data)
    for form in formset:
        id = int(form["facet_id"].value())
        facet = Facet.objects.get(id=id)
        form.facet_name = facet.name
        fvs = facet.values.all()
        choices = [('', '----------')] + [(fv.id, fv.value) for fv in fvs]
        form.fields["value"].choices = choices
    return formset

def create_patterned_facet_formset(pattern, slot, data=None):
    RtfvFormSet = formset_factory(ResourceTypeFacetValueForm, extra=0)
    init = []
    facets = pattern.facets_by_relationship(slot)
    for facet in facets:
        d = {"facet_id": facet.id,}
        init.append(d)
    formset = RtfvFormSet(initial=init, data=data)
    for form in formset:
        id = int(form["facet_id"].value())
        facet = Facet.objects.get(id=id)
        form.facet_name = facet.name
        fvs = pattern.facet_values_for_facet_and_relationship(facet, slot)
        fvs = list(set(fvs))
        choices = [(fv.id, fv.value) for fv in fvs]
        form.fields["value"].choices = choices
    return formset


def exchanges(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    end =  today
    start = today - datetime.timedelta(days=365)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    #et_donation = EventType.objects.get(name="Donation")
    #et_cash = EventType.objects.get(name="Cash Contribution")
    #et_pay = EventType.objects.get(name="Payment")
    #et_receive = EventType.objects.get(name="Receipt")
    #et_expense = EventType.objects.get(name="Expense")
    et_give = EventType.objects.get(name="Give")
    et_receive = EventType.objects.get(name="Receive")
    #references = AccountingReference.objects.all()
    ets = ExchangeType.objects.supply_exchange_types()
    event_ids = ""
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            #exchanges = Exchange.objects.financial_contributions(start, end)
            exchanges = Exchange.objects.supply_exchanges(start, end)
        else:
            #exchanges = Exchange.objects.financial_contributions()
            exchanges = Exchange.objects.supply_exchanges()
        if agent_id:
            exchanges = exchanges.filter(context_agent=agent)
        selected_values = request.POST["categories"]
        if selected_values:
            sv = selected_values.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                transfers_included = []
                exchanges_included = []
                events_included = []
                for ex in exchanges:
                    if str(ex.exchange_type.id) in vals:
                        exchanges_included.append(ex)
                    #the following a start at filtering by accounting ref, doesn't work
                    #for transfer in ex.transfers.all():
                    #    for event in transfer.events.all():
                    #        if event.resource_type.accounting_reference:
                    #           if event.resource_type.accounting_reference.code in vals:
                    #                transfers_included.append(transfer)
                    #    if transfers_included != []:
                    #        ex.transfer_list = transfers_included
                    #        exchanges_included.append(ex)
                    #        transfers_included = []
                    #for event in ex.events.all(): #work events not part of a transfer
                    #    if event.resource_type.accounting_reference:
                    #        if event.resource_type.accounting_reference.code in vals:
                    #            events_included.append(event)
                    #    if events_included != []:
                    #        ex.event_list = events_included
                    #        events_included = []
                    #ex.event_list = events_included
                exchanges = exchanges_included
    else:
        if agent_id:
            exchanges = Exchange.objects.supply_exchanges(start, end).filter(context_agent=agent)
        else:
            exchanges = Exchange.objects.supply_exchanges(start, end)

    #total_cash = 0
    #total_receipts = 0
    #total_expenses = 0
    #total_payments = 0
    total_transfers = 0
    total_rec_transfers = 0
    comma = ""
    for x in exchanges:
        try:
            xx = list(x.transfer_list)
        except AttributeError:
            x.transfer_list = list(x.transfers.all())
        for transfer in x.transfer_list:
            if not transfer.transfer_type.is_reciprocal:
                if transfer.quantity():
                    total_transfers = total_transfers + transfer.quantity()
            else:
                if transfer.quantity():
                    total_rec_transfers = total_rec_transfers + transfer.quantity()
            for event in transfer.events.all():
                event_ids = event_ids + comma + str(event.id)
                comma = ","
        for event in x.events.all():
            event_ids = event_ids + comma + str(event.id)
            comma = ","
        #todo: get sort to work


    return render(request, "valueaccounting/exchanges.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "total_transfers": total_transfers,
        "total_rec_transfers": total_rec_transfers,
        "select_all": select_all,
        "selected_values": selected_values,
        #"references": references,
        "ets": ets,
        "event_ids": event_ids,
        "agent": agent,
    })

#obsolete
def exchanges_old(request):
    end = datetime.date.today()
    start = datetime.date(end.year, 1, 1)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_donation = EventType.objects.get(name="Donation")
    et_cash = EventType.objects.get(name="Cash Contribution")
    et_pay = EventType.objects.get(name="Payment")
    et_receive = EventType.objects.get(name="Receipt")
    et_expense = EventType.objects.get(name="Expense")
    #et_process_expense = EventType.objects.get(name="Process Expense")
    references = AccountingReference.objects.all()
    event_ids = ""
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            exchanges = Exchange.objects.financial_contributions(start, end)
        else:
            exchanges = Exchange.objects.financial_contributions()
        selected_values = request.POST["categories"]
        if selected_values:
            sv = selected_values.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                events_included = []
                exchanges_included = []
                for ex in exchanges:
                    for event in ex.events.all():
                        if event.resource_type.accounting_reference:
                            if event.resource_type.accounting_reference.code in vals:
                                #if ex.class_label() == "Exchange":
                                events_included.append(event)
                                #else: #process
                                #    if event.event_type == et_process_expense:
                                #        events_included.append(event)
                    if events_included != []:
                        ex.event_list = events_included
                        exchanges_included.append(ex)
                        events_included = []
                exchanges = exchanges_included
    else:
        exchanges = Exchange.objects.financial_contributions(start, end)

    total_cash = 0
    total_receipts = 0
    total_expenses = 0
    total_payments = 0
    comma = ""
    for x in exchanges:
        try:
            xx = x.event_list
        except AttributeError:
            #if x.class_label() == "Exchange":
            x.event_list = x.events.all()
            #else: #process
            #    evs = x.events.all()
            #    event_list = []
            #   for event in evs:
            #        if event.event_type == et_process_expense:
            #            event_list.append(event)
            #    x.event_list = event_list
        for event in x.event_list:
            if event.event_type == et_pay:
                total_payments = total_payments + event.quantity
            elif event.event_type == et_cash:
                total_cash = total_cash + event.quantity
            elif event.event_type == et_donation:
                total_cash = total_cash + event.quantity
            elif event.event_type == et_expense:
                total_expenses = total_expenses + event.value
            #elif event.event_type == et_process_expense:
            #    total_expenses = total_expenses + event.value
            #    total_payments = total_payments + event.value
            elif event.event_type == et_receive:
                total_receipts = total_receipts + event.value
            event_ids = event_ids + comma + str(event.id)
            comma = ","

    return render(request, "valueaccounting/exchanges.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "total_cash": total_cash,
        "total_receipts": total_receipts,
        "total_expenses": total_expenses,
        "total_payments": total_payments,
        "select_all": select_all,
        "selected_values": selected_values,
        "references": references,
        "event_ids": event_ids,
    })

def internal_exchanges(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    end =  today
    start = today - datetime.timedelta(days=365)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_give = EventType.objects.get(name="Give")
    et_receive = EventType.objects.get(name="Receive")
    #references = AccountingReference.objects.all()
    ets = ExchangeType.objects.internal_exchange_types()
    event_ids = ""
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            exchanges = Exchange.objects.internal_exchanges(start, end)
        else:
            exchanges = Exchange.objects.internal_exchanges()
        if agent_id:
            exchanges = exchanges.filter(context_agent=agent)
        selected_values = request.POST["categories"]
        if selected_values:
            sv = selected_values.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                transfers_included = []
                exchanges_included = []
                events_included = []
                for ex in exchanges:
                    if str(ex.exchange_type.id) in vals:
                        exchanges_included.append(ex)
                exchanges = exchanges_included
    else:
        if agent_id:
            exchanges = Exchange.objects.internal_exchanges(start, end).filter(context_agent=agent)
        else:
            exchanges = Exchange.objects.internal_exchanges(start, end)

    total_transfers = 0
    total_rec_transfers = 0
    comma = ""
    for x in exchanges:
        try:
            xx = list(x.transfer_list)
        except AttributeError:
            x.transfer_list = list(x.transfers.all())
        for transfer in x.transfer_list:
            if not transfer.transfer_type.is_reciprocal:
                total_transfers = total_transfers + transfer.quantity()
            else:
                total_rec_transfers = total_rec_transfers + transfer.quantity()
            for event in transfer.events.all():
                event_ids = event_ids + comma + str(event.id)
                comma = ","
        for event in x.events.all():
            event_ids = event_ids + comma + str(event.id)
            comma = ","
        #todo: get sort to work


    return render(request, "valueaccounting/internal_exchanges.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "total_transfers": total_transfers,
        "total_rec_transfers": total_rec_transfers,
        "select_all": select_all,
        "selected_values": selected_values,
        #"references": references,
        "ets": ets,
        "event_ids": event_ids,
        "agent": agent,
    })

#obsolete
def material_contributions(request):
    end = datetime.date.today()
    start = datetime.date(end.year, 1, 1)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_matl = EventType.objects.get(name="Resource Contribution")
    event_ids = ""
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            exchanges = Exchange.objects.material_contributions().filter(start_date__range=[start, end])
        else:
            exchanges = Exchange.objects.material_contributions()
    else:
        exchanges = Exchange.objects.material_contributions().filter(start_date__range=[start, end])

    comma = ""
    for x in exchanges:
        try:
            xx = x.event_list
        except AttributeError:
            x.event_list = x.events.all()
        for event in x.event_list:
            event_ids = event_ids + comma + str(event.id)
            comma = ","

    return render(request, "valueaccounting/material_contributions.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "event_ids": event_ids,
    })

def demand_exchanges(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    end =  today
    start = today - datetime.timedelta(days=365)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_give = EventType.objects.get(name="Give")
    et_receive = EventType.objects.get(name="Receive")
    #references = AccountingReference.objects.all()
    ets = ExchangeType.objects.demand_exchange_types()
    event_ids = ""
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            exchanges = Exchange.objects.demand_exchanges(start, end)
        else:
            exchanges = Exchange.objects.demand_exchanges()
        if agent_id:
            exchanges = exchanges.filter(context_agent=agent)
        selected_values = request.POST["categories"]
        if selected_values:
            sv = selected_values.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                transfers_included = []
                exchanges_included = []
                events_included = []
                for ex in exchanges:
                    if str(ex.exchange_type.id) in vals:
                        exchanges_included.append(ex)
                exchanges = exchanges_included
    else:
        if agent_id:
            exchanges = Exchange.objects.demand_exchanges(start, end).filter(context_agent=agent)
        else:
            exchanges = Exchange.objects.demand_exchanges(start, end)

    total_transfers = 0
    total_rec_transfers = 0
    comma = ""
    for x in exchanges:
        try:
            xx = list(x.transfer_list)
        except AttributeError:
            x.transfer_list = list(x.transfers.all())
        for transfer in x.transfer_list:
            if not transfer.transfer_type.is_reciprocal:
                total_transfers = total_transfers + transfer.quantity()
            else:
                total_rec_transfers = total_rec_transfers + transfer.quantity()
            for event in transfer.events.all():
                event_ids = event_ids + comma + str(event.id)
                comma = ","
        for event in x.events.all():
            event_ids = event_ids + comma + str(event.id)
            comma = ","
        #todo: get sort to work


    return render(request, "valueaccounting/demand_exchanges.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "total_transfers": total_transfers,
        "total_rec_transfers": total_rec_transfers,
        "select_all": select_all,
        "selected_values": selected_values,
        #"references": references,
        "ets": ets,
        "event_ids": event_ids,
        "agent": agent,
    })

#obsolete
def sales_and_distributions(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    end =  today + datetime.timedelta(days=90)
    start = datetime.date(today.year, 1, 1)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_cash_receipt = EventType.objects.get(name="Cash Receipt")
    et_shipment = EventType.objects.get(name="Shipment")
    et_distribution = EventType.objects.get(name="Distribution")
    references = AccountingReference.objects.all()
    event_ids = ""
    select_all = True
    selected_values = "all"
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            exchanges = Exchange.objects.sales_and_distributions().filter(start_date__range=[start, end])
        else:
            exchanges = Exchange.objects.sales_and_distributions()
        if agent_id:
            exchanges = exchanges.filter(context_agent=agent)
        selected_values = request.POST["categories"]
        if selected_values:
            sv = selected_values.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                events_included = []
                exchanges_included = []
                for ex in exchanges:
                    for event in ex.events.all():
                        if event.resource_type.accounting_reference:
                            if event.resource_type.accounting_reference.code in vals:
                                events_included.append(event)
                    if events_included != []:
                        ex.event_list = events_included
                        exchanges_included.append(ex)
                        events_included = []
                exchanges = exchanges_included
    else:
        if agent_id:
            exchanges = Exchange.objects.sales_and_distributions().filter(start_date__range=[start, end]).filter(context_agent=agent)
        else:
            exchanges = Exchange.objects.sales_and_distributions().filter(start_date__range=[start, end])

    total_cash_receipts = 0
    total_shipments = 0
    total_distributions = 0
    comma = ""
    for x in exchanges:
        try:
            xx = x.event_list
        except AttributeError:
            x.event_list = x.events.all()
        for event in x.event_list:
            if event.event_type == et_cash_receipt:
                total_cash_receipts = total_cash_receipts + event.quantity
            elif event.event_type == et_shipment:
                total_shipments = total_shipments + event.value
            elif event.event_type == et_distribution:
                total_distributions = total_distributions + event.quantity
            event_ids = event_ids + comma + str(event.id)
            comma = ","

    return render(request, "valueaccounting/sales_and_distributions.html", {
        "exchanges": exchanges,
        "dt_selection_form": dt_selection_form,
        "total_cash_receipts": total_cash_receipts,
        "total_shipments": total_shipments,
        "total_distributions": total_distributions,
        "select_all": select_all,
        "selected_values": selected_values,
        "references": references,
        "event_ids": event_ids,
        "agent": agent,
    })

def distributions(request, agent_id=None):
    agent = None
    if agent_id:
        agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    user_agent = get_agent(request)
    end =  today + datetime.timedelta(days=5)
    start = datetime.date(today.year, 1, 1)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    event_ids = ""
    distributions = Distribution.objects.filter(distribution_date__range=[start, end])
    if agent_id:
        distributions = distributions.filter(context_agent=agent)
    if request.method == "POST":
        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            distributions = Distribution.objects.filter(distribution_date__range=[start, end])
        else:
            distributions = Distribution.objects.all()
        if agent_id:
            distributions = distributions.filter(context_agent=agent)

    total_distributions = 0
    comma = ""
    for dist in distributions:
        try:
            dist_el = dist.event_list
        except AttributeError:
            dist.event_list = dist.events.all()
        for event in dist.event_list:
            total_distributions = total_distributions + event.quantity
            event_ids = event_ids + comma + str(event.id)
            comma = ","

    return render(request, "valueaccounting/distributions.html", {
        "distributions": distributions,
        "dt_selection_form": dt_selection_form,
        "total_distributions": total_distributions,
        "event_ids": event_ids,
        "agent": agent,
        "user_agent": user_agent,
    })

@login_required
def exchange_events_csv(request):
    event_ids = request.GET.get("event-ids")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=contributions.csv'
    writer = csv.writer(response)
    writer.writerow(["Exchange Type", "Exchange ID", "Transfer Type", "Transfer ID", "Event ID", "Date", "Event Type", "Resource Type", "Quantity", "Unit of Quantity", "Value", "Unit of Value", "From Agent", "To Agent", "Project", "Description", "URL"])
    event_ids_split = event_ids.split(",")
    for event_id in event_ids_split:
        event = EconomicEvent.objects.get(pk=event_id)
        if event.from_agent == None:
            from_agent = ""
        else:
            from_agent = event.from_agent.nick
        if event.to_agent == None:
            to_agent = ""
        else:
            to_agent = event.to_agent.nick
        if event.url == "":
            if event.transfer:
                if event.transfer.exchange.url == "":
                    url = ""
                else:
                    url = event.transfer.exchange.url
            else:
                if event.exchange.url == "":
                    url = ""
                else:
                    url = event.exchange.url
        else:
            url = ""
        if event.exchange:
            exchange_name = event.exchange.exchange_type.name
            exchange_id = event.exchange.id
        else:
            exchange_name = ""
            exchange_id = ""
        if event.transfer:
            transfer_name = event.transfer.transfer_type.name
            transfer_id = event.transfer.id
            exchange_name = event.transfer.exchange.exchange_type.name
            exchange_id = event.transfer.exchange.id
        else:
            transfer_name = ""
            transfer_id = ""
        writer.writerow(
            [exchange_name,
             exchange_id,
             transfer_name,
             transfer_id,
             event.id,
             event.event_date,
             event.event_type.name,
             event.resource_type.name,
             event.quantity,
             event.unit_of_quantity,
             event.value,
             event.unit_of_value,
             from_agent,
             to_agent,
             event.context_agent.name,
             event.description,
             url,
            ]
        )
    return response


@login_required
def contribution_events_csv(request):
    event_ids = request.GET.get("event-ids")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=contributions.csv'
    writer = csv.writer(response)
    #writer.writerow(["Date", "Event Type", "Resource Type", "Quantity", "Unit of Quantity", "Value", "Unit of Value", "From Agent", "To Agent", "Project", "Description", "URL", "Use Case", "Event ID", "Exchange ID"])
    event_ids_split = event_ids.split(",")
    queryset = EconomicEvent.objects.filter(id__in=event_ids_split)
    opts = EconomicEvent._meta
    field_names = [field.name for field in opts.fields]
    writer.writerow(field_names)
    for obj in queryset:
        row = []
        for field in field_names:
            x = getattr(obj, field)
            try:
                x = x.encode('latin-1', 'replace')
            except AttributeError:
                pass
            row.append(x)
        writer.writerow(row)

    return response


def exchange_logging(request, exchange_type_id=None, exchange_id=None, context_agent_id=None):
    agent = get_agent(request)
    logger = False
    add_work_form = None
    if agent:
        if request.user.is_superuser:
            logger = True

    if exchange_type_id != "0": #new exchange
        if agent:
            exchange_type = get_object_or_404(ExchangeType, id=exchange_type_id)
            use_case = exchange_type.use_case

            if request.method == "POST":
                exchange_form = ExchangeForm(data=request.POST)
                if exchange_form.is_valid():
                    exchange = exchange_form.save(commit=False)
                    exchange.use_case = use_case
                    exchange.exchange_type = exchange_type
                    exchange.created_by = request.user
                    exchange.save()

                    return HttpResponseRedirect('/%s/%s/%s/'
                        % ('accounting/exchange', 0, exchange.id))

            if context_agent_id:
                context_agent = EconomicAgent.objects.get(id=context_agent_id)
                init = { "context_agent": context_agent }
                exchange_form = ExchangeForm(initial=init)
            else:
                exchange_form = ExchangeForm()
            slots = exchange_type.slots()
            return render(request, "valueaccounting/exchange_logging.html", {
                "use_case": use_case,
                "exchange_type": exchange_type,
                "exchange_form": exchange_form,
                "agent": agent,
                "user": request.user,
                "logger": logger,
                "slots": slots,
                "total_t": 0,
                "total_rect": 0,
                "help": get_help("exchange"),
            })
        else:
            raise ValidationError("System Error: No agent, not allowed to create exchange.")

    elif exchange_id != "0": #existing exchange
        exchange = get_object_or_404(Exchange, id=exchange_id)

        if request.method == "POST":
            exchange_form = ExchangeForm(instance=exchange, data=request.POST)
            if exchange_form.is_valid():
                exchange = exchange_form.save()
                return HttpResponseRedirect('/%s/%s/%s/'
                    % ('accounting/exchange', 0, exchange.id))

        context_agent = exchange.context_agent
        exchange_type = exchange.exchange_type
        use_case = exchange_type.use_case
        exchange_form = ExchangeForm(instance=exchange)

        slots = []
        total_t = 0
        total_rect = 0
        work_events = exchange.work_events()
        slots = exchange.slots_with_detail()

        for slot in slots:
            if slot.is_reciprocal:
                total_rect = total_rect + slot.total
            else:
                total_t = total_t + slot.total

        if agent:
            if request.user == exchange.created_by:
                logger = True

            for event in work_events:
                event.changeform = WorkEventAgentForm(
                    context_agent=context_agent,
                    instance=event,
                    prefix=str(event.id))
            work_init = {
                "from_agent": agent,
                "event_date": datetime.date.today()
            }
            add_work_form = WorkEventAgentForm(initial=work_init, context_agent=context_agent)

            for slot in slots:
                ta_init = slot.default_to_agent
                fa_init = slot.default_from_agent
                if not ta_init:
                    ta_init = agent
                if not fa_init:
                    fa_init = agent
                xfer_init = {
                    "from_agent": fa_init,
                    "to_agent": ta_init,
                    "event_date": datetime.date.today()
                }
                slot.add_xfer_form = TransferForm(initial=xfer_init, prefix="ATR" + str(slot.id), context_agent=context_agent, transfer_type=slot)
                slot.create_role_formset = resource_role_agent_formset(prefix=str(slot.id))
                commit_init = {
                    "from_agent": fa_init,
                    "to_agent": ta_init,
                    "commitment_date": datetime.date.today(),
                    "due_date": exchange.start_date,
                }
                slot.add_commit_form = TransferCommitmentForm(initial=commit_init, prefix="ACM" + str(slot.id), context_agent=context_agent, transfer_type=slot)

    else:
        raise ValidationError("System Error: No exchange or use case.")

    return render(request, "valueaccounting/exchange_logging.html", {
        "use_case": use_case,
        "exchange": exchange,
        "exchange_type": exchange_type,
        "exchange_form": exchange_form,
        "agent": agent,
        "context_agent": context_agent,
        "logger": logger,
        "slots": slots,
        "work_events": work_events,
        "add_work_form": add_work_form,
        "total_t": total_t,
        "total_rect": total_rect,
        "help": get_help("exchange"),
    })

'''
def exchange_logging_old(request, exchange_id):
    agent = get_agent(request)
    logger = False
    exchange = get_object_or_404(Exchange, id=exchange_id)
    use_case = exchange.use_case
    context_agent = exchange.context_agent
    pattern = exchange.process_pattern
    if use_case.identifier == "sale":
        exchange_form = SaleForm(context_agent, instance=exchange, data=request.POST or None)
    elif use_case.identifier == "distribution":
        exchange_form = DistributionForm(instance=exchange, data=request.POST or None)
    else:
        exchange_form = ExchangeForm(use_case, context_agent, instance=exchange, data=request.POST or None)
    add_receipt_form = None
    add_to_resource_form = None
    add_to_contr_resource_form = None
    add_payment_form = None
    add_expense_form = None
    add_material_form = None
    add_cash_form = None
    add_cash_resource_form = None
    add_work_form = None
    add_cash_receipt_form = None
    add_cash_receipt_resource_form = None
    add_shipment_form = None
    add_distribution_form = None
    add_disbursement_form = None
    add_uninventoried_shipment_form = None
    create_material_role_formset = None
    create_receipt_role_formset = None
    #add_commit_receipt_form = None
    #add_commit_payment_form = None
    slots = []
    expense_total = 0
    receipt_total = 0
    cash_receipt_total = 0
    purchase_total = 0
    cash_contr_total = 0
    matl_contr_total = 0
    shipment_total = 0
    payment_total = 0
    disburse_total = 0
    distribution_total = 0
    fee_total = 0
    transfer_total = 0
    total_in = 0
    total_out = 0
    shipped_ids = []

    #receipt_commitments = exchange.receipt_commitments()
    #payment_commitments = exchange.payment_commitments()
    shipment_commitments = exchange.shipment_commitments()
    cash_receipt_commitments = exchange.cash_receipt_commitments()
    receipt_events = exchange.receipt_events()
    payment_events = exchange.payment_events()
    expense_events = exchange.expense_events()
    work_events = exchange.work_events()
    cash_events = exchange.cash_events()
    material_events = exchange.material_contribution_events()
    cash_receipt_events = exchange.cash_receipt_events()
    shipment_events = exchange.shipment_events_no_commitment()
    distribution_events = exchange.distribution_events()
    disbursement_events = exchange.disbursement_events()
    fee_events = exchange.fee_events()
    transfer_events = exchange.transfer_events()

    if agent and pattern:
        slots = pattern.slots()
        if request.user.is_superuser or request.user == exchange.created_by:
            logger = True
        #for req in receipt_commitments:
        #    req.changeform = req.change_form()
        #for req in payment_commitments:
        #    req.changeform = req.change_form()
        for event in payment_events:
            total_out = total_out + event.quantity
            payment_total = payment_total + event.quantity
            event.changeform = PaymentEventForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        for event in expense_events:
            expense_total = expense_total + event.value
            total_in = total_in + event.value
            event.changeform = ExpenseEventForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        for event in work_events:
            event.changeform = WorkEventAgentForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        for event in receipt_events:
            receipt_total = receipt_total + event.value
            total_in = total_in + event.value
            event.changeform = UnorderedReceiptForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        for event in cash_receipt_events:
            total_in = total_in + event.quantity
            cash_receipt_total = cash_receipt_total + event.quantity
            event.changeform = CashReceiptForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        for event in shipment_events:
            total_out = total_out + event.value
            shipment_total = shipment_total + event.value
            if event.resource:
                event.changeform = ShipmentForm(
                    pattern=pattern,
                    context_agent=context_agent,
                    instance=event,
                    prefix=str(event.id))
            else:
                event.changeform = UninventoriedShipmentForm(
                    pattern=pattern,
                    context_agent=context_agent,
                    instance=event,
                    prefix=str(event.id))
        for event in distribution_events:
            total_out = total_out + event.quantity
            distribution_total = distribution_total + event.quantity
            event.changeform = DistributionEventForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id))
        for event in disbursement_events:
            total_in = total_in + event.quantity
            disburse_total = disburse_total + event.quantity
            event.changeform = DisbursementEventForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id))
        for event in cash_events:
            total_in = total_in + event.value
            cash_contr_total = cash_contr_total + event.value
            #event.changeform = CashEventForm(
            #    pattern=pattern,
            #    instance=event,
            #    prefix=str(event.id))
        for event in material_events:
            total_in = total_in + event.value
            matl_contr_total = matl_contr_total + event.value
        for event in fee_events:
            total_out = total_out + event.value
            fee_total = fee_total + event.value
        for event in transfer_events:
            total_out = total_out + event.value
            shipment_total = shipment_total + event.value #todo: transfers will become their own slot
        #for event in cash_events:
        #    event.changeform = CashContributionEventForm(
        #        pattern=pattern,
        #        instance=event,
        #       prefix=str(event.id))
        #for event in material_events:
        #    event.changeform = MaterialContributionEventForm(
        #        pattern=pattern,
        #        instance=event,
        #        prefix=str(event.id))

        if "pay" in slots:
            pay_init = {
                "from_agent": agent,
                "to_agent": exchange.supplier,
                "event_date": exchange.start_date
            }
            add_payment_form = PaymentEventForm(prefix='pay', initial=pay_init, pattern=pattern, context_agent=context_agent)
        if "expense" in slots:
            expense_init = {
                "from_agent": exchange.supplier,
                "event_date": exchange.start_date,
            }
            add_expense_form = ExpenseEventForm(prefix='expense', initial=expense_init, pattern=pattern, context_agent=context_agent)
        if "work" in slots:
            work_init = {
                "from_agent": agent,
                "event_date": exchange.start_date
            }
            add_work_form = WorkEventAgentForm(prefix='work', initial=work_init, pattern=pattern, context_agent=context_agent)
        if "receive" in slots:
            receipt_init = {
                "event_date": exchange.start_date,
                "from_agent": exchange.supplier
            }
            add_receipt_form = UnorderedReceiptForm(prefix='unorderedreceipt', initial=receipt_init, pattern=pattern, context_agent=context_agent)
            create_receipt_role_formset = resource_role_agent_formset(prefix='receiptrole')
            add_to_resource_form = SelectResourceOfTypeForm(prefix='addtoresource', pattern=pattern)
        if "cash" in slots:
            cash_init = {
                "event_date": exchange.start_date,
                "from_agent": agent
            }
            add_cash_form = CashContributionEventForm(prefix='cash', initial=cash_init, pattern=pattern, context_agent=context_agent)
            add_cash_resource_form = CashContributionResourceEventForm(prefix='cashres', initial=cash_init, pattern=pattern, context_agent=context_agent)
        if "resource" in slots:
            matl_init = {
                "event_date": exchange.start_date,
                "from_agent": agent
            }
            add_material_form = MaterialContributionEventForm(prefix='material', initial=matl_init, pattern=pattern, context_agent=context_agent)
            create_material_role_formset = resource_role_agent_formset(prefix='materialrole')
            add_to_contr_resource_form = SelectContrResourceOfTypeForm(prefix='addtoresource', initial=matl_init, pattern=pattern)
        if "receivecash" in slots:
            cr_init = {
                "event_date": exchange.start_date,
                "to_agent": context_agent,
            }
            add_cash_receipt_form = CashReceiptForm(prefix='cr', initial=cr_init, pattern=pattern, context_agent=context_agent)
            add_cash_receipt_resource_form = CashReceiptResourceForm(prefix='crr', initial=cr_init, pattern=pattern, context_agent=context_agent)
        if "shipment" in slots:
            ship_init = {
                "event_date": exchange.start_date,
                "from_agent": context_agent,
            }
            add_shipment_form = ShipmentForm(prefix='ship', initial=ship_init, pattern=pattern, context_agent=context_agent)
            add_uninventoried_shipment_form = UninventoriedShipmentForm(prefix='shipun', initial=ship_init, pattern=pattern, context_agent=context_agent)
            shipped_ids = [c.resource.id for c in exchange.shipment_events() if c.resource]
        if "distribute" in slots:
            dist_init = {
                "event_date": exchange.start_date,
            }
            add_distribution_form = DistributionEventForm(prefix='dist', initial=dist_init, pattern=pattern)
        if "disburse" in slots:
            disb_init = {
                "event_date": exchange.start_date,
            }
            add_disbursement_form = DisbursementEventForm(prefix='disb', initial=disb_init, pattern=pattern)

    if request.method == "POST":
        if exchange_form.is_valid():
            exchange = exchange_form.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/exchange', exchange.id))

    return render(request, "valueaccounting/exchange_logging.html", {
        "use_case": use_case,
        "exchange": exchange,
        "exchange_form": exchange_form,
        "agent": agent,
        "user": request.user,
        "logger": logger,
        "slots": slots,
        #"receipt_commitments": receipt_commitments,
        #"payment_commitments": payment_commitments,
        "shipment_commitments": shipment_commitments,
        "cash_receipt_commitments": cash_receipt_commitments,
        "receipt_events": receipt_events,
        "payment_events": payment_events,
        "expense_events": expense_events,
        "work_events": work_events,
        "cash_events": cash_events,
        "cash_receipt_events": cash_receipt_events,
        "distribution_events": distribution_events,
        "disbursement_events": disbursement_events,
        "shipment_events": shipment_events,
        "material_events": material_events,
        "fee_events": fee_events,
        "transfer_events": transfer_events,
        "add_receipt_form": add_receipt_form,
        "add_to_resource_form": add_to_resource_form,
        "add_to_contr_resource_form": add_to_contr_resource_form,
        "add_payment_form": add_payment_form,
        "add_expense_form": add_expense_form,
        "add_material_form": add_material_form,
        "add_cash_form": add_cash_form,
        "add_cash_resource_form": add_cash_resource_form,
        "add_cash_receipt_form": add_cash_receipt_form,
        "add_cash_receipt_resource_form": add_cash_receipt_resource_form,
        "add_shipment_form": add_shipment_form,
        "add_uninventoried_shipment_form": add_uninventoried_shipment_form,
        "add_distribution_form": add_distribution_form,
        "add_disbursement_form": add_disbursement_form,
        "add_work_form": add_work_form,
        "create_material_role_formset": create_material_role_formset,
        "create_receipt_role_formset": create_receipt_role_formset,
        #"add_commit_receipt_form": add_commit_receipt_form,
        #"add_commit_payment_form": add_commit_payment_form,
        "expense_total": expense_total,
        "receipt_total": receipt_total,
        "cash_receipt_total": cash_receipt_total,
        "purchase_total": purchase_total,
        "cash_contr_total": cash_contr_total,
        "matl_contr_total": matl_contr_total,
        "shipment_total": shipment_total,
        "payment_total": payment_total,
        "disburse_total": disburse_total,
        "distribution_total": distribution_total,
        "fee_total": fee_total,
        "transfer_total": transfer_total,
        "total_in": total_in,
        "total_out": total_out,
        "shipped_ids": shipped_ids,
        "help": get_help("exchange"),
    })

#obsolete
@login_required
def create_exchange(request, use_case_identifier):
    use_case = get_object_or_404(UseCase, identifier=use_case_identifier)
    context_agent = None
    context_types = AgentType.objects.context_types_string()
    context_agents = EconomicAgent.objects.context_agents() or None
    if context_agents:
        context_agent = context_agents[0]
    exchange_form = ExchangeForm(use_case, context_agent)
    if request.method == "POST":
        ca_id = request.POST.get("context_agent")
        context_agent = EconomicAgent.objects.get(id=ca_id)
        exchange_form = ExchangeForm(use_case, context_agent, data=request.POST)
        if exchange_form.is_valid():
            exchange = exchange_form.save(commit=False)
            exchange.use_case = use_case
            exchange.created_by = request.user
            exchange.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/exchange', exchange.id))
    return render(request, "valueaccounting/create_exchange.html", {
        "exchange_form": exchange_form,
        "use_case": use_case,
        "context_agent": context_agent,
        "context_types": context_types,
        "help": get_help("create_exchange"),
    })

#obsolete
@login_required
def create_sale(request):
    context_agent = None
    context_types = AgentType.objects.context_types_string()
    context_agents = EconomicAgent.objects.context_agents() or None
    if context_agents:
        context_agent = context_agents[0]
    exchange_form = SaleForm(context_agent=context_agent)
    if request.method == "POST":
        ca_id = request.POST.get("context_agent")
        context_agent = EconomicAgent.objects.get(id=ca_id)
        exchange_form = SaleForm(context_agent=context_agent, data=request.POST)
        if exchange_form.is_valid():
            exchange = exchange_form.save(commit=False)
            exchange.use_case = UseCase.objects.get(identifier="sale")
            exchange.created_by = request.user
            exchange.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/exchange', exchange.id))
    return render(request, "valueaccounting/create_sale.html", {
        "exchange_form": exchange_form,
        "context_agent": context_agent,
        "context_types": context_types,
        "help": get_help("create_sale"),
    })

#obsolete
@login_required
def create_distribution(request, agent_id):
    if not request.user.is_staff:
        return render(request, 'valueaccounting/no_permission.html')
    context_agent = get_object_or_404(EconomicAgent, id=agent_id)
    exchange_form = DistributionForm()
    if request.method == "POST":
        exchange_form = DistributionForm(data=request.POST)
        if exchange_form.is_valid():
            exchange = exchange_form.save(commit=False)
            exchange.use_case = UseCase.objects.get(identifier="distribution")
            exchange.context_agent = context_agent
            exchange.created_by = request.user
            exchange.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/exchange', exchange.id))
    return render(request, "valueaccounting/create_distribution.html", {
        "exchange_form": exchange_form,
        "context_agent": context_agent,
        "help": get_help("create_distribution"),
    })
'''

def distribution_logging(request, distribution_id=None):
    agent = get_agent(request)
    if not agent:
        if not distribution_id:
            return render(request, 'valueaccounting/no_permission.html')
    logger = False
    if agent:
        if request.user.is_superuser:
            logger = True
    pattern = None
    use_case = UseCase.objects.get(identifier="distribution")
    patterns = ProcessPattern.objects.usecase_patterns(use_case)
    if patterns:
        pattern = patterns[0]
    dist = None
    total_disb = 0
    total_dist = 0
    add_distribution_form = None
    add_disbursement_form = None

    if not distribution_id: #new distribution
        if agent:
            if request.method == "POST":
                main_form = DistributionForm(data=request.POST)
                if main_form.is_valid():
                    dist = main_form.save(commit=False)
                    dist.process_pattern = pattern
                    dist.created_by = request.user
                    dist.save()
                    return HttpResponseRedirect('/%s/%s/'
                        % ('accounting/distribution', dist.id))

            main_form = DistributionForm()

        else:
            raise ValidationError("System Error: No agent, not allowed to create distribution.")

    else: #existing distribution
        dist = get_object_or_404(Distribution, id=distribution_id)

        if request.method == "POST":
            main_form = DistributionForm(instance=dist, data=request.POST)
            if main_form.is_valid():
                dist = main_form.save()
                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/distribution', dist.id))

        main_form = DistributionForm(instance=dist)
        dist_init = {
            "event_date": dist.distribution_date,
        }
        add_distribution_form = DistributionEventForm(prefix='dist', initial=dist_init, pattern=pattern)
        disb_init = {
            "event_date": dist.distribution_date,
        }
        add_disbursement_form = DisbursementEventForm(prefix='disb', initial=disb_init, pattern=pattern)

    return render(request, "valueaccounting/distribution_logging.html", {
        "main_form": main_form,
        "dist": dist,
        "agent": agent,
        "logger": logger,
        "add_distribution_form": add_distribution_form,
        "add_disbursement_form": add_disbursement_form,
        "help": get_help("distribution_logging"),
    })

@login_required
def create_distribution_using_value_equation(request, agent_id, value_equation_id=None):
    #start_time = time.time()
    if not request.user.is_staff:
        return render(request, 'valueaccounting/no_permission.html')
    context_agent = get_object_or_404(EconomicAgent, id=agent_id)
    if value_equation_id:
        ve = ValueEquation.objects.get(id=value_equation_id)
    else:
        ve = None
    buckets = []
    use_case = UseCase.objects.get(identifier="distribution")
    pattern = None
    patts = ProcessPattern.objects.usecase_patterns(use_case)
    if patts:
        pattern = patts[0]
    agent_totals = None
    events_to_distribute = {}
    no_totals = None
    if request.method == "POST":
        header_form = DistributionValueEquationForm(context_agent=context_agent, pattern=pattern, post=True, data=request.POST)
        if header_form.is_valid():
            data = header_form.cleaned_data
            ve = data["value_equation"]
            amount = data["money_to_distribute"]
            resource = data["resource"]
            etd = data["events_to_distribute"]
            partial = data["partial_distribution"]
            if etd:
                resource = etd[0].resource
                amount = 0
                if len(etd) == 1:
                    if partial:
                        amount= partial
                    else:
                        amount = etd[0].quantity
                else:
                    for cr in etd:
                        amount += cr.quantity
            dist_date = data["start_date"]
            notes = data["notes"]
            serialized_filters = {}
            buckets = ve.buckets.all()
            for bucket in buckets:
                if bucket.filter_method:
                    bucket_form = bucket.filter_entry_form(data=request.POST or None)
                    if bucket_form.is_valid():
                        ser_string = bucket_data = bucket_form.serialize()
                        serialized_filters[bucket.id] = ser_string
                        bucket.form = bucket_form

            test_only = request.POST.get("test-only")
            if test_only:
                agent_totals, contribution_events = ve.run_value_equation(
                    amount_to_distribute=amount,
                    serialized_filters=serialized_filters)
                if not agent_totals:
                    no_totals = "No contributions found."

            else:
                distribution = Distribution(
                    name="Distribution for " + context_agent.nick,
                    process_pattern=pattern,
                    distribution_date=dist_date,
                    notes=notes,
                    context_agent=context_agent,
                    created_by=request.user,
                )
                #exchange.save()

                distribution = ve.run_value_equation_and_save(
                    events_to_distribute=etd,
                    distribution=distribution,
                    money_resource=resource,
                    amount_to_distribute=amount,
                    serialized_filters=serialized_filters)
                for event in distribution.distribution_events():
                    send_distribution_notification(event)

                return HttpResponseRedirect('/%s/%s/'
                    % ('accounting/distribution', distribution.id))

    else:
        ves = context_agent.live_value_equations()
        init = { "start_date": datetime.date.today(), "value_equation": ve }
        header_form = DistributionValueEquationForm(context_agent=context_agent, pattern=pattern, post=False, initial=init)
        etd = context_agent.undistributed_events()
        for ev in etd:
            events_to_distribute[ev.id] = float(ev.undistributed_amount())
        if ves:
            if not ve:
                ve = ves[0]
            buckets = ve.buckets.all()
            for bucket in buckets:
                if bucket.filter_method:
                    bucket.form = bucket.filter_entry_form()
    #end_time = time.time()
    #print("views.create_distribution_using_value_equation elapsed time was %g seconds" % (end_time - start_time))
    return render(request, "valueaccounting/create_distribution_using_value_equation.html", {
        "events_to_distribute": events_to_distribute,
        "header_form": header_form,
        "buckets": buckets,
        "ve": ve,
        "context_agent": context_agent,
        "agent_totals": agent_totals,
        "no_totals": no_totals,
        "help": get_help("create_distribution"),
    })


def send_distribution_notification(distribution_event):
    if notification:
        to_agent = distribution_event.to_agent
        users =  users = [au.user for au in to_agent.users.all()]
        site_name = get_site_name()
        if users:
            notification.send(
                users,
                "valnet_distribution",
                {"distribution": distribution_event,
                "account": distribution_event.resource,
                "site_name": site_name,
                }
            )

'''
#todo: this is not tested, is for exchange
@login_required
def payment_event_for_commitment(request):
    id = request.POST.get("id")
    resource_id = request.POST.get("resourceId")
    cited = int(request.POST.get("cited"))
    event_date = request.POST.get("eventDate")
    if event_date:
        event_date = datetime.datetime.strptime(event_date, '%Y-%m-%d').date()
    else:
        event_date = datetime.date.today()
    ct = get_object_or_404(Commitment, pk=id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    agent = get_agent(request)
    quantity = Decimal("1")
    event = None
    events = ct.fulfillment_events.filter(resource=resource)
    if events:
        event = events[events.count() - 1]
    if event:
        if not cited:
            event.delete()
    else:
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = ct.event_type,
            from_agent = agent,
            resource_type = ct.resource_type,
            process = ct.process,
            project = ct.project,
            quantity = quantity,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()

    data = "ok"
    return HttpResponse(data, content_type="text/plain")
'''

#demo page for DHEN
#@login_required
def resource_flow(request):
    pattern = ProcessPattern.objects.get(name="Change")
    resource_form = ResourceFlowForm(pattern=pattern)
    role_formset = resource_role_agent_formset(prefix='role')

    return render(request, "valueaccounting/resource_flow.html", {
        "resource_form": resource_form,
        "role_formset": role_formset,
    })

#demo page for DHEN and GT
#@login_required
def workflow_board_demo(request):
    pattern = ProcessPattern.objects.get(name="Change")
    resource_form = ResourceFlowForm(pattern=pattern)
    process_form = PlanProcessForm()

    return render(request, "valueaccounting/workflow_board_demo.html", {
        "resource_form": resource_form,
        "process_form": process_form,
    })

#demo page for DHEN
#@login_required
def inventory_board_demo(request):
    pattern = ProcessPattern.objects.get(name="Change")
    resource_form = ResourceFlowForm(pattern=pattern)
    process_form = PlanProcessForm()
    move_harvester_form = ExchangeFlowForm()
    move_dryer_form = ExchangeFlowForm()
    move_seller_form = ExchangeFlowForm()

    return render(request, "valueaccounting/inventory_board_demo.html", {
        "resource_form": resource_form,
        "process_form": process_form,
        "move_harvester_form": move_harvester_form,
        "move_dryer_form": move_dryer_form,
        "move_seller_form": move_seller_form,
    })

def lots(request):


    return render(request, "valueaccounting/lots.html", {
        "resource_form": resource_form,
        "process_form": process_form,
    })

#@login_required
def bucket_filter_header(request):
    header_form = FilterSetHeaderForm(data=request.POST or None)
    if request.method == "POST":
        if header_form.is_valid():
            data = header_form.cleaned_data
            agent = data["context"]
            event_type = data["event_type"]
            pattern = data["pattern"]
            if pattern:
                pattern_id = pattern.id
            else:
                pattern_id = 0
            filter_set = data["filter_set"]
            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                % ('accounting/bucket-filter', agent.id, event_type.id, pattern_id, filter_set))
    return render(request, "valueaccounting/bucket_filter_header.html", {
        "header_form": header_form,
    })

#@login_required
def bucket_filter(request, agent_id, event_type_id, pattern_id, filter_set):
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    event_type = get_object_or_404(EventType, pk=event_type_id)
    events = None
    pattern = None
    count = 0
    pattern_id = int(pattern_id)
    if pattern_id:
        pattern = get_object_or_404(ProcessPattern, pk=pattern_id)
    if filter_set == "Order":
        filter_form = OrderFilterSetForm(project=agent, event_type=event_type, pattern=pattern, data=request.POST or None)
    elif filter_set == "Context":
        filter_form = ProjectFilterSetForm(project=agent, event_type=event_type, pattern=pattern, data=request.POST or None)
    elif filter_set == "Delivery":
        filter_form = DeliveryFilterSetForm(project=agent, event_type=event_type, pattern=pattern, data=request.POST or None)
    if request.method == "POST":
        if filter_form.is_valid():
            s = filter_form.serialize()
            d = filter_form.deserialize(s)
            data = filter_form.cleaned_data
            process_types = data["process_types"]
            resource_types = data["resource_types"]
            if filter_set == "Order":
                order = data["order"]
                events = [e for e in order.all_events() if e.event_type==event_type]
                if process_types:
                    events = [e for e in events if e.process.process_type in process_types]
                if resource_types:
                    events = [e for e in events if e.resource_type in resource_types]
                count = len(events)
            elif filter_set == "Context":
                start_date = data["start_date"]
                end_date = data["end_date"]
                events = EconomicEvent.objects.filter(context_agent=agent, event_type=event_type)
                if start_date and end_date:
                    events = events.filter(event_date__range=(start_date, end_date))
                elif start_date:
                    events = events.filter(event_date__gte=start_date)
                elif end_date:
                    events = events.filter(event_date__gte=end_date)
                if process_types:
                    events = events.filter(process__process_type__in=process_types)
                if resource_types:
                    events = events.filter(resource_type__in=resource_types)
                count = events.count()
            elif filter_set == "Delivery":
                shipment_events = data["shipment_events"]
                lots = [e.resource for e in shipment_events]
                events = []
                for lot in lots:
                    events.extend([event for event in lot.incoming_events() if event.event_type==event_type])
                if process_types:
                    events = [e for e in events if e.process.process_type in process_types]
                if resource_types:
                    events = [e for e in events if e.resource_type in resource_types]
                count = len(events)

    return render(request, "valueaccounting/bucket_filter.html", {
        "filter_set": filter_set,
        "context_agent": agent,
        "event_type": event_type,
        "pattern": pattern,
        "filter_form": filter_form,
        "events": events,
        "count": count,
    })


class AgentSubtotal(object):
    def __init__(self, agent, bucket_rule, quantity=Decimal('0.0'), value=Decimal('0.0'), distr_amt=Decimal('0.0')):
        self.agent = agent
        self.bucket_rule = bucket_rule
        self.quantity = quantity
        self.value = value
        self.distr_amt=distr_amt

    def key(self):
        return "-".join([str(self.agent.id), str(self.bucket_rule.id)])

    def quantity_formatted(self):
        return self.quantity.quantize(Decimal('.01'), rounding=ROUND_UP)


@login_required
def value_equation_sandbox(request, value_equation_id=None):
    ve = None
    ves = ValueEquation.objects.all()
    init = {}
    if value_equation_id:
        ve = ValueEquation.objects.get(id=value_equation_id)
        init = {"value_equation": ve}
    header_form = ValueEquationSandboxForm(initial=init, data=request.POST or None)
    buckets = []
    agent_totals = []
    details = []
    total = None
    hours = None
    agent_subtotals = None
    event_count = 0
    if ves:
        if not ve:
            ve = ves[0]
        buckets = ve.buckets.all()
    if request.method == "POST":
        if header_form.is_valid():
            data = header_form.cleaned_data
            value_equation = data["value_equation"]
            amount = data["amount_to_distribute"]
            serialized_filters = {}
            for bucket in buckets:
                if bucket.filter_method:
                    bucket_form = bucket.filter_entry_form(data=request.POST or None)
                    if bucket_form.is_valid():
                        ser_string = bucket_data = bucket_form.serialize()
                        serialized_filters[bucket.id] = ser_string
                        bucket.form = bucket_form
            agent_totals, details = ve.run_value_equation(amount_to_distribute=Decimal(amount), serialized_filters=serialized_filters)
            total = sum(at.quantity for at in agent_totals)
            hours = sum(d.quantity for d in details)
            #daniel = EconomicAgent.objects.get(nick="Daniel")
            #dan_details = [d for d in details if d.from_agent==daniel]
            agent_subtotals = {}
            for d in details:
                key = "-".join([str(d.from_agent.id), str(d.vebr.id)])
                if key not in agent_subtotals:
                    agent_subtotals[key] = AgentSubtotal(d.from_agent, d.vebr)
                sub = agent_subtotals[key]
                sub.quantity += d.quantity
                try:
                    sub.value += d.share
                except AttributeError:
                    sub.value = Decimal("0.0")
                try:
                    sub.distr_amt += d.distr_amt
                except AttributeError:
                    sub.distr_amt = Decimal("0.0")
                sub.rate = 0
                if sub.distr_amt and sub.quantity:
                    sub.rate = (sub.distr_amt / sub.quantity).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            agent_subtotals = list(agent_subtotals.values())
            agent_subtotals = sorted(agent_subtotals, key=methodcaller('key'))

            details.sort(key=lambda x: x.from_agent)
            event_count = len(details)

    else:
        for bucket in buckets:
            if bucket.filter_method:
                bucket.form = bucket.filter_entry_form()

    return render(request, "valueaccounting/value_equation_sandbox.html", {
        "header_form": header_form,
        "buckets": buckets,
        "agent_totals": agent_totals,
        "details": details,
        "agent_subtotals": agent_subtotals,
        "total": total,
        "event_count": event_count,
        "hours": hours,
        "ve": ve,
    })

def json_value_equation_bucket(request, value_equation_id):
    ve = ValueEquation.objects.get(id=value_equation_id)
    bkts = ve.buckets.all()
    buckets = []
    for b in bkts:
        agent_name = "null"
        filter_method = "null"
        if b.distribution_agent:
            agent_name = b.distribution_agent.name
        if b.filter_method:
            filter_method = b.filter_method
        fields = {
            "sequence": b.sequence,
            "name": b.name,
            "percentage": b.percentage,
            "agent_name": agent_name,
            "filter_method": filter_method,
        }
        buckets.append({"fields": fields})
        json = simplejson.dumps(buckets, ensure_ascii=False)
    return HttpResponse(json, content_type='application/json')

def value_equations(request):
    value_equations = ValueEquation.objects.all()
    agent = get_agent(request)

    return render(request, "valueaccounting/value_equations.html", {
        "value_equations": value_equations,
        "agent": agent,
    })


def edit_value_equation(request, value_equation_id=None):
    value_equation = None
    value_equation_bucket_form = None
    if value_equation_id:
        value_equation = get_object_or_404(ValueEquation, id=value_equation_id)
        value_equation_form = ValueEquationForm(instance=value_equation)
        value_equation_bucket_form = ValueEquationBucketForm()
    else:
        value_equation_form = ValueEquationForm()
    agent = get_agent(request)
    test_results = []
    rpt_heading = ""
    if request.method == "POST":
        rule_id = int(request.POST['test'])
        vebr = ValueEquationBucketRule.objects.get(id=rule_id)
        tr = vebr.test_results()
        nbr = len(tr)
        if nbr > 50:
            nbr = 50
        count = 0
        while count < nbr:
            tr[count].claim_amount = vebr.compute_claim_value(tr[count])
            test_results.append(tr[count])
            count+=1
        rpt_heading = "Bucket " + str(vebr.value_equation_bucket.sequence) + " " + vebr.event_type.name

    return render(request, "valueaccounting/edit_value_equation.html", {
        "value_equation": value_equation,
        "agent": agent,
        "value_equation_form": value_equation_form,
        "value_equation_bucket_form": value_equation_bucket_form,
        "test_results": test_results,
        "rpt_heading": rpt_heading,
    })

@login_required
def create_value_equation(request):
    if request.method == "POST":
        ve_form = ValueEquationForm(data=request.POST)
        if ve_form.is_valid():
            ve = ve_form.save(commit=False)
            ve.created_by = request.user
            ve.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def change_value_equation(request, value_equation_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    if request.method == "POST":
        ve_form = ValueEquationForm(instance=ve, data=request.POST)
        if ve_form.is_valid():
            ve = ve_form.save(commit=False)
            ve.changed_by = request.user
            ve.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))


@login_required
def delete_value_equation(request, value_equation_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    ve.delete()
    return HttpResponseRedirect('/%s/'
        % ('accounting/value-equations'))


@login_required
def create_value_equation_bucket(request, value_equation_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    if request.method == "POST":
        veb_form = ValueEquationBucketForm(data=request.POST)
        if veb_form.is_valid():
            veb = veb_form.save(commit=False)
            veb.value_equation = ve
            veb.created_by = request.user
            veb.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def change_value_equation_bucket(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    if request.method == "POST":
        veb_form = ValueEquationBucketForm(prefix=str(veb.id), instance=veb, data=request.POST)
        if veb_form.is_valid():
            veb = veb_form.save(commit=False)
            veb.changed_by = request.user
            veb.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def delete_value_equation_bucket(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    veb.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def create_value_equation_bucket_rule(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    if request.method == "POST":
        vebr_form = ValueEquationBucketRuleForm(prefix=str(bucket_id), data=request.POST)
        if vebr_form.is_valid():
            vebr = vebr_form.save(commit=False)
            vebr.value_equation_bucket = veb
            vebr.created_by = request.user
            filter_form = BucketRuleFilterSetForm(context_agent=None, event_type=None, pattern=None, prefix=str(bucket_id), data=request.POST)
            if filter_form.is_valid():
                vebr.filter_rule = filter_form.serialize()
                vebr.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def change_value_equation_bucket_rule(request, rule_id):
    vebr = get_object_or_404(ValueEquationBucketRule, id=rule_id)
    ve = vebr.value_equation_bucket.value_equation
    if request.method == "POST":
        vebr_form = ValueEquationBucketRuleForm(prefix="vebr" + str(vebr.id), instance=vebr, data=request.POST)
        if vebr_form.is_valid():
            vebr = vebr_form.save(commit=False)
            vebr.changed_by = request.user
            filter_form = BucketRuleFilterSetForm(context_agent=None, event_type=None, pattern=None, prefix="vebrf" + str(rule_id), data=request.POST)
            if filter_form.is_valid():
                vebr.filter_rule = filter_form.serialize()
                vebr.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def delete_value_equation_bucket_rule(request, rule_id):
    vebr = get_object_or_404(ValueEquationBucketRule, id=rule_id)
    ve = vebr.value_equation_bucket.value_equation
    vebr.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/edit-value-equation', ve.id))

@login_required
def value_equation_live_test(request, value_equation_id):
    value_equation = get_object_or_404(ValueEquation, pk=value_equation_id)
    if not value_equation.live:
        value_equation.live = True
        value_equation.save()
        return HttpResponseRedirect('/%s/'
            % ('accounting/value-equations'))
    else:
        if value_equation.live:
            value_equation.live = False
            value_equation.save()
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/edit-value-equation', value_equation.id))


def cash_report(request):
    end = datetime.date.today()
    start = datetime.date(end.year, end.month, 1)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    starting_balance = 0
    balance_form = BalanceForm(data=request.POST or None)
    event_ids = ""
    select_all = True
    selected_vas = "all"
    external_accounts = None
    virtual_accounts = EconomicResource.objects.virtual_accounts()
    option = "S"

    if request.method == "POST":
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]
            events = EconomicEvent.objects.virtual_account_events(start_date=start, end_date=end)
        else:
            events = EconomicEvent.objects.virtual_account_events()
        if balance_form.is_valid():
            starting_balance = balance_form.cleaned_data["starting_balance"]
            if starting_balance == '' or starting_balance == None:
                starting_balance = 0
        else:
            starting_balance = 0
        option = request.POST["option"]
        selected_vas = request.POST["selected-vas"]
        if selected_vas:
            sv = selected_vas.split(",")
            vals = []
            for v in sv:
                vals.append(v.strip())
            if vals[0] == "all":
                select_all = True
            else:
                select_all = False
                events_included = []
                for event in events:
                    if str(event.resource.id) in vals:
                        events_included.append(event)
                events = events_included
    else:
        events = EconomicEvent.objects.virtual_account_events(start_date=start, end_date=end)

    in_total = 0
    out_total = 0
    comma = ""
    summary = {}
    for event in events:
        if event.creates_resources():
            event.in_out = "in"
            in_total += event.quantity
        else:
            event.in_out = "out"
            out_total += event.quantity
        if event.accounting_reference:
            event.account = event.accounting_reference.name
        else:
            event.account = event.event_type.name
        event.virtual_account = event.resource.identifier
        event_ids = event_ids + comma + str(event.id)
        comma = ","
        if event.account in summary:
            summary[event.account] = summary[event.account] + event.quantity
        else:
            summary[event.account] = event.quantity

    balance = starting_balance + in_total - out_total
    summary_list = sorted(summary.items())

    return render(request, "valueaccounting/cash_report.html", {
        "events": events,
        "summary_list": summary_list,
        "dt_selection_form": dt_selection_form,
        "balance_form": balance_form,
        "in_total": in_total,
        "out_total": out_total,
        "balance": balance,
        "virtual_accounts": virtual_accounts,
        "external_accounts": external_accounts,
        "starting_balance": starting_balance,
        "select_all": select_all,
        "selected_vas": selected_vas,
        "event_ids": event_ids,
        "option": option,
    })

@login_required
def cash_events_csv(request):
    event_ids = request.GET.get("event-ids")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=contributions.csv'
    writer = csv.writer(response)
    writer.writerow(["Date", "Event Type", "Resource Type", "Quantity", "Unit of Quantity", "Value", "Unit of Value", "From Agent", "To Agent", "Project", "Reference", "Description", "URL", "Use Case", "Event ID", "Exchange ID"])
    event_ids_split = event_ids.split(",")
    for event_id in event_ids_split:
        event = EconomicEvent.objects.get(pk=event_id)
        if event.from_agent == None:
            from_agent = ""
        else:
            from_agent = event.from_agent.nick
        if event.to_agent == None:
            to_agent = ""
        else:
            to_agent = event.to_agent.nick
        if event.url == "":
            if event.exchange.url == "":
                url = ""
            else:
                url = event.exchange.url
        else:
            url = ""
        writer.writerow(
            [event.event_date,
             event.event_type.name,
             event.resource_type.name,
             event.quantity,
             event.unit_of_quantity,
             event.value,
             event.unit_of_value,
             from_agent,
             to_agent,
             event.context_agent.name,
             event.event_reference,
             event.description,
             url,
             event.exchange.use_case,
             event.id,
             event.exchange.id
            ]
        )
    return response

def virtual_accounts(request):
    virtual_accounts = EconomicResource.objects.filter(resource_type__behavior="account")
    agent = get_agent(request)
    if agent:
        for va in virtual_accounts:
            va.payout = va.allow_payout_by(agent, request.user)

    return render(request, "valueaccounting/virtual_accounts.html", {
        "virtual_accounts": virtual_accounts,
        "agent": agent,
    })

@login_required
def payout_from_virtual_account(request, account_id):
    if request.method == "POST":
        acct = get_object_or_404(EconomicResource, pk=account_id)
        owner = acct.owner()
        event_type = EventType.objects.get(name="Payout")
        context = None
        cas = acct.context_agents() #todo: what is correct here?
        if cas:
            context = cas[0]
        form = acct.payout_form(data=request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            event = form.save(commit=False)
            event.event_type = event_type
            event.from_agent = owner
            event.to_agent = owner
            event.resource_type = acct.resource_type
            event.resource = acct
            event.unit_of_quantity = acct.unit_of_quantity()
            event.created_by = request.user
            #event.context = context
            event.save()
            acct.quantity -= event.quantity
            acct.save()

    return HttpResponseRedirect('/%s/'
        % ('accounting/virtual-accounts'))


#obsolete: everything below has been moved to the new api app and shd be deleted soon
#the following methods relate to providing linked open data from NRP instances, for the valueflows vocab project.
#they use rdflib, Copyright (c) 2012-2015, RDFLib Team All rights reserved.

def get_lod_setup_items():
    from rdflib import Graph
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib import Namespace

    path = get_url_starter() + "/accounting/"
    instance_abbrv = Site.objects.get_current().domain.split(".")[0]

    context = {
        "vf": "https://w3id.org/valueflows/",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        #"rdfs:label": { "@container": "@language" },
        "Agent": "vf:Agent",
        "Person": "vf:Person",
        "Group": "vf:Group",
        #"Organization": "vf:Organization",
        "url":  { "@id": "vf:url", "@type": "@id" },
        "image": { "@id": "vf:image", "@type": "@id" },
        #"displayName": "vf:displayName",
        #"displayNameMap": { "@id": "displayName", "@container": "@language" },
        "Relationship": "vf:Relationship",
        "subject": { "@id": "vf:subject", "@type": "@id" },
        "object": { "@id": "vf:object", "@type": "@id" },
        "relationship": { "@id": "vf:relationship", "@type": "@id" },
        #"member": { "@id": "vf:member", "@type": "@id" }
        "label": "skos:prefLabel",
        "labelMap": { "@id": "skos:prefLabel", "@container": "@language" },
        "note": "skos:note",
        "noteMap": { "@id": "skos:note", "@container": "@language" },
        "inverseOf": "owl:inverseOf",
        instance_abbrv: path,
    }

    store = Graph()
    #store.bind("foaf", FOAF)
    store.bind("rdf", RDF)
    store.bind("rdfs", RDFS)
    store.bind("owl", OWL)
    store.bind("skos", SKOS)
    #as_ns = Namespace("http://www.w3.org/ns/activitystreams#")
    #store.bind("as", as_ns)
    #schema_ns = Namespace("http://schema.org/")
    #store.bind("schema", schema_ns)
    #at_ns = Namespace(path + "agent-type/")
    #store.bind("at", at_ns)
    #aat_ns = Namespace(path + "agent-relationship-type/")
    #store.bind("aat", aat_ns)
    vf_ns = Namespace("https://w3id.org/valueflows/")
    store.bind("vf", vf_ns)
    instance_ns = Namespace(path)
    store.bind("instance", instance_ns)

    return path, instance_abbrv, context, store, vf_ns


def agent_type_lod(request, agent_type_name):
    ats = AgentType.objects.all()
    agent_type = None

    for at in ats:
        if camelcase(at.name) == agent_type_name:
            agent_type = at

    if not agent_type:
        return HttpResponse({}, content_type='application/json')

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    if agent_type.name != "Person" and agent_type.name != "Group" and agent_type.name != "Individual":
        class_name = camelcase(agent_type.name)
        ref = URIRef(instance_abbrv + ":agent-type-lod/" +class_name)
        store.add((ref, RDF.type, OWL.Class))
        store.add((ref, SKOS.prefLabel, Literal(class_name, lang="en")))
        if agent_type.party_type == "individual":
            store.add((ref, RDFS.subClassOf, vf_ns.Person))
        else:
            store.add((ref, RDFS.subClassOf, vf_ns.Group))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render(request, "valueaccounting/agent_type.html", {
    #    "agent_type": agent_type,
    #})

def agent_relationship_type_lod(request, agent_assoc_type_name):
    aats = AgentAssociationType.objects.all()
    agent_assoc_type = None
    for aat in aats:
        if camelcase_lower(aat.label) == agent_assoc_type_name:
            agent_assoc_type = aat
            inverse = False
        elif camelcase_lower(aat.inverse_label) == agent_assoc_type_name:
            agent_assoc_type = aat
            inverse = True

    if not agent_assoc_type:
        return HttpResponse({}, content_type='application/json')

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    if inverse:
        property_name = camelcase_lower(agent_assoc_type.inverse_label)
        inverse_property_name = camelcase_lower(agent_assoc_type.label)
        label = agent_assoc_type.inverse_label
    else:
        property_name = camelcase_lower(agent_assoc_type.label)
        inverse_property_name = camelcase_lower(agent_assoc_type.inverse_label)
        label = agent_assoc_type.label
    ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inverse_property_name)
    store.add((ref, RDF.type, RDF.Property))
    store.add((ref, SKOS.prefLabel, Literal(label, lang="en")))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render(request, "valueaccounting/agent_assoc_type.html", {
    #    "agent_assoc_type": agent_assoc_type,
    #})

def agent_relationship_lod(request, agent_assoc_id):
    aa = AgentAssociation.objects.filter(id=agent_assoc_id)
    if not aa:
        return HttpResponse({}, content_type='application/json')
    else:
        agent_association = aa[0]

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(agent_association.id) + "/")
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(agent_association.id) + "/")
    ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.is_associate.id) + "/")
    ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.has_associate.id) + "/")
    property_name = camelcase_lower(agent_association.association_type.label)
    ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type/" + property_name)
    store.add((ref, RDF.type, vf_ns["Relationship"]))
    store.add((ref, vf_ns["subject"], ref_subject))
    store.add((ref, vf_ns["object"], ref_object))
    store.add((ref, vf_ns["relationship"], ref_relationship))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render(request, "valueaccounting/agent_association.html", {
    #    "agent_association": agent_association,
    #})


def agent_relationship_inv_lod(request, agent_assoc_id):
    aa = AgentAssociation.objects.filter(id=agent_assoc_id)
    if not aa:
        return HttpResponse({}, content_type='application/json')
    else:
        agent_association = aa[0]

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(agent_association.id) + "/")
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(agent_association.id) + "/")
    ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.is_associate.id) + "/")
    ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.has_associate.id) + "/")
    property_name = camelcase_lower(agent_association.association_type.inverse_label)
    ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
    store.add((ref, RDF.type, vf_ns["Relationship"]))
    store.add((ref, vf_ns["subject"], ref_subject))
    store.add((ref, vf_ns["object"], ref_object))
    store.add((ref, vf_ns["relationship"], ref_relationship))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render(request, "valueaccounting/agent_association.html", {
    #    "agent_association": agent_association,
    #})

def agent_lod(request, agent_id):
    agents = EconomicAgent.objects.filter(id=agent_id)
    if not agents:
        return HttpResponse({}, content_type='application/json')

    agent = agents[0]
    subject_assocs = agent.all_is_associates()
    object_assocs = agent.all_has_associates()

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    #Lynn: I made a change here for consistency. Please check and fix if needed.
    ref = URIRef(instance_abbrv + ":agent-lod/" + str(agent.id) + "/")
    if agent.agent_type.name == "Individual" or agent.agent_type.name == "Person":
        store.add((ref, RDF.type, vf_ns.Person))
    #elif agent.agent_type.name == "Organization":
    #    store.add((ref, RDF.type, vf_ns.Organization))
    else:
        at_class_name = camelcase(agent.agent_type.name)
        ref_class = URIRef(instance_abbrv + ":agent-type-lod/" + at_class_name)
        store.add((ref, RDF.type, ref_class))
    store.add((ref, vf_ns["label"], Literal(agent.name, lang="en")))
    #if agent.photo_url:
    #    store.add((ref, vf_ns["image"], agent.photo_url))

    #if subject_assocs or object_assocs:
    #    store.add((  ))
    if subject_assocs:
        for a in subject_assocs:
            obj_ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(a.id) + "/")
            property_name = camelcase_lower(a.association_type.label)
            ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
            store.add((ref, ref_relationship, obj_ref))
    if object_assocs:
        for a in object_assocs:
            subj_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(a.id) + "/")
            inv_property_name = camelcase_lower(a.association_type.inverse_label)
            inv_ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inv_property_name)
            store.add((ref, inv_ref_relationship, subj_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')

#following method supplied by Niklas at rdflib-jsonld support to get the desired output for nested rdf inputs for rdflib
def simplyframe(data):
    items, refs = {}, {}
    for item in data['@graph']:
        itemid = item.get('@id')
        if itemid:
            items[itemid] = item
        for vs in list(item.values()):
            for v in [vs] if not isinstance(vs, list) else vs:
                if isinstance(v, dict):
                    refid = v.get('@id')
                    if refid and refid.startswith('_:'):
                        refs.setdefault(refid, (v, []))[1].append(item)
    for ref, subjects in list(refs.values()):
        if len(subjects) == 1:
            ref.update(items.pop(ref['@id']))
            del ref['@id']
    data['@graph'] = list(items.values())

def agent_jsonld(request):
    #test = "{'@context': 'http://json-ld.org/contexts/person.jsonld', '@id': 'http://dbpedia.org/resource/John_Lennon', 'name': 'John Lennon', 'born': '1940-10-09', 'spouse': 'http://dbpedia.org/resource/Cynthia_Lennon' }"
    #test = '{ "@id": "http://nrp.webfactional.com/accounting/agent-lod/1", "@type": "Person", "vf:label": { "@language": "en", "@value": "Bob Haugen" } }'
    #return HttpResponse(test, content_type='application/json')

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    agent_types = AgentType.objects.all()
    for at in agent_types:
        #if at.name != "Person" and at.name != "Organization" and at.name != "Group" and at.name != "Individual":
        if at.name != "Person" and at.name != "Group" and at.name != "Individual":
            class_name = camelcase(at.name)
            #ref = URIRef(at_ns[class_name])
            ref = URIRef(instance_abbrv + ":agent-type-lod/" +class_name)
            store.add((ref, RDF.type, OWL.Class))
            store.add((ref, SKOS.prefLabel, Literal(class_name, lang="en")))
            if at.party_type == "individual":
                store.add((ref, RDFS.subClassOf, vf_ns.Person))
            else:
                store.add((ref, RDFS.subClassOf, vf_ns.Group))

    aa_types = AgentAssociationType.objects.all()
    for aat in aa_types:
        property_name = camelcase_lower(aat.label)
        inverse_property_name = camelcase_lower(aat.inverse_label)
        ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
        store.add((ref, RDF.type, RDF.Property))
        store.add((ref, SKOS.prefLabel, Literal(aat.label, lang="en")))
        #inverse = BNode()
        #store.add((ref, OWL.inverseOf, inverse))
        #store.add((inverse, RDFS.label, Literal(aat.inverse_label, lang="en")))
        if property_name != inverse_property_name:
            inv_ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inverse_property_name)
            store.add((inv_ref, RDF.type, RDF.Property))
            store.add((inv_ref, SKOS.prefLabel, Literal(aat.inverse_label, lang="en")))
        store.add((ref, OWL.inverseOf, inv_ref))
        store.add((inv_ref, OWL.inverseOf, ref))

    associations = AgentAssociation.objects.filter(state="active")
    agents = [assn.is_associate for assn in associations]
    agents.extend([assn.has_associate for assn in associations])
    agents = list(set(agents))

    for agent in agents:
        ref = URIRef(instance_abbrv + ":agent-lod/" + str(agent.id) + "/")
        if agent.agent_type.name == "Individual" or agent.agent_type.name == "Person":
            store.add((ref, RDF.type, vf_ns.Person))
        #elif agent.agent_type.name == "Organization":
        #    store.add((ref, RDF.type, vf_ns.Organization))
        else:
            at_class_name = camelcase(agent.agent_type.name)
            ref_class = URIRef(instance_abbrv + ":agent-type-lod/" + at_class_name)
            store.add((ref, RDF.type, ref_class))
        store.add((ref, vf_ns["label"], Literal(agent.name, lang="en")))
        #if agent.name != agent.nick:
        #    store.add((ref, FOAF.nick, Literal(agent.nick, lang="en")))
        #if agent.photo_url:
        #    store.add((ref, vf_ns["image"], agent.photo_url))

    for a in associations:
        ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(a.id) + "/")
        inv_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(a.id) + "/")
        ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(a.is_associate.id) + "/")
        ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(a.has_associate.id) + "/")
        property_name = camelcase_lower(a.association_type.label)
        inv_property_name = camelcase_lower(a.association_type.inverse_label)
        ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
        inv_ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inv_property_name)
        store.add((ref, RDF.type, vf_ns["Relationship"]))
        store.add((ref, vf_ns["subject"], ref_subject))
        store.add((ref, vf_ns["object"], ref_object))
        store.add((ref, vf_ns["relationship"], ref_relationship))
        store.add((inv_ref, RDF.type, vf_ns["Relationship"]))
        store.add((inv_ref, vf_ns["object"], ref_subject))
        store.add((inv_ref, vf_ns["subject"], ref_object))
        store.add((inv_ref, vf_ns["relationship"], inv_ref_relationship))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    #import json
    #data = json.loads(ser)
    #simplyframe(data)
    #return HttpResponse(json.dumps(data, indent=4), content_type='application/json')
    return HttpResponse(ser, content_type='application/json')

def agent_jsonld_query(request):
    from rdflib import Graph
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef
    from urllib.request import urlopen
    from io import StringIO

    g = Graph()
    url = "http://nrp.webfactional.com/accounting/agent-jsonld/"
    remote_jsonld = urlopen(url).read()
    dict_data = simplejson.loads(remote_jsonld)
    context = dict_data["@context"]
    graph = dict_data["@graph"]
    local_graph = simplejson.dumps(graph)
    g.parse(StringIO(str(local_graph)), context=context, format="json-ld")
    local_expanded_json = g.serialize(format="json-ld", indent=4)
    local_expanded_dict = simplejson.loads(local_expanded_json)


    result = ""
    agents = [x for x in graph if x['@id'].find('agent-lod') > -1]
    agent_dict = {}
    for a in agents:
        agent_dict[str(a['@id'])] = a

    rels = [x for x in graph if x['@type']=='Relationship']

    agent_rels = []
    for r in rels:
        d = {}
        d["subject"] = agent_dict[r["subject"]]
        d["object"] = agent_dict[r["object"]]
        d["relationship"] = r["relationship"]
        agent_rels.append(d)

    for ar in agent_rels:
        object = ar['object']
        object_type = object['@type']
        if object_type.find('/') > -1:
            object_type = object_type.split('/')[1]
        object_label = object['vf:label']['@value']
        subject = ar['subject']
        subject_type = subject['@type']
        if subject_type.find('/') > -1:
            subject_type = subject_type.split('/')[1]
        subject_label = subject['vf:label']['@value']
        relationship = ar['relationship']
        if relationship.find('/') > -1:
            relationship = relationship.split('/')[1]
        ostr = ", a ".join([object_label, object_type])
        sstr = ", a ".join([subject_label, subject_type])
        line = " ".join([ sstr, relationship, ostr])
        result += line + "\n"
    result += "\n"
    result += "========== Gory details from http://nrp.webfactional.com/accounting/agent-jsonld/ ==========\n"

    for item in local_expanded_dict:
        for key, value in list(item.items()):
            if type(value) is list:
                value = value[0]
                if type(value) is dict:
                    valist = []
                    for key2, value2 in list(value.items()):
                        valist.append(": ".join([key2, value2]))
                    value = ", ".join(valist)
            line = ": ".join([key, value])
            result += line + "\n"
        result += "========== \n"

    #result = "Number of triples: " + str(len(g)) + "\n"
    #for s,p,o in g.triples( (None, None, None) ):
    #    result += s + " " + p + " " + o + "\n"
    return HttpResponse(result, content_type='text/plain')
    #return HttpResponse(local_expanded_json, content_type='application/json')

'''
g = Graph()
url = "http://dhen.webfactional.com/accounting/agent-jsonld/"
remote_jsonld = urlopen(url).read()
dict_data = simplejson.loads(remote_jsonld)
import json as simplejson
dict_data = simplejson.loads(remote_jsonld)
context = dict_data["@context"]
graph = dict_data["@graph"]
peeps = [x for x in graph if x['@type']=='Person']
rels = [x for x in graph if x['@type']=='Relationship']
ids = [x['@id'].split('/')[1] for x in graph]
'''

@login_required
def skill_suggestions(request):
    state = "new"
    state_form = RequestStateForm(
        initial={"state": "new",},
        data=request.POST or None)
    if request.method == "POST":
        if state_form.is_valid():
            data = state_form.cleaned_data
            state = data["state"]
    suggestions =  SkillSuggestion.objects.filter(state=state)

    return render(request, "valueaccounting/skill_suggestions.html", {
        "help": get_help("skill_suggestions"),
        "suggestions": suggestions,
        "state_form": state_form,
        "state": state,
    })

@login_required
def validate_resource_type_name(request):
    answer = True
    error = ""
    data = request.GET
    values = list(data.values())
    if values:
        name = values[0]
        try:
            user = EconomicResourceType.objects.get(name=name)
            error = "Resource Type name already taken"
        except EconomicResourceType.DoesNotExist:
            pass

    if error:
        answer = error
    response = simplejson.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")


@login_required
def create_skill_for_suggestion(request, suggestion_id):
    if request.method == "POST":
        suggestion = get_object_or_404(SkillSuggestion, pk=suggestion_id)
        form = SkillSuggestionResourceTypeForm(prefix=suggestion.form_prefix(), data=request.POST or None)
        if form.is_valid():
            skill = form.save(commit=False)
            skill.inventory_rule="never"
            skill.behavior="work"
            hrs = Unit.objects.filter(name_en__icontains="Hour")
            hr = None
            if hrs:
                hr = hrs[0]
            else:
                hr = Unit(
                    name="Hour",
                    unit_type="time",
                    abbrev="Hr",
                    )
                hr.save()
            skill.unit=hr
            skill.created_by=request.user
            skill.save()
            suggestion.resource_type=skill
            suggestion.state="accepted"
            suggestion.save()

    return HttpResponseRedirect('/%s/'
        % ('accounting/skill-suggestions'))

@login_required
def decline_suggestion(request, suggestion_id):
    suggestion = get_object_or_404(SkillSuggestion, pk=suggestion_id)
    suggestion.state = "declined"
    suggestion.save()
    return HttpResponseRedirect('/%s/'
        % ('accounting/skill-suggestions'))

@login_required
def undecline_suggestion(request, suggestion_id):
    suggestion = get_object_or_404(SkillSuggestion, pk=suggestion_id)
    if suggestion.resource_type:
      suggestion.state = "accepted"
    else:
      suggestion.state = "new"
    suggestion.save()
    return HttpResponseRedirect('/%s/'
        % ('accounting/skill-suggestions'))

@login_required
def membership_requests(request):
    state = "new"
    state_form = RequestStateForm(
        initial={"state": "new",},
        data=request.POST or None)
    #agent_form = MembershipAgentSelectionForm()
    if request.method == "POST":
        if state_form.is_valid():
            data = state_form.cleaned_data
            state = data["state"]
    requests =  MembershipRequest.objects.filter(state=state)

    return render(request, "valueaccounting/membership_requests.html", {
        "help": get_help("membership_requests"),
        "requests": requests,
        "state_form": state_form,
        "state": state,
        #"agent_form": agent_form,
    })

"""
@login_required
def membership_request(request, membership_request_id):
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'valueaccounting/no_permission.html')
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    init = {
        "name": " ".join([mbr_req.name, mbr_req.surname]),
        "nick": mbr_req.requested_username,
        "description": mbr_req.description,
        "email": mbr_req.email_address,
        "url": mbr_req.website,
        }
    if mbr_req.type_of_membership == "individual":
        at = AgentType.objects.filter(party_type="individual")
        if at:
            at = at[0]
            init["agent_type"] = at
    agent_form = AgentCreateForm(initial=init)
    nicks = '~'.join([
        agt.nick for agt in EconomicAgent.objects.all()])
    return render(request, "valueaccounting/membership_request.html", {
        "help": get_help("membership_request"),
        "mbr_req": mbr_req,
        "agent_form": agent_form,
        "user_agent": user_agent,
        "nicks": nicks,
    })
"""

@login_required
def decline_request(request, membership_request_id):
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    mbr_req.state = "declined"
    mbr_req.save()
    return HttpResponseRedirect('/%s/'
        % ('accounting/membership-requests'))

@login_required
def undecline_request(request, membership_request_id):
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    mbr_req.state = "new"
    mbr_req.save()
    return HttpResponseRedirect('/%s/'
        % ('accounting/membership-requests'))

@login_required
def delete_request(request, membership_request_id):
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    mbr_req.delete()
    return HttpResponseRedirect('/%s/'
        % ('accounting/membership-requests'))

@login_required
def create_agent_for_request(request, membership_request_id):
    if request.method == "POST":
        mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
        form = AgentCreateForm(request.POST)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.created_by=request.user
            agent.save()
            mbr_req.agent = agent
            mbr_req.state = "accepted"
            mbr_req.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/agent', agent.id))
    return HttpResponseRedirect('/%s/%s/'
        % ('accounting/membership-request', membership_request_id))

def connect_agent_to_request(request, membership_request_id):
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    if request.method == "POST":
        agent_form = MembershipAgentSelectionForm(data=request.POST)
        if agent_form.is_valid():
            data = agent_form.cleaned_data
            agent = data["created_agent"]
            mbr_req.agent=agent
            mbr_req.save()

    return HttpResponseRedirect('/%s/'
        % ('accounting/membership-requests'))


def resource_role_context_agent_formset(prefix, data=None):
    RraFormSet = modelformset_factory(
        AgentResourceRole,
        form=ResourceRoleContextAgentForm,
        can_delete=True,
        extra=4,
        )
    formset = RraFormSet(prefix=prefix, queryset=AgentResourceRole.objects.none(), data=data)
    return formset

@login_required
def send_fdc_welcome(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    return_data = "ERROR"
    if send_email(request, agent, agent.faircoin_address(), password_generator()):
        return_data = "OK"
    return HttpResponse(return_data, content_type="text/plain")

def send_email(request, user, faircoin_address, password):
    protocol = getattr(settings, "DEFAULT_HTTP_PROTOCOL", "http")
    current_site = get_current_site(request)
    print(current_site)
    ctx = {
        "user": user,
        "faircoin_address": faircoin_address,
        "password": password,
        "protocol": protocol,
        "current_site": current_site,
    }
    subject = render_to_string("valueaccounting/email_fdc_welcome_subject.txt", ctx)
    subject = "".join(subject.splitlines())
    message = render_to_string("valueaccounting/email_fdc_welcome_body.txt", ctx)
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
