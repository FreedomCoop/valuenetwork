from __future__ import unicode_literals
from decimal import Decimal

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User

from valuenetwork.valueaccounting.models import EconomicAgent

class MulticurrencyAuth(models.Model):
    agent = models.ForeignKey(EconomicAgent, on_delete=models.CASCADE)
    auth_user = models.CharField(max_length=100, editable=False)
    access_key = models.CharField(max_length=100, editable=False)
    access_secret = models.CharField(max_length=100, editable=False)
    created_by = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    updated = models.DateField(auto_now=True)

    def related_join_request(self):
        jnreq = None
        if self.agent:
            for req in self.agent.project_join_requests.all():
                if req.project.agent.need_multicurrency():
                    jnreq = req
        return jnreq

    def balance_obj(self):
        from multicurrency.utils import ChipChapAuthConnection
        unitbalance = {}
        connection = ChipChapAuthConnection.get()
        try:
            balance = connection.wallet_balance(
                self.access_key,
                self.access_secret,
            )
        except:
            return None
        if balance['status'] == 'ok':
            for bal in balance['data']:
                if int(bal['balance']) != 0:
                    if not bal['id'] == 'multidivisa':
                        clean_bal = Decimal(int(bal['balance']))/(10**int(bal['scale']))
                        clean_currency = bal['currency'] if bal['currency'] != 'FAC' else 'FAIR'
                        unitbalance[clean_currency.lower()] = clean_bal
        return unitbalance

    def pay_shares_html(self, jn_req, user=None):
        saldo = 0
        unit = None
        out_text = ''
        reqdata = {}
        #payform = None
        balobj = self.balance_obj()
        punit = jn_req.payment_unit()
        if not punit:
            out_text = _("Error: payment unit not found! ")
        else:
            if not balobj:
                out_text = _("Error: balance object not found! ")
            else:
                if punit.abbrev in balobj:
                    saldo = balobj[punit.abbrev]
                    unit = punit.abbrev
                else:
                    out_text = _("Error: not found unit in balance object! ")

            if saldo:
                pend = jn_req.payment_pending_to_pay()
                if saldo < pend:
                    out_text = str(_("The balance in your wallet needs some more "))+unit
                else:
                    out_text = '<b>'+str(_("You can pay the shares now!"))+'</b>'
                    if user and user.is_superuser:
                        out_text += ' '+str(saldo)+" "+punit.symbol+" >= "+str(pend)+" "+punit.symbol
                        if jn_req.payment_payed_amount():
                            out_text += " ("+str(_("paid:"))+str(jn_req.payment_payed_amount())+")"
                    #out_text += "&nbsp; <a href='"+str()+"' class='btn btn-primary'>"+str(_("Transfer"))+" "+str(pend)+" "+punit.symbol+" "+str(_("to"))+" "+jn_req.project.agent.nick+"</a>"
                    reqdata = {
                        'jnreq_id': jn_req.id,
                        'auth_id': self.id,
                        'amount': pend,
                        'unit': unit,
                    }
                    #print reqdata
                    #payform = PaySharesForm(data=reqdata, initial=reqdata) #initial={'jnreq': jn_req, 'auth': self, 'amount': pend, 'unit': unit})
            elif balobj:
                out_text = _("Not enough balance in your wallet for the chosen currency:")+' <b>'+str(punit)+'</b>'
            else:
                out_text = _("Error retrieving your balance... ")
                if user and user.is_superuser:
                    out_text += "(punit: "+str(punit) #balance['status'])
        return out_text, reqdata
