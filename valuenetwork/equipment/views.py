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
from valuenetwork.equipment.forms import *
from valuenetwork.valueaccounting.views import get_agent


def consumable_formset(consumable_rt, data=None):
    ConsumableFormSet = formset_factory(form=ConsumableForm, extra=0)
    init = []
    consumable_resources = EconomicResource.objects.filter(resource_type=consumable_rt)
    for res in consumable_resources:
        d = {"resource_id": res.id,}
        init.append(d)
    formset = ConsumableFormSet(initial=init, data=data)
    for form in formset:
        id = int(form["resource_id"].value())
        resource = EconomicResource.objects.get(id=id)
        form.identifier = resource.identifier
    return formset

@login_required
def log_equipment_use(request, scenario, equip_resource_id, context_agent_id, pattern_id,
    sale_pattern_id, equip_svc_rt_id, equip_fee_rt_id, tech_rt_id, consumable_rt_id,
    payment_rt_id, tech_rel_id, ve_id, va_id, price_id, part_rt_id, cite_rt_id
):
    #scenario: 1=commercial, 2=project, 3=fablab, 4=techshop, 5=other
    equipment = get_object_or_404(EconomicResource, id=equip_resource_id)
    equipment_svc_rt = get_object_or_404(EconomicResourceType, id=equip_svc_rt_id)
    equipment_fee_rt = get_object_or_404(EconomicResourceType, id=equip_fee_rt_id)
    technician_rt = EconomicResourceType.objects.get(id=tech_rt_id)
    payment_rt = EconomicResourceType.objects.get(id=payment_rt_id)
    context_agent = get_object_or_404(EconomicAgent, id=context_agent_id)
    pattern = ProcessPattern.objects.get(id=pattern_id)
    sale_pattern = ProcessPattern.objects.get(id=sale_pattern_id)
    consumable_rt = EconomicResourceType.objects.get(id=consumable_rt_id)
    logged_on_agent = get_agent(request)
    ve = ValueEquation.objects.get(id=ve_id)
    mtnce_virtual_account = EconomicResource.objects.get(id=va_id)
    tech_rel_type = AgentResourceRoleType.objects.get(id=tech_rel_id)
    init = {"event_date": datetime.date.today(), "from_agent": logged_on_agent}
    equip_form = EquipmentUseForm(equip_resource=equipment, context_agent=context_agent, tech_type=tech_rel_type, initial=init, data=request.POST or None)
    formset = consumable_formset(consumable_rt=consumable_rt)
    process_form = ProcessForm(data=request.POST or None)

    if request.method == "POST":
        if equip_form.is_valid():
            data = equip_form.cleaned_data
            input_date = data["event_date"]
            who = data["from_agent"]
            quantity = data["quantity"]
            technician = data["technician"]
            technician_quantity = data["technician_hours"]
            et_ship = EventType.objects.get(name="Shipment")
            et_use = EventType.objects.get(name="Resource use")
            et_consume = EventType.objects.get(name="Resource Consumption")
            et_work = EventType.objects.get(name="Time Contribution")
            et_create = EventType.objects.get(name="Resource Production")
            et_fee = EventType.objects.get(name="Fee")
            et_transfer = EventType.objects.get(name="Transfer")
            total_price = 0
            next_process = None
            if scenario == '2':
                if process_form.is_valid():
                    pdata = process_form.cleaned_data
                    next_process = pdata["process"]

            process = Process(
                name="Paid service: Use of " + equipment.identifier,
                end_date=input_date,
                start_date=input_date,
                process_pattern=pattern,
                created_by=request.user,
                context_agent=context_agent,
                started=input_date,
                finished=True,
            )
            process.save()
            formset = consumable_formset(data=request.POST, consumable_rt=consumable_rt)
            for form in formset.forms:
                if form.is_valid():
                    data_cons = form.cleaned_data
                    if data_cons:
                        qty = data_cons["quantity"]
                        if qty:
                            if qty > 0:
                                res_id = data_cons["resource_id"]
                                consumable = EconomicResource.objects.get(id=int(res_id))
                                consume_event = EconomicEvent(
                                    event_type = et_consume,
                                    event_date = input_date,
                                    resource = consumable,
                                    resource_type = consumable.resource_type,
                                    process = process,
                                    from_agent = context_agent,
                                    to_agent = context_agent,
                                    context_agent = context_agent,
                                    quantity = qty,
                                    unit_of_quantity = consumable_rt.unit,
                                    unit_of_value = consumable.resource_type.unit_of_price,
                                    created_by = request.user,
                                )
                                consume_event.save()
                                consumable.quantity = consumable.quantity - qty
                                consumable.save()
            if technician and technician_quantity > 0:
                tech_event = EconomicEvent(
                    event_type = et_work,
                    event_date = input_date,
                    resource_type = technician_rt,
                    process = process,
                    from_agent = technician,
                    to_agent = context_agent,
                    context_agent = process.context_agent,
                    quantity = technician_quantity,
                    unit_of_quantity = technician_rt.unit,
                    unit_of_value = technician_rt.unit_of_price,
                    created_by = request.user,
                    is_contribution = True,
                )
                tech_event.save()
                total_price += tech_event.value
            if scenario == '3' or scenario == '4': #fablab, techshop
                use_event = EconomicEvent(
                    event_type = et_use,
                    event_date = input_date,
                    resource_type = equipment.resource_type,
                    resource = equipment,
                    process = process,
                    from_agent = context_agent,
                    to_agent = who,
                    context_agent = context_agent,
                    quantity = quantity,
                    unit_of_quantity = equipment.resource_type.unit_of_use,
                    price = quantity * ResourceTypeSpecialPrice.objects.get(id=price_id).price_per_unit,
                    unit_of_price = equipment.resource_type.unit_of_price,
                    created_by = request.user,
                )
                use_event.save()
                total_price += use_event.price

            #ephemeral output resource
            printer_service = EconomicResource(
                resource_type=equipment_svc_rt,
                identifier="Temporary service resource 3D printing " + str(input_date) + " for " + who.nick,
                quantity=1,
                value_per_unit = total_price,
                created_by=request.user,
            )
            printer_service.save()
            output_event = EconomicEvent(
                event_type = et_create,
                event_date = input_date,
                resource_type = equipment_svc_rt,
                resource = printer_service,
                process = process,
                from_agent = context_agent,
                to_agent = context_agent,
                context_agent = process.context_agent,
                quantity = 1,
                unit_of_quantity = equipment_svc_rt.unit,
                unit_of_value = equipment_svc_rt.unit_of_price,
                created_by = request.user,
            )
            output_event.save()
            total_value = output_event.resource.compute_value_per_unit(value_equation=ve)
            #if scenario == '3' or scenario == '4': #fablab, techshop
            #    total_value += use_event.price
            output_event.value = total_value
            output_event.save()

            if scenario == '2' and next_process:
                cust = next_process.context_agent
            else:
                cust = who
            sale = Exchange(
                name="Use of " + equipment.identifier,
                process_pattern=sale_pattern,
                use_case=UseCase.objects.get(identifier="sale"),
                start_date=input_date,
                customer=cust,
                context_agent=context_agent,
                created_by=request.user,
            )
            sale.save()
            #todo: hardcoded fee event for now
            mtnce_fee_event = EconomicEvent(
                event_type = et_fee,
                event_date = input_date,
                resource_type = equipment_fee_rt,
                resource = mtnce_virtual_account,
                exchange = sale,
                from_agent = context_agent,
                to_agent = cust,
                context_agent = context_agent,
                quantity = quantity * equipment_fee_rt.price_per_unit,
                unit_of_quantity = equipment_fee_rt.unit_of_price,
                value = quantity * equipment_fee_rt.price_per_unit,
                unit_of_value = equipment_fee_rt.unit_of_price,
                created_by = request.user,
            )
            mtnce_fee_event.save()
            mtnce_virtual_account.quantity = mtnce_virtual_account.quantity + mtnce_fee_event.quantity
            mtnce_virtual_account.save()
            ship_event = EconomicEvent(
                event_type = et_transfer,
                event_date = input_date,
                resource_type = equipment_svc_rt,
                resource = printer_service,
                exchange = sale,
                from_agent = context_agent,
                to_agent = cust,
                context_agent = context_agent,
                quantity = 1,
                unit_of_quantity = equipment_svc_rt.unit,
                value = total_value,
                unit_of_value = equipment_svc_rt.unit_of_price,
                created_by = request.user,
            )
            ship_event.save()
            #if scenario == '3' or scenario == '4':
            #    use_ship_event = EconomicEvent(
            #        event_type = et_ship,
            #        event_date = input_date,
            #        resource_type = use_svc_rt,
            #        exchange = sale,
            #        from_agent = context_agent,
            #        to_agent = who,
            #        context_agent = context_agent,
            #        quantity = quantity,
            #        unit_of_quantity = use_svc_rt.unit,
            #        value = quantity * use_svc_rt.price_per_unit,
            #        unit_of_value = use_svc_rt.unit_of_price,
            #        created_by = request.user,
            #    )
            #    use_ship_event.save()
            printer_service.quantity = 0
            printer_service.save()

            if scenario == '1':
                next_process = Process(
                    name="Make commercial 3D printed part",
                    end_date=input_date,
                    start_date=input_date,
                    process_pattern=pattern,
                    created_by=request.user,
                    context_agent=context_agent,
                    started=input_date,
                    finished=True,
                )
                next_process.save()
                part_rt = EconomicResourceType.objects.get(id=part_rt_id)
                printed_part = EconomicResource(
                    resource_type=part_rt,
                    identifier="Commercial 3D printed part " + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
                    quantity=1,
                    created_by=request.user,
                )
                printed_part.save()
                output_part_event = EconomicEvent(
                    event_type = et_create,
                    event_date = input_date,
                    resource_type = part_rt,
                    resource = printed_part,
                    process = next_process,
                    from_agent = context_agent,
                    to_agent = context_agent,
                    context_agent = context_agent,
                    quantity = 1,
                    unit_of_quantity = part_rt.unit,
                    unit_of_value = part_rt.unit_of_price,
                    created_by = request.user,
                )
                output_part_event.save()
            if scenario == '2' or scenario == '1':
                if next_process:
                    use_event = EconomicEvent(
                        event_type = et_use,
                        event_date = input_date,
                        resource_type = equipment.resource_type,
                        resource = equipment,
                        process = next_process,
                        from_agent = context_agent,
                        to_agent = next_process.context_agent,
                        context_agent = next_process.context_agent,
                        quantity = quantity,
                        unit_of_quantity = equipment.resource_type.unit_of_use,
                        value = 0,
                        unit_of_value = payment_rt.unit,
                        created_by = request.user,
                    )
                    use_event.save()
                    svc_input_event = EconomicEvent(
                        event_type = et_consume,
                        event_date = input_date,
                        resource_type = equipment_svc_rt,
                        resource = printer_service,
                        process = next_process,
                        from_agent = next_process.context_agent,
                        to_agent = next_process.context_agent,
                        context_agent = next_process.context_agent,
                        quantity = 1,
                        unit_of_quantity = equipment_svc_rt.unit,
                        unit_of_value = equipment_svc_rt.unit_of_price,
                        created_by = request.user,
                    )
                    svc_input_event.save()

            if next_process:
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/'
                    % ('equipment/pay-equipment-use', scenario, sale.id, process.id, payment_rt_id, equip_resource_id, mtnce_fee_event.id, ve_id, quantity, who.id, next_process.id, int(cite_rt_id)))
            else:
                return HttpResponseRedirect('/%s/%s/%s/%s/%s/%s/%s/%s/%s/%s/'
                    % ('equipment/pay-equipment-use', scenario, sale.id, process.id, payment_rt_id, equip_resource_id, mtnce_fee_event.id, ve_id, quantity, who.id))

    return render_to_response("equipment/log_equipment_use.html", {
        "equip_form": equip_form,
        "process_form": process_form,
        "formset": formset,
        "equipment": equipment,
        "consumable_rt": consumable_rt,
        "scenario": scenario,
    }, context_instance=RequestContext(request))

