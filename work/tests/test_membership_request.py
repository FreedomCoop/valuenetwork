# To run this test you'll need to download phantomjs. See:
# https://gist.github.com/telbiyski/ec56a92d7114b8631c906c18064ce620

from django.test import LiveServerTestCase

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from work.tests import objects_for_work_tests
from django.conf import settings
from captcha.models import CaptchaStore

class MembershipRequestTestCase(LiveServerTestCase):

    # It helps selenium to wait for loading new pages.
    def wait_loading(self, driver, xpath_string):
        try:
            WebDriverWait(driver, 20).until(lambda driver: driver.find_element_by_xpath(xpath_string))
        except TimeoutException as ex:
            print("Exception has been thrown. " + str(ex))
            self.tearDownClass()

    # It helps selenium to wait for js/css changes of element visibility.
    def wait_js(self, driver, xpath_string):
        try:
            WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.XPATH, xpath_string)))
        except TimeoutException as ex:
            print("Exception has been thrown. " + str(ex))
            self.tearDownClass()

    @classmethod
    def setUpClass(cls):
        super(MembershipRequestTestCase, cls).setUpClass()
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('headless')
        chrome_options.add_argument('--lang=EN')
        chrome_options.add_argument('window-size=1920x1080')
        cls.selenium = webdriver.Chrome(chrome_options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(MembershipRequestTestCase, cls).tearDownClass()

    # This is the membership request test.
    def test_membership_request(self):
        print "------- JoinRequest Test 1 (start) -------"
        objects_for_work_tests.initial_test_data()

        theurl = self.live_server_url

        settings.PAYMENT_GATEWAYS['freedom-coop'] = {
            'faircoin': {
                'url':'',
                'html':'Please send the faircoins from your OCP Faircoin Account:',
                'unit':'FAIR'
            }
        }
        settings.PROJECTS_LOGIN['freedom-coop'] = {
            'html':"<p>This is OCP, our Open Collaborative Platform. The OCP is the key organizational tool we offer to individuals, collectives, and project coordinators inside Freedom Coop.</p><p>Therefore, it can be used to:</p><ul><li>Boost open collaborative projects between people in different places.</li><li>Manage open collective projects and their team work by setting up task forces.</li><li>Account the time spent by every member to use it as a base of income distribution and a way of self-actualization for any project.</li><li>Use some legal services that can be covered with a quarterly fee and tax distribution between Freedom Coop members.</li><li>Manage an online Faircoin wallet to accept and make payments.</li></ul><p>Freedom Coop, will use OCP for our collective organization as an open cooperative process.</p>",
            #'background_url':'img/photo-OCP-1600x900_green.jpg',
            'css':'',
            'services': [
                'faircoins',
                #'tasks',
                'skills',
                'projects',
                'exchanges',
                #'processes',
            ],
            'domains': [
                theurl, #'localhost:*' # 50127 43879'
                #'127.0.0.1',
                #'127.0.0.1:8000'
            ],
            'smtp': {
                'host': '',
                'username': '',
                'password': '',
                'port': 587,
                'use_tls': True
            }
        }
        settings.LOGIN_EXEMPT_URLS += [
            r'^freedom-coop/',
            r'^join/freedom-coop/',
        ]


        s = self.selenium
        s.maximize_window()

        # Anonymous user fills the membership request form.
        print "opening url: "+str('%s%s' % (theurl, "/freedom-coop"))
        s.get('%s%s' % (theurl, "/freedom-coop"))
        print 't- 1: '+s.title
        #self.wait_loading(s, '//title[contains(text(), "Freedom Coop")]')
        self.assertIn("Freedom Coop", s.title)
        sel = s.find_element_by_xpath('//select[@name="language"]')
        opts = sel.find_elements_by_tag_name("option")
        for op in opts:
            print "t- select option: " + op.get_attribute("value")
            if op.get_attribute("value") == 'en':
                op.click()
                break
        print 't- 2: '+s.title
        #self.wait_loading(s, '//a[contains(text(), "Join Freedom Coop")]')
        but = s.find_element_by_xpath('//a[contains(text(), "Join Freedom Coop")]')
        but.click()
        print 't- 3: '+s.title
        self.assertIn("Request to Join: Freedom Coop", s.title)
        #print 't- 4: '+s.title

        captcha = CaptchaStore.objects.get(hashkey=CaptchaStore.generate_key())

        s.find_element_by_id("id_name").send_keys("test_name01")
        s.find_element_by_id("id_surname").send_keys("test_surname01")
        s.find_element_by_id("id_requested_username").send_keys("test_user01")
        s.find_element_by_id("id_email_address").send_keys("test_name01@example.com")
        s.find_element_by_id("id_description").send_keys("This is a test user.")
        s.find_element_by_id("id_freedomcoopshares").send_keys("1")
        #s.find_element_by_id("id_captcha_0").send_keys(captcha.hashkey)
        s.execute_script("document.getElementById('id_captcha_0').setAttribute('value', '"+str(captcha.hashkey)+"')");
        s.find_element_by_id("id_captcha_1").send_keys(captcha.response)

        s.find_element_by_xpath('//input[@type="submit"]').click()
        print 't- 5: '+s.title
        #import pdb; pdb.set_trace()
        self.assertIn("Thank you", s.title)
        print "t- JoinRequest form Submitted! "
        print "------- join-request test 1 completed -------"
        print
        # TODO: add freedom-coop project to objects_for_work_test.py
        '''
        # Admin login.
        s.get('%s%s' % (self.live_server_url, "/freedom-coop"))
        self.wait_loading(s, '//title[contains(text(), "OCP: Open Collaborative Platform")]')
        s.find_element_by_id("id_username").send_keys("admin_user")
        s.find_element_by_id("id_password").send_keys("admin_passwd")
        s.find_element_by_xpath('//button[@type="submit"]').click()
        self.wait_loading(s, '//title[contains(text(), "| My Dashboard")]')

        # Admin takes the simple task (accounting/work -> Mine!)
        self.wait_js(s, '//a[contains(text(), "admin_agent")]')
        s.find_element_by_partial_link_text("admin_agent").click()
        self.wait_js(s, '//a[contains(text(), "Coop Admin App")]')
        s.find_element_by_partial_link_text('Coop Admin App').click()
        self.wait_loading(s, '//title[contains(text(), "| My Work")]')
        s.find_element_by_partial_link_text("All Work").click()
        self.wait_loading(s, '//title[contains(text(), "| Work")]')
        self.wait_js(s, '//input[@value="Mine!"]')
        s.find_element_by_xpath('//input[@value="Mine!"]').click()
        self.wait_js(s, '//input[@value="Decline"]')

        # Admin creates agent (click Open -> click Create Agent)
        # (open new tab is a mess, so we go to the "Open" link url)
        s.get('%s%s' % (self.live_server_url, "/accounting/membership-request/1/"))
        self.wait_loading(s, '//title[contains(text(), "| Freedom Coop Membership Request for")]')
        s.find_element_by_partial_link_text("Create New Agent").click()
        self.wait_js(s, '//input[@value="Save"]')
        s.find_element_by_xpath('//input[@value="Save"]').click()
        self.wait_loading(s, '//title[contains(text(), "| Agent:")]')

        # Admin creates user (click Create user -> enter new password)
        s.find_element_by_partial_link_text("Create User").click()
        self.wait_js(s, '//button[contains(text(), "Save user")]')
        s.find_element_by_id("id_password1").send_keys("test_user01password")
        s.find_element_by_id("id_password2").send_keys("test_user01password")
        s.find_element_by_xpath('//button[contains(text(), "Save user")]').click()
        self.wait_js(s, '//td[contains(text(), "test_user01")]')


        # Admin defines associations (click Maintain Associations)
        s.find_element_by_partial_link_text("Maintain Associations").click()
        self.wait_loading(s, '//title[contains(text(), "| Maintain Associations")]')

        # - change "is participant of" -> FC MembershipRequest
        # - change "Active" -> candidate
        '''
