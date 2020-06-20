# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-12-02 18:25


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('general', '0010_unit_ocp_unit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unit',
            name='ocp_unit',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='gen_unit', to='valueaccounting.Unit', verbose_name='OCP Unit'),
        ),
    ]
