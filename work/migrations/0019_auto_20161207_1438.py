# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0018_ocp_material_type_ocp_nonmaterial_type_ocp_record_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ocp_record_type',
            name='exchange_type',
            field=models.OneToOneField(related_name='ocp_record_type', null=True, blank=True, to='valueaccounting.ExchangeType', verbose_name='ocp exchange type', on_delete=models.SET_NULL),
        ),
    ]
