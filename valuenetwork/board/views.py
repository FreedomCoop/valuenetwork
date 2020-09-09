import datetime

from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import formset_factory, modelformset_factory, inlineformset_factory, BaseModelFormSet
from django.forms import ValidationError
import json as simplejson
from collections import OrderedDict
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings

from valuenetwork.valueaccounting.models import *
from valuenetwork.board.forms import *
from valuenetwork.valueaccounting.views import get_agent

def default_context_agent():
    return EconomicAgent.objects.get(id=3) #todo:  BIG hack alert!!!!

#todo: a lot of this can be configured instead of hard-coded
def dhen_board(request, context_agent_id=None):
    agent = get_agent(request)
    pattern = ProcessPattern.objects.get(name="Herbs")
    selected_resource_type = None
    #filter_form = FilterForm(pattern=pattern, data=request.POST or None,)
    if context_agent_id:
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
    else:
        context_agent = default_context_agent()
    seller = EconomicAgent.objects.get(id=4) #todo: even worse hack!!
    rec_extype = ExchangeType.objects.get(name="Purchase to Drying Site")
    e_date = datetime.date.today()
    init = {"start_date": e_date }
    available_extype = ExchangeType.objects.get(name="Make Available")
    available_form = AvailableForm(initial=init, exchange_type=available_extype, context_agent=context_agent, prefix="AVL")
    init = {"event_date": e_date, "paid": "later", }
    receive_form = ReceiveForm(initial=init, exchange_type=rec_extype, context_agent=context_agent, prefix="REC")
    et = EventType.objects.get(name="Resource Production")
    farm_stage = None  
    #harvester_stage = ExchangeType.objects.get(name="Farm to Harvester")  
    dryer_stage = ExchangeType.objects.get(name="Harvester to Drying Site")  
    seller_stage = ExchangeType.objects.get(name="Drying Site to Seller")
    rts = pattern.get_resource_types(event_type=et)
    for rt in rts:
        init = {"event_date": e_date,}
        rt.farm_commits = rt.commits_for_exchange_stage(stage=farm_stage)
        for com in rt.farm_commits:
            if com.start_date > e_date:
                com.future = True
            prefix = com.form_prefix()
            qty_help = " ".join([com.unit_of_quantity.abbrev, ", up to 2 decimal places"])
            com.transfer_form = ExchangeFlowForm(initial=init, qty_help=qty_help, assoc_type_identifier="DryingSite", context_agent=context_agent, prefix=prefix)
            com.zero_form = ZeroOutForm(prefix=prefix)
            com.lot_form = NewResourceForm(prefix=prefix)
            com.multiple_formset = create_exchange_formset(context_agent=context_agent, assoc_type_identifier="Harvester", prefix=prefix)            
        rt.dryer_resources = rt.onhand_for_exchange_stage(stage=dryer_stage)
        init = {"event_date": e_date, "paid": "later"}
        for res in rt.dryer_resources:
            prefix = res.form_prefix()
            qty_help = " ".join([res.unit_of_quantity().abbrev, ", up to 2 decimal places"])
            res.transfer_form = TransferFlowForm(initial=init, qty_help=qty_help, assoc_type_identifier="Seller", context_agent=context_agent, prefix=prefix)
        rt.seller_resources = rt.onhand_for_exchange_stage(stage=seller_stage)
        if rt.seller_resources:
            init_rt = {"event_date": e_date,} 
            rt.combine_form = CombineResourcesForm(prefix = rt.form_prefix(), initial=init_rt, resource_type=rt, stage=seller_stage)
    
    return render_to_response("board/dhen_board.html", {
        "agent": agent,
        "context_agent": context_agent,
        "seller": seller,
        "available_form": available_form,
        "receive_form": receive_form,
        #"filter_form": filter_form,
        "resource_types": rts,
        "available_extype": available_extype,
    }, context_instance=RequestContext(request))

