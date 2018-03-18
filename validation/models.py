# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from valuenetwork.valueaccounting.models import EconomicEvent, EconomicAgent

class Validation(models.Model):
    event = models.ForeignKey(EconomicEvent,
        related_name="validations")
    validated_by = models.ForeignKey(EconomicAgent,
        related_name="validations")
    validation_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)

    class Meta:
        ordering = ('validation_date',)
