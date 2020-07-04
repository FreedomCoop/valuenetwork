from django.contrib.auth.models import User
from django.conf import settings
from django.test import RequestFactory
import decimal

from valuenetwork.valueaccounting.models import \
    AgentType, EconomicAgent, AgentUser, EventType, EconomicResourceType, \
    Unit, AgentResourceRoleType

from work.models import Project, create_unit_types

from fobi.utils import perform_form_entry_import
import json

# It creates the needed initial data to run the work tests:
# admin_user, admin_agent, Freedom Coop agent, FC Membership request agent, ...
def initial_test_data():
    # To see debugging errors in the browser while making changes in the test.
    setattr(settings, 'DEBUG', True)

    # We want to reuse the test db, to be faster (manage.py test --keepdb),
    # so we create the objects only if they are not in test db.
    try:
        admin_user = User.objects.get(username='admin_user')
    except User.DoesNotExist:
        admin_user = User.objects.create_superuser(
            username='admin_user',
            password='admin_passwd',
            email='admin_user@example.com'
        )
        print "t- created User: 'admin_user'"

    # AgentTypes
    individual_at, c = AgentType.objects.get_or_create(
        name='Individual', party_type='individual', is_context=False)
    if c: print "t- created AgentType: 'Individual'"

    project_at, c = AgentType.objects.get_or_create(
        name='Project', party_type='team', is_context=True)
    if c: print "t- created AgentType: 'Project'"

    cooperative_at, c = AgentType.objects.get_or_create(
        name='Cooperative', party_type='organization', is_context=True)
    if c: print "t- created AgentType: 'Cooperative'"

    # EconomicAgent for admin_user related to him/her.
    admin_ea, c = EconomicAgent.objects.get_or_create(name='admin_agent',
        nick='admin_agent', agent_type=individual_at,  is_context=False)
    if c: print "t- created EconomicAgent: 'admin_agent'"

    au, c = AgentUser.objects.get_or_create(agent=admin_ea, user=admin_user)
    if c: print "t- created AgentUser: "+str(au)

    # EconomicAgent for Freedom Coop
    fdc, c = EconomicAgent.objects.get_or_create(name='Freedom Coop',
        nick='Freedom Coop', agent_type=cooperative_at, is_context=True)
    if c: print "t- created EconomicAgent: 'Freedom Coop'"

    # Project for FreedomCoop
    pro, c = Project.objects.get_or_create(agent=fdc, joining_style="shares", fobi_slug='freedom-coop')
    if c: print "t- created Project: "+str(pro)
    pro.visibility = 'public'
    pro.save()

    # Fobi form for project
    json_data = open(settings.BASE_DIR+'/work/tests/freedom-coop.json')
    form_data = json.load(json_data) # deserialises it
    #data2 = json.dumps(data1) # json formatted string

    request = RequestFactory().get(settings.BASE_DIR)
    request.user = admin_user
    form_entry = perform_form_entry_import(request, form_data)
    if form_entry:
        print "t- created fobi FormEntry importing freedom-coop.json: "+str(form_entry)
        #import pdb; pdb.set_trace()

    json_data.close()

    create_unit_types()

    # EconomicAgent for Memebership Request
    #fdcm, c = EconomicAgent.objects.get_or_create(name='FreedomCoop Membership',
    #    nick=settings.SEND_MEMBERSHIP_PAYMENT_TO, agent_type=project_at, is_context=True)
    #if c: print "t- created EconomicAgent: 'FreedomCoop Membership'"

    # EventType for todos
    et, c = EventType.objects.get_or_create(name='Todo', label='todo',
        relationship='todo', related_to='agent', resource_effect='=')
    if c: print "t- created EventType: 'Todo'"

    hr = Unit.objects.get(name='Hours')
    ert, c = EconomicResourceType.objects.get_or_create(name='some_skill_of_Admin', unit=hr, unit_of_use=hr, behavior='work')
    if c: print "t- created EconomicResourceType: "+str(ert)

    # Manage FairCoin
    FC_unit = Unit.objects.get(name='FairCoin') #_or_create(unit_type='value', name='FairCoin', abbrev='fair')
    if FC_unit: print "t- found Unit: 'FairCoin'"

    ert = EconomicResourceType.objects.get(name_en='Faircoin Ocp Account') #, unit=FC_unit, unit_of_use=FC_unit,
        #value_per_unit_of_use=decimal.Decimal('1.00'), substitutable=True, behavior='dig_acct')
    if ert: print "t- found EconomicResourceType: 'Faircoin Ocp Account'"

    arrt, c = AgentResourceRoleType.objects.get_or_create(name_en='Owner', is_owner=True)
    if c: print "t- created AgentResourceRoleType: "+str(arrt)

