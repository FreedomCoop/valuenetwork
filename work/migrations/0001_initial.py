# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('valueaccounting', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MembershipRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('request_date', models.DateField(auto_now_add=True, null=True)),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('surname', models.CharField(max_length=255, verbose_name='surname (for individuals)', blank=True)),
                ('requested_username', models.CharField(max_length=32, verbose_name='requested username')),
                ('email_address', models.EmailField(max_length=96, verbose_name='email address')),
                ('phone_number', models.CharField(max_length=32, null=True, verbose_name='phone number', blank=True)),
                ('address', models.CharField(max_length=255, verbose_name='address (where do you live?)', blank=True)),
                ('native_language', models.CharField(max_length=255, verbose_name='native language')),
                ('type_of_membership', models.CharField(default=b'individual', max_length=12, verbose_name='type of membership', choices=[(b'individual', 'individual'), (b'collective', 'collective')])),
                ('membership_for_services', models.BooleanField(default=False, help_text='you have legal entity and want to offer services or products to the cooperative', verbose_name='Membership for services')),
                ('autonomous_membership', models.BooleanField(default=False, help_text="you don't have legal entity and want to use the cooperative to make invoices either from inside and to outside the cooperative", verbose_name='Autonomous membership')),
                ('ocp_user_membership', models.BooleanField(default=False, help_text='for those that only want to use the OCP platform', verbose_name='OCP user membership')),
                ('consumer_membership', models.BooleanField(default=False, help_text="you don't offer any product or service but want to consume through it and support the cooperative", verbose_name='Consumer membership')),
                ('number_of_shares', models.IntegerField(default=1, help_text='How many shares do you want to underwrite? (minimum one. Each share worth 600 Faircoin = 30 Euro.', verbose_name='number of shares')),
                ('work_for_shares', models.BooleanField(default=False, help_text="You can get 1 share for 6 hours of work. If you choose this option, we will send you a list of tasks and the deadline. You won't have full access before the tasks are accomplished.", verbose_name='work for one share')),
                ('description', models.TextField(help_text='Describe your project or collective and skills or abilities you can offer to the cooperative', verbose_name='Description')),
                ('website', models.CharField(max_length=255, verbose_name='website', blank=True)),
                ('how_do_you_know_fc', models.TextField(verbose_name='How do you know Freedom Coop?', blank=True)),
                ('known_member', models.TextField(verbose_name='Do you know any member already from FreedomCoop or FairCoop? If so, who?', blank=True)),
                ('comments_and_questions', models.TextField(verbose_name='Comments and questions', blank=True)),
                ('agent', models.ForeignKey(related_name='membership_requests', blank=True, to='valueaccounting.EconomicAgent', help_text='this membership request became this EconomicAgent', null=True, verbose_name='agent', on_delete=models.SET_NULL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
