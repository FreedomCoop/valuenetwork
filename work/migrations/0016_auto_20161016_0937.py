# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0004_auto_20160817_2119'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('work', '0015_auto_20161006_1826'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceNumber',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('invoice_number', models.CharField(max_length=128, verbose_name='invoice number')),
                ('invoice_date', models.DateField(verbose_name='invoice date')),
                ('year', models.IntegerField(verbose_name='year')),
                ('quarter', models.IntegerField(verbose_name='quarter')),
                ('sequence', models.IntegerField(verbose_name='sequence')),
                ('created_date', models.DateField(auto_now_add=True)),
                ('created_by', models.ForeignKey(related_name='invoice_numbers_created', editable=False, to=settings.AUTH_USER_MODEL, verbose_name='created by', on_delete=models.SET_NULL)),
                ('exchange', models.ForeignKey(related_name='invoice_numbers', verbose_name='exchange', blank=True, to='valueaccounting.Exchange', null=True, on_delete=models.SET_NULL)),
                ('member', models.ForeignKey(related_name='invoice_numbers', verbose_name='member', to='valueaccounting.EconomicAgent', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-invoice_date',),
            },
        ),
        migrations.AlterField(
            model_name='newfeature',
            name='name',
            field=models.CharField(max_length=24, verbose_name='name'),
        ),
    ]
