import requests
import time
import hashlib
import hmac
import logging
from random import randint
from base64 import b64decode

from django.conf import settings
from django.forms import ValidationError


class ChipChapAuthError(Exception):
    def __init__(self, message, errors):
        super(ChipChapAuthError, self).__init__(message)
        self.errors = errors


class ChipChapAuthConnection(object):

    def __init__(self):
        self.logger = self.init_logger()
        if 'client_id' in settings.MULTICURRENCY:
            self.able_to_connect = True
            cdata = settings.MULTICURRENCY
            self.client_id = cdata['client_id']
            self.client_secret = cdata['client_secret']
            self.access_key = cdata['access_key']
            self.access_secret = cdata['access_secret']
            self.url_new_user = cdata['url_new_user']
            self.url_client = cdata['url_client']
            self.url_history = cdata['url_history']
            self.url_balance = cdata['url_balance']
            if not hasattr(cdata, 'ocp_api_key'):
                self.ocp_api_key = None
                #raise ValidationError("Is needed the API key given by BotC wallet to this platform (settings).")
                print "WARN: Multiwallet Read-Only! To make payments is needed the API key given by OCP to the BotC wallet platform (in local_settings)."
                self.logger.error("WARN: Multiwallet Read-Only! To make payments is needed the API key given by OCP to the BotC wallet platform (in local_settings).")
            else:
                self.ocp_api_key = cdata['ocp_api_key']
                self.logger.info("Connected with an OCP api-key for safe access.")
            if not hasattr(cdata, "url_w2w"):
                self.url_w2w = None
                print("WARN: Multiwallet without W2W permissions! Can't let users pay the shares...")
                self.logger.error("WARN: Multiwallet without W2W permissions! Can't let users pay the shares...")
            else:
                self.url_w2w = cdata['url_w2w']
            if not "url_ticker" in cdata:
                self.url_ticker = None
                print("WARN: Multicurrency without Ticker! Can't process crypto prices (except faircoin)")
                self.logger.error("WARN: Multicurrency without Ticker! Can't process crypto prices (except faircoin)")
            else:
                self.url_ticker = cdata['url_ticker']
        else:
            self.able_to_connect = False
            self.logger.critical("Invalid configuration data to connect.")

    @classmethod
    def get(cls):
        return cls()

    @classmethod
    def init_logger(cls):
        logger = logging.getLogger("multicurrency")
        logger.setLevel(logging.WARNING)
        if 'log_file' in settings.MULTICURRENCY:
            fhpath = settings.MULTICURRENCY["log_file"]
        else:
            fhpath = "/".join(
                [settings.PROJECT_ROOT, "multicurrency.log", ])
        fh = logging.handlers.TimedRotatingFileHandler(
            fhpath, when="d", interval=1, backupCount=7)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return logger

    @classmethod
    def chipchap_x_signature(cls, access_key, access_secret):
        if len(access_secret) % 4:
            access_secret += '=' * (4 - len(access_secret) % 4)
        nonce = str(randint(0, 100000000))
        timestamp = str(int(time.time()))
        string_to_sign = access_key + nonce + timestamp
        signature = hmac.new(
            b64decode(access_secret), string_to_sign,
            digestmod=hashlib.sha256).hexdigest()
        headers = {
            'X-Signature': 'Signature access-key="' + access_key +
            '", nonce="' + nonce + '", timestamp="' + timestamp +
            '", version="2", signature="' + signature + '"'}
        return headers

    def new_chipchap_user(self, username, email, company_name, password,
                          repassword):
        if not self.able_to_connect:
            raise ChipChapAuthError('Connection Error', 'No data to connect')

        headers = ChipChapAuthConnection.chipchap_x_signature(
            self.access_key, self.access_secret)
        data = {
            'username': username,
            'email': email,
            'company_name': company_name,
            'password': password,
            'repassword': repassword,
        }
        response = requests.post(self.url_new_user, headers=headers, data=data)
        if int(response.status_code) == 201:
            self.logger.info("New chipchap user request for " + username
                             + " has been succesfully processed.")
            return response.json()
        else:
            msg = response.json()
            self.logger.critical(
                "New chipchap user request for " + username + " has returned "
                + str(response.status_code) + " status code. Error: "
                + response.text)
            raise ChipChapAuthError(
                'Error ' + str(response.status_code)
                + ': ' + msg['message'], response.text)

    def new_client(self, username, password):
        if not self.able_to_connect:
            raise ChipChapAuthError('Connection Error', 'No data to connect')

        headers = ChipChapAuthConnection.chipchap_x_signature(
            self.access_key, self.access_secret)
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
            self.logger.critical(
                "Authentication request for " + username + " has returned "
                + str(response.status_code) + " status code. Error: "
                + response.text)
            raise ChipChapAuthError(
                'Error ' + str(response.status_code), response.text)

    def wallet_history(self, access_key, access_secret, limit=10, offset=0):
        if not self.able_to_connect:
            raise ChipChapAuthError('Connection Error', 'No data to connect')

        headers = ChipChapAuthConnection.chipchap_x_signature(
            access_key, access_secret)
        params = {
            "limit": limit,
            "offset": offset,
        }
        tx_list = requests.get(
            self.url_history, headers=headers, params=params)
        balance = requests.get(self.url_balance, headers=headers)
        if int(tx_list.status_code) == 200 and int(balance.status_code) == 200:
            return tx_list.json(), balance.json()
        else:
            error = str(balance.status_code) + ' and ' + str(
                tx_list.status_code)
            msg = balance.text + ' and ' + tx_list.text
            self.logger.critical("Balance and history requests have returned "
                                 + error + " status codes. Error: " + msg)
            raise ChipChapAuthError('Error ' + error, msg)

    def wallet_balance(self, access_key, access_secret):
        if not self.able_to_connect:
            raise ChipChapAuthError('Connection Error', 'No data to connect')
        headers = ChipChapAuthConnection.chipchap_x_signature(
            access_key, access_secret)

        balance = requests.get(self.url_balance, headers=headers)
        if int(balance.status_code) == 200:
            return balance.json()
        else:
            error = str(balance.status_code)
            msg = balance.text
            self.logger.critical("Balance request have returned "
                                 + error + " status code. Error: " + msg)
            raise ChipChapAuthError('Error ' + error, msg)

    def send_w2w(self, access_key, access_secret, unit, amount, username, scale):
        if not self.able_to_connect:
            raise ChipChapAuthError('Connection Error', 'No data to connect')
        headers = ChipChapAuthConnection.chipchap_x_signature(
            access_key, access_secret)

        params = {
            'username': username,
            'amount': amount,
        }
        payment = requests.get(self.url_w2w+(unit), headers=headers, params=params)
        if int(payment.status_code) == 200:
            return payment.json()
        else:
            error = str(payment.status_code)
            msg = payment.text
            self.logger.critical("Payment w2w request have returned "
                                 + error + " status code. Error: " + msg)
            raise ChipChapAuthError('Error ' + error, msg)

