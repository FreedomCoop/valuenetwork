# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import date

from django.db import models
from django.utils.translation import ugettext_lazy as _

from valuenetwork.valueaccounting.models import EconomicResource, EconomicEvent
from faircoin import utils as faircoin_utils
from decimal import Decimal

FAIRCOIN_DIVISOR = Decimal("100000000.00")

FC2_DATE = date(2017, 7, 18) # launch of FairCoin 2.0
FC1_TX_URL = "https://chain.fair-coin.org/tx/"
FC2_TX_URL = "https://chain.fair.to/transaction?transaction="

WALLET = faircoin_utils.is_connected()

class FaircoinAddress(models.Model):
    resource = models.OneToOneField(EconomicResource, on_delete=models.CASCADE,
        verbose_name=_('resource'), related_name='faircoin_address')
    address = models.CharField(_("faircoin address"), max_length=96,
        null=False, editable=False)

    def balance(self):
        wallet = faircoin_utils.is_connected()
        if wallet:
            is_wallet_address = faircoin_utils.is_mine(self.address)
            if is_wallet_address:
                try:
                    balances = faircoin_utils.get_address_balance(self.address)
                    unconfirmed_balance =  Decimal(balances[1]) / FAIRCOIN_DIVISOR
                    unconfirmed_balance += self.resource.balance_in_tx_state_new()
                    confirmed_balance = Decimal(balances[0]) / FAIRCOIN_DIVISOR
                    if unconfirmed_balance < 0:
                        confirmed_balance += unconfirmed_balance
                    elif unconfirmed_balance == 0:
                        unconfirmed_balance = confirmed_balance
                    return confirmed_balance
                except:
                    pass
        return None

    def is_mine(self):
        is_wallet_address = False
        if WALLET:
            is_wallet_address = faircoin_utils.is_mine(self.address)
        return is_wallet_address

    def owner(self):
        return self.resource.owner()

    def to_fairtxs(self):
        tos = []
        if self.address:
            tos = FaircoinTransaction.objects.filter(to_address=self.address)
        return tos

    def from_fairtxs(self):
        ag = self.owner()
        txs = []
        if ag and ag.faircoin_address():
            txs = FaircoinTransaction.objects.filter(event__from_agent=ag)
        return txs




TX_STATE_CHOICES = (
    ('new', _('New')),
    ('pending', _('Pending')),
    ('broadcast', _('Broadcast')),
    ('confirmed', _('Confirmed')),
    ('external', _('External')),
    ('error', _('Error')),
)

class FaircoinTransaction(models.Model):
    event = models.OneToOneField(EconomicEvent, on_delete=models.CASCADE, verbose_name=_('event'), related_name='faircoin_transaction')
    tx_hash = models.CharField(_("Faircoin Transaction Hash"), max_length=96, blank=True, null=True, editable=False)
    tx_state = models.CharField(_('Faircoin Transaction State'), max_length=12, choices=TX_STATE_CHOICES, blank=True, null=True)
    to_address = models.CharField(_('To Address'), max_length=128, blank=True, null=True)
    amount = models.DecimalField(_('Quantity'), max_digits=16, decimal_places=8, default=0)
    minus_fee = models.BooleanField('Substract fee to total', default=False)

    def is_old_blockchain(self):
        fc2_launch_date = FC2_DATE
        if self.event.event_date < fc2_launch_date:
            return True
        else:
            return False

    def chain_link(self):
        if self.tx_hash:
            if self.is_old_blockchain():
                return FC1_TX_URL+str(self.tx_hash)
            else:
                return FC2_TX_URL+str(self.tx_hash)

