# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0004_auto_20161201_1831'),
        ('work', '0026_ocp_record_type_ocp_skill_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='ocp_artwork_type',
            name='unit_type',
            field=mptt.fields.TreeForeignKey(related_name='ocp_artwork_types', blank=True, to='general.Unit_Type', help_text='a related General Unit Type', null=True, verbose_name='general unit_type', on_delete=models.SET_NULL),
        ),
    ]
