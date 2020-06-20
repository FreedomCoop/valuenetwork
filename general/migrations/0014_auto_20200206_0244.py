# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2020-02-06 02:44


from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0013_record_changed_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record',
            name='changed_date',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='unitratio',
            name='rate',
            field=models.DecimalField(decimal_places=9, default=Decimal('0.0'), max_digits=50, verbose_name='Ratio multiplier'),
        ),
    ]
