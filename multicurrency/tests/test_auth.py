
from mock import patch
import json

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from multicurrency.models import MulticurrencyAuth
from multicurrency.utils import ChipChapAuthConnection, ChipChapAuthError
from valuenetwork.valueaccounting.models import AgentType, EconomicAgent, AgentUser


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

def fake_new_client(self, username, password):
    if username == 'auth_user' and password == 'auth_user_passwd':
        response = {
            'username': username,
            'access_key': 'TestAccessKey',
            'access_secret': 'TestAccessSecret'
        }
        return response
    else:
        raise ChipChapAuthError('Error Testing', 'Authentication failed.')

def fake_wallet_history(self, access_key, access_secret, limit=10, offset=0):
    if access_key == 'TestAccessKey' and access_secret == 'TestAccessSecret':
        with open('multicurrency/tests/chipchap_test_tx.json', 'r') as tx_file:
            tx_list = json.load(tx_file)
        with open('multicurrency/tests/chipchap_test_balance.json', 'r') as balance_file:
            balance = json.load(balance_file)
        return tx_list, balance
    else:
        raise ChipChapAuthError('Error Testing', 'Receiving transaction list failed.')

class ChipChapAuthTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.agent = create_user_agent()

    @patch.object(ChipChapAuthConnection, 'new_client', fake_new_client)
    @patch.object(ChipChapAuthConnection, 'wallet_history', fake_wallet_history)
    def test_create_multicurrency_auth(self):
        print("-------- Multicurrency Test (readonly) --------")
        self.client.login(username='test_user', password='test_user_passwd')

        url = reverse('multicurrency_auth', args=[self.agent.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Authenticate ChipChap user
        data = {
            "loginname": "auth_user",
            "wallet_password": "auth_user_passwd",
        }
        response = self.client.post(url, data=data)
        #import pdb; pdb.set_trace()
        self.assertEqual(response.status_code, 302)

        auth = MulticurrencyAuth.objects.filter(agent=self.agent)
        self.assertEqual(auth.count(), 1)
        print("t- authenticated!")

        # Visit tx list of agent/user
        url = reverse('multicurrency_history', args=[self.agent.id, auth[0].id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print("t- multicurrency history loaded!")

        # Logout ChipChap user
        url = reverse('multicurrency_deleteauth', args=[self.agent.id, auth[0].id])
        response = self.client.post(url, data = {'hidden_delete': 'delete'})
        self.assertEqual(response.status_code, 302)

        auth = MulticurrencyAuth.objects.all()
        self.assertEqual(auth.count(), 0)
        print("t- deleted auth!")

        print("------- end multicurrency test -------")
