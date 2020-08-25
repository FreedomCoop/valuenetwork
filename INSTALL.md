# Basic install for a Linux local development instance

OCP v1.0 has been successfully tested with Python 3.7+ (stable in debian buster when writing)

1- Install system dependencies: ::

    sudo apt install python3-setuptools python3-pyqt5 python3-pip python3-venv npm git

2- Point your terminal to your code projects folder (e.g. '~/Envs/') and create a python3 virtual environment (e.g. 'py3'): ::

    cd [installations dir]
    python3 -m venv py3

3- Clone the repo and enter the project folder: ::

    git clone https://github.com/FreedomCoop/valuenetwork.git ocp
    cd ocp

4- Activate the virtual environment and upgrade pip: ::

    source ../py3/bin/activate
    pip install -U pip
    pip install -U setuptools

(If you prefer to nest the ocp folder inside the py3 env folder, adapt the activate
command acordingly)

5- Install python dependencies: ::

    pip install -U -r requirements.txt --trusted-host dist.pinaxproject.com

6- Create npm build system and compile css+js: ::

    npm install
    npm run compile
    npm run optimize

7- Create any possibly missing migrations (e.g. for 'fobi') and create the sqlite database: ::

    ./manage.py makemigrations
    ./manage.py migrate

8- create a superuser for yourself so you can login: ::

    ./manage.py createsuperuser

9- To check all and run the tests: ::

    ./manage.py check
    ./manage.py test
    
10- To start a local server for development, the new way is (recompiling statics): ::

    npm run dev
    
...and the old way (non recompiling), just in case: ::

    ./manage.py runserver

Check everything is ok in http://127.0.0.1:8000 with web browser.



## Important:

- You'll need to create your own `local_settings.py` file (using the
`local_settings_example.py` as a template) to redefine some `ocp/settings.py`
values (e.g. languages, database, etc) and also to define the main context
agents settings about their custom login domains, css and js, email notification
servers, active services, etc.

- If you are dealing with a multi-language instance, please read carefully the
`docs/translations.md` doc.

- If you are installing also a faircoin wallet for the users to manage their own
faircoin accounts in OCP, please follow `docs/install_ocp_faircoin.md`

- If you want to deploy ocp in a production server please follow the
instructions at `docs/install_ocp_debian_apache_ssl.rst`


## Initial Data:

The migrate command runs a script to check for and create some basic units and
types (required to run the actually deployed instances).

When you log in for the first time, you should
create an EconomicAgent for yourself. Go into Admin,
which is on the pulldown menu by your username on the upper right.
Click on Economic agents, and then click on "add economic agent".
When you have added as much info as you want, go to the bottom
of the page, and select your username in the first User
select widget.
You will be the only user who will need to do this.

All other Agents and Users will be created during the membership process of any
context agent upgraded to an OCP Project (with moderated access and with public
visibility), once its custom register form is set-up in the fobi system and
connected to the project with its form slug field. To do that:

  - If not created yet, go to 'your projects' page and create the new project, 
    your agent will become a coordinator of this project.
  - Choose a 'moderated' joininng style (or 'shares') and a 'public' visibility 
    to have an external register form for non-logged users.
  - Go to `/fobi` url and create a form with the name of the project. Be aware
    of the resulting 'slug' by checking the url of the link to read the form.
    That slug will be the main identifier of the project in the local_settings
    file objects.
  - Define only the custom fields (questions) used in the project. Remember
    that the main user fields are already requested by the OCP (individual or
    group type, name and surname, nickname/username, email, phone, address and website), so
    focus only on the really custom questions for the project context, and
    follow a few rules described below.
  - Add the DB Store handler in the fobi form 'handlers' tab. 
  - Once the form is ready, set its 'slug' in the project's 'Custom project
    url slug' field. Verify the project's connection with its form with the links to view
    the form that appear in the project's page. 
  - Check the local_settings objects are properly defined with the project's fobi 'slug' as a key 
    for its options, and the project page shows the custom settings like the css and js rules, the 
    background image behind the logo image, etc.

Some fobi custom fields little rules, related the active services for a project:

  - If you're setting-up a project with Payment Gateways:
    - the selector fobi field must be internally named `payment_mode`.
    - The select options of that field should use as keys a short string
        representing the gateway (e.g. `transfer`, `faircoin`, `btc`, `ccard`, etc).
    - The local_settings PAYMENT_GATEWAYS object for the project should define for every
        gateway key a proper gateway block definition (see `ocp/local_settings_example.py`).

  - If you're setting-up a project with Shares:
    - The numeric fobi field that will store the amount of shares the user wants
        must be internally named `projectname_shares` (being 'projectname' the
        lowcase version of the project name without spaces).
    - The local_settings PROJECTS_LOGIN object for the project should have
        the `shares` active in its `services` block.
    - Edit the project details from the project page, and choose 'shares' as
        the joining style.
    - To create the project Shares use the form that appears at the project
        page (in the 'Offered Shares' block), once all the above is ready.
    - Once the share is defined (with its value related any currency) and
        the payment gateways defined in the local_settings file appear correctly
        in the projects page (with a green 'ok'), then you should create the
        exchanges_types related the active payment gateways by clicking the
        button 'Create Shares Exchange Types'.


If you're setting-up the Multicurrency system of Bank of the Commons:
  - The local_settings MULTICURRENCY object must be defined with the
        proper API urls and the BotC API secret key given to your instance.
  - The local_settings PROJECTS_LOGIN object for the project should include
        the `multicurrency` option as an active service.
  - For that project and their members will appear the option to connect
        with their existent BotC-Wallet account or create a new one from OCP.
  - The connection with BotC-Wallet is still readonly, so to move money
        you still have to use the https://wallet.bankofthecommons.coop site.



*Note: the original code fixtures are still broken. In the meantime, you can
get a test database from somebody.*
