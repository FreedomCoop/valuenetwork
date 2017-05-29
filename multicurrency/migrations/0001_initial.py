# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-28 20:54
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('valueaccounting', '0009_auto_20170422_0732'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MulticurrencyAuth',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('auth_user', models.CharField(editable=False, max_length=100)),
                ('access_key', models.CharField(editable=False, max_length=100)),
                ('access_secret', models.CharField(editable=False, max_length=100)),
                ('created', models.DateField(auto_now_add=True)),
                ('updated', models.DateField(auto_now=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='valueaccounting.EconomicAgent')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
