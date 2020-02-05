# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0006_facet_clas'),
        ('general', '0004_auto_20161201_1831'),
        ('work', '0019_auto_20161207_1438'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ocp_Skill_Type',
            fields=[
                ('job', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Job', on_delete=models.CASCADE)),
                ('facet_value', models.OneToOneField(related_name='ocp_skill_type', null=True, to='valueaccounting.FacetValue', blank=True, help_text='a related OCP FacetValue', verbose_name='ocp facet_value', on_delete=models.SET_NULL)),
                ('resource_type', models.OneToOneField(related_name='ocp_skill_type', null=True, to='valueaccounting.EconomicResourceType', blank=True, help_text='a related OCP ResourceType', verbose_name='ocp resource_type', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Skill Resources',
                'verbose_name_plural': 'o-> Types of General Skill Resources',
            },
            bases=('general.job',),
        ),
    ]
