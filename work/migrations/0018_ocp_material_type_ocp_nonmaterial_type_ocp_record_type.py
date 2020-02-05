# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0006_facet_clas'),
        ('general', '0004_auto_20161201_1831'),
        ('work', '0017_auto_20161016_1446'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ocp_Material_Type',
            fields=[
                ('material_type', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Material_Type', on_delete=models.CASCADE)),
                ('facet_value', models.OneToOneField(related_name='ocp_material_type', null=True, to='valueaccounting.FacetValue', blank=True, help_text='a related OCP FacetValue', verbose_name='ocp facet_value', on_delete=models.SET_NULL)),
                ('resource_type', models.OneToOneField(related_name='ocp_material_type', null=True, to='valueaccounting.EconomicResourceType', blank=True, help_text='a related OCP ResourceType', verbose_name='ocp resource_type', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Material Resources',
                'verbose_name_plural': 'o-> Types of General Material Resources',
            },
            bases=('general.material_type',),
        ),
        migrations.CreateModel(
            name='Ocp_Nonmaterial_Type',
            fields=[
                ('nonmaterial_type', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Nonmaterial_Type', on_delete=models.CASCADE)),
                ('facet_value', models.OneToOneField(related_name='ocp_nonmaterial_type', null=True, to='valueaccounting.FacetValue', blank=True, help_text='a related OCP FacetValue', verbose_name='ocp facet_value', on_delete=models.SET_NULL)),
                ('resource_type', models.OneToOneField(related_name='ocp_nonmaterial_type', null=True, to='valueaccounting.EconomicResourceType', blank=True, help_text='a related OCP ResourceType', verbose_name='ocp resource_type', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Non-material Resources',
                'verbose_name_plural': 'o-> Types of General Non-material Resources',
            },
            bases=('general.nonmaterial_type',),
        ),
        migrations.CreateModel(
            name='Ocp_Record_Type',
            fields=[
                ('record_type', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Record_Type', on_delete=models.CASCADE)),
                ('exchange_type', models.ForeignKey(related_name='ocp_record_types', verbose_name='ocp exchange type', blank=True, to='valueaccounting.ExchangeType', null=True, on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Record',
                'verbose_name_plural': 'o-> Types of General Records',
            },
            bases=('general.record_type',),
        ),
    ]
