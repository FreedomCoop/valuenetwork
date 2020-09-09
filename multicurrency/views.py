from decimal import Decimal

from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.utils.translation import ugettext_lazy as _

from valuenetwork.valueaccounting.models import EconomicAgent
from multicurrency.models import MulticurrencyAuth, MultiwalletTransaction
from multicurrency.forms import MulticurrencyAuthForm, \
    MulticurrencyAuthDeleteForm, MulticurrencyAuthCreateForm, PaySharesForm
from multicurrency.utils import ChipChapAuthConnection, ChipChapAuthError
from work.models import JoinRequest


def get_agents(request, agent_id):

    user_agent = None
    try:
        au = request.user.agent
        user_agent = au.agent
    except:
        pass
    if user_agent and user_agent.id == int(agent_id):
        return True, user_agent, user_agent

    agent = None
    try:
        agent = EconomicAgent.objects.get(id=agent_id)
    except:
        pass
    if user_agent and agent and agent in user_agent.managed_projects():
        return True, user_agent, agent

    return False, user_agent, agent


@login_required
def auth(request, agent_id):
    access_permission, user_agent, agent = get_agents(request, agent_id)
    if not access_permission:
        raise PermissionDenied

    if request.method == 'POST':
        form = MulticurrencyAuthForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['loginname']
            acs = MulticurrencyAuth.objects.filter(auth_user__iexact=name)
            if acs:
                messages.error(request, _("This login name already exists."))
                return redirect('multicurrency_auth', agent_id=agent_id)

            password = form.cleaned_data['wallet_password']
            oauth = None
            connection = ChipChapAuthConnection.get()
            try:
                response = connection.new_client(name, password)
            except ChipChapAuthError:
                messages.error(request, _('Authentication failed.'))
                return redirect('multicurrency_auth', agent_id=agent_id)
            try:
                oauth = MulticurrencyAuth.objects.create(
                    agent=agent,
                    auth_user=name,
                    access_key=response['access_key'],
                    access_secret=response['access_secret'],
                    created_by=request.user,
                )
            except:
                messages.error(
                    request, _('Something was wrong saving your data.'))
            if oauth:
                messages.success(
                    request,
                    _('Your BotC-Wallet user has been succesfully authenticated.'))

            for req in agent.project_join_requests.all():
                if req.project.agent.need_multicurrency():
                    req.multiwallet_user(name)

            if oauth:
                return redirect('multicurrency_history', agent_id=agent_id, oauth_id=oauth.id)

            return redirect('multicurrency_auth', agent_id=agent_id)
        else:
            messages.error(request, "The form has errors: "+str(form.errors))
            return redirect('multicurrency_auth', agent_id=agent_id)



    else:
        try:
            oauths = MulticurrencyAuth.objects.filter(agent=agent)
        except MulticurrencyAuth.DoesNotExist:
            oauths = None

        jnreq = None
        if agent:
            for req in agent.project_join_requests.all():
                if req.project.agent.need_multicurrency():
                    jnreq = req

        form = MulticurrencyAuthForm()
        delete_form = MulticurrencyAuthDeleteForm()
        create_form = MulticurrencyAuthCreateForm(initial={
            'username': agent.nick,
            'email': agent.email,
            })
        return render(request, 'multicurrency_auth.html', {
            'agent': agent,
            'user_agent': user_agent,
            'oauths': oauths,
            'jn_req': jnreq,
            'oauth_form': form,
            'create_form': create_form,
            'delete_form': delete_form,
            })


@login_required
def deleteauth(request, agent_id, oauth_id):
    access_permission, user_agent, agent = get_agents(request, agent_id)
    if not access_permission:
        raise PermissionDenied

    try:
        oauths = MulticurrencyAuth.objects.filter(agent=agent)
    except MulticurrencyAuth.DoesNotExist:
        raise Http404

    oauth = None
    for o in oauths:
        if o.id == int(oauth_id):
            oauth = o

    if not oauth:
        raise Http404

    if request.method == 'POST':
        form = MulticurrencyAuthDeleteForm(request.POST)
        if form.is_valid():
            oauth.delete()
            messages.success(
                request,
                _('Your BotC-Wallet user has been succesfully logged out.'))
    return redirect('multicurrency_auth', agent_id=agent_id)


