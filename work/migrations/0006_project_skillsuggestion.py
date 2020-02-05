# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0004_auto_20160817_2119'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('work', '0005_auto_20160810_1809'),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('joining_style', models.CharField(default=b'moderated', max_length=12, verbose_name='joining style', choices=[(b'moderated', 'moderated'), (b'autojoin', 'autojoin')])),
                ('visibility', models.CharField(default=b'private', max_length=12, verbose_name='visibility', choices=[(b'private', 'private'), (b'FCmembers', 'only FC members'), (b'public', 'public')])),
                ('agent', models.OneToOneField(related_name='project', verbose_name='agent', to='valueaccounting.EconomicAgent', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='SkillSuggestion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('skill', models.CharField(help_text='A new skill that you want to offer that is not already listed', max_length=128, verbose_name='skill')),
                ('suggestion_date', models.DateField(auto_now_add=True, null=True)),
                ('suggested_by', models.ForeignKey(related_name='skill_suggestion', blank=True, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='suggested by', on_delete=models.SET_NULL)),
            ],
        ),
    ]
