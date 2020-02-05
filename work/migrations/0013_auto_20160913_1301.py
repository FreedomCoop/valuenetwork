# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0004_auto_20160817_2119'),
        ('work', '0012_joinrequest_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillsuggestion',
            name='resource_type',
            field=models.ForeignKey(related_name='skill_suggestions', blank=True, to='valueaccounting.EconomicResourceType', help_text='this skill suggestion became this ResourceType', null=True, verbose_name='resource_type', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='skillsuggestion',
            name='state',
            field=models.CharField(default=b'new', verbose_name='state', max_length=12, editable=False, choices=[(b'new', 'new'), (b'accepted', 'accepted'), (b'declined', 'declined')]),
        ),
    ]
