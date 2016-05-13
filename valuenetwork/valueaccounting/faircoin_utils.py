import logging

import faircoin_nrp.electrum_fair_nrp as efn

from valuenetwork.valueaccounting.models import EconomicEvent
#todo faircoin: how to handle failures?

def init_electrum_fair():
    #import pdb; pdb.set_trace()
    try:
        if not efn.network:
            efn.init()
        else:
            if not efn.network.is_connected():
                efn.init()
    except:
        #handle failure better here
        msg = "Can not init Electrum Network. Exiting."
        assert False, msg
        
def create_address_for_agent(agent):
    #import pdb; pdb.set_trace()
    init_electrum_fair()
    wallet = efn.wallet
    address = None
    address = efn.new_fair_address(
        entity_id = agent.nick, 
        entity = agent.agent_type.name,
        )
    return address
    
def network_fee():
    return efn.network_fee
    
def send_faircoins(address_origin, address_end, amount):
    #import pdb; pdb.set_trace()
    init_electrum_fair()
    wallet = efn.wallet
    tx = efn.make_transaction_from_address(address_origin, address_end, amount)
    tx_hash = tx.hash()
    # this is my feeble attempt to determine
    # if the transaction has been broadcasted.
    # it does not work, doesn't wait long enough.
    # And cannot actually tell if the tx has failed
    # to be accepted by the network.
    broadcasted = False
    for i in range(0, 32):
        try:
            wallet.tx_result
            print "wallet.tx_result"
        except AttributeError:
            continue
        if broadcasted:
            print "broadcast break"
            break
        broadcasted, out = wallet.receive_tx(tx_hash, tx)
    return tx, broadcasted
    
def send_fake_faircoins(address_origin, address_end, amount):
    import time
    tx = str(time.time())
    broadcasted = True
    print "sent fake faircoins"
    return tx, broadcasted
    
def get_address_history(address):
    init_electrum_fair()
    wallet = efn.wallet
    return wallet.get_address_history(address)

def get_address_balance(address):
    init_electrum_fair()
    return efn.get_address_balance(address)
    
def is_valid(address):
    init_electrum_fair()
    return efn.is_valid(address)
    
def get_confirmations(tx):
    init_electrum_fair()
    return efn.get_confirmations(tx)
        
def broadcast_tx():
    init_electrum_fair()
    events = EconomicEvent.objects.filter(
        digital_currency_tx_state="new",
        event_type__name="Give")
    #can I do a lot of events in a batch?
    #probly...
    if events:
        event = events[0]
        if event.resource:
            address_origin = event.resource.digital_currency_address
            address_end = event.event_reference
            amount = event.quantity
            tx_hash = efn.make_transaction_from_address(address_origin, address_end, amount)
            if tx_hash:
                event.digital_currency_tx_state = "broadcast"
                event.digital_currency_tx_hash = tx_hash
                event.save()
                transfer = event.transfer
                if transfer:
                    revent = transfer.receive_event()
                    if revent:
                        revent.digital_currency_tx_state = "broadcast"
                        revent.digital_currency_tx_hash = tx_hash
                        revent.save()
                msg = " ".join([ "**** sent tx", tx_hash, "amount", str(amount), "from", address_origin, "to", address_end ])
                logging.info(msg)
    return events.count()