@login_required
def add_available(request, context_agent_id):
    if request.method == "POST":
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
        form = AvailableForm(data=request.POST, prefix="AVL")
        if form.is_valid():
            commit = form.save(commit=False)
            commit.event_type = EventType.objects.get(name="Give")
            commit.to_agent = context_agent
            commit.context_agent = context_agent
            commit.due_date = commit.start_date
            commit.commitment_date = commit.start_date
            commit.unit_of_quantity = commit.resource_type.unit
            commit.exchange_stage = None
            commit.created_by = request.user
            commit.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))

@login_required
def receive_directly(request, context_agent_id):
    if request.method == "POST":
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
        stage = ExchangeType.objects.get(name="Harvester to Drying Site") 
        exchange_type = ExchangeType.objects.get(name="Purchase to Drying Site") #todo: odd to have stage different....
        form = ReceiveForm(data=request.POST, prefix="REC")
        if form.is_valid():        
            data = form.cleaned_data
            event_date = data["event_date"]
            identifier = data["identifier"]
            from_agent = data["from_agent"] 
            to_agent = data["to_agent"] 
            resource_type = data["resource_type"]
            quantity = data["quantity"]
            description = data["description"] 
            paid = data["paid"]
            value = data["value"]
            unit_of_value = data["unit_of_value"]
            receive_et = EventType.objects.get(name="Receive")
            give_et = EventType.objects.get(name="Give")
            pay_rt = EconomicResourceType.objects.filter(unit__unit_type="value")[0]
            exchange = Exchange(
                name="Purchase " + resource_type.name + " from " + from_agent.nick,
                use_case=UseCase.objects.get(identifier="supply_xfer"),
                start_date=event_date,
                context_agent=context_agent,
                exchange_type=exchange_type, 
                created_by=request.user,                
            )
            exchange.save()
            resource = EconomicResource(
                identifier=identifier,
                resource_type=resource_type,
                quantity=quantity,
                exchange_stage=stage, 
                notes=description,
                created_by=request.user
            )
            resource.save()
            transfer_type = exchange_type.transfer_types_non_reciprocal()[0]
            xfer_name = transfer_type.name + " of " + resource_type.name
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
            event = EconomicEvent(
                event_type = receive_et,
                event_date = event_date,
                resource = resource,
                resource_type = resource_type,
                transfer = xfer,
                exchange_stage=stage,
                from_agent = from_agent,
                to_agent = to_agent,
                context_agent = context_agent,
                quantity = quantity,
                unit_of_quantity = resource_type.unit,
                value = value,
                unit_of_value = unit_of_value,
                description=description,
                created_by = request.user,                
            )
            event.save()
            
            if paid == "paid":
                if value > 0:
                    transfer_type = exchange_type.transfer_types_reciprocal()[0]
                    xfer_name = transfer_type.name + " for " + resource_type.name
                    pay_xfer = Transfer(
                        name=xfer_name,
                        transfer_type = transfer_type,
                        exchange = exchange,
                        context_agent = context_agent,
                        transfer_date = event_date,
                        notes = description,
                        created_by = request.user              
                        )
                    pay_xfer.save()
                    pay_event = EconomicEvent(
                        event_type = give_et,
                        event_date = event_date,
                        resource_type = pay_rt,
                        transfer = pay_xfer,
                        exchange_stage=stage,
                        from_agent = event.to_agent,
                        to_agent = event.from_agent,
                        context_agent = context_agent,
                        quantity = value,
                        unit_of_quantity = unit_of_value,
                        value = value,
                        unit_of_value = unit_of_value,
                        created_by = request.user,                        
                    )
                    pay_event.save()
            elif paid == "later":
                if value > 0:
                    transfer_type = exchange_type.transfer_types_reciprocal()[0]
                    xfer_name = transfer_type.name + " for " + resource_type.name
                    pay_xfer = Transfer(
                        name=xfer_name,
                        transfer_type = transfer_type,
                        exchange = exchange,
                        context_agent = context_agent,
                        transfer_date = event_date,
                        notes = description,
                        created_by = request.user              
                        )
                    pay_xfer.save()
                    commit = Commitment (
                        commitment_date=event_date,
                        event_type=give_et,
                        transfer=pay_xfer,
                        exchange_stage=stage,
                        due_date=event_date,
                        from_agent=event.to_agent,
                        to_agent=event.from_agent,
                        context_agent=context_agent,
                        resource_type=pay_rt,
                        quantity=value,
                        unit_of_quantity=unit_of_value,
                        value=value,
                        unit_of_value=unit_of_value,
                        created_by=request.user,                        
                    )
                    commit.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))

