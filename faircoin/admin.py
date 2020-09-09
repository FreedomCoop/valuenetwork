# -*- coding: utf-8 -*-


from django.contrib import admin
from django.template.defaultfilters import truncatechars

from faircoin.models import FaircoinAddress, FaircoinTransaction

class FaircoinAddressAdmin(admin.ModelAdmin):
    readonly_fields = ('address', 'resource',)
    fields = ('address', 'resource',)
    list_display = ('address', 'resource_owner','resource_created_date')
    search_fields = ['address']
    ordering = ['-resource_id']

    def resource_owner(self, add_obj):
        return add_obj.resource.owner()
    resource_owner.short_description = 'Owner'

    def resource_created_date(self, add_obj):
        return add_obj.resource.created_date
    resource_created_date.short_description = 'Created Date'
    resource_created_date.admin_order_field = 'resource__created_date'

admin.site.register(FaircoinAddress, FaircoinAddressAdmin)

class FaircoinTransactionAdmin(admin.ModelAdmin):
    readonly_fields = ('tx_hash', 'to_address', 'event',)
    fields = ('tx_hash', 'tx_state', 'to_address', 'event',)
    list_display = ('tx_hash_short', 'tx_state', 'event_date', 'event_quantity', 'event_from_agent', 'event_to_agent')
    list_filter = ['tx_state',]
    ordering = ['-event_id']

    def event_date(self, tx_obj):
        return tx_obj.event.event_date
    event_date.short_description = 'Date'
    event_date.admin_order_field = 'event__event_date'

    def event_quantity(self, tx_obj):
        return tx_obj.event.quantity
    event_quantity.short_description = 'Amount'
    event_quantity.admin_order_field = 'event__quantity'

    def event_from_agent(self, tx_obj):
        return tx_obj.event.from_agent
    event_from_agent.short_description = 'From agent'
    event_from_agent.admin_order_field = 'event__from_agent'

    def event_to_agent(self, tx_obj):
        return tx_obj.event.to_agent
    event_to_agent.short_description = 'To agent'
    event_to_agent.admin_order_field = 'event__to_agent'

    def tx_hash_short(self, tx_obj):
        return truncatechars(tx_obj.tx_hash, 16)
    tx_hash_short.short_description = 'Tx hash'

admin.site.register(FaircoinTransaction, FaircoinTransactionAdmin)
