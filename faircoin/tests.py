# -*- coding: utf-8 -*-

from mock import patch
import json, time

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from valuenetwork.valueaccounting.models import AgentType, EconomicAgent,\
    AgentUser, AgentResourceRoleType, EconomicResourceType
from faircoin.utils import send_command

def create_user_agent():
    individual_at, c = AgentType.objects.get_or_create(
        name='Individual', party_type='individual', is_context=False)
    test_agent, c = EconomicAgent.objects.get_or_create(name='test_agent',
        nick='test_agent', agent_type=individual_at,  is_context=False)
    cooperative_at, c = AgentType.objects.get_or_create(
        name='Cooperative', party_type='organization', is_context=True)
    EconomicAgent.objects.get_or_create(name='Freedom Coop',
        nick='Freedom Coop', agent_type=cooperative_at, is_context=True)
    test_user = User.objects.create(username='test_user')
    test_user.set_password('test_user_passwd')
    test_user.save()
    AgentUser.objects.get_or_create(agent=test_agent, user=test_user)
    return test_agent

def create_faircoin_resource(agent):
    AgentResourceRoleType.objects.get_or_create(is_owner=True)
    EconomicResourceType.objects.get_or_create(behavior="dig_acct")
    address = "TestfaircoinAddress"
    resource = agent.create_faircoin_resource(address)
    return resource

def fake_send_command(cmd, params):
    if cmd == "is_connected" or cmd == "is_valid" or cmd == "is_mine":
        return True
    elif cmd == "network_fee":
        return 1000
    elif cmd == "get_address_balance":
        return [0, 0, 0]
    elif cmd == "get_address_history":
        return []
    else:
        return None

class FaircoinTest(TestCase):

    def setUp(self):
        print()
        print("------- Faircoin Account Test (start)-------")
        self.client = Client()
        self.agent = create_user_agent()
        self.resource = create_faircoin_resource(self.agent)

    # TODO: Use @patch mock decorator for mocking faircoin.utils.send_command
    def test_faircoin_views_and_templates(self):
        self.client.login(username='test_user', password='test_user_passwd')

        url = reverse('manage_faircoin_account', args=[self.resource.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print("t- manage_faircoin_account ok!")

        url = reverse('faircoin_history', args=[self.resource.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print("t- faircoin_history ok!")

        print("------- faircoin account test (end) -------")
