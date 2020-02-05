# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0007_transfertype_inherit_types'),
        ('work', '0024_ocp_unit_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='ocp_skill_type',
            name='facet',
            field=models.OneToOneField(related_name='ocp_skill_type', null=True, to='valueaccounting.Facet', blank=True, help_text='a related OCP Facet', verbose_name='ocp facet', on_delete=models.SET_NULL),
        ),
    ]
