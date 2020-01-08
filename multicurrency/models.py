from __future__ import unicode_literals, division
from decimal import Decimal
import requests
import logging
loger = logging.getLogger("multicurrency")

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError

from valuenetwork.valueaccounting.models import EconomicAgent, EconomicEvent
from work.utils import remove_exponent

DIVISOR = 100000000
if hasattr(settings, 'DECIMALS'):
    DECIMALS = settings.DECIMALS
else:
    DECIMALS = Decimal('1.000000000')
if hasattr(settings, 'MARGIN'):
    MARGIN = settings.MARGIN
else:
    MARGIN = Decimal("0.000001")

if 'faircoin' in settings.INSTALLED_APPS:
    from faircoin.models import FC2_TX_URL
    if not 'url_fair_tx' in settings.MULTICURRENCY:
        settings.MULTICURRENCY['url_fair_tx'] = FC2_TX_URL
        #settings.MULTICURRENCY['url_fair_tx_json'] = FC2_TX_URL

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
                    out_text = str(_("The balance in your wallet needs some more "))+unit.upper()
                else:
                    out_text = '<b>'+str(_("You can pay the shares now!"))+'</b>'
                    if user and user.is_superuser:
                        out_text += ' '+str(saldo)+" "+punit.symbol+" >= "+str(remove_exponent(pend))+" "+punit.symbol
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
                    out_text += "(punit: "+str(punit)+")" #balance['status'])
        return out_text, reqdata


