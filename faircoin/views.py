# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from decimal import Decimal
import json

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.forms import ValidationError
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings

from valuenetwork.valueaccounting.models import EconomicResource, EconomicEvent, EconomicResourceType, Help
from valuenetwork.valueaccounting.forms import EconomicResourceForm
from valuenetwork.valueaccounting.service import ExchangeService
from faircoin import utils as faircoin_utils
from faircoin.forms import SendFairCoinsForm
from faircoin.decorators import confirm_password

FAIRCOIN_DIVISOR = Decimal("100000000.00")

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

@login_required
def manage_faircoin_account(request, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    user_agent = get_agent(request)
    if not user_agent or not (resource.owner() == user_agent or resource.owner() in user_agent.managed_projects()):
        raise Http404

    send_coins_form = None
    is_wallet_address = None
    limit = 0
    confirmed_balance = None
    unconfirmed_balance = None
    faircoin_account = False
    payment_due = False
    share_price = False
    number_of_shares = False
    can_pay = False
    candidate_membership = None
    wallet = faircoin_utils.is_connected()
    if wallet:
        is_wallet_address = faircoin_utils.is_mine(resource.faircoin_address.address)
        if is_wallet_address:
            send_coins_form = SendFairCoinsForm(agent=resource.owner())
            try:
                balances = faircoin_utils.get_address_balance(resource.faircoin_address.address)
                unconfirmed_balance =  Decimal(balances[1]) / FAIRCOIN_DIVISOR
                unconfirmed_balance += resource.balance_in_tx_state_new()
                confirmed_balance = Decimal(balances[0]) / FAIRCOIN_DIVISOR
                if unconfirmed_balance < 0:
                    confirmed_balance += unconfirmed_balance
                elif unconfirmed_balance == 0:
                    unconfirmed_balance = confirmed_balance
            except:
                confirmed_balance = "Not accessible now"
                unconfirmed_balance = "Not accessible now"
        else:
            wallet = False
            if resource.is_address_requested(): is_wallet_address = True

    project = None
    for req in resource.owner().project_join_requests.all():
      candidate_membership = resource.owner().candidate_membership(req.project.agent)
      if candidate_membership:
        obj = req.payment_option()
        faircoin_account = resource.owner().faircoin_resource()
        if faircoin_account and wallet and obj['key'] == 'faircoin' and req.project.shares_account_type():
            share = req.project.shares_type() #EconomicResourceType.objects.membership_share()
            share_price = share.price_per_unit
            number_of_shares = req.pending_shares() #resource.owner().number_of_shares()
            share_price = share_price * number_of_shares
            project = req.project
            payment_due = True
            if resource.owner().owns_resource_of_type(req.project.shares_account_type()) and share_price == 0:
                payment_due = False
            if confirmed_balance and confirmed_balance != "Not accessible now":
                can_pay = confirmed_balance >= share_price

    return render(request, "faircoin/faircoin_account.html", {
        "resource": resource,
        "photo_size": (128, 128),
        "agent": resource.owner(),
        "wallet": wallet,
        "send_coins_form": send_coins_form,
        "is_wallet_address": is_wallet_address,
        "confirmed_balance": confirmed_balance,
        "unconfirmed_balance": unconfirmed_balance,
        "faircoin_account": faircoin_account,
        "candidate_membership": candidate_membership,
        "payment_due": payment_due,
        "share_price": share_price,
        "number_of_shares": number_of_shares,
        "can_pay": can_pay,
        "project": project,
        "help": get_help("faircoin account"),
    })

def validate_faircoin_address_for_worker(request):
    data = request.GET
    address = data["to_address"].strip()
    answer = faircoin_utils.is_valid(address)
    if answer == False:
        answer = "Invalid FairCoin address"
    response = json.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")

@login_required
def change_faircoin_account(request, resource_id):
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        form = EconomicResourceForm(data=request.POST, instance=resource)
        if form.is_valid():
            data = form.cleaned_data
            resource = form.save(commit=False)
            resource.changed_by=request.user
            resource.save()
            return HttpResponseRedirect('/%s/%s/'
                % ('faircoin/manage-faircoin-account', resource_id))
        else:
            raise ValidationError(form.errors)

@login_required
def transfer_faircoins(request, resource_id):
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, id=resource_id)
        agent = get_agent(request)
        to_agent = request.POST["to_user"]
        send_coins_form = SendFairCoinsForm(data=request.POST, agent=resource.owner())
        if send_coins_form.is_valid():
            data = send_coins_form.cleaned_data
            address_end = data["to_address"]
            quantity = data["quantity"]

            if ("send_all" in request.POST) and request.POST['send_all']: sub_fee = True
            else: sub_fee = data['minus_fee']
            address_origin = resource.faircoin_address.address
            if address_origin and address_end and quantity:
                exchange_service = ExchangeService.get()
                exchange = exchange_service.send_faircoins(
                    from_agent = resource.owner(),
                    recipient = address_end,
                    qty = quantity,
                    resource = resource,
                    notes = data['description'],
                    minus_fee = sub_fee,
                )
                return HttpResponseRedirect('/%s/%s/'
                    % ('faircoin/faircoin-history', resource.id))
        else:
            raise ValidationError(send_coins_form.errors)
    else:
        raise Http404
    return HttpResponseRedirect('/%s/%s/'
        % ('faircoin/manage-faircoin-account', resource.id))


@login_required
def faircoin_history(request, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    agent = get_agent(request)
    wallet = faircoin_utils.is_connected()
    confirmed_balance = None
    unconfirmed_balance = None
    if wallet:
        if resource.is_wallet_address():
            exchange_service = ExchangeService.get()
            exchange_service.include_blockchain_tx_as_event(resource.owner(), resource)
            try:
                balances = faircoin_utils.get_address_balance(resource.faircoin_address.address)
                confirmed_balance = Decimal(balances[0]) / FAIRCOIN_DIVISOR
                unconfirmed_balance =  Decimal(balances[0] + balances[1]) / FAIRCOIN_DIVISOR
                unconfirmed_balance += resource.balance_in_tx_state_new()
            except:
                confirmed_balance = "Not accessible now"
                unconfirmed_balance = "Not accessible now"
        else:
            wallet = False
    event_list = resource.events.all()
    init = {"quantity": resource.quantity,}
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
    if resource.owner() == agent or resource.owner() in agent.managed_projects() or agent.is_staff():
        return render(request, "faircoin/faircoin_history.html", {
            "resource": resource,
            "agent": agent,
            "confirmed_balance": confirmed_balance,
            "unconfirmed_balance": unconfirmed_balance,
            "unit": unit,
            "events": events,
            "wallet": wallet,
        })
    else:
        return render(request, 'work/no_permission.html')


@login_required
def edit_faircoin_event_description(request, resource_id):
    agent = get_agent(request)
    resource = EconomicResource.objects.get(id=resource_id)
    if request.method == "POST":
        data = request.POST
        evid = data['id']
        ntext = data['value']
        event = EconomicEvent.objects.get(id=evid)
        event.description = ntext
        event.save()
        return HttpResponse("Ok", content_type="text/plain")
    return HttpResponse("Fail", content_type="text/plain")

from django.views.generic.edit import UpdateView
from .forms import ConfirmPasswordForm

class ConfirmPasswordView(UpdateView):
    form_class = ConfirmPasswordForm
    template_name = 'faircoin/confirm_password.html'

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        return self.request.get_full_path()
