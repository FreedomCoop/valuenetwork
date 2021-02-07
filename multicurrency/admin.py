from django.contrib import admin
from multicurrency.models import *
# Register your models here.

class BlockchainTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'tx_hash', 'tx_fee', 'from_address', 'to_address', )
    fields = ('event', 'tx_hash', 'tx_fee', 'from_address', 'to_address' )
    raw_id_fields = ["event"]
admin.site.register(BlockchainTransaction, BlockchainTransactionAdmin)


#class MulticurrencyAuthAdmin(admin.ModelAdmin):
#    list_display = ('id', 'agent')
#    raw_id_fields = ["agent"]
#admin.site.register(MulticurrencyAuth, MulticurrencyAuthAdmin)