@login_required
def createauth(request, agent_id):
    access_permission, user_agent, agent = get_agents(request, agent_id)
    if not access_permission:
        raise PermissionDenied

    if request.method == 'POST':
        form = MulticurrencyAuthCreateForm(request.POST)
        if form.is_valid():
            connection = ChipChapAuthConnection.get()
            try:
                response = connection.new_chipchap_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    company_name=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    repassword=form.cleaned_data['password'],
                )
            except ChipChapAuthError as e:
                messages.error(
                    request,
                    _('Something was wrong creating new BotC-wallet user.')
                    + ' (' + str(e) + ')')
                return redirect('multicurrency_auth', agent_id=agent_id)
            try:
                response2 = connection.new_client(
                    form.cleaned_data['username'],
                    form.cleaned_data['password'])
            except ChipChapAuthError:
                messages.success(
                    request,
                    _('Your BotC-Wallet account has been succesfully created. Check '
                      'your email and follow the link to confirm your email in'
                      ' BotC-Wallet system. Come back here with your credentials,'
                      ' and authenticate your new user in the bottom form.'))
                # messages.error(request, _('Authentication failed.'))

                for req in agent.project_join_requests.all():
                    if req.project.agent.need_multicurrency():
                        req.multiwallet_user(form.cleaned_data['username'])

                return redirect('multicurrency_auth', agent_id=agent_id)
            try:
                MulticurrencyAuth.objects.create(
                    agent=agent,
                    auth_user=form.cleaned_data['username'],
                    access_key=response2['access_key'],
                    access_secret=response2['access_secret'],
                    created_by=request.user,
                )
            except:
                messages.error(
                    request, _('Something was wrong saving your data.'))

    return redirect('multicurrency_auth', agent_id=agent_id)


@login_required
def history(request, agent_id, oauth_id):
    access_permission, user_agent, agent = get_agents(request, agent_id)
    if not access_permission:
        raise PermissionDenied

    try:
        oauths = MulticurrencyAuth.objects.filter(agent=agent)
    except MulticurrencyAuth.DoesNotExist:
        raise PermissionDenied

    oauth = None
    for o in oauths:
        if o.id == int(oauth_id):
            oauth = o

    if not oauth:
        raise PermissionDenied

    items_per_page = 25
    try:
        limit = int(request.GET.get('limit', str(items_per_page)))
        offset = int(request.GET.get('offset', '0'))
    except:
        limit = items_per_page
        offset = 0

    connection = ChipChapAuthConnection.get()
    try:
        tx_list, balance = connection.wallet_history(
            oauth.access_key,
            oauth.access_secret,
            limit=limit,
            offset=offset,
        )
    except ChipChapAuthError:
        messages.error(
            request, _('Something was wrong connecting to BotC-wallet.'))
        return redirect('multicurrency_auth', agent_id=agent_id)

    if tx_list['status'] == 'ok' and balance['status'] == 'ok':
        balance_clean = []
        for bal in balance['data']:
            if int(bal['balance']) != 0:
              if not bal['id'] == 'multidivisa':
                clean_bal = Decimal(int(bal['balance']))/(10**int(bal['scale']))
                clean_currency = bal['currency'] if bal['currency'] != 'FAC' else 'FAIR'
                balance_clean.append(str(clean_bal.quantize(Decimal('0.01'))) + ' ' + clean_currency)
        methods = {
            'fac': 'FAIR',
            'halcash_es': 'Halcash ES',
            'exchange_EURtoFAC': 'EUR to FAIR',
            'sepa': 'SEPA',
            'wallet_to_wallet': 'wallet to wallet',
        }
        table_caption = "Showing " + str(tx_list['data']['start'] + 1) + " to "\
            + str(tx_list['data']['end']) + " of " + str(tx_list['data']['total'])\
            + " movements"
        table_headers = [_('Created'), _('Updated'), _('Concept'), _('Method'), _('IO'), _('Account or Address'), _('Amount'), _('Unit'), _("Status")]
        table_rows = []
        paginator = {}
        if tx_list['data']['total'] > 0:
            for tx in tx_list['data']['elements']:
                created = parse_datetime(tx['created']) if 'created' in tx else '--'
                updated = parse_datetime(tx['updated']) if 'updated' in tx else '--'
                concept = '--'
                address = '--'
                io = '-'
                unit = '--'
                if 'pay_in_info' in tx:
                    io = '<span class="complete">&lt;&lt;</span>'
                    concept = tx['pay_in_info']['concept'] if 'concept' in tx['pay_in_info'] else '--'
                    address = tx['pay_in_info']['address'] if 'address' in tx['pay_in_info'] else '--'
                    if address == '--' and 'data_out' in tx:
                        address = tx['data_out']['received_from'] if 'received_from' in tx['data_out'] else '--'
                elif 'pay_out_info' in tx:
                    io = '<span class="error">&gt;&gt;</span>'
                    concept = tx['pay_out_info']['concept'] if 'concept' in tx['pay_out_info'] else '--'
                    address = tx['pay_out_info']['address'] if 'address' in tx['pay_out_info'] else '--'
                    if address == '--':
                        address = tx['pay_out_info']['beneficiary'] if 'beneficiary' in tx['pay_out_info'] else '--'
                method = tx['method'] if 'method' in tx else '--'
                if method in methods: method = methods[method]
                if 'ANDROID FAIR APP' in concept:
                    concept = _("FairPay: payed with your NFC card")
                if 'ANDROID APP' in concept:
                    concept = _("FairPay: charged via NFC card")
                if 'Payment' == concept and method == 'FAIR':
                    concept = _("FairPay: charged via QR code")
                #import pdb; pdb.set_trace()
                amount = Decimal(tx['amount']) if 'amount' in tx else Decimal('0')
                scale = int(tx['scale']) if 'scale' in tx else 0
                amount = amount/(10**scale)
                if 'type' in tx:
                    amount = -amount if tx['type'] == 'out' else amount
                currency = tx['currency'] if 'currency' in tx else '--'
                if currency == "FAC": currency = "FAIR"
                status = str(tx['status'])
                if request.user.is_superuser:
                    status = str(tx['id'])
                multitxs = MultiwalletTransaction.objects.filter(tx_id=tx['id'])
                if multitxs:
                    status = ''
                    exch = None
                    for mtx in multitxs:
                        if hasattr(mtx.event, 'exchange'):
                            exch = mtx.event.exchange
                        elif hasattr(mtx.event, 'transfer') and hasattr(mtx.event.transfer, 'exchange'):
                            exch = mtx.event.transfer.exchange
                        if exch:
                            status += "<b><a href='"+reverse("exchange_logging_work", args=(agent_id, 0, exch.id))+"'>"
                            status += str(_("Exchange")) #exch.status()
                            status += "</a></b> "
                            if hasattr(exch, 'join_request'):
                                status += "/ <b><a href='"+reverse("project_feedback", args=(agent_id, exch.join_request.id))+"'>"
                                status += str(_("Feedback"))
                                status += "</a></b>"
                            break
                table_rows.append([
                    created.strftime('%Y/%m/%d-%H:%M'),
                    updated.strftime('%Y/%m/%d-%H:%M'),
                    concept,
                    method,
                    io,
                    address,
                    str(round(amount, scale)), #.quantize(Decimal('0.01'))),
                    currency,
                    status
                ])
                if tx_list['data']['total'] > tx_list['data']['end']:
                    paginator['next'] = {
                        'limit': str(limit),
                        'offset': str(tx_list['data']['end'])
                    }
                if tx_list['data']['start'] >= limit:
                    paginator['previous'] = {
                        'limit': str(limit),
                        'offset': str(int(tx_list['data']['start']) - limit)
                    }
        return render(request, 'multicurrency_history.html', {
            'balance_clean': balance_clean,
            'table_caption': table_caption,
            'table_headers': table_headers,
            'table_rows': table_rows,
            'auth_user': oauth.auth_user,
            'oauth_id': oauth.id,
            'jn_req': oauth.related_join_request(),
            'agent': agent,
            'offset': offset,
            'paginator': paginator,
        })
    else:
        messages.error(
            request,
            _('Something was wrong connecting to BotC-wallet.'))
        return redirect('multicurrency_auth', agent_id=agent_id)



