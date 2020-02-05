# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0003_auto_20161130_2151'),
    ]

    operations = [
        migrations.AlterField(
            model_name='address',
            name='jobs',
            field=models.ManyToManyField(related_name='addresses', verbose_name='Related Jobs', to='general.Job', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', verbose_name='Addresses', through='general.rel_Human_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='companies',
            field=models.ManyToManyField(related_name='hum_companies', verbose_name='Companies', to='general.Company', through='general.rel_Human_Companies', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='jobs',
            field=mptt.fields.TreeManyToManyField(to='general.Job', verbose_name='Activities, Jobs, Skills', through='general.rel_Human_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='materials',
            field=models.ManyToManyField(to='general.Material', verbose_name='Material artworks', through='general.rel_Human_Materials', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', verbose_name='Non-material artworks', through='general.rel_Human_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='persons',
            field=models.ManyToManyField(related_name='hum_persons', verbose_name='Persons', to='general.Person', through='general.rel_Human_Persons', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='projects',
            field=models.ManyToManyField(related_name='hum_projects', verbose_name='Projects', to='general.Project', through='general.rel_Human_Projects', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='records',
            field=models.ManyToManyField(to='general.Record', verbose_name='Records', through='general.rel_Human_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='human',
            name='regions',
            field=models.ManyToManyField(to='general.Region', verbose_name='Regions', through='general.rel_Human_Regions', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', verbose_name='related Addresses', through='general.rel_Material_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='jobs',
            field=models.ManyToManyField(to='general.Job', verbose_name='related Arts/Jobs', through='general.rel_Material_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='materials',
            field=models.ManyToManyField(to='general.Material', verbose_name='related Material artworks', through='general.rel_Material_Materials', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', verbose_name='related Non-materials', through='general.rel_Material_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='material',
            name='records',
            field=models.ManyToManyField(to='general.Record', verbose_name='related Records', through='general.rel_Material_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='addresses',
            field=models.ManyToManyField(to='general.Address', verbose_name='related Addresses', through='general.rel_Nonmaterial_Addresses', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='jobs',
            field=models.ManyToManyField(to='general.Job', verbose_name='related Arts/Jobs', through='general.rel_Nonmaterial_Jobs', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='nonmaterials',
            field=models.ManyToManyField(to='general.Nonmaterial', verbose_name='related Non-material artworks', through='general.rel_Nonmaterial_Nonmaterials', blank=True),
        ),
        migrations.AlterField(
            model_name='nonmaterial',
            name='records',
            field=models.ManyToManyField(to='general.Record', verbose_name='related Records', through='general.rel_Nonmaterial_Records', blank=True),
        ),
        migrations.AlterField(
            model_name='rel_human_jobs',
            name='job',
            field=mptt.fields.TreeForeignKey(verbose_name='Job', to='general.Job', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='rel_human_jobs',
            name='relation',
            field=mptt.fields.TreeForeignKey(related_name='hu_job+', verbose_name='relation', blank=True, to='general.Relation', null=True, on_delete=models.SET_NULL),
        ),
    ]