@login_required
def pay_equipment_use(request, scenario, sale_id, process_id, payment_rt_id, equip_resource_id,
    mtnce_fee_event_id, ve_id, use_qty, who_id, next_process_id=None, cite_rt_id=None
):
    #scenario: 1=commercial, 2=project, 3=fablab, 4=techshop, 5=other
    sale = get_object_or_404(Exchange, id=sale_id)
    process = get_object_or_404(Process, id=process_id)
    payment_rt = EconomicResourceType.objects.get(id=payment_rt_id)
    payment_unit = payment_rt.unit
    equipment = EconomicResource.objects.get(id=equip_resource_id)
    ve = ValueEquation.objects.get(id=ve_id)
    ve_exchange = None
    who = EconomicAgent.objects.get(id=who_id)
    paid=False
    ship_events = sale.transfer_events()
    sale_total_no_fee = 0
    for se in ship_events:
        sale_total_no_fee += se.value
    #ship_events = sale.shipment_events()
    #for se in ship_events:
    #    sale_total_no_fee += se.value
    mtnce_event = EconomicEvent.objects.get(id=mtnce_fee_event_id)
    mtnce_use = str(use_qty) + " " + equipment.resource_type.unit_of_use.abbrev
    sale_total = sale_total_no_fee + mtnce_event.quantity
    sale_total_formatted = "".join([payment_rt.unit.symbol, str(sale_total.quantize(Decimal('.01'), rounding=ROUND_UP))])
    pay_form = PaymentForm(data=request.POST or None)

    if request.method == "POST":
        if pay_form.is_valid():
            data = pay_form.cleaned_data
            payment_method = data["payment_method"]

            cr_et = EventType.objects.get(name="Cash Receipt")
            money_resource = sale.context_agent.virtual_accounts()[0]
            cr_event = EconomicEvent(
                event_type = cr_et,
                event_date = sale.start_date,
                exchange = sale,
                resource_type = payment_rt, #todo: fix?? ends up being canadian dollars and a virtual account
                resource = money_resource,
                from_agent = who,
                to_agent = sale.context_agent,
                context_agent = sale.context_agent,
                quantity = sale_total,
                unit_of_quantity = payment_unit,
                value = sale_total,
                unit_of_value = payment_unit,
                event_reference = payment_method,
                created_by = request.user,
                is_contribution = True,
            )
            cr_event.save()
            money_resource.quantity = money_resource.quantity + sale_total
            money_resource.save()
            paid = True

            use_case = UseCase.objects.get(identifier="distribution")
            dist_pattern = ProcessPattern.objects.usecase_patterns(use_case)[0]
            ve_exchange = Exchange(name="Distribution for use of " + equipment.identifier,
                process_pattern=dist_pattern,
                use_case=use_case,
                start_date=sale.start_date,
                context_agent=sale.context_agent,
                created_by=request.user,
            )
            crs = [cr_event]
            serialized_filters = {}
            dist_shipment = ship_events[0]
            buckets = ve.buckets.all()
            for bucket in buckets:
                if bucket.filter_method:
                    #'{"shipments": [4836], "method": "Shipment"}'}
                    ser_string = "".join([
                        '{"shipments": [',
                        str(dist_shipment.id),
                        '], "method": "Shipment"}'
                        ])
                    serialized_filters[bucket.id] = ser_string

                    #data[bucket.id] = [dist_shipment,]
                    #bucket_form = bucket.filter_entry_form(data=request.POST or None)
                    #if bucket_form.is_valid():
                    #    ser_string = bucket_data = bucket_form.serialize()
                    #    serialized_filters[bucket.id] = ser_string
                    #    bucket.form = bucket_form
            ve_exchange = ve.run_value_equation_and_save(
                cash_receipts=crs,
                exchange=ve_exchange,
                money_resource=money_resource,
                amount_to_distribute=sale_total_no_fee,
                serialized_filters=serialized_filters)
            #todo: this should send notifications some day?
            #for event in ve_exchange.distribution_events():
            #    send_distribution_notification(event)

    return render_to_response("equipment/pay_equipment_use.html", {
        "process": process,
        "mtnce_event": mtnce_event,
        "mtnce_use": mtnce_use,
        "sale_total": sale_total_formatted,
        "payment_unit": payment_unit,
        "paid": paid,
        "equipment": equipment,
        "ve_exchange": ve_exchange,
        "ve": ve,
        "pay_form": pay_form,
        "scenario": scenario,
        "next_process_id": next_process_id,
        "cite_rt_id": cite_rt_id,
    }, context_instance=RequestContext(request))

