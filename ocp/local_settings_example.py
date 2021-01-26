#!/usr/bin/python
# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.text import format_lazy
from django.utils.translation import ugettext_lazy as _
from decimal import Decimal

"""
    The settings.py will import this file, if it exists
    and the local_settings will override settings with the same name.

    You also want your local_settings.py to be different
    on a development machine and a server,
    in ways that will be mentioned below.

    Note: don't use this local_settings_example.py.
    It is internally inconsistent to show some choices.
    Create your own local_settings.py file
    to fit your own needs.
"""

#for a development machine
DEBUG = True
#for a server
#DEBUG = False
TEMPLATE_DEBUG = DEBUG

#this is nice for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'ocp.sqlite'
    }
}
#for a server, you want a real database
'''DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.', # Add 'postgresql_psycopg2', 'mysql', or 'oracle'.
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',                      # Set to empty string for default.
    }
}'''


# ocp settings can be overridden
USE_WORK_NOW = False
SUBSTITUTABLE_DEFAULT = False

SITE_NAME = 'OCP'
STATIC_URL = "/static/" # your desired static url

MEDIA_URL = "/media/" # your desired media url
MEDIA_ROOT = "/home/user/Envs/py3/ocp/site_media/media/" # your desired media folder

#example: Greece
MAP_LATITUDE = 38.2749497
MAP_LONGITUDE = 23.8102717
MAP_ZOOM = 6

#and you can override any other settings in settings.py

# custom log file position (remember to create any needed folder to store the logs)
settings.LOGGING['handlers']['applogfile']['filename'] = '../log/ocp_debug.log' # put your desired path!
# if internal faircoins:
settings.LOGGING['handlers']['fairlogfile']['filename'] = '../log/fair_debug.log' # put your desired path!

# place your server default email address
DEFAULT_FROM_EMAIL = ""

# set the default server email SMTP
EMAIL_USE_TLS = True
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = 587

# to run the multicurrency service you need to define the connection details with Bank of the Commons
MULTICURRENCY = {
      'client_id': '',
      'client_secret': '',
      'access_key': '',
      'access_secret': '',
      'url_client': "",
      'url_history': "",
      'url_balance': "",
      'url_new_user': "",
      'url_ticker': 'https://api.bankofthecommons.coop/exchange/v1/ticker/', # +:currency
      'url_btc_tx_json': 'https://blockchain.info/rawtx/', # or any other btc block explorer endpoint giving json from a tx
      'url_btc_tx': 'https://www.blockchain.com/btc/tx/', # or any other btc block explorer url giving a view of the tx
      'url_fair_tx': 'https://chain.fair.to/transaction?transaction=', # or any other faircoin block explorer
      'log_file': '../log/multicurrency.log', # put your desired log file path
}

RANDOM_PASSWORD_LENGHT = 10

CRYPTOS = ('btc', 'eth', 'fair')
#CRYPTO_LAPSUS = 60 # for example, to forget the stored unit-ratio after 1 minute, set 60 seconds here
#CRYPTO_DECIMALS = 9 # put the desired crypto assets shown decimals
#DECIMALS = Decimal('0.000000000') # put the same number of zeros here


# To accept payments for the shares of one project, define here the methods details

PAYMENT_GATEWAYS = {
    'slug-of-the-project': {
        'transfer': {
            'url':'',
            'html': format_lazy("You can set your transfer from your bank account to our account:<br>IBAN:  <b>{iban}</b><br>BIC/Swift:  <b>{bic}</b><br>Concept:  <b>Put your new username!</b><br>Account owner:  <b>{owner}</b><br>Bank name:  <b>{bank}</b><br>Bank address:  <b>{baddress}</b>", iban="the_iban_number", bic="the_bic_code", owner="the_account_owner_name", bank="the_bank_name", baddress="the_bank_address"),
            'unit':'EUR'
        },
        'ccard': {
            'url':'url of the cc gateway',
            'html':_('Pay your Shares'),
            'unit':'EUR',
            'secret':'',
            'tokenorder':'',
            'algorithm':'',
            'fees': {
                'percent':0,
                'fixed':0,
                'unit':'EUR',
                'payer':'user' # or 'project'
            }
        },
        'faircoin': {
            'url':'',
            'html':'Please send the actual value in euros of your shares (converted to faircoin) to the FairCoin Address: <b>the_faircoin_address</b>',
            'unit':'FAIR',
            'margin':0.0034 # the difference margin accepted between the payed amount and the calculated amount
        },
        #'btc': {
        #    'url':'',
        #    'html':'Btc Address: <b>the btc address</b>',
        #    'unit':'BTC',
        #    'margin':0.00000001,
        #    'addrarr': ["BTC_address_ofTheProject'addrarr': ["1D7UWNrUxHRKAKLghnvRif7DPz7e2TBg1W"],"],
        #}
    }
}


# When different domains of different projects point to the same OCP, here you define the custom login page for each context domain and their available services

PROJECTS_LOGIN = {
    'slug-of-the-project': {
        'html':_("<p>Place any html text for the custom login page.</p>"),
        'background_url':'img/custom_background.jpg',
        'css':'/* put here any custom css rules */',
        'js':"$(document).ready(function(){  });",
        'services': [
            #'faircoins',
            'multicurrency',
            #'projects',
            'exchanges',
            #'tasks',
            #'skills',
            #'processes',
            'shares',
        ],
        'domains': [
            'custom.domains.of.the.project',
            '127.0.0.1:8000'
        ],
        'smtp': {
            'host': '', # put the smtp server host name
            'username': '', # put the smtp host username
            'password': '', # put the smtp host password
            'port': 587, # change to your port
            'use_tls': True # set TLS to True or False
        }
    },
    'another-project-slug': {
        'html':_("<p>Place any html text for the custom login page.</p>"),
        'background_url':'img/project2_background.jpg',
        'css':'',
        #'js':'',
        'services': [
            'faircoins',
            #'multicurrency',
            'projects',
            'exchanges',
            'tasks',
            'skills',
            'processes',
            'shares',
        ],
        'domains': [
            'custom.domain.of.another.project',
            #'127.0.0.1:8000'
        ],
        'smtp': {
            'host': '', # put the smtp server host name
            'username': '', # put the smtp host username
            'password': '', # put the smtp host password
            'port': 587, # change to your port
            'use_tls': True # set TLS to True or False
        }
    }
}

settings.LOGIN_EXEMPT_URLS += [
    r'^slug-of-the-project',
    r'^another-project-slug',
    r'^total-shares/slug-of-the-project', # to open a public url showing actual shares totals for the project
    r'^update-share-payment/slug-of-the-project' # to open a special listener for the project to update the share payment status
]
