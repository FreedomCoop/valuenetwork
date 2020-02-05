# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fobi_contrib_plugins_form_handlers_db_store', '0001_initial'),
        ('work', '0009_project_fobi_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='joinrequest',
            name='fobi_data',
            field=models.OneToOneField(related_name='join_request', null=True, to='fobi_contrib_plugins_form_handlers_db_store.SavedFormDataEntry', blank=True, help_text='this join request is linked to this custom form (fobi SavedFormDataEntry)', verbose_name='custom fobi id', on_delete=models.SET_NULL),
        ),
        migrations.AlterField(
            model_name='joinrequest',
            name='project',
            field=models.ForeignKey(related_name='join_requests', verbose_name='project', to='work.Project', help_text='this join request is for joining this Project', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='joinrequest',
            name='type_of_user',
            field=models.CharField(default=b'individual', max_length=12, verbose_name='Type of user', choices=[(b'individual', 'individual'), (b'collective', 'collective')]),
        ),
    ]
