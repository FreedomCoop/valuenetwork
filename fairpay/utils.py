import requests, json, time, hashlib, hmac
from random import randint
from base64 import b64encode, b64decode
from django.conf import settings

class ChipChapAuthError(Exception):
    def __init__(self, message, errors):
        super(ChipChapAuthError, self).__init__(message)
        self.errors = errors

class ChipChapAuthConnection(object):

    def __init__(self):
        connecting_data = settings.FAIRPAY
        self.client_id = connecting_data['client_id']
        self.client_secret = connecting_data['client_secret']
        self.access_key = connecting_data['access_key']
        self.access_secret = connecting_data['access_secret']
        self.url_client = "https://api.chip-chap.com/oauth/v1/public"
        self.url_history = "https://api.chip-chap.com/user/v2/wallet/transactions"

    @classmethod
    def get(cls):
        return cls()

    @classmethod
    def chipchap_x_signature(cls, access_key, access_secret):
        if len(access_secret) % 4:
            access_secret += '=' * (4 - len(access_secret) % 4)
        nonce = str(randint(0, 100000000))
        timestamp = str(int(time.time()))
        string_to_sign = access_key + nonce + timestamp
        signature = hmac.new(b64decode(access_secret), string_to_sign,
            digestmod=hashlib.sha256).hexdigest()
        headers = {'X-Signature':
            'Signature access-key="' + access_key +
            '", nonce="' + nonce +
            '", timestamp="' + timestamp +
            '", version="2", signature="' + signature +
            '"'}
        return headers

    def new_client(self, username, password):
        headers = ChipChapAuthConnection.chipchap_x_signature(self.access_key, self.access_secret)
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': username,
            'password': password,
        }
        response = requests.post(self.url_client, headers=headers, data=data)
        if int(response.status_code) == 200:
            return response.json()
        else:
            raise ChipChapAuthError('Error ' + str(response.status_code), response.text)

    def wallet_history(self, access_key, access_secret, limit=10, offset=0):
        headers = ChipChapAuthConnection.chipchap_x_signature(access_key, access_secret)
        data = {
            "limit": limit,
            "offset": offset,
        }
        response = requests.get(self.url_history, headers=headers, data=data)
        if int(response.status_code) == 200:
            return response.json()
        else:
            raise ChipChapAuthError('Error ' + str(response.status_code), response.text)
