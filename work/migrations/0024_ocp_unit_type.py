# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0007_transfertype_inherit_types'),
        ('general', '0004_auto_20161201_1831'),
        ('work', '0023_auto_20170121_0004'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ocp_Unit_Type',
            fields=[
                ('unit_type', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Unit_Type', on_delete=models.CASCADE)),
                ('ocp_unit', models.OneToOneField(related_name='ocp_unit_type', null=True, to='valueaccounting.Unit', blank=True, help_text='a related OCP Unit', verbose_name='ocp unit', on_delete=models.SET_NULL)),
                ('unit', models.OneToOneField(related_name='ocp_unit_type', null=True, to='general.Unit', blank=True, help_text='a related General Unit', verbose_name='general unit', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Unit',
                'verbose_name_plural': 'o-> Types of General Units',
            },
            bases=('general.unit_type',),
        ),
    ]
