import datetime

from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import formset_factory, modelformset_factory, inlineformset_factory, BaseModelFormSet
from django.forms import ValidationError
from django.utils import simplejson
from django.utils.datastructures import SortedDict
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.forms import *
from work.forms import *
from valuenetwork.valueaccounting.views import *
#from valuenetwork.valueaccounting.views import get_agent, get_help, get_site_name, resource_role_agent_formset, uncommit, commitment_finished, commit_to_task

if "notification" in settings.INSTALLED_APPS:
    from notification import models as notification
else:
    notification = None


def work_home(request):

    return render_to_response("work_home.html",
        context_instance=RequestContext(request))

    
@login_required
def my_dashboard(request):
    #import pdb; pdb.set_trace()
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
            event_type__relationship="work").exclude(resource_type__id__in=skill_ids)       
    else:
        other_unassigned = Commitment.objects.unfinished().filter(
            from_agent=None, 
            event_type__relationship="work")
    work_now = settings.USE_WORK_NOW
    return render_to_response("work/my_dashboard.html", {
        "agent": agent,
        "my_work": my_work,
        "my_skillz": my_skillz,
        "other_unassigned": other_unassigned,
        "work_now": work_now,
        #"help": get_help("my_work"),
    }, context_instance=RequestContext(request))
    
def map(request):
    agent = get_agent(request)
    locations = Location.objects.all()
    nolocs = Location.objects.filter(latitude=0.0)
    latitude = settings.MAP_LATITUDE
    longitude = settings.MAP_LONGITUDE
    zoom = settings.MAP_ZOOM
    return render_to_response("work/map.html", {
        "agent": agent,
        "locations": locations,
        "nolocs": nolocs,
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
        #"help": get_help("map"),
    }, context_instance=RequestContext(request))

@login_required
def profile(request):
    #import pdb; pdb.set_trace()
    agent = get_agent(request)
    change_form = AgentCreateForm(instance=agent)
    skills = EconomicResourceType.objects.filter(behavior="work")
    et_work = EventType.objects.get(name="Time Contribution")
    arts = agent.resource_types.filter(event_type=et_work)
    agent_skills = []
    for art in arts:
        agent_skills.append(art.resource_type)
    for skill in skills:
        skill.checked = False
        if skill in agent_skills:
            skill.checked = True
    upload_form = UploadAgentForm(instance=agent)
          
    return render_to_response("work/profile.html", {
        "agent": agent,
        "photo_size": (128, 128),
        "change_form": change_form,
        "upload_form": upload_form,
        "skills": skills,
        "help": get_help("agent"),
    }, context_instance=RequestContext(request))