def create_exchange_formset(context_agent, assoc_type_identifier, prefix, data=None):
    ExchangeFormSet = formset_factory(MultipleExchangeEventForm, extra=10)
    #init = {"paid": "paid"}
    formset = ExchangeFormSet(data=data, prefix=prefix)
    to_agents = context_agent.all_has_associates_by_type(assoc_type_identifier=assoc_type_identifier)
    for form in formset:
        #id = int(form["facet_id"].value())
        form.fields["to_agent"].queryset = to_agents
        form.fields["paid_stage_1"].initial = "never"
        form.fields["paid_stage_2"].initial = "later"
    return formset

#todo: hardcoded recipe and exchange types
def get_next_stage(exchange_type=None):
    if not exchange_type:
        next_stage = ExchangeType.objects.get(name="Farm to Harvester")
    elif exchange_type.name == "Farm to Harvester":
        next_stage = ExchangeType.objects.get(name="Harvester to Drying Site")
    elif exchange_type.name == "Harvester to Drying Site":
        next_stage = ExchangeType.objects.get(name="Drying Site to Seller")
    else:
        next_stage = None
    return next_stage
    
@login_required
def purchase_resource(request, context_agent_id, commitment_id): #this is the farm > harvester > drying site, confusing name
    if request.method == "POST":
        commitment = get_object_or_404(Commitment, id=commitment_id)
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
        stage = None
        next_stage = get_next_stage(stage)
        next_next_stage = get_next_stage(next_stage)
        prefix = commitment.form_prefix()
        form = ExchangeFlowForm(prefix=prefix, data=request.POST)
        lot_form = NewResourceForm(prefix=prefix, data=request.POST)
        zero_form = ZeroOutForm(prefix=prefix, data=request.POST)

        if zero_form.is_valid():        
            zero_data = zero_form.cleaned_data
            zero_out = zero_data["zero_out"]
            if zero_out == True:
                commitment.finished = True
                commitment.save()
        
        if form.is_valid() and lot_form.is_valid():
            data = form.cleaned_data
            event_date = data["event_date"] 
            to_agent = data["to_agent"]
            unit_of_value = data["unit_of_value"]
            notes  = data["notes"]
            lot_data = lot_form.cleaned_data
            identifier = lot_data["identifier"]
            purch_use_case = UseCase.objects.get(identifier="supply_xfer")
            purch_exchange_type = ExchangeType.objects.get(name="Farm to Harvester")
            xfer_use_case = UseCase.objects.get(identifier="intrnl_xfer")
            xfer_exchange_type = ExchangeType.objects.get(name="Harvester to Drying Site")
            proc_use_case = UseCase.objects.get(identifier="rand")
            proc_pattern = None
            proc_patterns = [puc.pattern for puc in proc_use_case.patterns.all()]
            if proc_patterns:
                proc_pattern = proc_patterns[0]
            give_et = EventType.objects.get(name="Give")
            receive_et = EventType.objects.get(name="Receive")
            consume_et = EventType.objects.get(name="Resource Consumption")
            produce_et = EventType.objects.get(name="Resource Production")
            pay_rt = EconomicResourceType.objects.filter(unit__unit_type="value")[0]
            formset = create_exchange_formset(prefix=prefix, data=request.POST, context_agent=context_agent, assoc_type_identifier="Harvester")
            quantity = 0
            ces = []
            for form_ee in formset.forms:
                if form_ee.is_valid():
                    data_ee = form_ee.cleaned_data
                    breakout_to_agent = data_ee["to_agent"]
                    if breakout_to_agent:
                        breakout_quantity = data_ee["quantity"]
                        quantity += breakout_quantity
                        value_stage_1 = data_ee["value_stage_1"]
                        paid_stage_1 = data_ee["paid_stage_1"]
                        value_stage_2 = data_ee["value_stage_2"]
                        paid_stage_2 = data_ee["paid_stage_2"]
                        
                        exchange = Exchange(
                            name="Transfer " + commitment.resource_type.name + " from farm",
                            use_case=purch_use_case,
                            exchange_type=purch_exchange_type,
                            start_date=event_date,
                            context_agent=context_agent,
                            created_by=request.user,                
                        )
                        exchange.save()
                        resource = EconomicResource(
                            identifier=commitment.resource_type.name + " from farm",
                            resource_type=commitment.resource_type,
                            quantity=0,
                            exchange_stage=next_next_stage,
                            created_by=request.user
                        )
                        resource.save()
                        transfer_type = purch_exchange_type.transfer_types_non_reciprocal()[0]
                        xfer_name = transfer_type.name + " of " + commitment.resource_type.name
                        xfer = Transfer(
                            name=xfer_name,
                            transfer_type = transfer_type,
                            exchange = exchange,
                            context_agent = context_agent,
                            transfer_date = event_date,
                            created_by = request.user              
                        )
                        xfer.save() 
                        receipt_event = EconomicEvent(
                            event_type = receive_et,
                            event_date = event_date,
                            resource = resource,
                            resource_type = resource.resource_type,
                            exchange_stage=next_stage,
                            transfer=xfer,
                            commitment=commitment,
                            from_agent = commitment.from_agent,
                            to_agent = breakout_to_agent,
                            context_agent = context_agent,
                            quantity = breakout_quantity,
                            unit_of_quantity = resource.resource_type.unit,
                            value = value_stage_1,
                            unit_of_value = unit_of_value,
                            created_by = request.user,
                        )
                        receipt_event.save()
                        if paid_stage_1 == "paid":
                            if value_stage_1 > 0:
                                transfer_type = purch_exchange_type.transfer_types_reciprocal()[0]
                                xfer_name = transfer_type.name + " for " + commitment.resource_type.name
                                xfer = Transfer(
                                    name=xfer_name,
                                    transfer_type = transfer_type,
                                    exchange = exchange,
                                    context_agent = context_agent,
                                    transfer_date = event_date,
                                    created_by = request.user              
                                )
                                xfer.save()
                                pay_event_1 = EconomicEvent(
                                    event_type = give_et,
                                    event_date = event_date,
                                    resource_type = pay_rt,
                                    exchange_stage=next_stage,
                                    transfer=xfer,
                                    from_agent = receipt_event.to_agent,
                                    to_agent = receipt_event.from_agent,
                                    context_agent = context_agent,
                                    quantity = value_stage_1,
                                    unit_of_quantity = unit_of_value,
                                    value = value_stage_1,
                                    unit_of_value = unit_of_value,
                                    created_by = request.user,                        
                                )
                                pay_event_1.save()
                        elif paid_stage_1 == "later":
                            if value_stage_1 > 0:
                                transfer_type = purch_exchange_type.transfer_types_reciprocal()[0]
                                xfer_name = transfer_type.name + " for " + commitment.resource_type.name
                                xfer = Transfer(
                                    name=xfer_name,
                                    transfer_type = transfer_type,
                                    exchange = exchange,
                                    context_agent = context_agent,
                                    transfer_date = event_date,
                                    created_by = request.user              
                                )
                                xfer.save()
                                commit_1 = Commitment (
                                    commitment_date=event_date,
                                    event_type=give_et,
                                    exchange_stage=next_stage,
                                    transfer=xfer,
                                    due_date=event_date,
                                    from_agent=receipt_event.to_agent,
                                    to_agent=receipt_event.from_agent,
                                    context_agent=context_agent,
                                    resource_type=pay_rt,
                                    quantity=value_stage_1,
                                    unit_of_quantity=unit_of_value,
                                    value=value_stage_1,
                                    unit_of_value=unit_of_value,
                                    created_by=request.user,                        
                                )
                                commit_1.save()
                                
                        xfer_exchange = Exchange(
                            name="Transfer " + commitment.resource_type.name,
                            use_case=xfer_use_case,
                            start_date=event_date,
                            context_agent=context_agent,
                            exchange_type=xfer_exchange_type,
                            created_by=request.user,                
                        )
                        xfer_exchange.save()
                        transfer_type = xfer_exchange_type.transfer_types_non_reciprocal()[0]
                        xfer_name = transfer_type.name + " of " + commitment.resource_type.name
                        xfer = Transfer(
                            name=xfer_name,
                            transfer_type = transfer_type,
                            exchange = xfer_exchange,
                            context_agent = context_agent,
                            transfer_date = event_date,
                            created_by = request.user              
                        )
                        xfer.save()
                        xfer_event = EconomicEvent(
                            event_type = give_et,
                            event_date = event_date,
                            resource = resource,
                            resource_type = resource.resource_type,
                            exchange_stage=next_next_stage,
                            transfer=xfer,
                            from_agent = breakout_to_agent,
                            to_agent = to_agent,
                            context_agent = context_agent,
                            quantity = breakout_quantity,
                            unit_of_quantity = resource.resource_type.unit,
                            value = value_stage_2,
                            unit_of_value = unit_of_value,
                            created_by = request.user,
                        )
                        xfer_event.save()
                        xfer_event_receive = EconomicEvent(
                            event_type = receive_et,
                            event_date = event_date,
                            resource = resource,
                            resource_type = resource.resource_type,
                            exchange_stage=next_next_stage,
                            transfer=xfer,
                            from_agent = breakout_to_agent,
                            to_agent = to_agent,
                            context_agent = context_agent,
                            quantity = breakout_quantity,
                            unit_of_quantity = resource.resource_type.unit,
                            value = value_stage_2,
                            unit_of_value = unit_of_value,
                            created_by = request.user,
                        )
                        xfer_event_receive.save()
                        if paid_stage_2 == "paid":
                            if value_stage_2 > 0:
                                transfer_type = xfer_exchange_type.transfer_types_reciprocal()[0]
                                xfer_name = transfer_type.name + " for " + commitment.resource_type.name
                                xfer = Transfer(
                                    name=xfer_name,
                                    transfer_type = transfer_type,
                                    exchange = xfer_exchange,
                                    context_agent = context_agent,
                                    transfer_date = event_date,
                                    created_by = request.user              
                                )
                                xfer.save()
                                pay_event_2 = EconomicEvent(
                                    event_type = give_et,
                                    event_date = event_date,
                                    resource_type = pay_rt,
                                    transfer = xfer,
                                    exchange_stage=next_next_stage,
                                    from_agent = xfer_event.to_agent,
                                    to_agent = xfer_event.from_agent,
                                    context_agent = context_agent,
                                    quantity = value_stage_2,
                                    unit_of_quantity = unit_of_value,
                                    value = value_stage_2,
                                    unit_of_value = unit_of_value,
                                    created_by = request.user,                        
                                )
                                pay_event_2.save()
                                pay_event_2_receive = EconomicEvent(
                                    event_type = receive_et,
                                    event_date = event_date,
                                    resource_type = pay_rt,
                                    transfer = xfer,
                                    exchange_stage=next_next_stage,
                                    from_agent = xfer_event.to_agent,
                                    to_agent = xfer_event.from_agent,
                                    context_agent = context_agent,
                                    quantity = value_stage_2,
                                    unit_of_quantity = unit_of_value,
                                    value = value_stage_2,
                                    unit_of_value = unit_of_value,
                                    created_by = request.user,                        
                                )
                                pay_event_2_receive.save()
                        elif paid_stage_2 == "later":
                            if value_stage_2 > 0:
                                transfer_type = xfer_exchange_type.transfer_types_reciprocal()[0]
                                xfer_name = transfer_type.name + " for " + commitment.resource_type.name
                                xfer = Transfer(
                                    name=xfer_name,
                                    transfer_type = transfer_type,
                                    exchange = xfer_exchange,
                                    context_agent = context_agent,
                                    transfer_date = event_date,
                                    created_by = request.user              
                                )
                                xfer.save()
                                commit_2 = Commitment (
                                    commitment_date=event_date,
                                    event_type=give_et,
                                    transfer=xfer,
                                    exchange_stage=next_next_stage,
                                    due_date=event_date,
                                    from_agent=xfer_event.to_agent,
                                    to_agent=xfer_event.from_agent,
                                    context_agent=context_agent,
                                    resource_type=pay_rt,
                                    quantity=value_stage_2,
                                    unit_of_quantity=unit_of_value,
                                    value=value_stage_2,
                                    unit_of_value=unit_of_value,
                                    created_by=request.user,                        
                                )
                                commit_2.save()
                                                
                        consume_event = EconomicEvent(
                            event_type = consume_et,
                            event_date = event_date,
                            resource = resource,
                            resource_type = resource.resource_type,
                            exchange_stage=next_next_stage,
                            from_agent = to_agent,
                            to_agent = to_agent,
                            context_agent = context_agent,
                            quantity = breakout_quantity,
                            unit_of_quantity = resource.resource_type.unit,
                            created_by = request.user,
                        )
                        consume_event.save()
                        ces.append(consume_event)
            
            process = Process(
                name="Combined harvested: new lot",
                process_pattern=proc_pattern,
                end_date=event_date,
                start_date=event_date,
                started=event_date,
                context_agent=context_agent,
                finished=True,
                process_type=ProcessType.objects.get(name="Into Drying Room"),
                created_by=request.user,
            )
            process.save()
            for ce in ces:
                ce.process = process
                ce.save()
            prod_resource = EconomicResource(
                identifier=identifier,
                resource_type=commitment.resource_type,
                quantity=quantity,
                exchange_stage=next_next_stage,
                notes=notes,
                created_by=request.user                
            )
            prod_resource.save()
            prod_event = EconomicEvent(
                event_type = produce_et,
                event_date = event_date,
                resource = prod_resource,
                resource_type = prod_resource.resource_type,
                exchange_stage=next_next_stage,
                process = process,
                from_agent = to_agent,
                to_agent = to_agent,
                context_agent = context_agent,
                quantity = quantity,
                unit_of_quantity = prod_resource.resource_type.unit,
                description=notes,
                created_by = request.user,               
            )
            prod_event.save()
            
            #todo: put skip stage here!
            
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))

