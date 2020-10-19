import sys
import time
import logging
from decimal import *

logger = logging.getLogger("fair")

from django.conf import settings
from django.db.models import Q

import faircoin.utils as efn
from .models import FaircoinAddress
from valuenetwork.valueaccounting.models import EconomicAgent, EconomicEvent, EconomicResource
from valuenetwork.valueaccounting.lockfile import FileLock, AlreadyLocked, LockTimeout, LockFailed


#FAIRCOIN_DIVISOR = int(100000000)

def acquire_lock():
    lock = FileLock("broadcast-faircoins")
    logger.debug("acquiring lock...")
    try:
        #lock.acquire(settings.BROADCAST_FAIRCOINS_LOCK_WAIT_TIMEOUT)
        lock.acquire(1)
    except AlreadyLocked:
        logger.warning("lock already in place. quitting.")
        return False
    except LockTimeout:
        logger.warning("waiting for the lock timed out. quitting.")
        return False
    logger.debug("lock acquired.")
    return lock

def create_address_for_agent(agent):
    address = None
    used_query_list = FaircoinAddress.objects.values_list('address', flat=True)
    used_list = list(used_query_list)
    if efn.is_connected():
        try:
            unused_address = efn.get_unused_addresses()
        except Exception:
            _, e, _ = sys.exc_info()
            logger.critical("Can not get the list of unused addresses from the wallet: {0}".format(e))
        for add in unused_address:
            if add not in used_list:
                logger.debug("Found unused %s -- %s" %(add, efn.get_address_index(add)))
                address = add
                break
        if (address is None) or (address == 'ERROR'):
                msg = ("CAN NOT CREATE ADDRESS FOR %s" %(agent.name))
                logger.critical(msg)
                return None
    return address

def create_address_for_resource(resource):
    agent = resource.owner()
    address = create_address_for_agent(agent)
    if address:
        fairaddress = resource.faircoin_address
        fairaddress.address = address
        fairaddress.save()
        return True
    else:
        msg = " ".join(["Failed to get a FairCoin address for", agent.name])
        logger.warning(msg)
        return False

def create_requested_addresses():
    try:
        requests = EconomicResource.objects.filter(faircoin_address__address="address_requested")
        msg = " ".join(["new FairCoin address requests count:", str(requests.count())])
        logger.debug(msg)
    except Exception:
        _, e, _ = sys.exc_info()
        logger.critical("an exception occurred in retrieving FairCoin address requests: {0}".format(e))
        return "failed to get FairCoin address requests"

    if requests:
        if efn.is_connected():
            for resource in requests:
                result = create_address_for_resource(resource)
            msg = " ".join(["created", str(requests.count()), "new faircoin addresses."])
    else:
        msg = "No new faircoin address requests to process."
    return msg

def broadcast_tx():

    try:
        events1 = EconomicEvent.objects.filter(faircoin_transaction__tx_state="new").order_by('pk')
        events = events1.filter(Q(event_type__name='Give')|Q(event_type__name='Distribution'))
        if not events and events1:
            events2 = events1.filter(Q(event_type__name='Receive'))
            for ev in events2:
                mirr = ev.mirror_event()
                if mirr:
                    if hasattr(mirr, 'faircoin_transaction') and mirr.faircoin_transaction:
                        pass
                    else:
                        if hasattr(ev, 'faircoin_transaction') and ev.faircoin_transaction and mirr.event_type.name == 'Give':
                            tx = ev.faircoin_transaction
                            tx.event = mirr
                            #tx.save()
                            logger.warning("Using a 'Receive' event to link a FairTX!? CHANGED to Give mirror! mi:"+str(mirr.id)+" ev:"+str(ev.id)+" ("+str(ev)+")")
                            print("Using a 'Receive' event to link a FairTX!? CHANGED to Give mirror! mi:"+str(mirr.id)+" ev:"+str(ev.id)+" ("+str(ev)+")")
                            #break
                        #events = [ev]

        msg = " ".join(["new FairCoin event count:", str(events.count())])
        logger.debug(msg)
    except Exception:
        _, e, _ = sys.exc_info()
        logger.critical("an exception occurred in retrieving events: {0}".format(e))
        logger.warning("releasing lock because of error...")
        lock.release()
        logger.debug("released.")
        return "failed to get events"

    try:
        successful_events = 0
        failed_events = 0
        if events and efn.is_connected():
            logger.debug("broadcast_tx ready to process events")
            for event in events:
                if event.resource:
                    if event.event_type.name=="Give":
                        address_origin = event.resource.faircoin_address.address
                        address_end = event.faircoin_transaction.to_address
                    elif event.event_type.name=="Distribution":
                        address_origin = event.from_agent.faircoin_address()
                        address_end = event.resource.faircoin_address.address
                    fairtx = event.faircoin_transaction
                    amount = float(fairtx.amount) * 1.e8 # In satoshis
                    if amount < 1001:
                        fairtx.tx_state = "broadcast"
                        fairtx.tx_hash = "Null"
                        fairtx.save()
                        continue

                    logger.info("About to build transaction. Amount: %d From: %s To: %s Minus Fee: %s" %(int(amount), address_origin, address_end, fairtx.minus_fee))
                    tx_hash = None
                    try:
                        tx_hash, fee = efn.make_transaction_from_address(address_origin, address_end, int(amount), fairtx.minus_fee)
                    except Exception:
                        _, e, _ = sys.exc_info()
                        logger.critical("an exception occurred in make_transaction_from_address: {0}".format(e))

                    if (tx_hash == "ERROR") or (not tx_hash):
                        logger.warning("ERROR tx_hash, make tx failed without raising Exception")
                        failed_events += 1
                    elif tx_hash:
                        successful_events += 1
                        if event.event_type.name=="Give":
                            qty = event.quantity
                            qty += Decimal(fee) / Decimal("1.e8")
                            event.quantity = qty
                            event.save()
                        fairtx.tx_state = "broadcast"
                        fairtx.tx_hash = tx_hash
                        fairtx.save()
                        transfer = event.transfer
                        if transfer:
                            revent = transfer.receive_event()
                            if revent:
                                refairtx = revent.faircoin_transaction
                                refairtx.tx_state = "broadcast"
                                refairtx.tx_hash = tx_hash
                                refairtx.save()
                        msg = " ".join([ "Broadcasted tx", tx_hash, "amount", str(amount), "from", address_origin, "to", address_end ])
                        logger.info(msg)
    except Exception:
        _, e, _ = sys.exc_info()
        logger.critical("an exception occurred in processing events: {0}".format(e))
        return "failed to process events"

    if events:
        msg = " ".join(["Broadcast", str(successful_events), "new faircoin tx."])
        if failed_events:
            msg += " ".join([ str(failed_events), "events failed."])
    else:
        msg = "No new faircoin tx to process."
    return msg
