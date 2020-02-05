# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0022_auto_20170110_1710'),
    ]

    operations = [
        migrations.AddField(
            model_name='ocp_record_type',
            name='ocp_artwork_type',
            field=mptt.fields.TreeForeignKey(related_name='ocp_record_types', blank=True, to='work.Ocp_Artwork_Type', help_text='a related General Artwork Type', null=True, verbose_name='general artwork_type', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='ocp_skill_type',
            name='ocp_artwork_type',
            field=mptt.fields.TreeForeignKey(related_name='ocp_skill_types', blank=True, to='work.Ocp_Artwork_Type', help_text='a related General Artwork Type', null=True, verbose_name='general artwork_type', on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='ocp_artwork_type',
            name='context_agent',
            field=models.ForeignKey(related_name='ocp_artwork_types', blank=True, to='valueaccounting.EconomicAgent', help_text='a related OCP context EconomicAgent', null=True, verbose_name='context agent', on_delete=models.SET_NULL),
        ),
    ]