@login_required
def transfer_resource(request, context_agent_id, resource_id): #this is drying site to seller
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, id=resource_id)
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
        stage = ExchangeType.objects.get(name="Harvester to Drying Site")
        next_stage = get_next_stage(stage)
        prefix = resource.form_prefix()
        form = TransferFlowForm(prefix=prefix, data=request.POST)
        
        if form.is_valid():
            data = form.cleaned_data
            event_date = data["event_date"] 
            to_agent = data["to_agent"]
            quantity = data["quantity"]
            value = data["value"]
            if not value:
                value = 0
            unit_of_value = data["unit_of_value"]
            paid = data["paid"]
            notes = data["notes"]
            xfer_use_case = UseCase.objects.get(identifier="intrnl_xfer")
            exchange_type = next_stage
            give_et = EventType.objects.get(name="Give")
            receive_et = EventType.objects.get(name="Receive")
            pay_rt = EconomicResourceType.objects.filter(unit__unit_type="value")[0]
                        
            xfer_exchange = Exchange(
                name="Transfer " + resource.resource_type.name,
                use_case=xfer_use_case,
                start_date=event_date,
                context_agent=context_agent,
                exchange_type=exchange_type, 
                created_by=request.user,                
            )
            xfer_exchange.save()
            transfer_type = exchange_type.transfer_types_non_reciprocal()[0]
            xfer_name = transfer_type.name + " of " + resource.resource_type.name
            xfer = Transfer(
                name=xfer_name,
                transfer_type = transfer_type,
                exchange = xfer_exchange,
                context_agent = context_agent,
                transfer_date = event_date,
                created_by = request.user              
            )
            xfer.save() 
            xfer_give_event = EconomicEvent(
                event_type = give_et,
                event_date = event_date,
                resource = resource,
                resource_type = resource.resource_type,
                transfer=xfer,
                exchange_stage=next_stage,
                from_agent = resource.owner_based_on_exchange(),
                to_agent = to_agent,
                context_agent = context_agent,
                quantity = quantity,
                unit_of_quantity = resource.resource_type.unit,
                value = value,
                unit_of_value = unit_of_value,
                created_by = request.user,
            )
            xfer_give_event.save()
            xfer_rec_event = EconomicEvent(
                event_type = receive_et,
                event_date = event_date,
                resource = resource,
                resource_type = resource.resource_type,
                transfer=xfer,
                exchange_stage=next_stage,
                from_agent = resource.owner_based_on_exchange(),
                to_agent = to_agent,
                context_agent = context_agent,
                quantity = quantity,
                unit_of_quantity = resource.resource_type.unit,
                value = value,
                unit_of_value = unit_of_value,
                created_by = request.user,
            )
            xfer_rec_event.save()
            resource.exchange_stage = next_stage
            resource.quantity = quantity
            if resource.notes:
                resource.notes = resource.notes + "    -------    " + notes
            else:
                resource.notes = notes
            resource.save()
            if paid == "paid":
                if value > 0:
                    transfer_type = exchange_type.transfer_types_reciprocal()[0]
                    xfer_name = transfer_type.name + " for " + resource.resource_type.name
                    xfer = Transfer(
                        name=xfer_name,
                        transfer_type = transfer_type,
                        exchange = xfer_exchange,
                        context_agent = context_agent,
                        transfer_date = event_date,
                        created_by = request.user              
                    )
                    xfer.save()                     
                    pay_event = EconomicEvent(
                        event_type = give_et,
                        event_date = event_date,
                        resource_type = pay_rt,
                        transfer=xfer,
                        exchange_stage=next_stage,
                        from_agent = xfer_give_event.to_agent,
                        to_agent = xfer_give_event.from_agent,
                        context_agent = context_agent,
                        quantity = value,
                        unit_of_quantity = unit_of_value,
                        value = value,
                        unit_of_value = unit_of_value,
                        created_by = request.user,                        
                    )
                    pay_event.save()                     
                    pay_rec_event = EconomicEvent(
                        event_type = receive_et,
                        event_date = event_date,
                        resource_type = pay_rt,
                        transfer=xfer,
                        exchange_stage=next_stage,
                        from_agent = xfer_give_event.to_agent,
                        to_agent = xfer_give_event.from_agent,
                        context_agent = context_agent,
                        quantity = value,
                        unit_of_quantity = unit_of_value,
                        value = value,
                        unit_of_value = unit_of_value,
                        created_by = request.user,                        
                    )
                    pay_event.save()
            elif paid == "later":
                if value > 0:
                    transfer_type = exchange_type.transfer_types_reciprocal()[0]
                    xfer_name = transfer_type.name + " for " + resource.resource_type.name
                    xfer = Transfer(
                        name=xfer_name,
                        transfer_type = transfer_type,
                        exchange = xfer_exchange,
                        context_agent = context_agent,
                        transfer_date = event_date,
                        created_by = request.user              
                    )
                    xfer.save()   
                    commit = Commitment (
                        commitment_date=event_date,
                        event_type=give_et,
                        transfer=xfer,
                        exchange_stage=next_stage,
                        due_date=event_date,
                        from_agent=xfer_give_event.to_agent,
                        to_agent=xfer_give_event.from_agent,
                        context_agent=context_agent,
                        resource_type=pay_rt,
                        quantity=value,
                        unit_of_quantity=unit_of_value,
                        value=value,
                        unit_of_value=unit_of_value,
                        created_by=request.user,                        
                    )
                    commit.save()
                                                
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))

