# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0004_auto_20160817_2119'),
    ]

    operations = [
        migrations.AddField(
            model_name='economicresourcetype',
            name='context_agent',
            field=models.ForeignKey(related_name='context_resource_types', verbose_name='context agent', blank=True, to='valueaccounting.EconomicAgent', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='exchangetype',
            name='context_agent',
            field=models.ForeignKey(related_name='exchange_types', verbose_name='context agent', blank=True, to='valueaccounting.EconomicAgent', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='processpattern',
            name='context_agent',
            field=models.ForeignKey(related_name='process_patterns', verbose_name='context agent', blank=True, to='valueaccounting.EconomicAgent', null=True, on_delete=models.SET_NULL),
        ),
    ]