@login_required
def change_personal_info(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render_to_response('valueaccounting/no_permission.html')
    change_form = AgentCreateForm(instance=agent, data=request.POST or None)
    if request.method == "POST":
        #import pdb; pdb.set_trace()
        if change_form.is_valid():
            agent = change_form.save()
    return HttpResponseRedirect('/%s/'
        % ('work/profile'))

@login_required
def upload_picture(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render_to_response('valueaccounting/no_permission.html')
    form = UploadAgentForm(instance=agent, data=request.POST, files=request.FILES)
    if form.is_valid():
        data = form.cleaned_data
        agt = form.save(commit=False)                    
        agt.changed_by=request.user
        agt.save()
    
    return HttpResponseRedirect('/%s/'
        % ('work/profile'))

@login_required
def update_skills(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render_to_response('valueaccounting/no_permission.html')
    #import pdb; pdb.set_trace()
    et_work = EventType.objects.get(name="Time Contribution")
    arts = agent.resource_types.filter(event_type=et_work)
    old_skill_rts = []
    for art in arts:
        old_skill_rts.append(art.resource_type)
    new_skills_list = request.POST.getlist('skill')
    new_skill_rts = []
    for rt_id in new_skills_list:
        skill = EconomicResourceType.objects.get(id=int(rt_id))
        new_skill_rts.append(skill)
    for skill in old_skill_rts:
        if skill not in new_skill_rts:
            arts = AgentResourceType.objects.filter(agent=agent).filter(resource_type=skill)
            if arts:
                art = arts[0]
                art.delete()
    for skill in new_skill_rts:
        if skill not in old_skill_rts:
            art = AgentResourceType(
                agent=agent,
                resource_type=skill,
                event_type=et_work,
                created_by=request.user,
            )
            art.save()
    
    return HttpResponseRedirect('/%s/'
        % ('work/profile'))
        
@login_required
def add_worker_to_location(request, location_id, agent_id):
    if location_id and agent_id:
        location = get_object_or_404(Location, id=location_id)
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        agent.primary_location = location
        agent.save()
        return HttpResponseRedirect('/%s/'
            % ('work/profile'))
    else:
        return HttpResponseRedirect('/%s/'
            % ('work/map'))

@login_required
def add_location_to_worker(request, agent_id):
    if request.method == "POST":
        #import pdb; pdb.set_trace()
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        data = request.POST
        address = data["address"]
        longitude = data["agentLongitude"]
        latitude = data["agentLatitude"]
        location, created = Location.objects.get_or_create(
            latitude=latitude,
            longitude=longitude,
            address=address)
        if created:
            location.name = address
            location.save()
        agent.primary_location = location
        agent.save()
        return HttpResponseRedirect('/%s/'
            % ('work/profile'))
    else:
        return HttpResponseRedirect('/%s/'
            % ('work/map'))
        
@login_required    
def process_logging(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    pattern = process.process_pattern
    context_agent = process.context_agent
    #import pdb; pdb.set_trace()
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
        #import pdb; pdb.set_trace()
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
        #import pdb; pdb.set_trace()
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
    #import pdb; pdb.set_trace()
    citation_requirements = process.citation_requirements()
    for cr in citation_requirements:
        cr.resources = []
        for evt in cr.fulfilling_events():
            resource = evt.resource
            resource.event = evt
            cr.resources.append(resource)
    
    output_resource_ids = [e.resource.id for e in process.production_events() if e.resource]
    
    return render_to_response("work/process_logging.html", {
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
    }, context_instance=RequestContext(request))


@login_required
def my_history(request):
    #import pdb; pdb.set_trace()
    #agent = get_object_or_404(EconomicAgent, pk=agent_id)
    user_agent = get_agent(request)
    agent = user_agent
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
    event_types = {e.event_type for e in event_list}
    filter_form = EventTypeFilterForm(event_types=event_types, data=request.POST or None)
    paid_filter = "U"
    if request.method == "POST":
        if filter_form.is_valid():
            #import pdb; pdb.set_trace()
            data = filter_form.cleaned_data
            et_ids = data["event_types"]
            start = data["start_date"]
            end = data["end_date"]
            paid_filter = data["paid_filter"]
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
            #belt and suspenders: if no et_ids, form is not valid
            if et_ids:
                event_list = event_list.filter(event_type__id__in=et_ids)

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
    #took off csv export for now
    #event_ids = ",".join([str(event.id) for event in event_list]) 
                    
    if paid_filter == "U":
        event_list = list(event_list)
        for evnt in event_list:
            if evnt.owed_amount() == 0:
                    event_list.remove(evnt)
    
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
    
    #import pdb; pdb.set_trace()
    return render_to_response("work/my_history.html", {
        "agent": agent,
        "user_is_agent": user_is_agent,
        "events": events,
        "filter_form": filter_form,
        #"event_ids": event_ids,
        "no_bucket": no_bucket,
        "with_bucket": with_bucket,
        "claim_value": format(claim_value, ",.2f"),
        "outstanding_claims": format(outstanding_claims, ",.2f"),
        "claim_distributions": format(claim_distributions, ",.2f"),
        "other_distributions": format(other_distributions, ",.2f"),
    }, context_instance=RequestContext(request))

@login_required
def change_history_event(request, event_id):
    event = get_object_or_404(EconomicEvent, pk=event_id)
    page = request.GET.get("page")
    #import pdb; pdb.set_trace()
    event_form = event.change_form(data=request.POST or None)
    if request.method == "POST":
        #import pdb; pdb.set_trace()
        page = request.POST.get("page")
        if event_form.is_valid():
            event = event_form.save(commit=False)
            event.changed_by = request.user
            event.save()
        agent = event.from_agent
        #next = request.POST.get("next")
        if page:
            #if next:
            #    if next == "work-contributions":
            #        return HttpResponseRedirect('/%s/'
            #            % ('work/my-history', page))
            return HttpResponseRedirect('/%s/'
                % ('work/my-history', page))
        else:
            #if next:
            #    if next == "work-contributions":
            #        return HttpResponseRedirect('/%s/'
            #            % ('work/my-history'))
            return HttpResponseRedirect('/%s/'
                % ('work/my-history'))
    return render_to_response("work/change_history_event.html", {
        "event_form": event_form,
        "page": page,
    }, context_instance=RequestContext(request)) 

'''
@login_required
def register_skills(request):
    #import pdb; pdb.set_trace()
    agent = get_agent(request)
    skills = EconomicResourceType.objects.filter(behavior="work")
    
    return render_to_response("work/register_skills.html", {
        "agent": agent,
        "skills": skills,
    }, context_instance=RequestContext(request))
'''

def create_worktimer_context(
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
    #if event.quantity > 0:
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
def work_timer(
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
        #        return render_to_response('valueaccounting/no_permission.html')
    template_params = create_worktimer_context(
        request, 
        process,
        agent,
        ct, 
    )
    return render_to_response("work/work_timer.html",
        template_params,
        context_instance=RequestContext(request))

@login_required
def save_timed_work_now(request, event_id):
    #import pdb; pdb.set_trace()
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
        return HttpResponse(data, mimetype="text/plain")

@login_required
def work_process_finished(request, process_id):
    #import pdb; pdb.set_trace()
    process = get_object_or_404(Process, pk=process_id)
    if not process.finished:
        process.finished = True
        process.save()
    else:
        if process.finished:
            process.finished = False
            process.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process_id))