class BlockchainTransaction(models.Model):
    event = models.OneToOneField(EconomicEvent, on_delete=models.CASCADE, verbose_name=_('event'), related_name='chain_transaction')
    tx_hash = models.CharField(_("Transaction Hash"), max_length=96, editable=False) # 64 btc+fair, 66 eth
    from_address = models.CharField(_('From Address'), max_length=128, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    to_address = models.CharField(_('To Address'), max_length=128, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    #amount = models.DecimalField(_('Quantity'), max_digits=20, decimal_places=9, default=0) # is already in the event
    tx_fee = models.DecimalField(_('Transaction Fee'), max_digits=20, decimal_places=9, default=0)
    #include_fee = models.BooleanField('Quantity includes fee', default=False) # comparing events qty we see which is lower due the fee
    # will be true for sender give event, and false for receiver event

    def unit(self):
        if self.event.unit_of_quantity:
            return self.event.unit_of_quantity
        else:
            raise ValidationError("There's no unit_of_quantity in the related event: "+str(self.event))

    def chain_link(self):
        unit = self.unit()
        if unit.abbrev:
            key = 'url_'+unit.abbrev+'_tx'
            url = ''
            if key in settings.MULTICURRENCY:
                url = settings.MULTICURRENCY[key]
                return url+self.tx_hash
            else:
                raise ValidationError("The settings haven't any key like: "+key)
        else:
            raise ValidationError("There's no abbrev in the related unit: "+str(unit))

    def update_data(self, realamount=None): #, oauth=None):
        url = None
        json = None
        inputs = []
        input_vals = []
        outputs = []
        output_vals = []
        outvals = []
        mesg = ''
        if realamount:
            realamount = Decimal(realamount)
        """if not oauth:
            mesg += "Without a oauth we can't update_data!"
            self.event.delete()
            self.delete()
            return mesg"""

        if not self.tx_fee:
            unit = self.unit()
            msg = None
            if unit and unit.abbrev:
                if unit.abbrev == 'fair' and 'faircoin' in settings.INSTALLED_APPS:
                    from faircoin import utils as faircoin_utils
                    wallet = faircoin_utils.is_connected()
                    if wallet:
                        trans = faircoin_utils.send_command('get_transaction', [self.tx_hash])
                        if trans != 'ERROR':
                            json = {'hash': self.tx_hash,
                                    'out': [],
                                    'inputs': [],}
                            #mesg += "Res: (outs) "
                            for output in trans['outputs']:
                                #mesg += output['address']+" ("+str(output['value'])+"), "
                                json['out'].append({'addr': output['address'], 'value':output['value']})
                            #mesg += " - (inputs) "
                            for inp in trans['inputs']:
                                amount = 0
                                #inputs.append(inp['address']
                                if 'prevout_hash' in inp:
                                    intx = faircoin_utils.send_command('get_transaction', [inp['prevout_hash']])
                                    if intx != 'ERROR':
                                        for out in intx['outputs']:
                                            if out['address'] == inp['address']:
                                                amount = int(out['value'])
                                    else:
                                        amount = 'error'
                                #mesg += inp['address']+" ("+str(amount)+"), "
                                if amount and not amount == 'error':
                                    json['inputs'].append({'prev_out':{'addr': inp['address'], 'value': amount}}) #inp['value']}})
                                else:
                                    self.event.delete()
                                    self.delete()
                                    return mesg
                            #mesg += "<br>"+str(trans)
                        else:
                            mesg += trans
                            self.event.delete()
                            self.delete()
                            return mesg
                    else:
                        mesg += "There's no faircoin wallet to check the transaction."
                        self.event.delete()
                        self.delete()
                        return mesg
                else:
                    key = 'url_'+unit.abbrev+'_tx_json'
                    if key in settings.MULTICURRENCY:
                        url = settings.MULTICURRENCY[key]+self.tx_hash
                        #print("URL: "+url)
                        txobj = requests.get(url)
                        if int(txobj.status_code) == 200:
                            try:
                                json = txobj.json()
                            except:
                                mesg += ("Can't decode tx request as json! txobj:"+str(txobj))
                                for prop in txobj:
                                    mesg += "<br>"+str(prop)
                                self.event.delete()
                                self.delete()
                                return mesg
                        else:
                            mesg += ("Error retrieving the txobj: "+str(txobj)+"<br>")
                    else:
                        mesg += ("The key is not in settings: "+str(key)+"<br>")


                    """from multicurrency.utils import ChipChapAuthConnection
                    connection = ChipChapAuthConnection.get()
                    json, msg = connection.check_payment(
                            oauth.access_key,
                            oauth.access_secret,
                            unit.abbrev,
                            self.tx_hash,
                    )
                    if msg:
                        mesg += ("Error checking the tx: <b>"+msg+"</b>")
                        #for prop in txobj:
                        #    mesg += "<br>"+str(prop)
                        self.event.delete()
                        self.delete()
                        return mesg"""

                if json:
                    if 'hash' in json: #.status == "ok":
                        if json['hash'] == self.tx_hash:
                            if 'inputs' in json:
                                for inp in json['inputs']:
                                    if 'prev_out' in inp:
                                        if 'addr' in inp['prev_out']:
                                            inputs.append(inp['prev_out']['addr'])
                                            input_vals.append(inp['prev_out']['value'])
                                        else:
                                            print("tx has no addr in inputs prev_out? inp['prev_out']:"+str(inp['prev_out']))
                                            mesg += ("tx has no addr in inputs prev_out? inp['prev_out']:"+str(inp['prev_out']))
                                    else:
                                        print("tx has no prev_out? inp:"+str(inp))
                                        mesg += ("tx has no prev_out? inp:"+str(inp))
                            else:
                                print("tx has no inputs? json:"+str(json))
                                mesg += ("tx has no inputs? json:"+str(json))
                            if 'out' in json:
                                for out in json['out']:
                                    if 'addr' in out:
                                        if out['addr'] in inputs:
                                            print("tx skip output to same input")
                                        else:
                                            outputs.append(out['addr'])
                                            outvals.append(out['value'])
                                        output_vals.append(out['value'])
                                    else:
                                        print("tx output without address? out:"+str(out))
                                        mesg += ("tx output without address? out:"+str(out))
                            else:
                                print("tx without outputs? json:"+str(json))
                                mesg += ("tx without outputs? json:"+str(json))

                            total_in = sum(inp for inp in input_vals)
                            total_out = sum(out for out in output_vals)
                            if total_in and total_out:
                                fee = total_in - total_out
                                if fee > 0:
                                    outfee = Decimal(str(fee / DIVISOR)).quantize(DECIMALS) #, settings.CRYPTO_DECIMALS)
                                    print("outfee:"+str(outfee)+" type:"+str(type(outfee)))
                                    #outfee = remove_exponent(outfee)
                                    #print("outfee2:"+str(outfee)+" type:"+str(type(outfee)))
                                    self.tx_fee = outfee
                                else:
                                    raise ValidationError("negative fee?? json:"+str(json))

                                validval = 0
                                for outval in outvals: #) > 1:
                                    #mesg += ("Not yet suported various outputs for the crypto TX: "+str(json))
                                    #raise ValidationError("Not yet suported various outputs for the crypto TX: "+str(json))

                                    if self.event.event_type.name == 'Give':
                                        val = Decimal( (outval + fee) / DIVISOR).quantize(DECIMALS) #, settings.CRYPTO_DECIMALS)
                                        if realamount and not (realamount+outfee) == val:
                                            if (realamount+outfee) < val:
                                                rest = val - (realamount+outfee)
                                            else:
                                                rest = (realamount+outfee) - val
                                            if rest > MARGIN:
                                                print("ev-give: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found+fee:"+str(val)+" (type:"+str(type(val))+") - declared+fee:"+str(realamount+outfee)+"(type:"+str(type(realamount))+")")
                                                #mesg += ("(give event): Declared amount and chain discovered amount are too different!! fee:"+str(outfee)+", found+fee:"+str(val)+" <> declared+fee:"+str(realamount+outfee)+" (rest:"+str(remove_exponent(rest))+")") #+"(type:"+str(type(realamount))+")")
                                                #self.event.delete()
                                                #self.delete()
                                            else:
                                                validval = val
                                                print("ev-give: Declared amount and chain discovered amount are not equal but are close. Allow? rest:"+str(rest)+" fee:"+str(outfee))

                                                if not self.event.quantity == val:
                                                    print("UPDATE ev give quantity! qty:"+str(self.event.quantity)+" val:"+str(val)+" (type:"+str(type(val))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    loger.info("UPDATE ev give quantity! qty:"+str(self.event.quantity)+" val:"+str(val)+" type:"+str(type(val)))
                                                    self.event.quantity = val
                                                    self.event.save()
                                                if self.event.commitment:
                                                    if not self.event.commitment.quantity == val:
                                                        print("UPDATE ev give commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                        loger.info("UPDATE ev give commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                        self.event.commitment.quantity = val
                                                        self.event.commitment.save()
                                                break

                                    elif self.event.event_type.name == 'Receive':
                                        val = Decimal( outval / DIVISOR).quantize(DECIMALS) #, settings.CRYPTO_DECIMALS)
                                        if realamount and not realamount == val:
                                            if realamount < val:
                                                rest = val - realamount
                                            else:
                                                rest = realamount - val
                                            if rest > MARGIN:
                                                print("ev-receive: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found:"+str(val)+" (type:"+str(type(val))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                #mesg += ("(receive event): Declared amount and chain discovered amount are too different!! fee:"+str(outfee)+", found:"+str(val)+" <> declared:"+str(realamount)+" (rest:"+str(remove_exponent(rest))+")") #+"(type:"+str(type(realamount))+")")
                                                #self.event.delete()
                                                #self.delete()
                                            else:
                                                validval = val
                                                print("ev-receive: Declared amount and chain discovered amount are not equal but are close. Allow? rest:"+str(rest)+" fee:"+str(outfee))

                                                if not self.event.quantity == val:
                                                    print("UPDATE ev receive quantity! qty:"+str(self.event.quantity)+" val:"+str(val)+" (type:"+str(type(val))+") - realamount:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    loger.info("UPDATE ev receive quantity! qty:"+str(self.event.quantity)+" val:"+str(val))
                                                    self.event.quantity = val
                                                    self.event.save()
                                                if self.event.commitment:
                                                    if not self.event.commitment.quantity == val:
                                                        print("UPDATE ev receive commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                        loger.info("UPDATE ev receive commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                        self.event.commitment.quantity = val
                                                        self.event.commitment.save()
                                                break
                                    else:
                                        raise ValidationError("TX event type not supported: "+str(self.event.event_type.name))

                                if not validval:
                                    mesg += "Not found an output with a similar amount? "+str(outvals)
                                    self.event.delete()
                                    self.delete()
                                    return mesg
                            else:
                                raise ValidationError("not tx totals? total_in:"+str(total_in)+" total_out:"+str(total_out))

                            if self.event:
                                self.from_address = ' '.join(inputs)
                                self.to_address = ' '.join(outputs)
                                self.save()
                            #import pdb; pdb.set_trace()

                            return mesg

                        else:
                            print("tx hash is not the same?? json:"+str(json))
                            mesg += ("tx hash is not the same?? json:"+str(json))
                    else:
                        print('tx without hash?? json:'+str(json))
                        mesg += ('tx without hash?? json:'+str(json))
                else:
                    print("No JSON for the tx, delete event! ")
                    mesg += ("No JSON for the tx, delete event! ")
                    if self.event:
                        self.event.delete()
                        self.delete()
            else:
                if self.event:
                    mesg += ("There's no unit_of_quantity or abbrev in the related event: "+str(self.event))
                    self.event.delete()
                    self.delete()
                else:
                    mesg += ("This tx don't have a related event??")
        else:
            mesg += 'This tx already has the tx_fee!'

        return mesg
