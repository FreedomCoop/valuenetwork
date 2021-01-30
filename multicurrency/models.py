
from decimal import Decimal
import requests
import logging
loger = logging.getLogger("multicurrency")
from datetime import date, datetime

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages

from valuenetwork.valueaccounting.models import EconomicAgent, EconomicEvent, EventType
from work.utils import remove_exponent

DIVISOR = 100000000
if hasattr(settings, 'DECIMALS'):
    DECIMALS = settings.DECIMALS
else:
    DECIMALS = Decimal('1.000000000')

et_give = EventType.objects.get(name="Give")
et_receive = EventType.objects.get(name="Receive")

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
                    #print(reqdata)
                    #payform = PaySharesForm(data=reqdata, initial=reqdata) #initial={'jnreq': jn_req, 'auth': self, 'amount': pend, 'unit': unit})
            elif balobj:
                out_text = _("Not enough balance in your wallet for the chosen currency:")+' <b>'+str(punit.name)+'</b>'
            else:
                out_text = _("Error retrieving your balance... ")
                if user and user.is_superuser:
                    out_text += "(punit: "+str(punit.name)+")" #balance['status'])
        return out_text, reqdata



class MultiwalletTransaction(models.Model):
    event = models.OneToOneField(EconomicEvent, on_delete=models.CASCADE, verbose_name=_('event'), related_name='multiwallet_transaction')
    tx_id = models.CharField(_("Multiwallet Transaction ID"), max_length=96, editable=False) # 64 btc+fair, 66 eth
    status = models.CharField(_('Status'), max_length=32, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    sent_to = models.CharField(_('Sent to username'), max_length=128, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    method = models.CharField(_("Method"), max_length=128, blank=True, null=True)
    #amount = models.DecimalField(_('Quantity'), max_digits=20, decimal_places=9, default=0) # is already in the event
    tx_fee = models.DecimalField(_('Transaction Fee'), max_digits=20, decimal_places=9, default=0)

    def unit(self):
        if self.event.unit_of_quantity:
            return self.event.unit_of_quantity
        else:
            raise ValidationError("There's no unit_of_quantity in the related event: "+str(self.event))

    def amount(self):
        return self.event.quantity

    def update_data(self, oauth, request, realamount=None):
        url = None
        json = None
        inputs = []
        input_vals = []
        outputs = []
        output_vals = []
        outvals = []
        mesg = ''
        if realamount:
            if not isinstance(realamount, Decimal):
                realamount = Decimal(realamount)
        else:
            pass #mesg += "Without a realamount we can't check the payment"
        if not oauth:
            mesg += "Without an oauth we can't update_data!"
            return mesg

        unit = self.unit()
        msg = None
        if unit and unit.abbrev:
            if unit.abbrev == 'fair':
                if self.event.to_agent.nick == "BotC": # now only to pay botc shares
                    from multicurrency.utils import ChipChapAuthConnection
                    connection = ChipChapAuthConnection.get()
                    json, msg = connection.check_payment(
                        oauth.access_key,
                        oauth.access_secret,
                        unit.abbrev,
                        self.tx_id,
                    )
                    if msg:
                        if msg == 'success' or msg == 'ok':
                            pass
                        else:
                            mesg += str(_("Error checking the Transaction:"))+" <b>"+str(msg)+"</b> "
                    if json:
                        if not json['currency'] == 'FAC':
                            mesg += str(_("The multiwallet tx found is not FairCoin?"))
                            return mesg #pass #raise ValidationError("The multiwallet tx found is not FairCoin ?? ")

                        self.method = json['method']
                        if 'data_out' in json: # exchanges don't have 'data_out'
                            if 'sent_to' in json['data_out']:
                                self.sent_to = json['data_out']['sent_to']
                            else:
                                loger.info("No sent_to in tx data_out ?? "+str(json['data_out']))
                        self.status = json['status']
                        divisor = Decimal(10 ** json['scale'])
                        fees = Decimal(json['variable_fee']) + Decimal(json['fixed_fee'])
                        if fees:
                            self.tx_fee = remove_exponent(fees / divisor).quantize(settings.DECIMALS)
                            print("tx fees:"+str(fees)+" fee:"+str(self.tx_fee)) #
                        else:
                            self.tx_fee = 0
                        total = Decimal(json['total'] / divisor).quantize(settings.DECIMALS)
                        if total < 0:
                            total = total * -1

                        if total == realamount:
                            if fees:
                                print("Found tx fees:"+str(fees)+" fee:"+str(self.tx_fee)) #+" tx:"+str(self))
                                mesg += ("Found Fees ?? ("+str(self.tx_fee)+") abort...") #+" tx:"+str(self))
                                loger.warning("Found Fees ?? ("+str(self.tx_fee)+") Abort... for mTx:"+str(self.id)+" ev:"+str(self.event.id)+" txid:"+str(self.tx_id))

                            if not self.event.quantity == total:
                                messages.info(request, _("Updated the event Quantity ({0}) to: {1} / ").format(self.event.quantity, total))
                                self.event.quantity = total

                            if not self.event.event_reference == self.tx_id:
                                messages.info(request, _("Updated the event Reference ({0}) to: {1} / ").format(self.event.event_reference, self.tx_id))
                                self.event.event_reference = self.tx_id

                            dat = json['created']
                            pos = dat.find("+")
                            if not pos == -1:
                                dat = dat[:pos]
                            dt = datetime.strptime(dat, '%Y-%m-%dT%H:%M:%S')
                            dat = dt.date()
                            if not self.event.event_date == dat:
                                messages.info(request, _("Updated the event Date ({0}) to: {1} / ").format(self.event.event_date, dat))
                                self.event.event_date = dat

                            if mesg == '':
                                self.event.save()
                                self.save()

                        else:
                            mesg += str(_("The received amount ({0}) is not like the one found ({1}).").format(realamount, total))
                    else: # no json
                        mesg += "No transaction found with this ID."
                else: # not botc
                    mesg += "No BotC related ??"
            else: # not fair
                mesg += "No 'faircoin' unit ??"
        else: # not unit
            mesg += "No unit or abbrev ??"
        return mesg


class BlockchainTransaction(models.Model):
    event = models.OneToOneField(EconomicEvent, on_delete=models.CASCADE, verbose_name=_('event'), related_name='chain_transaction')
    tx_hash = models.CharField(_("Transaction Hash"), max_length=96, editable=False) # 64 btc+fair, 66 eth
    from_address = models.CharField(_('From Address'), max_length=128, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    to_address = models.CharField(_('To Address'), max_length=128, blank=True, null=True) # 33 btc, 34 fair, 42 eth
    #amount = models.DecimalField(_('Quantity'), max_digits=20, decimal_places=9, default=0) # is already in the event
    tx_fee = models.DecimalField(_('Transaction Fee'), max_digits=20, decimal_places=9, default=0)
    #used_ratio = models.DecimalField(_('Used unit ratio'), max_digits=20, decimal_places=9, blank=True, null=True)

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

    def related_join_request(self):
        if not self.event.exchange and self.event.transfer.exchange:
            loger.info("Fix missing event.exchange from event.transfer.exchange !! ev:"+str(self.event.id))
            print("Fix missing event.exchange from event.transfer.exchange !! ev:"+str(self.event.id))
            self.event.exchange = self.event.transfer.exchange
            self.event.save()

        if self.event.exchange:
            if hasattr(self.event.exchange, 'join_request') and self.event.exchange.join_request:
                return self.event.exchange.join_request
            else:
                loger.info("The related exchange is not related any join_request! ex:"+str(self.event.exchange.id))
                print("The related exchange is not related any join_request! ex:"+str(self.event.exchange.id))
        else:
            loger.info("Error: An event without any relted exchange? ev:"+str(self.event.id))
            print("Error: An event without any relted exchange? ev:"+str(self.event.id))
        return None

    def mirror(self):
        mirs = BlockchainTransaction.objects.filter(tx_hash=self.tx_hash).exclude(id=self.id)
        if len(mirs) == 1:
            return mirs[0]
        elif mirs:
            #loger.error("More than one mirror of BlockchainTransaction? id:"+str(self.id)+' mirs:'+str(mirs))
            #print("More than one mirror of BlockchainTransaction? id:"+str(self.id)+' mirs:'+str(mirs))
            raise ValidationError("More than one mirror of BlockchainTransaction? id:"+str(self.id)+' mirs:'+str(mirs))
        return None

    def update_data(self, realamount=None): #, oauth=None):
        url = None
        json = None
        inputs = []
        input_vals = []
        outputs = []
        output_vals = []
        outvals = []
        mesg = ''
        mirbtx = self.mirror()
        if realamount:
            realamount = Decimal(realamount)
        if not self.tx_fee:
            if not realamount and self.event.quantity > 0:
                print("Cancel update_data ? "+str(self)+' self.event.quantity:'+str(self.event.quantity))
                realamount = self.event.quantity
                #return mesg # cancel update?
            unit = self.unit()
            msg = None
            evtmir = None
            if unit and unit.abbrev:
                proj = None
                proaddr = None
                proaddrar = None
                if self.event.to_agent and hasattr(self.event.to_agent, 'project'):
                    proj = self.event.to_agent.project
                    evtmir = self.event.mirror_event()

                if unit.abbrev == 'fair':
                    if self.event.to_agent.nick == "BotC":
                        raise ValidationError("This model is not appropiate to store the Multiwallet ID! ")

                    elif 'faircoin' in settings.INSTALLED_APPS:
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
                        mesg += "Is faircoin but the faircoin app is not installed"
                        self.event.delete()
                        self.delete()
                        return mesg

                else: # not fairs!  BTC and co

                    proaddr = proj.cryptoAddress(unit.abbrev)
                    proaddrar = proj.cryptoAddrArr(unit.abbrev)
                    if not proaddr and proaddrar:
                        proaddr = proaddrar[0]
                    foundadd = None
                    foundval = None
                    key = 'url_'+unit.abbrev+'_tx_json'
                    if key in settings.MULTICURRENCY:
                        url = settings.MULTICURRENCY[key]+self.tx_hash
                        print(":: Retrieve chain data at URL: "+url)
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


                if json:
                    if 'hash' in json: #.status == "ok":
                        if json['hash'] == self.tx_hash:
                            if 'inputs' in json:
                                for inp in json['inputs']:
                                    if 'prev_out' in inp:
                                        if 'hash' in inp['prev_out']:
                                            inputs.append(inp['prev_out']['hash'])
                                            input_vals.append(inp['prev_out']['value'])
                                        else:
                                            print("tx has no hash in inputs prev_out? inp['prev_out']:"+str(inp['prev_out']))
                                            mesg += ("tx has no hash in inputs prev_out? inp['prev_out']:"+str(inp['prev_out']))
                                    else:
                                        print("tx has no prev_out? inp:"+str(inp))
                                        mesg += ("tx has no prev_out? inp:"+str(inp))
                            else:
                                print("tx has no inputs? json:"+str(json))
                                mesg += ("tx has no inputs? json:"+str(json))
                            if 'out' in json:
                                for out in json['out']:
                                    if 'hash' in out:
                                        if out['hash'] in inputs:
                                            print("tx skip output to same input")
                                        else:
                                            if proj and proaddr:
                                                if out['hash'] == proaddr or out['hash'] in proj.cryptoAddrArr(unit.abbrev):
                                                    print("Found proj crypto address!!")
                                                    foundadd = out['hash']
                                                    foundval = out['value']
                                                    #outvals.append(out['value'])
                                            outputs.append(out['hash'])
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
                                if fee and fee > 0:
                                    outfee = Decimal(str(fee / DIVISOR)).quantize(DECIMALS) #, settings.CRYPTO_DECIMALS)
                                    print("outfee:"+str(outfee)+" type:"+str(type(outfee)))
                                    #outfee = remove_exponent(outfee)
                                    #print("outfee2:"+str(outfee)+" type:"+str(type(outfee)))

                                    #self.tx_fee = outfee
                                    #self.mirror().tx_fee = outfee
                                else:
                                    raise ValidationError("negative fee?? json:"+str(json))

                                validval = 0
                                for outval in outvals: #) > 1:
                                    #mesg += ("Not yet suported various outputs for the crypto TX: "+str(json))
                                    #raise ValidationError("Not yet suported various outputs for the crypto TX: "+str(json))

                                    if self.event.event_type.name == 'Give':
                                        val = Decimal( (outval) / DIVISOR).quantize(DECIMALS) # ( + fee), settings.CRYPTO_DECIMALS)
                                        if realamount:
                                          print("- Is the same (give) realamount:"+str(realamount)+" val:"+str(val))
                                          loger.info("- Is the same (give) realamount:"+str(realamount)+" val:"+str(val))
                                          if not (realamount) == val: # +outfee

                                            if (realamount) < val: # +outfee
                                                rest = val - (realamount) #+outfee)
                                            else:
                                                rest = (realamount) - val #+outfee)
                                            jnreq = self.related_join_request()
                                            if jnreq:
                                                if rest > jnreq.payment_margin():
                                                    print("ev-give: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found+fee:"+str(val)+" (type:"+str(type(val))+") - declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    loger.info("ev-give: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found+fee:"+str(val)+" (type:"+str(type(val))+") - declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    #mesg += ("(give event): Declared amount and chain discovered amount are too different!! fee:"+str(outfee)+", found+fee:"+str(val)+" <> declared+fee:"+str(realamount+outfee)+" (rest:"+str(remove_exponent(rest))+")") #+"(type:"+str(type(realamount))+")")
                                                    #self.event.delete()
                                                    #self.delete()
                                                else:
                                                    validval = val
                                                    print("ev-give: Declared amount and chain discovered amount are not equal but are close. Allow... rest:"+str(rest)+" fee:"+str(outfee)+" declared:"+str(realamount))
                                                    loger.info("ev-give: Declared amount and chain discovered amount are not equal but are close. Allow... rest:"+str(rest)+" fee:"+str(outfee)+" declared:"+str(realamount))

                                          else: # same val
                                            print("ev-give: declared exactly the same amount (+fee): "+str(val))
                                            loger.info("ev-give: declared exactly the same amount (+fee): "+str(val))
                                            validval = val
                                        else: # not declared realamount
                                            if len(outvals) > 1:
                                                print("ev-give: Not declared amount but tx has >1 output! can't check. "+str(outvals))
                                                mesg += str(_("Sorry, the system can't check a tx with many outputs without declaring the received amount (give event). "))
                                                #for val in outvals:
                                                #    print('val: '+str(val/DIVISOR))
                                                #self.event.delete()
                                                #self.delete()
                                                break
                                            else:
                                                print("ev-give: Without declared amount! Do we get the unique tx output as the valid value? "+str(val))
                                                loger.info("ev-give: Without declared amount! Do we get the unique tx output as the valid value? TODO tx.id:"+str(self.id)+" ev.id:"+str(self.event.id)+" val:"+str(val))
                                            mesg += str(_("Please, set the received amount to check the transaction."))

                                        if validval:
                                            if not self.event.quantity == validval:
                                                print("UPDATE ev give quantity! qty:"+str(self.event.quantity)+" validval:"+str(validval)+" (type:"+str(type(validval))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                loger.info("UPDATE ev give quantity! qty:"+str(self.event.quantity)+" validval:"+str(validval)+" type:"+str(type(validval)))
                                                self.event.quantity = validval
                                                self.event.save()
                                            if not evtmir.quantity == validval:
                                                print("UPDATE evtmir give quantity! qty:"+str(evtmir.quantity)+" validval:"+str(validval)+" (type:"+str(type(validval))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                loger.info("UPDATE evtmir give quantity! qty:"+str(evtmir.quantity)+" validval:"+str(validval)+" type:"+str(type(validval)))
                                                evtmir.quantity = validval
                                                evtmir.save()
                                            if self.event.commitment:
                                                if not self.event.commitment.quantity == validval:
                                                    print("UPDATE ev give commitment quantity! qty:"+str(self.event.commitment.quantity)+" validval:"+str(validval))
                                                    loger.info("UPDATE ev give commitment quantity! qty:"+str(self.event.commitment.quantity)+" validval:"+str(validval))
                                                    self.event.commitment.quantity = validval
                                                    self.event.commitment.save()
                                            if evtmir.commitment:
                                                if not evtmir.commitment.quantity == validval:
                                                    print("UPDATE evtmir give commitment quantity! qty:"+str(evtmir.commitment.quantity)+" validval:"+str(validval))
                                                    loger.info("UPDATE evtmir give commitment quantity! qty:"+str(evtmir.commitment.quantity)+" validval:"+str(validval))
                                                    evtmir.commitment.quantity = validval
                                                    evtmir.commitment.save()
                                            break

                                    elif self.event.event_type.name == 'Receive':
                                        val = Decimal( outval / DIVISOR).quantize(DECIMALS) #, settings.CRYPTO_DECIMALS)
                                        if realamount:
                                          if not realamount == val:
                                            print("- Not same (receive) realamount:"+str(realamount)+" val:"+str(val))
                                            if realamount < val:
                                                rest = val - realamount
                                            else:
                                                rest = realamount - val
                                            jnreq = self.related_join_request()
                                            if jnreq:
                                                if rest > jnreq.payment_margin():
                                                    print("ev-receive: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found:"+str(val)+" (type:"+str(type(val))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    loger.info("ev-receive: Declared amount and chain discovered amount are too different!! rest:"+str(remove_exponent(rest))+" fee:"+str(outfee)+", found:"+str(val)+" (type:"+str(type(val))+") <> declared:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                    #mesg += ("(receive event): Declared amount and chain discovered amount are too different!! fee:"+str(outfee)+", found:"+str(val)+" <> declared:"+str(realamount)+" (rest:"+str(remove_exponent(rest))+")") #+"(type:"+str(type(realamount))+")")
                                                    #self.event.delete()
                                                    #self.delete()
                                                else:
                                                    validval = val
                                                    print("ev-receive: Declared amount and chain discovered amount are not equal but are close. Allow... rest:"+str(rest)+" fee:"+str(outfee)+" declared:"+str(realamount))
                                                    loger.info("ev-receive: Declared amount and chain discovered amount are not equal but are close. Allow... rest:"+str(rest)+" fee:"+str(outfee)+" declared:"+str(realamount))

                                          else: # same val
                                            print("ev-receive: declared exactly the same amount (-fee): "+str(val))
                                            loger.info("ev-receive: declared exactly the same amount (-fee): "+str(val))
                                            validval = val
                                        else: # not declared realamount
                                            if len(outvals) > 1:
                                                print("ev-receive: Not declared amount but tx has >1 output! can't check. outvals: "+str(outvals))
                                                loger.warning("ev-receive: Not declared amount but tx has >1 output! can't check.")
                                                for val in outvals:
                                                    print('val: '+str(val/DIVISOR))
                                                mesg += str(_("Sorry, the system can't check a tx with many outputs without declaring the received amount."))
                                                #self.event.delete()
                                                #self.delete()
                                                break
                                            else:
                                                print("ev-receive: Without declared amount! Do we get the unique tx output as the valid value? "+str(val))
                                                loger.info("ev-receive: Without declared amount! Do we get the unique tx output as the valid value? TODO tx.id:"+str(self.id)+" ev.id:"+str(self.event.id)+" val:"+str(val))
                                            mesg += str(_("Please, set the received amount to check the transaction."))

                                        if validval:
                                            if not self.event.quantity == validval:
                                                print("UPDATE ev receive quantity! qty:"+str(self.event.quantity)+" val:"+str(val)+" (type:"+str(type(val))+") - realamount:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                loger.info("UPDATE ev receive quantity! qty:"+str(self.event.quantity)+" val:"+str(val))
                                                self.event.quantity = val
                                                self.event.save()
                                            if not evtmir.quantity == validval: # mirror ev
                                                print("UPDATE evtmir receive quantity! qty:"+str(evtmir.quantity)+" val:"+str(val)+" (type:"+str(type(val))+") - realamount:"+str(realamount)+"(type:"+str(type(realamount))+")")
                                                loger.info("UPDATE evtmir receive quantity! qty:"+str(evtmir.quantity)+" val:"+str(val))
                                                evtmir.quantity = val
                                                evtmir.save()
                                            if self.event.commitment:
                                                if not self.event.commitment.quantity == val:
                                                    print("UPDATE ev receive commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                    loger.info("UPDATE ev receive commitment quantity! qty:"+str(self.event.commitment.quantity)+" val:"+str(val))
                                                    self.event.commitment.quantity = val
                                                    self.event.commitment.save()
                                            if evtmir.commitment:
                                                if not evtmir.commitment.quantity == val:
                                                    print("UPDATE evtmir receive commitment quantity! qty:"+str(evtmir.commitment.quantity)+" val:"+str(val))
                                                    loger.info("UPDATE evtmir receive commitment quantity! qty:"+str(evtmir.commitment.quantity)+" val:"+str(val))
                                                    evtmir.commitment.quantity = val
                                                    evtmir.commitment.save()
                                            break
                                    else:
                                        raise ValidationError("TX event type not supported: "+str(self.event.event_type.name))

                                # end for

                                if not validval:
                                    if foundadd:
                                        val = Decimal( (foundval) / DIVISOR).quantize(DECIMALS)
                                        mesg += str(_("Found the project address but a different amount?: "))+str(val)
                                        loger.warning("Found the project address but a different amount?: "+str(val))
                                        print("Found the project address but a different amount?: "+str(val))
                                        #print("! Not deleted ev:"+str(self.event.id)+" nor btx:"+str(self.id)+' foundadd: '+str(foundadd)+' Outputs:'+str(outputs))
                                        if val and self.event.quantity > val:
                                            print("FIXED ev:"+str(self.event.id)+' quantity:'+str(self.event.quantity)+' to real val:'+str(val)+' outfee:'+str(outfee))
                                            loger.info("FIXED ev:"+str(self.event.id)+' quantity:'+str(self.event.quantity)+' to real val:'+str(val)+' outfee:'+str(outfee))

                                            if outfee and mirbtx:
                                                if self.event.event_type == et_give:
                                                    self.event.quantity = val # + outfee
                                                elif self.event.event_type == et_receive:
                                                    self.event.quantity = val

                                                if not mirbtx == evtmir.chain_transaction:
                                                    raise ValidationError("The ChainTx mirror is not the same as its event mirror chain_tx ?? ")
                                                if evtmir.event_type == et_give:
                                                    evtmir.quantity = val # + outfee
                                                elif evtmir.event_type == et_receive:
                                                    evtmir.quantity = val

                                                # uncomment below to avoid scanning again the tx
                                                #self.tx_fee = outfee
                                                #mirbtx.tx_fee = outfee
                                                self.event.save()
                                                evtmir.save()

                                            else:
                                                print("No outfee! don't fix the ev:"+str(self.event)+' nor mir:'+str(mir.id))
                                                loger.info("No outfee! don't fix the ev:"+str(self.event)+' nor mir:'+str(mir.id))
                                        else:
                                            print("... and different ev.qty:"+str(self.event.quantity)+' val:'+str(val))
                                            loger.warning("... and different ev.qty:"+str(self.event.quantity)+' val:'+str(val))
                                    else:
                                        mesg += str(_("Not found address nor any output with a similar amount?")) #+" "+str(outvals)
                                        loger.warning("Not found address nor any output with a similar amount? "+str(outvals))
                                        print("Not found address nor any output with a similar amount? "+str(outvals))
                                        if len(outvals) < 2:
                                            self.event.delete()
                                            self.delete()
                                        else:
                                            pass

                                    return mesg
                            else:
                                raise ValidationError("not tx totals? total_in:"+str(total_in)+" total_out:"+str(total_out))

                            if self.event:
                                self.from_address = ' '.join(inputs)
                                if foundadd:
                                    self.to_address = foundadd
                                else:
                                    self.to_address = ' '.join(outputs)
                                self.save()
                                if mirbtx:
                                    mirbtx.from_address = self.from_address
                                    mirbtx.to_address = self.to_address
                                    mirbtx.save()
                                else:
                                    raise ValidationError("MISSING chain_tx mirror! id:"+str(self.id))
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