@login_required
def authpayment(request, agent_id):
    if request.method == 'POST':
        form = PaySharesForm(data=request.POST or None)
        if form.is_valid():
          data = form.cleaned_data
          jnreq = None
          if agent_id:
            access_permission, user_agent, agent = get_agents(request, agent_id)
            if not access_permission:
                raise PermissionDenied
            #import pdb; pdb.set_trace()
            try:
                oauths = MulticurrencyAuth.objects.filter(agent=agent)
            except MulticurrencyAuth.DoesNotExist:
                raise Http404
            oauth = None
            for o in oauths:
                if o.id == int(data['auth_id']):
                    oauth = o
            if not oauth:
                raise Http404
            if 'jnreq_id' in data and data['jnreq_id']:
                jnreq = JoinRequest.objects.get(id=data['jnreq_id'])
                pend = jnreq.payment_pending_to_pay()
                unit = jnreq.payment_unit().abbrev
                wuser = jnreq.multiwallet_user()
                if not unit == data['unit']:
                    raise ValidationError("unit is not the same")
                if not str(pend) == str(data['amount']):
                    raise ValidationError("amount is not the same (pend:"+str(pend)+" / amount:"+str(data['amount'])+")")
                if not wuser == oauth.auth_user:
                    raise ValidationError("multiwallet user is not the same !")
                balobj = oauth.balance_obj()
                if unit in balobj:
                    if balobj[unit] < pend:
                        raise ValidationError("not enough funds ?")
                else:
                    raise ValidationError("not found unit in balances ?")

                connection = ChipChapAuthConnection.get()
                try:
                    share_payment = connection.send_w2w(
                        oauth.access_key,
                        oauth.access_secret,
                        unit,
                        pend,
                        # TODO add wuser botc and scale
                    )
                except ChipChapAuthError:
                    messages.error(
                        request, _('Something was wrong connecting to BotC-wallet.'))
                    return redirect('multicurrency_auth', agent_id=agent_id)

                if share_payment['status'] == 'ok':
                    for payd in share_payment['data']:
                        print(payd)


            messages.success( request,
                _('The payment is done! Transfered')+" "+str(data['amount'])+" "+data['unit']+" "+str(_("to"))+" "+str(jnreq.project.agent.name)+".")

            return redirect('project_feedback', agent_id=agent_id, join_request_id=jnreq.id)
        else:
            messages.success( request,
                _('Error in the transfer form: ')) #+str(form))

    return redirect('members_agent', agent_id=agent_id)
