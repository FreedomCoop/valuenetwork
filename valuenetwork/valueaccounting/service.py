import datetime, logging
from decimal import *

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, Count

loger = logging.getLogger("ocp")

from valuenetwork.valueaccounting.models import (
    EconomicResource,
    EconomicResourceType,
    EventType,
    Transfer,
    TransferType,
    UseCase,
    ExchangeType,
    Exchange,
    EconomicEvent,
    AgentResourceRole,
    AgentResourceRoleType,
    Unit,
)


from faircoin import utils as faircoin_utils
from faircoin.models import FaircoinAddress, FaircoinTransaction

class ExchangeService(object):
    @classmethod
    def get(cls):
        return cls()

    @classmethod
    def faircoin_internal_exchange_type(cls):
        use_case = UseCase.objects.get(name="Internal Exchange")
        xt = ExchangeType.objects.filter(
            use_case=use_case,
            name="Transfer Faircoins")
        if xt:
            xt = xt[0]
        else:
            xt = ExchangeType(
                use_case=use_case,
                name="Transfer Faircoins")
            xt.save()
        return xt

    @classmethod
    def faircoin_internal_transfer_type(cls):
        xt = cls.faircoin_internal_exchange_type()
        tts = TransferType.objects.filter(
            exchange_type=xt,
            name=xt.name)
        if not tts:
            tts = TransferType.objects.filter(
                exchange_type=xt,
                name="Transfer FairCoins")
        if tts:
            tt = tts[0]
            if tt.name != xt.name:
                print("- changed tt.name '"+str(tt.name)+"' for the ex.name '"+str(xt.name)+"'")
                tt.name = xt.name
                tt.save()
        else:
            tt, c = TransferType.objects.get_or_create(
                exchange_type=xt,
                name=xt.name,
                sequence=1,
                is_currency=True)
            if c:
                print(("- created TransferType: "+str(tt)))

        return tt

    @classmethod
    def faircoin_outgoing_exchange_type(cls):
        use_case = UseCase.objects.get(name="Outgoing Exchange")
        xt = ExchangeType.objects.filter(
            use_case=use_case,
            name="Send Faircoins")
        if xt:
            xt = xt[0]
        else:
            xt = ExchangeType(
                use_case=use_case,
                name="Send Faircoins")
            xt.save()
        return xt

    @classmethod
    def faircoin_outgoing_transfer_type(cls):
        xt = cls.faircoin_outgoing_exchange_type()
        tts = TransferType.objects.filter(
            exchange_type=xt,
            name=xt.name)
        if not tts:
            tts = TransferType.objects.filter(
                exchange_type=xt,
                name="Send FairCoins")
        if tts:
            tt = tts[0]
            if tt.name != xt.name:
                print("- changed tt.name '"+str(tt.name)+"' for the ex.name '"+str(xt.name)+"'")
                tt.name = xt.name
                tt.save()
        else:
            tt = TransferType(
                exchange_type=xt,
                name=xt.name,
                sequence=1,
                is_currency=True,
            )
            tt.save()
        return tt

    @classmethod
    def faircoin_incoming_exchange_type(cls):
        use_case = UseCase.objects.get(name="Incoming Exchange")
        xt = ExchangeType.objects.filter(
            use_case=use_case,
            name="Receive Faircoins")
        if xt:
            xt = xt[0]
        else:
            xt = ExchangeType(
                use_case=use_case,
                name="Receive Faircoins")
            xt.save()
        return xt

    @classmethod
    def faircoin_incoming_transfer_type(cls):
        xt = cls.faircoin_incoming_exchange_type()
        tts = TransferType.objects.filter(
            exchange_type=xt,
            name=xt.name)
        if not tts:
            tts = TransferType.objects.filter(
                exchange_type=xt,
                name="Receive FairCoins")
        if tts:
            tt = tts[0]
            if tt.name != xt.name:
                print("- changed tt.name '"+str(tt.name)+"' for the ex.name '"+str(xt.name)+"'")
                tt.name = xt.name
                tt.save()
        else:
            tt = TransferType(
                exchange_type=xt,
                name=xt.name,
                sequence=1,
                is_currency=True,
            )
            tt.save()
        return tt


    def send_faircoins(self, from_agent, recipient, qty, resource, notes='', minus_fee=False):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        to_resources = EconomicResource.objects.filter(faircoin_address__address=recipient)
        to_resource = None
        to_agent = None
        if to_resources:
            to_resource = to_resources[0]  # shd be only one
            to_agent = to_resource.owner()
        et_give = EventType.objects.get(name="Give")
        fairunit = Unit.objects.get(abbrev="fair")
        if to_resource:
            tt = ExchangeService.faircoin_internal_transfer_type()
            xt = tt.exchange_type
            date = datetime.date.today()
            exchange = Exchange(
                exchange_type=xt,
                use_case=xt.use_case,
                name="Transfer Faircoins",
                start_date=date,
            )
            exchange.save()
            transfer = Transfer(
                transfer_type=tt,
                exchange=exchange,
                transfer_date=date,
                name="Transfer Faircoins",
                notes=notes,
            )
            transfer.save()
        else:
            tt = ExchangeService.faircoin_outgoing_transfer_type()
            xt = tt.exchange_type
            date = datetime.date.today()
            exchange = Exchange(
                exchange_type=xt,
                use_case=xt.use_case,
                name="Send Faircoins",
                start_date=date,
            )
            exchange.save()
            transfer = Transfer(
                transfer_type=tt,
                exchange=exchange,
                transfer_date=date,
                name="Send Faircoins",
                notes=notes,
            )
            transfer.save()

        state = "new"
        event = EconomicEvent(
            event_type=et_give,
            event_date=date,
            from_agent=from_agent,
            to_agent=to_agent,
            resource_type=resource.resource_type,
            resource=resource,
            quantity=qty,
            unit_of_quantity=fairunit,
            transfer=transfer,
            event_reference=recipient,
            description=notes,
        )
        event.save()
        fairtx = FaircoinTransaction(
            event=event,
            tx_state=state,
            to_address=recipient,
            amount=qty,
            minus_fee=minus_fee,
        )
        fairtx.save()

        if to_resource:
            et_receive = EventType.objects.get(name="Receive")
            event = EconomicEvent(
                event_type=et_receive,
                event_date=date,
                from_agent=from_agent,
                to_agent=to_agent,
                resource_type=to_resource.resource_type,
                resource=to_resource,
                quantity=qty,
                unit_of_quantity=fairunit,
                transfer=transfer,
                event_reference=recipient,
                description=notes,
            )
            event.save()
            fairtx = FaircoinTransaction(
                event=event,
                tx_state=state,
                to_address=recipient,
                amount=qty,
                minus_fee=minus_fee,
            )
            fairtx.save()

        return exchange

    def include_blockchain_tx_as_event(self, agent, resource):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return []

        redistribution_date = datetime.date(2017, 7, 18)
        redistribution_txs = (
            "009e53988153fbd13f458b0881734ff385f749d020e3ee7360e1ca9ed8ff0490",
            "12bc2f2f699dc75d1cbe0dd17597cd12649bb7698e179c752f22b70a0a3c98d4",
            "218c72570d992dc33456c148c1e26641a4b985e83054a5cae227ba71ee979ea3",
            "231c406153b1e5e75d47aade9dda5a2b806067f577d7d5b8e9574f19bb988d75",
            "39a808302aed7ff4cd68d8d2deb775502ae99c5eb207c65a9712a7125d5329c8",
            "634f11e66604bf38eafec4b0d7aeebf630073cfcb83c74a58fdd5e0772e88305",
            "6abd3941e457d3e68f42f7619eadc19767ad0724009f1f98caffde2403656d8f",
            "7229c6eaca9b2bd55edd10410fd3b223a4b700d53591ddb97690762f52526fdd",
            "7484be3956691dae231d8c4dafb62104dbf805e541b1cc1c572a06b65d9a3f18"
            "7927a0fbf3b6533f282815f49154dae94acde9e347e7a53f84b4e54d276b9792",
            "b31489979bfd28faa2fadcec559a9e5d10413048a5ad80bc7d3c46901a1ff362",
            "b46352e1b87783fbf9ed771d722c08035cfc1c7c4e1509d4654ae195c700af91",
            "d26e3759806a8ae53ae81a643786d2ad34705f8d792330d9bf8bdd306658a982",
        )

        faircoin_address = str(resource.faircoin_address.address)
        tx_in_blockchain = faircoin_utils.get_address_history(faircoin_address)
        if not tx_in_blockchain: # Something wrong in daemon or network.
            return []

        event_list = EconomicEvent.objects.filter(
            Q(resource=resource) | Q(faircoin_transaction__to_address=resource.faircoin_address.address)
            ).annotate(numev=Count("transfer__events")
            ).exclude(numev__gt=1, event_type__name="Receive")
        event_list = event_list.filter(
            event_date__gt=redistribution_date,
            faircoin_transaction__tx_hash__isnull=False
        )
        event_list2 = EconomicEvent.objects.filter( #
            resource=resource,
            event_date__gt=redistribution_date,
            faircoin_transaction__tx_hash__isnull=False
        )
        if event_list2 and not len(event_list) == len(event_list2):
            print("Different event_list counts! ;; evt_list:"+str(len(event_list))+" ev_list2:"+str(len(event_list2)))
            loger.info("Different event_list counts! ;; evt_list:"+str(len(event_list))+" ev_list2:"+str(len(event_list2)))

        tx_in_ocp = []
        for event in event_list:
            tx_in_ocp.append(str(event.faircoin_transaction.tx_hash))

        tx_included = []
        for tx in tx_in_blockchain:
            if str(tx[0]) not in tx_in_ocp and str(tx[0]) not in redistribution_txs:
                amount, time = faircoin_utils.get_transaction_info(str(tx[0]), faircoin_address)
                confirmations, timestamp = faircoin_utils.get_confirmations(str(tx[0]))
                if amount and confirmations:
                    qty=Decimal(amount)/Decimal(100000000)
                    date = datetime.date.fromtimestamp(time)
                    tt = ExchangeService.faircoin_incoming_transfer_type()
                    xt = tt.exchange_type
                    jn_req = event = fairtx = None
                    if hasattr(resource.owner(), 'project') and resource.owner().project:
                        for req in resource.owner().project.join_requests.all():
                            #print(";; req:"+str(req))
                            if req.exchange and req.agent.faircoin_resource():
                                txpay = req.exchange.txpay()
                                if txpay:
                                    for ev in txpay.events.all():
                                        if ev.to_agent == resource.owner() and hasattr(ev, 'faircoin_transaction') and ev.faircoin_transaction and not ev.faircoin_transaction.tx_hash:
                                            jn_req = req
                                            exchange = req.exchange
                                            transfer = txpay
                                            event = ev
                                            fairtx = ev.faircoin_transaction
                                            print(";;; found jn_req:"+str(jn_req.id)+" ev:"+str(ev.id)+" fairtx:"+str(fairtx.id))
                                            loger.info(";;; found jn_req:"+str(jn_req.id)+" ev:"+str(ev.id)+" fairtx:"+str(fairtx.id))
                                            break
                                        #else:
                                        #    print(";; skip ev ")
                                else:
                                    print(";;; not found txpay in req:"+str(req.id))
                                    loger.info(";;; not found txpay in req:"+str(req.id))
                            else:
                                print(";;; not req.exchange ?")
                            if jn_req:
                                #print(";; found")
                                break
                    else:
                        print(";;; no project")
                    for req in resource.owner().project_join_requests.all():
                        if req.exchange: #project.shares_account_type() == resource.resource_type:
                            for tf in req.exchange.transfers.all():
                                for ev in tf.events.all():
                                    if hasattr(ev, 'faircoin_transaction') and ev.faircoin_transaction:
                                        if ev.faircoin_transaction.to_address == resource.faircoin_address.address:
                                            jn_req = req
                                            exchange = req.exchange
                                            transfer = tf #req.exchange.txpay()
                                            event = ev #transfer.events.get(faircoin_transaction__tx_hash__isnull=True)
                                            fairtx = ev.faircoin_transaction
                                            print(";;; found jr:"+str(req.id)+" pro:"+str(req.project.agent)+" ev:"+str(ev.id)+" tf:"+str(tf.id)+" ex:"+str(exchange.id))
                                            loger.info(";;; found jr:"+str(req.id)+" pro:"+str(req.project.agent)+" ev:"+str(ev.id)+" tf:"+str(tf.id)+" ex:"+str(exchange.id))
                                            break
                    if not jn_req:
                        exchange = Exchange(
                            exchange_type=xt,
                            use_case=xt.use_case,
                            name="Receive Faircoins",
                            start_date=date,
                        )
                        exchange.save()
                        transfer = Transfer(
                            transfer_type=tt,
                            exchange=exchange,
                            transfer_date=date,
                            name="Receive Faircoins",
                        )
                        transfer.save()

                    et_receive = EventType.objects.get(name="Receive")
                    fairunit = Unit.objects.get(abbrev="fair")
                    state = "external"
                    if confirmations > 0:
                        state = "broadcast"
                    if confirmations > 2:
                        state = "confirmed"

                    if not event:
                        event = EconomicEvent(
                            event_type=et_receive,
                            event_date=date,
                            to_agent=agent,
                            resource_type=resource.resource_type,
                            resource=resource,
                            quantity=qty,
                            unit_of_quantity=fairunit,
                            transfer=transfer,
                            event_reference=faircoin_address
                        )
                    else:
                        event.quantity = qty
                        event.event_reference = faircoin_address
                        #event.event_date = date
                    event.save()
                    if not fairtx:
                        fairtx = FaircoinTransaction(
                            event=event,
                            tx_hash=str(tx[0]),
                            tx_state=state,
                            to_address=faircoin_address,
                            amount=qty,
                            minus_fee=False,
                        )
                    else:
                        fairtx.tx_state = state
                        fairtx.tx_hash = str(tx[0])
                        fairtx.amount = qty
                    fairtx.save()
                    tx_included.append(str(tx[0]))
        return tx_included

    def create_faircoin_resource(self, agent, address):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        role_types = AgentResourceRoleType.objects.filter(is_owner=True)
        owner_role_type = None
        if role_types:
            owner_role_type = role_types[0]
        resource_types = EconomicResourceType.objects.filter(
            behavior="dig_acct", name__icontains="Faircoin Ocp Account")
        if resource_types.count() == 0:
            raise ValidationError("Cannot create digital currency resource for " + agent.nick + " because no digital currency account ResourceTypes with 'Faircoin Ocp Account' in the name.")
            return None
        if resource_types.count() > 1:
            raise ValidationError("Cannot create digital currency resource for " + agent.nick + ", more than one digital currency account ResourceTypes.")
            return None
        resource_type = resource_types[0]
        if owner_role_type:
            # resource type has unit
            va = EconomicResource(
                resource_type=resource_type,
                identifier="Faircoin Ocp Account for " + agent.nick,
            )
            va.save()
            fairaddress = FaircoinAddress(
                resource=va,
                address=address,
            )
            fairaddress.save()
            arr = AgentResourceRole(
                agent=agent,
                role=owner_role_type,
                resource=va,
            )
            arr.save()
            return va
        else:
            raise ValidationError("Cannot create digital currency resource for " + agent.nick + " because no owner AgentResourceRoleTypes.")
            return None
