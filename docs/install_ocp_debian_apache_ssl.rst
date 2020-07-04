This is a howto for installing ocp in a debian/ubuntu system.

The ocp still runs on Python2 but the electrumfair wallet runs on Python3. We better create a 'ocp' linux user with py2 for the app and a 'wallet' linux user with py3 for the wallet.

- Install dependencies in the system: ::

    sudo apt-get install virtualenv git libjpeg-dev zlib1g-dev build-essential gettext
    sudo apt-get install python-setuptools python2.7-dev python-pil python-qt4

- Install electrumfair and daemon dependencies in the system (python3): ::

    sudo apt-get install python3-setuptools python3-pyqt5 python3-pip
    sudo pip3 install https://download.faircoin.world/electrum/ElectrumFair-3.0.5.tar.gz
    sudo pip install jsonrpclib

- Create an electrumfair wallet (as 'wallet' user or root): ::

    electrumfair create

This gives you seed to keep in safe place, and ask for password to encript the wallet.
All the electrumfair data will be created in /home/user/.electrumfair/ directory.
Be carefull if you already have an electrum-fair wallet installed with the same user.

- Download from github and copy daemon sample files: ::

    cd [installation dir]
    git clone https://github.com/FreedomCoop/valuenetwork.git
    cd valuenetwork
    cp faircoin/daemon/daemon_service.sample faircoin/daemon/daemon_service
    chmod a+x faircoin/daemon/daemon_service
    cp faircoin/daemon/daemon.py.sample faircoin/daemon/daemon.py
    chmod a+x faircoin/daemon/daemon.py
    cp faircoin/daemon/daemon.conf.sample faircoin/daemon/daemon.conf

- Setup daemon: ::

    vim faircoin/daemon/daemon_service #Set paths and user for starting the daemon.
    vim faircoin/daemon/daemon.conf #Set wallet config
    sudo ./faircoin/daemon/daemon_service start
    sudo ./faircoin/daemon/daemon_service status

If daemon runs ok, *daemon_service status* returns *Running*.
For ocp instances in production, better to move daemon_service to */etc/init.d/* and daemon.conf to */etc/*

- Create virtual enviroment and update pip and setuptools: ::

    cd [installation dir]
    virtualenv env
    cd valuenetwork
    source ../env/bin/activate
    pip install --upgrade pip
    pip install --upgrade setuptools

- Install ocp python dependencies: ::

    pip install -U -r requirements.txt --trusted-host dist.pinaxproject.com
    pip install --no-deps easy_thumbnails
    pip install Image

- Create database, load some data, run tests and start with dev server: ::

    python manage.py makemigrations
    python manage.py migrate

(Note: these fixtures are broken now. Will be fixed, but in the meantime, get a test database from somebody.) ::

    python manage.py loaddata ./fixtures/starters.json
    python manage.py loaddata ./fixtures/help.json

    python manage.py test valuenetwork.valueaccounting.tests
    python manage.py runserver

- Check everything is ok in http://127.0.0.1:8000 with web browser.

- Stop the dev web server: ctrl+c

- Set up a crontab like this: ::

    crontab -e

Add one task to the cron: ::

    * * * * * (cd /path/to/installation/valuenetwork; /path/to/installation/env/bin/python manage.py send_faircoin_requests > /dev/null 2>&1)

Apache2 and wsgi configuration
==============================

- Install system dependencies: ::

    sudo apt-get install apache2 libapache2-mod-wsgi

- Setup a secure website with certification. See:

    https://letsencrypt.org

    https://wiki.debian.org/Self-Signed_Certificate

- Configure virtual host: ::

    sudo vim /etc/apache2/sites-available/ocp-ssl.conf

This is a sample of the file: ::

    WSGIPythonPath /absolute/path/to/installation/valuenetwork:/absolute/path/to/installation/env/lib/python2.7/site-packages

    <IfModule mod_ssl.c>
        <VirtualHost _default_:443>

            ServerName [your domain]
            ServerAdmin webmaster@localhost

            ErrorLog ${APACHE_LOG_DIR}/error.log
            CustomLog ${APACHE_LOG_DIR}/access.log combined

            WSGIScriptAlias / /absolute/path/to/installation/valuenetwork/valuenetwork/wsgi.py:/absolute/path/to/installation/env/lib/python2.7/site-packages

            Alias /site_media/static/ /absolute/path/to/installation/static/
            Alias /static/ /absolute/path/to/installation/static/

            <Directory /absolute/path/to/installation/valuenetwork/valuenetwork/>
                <Files wsgi.py>
                    Require all granted
                </Files>
            </Directory>

            <Directory /absolute/path/to/installation/env/lib/python2.7/site-packages/>
                Require all granted
            </Directory>

        </VirtualHost>
    </IfModule>

- Enable site ocp-ssl: ::

    sudo a2ensite ocp-ssl.conf
    sudo service apache2 reload

- Modify wsgi.py: ::

    valuenetwork/wsgi.py

Add to the file: ::

    import sys
    sys.path.append('/absolute/path/to/installation/env/lib/python2.7/site-packages')
    sys.path.append('/absolute/path/to/installation/valuenetwork/')

If you get a *forbidden* error, make sure that apache has permission to access to the application, by checking directory and wsgi.py file permissions for user www-data and/or adding to /etc/apache2/apache2.conf: ::

    <Directory /absolute/path/to/installation/>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

- Create local_settings.py: ::

    vim local_settings.py

Include absolute path to database, STATIC_ROOT constant and map settings in local_settings.py: ::

    DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/absolute/path/to/installation/valuenetwork/valuenetwork.sqlite'
    }
    }
    STATIC_ROOT = "/absolute/path/to/installation/static/"
    MAP_LATITUDE = 48.1293204
    MAP_LONGITUDE = 4.153537
    MAP_ZOOM = 4
    DEFAULT_HTTP_PROTOCOL = "https"

- Create the static directory: ::

    mkdir /absolute/path/to/installation/static

- Run collectstatic: ::

    ./manage.py collectstatic

If static files are not visible in the site by a permissions error, you need to give access in apache2.conf: ::

    <Directory /absolute/path/to/installation/static/>
        Require all granted
    </Directory>

- Try to login. If you get an *unable to open database file* error, check apache (www-data) can read and write the db file (valuenetwork.sqlite), and the above directory too.


- An email server or an external email service with SMTP will be needed for notifications and recovering passwords. If you choose an external email service, add to local_settings.py: ::

    EMAIL_USE_TLS = True
    EMAIL_HOST = <external email service>
    EMAIL_HOST_USER = <user>
    EMAIL_HOST_PASSWORD = <passwd>
    EMAIL_PORT = <port external service>

When the site is able to send emails, another crontab configuration is needed: ::

    * * * * * (cd /path/to/installation/valuenetwork; /path/to/installation/env/bin/python manage.py emit_notices >> /path/to/installation/valuenetwork/emit_notices.log)

And in order to recive emails with correct links, you need to login with admin user and change in: ::

    https://[your domain]/admin/sites/site/1/

the field *Domain name* with your domain.


That's all!
