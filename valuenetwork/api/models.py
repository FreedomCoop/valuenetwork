from django.db import models

from valuenetwork.valueaccounting.models import Unit, EconomicEvent, Commitment, Location, EconomicAgent
from decimal import *

# Helpers for dealing with Agent polymorphism

def formatAgent(agent):
    if agent:
        if agent.agent_type.party_type == "individual":
            return Person(
                id=agent.id,
                name = agent.name,
                note = agent.description,
                primary_location = agent.primary_location,
                primary_phone = agent.primary_phone,
                image = agent.image,
                email = agent.email)
        else:
            return Organization(
                id=agent.id,
                name = agent.name,
                note = agent.description,
                image = agent.image,
                is_context = agent.is_context,
                primary_location = agent.primary_location,
                primary_phone = agent.primary_phone,
                type = agent.agent_type,
                email = agent.email)

def formatAgentList(agent_list):
    mixed_list = []
    for agent in agent_list:
        mixed_list.append(formatAgent(agent))
    return mixed_list

# Django model extensions for exposing OO type layer in Graphene, where the core doesn't directly support ValueFlows

class QuantityValue(models.Model):
    numeric_value = models.DecimalField(max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    unit = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        related_name="quantity_value_units")

    class Meta:
        managed = False


class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    note = models.TextField(blank=True, null=True)
    image = models.CharField(max_length=255, blank=True)
    is_context = models.BooleanField(default=False)
    type = models.CharField(max_length=255)
    primary_location = models.ForeignKey(Location,
        related_name='orgs_at_location',
        blank=True, null=True,
        on_delete=models.DO_NOTHING)
    primary_phone = models.CharField(max_length=32, blank=True, null=True)
    email = models.EmailField(max_length=96, blank=True, null=True)

    class Meta:
        managed = False


class Person(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    note = models.TextField(blank=True, null=True)
    image = models.CharField(max_length=255, blank=True)
    is_context = models.BooleanField(default=False)
    type = models.CharField(max_length=255, default="Person")
    primary_location = models.ForeignKey(Location,
        related_name='people_at_location',
        blank=True, null=True,
        on_delete=models.DO_NOTHING)
    primary_phone = models.CharField(max_length=32, blank=True, null=True)
    email = models.EmailField(max_length=96, blank=True, null=True)

    class Meta:
        managed = False


class Fulfillment(models.Model):
    fulfilled_by = models.ForeignKey(EconomicEvent,
        related_name="fulfillments",
        on_delete=models.DO_NOTHING)
    fulfills = models.ForeignKey(Commitment,
        related_name="fulfillments",
        on_delete=models.DO_NOTHING)
    fulfilled_quantity = models.ForeignKey(QuantityValue,
        related_name="fulfillments",
        on_delete=models.DO_NOTHING)
    note = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
