# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agenttype',
            name='parent',
            field=models.ForeignKey(related_name='sub_agents', blank=True, editable=False, to='valueaccounting.AgentType', null=True, verbose_name='parent', on_delete=models.SET_NULL),
            preserve_default=True,
        ),
    ]