def combine_resources(request, context_agent_id, resource_type_id):
    if request.method == "POST":
        resource_type = get_object_or_404(EconomicResourceType, id=resource_type_id)
        context_agent = EconomicAgent.objects.get(id=context_agent_id)
        stage = ExchangeType.objects.get(name="Drying Site to Seller") #actually the stage here should be the process stage, and the rest should handle that
        prefix = resource_type.form_prefix()
        form = CombineResourcesForm(prefix=prefix, data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            event_date = data["event_date"] 
            resources = data["resources"]
            identifier = data["identifier"]
            notes = data["notes"]
            proc_use_case = UseCase.objects.get(identifier="rand")
            proc_pattern = None
            proc_patterns = [puc.pattern for puc in proc_use_case.patterns.all()]
            if proc_patterns:
                proc_pattern = proc_patterns[0]
            consume_et = EventType.objects.get(name="Resource Consumption")
            produce_et = EventType.objects.get(name="Resource Production")
            if resources:
                process = Process(
                    name="Combined: new lot",
                    process_pattern=proc_pattern,
                    end_date=event_date,
                    start_date=event_date,
                    started=event_date,
                    context_agent=context_agent,
                    finished=True,
                    process_type=ProcessType.objects.get(name="Combine Lots"),
                    created_by=request.user,
                )
                process.save()
                
                qty = 0
                for res in resources:
                    consume_event = EconomicEvent(
                        event_type = consume_et,
                        event_date = event_date,
                        resource = res,
                        resource_type = res.resource_type,
                        process=process,
                        exchange_stage=stage,
                        from_agent = res.owner_based_on_exchange(),
                        to_agent = res.owner_based_on_exchange(),
                        context_agent = context_agent,
                        quantity = res.quantity,
                        unit_of_quantity = res.resource_type.unit,
                        created_by = request.user,
                    )
                    consume_event.save()
                    qty += res.quantity
                    res.quantity = 0
                    res.save()
                prod_resource = EconomicResource(
                    identifier=identifier,
                    resource_type=resource_type,
                    quantity=qty,
                    exchange_stage=stage,
                    notes=notes,
                    created_by=request.user                
                )
                prod_resource.save()
                prod_event = EconomicEvent(
                    event_type = produce_et,
                    event_date = event_date,
                    resource = prod_resource,
                    resource_type = prod_resource.resource_type,
                    exchange_stage=stage,
                    process = process,
                    from_agent = res.owner_based_on_exchange(),
                    to_agent = res.owner_based_on_exchange(),
                    context_agent = context_agent,
                    quantity = qty,
                    unit_of_quantity = prod_resource.resource_type.unit,
                    description=notes,
                    created_by = request.user,               
                )
                prod_event.save()
            
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))
    
