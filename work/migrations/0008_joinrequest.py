# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0004_auto_20160817_2119'),
        ('work', '0007_auto_20160830_2127'),
    ]

    operations = [
        migrations.CreateModel(
            name='JoinRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('request_date', models.DateField(auto_now_add=True, null=True)),
                ('type_of_user', models.CharField(default=b'individual', max_length=12, verbose_name='Type of user', choices=[(b'individual', 'individual user'), (b'collective', 'collective user')])),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('surname', models.CharField(max_length=255, verbose_name='Surname (for individual join requests)', blank=True)),
                ('requested_username', models.CharField(max_length=32, verbose_name='Requested username')),
                ('email_address', models.EmailField(max_length=96, verbose_name='Email address')),
                ('phone_number', models.CharField(max_length=32, null=True, verbose_name='Phone number', blank=True)),
                ('address', models.CharField(max_length=255, null=True, verbose_name='Town/Region where you are based', blank=True)),
                ('agent', models.ForeignKey(related_name='project_join_requests', blank=True, to='valueaccounting.EconomicAgent', help_text='this join request became this EconomicAgent', null=True, verbose_name='agent', on_delete=models.SET_NULL)),
                ('project', models.ForeignKey(related_name='join_requests', verbose_name='project', to='work.Project', help_text='this join request is for joining this EconomicAgent', on_delete=models.CASCADE)),
            ],
        ),
    ]
