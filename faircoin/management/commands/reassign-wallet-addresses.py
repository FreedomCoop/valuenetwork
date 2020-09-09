from django.core.management.base import BaseCommand

from valuenetwork.valueaccounting.process_faircoin_requests import create_address_for_agent
from faircoin.utils import is_mine as is_address_in_wallet
from valuenetwork.valueaccounting.models import EconomicAgent


class Command(BaseCommand):

    help = "Reassign wallet addresses to new FairCoin accounts after changing to a test Electrum wallet."

    def handle(self, *args, **options):
        reassigned = 0
        found = 0
        total = 0
        models = EconomicAgent.objects.all()

        for agent in models:
            total += 1
            fcr = agent.faircoin_resource()
            if fcr is None:
                continue
            if fcr.faircoin_address.address:
                found += 1
                if is_address_in_wallet(fcr.faircoin_address.address) == False:
                    reassigned += 1
                    new_address = create_address_for_agent(agent)
                    if new_address:
                        fcr.faircoin_address.address = new_address
                        fcr.save()

        print("Finished %d wallet reassignments of %d wallets & %d total agents" % (reassigned, found, total))
