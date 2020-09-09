# Basic install for a Linux local development instance

OCP v1.0 has been successfully tested with Python 3.7+ (stable in Debian buster at the time of writing)

1- Install system dependencies:

    sudo apt install python3-setuptools python3-pyqt5 python3-pip python3-venv npm git

2- Point your terminal to your code projects folder (e.g. '~/Envs/') and create a python3 virtual environment (e.g. 'py3'):

    cd [installations dir]
    python3 -m venv py3

3- Clone the repo and enter the project folder:

    git clone https://github.com/FreedomCoop/valuenetwork.git ocp
    cd ocp

4- Activate the virtual environment and upgrade pip:

    source ../py3/bin/activate
    pip install -U pip
    pip install -U setuptools

(If you prefer to nest the ocp folder inside the py3 env folder, adapt activate
command accordingly)

5- Install python dependencies:

    pip install -U -r requirements.txt --trusted-host dist.pinaxproject.com

6- Create npm build system and compile css+js:

    npm install
    npm run compile
    npm run optimize

7- Create any possibly missing migrations (e.g. for 'fobi') and create the sqlite database:

    ./manage.py makemigrations
    ./manage.py migrate

8- Create a superuser for yourself so you can login:

    ./manage.py createsuperuser 
  
  -- Prior to run a test you’ll need chrome/chromium and relative chromedrive version on your system, for that check here:
    
   https://chromedriver.chromium.org/downloads

   Once unzipped copy the binary overriding chromedriver version in the proper directory,
   
   here:

   sudo cp where_downloaded/chromedriver install_directory/py3/lib64/python3.7/site-packages/chromedriver_binary/

   or here:

   sudo  cp where_downloaded/chromedriver /py3/lib/python3.7/site-packages/chromedriver_binary/
   
   
  -- If working on a local development environment, then:
        
    ./manage.py collectstatic    
    
    
9- To check all and run the tests:

    ./manage.py check
    ./manage.py test
    
10- To start a local server for development, the new way is (recompiling statics):

    npm run dev
    
...and the old way (non recompiling), just in case:

    ./manage.py runserver

Check everything is ok in http://127.0.0.1:8000 with web browser.



## Important:

- You'll need to create your own `local_settings.py` file (using the
`local_settings_example.py` as a template) to redefine some `ocp/settings.py`
values (e.g. languages, database, etc) and also to define the main context
agents settings about their custom login domains, css and js, email notification
servers, active services, etc.

- To deal with a multi-language instance, please read carefully the
`docs/translations.md` doc.

- To install also a faircoin wallet for the users to manage their own
faircoin accounts in OCP, please follow [this doc](docs/install_ocp_faircoin.md)

- To deploy ocp in a production server please follow the
instructions [here](docs/install_ocp_debian_apache_ssl.rst)


## Initial Data:

The migrate command runs a script to check for and create some basic units and types (required to run the actually deployed instances).

When log in for the first time, it is recommended create your own EconomicAgent, for that, from the pull-down menu with your username on the upper right corner click on DB Admin, then click on Economic agents, and click again on "add economic agent".
Fill in the form with as much info as you wish, then go to the page left bottom and select your username in the first USER widget before save and exiting. 

All above is required for the first User only. To let other users/agents join through a moderated membership process, you must create a Project and configure the settings. 
To do that just follow these steps:

  - If not created yet, go to 'your projects' page and create a new project, whose coordinator will be your agent.
  - Choose a 'moderated' joining style (or 'shares') and a 'public' visibility to have an external register form for non-logged users.
  - Go to `/fobi` url and create a form with the name of the project. Be aware of the resulting 'slug' by checking the url of the link to view the form (e.g. in the view url `/fobi/view/slug-of-the-project-form`, is the last part: `slug-of-the-project-form`). That slug is not editable afterwards, only when creating/importing a form.
    That slug will be also the main identifier of the project in the local_settings file objects.
  - Define only the custom fields (questions) used in the project. Remember that the main user fields are already requested by OCP during registration process (individual or group type, name and surname, nickname/username, email, phone, address and website), so focus only on the really custom questions for the project context, and follow a few rules described below.
  - Add the DB Store handler in the fobi form 'handlers' tab. 
  - Once the form is ready, set its 'slug' in the project's 'Custom project url slug' field. Verify the project's connection with its form with the links to view
    the form that appears in the project's page. 
  - Check the local_settings objects are properly defined with the project's fobi 'slug' as a key for their options, and the project page shows the custom settings like the css and js rules, the background image behind the logo image, etc.

Below you will find some useful rules on fobi custom fields, related to the active services for a project:

  - To set-up a project with Payment Gateways:
    - the selector fobi field must be internally named `payment_mode`.
    - The select options of that field should use as keys a short string representing the gateway (e.g. `transfer`, `faircoin`, `btc`, `ccard`, etc).
    - The local_settings PAYMENT_GATEWAYS object for the project should define for every gateway key a proper gateway block definition (see `ocp/local_settings_example.py`).

  - To set up a project with Shares:
    - The numeric fobi field that will store the amount of shares the user wants to get, must be internally named `projectname_shares` (being 'projectname' the
        lowcase version of the project name without spaces).
    - The local_settings PROJECTS_LOGIN object for the project should have the `shares` active in its `services` block.
    - Edit the project details from the project page, and choose 'shares' as the joining style.
    - To create the project Shares use the form that appears in the project page (in the 'Offered Shares' block), once all the above is ready.
    - Once the share is defined (with its value related to any currency) and the payment gateways defined in the local_settings file appear correctly in the projects page (with a green 'ok'), then you should create the exchanges_types related the active payment gateways by clicking the button 'Create Shares Exchange Types'.


  - To set up the Multicurrency system of Bank of the Commons, please bear in mind the following steps::
   - The local_settings MULTICURRENCY object must be defined with the proper API urls and the BotC API secret key given to your instance.
   - The local_settings PROJECTS_LOGIN object for the project should include the `multicurrency` option as an active service.
   - For that project and their members will appear the option to connect with their existent BotC-Wallet account or create a new one from OCP.
   - The connection with BotC-Wallet is still readonly, so to perform any banking action, such as transfer money transfer, it's mandatory to use it from [here] (https://wallet.bankofthecommons.coop).



*Note: the original code fixtures are still broken. In the meantime, you can
get a test database from somebody.*
