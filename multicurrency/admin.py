from django.contrib import admin
from multicurrency.models import *
# Register your models here.

class BlockchainTransactionAdmin(admin.ModelAdmin):
    list_display = ('event', 'tx_hash', 'tx_fee', 'from_address', 'to_address', )

admin.site.register(BlockchainTransaction, BlockchainTransactionAdmin)
