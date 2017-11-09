# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-06 15:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0012_auto_20170717_1841'),
    ]

    operations = [
        migrations.AlterField(
            model_name='economicresourcetype',
            name='behavior',
            field=models.CharField(choices=[(b'work', 'Type of Work'), (b'account', 'Virtual Account'), (b'dig_curr', 'Digital Currency'), (b'dig_acct', 'Digital Currency Address'), (b'dig_wallet', 'Digital Currency Wallet'), (b'consumed', 'Produced/Changed + Consumed'), (b'used', 'Produced/Changed + Used'), (b'cited', 'Produced/Changed + Cited'), (b'produced', 'Produced/Changed only'), (b'other', 'Other')], default=b'other', max_length=12, verbose_name='behavior'),
        ),
    ]