@login_required
def change_available(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    context_agent_id = commitment.context_agent.id 
    if request.method == "POST":
        prefix = commitment.form_prefix()
        form = CommitmentForm(instance=commitment, data=request.POST, prefix=prefix)
        if form.is_valid():
            data = form.cleaned_data
            form.save()
            commitment.unit_of_quantity = commitment.resource_type.unit
            commitment.save()
        zero_form = ZeroOutForm(prefix=prefix, data=request.POST)
        if zero_form.is_valid():
            zero_data = zero_form.cleaned_data
            zero_out = zero_data["zero_out"]
            if zero_out == True:
                commitment.finished = True
                commitment.save()
                
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))
    
@login_required
def delete_farm_commitment(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    context_agent_id = commitment.context_agent.id
    if commitment.is_deletable():
        commitment.delete()
                
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))
    
@login_required
def undo_col2(request, resource_id):
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    context_agent_id = default_context_agent().id
    flows = resource.incoming_value_flows()
    for item in flows:
        if item.class_label() == "Economic Event":
            if item.commitment:
                commit = item.commitment
                commit.finished = False
                commit.save()
        item.delete()
    
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))
    
@login_required
def undo_col3(request, resource_id):
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    context_agent_id = default_context_agent().id
    flows = resource.incoming_value_flows()
    #todo: I'm not sure how to delete the right rows without going too far back in the chain......
    #for item in flows:
    #    if item.class_label() == "Economic Event":
    #        item.delete()
    
    return HttpResponseRedirect('/%s/%s/'
        % ('board/dhen-board', context_agent_id))

