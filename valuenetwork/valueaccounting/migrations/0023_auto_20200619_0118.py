# Generated by Django 2.0.13 on 2020-06-19 01:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0022_auto_20200601_1731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentresourcetype',
            name='unit_of_value',
            field=models.ForeignKey(blank=True, limit_choices_to={'unit_type': 'value'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agent_resource_value_units', to='valueaccounting.Unit', verbose_name='unit of value'),
        ),
        migrations.AlterField(
            model_name='claim',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='claims', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='commitment',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commitments', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distributions', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='economicevent',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='economicresourcetype',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='context_resource_types', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='economicresourcetype',
            name='unit_of_price',
            field=models.ForeignKey(blank=True, limit_choices_to={'unit_type': 'value'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resource_type_price_units', to='valueaccounting.Unit', verbose_name='unit of price'),
        ),
        migrations.AlterField(
            model_name='economicresourcetype',
            name='unit_of_value',
            field=models.ForeignKey(blank=True, editable=False, limit_choices_to={'unit_type': 'value'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resource_type_value_units', to='valueaccounting.Unit', verbose_name='unit of value'),
        ),
        migrations.AlterField(
            model_name='exchange',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exchanges', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='exchangetype',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exchange_types', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='process',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processes', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='processpattern',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='process_patterns', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='processtype',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='process_types', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='resourcetypelist',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lists', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='transfer',
            name='context_agent',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_context': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfers', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
        migrations.AlterField(
            model_name='valueequation',
            name='context_agent',
            field=models.ForeignKey(limit_choices_to={'is_context': True}, on_delete=django.db.models.deletion.CASCADE, related_name='value_equations', to='valueaccounting.EconomicAgent', verbose_name='context agent'),
        ),
    ]
