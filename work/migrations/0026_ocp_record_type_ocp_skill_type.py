# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0025_ocp_skill_type_facet'),
    ]

    operations = [
        migrations.AddField(
            model_name='ocp_record_type',
            name='ocp_skill_type',
            field=mptt.fields.TreeForeignKey(related_name='ocp_record_types', blank=True, to='work.Ocp_Skill_Type', help_text='a related General Skill Type', null=True, verbose_name='general skill_type', on_delete=models.SET_NULL),
        ),
    ]