@login_required
def log_additional_inputs(request, cite_rt_id, process_id):
    process = get_object_or_404(Process, id=process_id)
    cite_rt = EconomicResourceType.objects.get(id=cite_rt_id)
    cite_unit = cite_rt.unit_of_use
    cite_form = AdditionalCitationForm(prefix="cite", cite_rt=cite_rt, data=request.POST or None)
    work_form = AdditionalWorkForm(prefix = "work", data=request.POST or None)
    done = None

    if request.method == "POST":
        cite = request.POST.get("cite")
        work = request.POST.get("work")
        done = request.POST.get("done")
        input_date = datetime.date.today()
        if cite:
            if cite_form.is_valid():
                cite_et = EventType.objects.get(name="Citation")
                citation = cite_form.save(commit=False)
                citation.event_type = cite_et
                citation.resource_type = citation.resource.resource_type
                citation.event_date = input_date
                citation.from_agent = process.context_agent
                citation.to_agent = process.context_agent
                citation.process = process
                citation.context_agent = process.context_agent
                citation.unit_of_quantity = cite_rt.unit_of_use
                citation.created_by = request.user
                citation.save()
        elif work:
            if work_form.is_valid():
                work_et = EventType.objects.get(name="Time Contribution")
                work_event = work_form.save(commit=False)
                work_event.event_type = work_et
                work_event.event_date = input_date
                work_event.to_agent = process.context_agent
                work_event.process = process
                work_event.context_agent = process.context_agent
                work_event.unit_of_quantity = work_event.resource_type.unit
                work_event.is_contribution = True
                work_event.created_by = request.user
                work_event.save()


    return render_to_response("equipment/log_additional_inputs.html", {
        "process": process,
        "cite_form": cite_form,
        "work_form": work_form,
        "cite_unit": cite_unit,
        "done": done,
    }, context_instance=RequestContext(request))
