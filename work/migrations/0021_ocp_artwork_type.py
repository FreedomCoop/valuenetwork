# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0006_facet_clas'),
        ('general', '0004_auto_20161201_1831'),
        ('work', '0020_ocp_skill_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ocp_Artwork_Type',
            fields=[
                ('artwork_type', models.OneToOneField(parent_link=True, primary_key=True, serialize=False, to='general.Artwork_Type', on_delete=models.CASCADE)),
                ('context_agent', models.ForeignKey(related_name='ocp_artwork_types', blank=True, to='valueaccounting.EconomicAgent', help_text='a related context EconomicAgent', null=True, verbose_name='context agent', on_delete=models.SET_NULL)),
                ('facet', models.OneToOneField(related_name='ocp_artwork_type', null=True, to='valueaccounting.Facet', blank=True, help_text='a related OCP Facet', verbose_name='ocp facet', on_delete=models.SET_NULL)),
                ('facet_value', models.ForeignKey(related_name='ocp_artwork_type', blank=True, to='valueaccounting.FacetValue', help_text='a related OCP FacetValue', null=True, verbose_name='ocp facet_value', on_delete=models.SET_NULL)),
                ('material_type', mptt.fields.TreeForeignKey(related_name='ocp_artwork_types', blank=True, to='general.Material_Type', help_text='a related General Material Type', null=True, verbose_name='general material_type', on_delete=models.SET_NULL)),
                ('nonmaterial_type', mptt.fields.TreeForeignKey(related_name='ocp_artwork_types', blank=True, to='general.Nonmaterial_Type', help_text='a related General Non-material Type', null=True, verbose_name='general nonmaterial_type', on_delete=models.SET_NULL)),
                ('resource_type', models.OneToOneField(related_name='ocp_artwork_type', null=True, to='valueaccounting.EconomicResourceType', blank=True, help_text='a related OCP ResourceType', verbose_name='ocp resource_type', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Type of General Artwork/Resource',
                'verbose_name_plural': 'o-> Types of General Artworks/Resources',
            },
            bases=('general.artwork_type',),
        ),
    ]
