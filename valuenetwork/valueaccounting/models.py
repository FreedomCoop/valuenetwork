import datetime
import time
import re
from decimal import *
from operator import attrgetter
from toposort import toposort, toposort_flatten

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.template.defaultfilters import slugify
import json as simplejson
from django.db.models.functions import Lower
from django.conf import settings
from django.urls import reverse

from faircoin import utils as faircoin_utils
from easy_thumbnails.fields import ThumbnailerImageField

import logging
loger = logging.getLogger("ocp")

"""Models based on REA

These models are based on the Bill McCarthy's Resource-Event-Agent accounting model:
https://www.msu.edu/~mccarth4/
http://en.wikipedia.org/wiki/Resources,_events,_agents_(accounting_model)

REA is also the basis for ISO/IEC FDIS 15944-4 ACCOUNTING AND ECONOMIC ONTOLOGY
http://global.ihs.com/doc_detail.cfm?item_s_key=00495115&item_key_date=920616

"""

FAIRCOIN_DIVISOR = Decimal("100000000.00")

#from work.utils import remove_exponent
def remove_exponent(num):
    if not isinstance(num, float):
      if '.' in str(num):
        return num.to_integral() if num == num.to_integral() else num.normalize()
    return num

def unique_slugify(instance, value, slug_field_name='slug', queryset=None,
                   slug_separator='-'):
    """
    Calculates a unique slug of ``value`` for an instance.

    ``slug_field_name`` should be a string matching the name of the field to
    store the slug in (and the field to check against for uniqueness).

    ``queryset`` usually doesn't need to be explicitly provided - it'll default
    to using the ``.all()`` queryset from the model's default manager.
    """
    slug_field = instance._meta.get_field(slug_field_name)

    slug = getattr(instance, slug_field.attname)
    slug_len = slug_field.max_length

    # Sort out the initial slug. Chop its length down if we need to.
    slug = slugify(value)
    if slug_len:
        slug = slug[:slug_len]
    slug = _slug_strip(slug, slug_separator)
    original_slug = slug

    # Create a queryset, excluding the current instance.
    if not queryset:
        queryset = instance.__class__._default_manager.all()
        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)

    # Find a unique slug. If one matches, at '-2' to the end and try again
    # (then '-3', etc).
    next = 2
    while not slug or queryset.filter(**{slug_field_name: slug}):
        slug = original_slug
        end = '-%s' % next
        if slug_len and len(slug) + len(end) > slug_len:
            slug = slug[:slug_len-len(end)]
            slug = _slug_strip(slug, slug_separator)
        slug = '%s%s' % (slug, end)
        next += 1

    setattr(instance, slug_field.attname, slug)


def _slug_strip(value, separator=None):
    """
    Cleans up a slug by removing slug separator characters that occur at the
    beginning or end of a slug.

    If an alternate separator is used, it will also replace any instances of
    the default '-' separator with the new separator.
    """
    if separator == '-' or not separator:
        re_sep = '-'
    else:
        re_sep = '(?:-|%s)' % re.escape(separator)
        value = re.sub('%s+' % re_sep, separator, value)
    return re.sub(r'^%s+|%s+$' % (re_sep, re_sep), '', value)

def collect_trash(commitment, trash):
    # this method works for output commitments
    # collect_lower_trash works for inputs
    order_item = commitment.order_item
    process = commitment.process
    if process:
        if process in trash:
            return trash
        trash.append(process)
        for inp in process.incoming_commitments():
            pcs = inp.associated_producing_commitments()
            if pcs:
                for pc in pcs:
                    if pc.order_item == order_item:
                        collect_trash(pc, trash)
    return trash

def collect_lower_trash(commitment, trash):
    # this method works for input commitments
    # collect_trash works for outputs
    order_item = commitment.order_item
    pcs = commitment.associated_producing_commitments()
    if pcs:
        for pc in pcs:
            if pc.order_item == order_item:
                collect_trash(pc, trash)
    return trash

#class Stage(models.Model):
#    name = models.CharField(_('name'), max_length=32)
#    sequence = models.IntegerField(_('sequence'), default=0)


#    class Meta:
#        ordering = ('sequence',)

#    def __str__(self):
#        return self.name


class HomePageLayout(models.Model):
    banner = models.TextField(_('banner'), blank=True, null=True,
        help_text=_("HTML text for top Banner"))
    use_work_panel = models.BooleanField(_('use work panel'), default=False,
        help_text=_("Work panel, if used, will be Panel 1"))
    work_panel_headline = models.TextField(_('work panel headline'), blank=True, null=True)
    use_needs_panel = models.BooleanField(_('use needs panel'), default=False,
        help_text=_("Needs panel, if used, will be Panel 2"))
    needs_panel_headline = models.TextField(_('needs panel headline'), blank=True, null=True)
    use_creations_panel = models.BooleanField(_('use creations panel'), default=False,
        help_text=_("Creations panel, if used, will be Panel 3"))
    creations_panel_headline = models.TextField(_('creations panel headline'), blank=True, null=True)
    panel_1 = models.TextField(_('panel 1'), blank=True, null=True,
        help_text=_("HTML text for Panel 1"))
    panel_2 = models.TextField(_('panel 2'), blank=True, null=True,
        help_text=_("HTML text for Panel 2"))
    panel_3 = models.TextField(_('panel 3'), blank=True, null=True,
        help_text=_("HTML text for Panel 3"))
    footer = models.TextField(_('footer'), blank=True, null=True)

    class Meta:
        verbose_name_plural = _('home page layout')


#for help text
PAGE_CHOICES = (
    ('agent', _('Agent')),
    ('agents', _('All Agents')),
    ('all_work', _('All Work')),
    ('create_distribution', _('Create Distribution')),
    ('create_exchange', _('Create Exchange')),
    ('create_sale', _('Create Sale')),
    ('demand', _('Demand')),
    ('ed_asmbly_recipe', _('Edit Assembly Recipes')),
    ('ed_wf_recipe', _('Edit Workflow Recipes')),
    ('exchange', _('Exchange')),
    ('home', _('Home')),
    ('inventory', _('Inventory')),
    ('labnotes', _('Labnotes Form')),
    ('locations', _('Locations')),
    ('associations', _('Maintain Associations')),
    ('my_work', _('My Work')),
    ('non_production', _('Non-production time logging')),
    ('projects', _('Organization')),
    ("plan_from_recipe", _('Plan from recipe')),
    ("plan_from_rt", _('Plan from Resource Type')),
    ("plan_fr_rt_rcpe", _('Plan from Resource Type Recipe')),
    ('process', _('Process')),
    ('process_select', _('Process Selections')),
    ('recipes', _('Recipes')),
    ('resource_types', _('Resource Types')),
    ('resource_type', _('Resource Type')),
    ('supply', _('Supply')),
    ('non_proc_log', _('Non-process Logging (Work)')),
    ('proc_log', _('Process Logging (Work)')),
    ('profile', _('My Profile (Work)')),
    ('my_history', _('My History (Work)')),
    ('work_map', _('Map (Work)')),
    ('work_home', _('Home (Work)')),
    ('process_work', _('Process (Work)')),
    ('work_timer', _('Work Now (Work)')),
)

class Help(models.Model):
    page = models.CharField(_('page'), max_length=16, choices=PAGE_CHOICES, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)

    class Meta:
        verbose_name_plural = _('help')
        ordering = ('page',)

    def __str__(self):
        return self.get_page_display()


GENERAL_CLASS_CHOICES = (
    ('Material_Type', _('Material_Type')),
    ('Nonmaterial_Type', _('Nonmaterial_Type')),
)

class Facet(models.Model):
    name = models.CharField(_('name'), max_length=32, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)

    clas = models.CharField(_('clas'),
        max_length=20,
        blank=True, null=True,
        #choices=GENERAL_CLASS_CHOICES
    )

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def value_list(self):
        return ", ".join([fv.value for fv in self.values.all()])


class FacetValue(models.Model):
    facet = models.ForeignKey(Facet,
        verbose_name=_('facet'), related_name='values', on_delete=models.CASCADE)
    value = models.CharField(_('value'), max_length=32)
    description = models.TextField(_('description'), blank=True, null=True)

    class Meta:
        unique_together = ('facet', 'value')
        ordering = ('facet', 'value')

    def __str__(self):
        return ": ".join([self.facet.name, self.value])


UNIT_TYPE_CHOICES = (
    ('area', _('area')),
    ('length', _('length')),
    ('quantity', _('quantity')),
    ('time', _('time')),
    ('value', _('value')),
    ('volume', _('volume')),
    ('weight', _('weight')),
    ('ip', _('ip')),
    ('percent', _('percent')),
)

class Unit(models.Model):
    unit_type = models.CharField(_('unit type'), max_length=12, choices=UNIT_TYPE_CHOICES)
    abbrev = models.CharField(_('abbreviation'), max_length=8)
    name = models.CharField(_('name'), max_length=64)
    symbol = models.CharField(_('symbol'), max_length=1, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def is_currency(self):
        if hasattr(self, 'gen_unit') and self.gen_unit:
            ut = self.gen_unit.unit_type
            ancs = ut.get_ancestors()
            for an in ancs:
                if an.clas == 'currency':
                    return True
        if self.unit_type == 'value':
            return True
        return False


#todo: rethink?
ACTIVITY_CHOICES = (
    ('active', _('active contributor')),
    ('affiliate', _('close affiliate')),
    ('inactive', _('inactive contributor')),
    ('passive', _('passive agent')),
    ('external', _('external agent')),
)

SIZE_CHOICES = (
    ('individual', _('individual')),
    ('org', _('organization')),
    ('network', _('network')),
    ('team', _('project')),
    ('community', _('community')),
    ('company', _('company')), # bumbum fast hack (all this types can be handled flexible via general app)
)


class Location(models.Model):
    name = models.CharField(_('name'), max_length=128, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(default=0.0, blank=True, null=True)
    longitude = models.FloatField(default=0.0, blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property #ValueFlows
    def note(self):
        return self.description

    def resources(self):
        return self.resources_at_location.all()

    def agents(self):
        return self.agents_at_location.all()


class AgentTypeManager(models.Manager):

    #note the following context agent methods are not valid, context agent flag is on agent now
    def context_agent_types(self):
        return AgentType.objects.filter(is_context=True)

    def context_types_string(self):
        return " or ".join([ at.name for at in self.context_agent_types()])

    def non_context_agent_types(self):
        return AgentType.objects.filter(is_context=False)

    def individual_type(self):
        at = AgentType.objects.filter(party_type="individual")
        if at:
            return at[0]
        else:
            return None


class AgentType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    parent = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('parent'), related_name='sub_agents', editable=False)
    party_type = models.CharField(_('party type'),
        max_length=12, choices=SIZE_CHOICES,
        default='individual')
    description = models.TextField(_('description'), blank=True, null=True)
    is_context = models.BooleanField(_('is context'), default=False)
    objects = AgentTypeManager()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, name, party_type, is_context, verbosity=2):
        """
        Creates a new AgentType, updates an existing one, or does nothing.
        This is intended to be used as a post_syncdb manangement step.
        """
        try:
            agent_type = cls._default_manager.get(name=name)
            updated = False
            if party_type != agent_type.party_type:
                agent_type.party_type = party_type
                updated = True
            if is_context != agent_type.is_context:
                agent_type.is_context = is_context
                updated = True
            if updated:
                agent_type.save()
                if verbosity > 1:
                    print("- Updated {} AgentType".format(name))
        except cls.DoesNotExist:
            cls(name=name, party_type=party_type, is_context=is_context).save()
            if verbosity > 1:
                print("- Created {} AgentType".format(name))

    @property #ValueFlows
    def note(self):
        return self.description


class AgentAccount(object):
    def __init__(self, agent, event_type, count, quantity, events):
        self.agent = agent
        self.event_type = event_type
        self.count = count
        self.quantity = quantity
        self.events=events

    def example(self):
        return self.events[0]


class AgentManager(models.Manager):

    def without_user(self):
        return self.filter(users__isnull=True)

    def individuals_without_user(self):
        return self.individuals().filter(users__isnull=True)

    def with_user(self):
        return self.exclude(users__isnull=True)

    def without_membership_request(self):
        return self.filter(membership_requests__isnull=True).order_by("name")

    def without_join_request(self, project=None):
        if project:
            ids = list(set([ag.id for ag in project.agent.managers()]))
            if not project.agent.id in ids:
                ids.append(project.agent.id)
            return self.all().exclude(project_join_requests__isnull=False, project_join_requests__project__isnull=False, project_join_requests__project=project).exclude(id__in=ids).order_by('name')
        return self.filter(project_join_requests__isnull=True).order_by("name")

    def projects(self):
        return EconomicAgent.objects.filter(agent_type__party_type="team")

    def individuals(self):
        return EconomicAgent.objects.filter(agent_type__party_type="individual")

    def organizations(self):
        return EconomicAgent.objects.filter(agent_type__party_type="org")

    def networks(self):
        return EconomicAgent.objects.filter(agent_type__party_type="network")

    #def projects_and_networks(self):
    #    return EconomicAgent.objects.filter(Q(agent_type__party_type="network") | Q(agent_type__party_type="team"))

    def context_agents(self):
        return EconomicAgent.objects.filter(is_context=True)

    def non_context_agents(self):
        return EconomicAgent.objects.filter(is_context=False)

    def resource_role_agents(self):
        #return EconomicAgent.objects.filter(Q(is_context=True)|Q(agent_type__party_type="individual"))
        #todo: should there be some limits?  Ran into condition where we needed an organization, therefore change to below.
        return EconomicAgent.objects.all()

    def freedom_coop(self):
        try:
            fc = EconomicAgent.objects.get(name_en="Freedom Coop")
        except EconomicAgent.DoesNotExist:
            raise ValidationError("Freedom Coop does not exist by that name")
        return fc

    def freedom_coop_projects(self):
        try:
            fc = EconomicAgent.objects.get(nick_en="FC_Projects")
        except EconomicAgent.DoesNotExist:
            raise ValidationError("FreedomCoop Projects group does not exist by 'FC_Projects' nickname.")
        return fc

    def root_ocp_agent(self):
        try:
            ocp = EconomicAgent.objects.get(nick_en="OCP")
        except EconomicAgent.DoesNotExist:
            raise ValidationError("OCP main root Agent does not exist by 'OCP' nickname.")
        return ocp

    def open_projects(self):
        return EconomicAgent.objects.filter(project__visibility="public") #is_public="True")



class EconomicAgent(models.Model):
    name = models.CharField(_('name'), max_length=255)
    nick = models.CharField(_('nick'), max_length=32, unique=True,
        help_text=_("Must be unique, and no more than 32 characters"))
    url = models.CharField(_('url'), max_length=255, blank=True)
    agent_type = models.ForeignKey(AgentType,
        verbose_name=_('agent type'), related_name='agents', on_delete=models.CASCADE)
    description = models.TextField(_('description'), blank=True, null=True)
    address = models.CharField(_('address'), max_length=255, blank=True)
    email = models.EmailField(_('email address'), max_length=96, blank=True, null=True)
    phone_primary = models.CharField(_('primary phone'), max_length=32, blank=True, null=True)
    phone_secondary = models.CharField(_('secondary phone'), max_length=32, blank=True, null=True)
    latitude = models.FloatField(_('latitude'), default=0.0, blank=True, null=True)
    longitude = models.FloatField(_('longitude'), default=0.0, blank=True, null=True)
    primary_location = models.ForeignKey(Location,
        verbose_name=_('current location'), related_name='agents_at_location',
        blank=True, null=True,
        on_delete=models.SET_NULL)
    reputation = models.DecimalField(_('reputation'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    photo = ThumbnailerImageField(_("photo"),
        upload_to='photos', blank=True, null=True)
    photo_url = models.CharField(_('photo url'), max_length=255, blank=True)
    unit_of_claim_value = models.ForeignKey(Unit, blank=True, null=True,
        verbose_name=_('unit used in claims'), related_name="agents",
        help_text=_('For a context agent, the unit of all claims'), on_delete=models.SET_NULL)
    is_context = models.BooleanField(_('is context'), default=False)
    slug = models.SlugField(_("Page name"), editable=False)
    created_date = models.DateField(_('created date'), default=datetime.date.today)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='agents_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='agents_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    objects = AgentManager()

    class Meta:
        ordering = ('nick',)

    def __str__(self):
        return self.nick

    def save(self, *args, **kwargs):
        unique_slugify(self, self.nick)
        super(EconomicAgent, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        aus = self.users.all()
        if aus:
            for au in aus:
                user = au.user
                user.delete()
                au.delete()
        super(EconomicAgent, self).delete(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('agent', kwargs={'agent_id': str(self.id),})

    @property #ValueFlows
    def image(self):
        if self.photo_url:
            return self.photo_url
        elif self.photo:
            from valuenetwork.valueaccounting.utils import get_url_starter
            return get_url_starter() + self.photo.url
        else:
            return ""

    @property #ValueFlows
    def note(self):
        return self.description

    @property #ValueFlows
    def primary_phone(self):
        return self.phone_primary

    @property #ValueFlows
    def type(self):
        tp = self.agent_type.name
        if tp == "Individual":
            tp = "Person"
        return tp

    # basic authorization in one place for use by the api(s) initially
    def is_authorized(self, object_to_mutate=None, context_agent_id=None):
        user = self.my_user()
        if not user:
            return False
        if self.is_superuser():
            return True
        if context_agent_id:
            context_agent = EconomicAgent.objects.get(pk=context_agent_id)
        elif object_to_mutate:
            if type(object_to_mutate) is Order: #orders do not have a context agent if not created from recipe
                if object_to_mutate.pk: #update or delete
                    if object_to_mutate.created_by == user:
                        return True
                    else:
                        return False
                else: #create not from recipe
                    return True
            elif type(object_to_mutate) is EconomicResource:
                #arr = object_to_mutate. #TODO: add auth for resource (what?)
                return True
            elif type(object_to_mutate) is AgentAssociation:
                #TODO: probably needs more definition, possibly including joining options; maybe a separate method....
                if object_to_mutate.is_associate == self:
                    return True
                if object_to_mutate.has_associate == self:
                    return True
                if object_to_mutate.is_associate.is_context:
                    context_agent = object_to_mutate.is_associate
                elif object_to_mutate.has_associate.is_context:
                    context_agent = object_to_mutate.has_associate
            elif type(object_to_mutate) is EconomicAgent:
                if object_to_mutate == self:
                    return True
                elif object_to_mutate.is_context == True:
                    if self.is_manager_of(object_to_mutate): #TODO: need actual generic requirement
                        return True
                    else:
                        return False
                else:
                    return False
            elif type(object_to_mutate) is AgentResourceType:
                if self == object_to_mutate.agent:
                    return True
                else:
                    return False
            else:
                context_agent = object_to_mutate.context_agent
        else:
            return False
        if context_agent not in self.is_member_of():
            return False
        if object_to_mutate:
            if object_to_mutate.pk: #update or delete
                if type(object_to_mutate) is EconomicEvent:
                    if object_to_mutate.created_by == user:
                        return True
                    else:
                        return False
                else:
                    return True
            else: #create
                return True
        else: #create check ahead
            return True

    def recipes(self):
        resource_types = []
        candidate_resource_types = self.get_resource_types_with_recipe()
        for rt in candidate_resource_types:
            if rt.recipe_needs_starting_resource():
                rt.onhand_resources = []
                onhand = rt.onhand_for_resource_driven_recipe()
                if onhand:
                    resource_types.append(rt)
                    for oh in onhand:
                        rt.onhand_resources.append(oh)
            else:
                    resource_types.append(rt)
        return resource_types

    def notification_settings(self):
        from pinax.notifications.models import NoticeSetting
        user = self.my_user()
        return NoticeSetting.objects.filter(user=user)

    def membership_request(self):
        reqs = self.membership_requests.all()
        if reqs:
            return reqs[0]
        else:
            return None

    def membership_request_id(self):
        req = self.membership_request()
        if req:
            return req.id
        else:
            return None

    """def joinaproject_request(self): # TODO deprecate this function around (only first request!)
        reqs = self.project_join_requests.all()
        if reqs:
            return reqs[0]
        else:
            return None

    def joinaproject_request_id(self): # TODO deprecate this function around (only first request!)
        reqs = self.project_join_requests.all()
        if reqs:
            return reqs[0].id
        else:
            return None
    """

    def joinaproject_requests(self):
        reqs = self.project_join_requests.all()
        if reqs:
            return reqs
        else:
            return None

    def joinaproject_requests_projects(self):
        reqs = self.project_join_requests.all()
        projects = []
        if reqs:
          for req in reqs:
            projects.append(req.project)
          return projects
        else:
            return None

    def request_faircoin_address(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        address = self.faircoin_address()
        if not address:
            address = "address_requested"
            resource = self.create_faircoin_resource(address)
        return address

    def create_fake_faircoin_address(self):
        address = self.faircoin_address()
        if not address:
            address = str(time.time())
            resource = self.create_faircoin_resource(address)
            print("created fake faircoin address")
        return address

    def create_faircoin_resource(self, address):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        from valuenetwork.valueaccounting.service import ExchangeService
        service = ExchangeService.get()
        resource = service.create_faircoin_resource(self, address)
        return resource

    def faircoin_address(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        fcr = self.faircoin_resource()
        if fcr:
            return fcr.faircoin_address.address
        else:
            return None

    def faircoin_resource(self):
        candidates = self.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type__behavior="dig_acct",
            resource__faircoin_address__address__isnull=False)
        if candidates:
            if len(candidates) > 1:
                for can in candidates:
                    if can.resource.faircoin_address.is_mine():
                        return can.resource
            else:
                return candidates[0].resource
        else:
            return None

    def faircoin_resources(self):
        candidates = self.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type__behavior="dig_acct",
            resource__faircoin_address__address__isnull=False)
        if candidates:
            return [can.resource for can in candidates]
        else:
            return []


    def candidate_membership(self, project_agent=None):
        aa = self.candidate_association(project_agent)
        if aa:
            if aa.state == "potential":
                return aa.has_associate
        return None

    def candidate_association(self, project_agent=None):
        aas = self.is_associate_of.all()
        if not project_agent:
            raise ValidationError("Bad use, missing project agent! "+str(self))
        if aas:
            for aa in aas:
                #import pdb; pdb.set_trace() #aa = aas[0]
                if project_agent and aa.has_associate == project_agent:
                    if aa.state == "potential":
                        return aa
        return None

    def number_of_shares(self):
        if self.agent_type.party_type == "individual":
            shares = 1
        else:
            shares = 2
        req = self.membership_request()
        if req:
            req_shares = req.number_of_shares
            shares = req_shares if req_shares>shares else shares
        return shares

    def owns(self, resource):
        if self in resource.owners():
            return True
        else:
            return False

    def owns_resource_of_type(self, resource_type):
        answer = False
        arrs = self.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type=resource_type)
        if arrs:
            answer = True
        return answer

    def owned_resource_of_type(self, resource_type):
        answer = None
        arrs = self.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type=resource_type)
        if arrs:
            if len(arrs) > 1:
                loger.warning(str(self)+" has more than one owned_resource_of_type "+str(resource_type))
            answer = arrs[0].resource
        return answer

    def my_user(self):
        users = self.users.all()
        if users:
            if len(users) > 1:
                loger.error("The agent has more than one user? ag:"+str(self.id)+" users:"+str(users))
                raise ValidationError("The agent has more than one user? ag:"+str(self.id)+" users:"+str(users))
            return users[0].user
        return None

    def is_superuser(self):
        if self.my_user():
            return self.my_user().is_superuser
        return False

    def is_staff(self):
        if self.my_user():
            return self.my_user().is_staff
        return False

    def is_coop_worker(self):
        if not self.is_superuser() and not self.is_staff():
            return True
        return False

    def is_active_freedom_coop_member(self):
        fc = EconomicAgent.objects.freedom_coop()
        fcaas = self.is_associate_of.filter(
            association_type__association_behavior="member",
            has_associate=fc,
            state="active")
        if fcaas:
            return True
        else:
            return False

    def is_participant(self):
        fcaas = self.is_associate_of.filter(
                association_type__association_behavior="member",
                #has_associate=req.project.agent,
                state="active")

        #if not self.is_active_freedom_coop_member() and self.joinaproject_requests():
        #  reqs = self.joinaproject_requests()
        #  if reqs:
        #    for req in reqs:
        #      aas = self.is_associate_of.filter(
        #        association_type__association_behavior="member",
        #        has_associate=req.project.agent,
        #        state="active")
        #      if aas:
        #        break
        #        return True
        if fcaas:
            return True
        else:
            return False

    def is_participant_candidate(self):
        fcaas = None
        if not self.is_active_freedom_coop_member() and self.joinaproject_requests():
          reqs = self.joinaproject_requests()
          if reqs:
            for req in reqs:
              fcaas = self.is_associate_of.filter(
                association_type__association_behavior="member",
                has_associate=req.project.agent,
                state="potential")
        if fcaas and not self.is_participant():
            return True
        else:
            return False

    def seniority(self):
        return (datetime.date.today() - self.created_date).days

    def node_id(self):
        if self.agent_type.party_type == "team":
            return "-".join(["Project", str(self.id)])
        else:
            return "-".join(["Agent", str(self.id)])

    def color(self): #todo: not tested
        if self.agent_type.party_type == "team":
            return "blue"
        else:
            return "green"

    def produced_resource_type_relationships(self):
        return self.resource_types.filter(event_type__relationship='out')

    def produced_resource_types(self):
        return [ptrt.resource_type for ptrt in self.produced_resource_type_relationships()]

    def consumed_and_used_resource_type_relationships(self):
        return self.resource_types.filter(
            Q(event_type__relationship='consume')|Q(event_type__relationship='use'))

    def consumed_and_used_resource_types(self):
        return [ptrt.resource_type for ptrt in self.consumed_and_used_resource_type_relationships()]

    def orders(self):
        ps = self.processes.all()
        oset = {p.independent_demand() for p in ps if p.independent_demand()}
        return list(oset)

    def planned_orders(self):
        return [o for o in self.orders() if o.kanban_state() == "planned"]

    def doing_orders(self):
        return [o for o in self.orders() if o.kanban_state() == "doing"]

    def finished_orders(self):
        return [o for o in self.orders() if o.kanban_state() == "done"]

    def active_orders(self):
        return [o for o in self.orders() if o.has_open_processes()]

    def xbill_parents(self):
        return self.produced_resource_type_relationships()

    def xbill_children(self):
        return []

    def xbill_class(self):
        return "economic-agent"

    def score(self):
        return sum(art.score for art in self.resource_types.all())

    def skills(self):
        arts = self.resource_types.all()
        rts = []
        for art in arts:
            if art.resource_type not in rts:
                rts.append(art.resource_type)
        return rts

    def skill_relationships(self):
        return self.resource_types.all()

    def contributions(self):
        return self.given_events.filter(is_contribution=True)

    def involved_in_events(self):
        return EconomicEvent.objects.filter(Q(from_agent=self)|Q(to_agent=self)|Q(context_agent=self))

    def involved_in_commitments(self):
        return Commitment.objects.filter(Q(from_agent=self)|Q(to_agent=self)|Q(context_agent=self))

    def active_commitments(self):
        return [p for p in self.involved_in_commitments() if p.finished==False]

    def finished_commitments(self):
        return [p for p in self.involved_in_commitments() if p.finished==True]

    def agent_commitments(self, finished=None, also_search_children=False, sort_desc=False):
        if also_search_children:
            agents = self.with_all_sub_agents() #includes self
        else:
            agents = []
            agents.append(self)
        commits = []
        for agent in agents:
            if finished==True:
                commits.extend(list(agent.finished_commitments()))
            elif finished==False:
                commits.extend(list(agent.active_commitments()))
            else:
                commits.extend(list(agent.involved_in_commitments()))
        if sort_desc:
            commits.sort(key=lambda x: x.due_date, reverse=True)
        return commits

    # primitive search
    def search_commitments(self, search_string, finished=None, also_search_children=False, sort_desc=False):
        commits = self.agent_commitments(finished, also_search_children, sort_desc)
        answer = []
        strings = search_string.lower().split(" ")
        for com in commits:
            for string in strings:
                if com.description:
                    if string in com.description.lower():
                        answer.append(com)
                        break
        return answer

    def user(self):
        users = self.users.filter(user__is_active=True)
        if users:
            return users[0]
        else:
            return None

    def username(self):
        agent_user = self.user()
        if agent_user:
            return agent_user.user.username
        else:
            return ""

    def worked_processes(self):
        cts = self.given_commitments.all()
        events = self.given_events.all()
        processes = [x.process for x in cts if x.process]
        processes.extend([x.process for x in events if x.process])
        return list(set(processes))

    def active_worked_processes(self):
        aps = [p for p in self.worked_processes() if p.finished==False]
        return aps

    def finished_worked_processes(self):
        aps = [p for p in self.worked_processes() if p.finished==True]
        return aps

    def context_processes(self):
        return self.processes.all()

    def active_context_processes(self):
        return self.context_processes().filter(finished=False)

    def finished_context_processes(self):
        return self.context_processes().filter(finished=True)

    def is_individual(self):
        return self.agent_type.party_type == "individual"

    def active_processes(self):
        if self.is_individual():
            return self.active_worked_processes()
        else:
            return self.active_context_processes()

    def finished_processes(self):
        if self.is_individual():
            return self.finished_worked_processes()
        else:
            return self.finished_context_processes()

    def all_processes(self):
        if self.is_individual():
            return self.worked_processes()
        else:
            return self.context_processes()

    # primitive search
    def search_processes(self, search_string, finished=None, also_search_children=True):
        if also_search_children:
            agents = self.with_all_sub_agents() #includes self
        else: #not tested
            agents = []
            agents.append(self)
        procs = []
        for agent in agents:
            if finished==True:
                procs.extend(list(agent.finished_processes()))
            elif finished==False:
                procs.extend(list(agent.active_processes()))
            else:
                procs.extend(list(agent.all_processes()))
        answer = []
        strings = search_string.lower().split(" ")
        for proc in procs:
            for string in strings:
                if string in proc.name.lower():
                    answer.append(proc)
                elif string in proc.notes.lower():
                    answer.append(proc)
        return list(set(answer))

    def all_plans(self):
        procs = self.all_processes()
        plans = []
        for proc in procs:
            if proc.independent_demand():
                if proc.independent_demand() not in plans:
                    plans.append(proc.independent_demand())
            elif proc.plan:
                if proc.plan not in plans:
                    plans.append(proc.plan)
        plans.sort(key=lambda x: x.due_date)
        return plans

    def finished_plans(self):
        plans = self.all_plans()
        closed_plans = []
        for plan in plans:
            if not plan.has_open_processes():
                closed_plans.append(plan)
        return closed_plans

    def unfinished_plans(self):
        plans = self.all_plans()
        open_plans = []
        for plan in plans:
            if plan.has_open_processes():
                open_plans.append(plan)
        return open_plans

    # primitive search
    def search_plans(self, search_string, finished=None, also_search_children=True):
        if also_search_children:
            agents = self.with_all_sub_agents() #includes self
        else: #not tested
            agents = []
            agents.append(self)
        plans = []
        for agent in agents:
            if finished==True:
                plans.extend(list(agent.finished_plans()))
            elif finished==False:
                plans.extend(list(agent.unfinished_plans()))
            else:
                plans.extend(list(agent.all_plans()))
        answer = []
        strings = search_string.lower().split(" ")
        for plan in plans:
            for string in strings:
                if plan.name:
                    if string in plan.name.lower():
                        answer.append(plan)
                if plan.description:
                    if string in plan.description.lower():
                        answer.append(plan)
        return list(set(answer))

    def resources_created(self):
        creations = []
        for p in self.all_processes():
            creations.extend(p.deliverables())
        return list(set(creations))

    def resource_relationships(self):
        return self.agent_resource_roles.all()

    #from here these were copied from project - todo: fix these to work correctly using context agent relationships (these are in various stages of fix and test)
    def time_contributions(self):
        return sum(event.quantity for event in self.events.filter(
            is_contribution=True,
            event_type__relationship="work"))

    def context_contributions(self):
        return sum(event.quantity for event in self.events.filter(
            is_contribution=True))

    def contributions_count(self):
        if self.is_individual():
            return self.contributions().count()
        else:
            return self.contribution_events().count()

    def contribution_events(self):
        return self.events.filter(is_contribution=True)

    def contributors(self):
        ids = self.events.filter(is_contribution=True).values_list('from_agent').order_by('from_agent').distinct()
        id_list = [id[0] for id in ids]
        return EconomicAgent.objects.filter(id__in=id_list)

    def total_financial_contributions(self):
        #this is wrong
        events = self.events.filter(
            Q(event_type__name='Cash Contribution')|
            Q(event_type__name='Purchase Contribution')|
            Q(event_type__name='Expense Contribution')
            )
        return sum(event.quantity for event in events)

    def total_financial_income(self):
        #this is really wrong
        events = self.events.filter(
            Q(event_type__name='Cash Contribution')|
            Q(event_type__name='Purchase Contribution')|
            Q(event_type__name='Expense Contribution')
            )
        return sum(event.quantity for event in events)

    def all_events(self):
        return EconomicEvent.objects.filter(
            Q(from_agent=self)|Q(to_agent=self))

    def events_by_event_type(self):
        agent_events = EconomicEvent.objects.filter(
            Q(from_agent=self)|Q(to_agent=self))
        ets = EventType.objects.all()
        answer = []
        for et in ets:
            events = agent_events.filter(event_type=et)
            if events:
                count = events.count()
                quantity = sum(e.quantity for e in events)
                aa = AgentAccount(self, et, count, quantity, events)
                answer.append(aa)
        return answer

    def distributions_count(self):
        return Distribution.objects.filter(context_agent=self).count()

    def demand_exchange_count(self):
        return Exchange.objects.demand_exchanges().filter(context_agent=self).count()

    def supply_exchange_count(self):
        return Exchange.objects.supply_exchanges().filter(context_agent=self).count()

    def internal_exchange_count(self):
        return Exchange.objects.internal_exchanges().filter(context_agent=self).count()

    def with_all_sub_agents(self):
        from valuenetwork.valueaccounting.utils import flattened_children_by_association
        aas = AgentAssociation.objects.filter(association_type__association_behavior="child").order_by("is_associate__name")
        return flattened_children_by_association(self, aas, [])

    def with_all_associations(self):
        from valuenetwork.valueaccounting.utils import group_dfs_by_has_associate, group_dfs_by_is_associate
        if self.is_individual():
            agents = [self,]
            agents.extend([ag.has_associate for ag in self.is_associate_of.all()])
            agents.extend([ag.is_associate for ag in self.has_associates.all()])
        else:
            associations = AgentAssociation.objects.all().order_by("-association_type")
            #associations = associations.exclude(is_associate__agent_type__party_type="individual")
            #associations = associations.exclude(association_type__identifier="supplier")
            gas = group_dfs_by_has_associate(self, self, associations, [], 1)
            gas.extend(group_dfs_by_is_associate(self, self, associations, [], 1))
            agents = [self,]
            for ga in gas:
                if ga not in agents:
                    agents.append(ga)
        return agents

    def related_contexts(self):
        agents = [ag.has_associate for ag in self.is_associate_of.all()]
        agents.extend([ag.is_associate for ag in self.has_associates.all()])
        if self.is_context and not self in agents:
          agents.extend([self])
        #cas = [a for a in agents if a.is_context]
        #return list(set(cas))
        return [a for a in agents if a.is_context]

    def related_all_contexts(self, childs=True):
        agents = [ag.has_associate for ag in self.is_associate_of.all()]
        # bumbum get also parents of parents contexts
        grand_parents = []
        for agn in agents:
          grand_parents.extend([ag.has_associate for ag in agn.is_associate_of.all()])
        agents.extend(grand_parents)
        if childs:
          agents.extend([ag.is_associate for ag in self.has_associates.all()])
        if self.is_context and not self in agents:
          agents.extend([self])
        return list(set([a for a in agents if a.is_context]))

    def related_all_agents(self, childs=True):
        agents = [ag.has_associate for ag in self.is_associate_of.all()]
        # get also parents of parents contexts
        grand_parents = []
        mates = []
        for agn in agents:
            grand_parents.extend([ag.has_associate for ag in agn.is_associate_of.all()])
            if self.is_individual():
                mates.extend([ag.is_associate for ag in agn.has_associates.all()])
        agents.extend(grand_parents)
        if childs:
          agents.extend([ag.is_associate for ag in self.has_associates.all()])
        if self.is_individual():
            agents.extend(mates)
        if self.is_context and not self in agents:
          agents.extend([self])
        grandgrand_parents = [] # get grandparents of parents. TODO: recursive parents until root
        for agn in grand_parents:
          grandgrand_parents.extend([ag.has_associate for ag in agn.is_associate_of.all()])
        agents.extend(grandgrand_parents)
        ocp = EconomicAgent.objects.root_ocp_agent()
        if not ocp in agents:
            agents.extend([ocp])
        return list(set(agents))

    def related_contexts_queryset(self):
        ctx_ids = [ctx.id for ctx in self.related_contexts()]
        return EconomicAgent.objects.filter(id__in=ctx_ids)

    #def related_agents_queryset(self):
    #    ctx_ids = [ctx.id for ctx in self.related_contexts()]
    #    return EconomicAgent.objects.filter(id__in=ctx_ids, is_context=True)

    def related_all_contexts_queryset(self, agent=None, childs=True):
        ctx_ids = [ctx.id for ctx in self.related_all_contexts(childs)]
        if agent and not agent.id in ctx_ids:
          ctx_ids.append(agent.id)
        return EconomicAgent.objects.filter(id__in=ctx_ids)

    def related_all_agents_queryset(self, agent=None, childs=True):
        ctx_ids = [ctx.id for ctx in self.related_all_agents(childs)]
        if agent and not agent.id in ctx_ids:
          ctx_ids.append(agent.id)
        return EconomicAgent.objects.filter(id__in=ctx_ids)

    def need_skills(self):
        resp = True
        ags = self.related_contexts()
        add = 0
        if self.is_context and self in ags:
            if len(ags) > 1:
                add = 1
            #ags.append(self)
        noneed = []
        for ag in ags:
            try:
                if ag.project and ag.project.services():
                    if not 'skills' in ag.project.services():
                        noneed.append(ag)
            except:
                pass
        if len(ags)-add == len(noneed):
            resp = False
        if self in noneed:
            resp = False
        #import pdb; pdb.set_trace()
        if not self.is_participant():
            resp = False
        return resp

    def need_faircoins(self):
        resp = True
        ags = self.related_contexts()
        add = 0
        if self.is_context and self in ags:
            if len(ags) > 1:
                add = 1
            #ags.append(self)
        noneed = []
        for ag in ags:
            try:
                if ag.project and ag.project.services():
                    if not 'faircoins' in ag.project.services():
                        noneed.append(ag)
                else:
                    noneed.append(ag)
            except:
                pass
        if len(ags)-add == len(noneed):
            resp = False
        if self in noneed:
            resp = False
        #import pdb; pdb.set_trace()
        return resp

    def need_exchanges(self):
        resp = False # True
        ags = self.related_contexts()
        #add = 0
        #if self.is_context and self in ags:
        #    if len(ags) > 1:
        #        add = 1
        need = [] #noneed = []
        for ag in ags:
            try:
                if ag.project and ag.project.services():
                    if 'exchanges' in ag.project.services(): # if not
                        resp = True #noneed.append(ag)
                else:
                    pass #noneed.append(ag)
            except:
                pass
        #if len(ags)-add == len(noneed):
        #    resp = False
        #if self in noneed:
        #    resp = False
        return resp

    def need_projects(self):
        resp = True
        ags = self.related_contexts()
        if self in ags and len(ags) > 1:
            ags.remove(self)
        if ags and len(ags) < 2: # only one project
            if ags[0].project and ags[0].project.services():
                if not 'projects' in ags[0].project.services():
                    resp = False
        #import pdb; pdb.set_trace()
        return resp

    def need_tasks(self):
        resp = False #True
        ags = self.related_contexts()
        #add = 0
        #if self.is_context and self in ags:
        #    if len(ags) > 1:
        #        add = 1
        #noneed = []
        for ag in ags:
            try:
                if ag.project and ag.project.services():
                    if 'tasks' in ag.project.services(): # if not
                        resp = True #noneed.append(ag)
                #else:
                #    noneed.append(ag)
            except:
                pass
        #if len(ags)-add == len(noneed):
        #    resp = False
        #if self in noneed:
        #    resp = False
        if not self.is_participant():
            resp = False
        return resp

    def need_multicurrency(self):
        resp = False
        ags = self.related_contexts()
        add = 0
        if self.is_context and not self in ags:
            ags.append(self)
        need = []
        for ag in ags:
            try:
                if ag.project and ag.project.services():
                    if 'multicurrency' in ag.project.services():
                        need.append(ag)
            except:
                pass
        if len(need):
            for ag in need:
                if not ag == self:
                    if self in ag.participants():
                        resp = True
                    else:
                        resp = False
                else:
                    resp = True

        #import pdb; pdb.set_trace()
        return resp

    def invoicing_candidates(self):
        ctx = self.related_contexts()
        ids = [c.id for c in ctx if c.is_active_freedom_coop_member()]
        if self.is_active_freedom_coop_member():
            ids.insert(0, self.id)
        return EconomicAgent.objects.filter(id__in=ids)


    #  bum2
    def managed_projects(self): #returns a list or None
        agents = [ag.has_associate for ag in self.is_associate_of.filter(association_type__association_behavior="manager")]
        if self.is_context and not self in agents:
          agents.extend([self])
        return [a for a in agents if a.is_context] #EconomicAgent.objects.filter(pk__in=agent_ids)

    def is_public(self):
        project = self.project
        if project and project.is_public():
          return True
        else:
          return False

    def used_units_ids(self, exs=None):
        #print("..used_units_ids:")
        if not exs:
            exs = Exchange.objects.exchanges_by_type(self)
        uids = []
        for ex in exs:
          txs = ex.transfers.all()#filter(events__unit_of_value__ocp_unit_type__isnull=False) #exchange_type.transfer_types.all()
          for tx in txs:
            uv = tx.unit_of_value()
            if uv and hasattr(uv, 'gen_unit'):
              if not uv.gen_unit.unit_type.id in uids:
                # mptt: get_ancestors(ascending=False, include_self=False)
                #ancs = uv.ocp_unit_type.get_ancestors(False, True)
                #for an in ancs:
                #  if not an.id in uids:
                #    uids.append(an.id)
                uids.append(uv.gen_unit.unit_type.id)
            #rt = tx.resource_type()
            #if rt.unit_of_value and rt.unit_of_value.ocp_unit_type:
              #ancs = rt.unit_of_value.ocp_unit_type.get_ancestors(False, True)
              #for an in ancs:
              #  if not an.id in uids:
              #    uids.append(an.id)
              #pass #uids.append(rt.unit_of_value.ocp_unit_type.id)
            uq = tx.unit_of_quantity()
            if uq:
              #print("....found uq: "+str(uq))
              if not hasattr(uq, 'gen_unit'):
                raise ValidationError("The unit has not gen_unit! "+str(uq))
              else:
                if uq.gen_unit.unit_type.clas == 'each':
                  rt = tx.resource_type()
                  if hasattr(rt, 'ocp_artwork_type') and rt.ocp_artwork_type:
                    ancs = rt.ocp_artwork_type.get_ancestors(False,True)
                    cur = False
                    for an in ancs:
                      if an.clas == "currency":
                        cur = True
                    if cur or rt.ocp_artwork_type.is_account():
                      if hasattr(rt.ocp_artwork_type, 'general_unit_type') and rt.ocp_artwork_type.general_unit_type.id:
                        #if rt.ocp_artwork_type.general_unit_type.ocp_unit_type:
                        if not rt.ocp_artwork_type.general_unit_type.id in uids:
                            uids.append(rt.ocp_artwork_type.general_unit_type.id)
                        else:
                            pass #raise ValidationError("the unit type is already in uids: "+str(uids))
                      else:
                          raise ValidationError("The rt has not any related general_unit_type! "+str(rt.ocp_artwork_type))
                    else:
                        pass #raise ValidationError("The rt is not related currency or accounts: "+str(rt.ocp_artwork_type.is_account()))
                  else:
                    loger.info("WARN! The resource type has not a related ocp_artwork_type! id:"+str(rt.id)+" "+str(rt))
                    #raise ValidationError("The resource type has not a related ocp_artwork_type! "+str(rt))
                else:
                    #print("The unit of quantity ocp_unit_type.clas is not 'each': "+str(uq.gen_unit.unit_type.clas))
                    if uq.gen_unit.unit_type.id not in uids and uq.is_currency(): #gen_unit.unit_type.clas == 'each':
                        uids.append(uq.gen_unit.unit_type.id)
                    #pass #raise ValidationError("The unit of quantity ocp_unit_type.clas is not 'each': "+str(uq.ocp_unit_type))
            else:
              rt = tx.resource_type()
              rtun = None
              if not rt:
                shr = tx.transfer_type.is_share()
                if shr:
                    rt = shr.resource_type
              if not rt:
                if tx.transfer_type == ex.ttpay() and ex.join_request:
                    #print("TX: "+str(ex.join_request.payment_unit()))
                    rt = ex.join_request.payment_unit_rt()
              if rt:
                rtun = rt.unit
                #rtut = rtun.unit_type
              else:
                print("....tx has no resource_type? tx:"+str(tx.id)+" "+str(tx))
                loger.info("....tx has no resource_type? tx:"+str(tx.id)+" "+str(tx))
              if rtun:
                if not hasattr(rtun, 'gen_unit'):
                  raise ValidationError("The resource_type unit has not gen_unit! "+str(rtun))
                else:
                  if not rtun.gen_unit.unit_type.id in uids:
                    uids.append(rtun.gen_unit.unit_type.id)
              else:
                print("....tx.resource_type has no unit? rt:"+str(rt))
                loger.info("....tx.resource_type has no unit? rt:"+str(rt))
        if not uids:
            print(".... empty uids set? ag:"+str(self)+" exs:"+str(len(exs)))
            loger.info(".... empty uids set? ag:"+str(self)+" exs:"+str(len(exs)))

        return uids


    def task_assignment_candidates(self):
        answer = []
        if self.is_context:
            answer = [a.is_associate for a in self.all_has_associates() if a.is_associate.is_individual()]
        return answer

    def commitments_with_my_skills(self):
        answer = []
        if not self.is_context:
            skill_ids = self.resource_types.values_list('resource_type__id', flat=True)
            my_projects = self.is_member_of()
            project_ids = []
            for proj in my_projects:
                project_ids.append(proj.id)
            answer = Commitment.objects.unfinished().filter(
                from_agent=None,
                event_type__relationship="work",
                resource_type__id__in=skill_ids,
                process__context_agent__id__in=project_ids)
        return answer

    def child_tree(self):
        from valuenetwork.valueaccounting.utils import agent_dfs_by_association
        #todo: figure out why this failed when AAs were ordered by from_agent
        aas = AgentAssociation.objects.filter(association_type__association_behavior="child").order_by("is_associate__name")
        return agent_dfs_by_association(self, aas, 1)

    def wip(self):
        return self.active_processes()

    def process_types_queryset(self):
        pts = list(ProcessType.objects.filter(context_agent=self))
        parent = self.parent()
        while parent:
            pts.extend(ProcessType.objects.filter(context_agent=parent))
            parent = parent.parent()
        pt_ids = [pt.id for pt in pts]
        return ProcessType.objects.filter(id__in=pt_ids)

    def get_resource_types_with_recipe(self):
        rts = [pt.main_produced_resource_type() for pt in ProcessType.objects.filter(context_agent=self) if pt.main_produced_resource_type()]
        parents = []
        parent = self.parent()
        while parent:
            parents.append(parent)
            parent = parent.parent()
        for p in parents:
            rts.extend([pt.main_produced_resource_type() for pt in ProcessType.objects.filter(context_agent=p) if pt.main_produced_resource_type()])
        parent_rts = rts
        for rt in parent_rts:
            rts.extend(rt.all_children())

        return list(set(rts))

    def get_resource_type_lists(self):
        rt_lists = list(self.lists.all())
        parents = []
        parent = self.parent()
        while parent:
            parents.append(parent)
            parent = parent.parent()
        for p in parents:
            rt_lists.extend(list(p.lists.all()))
        rt_lists = list(set(rt_lists))
        rt_lists.sort(key=lambda x: x.name)
        return rt_lists

    #from here are new methods for context agent code
    def parent(self):
        #assumes only one parent
        associations = self.is_associate_of.filter(association_type__association_behavior="child").filter(state="active")
        parent = None
        if associations.count() > 0:
            parent = associations[0].has_associate
        return parent

    def context_parents(self):
        #assumes multiple parents
        associations = self.is_associate_of.filter(association_type__association_behavior="child").filter(state="active")
        parents = None
        if associations.count() > 0:
            parents = associations #.has_associate
        else:
          associations = self.is_associate_of.filter(association_type__association_behavior="member").filter(state="active")
          if associations.count() > 0:
            parents = associations
        return parents

    def all_ancestors(self):
        parent_ids = []
        parent_ids.append(self.id)
        parent = self.parent()
        while parent:
            parent_ids.append(parent.id)
            parent = parent.parent()
        parents = EconomicAgent.objects.filter(pk__in=parent_ids)
        return parents

    #def children(self): #TODO: not tested
    #    associations = self.has_associates.filter(association_type__association_behavior="child").filter(state="active")
    #    children = []
    #    for association in associations:
    #        children.append(association.has_associate)
    #    return children

    def is_root(self):
        if self.parent():
            return False
        else:
            return True

    def is_context_root(self):
        if self.context_parents(): #.count() > 0:
            return False
        else:
            return True

    def suppliers(self):
        agent_ids = self.has_associates.filter(association_type__association_behavior="supplier").filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def exchange_firms(self):
        agent_ids = self.has_associates.filter(association_type__association_behavior="exchange").filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def members(self):
        agent_ids = self.has_associates.filter(
            Q(association_type__association_behavior="member") | Q(association_type__association_behavior="manager")
            ).filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def member_associations(self):
        return AgentAssociation.objects.filter(has_associate=self).filter(
            Q(association_type__association_behavior="member") | Q(association_type__association_behavior="manager")
            ).filter(state="active")

    def individual_members(self):
        return self.members().filter(agent_type__party_type="individual")

    def is_member_of(self):
        assocs = self.is_associate_of.filter(
            Q(association_type__association_behavior="member") | Q(association_type__association_behavior="manager")
            ).filter(state="active")
        agents = []
        for assoc in assocs:
            agents.append(assoc.has_associate)
        return agents

    def is_member_of_agent(self, agent_id):
        memberships = self.is_member_of()
        for mem in memberships:
            if mem.id == agent_id:
                return True
        return False

    #  bum2
    def managers(self): #returns a list or None
        agent_ids = self.has_associates.filter(association_type__association_behavior="manager").filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def participants(self): #returns a list or None
        both = ["member","manager"]
        agent_ids = self.has_associates.filter(association_type__association_behavior__in=both).filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def candidates(self):
        agents = None
        if self.project and self.project.join_requests:
            agent_ids = self.project.join_requests.filter(state='new').values_list('agent')
            agents = EconomicAgent.objects.filter(pk__in=agent_ids)
        return agents

    def declined_agents(self):
        agents = None
        if self.project and self.project.join_requests:
            agent_ids = self.project.join_requests.filter(state='declined').values_list('agent')
            agents = EconomicAgent.objects.filter(pk__in=agent_ids)
        return agents

    #def affiliates(self):
    #    agent_ids = self.has_associates.filter(association_type__identifier="affiliate").filter(state="active").values_list('is_associate')
    #    return EconomicAgent.objects.filter(pk__in=agent_ids)

    def customers(self):
        agent_ids = self.has_associates.filter(association_type__association_behavior="customer").filter(state="active").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def potential_customers(self):
        agent_ids = self.has_associates.filter(association_type__association_behavior="customer").filter(state="potential").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def all_has_associates_by_type(self, assoc_type_identifier):
        agent_ids = self.has_associates.filter(association_type__identifier=assoc_type_identifier).exclude(state="inactive").values_list('is_associate')
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def has_associates_of_type(self, assoc_type_identifier): #returns boolean
        if self.all_has_associates_by_type(assoc_type_identifier).count() > 0: #todo: can this be made more efficient, return count from sql?
            return True
        else:
            return False

    def has_associates_self_or_inherited(self, assoc_type_identifier):
        assocs = self.all_has_associates_by_type(assoc_type_identifier)
        if assocs:
            return assocs
        parent = self.parent()
        while parent:
            assocs = parent.all_has_associates_by_type(assoc_type_identifier)
            if assocs:
                return assocs
            parent = parent.parent()
        return EconomicAgent.objects.none()

    def associate_count_of_type(self, assoc_type_identifier):
        return self.all_has_associates_by_type(assoc_type_identifier).count()

    def agent_association_types(self):
        my_aats = []
        all_aats = AgentAssociationType.objects.all()
        for aat in all_aats:
            if self.has_associates_of_type(aat.identifier):
                my_aats.append(aat)
        return my_aats

    def has_group_associates(self):
        atgs = self.has_associates.exclude(is_associate__agent_type__party_type="individual")
        return atgs

    def is_associated_with_groups(self):
        afgs = self.is_associate_of.exclude(has_associate__agent_type__party_type="individual")
        return afgs

    def association_with(self, context):
        associations = self.is_associate_of.filter(has_associate=context)
        if associations:
            return associations[0]
        else:
            return []

    def is_manager_of(self, context):
        if self is context:
            return True
        association = self.association_with(context)
        if association:
            if association.association_type.association_behavior == "manager":
                return True
        return False

    def exchange_firm(self):
        xs = self.exchange_firms()
        if xs:
            return xs[0]
        parent = self.parent()
        while parent:
            xs = parent.exchange_firms()
            if xs:
                return xs[0]
            parent = parent.parent()
        return None

    def defined_resource_types(self, event_type=None):
        agents = list(self.all_ancestors())
        rts = []
        for agent in agents:
            rts.extend(agent.context_resource_types.all())
        return list(set(rts))

    def virtual_accounts(self):
        vars = self.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type__behavior="account")
        return [var.resource for var in vars]

    def owned_shares(self, context=None):
        shares = []
        for rs in self.owned_resources():
            if rs.resource_type in EconomicResourceType.objects.shares_types():
                if context:
                    if rs.resource_type.context_agent:
                        if rs.resource_type.context_agent == context:
                            shares.append(rs)
                    else:
                        print("... rs.rt without ca...")
                else:
                    shares.append(rs)
        return shares

    def owned_shares_accounts(self, res_type=None):
        shares = []
        for rs in self.owned_resources():
            if res_type and rs.resource_type == res_type:
                return [rs]
            if not res_type and rs.resource_type in EconomicResourceType.objects.share_accounts_types():
                shares.append(rs)
        return shares

    def owned_accounts(self):
        vars = self.agent_resource_roles.filter(role__is_owner=True).filter(
            Q(resource__resource_type__behavior="account") | Q(resource__resource_type__behavior="dig_acct")
        ).distinct()
        return [var.resource for var in vars]

    def owned_resources(self):
        arrs = self.agent_resource_roles.filter(role__is_owner=True).exclude(resource__quantity=0)
        return [arr.resource for arr in arrs]

    #TODO: this is too simple, would be good to eliminate non-searchable words, manage ""'d words, search whole words only, etc.
    #used for inventory type resources only
    def search_owned_resources(self, search_string, also_search_children=True):
        resources = self.owned_resources()
        if also_search_children:
            children = self.with_all_sub_agents()
            for child in children:
                resources.extend(child.owned_resources())
        answer = []
        strings = search_string.lower().split(" ")
        for res in resources:
            if res.resource_type.inventory_rule == "yes":
                for string in strings:
                    if string in res.resource_type.name.lower():
                        answer.append(res)
                    elif string in res.resource_type.description.lower():
                        answer.append(res)
                    elif string in res.notes.lower():
                        answer.append(res)
                    elif string in res.identifier.lower():
                        answer.append(res)
        return list(set(answer))

    def owned_currency_resources(self):
        arrs = self.agent_resource_roles.filter(role__is_owner=True).exclude(
            resource__resource_type__behavior="other").exclude(
            resource__resource_type__behavior="used").exclude(
            resource__resource_type__behavior="cited").exclude(
            resource__resource_type__behavior="consumed").exclude(
            resource__resource_type__behavior="produced").exclude(
            resource__quantity=0)
        return [arr.resource for arr in arrs]

    def owned_inventory_resources(self):
        arrs = self.agent_resource_roles.filter(role__is_owner=True).filter(
            Q(resource__resource_type__behavior="other")|
            Q(resource__resource_type__behavior="used")|
            Q(resource__resource_type__behavior="cited")|
            Q(resource__resource_type__behavior="consumed")|
            Q(resource__resource_type__behavior="produced")).exclude(
            resource__quantity=0)
        return [arr.resource for arr in arrs]

    def owned_inventory_resources_with_subs(self):
        agents = self.with_all_sub_agents()
        resources = []
        for agent in agents:
            ress = agent.owned_inventory_resources()
            resources.extend(ress)
        return resources

    def create_virtual_account(self, resource_type):
        role_types = AgentResourceRoleType.objects.filter(is_owner=True)
        owner_role_type = None
        if role_types:
            owner_role_type = role_types[0]
        if owner_role_type:
            va = EconomicResource(
                resource_type=resource_type,
                identifier="Virtual account for " + self.nick,
            )
            va.save()
            arr = AgentResourceRole(
                agent=self,
                role=owner_role_type,
                resource=va,
            )
            arr.save()
            return va
        else:
            raise ValidationError("Cannot create virtual account for " + self.nick + " because no owner AgentResourceRoleTypes.")
            return None

    def own_or_parent_value_equations(self):
        ves = self.value_equations.all()
        if ves:
            return ves
        parent = self.parent()
        while parent:
            ves = parent.value_equations.all()
            if ves:
                return ves
            parent = parent.parent()
        return []

    def live_value_equations(self):
        #shd this use own_or_parent_value_equations?
        return self.value_equations.filter(live=True)

    def compatible_value_equation(self, value_equation):
        if value_equation.context_agent == self:
            return True
        if value_equation.live:
            if value_equation in self.live_value_equations():
                return True
        else:
            if value_equation in self.own_or_parent_value_equations():
                return True
        return False

    def default_agent(self):
        return self

    def all_suppliers(self):
        sups = list(self.suppliers())
        parent = self.parent()
        while parent:
            sups.extend(parent.suppliers())
            parent = parent.parent()
        sup_ids = [sup.id for sup in sups]
        return EconomicAgent.objects.filter(pk__in=sup_ids)

    def all_customers(self):
        custs = list(self.customers())
        parent = self.parent()
        while parent:
            custs.extend(parent.customers())
            parent = parent.parent()
        cust_ids = [cust.id for cust in custs]
        return EconomicAgent.objects.filter(pk__in=cust_ids)

    def all_members(self):
        mems = self.all_members_list()
        mem_ids = [mem.id for mem in mems]
        return EconomicAgent.objects.filter(pk__in=mem_ids)

    def all_members_list(self):
        mems = list(self.members())
        parent = self.parent()
        while parent:
            mems.extend(parent.members())
            parent = parent.parent()
        return mems

    def all_ancestors_and_members(self):
        agent_list = list(self.all_ancestors())
        agent_list.extend(self.all_members_list())
        agent_ids = [agent.id for agent in agent_list]
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def context_equipment_users(self):
        agent_list = self.all_members_list()
        agent_list.extend([agent for agent in self.exchange_firms()])
        return agent_list

    def all_has_associates(self):
        return self.has_associates.all().order_by('association_type__name', 'is_associate__nick')

    def all_is_associates(self):
        return self.is_associate_of.all().order_by('association_type__name', 'has_associate__nick')

    def all_associations(self):
        return AgentAssociation.objects.filter(
            Q(has_associate=self ) | Q(is_associate=self))

    def all_active_associations(self):
        return AgentAssociation.objects.filter(
            Q(has_associate=self ) | Q(is_associate=self)).filter(state="active").order_by('association_type__name', 'has_associate__name')

    def active_associates_as_subject(self):
        return AgentAssociation.objects.filter(is_associate=self).filter(state="active").order_by('association_type__name', 'has_associate__name')

    def active_associates_as_object(self): #has_associates
        return AgentAssociation.objects.filter(has_associate=self).filter(state="active").order_by('association_type__name', 'has_associate__name')

    def active_association_types(self):
        assocs = self.all_active_associations()
        roles = []
        for assoc in assocs:
            if assoc.association_type not in roles:
                roles.append(assoc.association_type)
        return roles

    def is_context_agent(self):
        return self.is_context

    def orders_queryset(self):
        orders = []
        exf = self.exchange_firm()
        cr_orders = []
        if exf:
            crs = self.undistributed_events()
            cr_orders = [cr.exchange.order for cr in crs if cr.exchange]
        for order in Order.objects.all():
            cas = order.context_agents()
            if self in cas:
                orders.append(order)
            if exf:
                if exf in cas:
                    if order in cr_orders:
                        orders.append(order)
        orders = list(set(orders))
        order_ids = [order.id for order in orders]
        return Order.objects.filter(id__in=order_ids)

    def shipments_queryset(self):
        shipments = []
        exf = self.exchange_firm()
        #ship = EventType.objects.get(label="ships")
        #transfer = EventType.objects.get(name="Reciprocal Transfer")
        #qs = EconomicEvent.objects.filter(Q(event_type=ship)|Q(event_type=transfer))
        et_give = EventType.objects.get(name="Give")
        uc_demand = UseCase.objects.get(identifier="demand_xfer")
        qs = EconomicEvent.objects.filter(event_type=et_give).filter(transfer__transfer_type__exchange_type__use_case=uc_demand)
        #todo: retest, may need production events for shipments to tell
        #if a shipment shd be excluded or not
        if exf:
            cas = [self, exf]
            qs = qs.filter(context_agent__in=cas)
            ids_to_delete = []
            for ship in qs:
                if ship.context_agent != self:
                    if ship.commitment:
                        if ship.commitment.context_agent != self:
                            pc_cas = [pc.context_agent for pc in ship.commitment.get_production_commitments_for_shipment()]
                            pc_cas = list(set(pc_cas))
                            if self not in pc_cas:
                                ids_to_delete.append(ship.id)
                    #else:
                    #    ids_to_delete.append(ship.id)
                if ids_to_delete:
                    qs = qs.exclude(id__in=ids_to_delete)
        else:
            qs = qs.filter(context_agent=self)
        return qs

    def undistributed_events(self):
        event_ids = []
        #et = EventType.objects.get(name="Cash Receipt")
        events = EconomicEvent.objects.filter(to_agent=self).filter(is_to_distribute=True)
        for event in events:
            if event.is_undistributed():
                event_ids.append(event.id)
        exf = self.exchange_firm()
        #todo: maybe use shipments in addition or instead of virtual accounts?
        #exchange firm might put cash receipt into a more general virtual account
        if exf:
            events = exf.undistributed_events()
            event_ids.extend(event.id for event in events)
            #todo: analyze this. (note change from cash receipts to events marked is_to_distribute
            #is_undistributed is unnecessary: crs only includes undistributed
            #is_virtual_account_of is the restriction that needs analysis
            #for cr in crs:
            #    if cr.is_undistributed():
            #        if cr.resource.is_virtual_account_of(self):
            #            cr_ids.append(cr.id)
        return EconomicEvent.objects.filter(id__in=event_ids)

    def undistributed_distributions(self):
        id_ids = []
        et = EventType.objects.get(name="Distribution")
        ids = EconomicEvent.objects.filter(to_agent=self).filter(event_type=et)
        for id in ids:
            if id.is_undistributed():
                id_ids.append(id.id)
        return EconomicEvent.objects.filter(id__in=id_ids)

    def is_deletable(self):
        if self.given_events.filter(quantity__gt=0):
            return False
        if self.taken_events.filter(quantity__gt=0):
            return False
        if self.given_commitments.filter(quantity__gt=0):
            return False
        if self.taken_commitments.filter(quantity__gt=0):
            return False
        if self.exchanges_as_customer.all():
            return False
        if self.exchanges_as_supplier.all():
            return False
        if self.virtual_accounts():
            return False
        if self.faircoin_resource():
            return False
        if self.events.filter(quantity__gt=0):
            return False
        if self.commitments.filter(quantity__gt=0):
            return False
        if self.is_associate_of.all():
            if self.is_associate_of.filter(state='active'):
                return False
            else:
                rels = self.is_associate_of.all()
                reqs = self.project_join_requests.filter(state='new')
                if len(rels) == 1:
                    if len(reqs) == 1:
                        pass
                    else:
                        return False
                else:
                    return False
        if self.has_associates.all():
            return False
        return True

    def contexts_participated_in(self):
        answer = []
        if self.agent_type.party_type == "individual":
            events = self.given_events.exclude(context_agent__isnull=True)
            cids = events.values_list('context_agent', flat=True)
            cids = list(set(cids))
            answer = EconomicAgent.objects.filter(id__in=cids)
        return answer


class AgentUser(models.Model):
    agent = models.ForeignKey(EconomicAgent,
        verbose_name=_('agent'), related_name='users', on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE,
        verbose_name=_('user'), related_name='agent')


ASSOCIATION_BEHAVIOR_CHOICES = (
    ('manager', 'manager'),
    ('custodian', 'custodian'),
    ('member', 'member'),
    ('child', 'child'),
    ('peer', 'peer'),
    ('supplier', 'supplier'),
    ('customer', 'customer')
)

class AgentAssociationTypeManager(models.Manager):

    def member_types(self):
        return AgentAssociationType.objects.filter(Q(association_behavior='member')|Q(association_behavior='manager'))

class AgentAssociationType(models.Model):
    identifier = models.CharField(_('identifier'), max_length=12, unique=True)
    name = models.CharField(_('name'), max_length=128)
    plural_name = models.CharField(_('plural name'), default="", max_length=128)
    association_behavior = models.CharField(_('association behavior'),
        max_length=12, choices=ASSOCIATION_BEHAVIOR_CHOICES,
        blank=True, null=True)
    description = models.TextField(_('description'), blank=True, null=True)
    label = models.CharField(_('label'), max_length=32, null=True)
    inverse_label = models.CharField(_('inverse label'), max_length=40, null=True)

    objects = AgentAssociationTypeManager()

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, identifier, name, plural_name, association_behavior, label, inverse_label, verbosity=2):
        """
        Creates a new AgentType, updates an existing one, or does nothing.
        This is intended to be used as a post_syncdb manangement step.
        """
        try:
            agent_association_type = cls._default_manager.get(identifier=identifier)
            updated = False
            if name != agent_association_type.name:
                agent_association_type.name = name
                updated = True
            if plural_name != agent_association_type.plural_name:
                agent_association_type.plural_name = plural_name
                updated = True
            if association_behavior != agent_association_type.association_behavior:
                agent_association_type.association_behavior = association_behavior
                updated = True
            if label != agent_association_type.label:
                agent_association_type.label = label
                updated = True
            if inverse_label != agent_association_type.inverse_label:
                agent_association_type.inverse_label = inverse_label
                updated = True
            if updated:
                agent_association_type.save()
                if verbosity > 1:
                    print("Updated {} AgentAssociationType".format(name))
        except cls.DoesNotExist:
            cls(identifier=identifier, name=name, plural_name=plural_name, association_behavior=association_behavior, label=label, inverse_label=inverse_label).save()
            if verbosity > 1:
                print("Created {} AgentAssociationType".format(name))

    @property #ValueFlows
    def category(self):
        if self.association_behavior == "member" or self.association_behavior == "manager":
            return "member"
        elif self.association_behavior == "child":
            return "part"
        elif self.association_behavior == "supplier" or self.association_behavior == "customer":
            return "trading partner"
        elif self.association_behavior == "child":
            return "part"
        elif self.association_behavior == "custodian":
            return "legal partner"
        elif self.association_behavior == "peer":
            return "peer"
        else:
            return "none"


#from django.db.models.signals import post_migrate
#from valuenetwork.valueaccounting.apps import ValueAccountingAppConfig

#def create_agent_types(app, **kwargs):
#    if app != "valueaccounting":
#        return
def create_agent_types(**kwargs):
    AgentType.create('Individual', 'individual', False)
    AgentType.create('Organization', 'org', True)
    AgentType.create('Network', 'network', True)
    AgentType.create('Project', 'team', True)
    #AgentType.create('Community', 'community', True)
    AgentType.create('Company', 'company', True)
    print("created agent types")

#post_migrate.connect(create_agent_types, sender=ValueAccountingAppConfig)

#def create_agent_association_types(app, **kwargs):
#    if app != "valueaccounting":
#        return
def create_agent_association_types(**kwargs):
    AgentAssociationType.create('child', 'Child', 'Children', 'child', 'is child of', 'has child')
    AgentAssociationType.create('member', 'Member', 'Members', 'member', 'is member of', 'has member')
    AgentAssociationType.create('supplier', 'Supplier', 'Suppliers', 'supplier', 'is supplier of', 'has supplier')
    AgentAssociationType.create('customer', 'Customer', 'Customers', 'customer', 'is customer of', 'has customer')
    print("created agent association types")

#post_migrate.connect(create_agent_association_types, sender=ValueAccountingAppConfig)

RELATIONSHIP_STATE_CHOICES = (
    ('active', _('active')),
    ('inactive', _('inactive')),
    ('potential', _('candidate')),
)

class AgentAssociation(models.Model):
    is_associate = models.ForeignKey(EconomicAgent,
        verbose_name=_('is associate of'), related_name='is_associate_of', on_delete=models.CASCADE)
    has_associate = models.ForeignKey(EconomicAgent,
        verbose_name=_('has associate'), related_name='has_associates', on_delete=models.CASCADE)
    association_type = models.ForeignKey(AgentAssociationType,
        verbose_name=_('association type'), related_name='associations', on_delete=models.CASCADE)
    description = models.TextField(_('description'), blank=True, null=True)
    state = models.CharField(_('state'),
        max_length=12, choices=RELATIONSHIP_STATE_CHOICES,
        default='active')

    class Meta:
        ordering = ('is_associate',)

    def __str__(self):
        return self.is_associate.nick + " " + self.association_type.label + " " + self.has_associate.nick

    def representation(self):
        state = ""
        if self.state == "potential":
            state = "".join(["(", self.get_state_display(), ")"])
        return " ".join([
            self.is_associate.nick,
            self.association_type.label,
            self.has_associate.nick,
            state,
            ])

    @property #ValueFlows
    def subject(self):
        return self.is_associate

    @property #ValueFlows
    def object(self):
        return self.has_associate

    @property #ValueFlows
    def relationship(self):
        return self.association_type

    @property #ValueFlows
    def join_request_date(self):
        from work.models import JoinRequest, Project
        proj = Project.objects.filter(agent=self.has_associate)
        if proj:
            jrs = JoinRequest.objects.filter(project=proj[0]).filter(agent=self.is_associate)
            if jrs:
                jr = jrs[0]
                return jr.request_date
        return None


#todo exchange redesign fallout
#many of these are obsolete
DIRECTION_CHOICES = (
    ('in', _('input')),
    ('consume', _('consume')),
    ('use', _('use')),
    ('out', _('output')),
    ('cite', _('citation')),
    ('work', _('work')),
    ('todo', _('todo')),
    ('pay', _('payment')),
    ('receive', _('receipt')),
    ('expense', _('expense')),
    ('cash', _('cash input')),
    ('resource', _('resource contribution')),
    ('receivecash', _('cash receipt')),
    ('shipment', _('shipment')),
    ('distribute', _('distribution')),
    ('adjust', _('adjust')),
    #('payexpense', _('expense payment')),
    ('disburse', _('disburses cash')),
)

RELATED_CHOICES = (
    ('process', _('process')),
    ('agent', _('agent')), #not used logically as an event type, rather for agent - resource type relationships
    ('exchange', _('exchange')),
    ('distribution', _('distribution')),
)

RESOURCE_EFFECT_CHOICES = (
    ('+', _('increase')),
    ('-', _('decrease')),
    ('+-', _('adjust')),
    ('x', _('transfer')), #means - for from_agent, + for to_agent
    ('=', _('no effect')),
    ('<', _('failure')),
    ('+~', _('create to change')),
    ('>~', _('to be changed')),
    ('~>', _('change')),
)


class EventTypeManager(models.Manager):

    def get_by_natural_key(self, name):
        return self.get(name=name)

    def used_for_value_equations(self):
        ets = EventType.objects.all()
        used_ids = [et.id for et in ets if et.used_for_value_equations()]
        return EventType.objects.filter(id__in=used_ids)

    #todo exchange redesign fallout
    #obsolete event type
    def cash_event_types(self):
        return EventType.objects.filter(relationship="cash")

    #ValueFlows
    def convert_action_to_event_type(self, action):
        if action == "work":
            return EventType.objects.get(name="Time Contribution")
        elif action == "consume":
            return EventType.objects.get(name="Resource Consumption")
        elif action == "produce":
            return EventType.objects.get(name="Resource Production")
        elif action == "use":
            return EventType.objects.get(name="Resource use")
        elif action == "cite":
            return EventType.objects.get(name="Citation")
        elif action == "accept":
            return EventType.objects.get(name="To Be Changed")
        elif action == "improve":
            return EventType.objects.get(name="Change")
        elif action == "give":
            return EventType.objects.get(name="Give")
        elif action == "take":
            return EventType.objects.get(name="Receive")
        elif action == "adjust":
            return EventType.objects.get(name="Adjust Quantity")
        else:
            return "NONE"


class EventType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    label = models.CharField(_('label'), max_length=32)
    inverse_label = models.CharField(_('inverse label'), max_length=40, blank=True)
    relationship = models.CharField(_('relationship'),
        max_length=12, choices=DIRECTION_CHOICES, default='in')
    related_to = models.CharField(_('related to'),
        max_length=12, choices=RELATED_CHOICES, default='process')
    resource_effect = models.CharField(_('resource effect'),
        max_length=12, choices=RESOURCE_EFFECT_CHOICES)
    unit_type = models.CharField(_('unit type'),
        max_length=12, choices=UNIT_TYPE_CHOICES,
        blank=True)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = EventTypeManager()

    class Meta:
        ordering = ('label',)

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        unique_slugify(self, self.name)
        super(EventType, self).save(*args, **kwargs)

    @classmethod
    def create(cls, name, label, inverse_label, relationship, related_to, resource_effect, unit_type, verbosity=2):
        """
        Creates a new EventType, updates an existing one, or does nothing.
        This is intended to be used as a post_syncdb manangement step.
        """
        try:
            event_type = cls._default_manager.get(name=name)
            updated = False
            if name != event_type.name:
                event_type.name = name
                updated = True
            if label != event_type.label:
                event_type.label = label
                updated = True
            if inverse_label != event_type.inverse_label:
                event_type.inverse_label = inverse_label
                updated = True
            if relationship != event_type.relationship:
                event_type.relationship = relationship
                updated = True
            if related_to != event_type.related_to:
                event_type.related_to = related_to
                updated = True
            if resource_effect != event_type.resource_effect:
                event_type.resource_effect = resource_effect
                updated = True
            if unit_type != event_type.unit_type:
                event_type.unit_type = unit_type
                updated = True
            if updated:
                event_type.save()
                if verbosity > 1:
                    print("Updated {} EventType".format(name))
        except cls.DoesNotExist:
            cls(name=name, label=label, inverse_label=inverse_label, relationship=relationship,
                related_to=related_to, resource_effect=resource_effect, unit_type=unit_type).save()
            if verbosity > 1:
                print("Created {} EventType".format(name))

    @property #ValueFlows
    def action(self):
        if self.name == "Time Contribution" or self.name == "Todo":
            return "work"
        elif self.name == "Resource Consumption":
            return "consume"
        elif self.name == "Resource Production" or self.name == "Create Changeable":
            return "produce"
        elif self.name == "Resource use":
            return "use"
        elif self.name == "Citation":
            return "cite"
        elif self.name == "Change":
            return "improve"
        elif self.name == "To Be Changed":
            return "accept"
        elif self.name == "Give":
            return "give"
        elif self.name == "Receive":
            return "take"
        elif self.name == "Adjust Quantity":
            return "adjust"
        else:
            return self.label

    def default_event_value_equation(self):
        #todo exchange redesign fallout
        #some of these are obsolete
        if self.used_for_value_equations():
            if self.relationship == "cite" or self.relationship == "pay" or self.name == "Cash Receipt":
                return "quantity"
            elif self.relationship == "resource" or self.relationship == "receive":
                return "value"
            elif self.relationship == "expense" or self.relationship == "cash":
                return "value"
            elif self.relationship == "use":
                return "quantity * valuePerUnitOfUse"
            else:
                return "quantity * valuePerUnit"
        return ""

    def used_for_value_equations(self):
        #todo exchange redesign fallout
        #some of these are obsolete
        bad_relationships = [
            "consume",
            "in",
            #"pay",
            #"receivecash",
            "shipment",
            "adjust",
            "distribute",
            "use",
        ]
        bad_names = [
            "Work Provision",
            "Failed quantity",
            "Damage",
            "Receipt",
            "Sale",
            "Supply",
        ]
        if self.relationship in bad_relationships:
            return False
        elif self.name in bad_names:
            return False
        return True

    def creates_resources(self):
        if "+" in self.resource_effect:
            #this is to rule out adjustments
            if not "-" in self.resource_effect:
                return True
        return False

    def consumes_resources(self):
        return self.resource_effect == "-"

    def is_change_related(self):
        if "~" in self.resource_effect:
            return True
        else:
            return False

    def applies_stage(self):
        return self.resource_effect == "+~"

    def changes_stage(self):
        return self.resource_effect == "~>"

    def stage_to_be_changed(self):
        return self.resource_effect == ">~"

    def is_work(self):
        if self.relationship == "work":
            return True
        else:
            return False


class AccountingReference(models.Model):
    code = models.CharField(_('code'), max_length=128, unique=True)
    name = models.CharField(_('name'), max_length=128)

    def __str__(self):
        return self.name


#MATERIALITY_CHOICES = (
#    ('intellectual', _('intellectual')),
#    ('material', _('material')),
#    ('purchmatl', _('purchased material')),
#    ('purchtool', _('purchased tool')),
#    ('space', _('space')),
#    ('tool', _('tool')),
#    ('value', _('value')),
#    ('work', _('work')),
#)

class ResourceState(models.Model):
    name = models.CharField(_('name'), max_length=128, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)


class RecipeInheritance(object):
    def __init__(self, parent, heir):
        self.parent = parent
        self.heir = heir

    def substitute(self, candidate):
        if candidate == self.parent:
            return self.heir
        else:
            return candidate


class ResourceClass(models.Model):
    name = models.CharField(_('name'), max_length=128, unique=True)
    description = models.TextField(_('description'), blank=True, null=True)

    def __str__(self):
        return self.name


class EconomicResourceTypeManager(models.Manager):

    def resource_types_with_recipes(self, context_agent=None):
        resource_types = []
        if context_agent:
            candidate_resource_types = context_agent.get_resource_types_with_recipe()
            for rt in candidate_resource_types:
                if rt.recipe_needs_starting_resource():
                    rt.onhand_resources = []
                    onhand = rt.onhand_for_resource_driven_recipe()
                    if onhand:
                        resource_types.append(rt)
                        for oh in onhand:
                            rt.onhand_resources.append(oh)
                else:
                    resource_types.append(rt)
        else:
            rts = EconomicResourceType.objects.all()
            for rt in rts:
                if rt.process_types.filter(event_type__relationship='out'):
                    resource_types.append(rt)
        return resource_types

    def membership_share(self):
        try:
            share = EconomicResourceType.objects.get(name_en="FreedomCoop Share")
        except EconomicResourceType.DoesNotExist:
            raise ValidationError("FreedomCoop Share does not exist by that name")
        return share

    def shares_types(self):
        shats = []
        try:
            from work.models import Ocp_Artwork_Type
            shr = Ocp_Artwork_Type.objects.get(clas='shares')
            ids = [sh.id for sh in shr.get_descendants()]
            shats = EconomicResourceType.objects.filter(ocp_artwork_type__id__in=ids)
        except:
            loger.error("Can't find share types! at "+str(self))
            pass
        return shats

    def share_accounts_types(self):
        shats = []
        try:
            from work.models import Ocp_Artwork_Type
            shr = Ocp_Artwork_Type.objects.get(clas='accounts')
            ats = [rs.ocp_artwork_type for rs in self.shares_types()]
            accs = Ocp_Artwork_Type.objects.filter(rel_nonmaterial_type__in=ats)
            for ac in accs:
                shats.append(ac.resource_type)
        except:
            loger.error("Can't find share account types! at "+str(self))
            pass
        return shats


    #moved this logic from views for use in api
    def resource_types_by_facet_values(self, fvs_string=None):
        """ Logic:
            Facet values in different Facets are ANDed.
            Ie, a resource type must have all of those facet values.
            Facet values in the same Facet are ORed.
            Ie, a resource type must have at least one of those facet values.
        """
        rts = EconomicResourceType.objects.all()
        resource_types = []
        facets = Facet.objects.all()
        if fvs_string:
            vals = fvs_string.split(",")
            if vals[0] == "all":
                for rt in rts:
                    if rt.onhand_qty()>0:
                        resource_types.append(rt)
            else:
                fvs = []
                for val in vals:
                    val_split = val.split(":")
                    fname = val_split[0]
                    fvalue = val_split[1].strip()
                    fvs.append(FacetValue.objects.get(facet__name=fname,value=fvalue))
                fv_ids = [fv.id for fv in fvs]
                rt_facet_values = ResourceTypeFacetValue.objects.filter(facet_value__id__in=fv_ids)
                rts = [rtfv.resource_type for rtfv in rt_facet_values]
                answer = []
                singles = [] #Facets with only one facet_value in the Pattern
                multis = []  #Facets with more than one facet_value in the Pattern
                aspects = {}
                for fv in fvs:
                    if fv.facet not in aspects:
                        aspects[fv.facet] = []
                    aspects[fv.facet].append(fv)
                for facet, fvs in list(aspects.items()):
                    if len(fvs) > 1:
                        for fv in fvs:
                            multis.append(fv)
                    else:
                        singles.append(fvs[0])
                single_ids = [s.id for s in singles]
                for rt in rts:
                    rt_singles = [rtfv.facet_value for rtfv in rt.facets.filter(facet_value_id__in=single_ids)]
                    rt_multis = [rtfv.facet_value for rtfv in rt.facets.exclude(facet_value_id__in=single_ids)]
                    if set(rt_singles) == set(singles):
                        if not rt in answer:
                            if multis:
                                # if multis intersect
                                if set(rt_multis) & set(multis):
                                    answer.append(rt)
                            else:
                                answer.append(rt)
                answer_ids = [a.id for a in answer]
                rts = list(EconomicResourceType.objects.filter(id__in=answer_ids))
                for rt in rts:
                    if rt.onhand_qty()>0:
                        resource_types.append(rt)
                resource_types.sort(key=lambda rt: rt.label())
        else:
            for rt in rts:
                if rt.onhand_qty()>0:
                    resource_types.append(rt)
        return resource_types


INVENTORY_RULE_CHOICES = (
    ('yes', _('Keep inventory')),
    ('no', _('Not worth it')),
    ('never', _('Does not apply')),
)

BEHAVIOR_CHOICES = (
    ('work', _('Type of Work')),
    ('account', _('Virtual Account')),
    ('dig_curr', _('Digital Currency')),
    ('dig_acct', _('Digital Currency Address')),
    ('dig_wallet', _('Digital Currency Wallet')),
    ('consumed', _('Produced/Changed + Consumed')),
    ('used', _('Produced/Changed + Used')),
    ('cited', _('Produced/Changed + Cited')),
    ('produced', _('Produced/Changed only')),
    ('other', _('Other')),
)


class EconomicResourceType(models.Model):
    name = models.CharField(_('name'), max_length=128, unique=True)
    #version = models.CharField(_('version'), max_length=32, blank=True)
    parent = models.ForeignKey('self', blank=True, null=True,
        verbose_name=_('parent'), related_name='children', on_delete=models.SET_NULL)
    resource_class = models.ForeignKey(ResourceClass, blank=True, null=True,
        verbose_name=_('resource class'), related_name='resource_types', on_delete=models.SET_NULL)
    unit = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="resource_units",
        help_text=_('if this resource has different units of use and inventory, this is the unit of inventory'))
    unit_of_use = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of use'), related_name="units_of_use",
        help_text=_('if this resource has different units of use and inventory, this is the unit of use'))
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={'unit_type': 'value'},
        verbose_name=_('unit of value'), related_name="resource_type_value_units", editable=False)
    value_per_unit = models.DecimalField(_('value per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"), editable=False)
    value_per_unit_of_use = models.DecimalField(_('value per unit of use'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"), editable=False)
    price_per_unit = models.DecimalField(_('price per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    unit_of_price = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={'unit_type': 'value'},
        verbose_name=_('unit of price'), related_name="resource_type_price_units")
    substitutable = models.BooleanField(_('substitutable'), default=True,
        help_text=_('Can any resource of this type be substituted for any other resource of this type?'))
    inventory_rule = models.CharField(_('inventory rule'), max_length=5,
        choices=INVENTORY_RULE_CHOICES, default='yes')
    behavior = models.CharField(_('behavior'), max_length=12,
        choices=BEHAVIOR_CHOICES, default='other')
    photo = ThumbnailerImageField(_("photo"),
        upload_to='photos', blank=True, null=True)
    photo_url = models.CharField(_('photo url'), max_length=255, blank=True)
    url = models.CharField(_('url'), max_length=255, blank=True)
    description = models.TextField(_('description'), blank=True, null=True)
    accounting_reference = models.ForeignKey(AccountingReference, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('accounting reference'), related_name="resource_types",
        help_text=_('optional reference to an external account'))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='resource_types_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='resource_types_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='context_resource_types')

    objects = EconomicResourceTypeManager()

    class Meta:
        ordering = ('name',)
        verbose_name = _('resource type')

    def __str__(self):
        return self.name

    def description_str(self):
        if self.description:
            stri = self.description.replace("\n\r", "<br>").replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
            return stri
        else:
            return self.description

    def get_absolute_url(self):
        return reverse('resource_type', kwargs={'resource_type_id': str(self.id),})

    @property #ValueFlows
    def image(self):
        if self.photo_url:
            return self.photo_url
        elif self.photo:
            from valuenetwork.valueaccounting.utils import get_url_starter
            return get_url_starter() + self.photo.url
        else:
            return ""

    @property #ValueFlows
    def note(self):
        return self.description

    @property
    def category(self):
        if (self.behavior == "other"
            or self.behavior == "consumed"
            or self.behavior == "used"
            or self.behavior == "produced"
            or self.behavior == "cited"):
            return "INVENTORY"
        elif self.behavior == "work":
            return "WORK"
        else:
            return "CURRENCY"

    @property
    def process_category(self):
        if (self.behavior ==  "consumed"
            or self.behavior == "used"
            or self.behavior == "produced"
            or self.behavior == "cited"):
            return self.behavior
        else:
            return None

    def label(self):
        return self.__str__()

    def save(self, *args, **kwargs):
        #unique_slugify(self, self.name)
        super(EconomicResourceType, self).save(*args, **kwargs)

    def is_virtual_account(self):
        if self.behavior == "account" or self.behavior == "dig_acct":
            return True
        else:
            return False

    def is_account(self):
        if hasattr(self, 'ocp_artwork_type') and self.ocp_artwork_type:
            return self.ocp_artwork_type.is_account()
        return self.is_virtual_account()

    def is_work(self):
        if self.behavior == "work":
            return True
        else:
            return False

    def direct_children(self):
        return self.children.all()

    def with_all_children(self):
        answer = [self,]
        kids = self.direct_children()
        for kid in kids:
            answer.extend(kid.with_all_children())
        return answer

    def all_children(self):
        kids = self.direct_children()
        answer = list(kids)
        for kid in kids:
            answer.extend(kid.all_children())
        return answer

    def child_of_class(self, resource_class):
        kids = self.all_children()
        for kid in kids:
            if kid.resource_class == resource_class:
                return kid
        return None

    def node_id(self):
        return "-".join(["ResourceType", str(self.id)])

    def color(self):
        return "red"

    def onhand(self):
        return EconomicResource.goods.filter(
            resource_type=self,
            quantity__gt=0)

    def onhand_for_stage(self, stage):
        return EconomicResource.goods.filter(
            resource_type=self,
            stage=stage,
            quantity__gt=0)

    def onhand_for_exchange_stage(self, stage):
        return EconomicResource.goods.filter(
            resource_type=self,
            exchange_stage=stage,
            quantity__gt=0)

    def commits_for_exchange_stage(self, stage):
        cfes = []
        commits = Commitment.objects.filter(
            exchange_stage=stage,
            resource_type = self,
            finished=False)
        for com in commits:
            if com.unfilled_quantity > 0:
                cfes.append(com)
        return cfes

    def onhand_for_resource_driven_recipe(self):
        return EconomicResource.goods.filter(
            resource_type=self,
            independent_demand__isnull=True,
            stage__isnull=True,
            quantity__gt=0)

    def all_resources(self):
        return self.resources.all()

    def onhand_qty(self):
        return sum(oh.quantity for oh in self.onhand())

    def onhand_qty_for_stage(self, stage):
        return sum(oh.quantity for oh in self.onhand_for_stage(stage))

    def onhand_qty_for_commitment(self, commitment):
        #pr changed
        #does not need order_item because net already skipped non-subs
        due_date = commitment.due_date
        stage = commitment.stage
        if stage:
            oh_qty = self.onhand_qty_for_stage(stage)
            priors = self.consuming_commitments_for_stage(stage).filter(due_date__lt=due_date)
        else:
            oh_qty = self.onhand_qty()
            priors = self.consuming_commitments().filter(due_date__lt=due_date)
        remainder = oh_qty - sum(p.quantity for p in priors)
        if remainder > 0:
            return remainder
        else:
            return Decimal("0")

    def scheduled_qty_for_commitment(self, commitment):
        #pr changed
        #does not need order_item because net already skipped non-subs
        due_date = commitment.due_date
        stage = commitment.stage
        sked_rcts = self.active_producing_commitments().filter(due_date__lte=due_date).exclude(id=commitment.id)
        if stage:
            sked_rcts = sked_rcts.filter(stage=stage)
        unfilled_rcts = []
        for sr in sked_rcts:
            if not sr.is_fulfilled():
                unfilled_rcts.append(sr)
        sked_qty = sum(pc.quantity for pc in unfilled_rcts)
        if not sked_qty:
            return Decimal("0")
        if stage:
            priors = self.consuming_commitments_for_stage(stage).filter(due_date__lt=due_date)
        else:
            priors = self.consuming_commitments().filter(due_date__lt=due_date)
        remainder = sked_qty - sum(p.quantity for p in priors)
        if remainder > 0:
            return remainder
        else:
            return Decimal("0")

    def producing_process_type_relationships(self):
        #todo pr: this shd be replaced by own_recipes
        return self.process_types.filter(event_type__relationship='out')

    def manufacturing_producing_process_type_relationships(self):
        return self.process_types.filter(
            stage__isnull=True,
            event_type__relationship='out')

    def own_recipes(self):
        #todo pr: or shd that be own_producing_commitment_types?
        return self.process_types.filter(event_type__relationship='out')

    def own_or_parent_recipes(self):
        ptrs =  self.own_recipes()
        parent = None
        inheritance = None
        if not ptrs:
            parent = self.parent
            while parent:
                ptrs = parent.own_recipes()
                if ptrs:
                    break
                else:
                    parent = parent.parent
        if ptrs:
            if parent:
                inheritance = RecipeInheritance(parent, self)
        return ptrs, inheritance

    def main_producing_process_type_relationship(self, stage=None, state=None):
        #pr changed
        ptrts, inheritance = self.own_or_parent_recipes()
        if stage or state:
            ptrts = ptrts.filter(stage=stage, state=state)
        if ptrts:
            one_ptrt = ptrts[0]
            if stage or state:
                return one_ptrt, inheritance
            else:
                if one_ptrt.stage:
                    stages, inheritance = self.staged_commitment_type_sequence()
                    if stages:
                        one_ptrt = stages[-1]
                    else:
                        return None, None
                return one_ptrt, inheritance
        else:
            return None, None

    def recipe_is_staged(self):
        #todo pr: shd this use own_or_parent_recipes?
        #staged_commitments = self.process_types.filter(stage__isnull=False)
        #pr changed
        ptrts, inheritance = self.own_or_parent_recipes()
        stages = [ct for ct in ptrts if ct.stage]
        if stages:
            return True
        else:
            return False

    def producing_process_types(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return [pt.process_type for pt in self.producing_process_type_relationships()]

    def main_producing_process_type(self, stage=None, state=None):
        #todo pr: shd this return inheritance, too?
        ptrt, inheritance = self.main_producing_process_type_relationship(stage, state)
        if ptrt:
            return ptrt.process_type
        else:
            return None

    def all_staged_commitment_types(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.filter(stage__isnull=False)

    def all_staged_process_types(self):
        cts = self.all_staged_commitment_types()
        pts = [ct.process_type for ct in cts]
        return list(set(pts))

    def all_stages(self):
        ids = [pt.id for pt in self.all_staged_process_types()]
        return ProcessType.objects.filter(id__in=ids)

    def staged_commitment_type_sequence(self):
        #pr changed
        staged_commitments = self.process_types.filter(stage__isnull=False)
        parent = None
        inheritance = None
        if not staged_commitments:
            parent = self.parent
            while parent:
                staged_commitments = parent.process_types.filter(stage__isnull=False)
                if staged_commitments:
                    break
                else:
                    parent = parent.parent
        if not staged_commitments:
            return [], None
        creation_et = EventType.objects.get(name='Create Changeable')
        chain = []
        creation = None
        try:
            if parent:
                inheritance = RecipeInheritance(parent, self)
                creation = parent.process_types.get(
                    stage__isnull=False,
                    event_type=creation_et)
            else:
                #bug: this code failed when it got more than one result
                #see https://github.com/valnet/valuenetwork/issues/403
                creation = self.process_types.get(
                    stage__isnull=False,
                    event_type=creation_et)
        except ProcessTypeResourceType.DoesNotExist:
            try:
                if parent:
                    creation = parent.process_types.get(
                        stage__isnull=True)
                else:
                    creation = self.process_types.get(
                        stage__isnull=True)
            except ProcessTypeResourceType.DoesNotExist:
                pass
        if creation:
            creation.follow_stage_chain(chain)
        else:
            if staged_commitments:
                creation = staged_commitments[0]
                creation.follow_stage_chain(chain)
        return chain, inheritance

    def staged_commitment_type_sequence_beyond_workflow(self):
        #pr changed
        staged_commitments = self.process_types.filter(stage__isnull=False)
        parent = None
        inheritance = None
        if not staged_commitments:
            parent = self.parent
            while parent:
                staged_commitments = parent.process_types.filter(stage__isnull=False)
                if staged_commitments:
                    break
                else:
                    parent = parent.parent
        if not staged_commitments:
            return [], None
        creation_et = EventType.objects.get(name='Create Changeable')
        chain = []
        creation = None
        try:
            if parent:
                inheritance = RecipeInheritance(parent, self)
                creation = parent.process_types.get(
                    stage__isnull=False,
                    event_type=creation_et)
            else:
                creation = self.process_types.get(
                    stage__isnull=False,
                    event_type=creation_et)
        except ProcessTypeResourceType.DoesNotExist:
            try:
                if parent:
                    creation = parent.process_types.get(
                        stage__isnull=True)
                else:
                    creation = self.process_types.get(
                        stage__isnull=True)
            except ProcessTypeResourceType.DoesNotExist:
                pass
        if creation:
            creation.follow_stage_chain_beyond_workflow(chain)
        else:
            if staged_commitments:
                creation = staged_commitments[0]
                creation.follow_stage_chain(chain)
        return chain, inheritance

    def staged_process_type_sequence(self):
        #pr changed
        pts = []
        stages, inheritance = self.staged_commitment_type_sequence()
        for stage in stages:
            if stage.process_type not in pts:
                pts.append(stage.process_type)
        return pts, inheritance

    def all_stages(self):
        pts, inheritance = self.staged_process_type_sequence()
        ids = [pt.id for pt in pts]
        return ProcessType.objects.filter(id__in=ids)

    def staged_process_type_sequence_beyond_workflow(self):
        #pr changed
        pts = []
        stages, inheritance = self.staged_commitment_type_sequence_beyond_workflow()
        for stage in stages:
            if stage.process_type not in pts:
                pts.append(stage.process_type)
        return pts, inheritance

    def recipe_needs_starting_resource(self):
        #todo pr: shd this pass inheritance on?
        #shd recipe_is_staged consider own_or_parent_recipes?
        if not self.recipe_is_staged():
            return False
        seq, inheritance = self.staged_commitment_type_sequence()
        answer = False
        if seq:
            ct0 = seq[0]
            if ct0.event_type.name == 'To Be Changed':
                answer =  True
        return answer

    def has_listable_recipe(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        answer = False
        ctype, inheritance = self.own_or_parent_recipes()
        if ctype:
            answer = True
            if self.recipe_needs_starting_resource():
                answer = False
        return answer

    def can_be_parent(self):
        if self.own_recipes():
            #if self.recipe_is_staged():
            return True
        return False

    def generate_mfg_work_order(self, order_name, due_date, created_by):
        #made from code in view plan_from_recipe but simplified to minimum requirement
        today = datetime.date.today()
        due = datetime.datetime.strptime(due_date, '%Y-%m-%d').date()
        demand = Order(
            order_type="rand",
            order_date=today,
            due_date=due,
            name=order_name,
            created_by=created_by)
        demand.save()

        ptrt, inheritance = self.main_producing_process_type_relationship()
        et = ptrt.event_type
        if et:
            commitment = demand.add_commitment(
                resource_type=self,
                #Todo: apply selected_context_agent here? Only if inheritance?
                context_agent=ptrt.process_type.context_agent,
                quantity=ptrt.quantity,
                event_type=et,
                unit=self.unit,
                description=ptrt.description or "",
                stage=ptrt.stage,
                state=ptrt.state,
                due=demand.due_date,
                )
            commitment.created_by=created_by
            commitment.save()

            process = commitment.generate_producing_process(created_by, [], inheritance=inheritance, explode=True)

        #TODO: add notifications here if wanted, see view

        return demand


    def generate_staged_work_order(self, order_name, start_date, user):
        #pr changed
        pts, inheritance = self.staged_process_type_sequence()
        order = Order(
            order_type="rand",
            name=order_name,
            order_date=datetime.date.today(),
            due_date=start_date,
            created_by=user)
        order.save()
        processes = []
        new_start_date = start_date
        for pt in pts:
            p = pt.create_process(new_start_date, user, inheritance, order)
            new_start_date = p.end_date
            processes.append(p)
        if processes:
            last_process = processes[-1]
            octs = last_process.outgoing_commitments()
            order_item = None
            for ct in octs:
                ct.order = order
                if not order_name:
                    order_name = " ".join([order_name, ct.resource_type.name])
                    order.name = order_name
                ct.save()
            assert octs.count() == 1, 'generate_staged_work_order assumes one and only output'
            order_item = octs[0]
            order.due_date = last_process.end_date
            order.save()
        #Todo: apply selected_context_agent here
        for process in processes:
            for ct in process.commitments.all():
                ct.independent_demand = order
                ct.order_item = order_item
                ct.save()
        return order

    def generate_staged_order_item(self, order, start_date, user):
        #pr changed
        pts, inheritance = self.staged_process_type_sequence()
        processes = []
        new_start_date = start_date
        for pt in pts:
            p = pt.create_process(new_start_date, user, order=order)
            new_start_date = p.end_date
            processes.append(p)
        if processes:
            last_process = processes[-1]
            octs = last_process.outgoing_commitments()
            order_item = None
            for ct in octs:
                ct.order = order
                ct.save()
            assert octs.count() == 1, 'generate_staged_order_item assumes one and only one output'
            order_item = octs[0]
            if order.due_date < last_process.end_date:
                order.due_date = last_process.end_date
                order.save()
        #Todo: apply selected_context_agent here
        for process in processes:
            for ct in process.commitments.all():
                ct.independent_demand = order
                ct.order_item = order_item
                ct.save()
        return order

    def generate_staged_work_order_from_resource(self, resource, order_name, start_date, user):
        if not start_date: # fix tests error
            start_date = datetime.date.today()
        #pr changed
        pts, inheritance = self.staged_process_type_sequence()
        order = Order(
            order_type="rand",
            name=order_name,
            order_date=datetime.date.today(),
            due_date=start_date,
            created_by=user)
        order.save()
        processes = []
        new_start_date = start_date
        for pt in pts:
            p = pt.create_process(new_start_date, user, inheritance, order)
            new_start_date = p.end_date
            processes.append(p)
        if processes:
            last_process = processes[-1]
            octs = last_process.outgoing_commitments()
            order_item = None
            for ct in octs:
                order_qty = ct.quantity
                ct.order = order
                if not order_name:
                    order_name = " ".join([order_name, ct.resource_type.name])
                    order.name = order_name
                ct.save()
            assert octs.count() == 1, 'generate_staged_work_order_from_resource assumes one and only one output'
            order_item = octs[0]
            order.due_date = last_process.end_date
            order.save()
            #pr changed
            if not resource.resource_type.substitutable:
                resource.independent_demand = order
                resource.order_item = order_item
                resource.save()
        #Todo: apply selected_context_agent here
        for process in processes:
            for commitment in process.commitments.all():
                commitment.independent_demand = order
                commitment.order_item = order_item
                if commitment.resource_type == self:
                    commitment.quantity = resource.quantity
                elif commitment.is_work():
                    if commitment.quantity == order_qty and commitment.unit_of_quantity == self.unit:
                        commitment.quantity = resource.quantity
                commitment.save()

        return order

    def is_process_output(self):
        #todo: does this still return false positives?
        #todo pr: cd this be shortcut but looking at recipes first?
        #todo pr: shd this be own or own_or_parent_recipes?
        fvs = self.facets.all()
        for fv in fvs:
            pfvs = fv.facet_value.patterns.filter(
                event_type__related_to="process",
                event_type__relationship="out")
            if pfvs:
                for pf in pfvs:
                    pattern = pf.pattern
                    if self in pattern.output_resource_types():
                        return True
        return False

    #does not seem to be used
    def is_purchased(self):
        rts = all_purchased_resource_types()
        return self in rts

    def consuming_process_type_relationships(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.filter(event_type__resource_effect='-')

    def citing_process_type_relationships(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.filter(event_type__relationship='cite')

    def wanting_process_type_relationships(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.exclude(event_type__relationship='out')

    def wanting_commitments(self):
        return self.commitments.filter(
            finished=False).exclude(event_type__relationship='out')

    def wanting_processes(self):
        processes = [c.process for c in self.wanting_commitments() if c.process]
        events = self.events.filter(quantity__gt=0).exclude(event_type__relationship='out')
        processes.extend([e.process for e in events if e.process])
        return list(set(processes))

    def consuming_commitments(self):
        return self.commitments.filter(
            finished=False, event_type__resource_effect='-')

    def consuming_commitments_for_stage(self, stage):
        return self.commitments.filter(
            finished=False,
            stage=stage,
            event_type__resource_effect='>~')

    def wanting_process_type_relationships(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.exclude(event_type__relationship='out')

    def wanting_process_type_relationships_for_stage(self, stage):
        #todo pr: shd this be own or own_or_parent_recipes?
        return self.process_types.exclude(event_type__relationship='out').filter(stage=stage)

    def wanting_process_types(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return [pt.process_type for pt in self.wanting_process_type_relationships()]

    def consuming_process_types(self):
        #todo pr: shd this be own or own_or_parent_recipes?
        return [pt.process_type for pt in self.consuming_process_type_relationships()]

    def producing_agent_relationships(self):
        return self.agents.filter(event_type__relationship='out')

    def work_agent_relationships(self):
        return self.agents.filter(event_type__relationship='work')

    def consuming_agent_relationships(self):
        return self.agents.filter(event_type__relationship='in')

    def consuming_agents(self):
        return [art.agent for art in self.consuming_agent_relationships()]

    def producing_agents(self):
        return [art.agent for art in self.producing_agent_relationships()]

    def work_agents(self):
        return [art.agent for art in self.work_agent_relationships()]

    def producer_relationships(self):
        return self.agents.filter(event_type__relationship='out')

    def producers(self):
        arts = self.producer_relationships()
        return [art.agent for art in arts]

    #todo: failures do not have commitments. If and when they do, the next two methods must change.
    #flow todo: workflow items will have more than one of these
    def producing_commitments(self):
        return self.commitments.filter(
            Q(event_type__relationship='out')|
            Q(event_type__name='Receipt'))

    def active_producing_commitments(self):
        producing_commitments = self.producing_commitments()
        return producing_commitments.filter(process__finished=False)

    def consuming_commitments(self):
        return self.commitments.filter(
            event_type__relationship='consume')

    def citing_commitments(self):
        return self.commitments.filter(
            event_type__relationship='cite')

    def scheduled_qty(self):
        return sum(pc.quantity for pc in self.producing_commitments())

    def xbill_parents(self):
        answer = list(self.wanting_process_type_relationships())
        answer.extend(list(self.options.all()))
        #answer.append(self)
        return answer

    def xbill_children(self):
        answer = []
        #todo pr: this shd be own_recipes
        answer.extend(self.manufacturing_producing_process_type_relationships())
        #answer.extend(self.producer_relationships())
        return answer

    def xbill_child_object(self):
        return self

    def xbill_class(self):
        return "economic-resource-type"

    def xbill_parent_object(self):
        return self

    def xbill_explanation(self):
        return "Resource Type"

    def xbill_label(self):
        return ""

    def generate_xbill(self):
        from valuenetwork.valueaccounting.utils import explode_xbill_children, xbill_dfs, annotate_tree_properties
        nodes = []
        exploded = []
        for kid in self.xbill_children():
            explode_xbill_children(kid, nodes, exploded)
        nodes = list(set(nodes))
        to_return = []
        visited = []
        for kid in self.xbill_children():
            to_return.extend(xbill_dfs(kid, nodes, visited, 1))
        annotate_tree_properties(to_return)
        return to_return

    def change_form(self):
        #todo pr: self shd be excluded from parents
        from valuenetwork.valueaccounting.forms import EconomicResourceTypeChangeForm
        return EconomicResourceTypeChangeForm(instance=self)

    def resource_create_form(self, prefix):
        from valuenetwork.valueaccounting.forms import EconomicResourceForm
        init = {"unit_of_quantity": self.unit,}
        return EconomicResourceForm(prefix=prefix, initial=init)

    def process_create_prefix(self):
        return "".join(["PC", str(self.id)])

    def process_create_form(self):
        from valuenetwork.valueaccounting.forms import XbillProcessTypeForm
        init = {"name": " ".join(["Make", self.name])}
        return XbillProcessTypeForm(initial=init, prefix=self.process_create_prefix())
        #return XbillProcessTypeForm(prefix=self.process_create_prefix())

    def process_stream_create_form(self):
        from valuenetwork.valueaccounting.forms import RecipeProcessTypeForm
        #init = {"name": " ".join(["Make", self.name])}
        #return RecipeProcessTypeForm(initial=init, prefix=self.process_create_prefix())
        return RecipeProcessTypeForm(prefix=self.process_create_prefix())

    def source_create_prefix(self):
        return "".join(["SRC", str(self.id)])

    def source_create_form(self):
        from valuenetwork.valueaccounting.forms import AgentResourceTypeForm
        return AgentResourceTypeForm(prefix=self.source_create_prefix())

    def form_prefix(self):
        return "".join(["RT", str(self.id)])

    def directional_unit(self, direction):
        answer = self.unit
        if self.unit_of_use:
            if direction == "use" or direction == "cite":
                answer = self.unit_of_use
        return answer

    def unit_for_use(self):
        return self.directional_unit("use")

    def process_output_unit(self):
        return self.unit

    def is_deletable(self):
        answer = True
        if self.events.all():
            answer = False
        elif self.resources.all():
            answer = False
        elif self.commitments.all():
            answer = False
        return answer

    def is_orphan(self):
        answer = True
        if not self.is_deletable():
            answer = False
        if self.process_types.all():
            answer = False
        return answer

    def work_without_value(self):
        work = self.events.filter(event_type__relationship="work")
        if work:
            if not self.value_per_unit:
                return True
        return False

    def facet_list(self):
        return ", ".join([facet.facet_value.__str__() for facet in self.facets.all()])

    def facet_values_list(self):
        return ", ".join([facet.facet_value.value for facet in self.facets.all()])

    def has_facet_value(self, facet_value):
        answer = False
        for rt_fv in self.facets.all():
            if rt_fv.facet_value == facet_value:
                answer = True
                break
        return answer

    def matches_filter(self, facet_values):
        answer = True
        incoming_facets = []
        for fv in facet_values:
            incoming_facets.append(fv.facet)
        filter_facets = set(incoming_facets)
        filter_facet_value_collections = []
        for f in filter_facets:
            fv_collection = []
            for fv in facet_values:
                if fv.facet == f:
                    fv_collection.append(fv)
            filter_facet_value_collections.append(fv_collection)
        filter_matches = []
        for (i, fac) in enumerate(filter_facets):
            fm = False
            for fv in filter_facet_value_collections[i]:
                if self.has_facet_value(fv):
                    fm = True
                    break
            filter_matches.append(fm)
        if False in filter_matches:
            answer = False
        return answer

    def uninventoried(self):
        if self.inventory_rule == "yes":
            return False
        else:
            return True


class ResourceTypeList(models.Model):
    name = models.CharField(_('name'), max_length=128)
    description = models.TextField(_('description'), blank=True, null=True)
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='lists')

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def resource_types_string(self):
        return ", ".join([elem.resource_type.name for elem in self.list_elements.all()])

    def form_prefix(self):
        return "-".join(["RTL", str(self.id)])

    def change_form(self):
        from valuenetwork.valueaccounting.forms import ResourceTypeListForm
        prefix=self.form_prefix()
        rt_ids = [elem.resource_type.id for elem in self.resource_types.all()]
        init = {"resource_types": rt_ids,}
        return ResourceTypeListForm(instance=self, prefix=prefix, initial=init)

    def recipe_class(self):
        answer = "workflow"
        for elem in self.list_elements.all():
            if not elem.resource_type.recipe_is_staged():
                answer = "manufacturing"
        return answer


class ResourceTypeListElement(models.Model):
    resource_type_list = models.ForeignKey(ResourceTypeList,
        verbose_name=_('resource type list'), related_name='list_elements', on_delete=models.CASCADE)
    resource_type = models.ForeignKey(EconomicResourceType,
        verbose_name=_('resource type'), related_name='lists', on_delete=models.CASCADE)
    default_quantity = models.DecimalField(_('default quantity'), max_digits=8, decimal_places=2,
        default=Decimal("1.0"))

    class Meta:
        unique_together = ('resource_type_list', 'resource_type')
        ordering = ('resource_type_list', 'resource_type')

    def __str__(self):
        return ": ".join([self.resource_type_list.name, self.resource_type.name])


class ResourceTypeFacetValue(models.Model):
    resource_type = models.ForeignKey(EconomicResourceType,
        verbose_name=_('resource type'), related_name='facets', on_delete=models.CASCADE)
    facet_value = models.ForeignKey(FacetValue,
        verbose_name=_('facet value'), related_name='resource_types', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('resource_type', 'facet_value')
        ordering = ('resource_type', 'facet_value')

    def __str__(self):
        return ": ".join([self.resource_type.name, self.facet_value.facet.name, self.facet_value.value])


def all_purchased_resource_types():
    uc = UseCase.objects.get(name="Purchasing")
    pats = ProcessPattern.objects.usecase_patterns(uc)
    #todo exchange redesign fallout
    #et = EventType.objects.get(name="Receipt")
    et = EventType.objects.get(name="Receive")
    rts = []
    for pat in pats:
        rts.extend(pat.get_resource_types(et))
    return rts


class ProcessPatternManager(models.Manager):

    def production_patterns(self):
        use_cases = PatternUseCase.objects.filter(
            Q(use_case__identifier='rand')|Q(use_case__identifier='design')|Q(use_case__identifier='recipe'))
        pattern_ids = [uc.pattern.id for uc in use_cases]
        return ProcessPattern.objects.filter(id__in=pattern_ids)

    def recipe_patterns(self):
        use_cases = PatternUseCase.objects.filter(use_case__identifier='recipe')
        pattern_ids = [uc.pattern.id for uc in use_cases]
        return ProcessPattern.objects.filter(id__in=pattern_ids)

    def usecase_patterns(self, use_case):
        use_cases = PatternUseCase.objects.filter(
            Q(use_case=use_case))
        pattern_ids = [uc.pattern.id for uc in use_cases]
        return ProcessPattern.objects.filter(id__in=pattern_ids)

    def all_production_resource_types(self):
        patterns = self.production_patterns()
        rt_ids = []
        for pat in patterns:
            #todo pr: shd this be own or own_or_parent_recipes?
            rt_ids.extend([rt.id for rt in pat.output_resource_types() if rt.producing_process_type_relationships()])
        return EconomicResourceType.objects.filter(id__in=rt_ids)


class ProcessPattern(models.Model):
    name = models.CharField(_('name'), max_length=32)

    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='process_patterns')

    objects = ProcessPatternManager()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def event_types(self):
        facets = self.facets.all()
        slots = [facet.event_type for facet in facets]
        slots = list(set(slots))
        #slots.sort(key=lambda x: x.label)
        #slots = sorted(slots, key=attrgetter('label'))
        #slots = sorted(slots, key=attrgetter('relationship'), reverse=True)
        slots = sorted(slots, key=attrgetter('name'))
        return slots

    def slots(self):
        return [et.relationship for et in self.event_types()]

    def change_event_types(self):
        return [et for et in self.event_types() if et.is_change_related()]

    def non_change_event_type_names(self):
        return [et.name for et in self.event_types() if not et.is_change_related()]

    def get_resource_types(self, event_type):
        """Matching logic:

            A Resource Type must have a matching value
            for each Facet in the Pattern.
            If a Pattern has more than one value for the same Facet,
            the Resource Type only needs to match one of them.
            And if the Resource Type has other Facets
            that are not in the Pattern, they do not matter.
        """

        pattern_facet_values = self.facets_for_event_type(event_type)
        facet_values = [pfv.facet_value for pfv in pattern_facet_values]
        facets = {}
        for fv in facet_values:
            if fv.facet not in facets:
                facets[fv.facet] = []
            facets[fv.facet].append(fv.value)

        fv_ids = [fv.id for fv in facet_values]
        rt_facet_values = ResourceTypeFacetValue.objects.filter(facet_value__id__in=fv_ids)

        rts = {}
        for rtfv in rt_facet_values:
            rt = rtfv.resource_type
            if rt not in rts:
                rts[rt] = []
            rts[rt].append(rtfv.facet_value)

        matches = []

        for rt, facet_values in list(rts.items()):
            match = True
            for facet, values in list(facets.items()):
                rt_fv = [fv for fv in facet_values if fv.facet == facet]
                if rt_fv:
                    rt_fv = rt_fv[0]
                    if rt_fv.value not in values:
                        match = False
                else:
                    match = False
            if match:
                matches.append(rt)

        answer_ids = [a.id for a in matches]
        answer = EconomicResourceType.objects.filter(id__in=answer_ids)
        return answer

    def resource_types_for_relationship(self, relationship):
        ets = [f.event_type for f in self.facets.filter(event_type__relationship=relationship)]
        if ets:
            ets = list(set(ets))
            if len(ets) == 1:
                return self.get_resource_types(ets[0])
            else:
                rts = []
                for et in ets:
                    rts.extend(list(self.get_resource_types(et)))
                rt_ids = [rt.id for rt in rts]
                return EconomicResourceType.objects.filter(id__in=rt_ids)
        else:
            return EconomicResourceType.objects.none()

    def all_resource_types(self):
        rts = []
        ets = self.event_types()
        for et in ets:
            rts.extend(self.get_resource_types(et))
        rt_ids = [rt.id for rt in rts]
        return EconomicResourceType.objects.filter(id__in=rt_ids)

    def work_resource_types(self):
        return self.resource_types_for_relationship("work")

    def todo_resource_types(self):
        return self.resource_types_for_relationship("todo")

    def citable_resource_types(self):
        return self.resource_types_for_relationship("cite")

    def citables_with_resources(self):
        rts = [rt for rt in self.citable_resource_types() if rt.onhand()]
        rt_ids = [rt.id for rt in rts]
        return EconomicResourceType.objects.filter(id__in=rt_ids)

    def citable_resources(self):
        rts = [rt for rt in self.citable_resource_types() if rt.onhand()]
        return EconomicResource.objects.filter(resource_type__in=rts)

    def input_resource_types(self):
        #TODO must be changed, in no longer covers
        # or event types must be changed so all ins are ins
        #return self.resource_types_for_relationship("in")
        answer = list(self.resource_types_for_relationship("in"))
        answer.extend(list(self.resource_types_for_relationship("consume")))
        answer.extend(list(self.resource_types_for_relationship("use")))
        return answer

    def consumable_resource_types(self):
        return self.resource_types_for_relationship("consume")

    def consumables_with_resources(self):
        rts = [rt for rt in self.consumable_resource_types() if rt.onhand()]
        rt_ids = [rt.id for rt in rts]
        return EconomicResourceType.objects.filter(id__in=rt_ids)

    def usable_resource_types(self):
        return self.resource_types_for_relationship("use")

    def usables_with_resources(self):
        rts = [rt for rt in self.usable_resource_types() if rt.onhand()]
        rt_ids = [rt.id for rt in rts]
        return EconomicResourceType.objects.filter(id__in=rt_ids)

    def output_resource_types(self):
        return self.resource_types_for_relationship("out")

    #def payment_resource_types(self):
    #    return self.resource_types_for_relationship("pay")

    #def receipt_resource_types(self):
    #    return self.resource_types_for_relationship("receive")

    #def receipt_resource_types_with_resources(self):
    #    rts = [rt for rt in self.resource_types_for_relationship("receive") if rt.all_resources()] # if rt.onhand()]
    #    rt_ids = [rt.id for rt in rts]
    #    return EconomicResourceType.objects.filter(id__in=rt_ids)

    #def matl_contr_resource_types_with_resources(self):
    #    rts = [rt for rt in self.resource_types_for_relationship("resource") if rt.onhand()]
    #    rt_ids = [rt.id for rt in rts]
    #    return EconomicResourceType.objects.filter(id__in=rt_ids)

    #def expense_resource_types(self):
    #    return self.resource_types_for_relationship("expense")

    #def process_expense_resource_types(self):
    #    return self.resource_types_for_relationship("payexpense")

    #def cash_contr_resource_types(self): #now includes cash contributions and donations
    #    return self.resource_types_for_relationship("cash")

    #def shipment_resource_types(self):
    #    return self.resource_types_for_relationship("shipment")

    #def shipment_uninventoried_resource_types(self):
    #    rts = [rt for rt in self.resource_types_for_relationship("shipment") if rt.uninventoried()]
    #    rt_ids = [rt.id for rt in rts]
    #    return EconomicResourceType.objects.filter(id__in=rt_ids)

    #def shipment_resources(self):
    #    rts = self.shipment_resource_types()
    #    resources = []
    #    for rt in rts:
    #        rt_resources = rt.all_resources()
    #        for res in rt_resources:
    #            resources.append(res)
    #    resource_ids = [res.id for res in resources]
    #    return EconomicResource.objects.filter(id__in=resource_ids).order_by("-created_date")

    #def material_contr_resource_types(self):
    #    return self.resource_types_for_relationship("resource")

    #def cash_receipt_resource_types(self):
    #    return self.resource_types_for_relationship("receivecash")

    def distribution_resource_types(self):
        return self.resource_types_for_relationship("distribute")

    def disbursement_resource_types(self):
        return self.resource_types_for_relationship("disburse")

    def facets_for_event_type(self, event_type):
        return self.facets.filter(event_type=event_type)

    def facet_values_for_relationship(self, relationship):
        return self.facets.filter(event_type__relationship=relationship)

    def output_facet_values(self):
        return self.facet_values_for_relationship("out")

    def citable_facet_values(self):
        return self.facet_values_for_relationship("cite")

    def input_facet_values(self):
        return self.facet_values_for_relationship("in")

    def consumable_facet_values(self):
        return self.facet_values_for_relationship("consume")

    def usable_facet_values(self):
        return self.facet_values_for_relationship("use")

    def work_facet_values(self):
        return self.facet_values_for_relationship("work")

    def input_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.input_facet_values()]
        return list(set(facets))

    def consumable_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.consumable_facet_values()]
        return list(set(facets))

    def usable_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.usable_facet_values()]
        return list(set(facets))

    def citable_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.citable_facet_values()]
        return list(set(facets))

    def work_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.work_facet_values()]
        return list(set(facets))

    def output_facets(self):
        facets = [pfv.facet_value.facet for pfv in self.output_facet_values()]
        return list(set(facets))

    def base_event_type_for_resource_type(self, relationship, resource_type):
        rt_fvs = [x.facet_value for x in resource_type.facets.all()]
        pfvs = self.facet_values_for_relationship(relationship)
        pat_fvs = [x.facet_value for x in pfvs]
        fv_intersect = set(rt_fvs) & set(pat_fvs)
        event_type = None
        #todo bug: this method can find more than one pfv
        if fv_intersect:
            fv = list(fv_intersect)[0]
            pfv = pfvs.get(facet_value=fv)
            event_type = pfv.event_type
        return event_type

    def event_type_for_resource_type(self, relationship, resource_type):
        event_type = self.base_event_type_for_resource_type(relationship, resource_type)
        if not event_type:
            ets = self.event_types()
            for et in ets:
                if et.relationship == relationship:
                    event_type=et
                    break
            if not event_type:
                ets = EventType.objects.filter(relationship=relationship)
                event_type = ets[0]
        return event_type

    def use_case_list(self):
        ucl = [uc.use_case.name for uc in self.use_cases.all()]
        return ", ".join(ucl)

    def use_case_identifier_list(self):
        ucl = [uc.use_case.identifier for uc in self.use_cases.all()]
        return ", ".join(ucl)

    def use_case_count(self):
        return self.use_cases.all().count()

    def facets_by_relationship(self, relationship):
        pfvs = self.facet_values_for_relationship(relationship)
        facets = [pfv.facet_value.facet for pfv in pfvs]
        return list(set(facets))

    def facet_values_for_facet_and_relationship(self, facet, relationship):
        fvs_all = self.facet_values_for_relationship(relationship)
        fvs_for_facet = []
        for fv in fvs_all:
            if fv.facet_value.facet == facet:
                fvs_for_facet.append(fv.facet_value)
        return fvs_for_facet


class PatternFacetValue(models.Model):
    pattern = models.ForeignKey(ProcessPattern, on_delete=models.CASCADE,
        verbose_name=_('pattern'), related_name='facets')
    facet_value = models.ForeignKey(FacetValue, on_delete=models.CASCADE,
        verbose_name=_('facet value'), related_name='patterns')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='patterns',
        help_text=_('consumed means gone, used means re-usable'))

    class Meta:
        unique_together = ('pattern', 'facet_value', 'event_type')
        ordering = ('pattern', 'event_type', 'facet_value')

    def __str__(self):
        return ": ".join([self.pattern.name, self.facet_value.facet.name, self.facet_value.value])


class UseCaseManager(models.Manager):

    def get_by_natural_key(self, identifier):
        return self.get(identifier=identifier)

    def exchange_use_cases(self):
        return UseCase.objects.filter(Q(identifier="supply_xfer")|Q(identifier="demand_xfer")|Q(identifier="intrnl_xfer"))

class UseCase(models.Model):
    identifier = models.CharField(_('identifier'), max_length=12)
    name = models.CharField(_('name'), max_length=128)
    restrict_to_one_pattern = models.BooleanField(_('restrict_to_one_pattern'), default=False)

    objects = UseCaseManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.identifier,)

    @classmethod
    def create(cls, identifier, name, restrict_to_one_pattern=False, verbosity=2):
        """
        Creates a new UseCase, updates an existing one, or does nothing.
        This is intended to be used as a post_syncdb manangement step.
        """
        try:
            use_case = cls._default_manager.get(identifier=identifier)
            updated = False
            if name != use_case.name:
                use_case.name = name
                updated = True
            if restrict_to_one_pattern != use_case.restrict_to_one_pattern:
                use_case.restrict_to_one_pattern = restrict_to_one_pattern
                updated = True
            if updated:
                use_case.save()
                if verbosity > 1:
                    print("Updated {} UseCase".format(identifier))
        except cls.DoesNotExist:
            cls(identifier=identifier, name=name, restrict_to_one_pattern=restrict_to_one_pattern).save()
            if verbosity > 1:
                print("Created {} UseCase".format(identifier))

    def allows_more_patterns(self):
        patterns_count = self.patterns.all().count()
        if patterns_count:
            if self.restrict_to_one_pattern:
                return False
        return True

    def allowed_event_types(self):
        ucets = UseCaseEventType.objects.filter(use_case=self)
        et_ids = []
        for ucet in ucets:
            if ucet.event_type.pk not in et_ids:
                et_ids.append(ucet.event_type.pk)
        return EventType.objects.filter(pk__in=et_ids)

    def allowed_patterns(self): #patterns must not have event types not assigned to the use case
        allowed_ets = self.allowed_event_types()
        all_ps = ProcessPattern.objects.all()
        allowed_ps = []
        for p in all_ps:
            allow_this_pattern = True
            for et in p.event_types():
                if et not in allowed_ets:
                    allow_this_pattern = False
            if allow_this_pattern:
                allowed_ps.append(p)
        return allowed_ps


#def create_use_cases(app, **kwargs):
#    if app != "valueaccounting":
#        return
def create_use_cases(**kwargs):
    #UseCase.create('cash_contr', _('Cash Contribution'), True)
    UseCase.create('non_prod', _('Non-production Logging'), True)
    UseCase.create('rand', _('Manufacturing Recipes/Logging'))
    UseCase.create('recipe', _('Workflow Recipes/Logging'))
    UseCase.create('todo', _('Todos'), True)
    UseCase.create('cust_orders', _('Customer Orders'))
    UseCase.create('purchasing', _('Purchasing'))
    #UseCase.create('res_contr', _('Material Contribution'))
    #UseCase.create('purch_contr', _('Purchase Contribution'))
    #UseCase.create('exp_contr', _('Expense Contribution'), True)
    #UseCase.create('sale', _('Sale'))
    UseCase.create('distribution', _('Distribution'), True)
    UseCase.create('val_equation', _('Value Equation'), True)
    UseCase.create('payout', _('Payout'), True)
    #UseCase.create('transfer', _('Transfer'))
    UseCase.create('available', _('Make Available'), True)
    UseCase.create('intrnl_xfer', _('Internal Exchange'))
    UseCase.create('supply_xfer', _('Incoming Exchange'))
    UseCase.create('demand_xfer', _('Outgoing Exchange'))
    print("created use cases")

#post_migrate.connect(create_use_cases, sender=ValueAccountingAppConfig)

#def create_event_types(app, **kwargs):
#    if app != "valueaccounting":
#        return
def create_event_types(**kwargs):
    #Keep the first column (name) as unique
    EventType.create('Citation', _('cites'), _('cited by'), 'cite', 'process', '=', '')
    EventType.create('Resource Consumption', _('consumes'), _('consumed by'), 'consume', 'process', '-', 'quantity')
    #EventType.create('Cash Contribution', _('contributes cash'), _('cash contributed by'), 'cash', 'exchange', '+', 'value')
    #EventType.create('Donation', _('donates cash'), _('cash donated by'), 'cash', 'exchange', '+', 'value')
    #EventType.create('Resource Contribution', _('contributes resource'), _('resource contributed by'), 'resource', 'exchange', '+', 'quantity')
    EventType.create('Damage', _('damages'), _('damaged by'), 'out', 'agent', '-', 'value')
    #EventType.create('Expense', _('expense'), '', 'expense', 'exchange', '=', 'value')
    EventType.create('Failed quantity', _('fails'), '', 'out', 'process', '<', 'quantity')
    #EventType.create('Payment', _('pays'), _('paid by'), 'pay', 'exchange', '-', 'value')
    EventType.create('Resource Production', _('produces'), _('produced by'), 'out', 'process', '+', 'quantity')
    EventType.create('Work Provision', _('provides'), _('provided by'), 'out', 'agent', '+', 'time')
    #EventType.create('Receipt', _('receives'), _('received by'), 'receive', 'exchange', '+', 'quantity')
    EventType.create('Sale', _('sells'), _('sold by'), 'out', 'agent', '=', '')
    #EventType.create('Shipment', _('ships'), _('shipped by'), 'shipment', 'exchange', '-', 'quantity')
    EventType.create('Supply', _('supplies'), _('supplied by'), 'out', 'agent', '=', '')
    EventType.create('Todo', _('todo'), '', 'todo', 'agent', '=', '')
    EventType.create('Resource use', _('uses'), _('used by'), 'use', 'process', '=', 'time')
    EventType.create('Time Contribution', _('work'), '', 'work', 'process', '=', 'time')
    EventType.create('Create Changeable', _('creates changeable'), 'changeable created', 'out', 'process', '+~', 'quantity')
    EventType.create('To Be Changed', _('to be changed'), '', 'in', 'process', '>~', 'quantity')
    EventType.create('Change', _('changes'), 'changed', 'out', 'process', '~>', 'quantity')
    EventType.create('Adjust Quantity', _('adjusts'), 'adjusted', 'adjust', 'agent', '+-', 'quantity')
    #EventType.create('Cash Receipt', _('receives cash'), _('cash received by'), 'receivecash', 'exchange', '+', 'value')
    EventType.create('Distribution', _('distributes'), _('distributed by'), 'distribute', 'distribution', '+', 'value')
    EventType.create('Cash Disbursement', _('disburses cash'), _('disbursed by'), 'disburse', 'distribution', '-', 'value')
    EventType.create('Payout', _('pays out'), _('paid by'), 'payout', 'agent', '-', 'value')
    #EventType.create('Loan', _('loans'), _('loaned by'), 'cash', 'exchange', '+', 'value')
    #EventType.create('Transfer', _('transfers'), _('transfered by'), 'transfer', 'exchange', '=', 'quantity')
    #EventType.create('Reciprocal Transfer', _('reciprocal transfers'), _('transfered by'), 'transfer', 'exchange', '=', 'quantity')
    #EventType.create('Fee', _('fees'), _('charged by'), 'fee', 'exchange', '-', 'value')
    EventType.create('Give', _('gives'), _('given by'), 'give', 'transfer', '-', 'quantity')
    EventType.create('Receive', _('receives'), _('received by'), 'receive', 'exchange', '+', 'quantity')
    #EventType.create('Make Available', _('makes available'), _('made available by'), 'available', 'agent', '+', 'quantity')

    print("created event types")

#post_migrate.connect(create_event_types, sender=ValueAccountingAppConfig)

class UseCaseEventType(models.Model):
    use_case = models.ForeignKey(UseCase, on_delete=models.CASCADE,
        verbose_name=_('use case'), related_name='event_types')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='use_cases')

    def __str__(self):
        return ": ".join([self.use_case.name, self.event_type.name])

    @classmethod
    def create(cls, use_case_identifier, event_type_name):
        """
        Creates a new UseCaseEventType, updates an existing one, or does nothing.
        This is intended to be used as a post_syncdb manangement step.
        """
        try:
            use_case = UseCase.objects.get(identifier=use_case_identifier)
            event_type = EventType.objects.get(name=event_type_name)
            ucet = cls._default_manager.get(use_case=use_case, event_type=event_type)
        except cls.DoesNotExist:
            cls(use_case=use_case, event_type=event_type).save()
            print("Created {} UseCaseEventType".format(use_case_identifier + " " + event_type_name))

#def create_usecase_eventtypes(app, **kwargs):
#    if app != "valueaccounting":
#        return
def create_usecase_eventtypes(**kwargs):
    #UseCaseEventType.create('cash_contr', 'Time Contribution')
    #UseCaseEventType.create('cash_contr', 'Cash Contribution')
    #UseCaseEventType.create('cash_contr', 'Donation')
    UseCaseEventType.create('non_prod', 'Time Contribution')
    UseCaseEventType.create('rand', 'Citation')
    UseCaseEventType.create('rand', 'Resource Consumption')
    UseCaseEventType.create('rand', 'Resource Production')
    UseCaseEventType.create('rand', 'Resource use')
    UseCaseEventType.create('rand', 'Time Contribution')
    UseCaseEventType.create('rand', 'To Be Changed')
    UseCaseEventType.create('rand', 'Change')
    UseCaseEventType.create('rand', 'Create Changeable')
    #UseCaseEventType.create('rand', 'Process Expense')
    #todo: 'rand' now = mfg/assembly, 'recipe' now = workflow.  Need to rename these use cases.
    UseCaseEventType.create('recipe','Citation')
    UseCaseEventType.create('recipe', 'Resource Consumption')
    UseCaseEventType.create('recipe', 'Resource Production')
    UseCaseEventType.create('recipe', 'Resource use')
    UseCaseEventType.create('recipe', 'Time Contribution')
    UseCaseEventType.create('recipe', 'To Be Changed')
    UseCaseEventType.create('recipe', 'Change')
    UseCaseEventType.create('recipe', 'Create Changeable')
    #UseCaseEventType.create('recipe', 'Process Expense')
    UseCaseEventType.create('todo', 'Todo')
    #UseCaseEventType.create('cust_orders', 'Damage')
    #UseCaseEventType.create('cust_orders', 'Transfer')
    #UseCaseEventType.create('cust_orders', 'Reciprocal Transfer')
    #UseCaseEventType.create('cust_orders', 'Payment')
    #UseCaseEventType.create('cust_orders', 'Receipt')
    #UseCaseEventType.create('cust_orders', 'Sale')
    #UseCaseEventType.create('cust_orders', 'Shipment')
    #UseCaseEventType.create('purchasing', 'Payment')
    #UseCaseEventType.create('purchasing', 'Receipt')
    #UseCaseEventType.create('res_contr', 'Time Contribution')
    #UseCaseEventType.create('res_contr', 'Resource Contribution')
    #UseCaseEventType.create('purch_contr', 'Time Contribution')
    #UseCaseEventType.create('purch_contr', 'Expense')
    #UseCaseEventType.create('purch_contr', 'Payment')
    #UseCaseEventType.create('purch_contr', 'Receipt')
    #UseCaseEventType.create('exp_contr', 'Time Contribution')
    #UseCaseEventType.create('exp_contr', 'Expense')
    #UseCaseEventType.create('exp_contr', 'Payment')
    #UseCaseEventType.create('sale', 'Shipment')
    #UseCaseEventType.create('sale', 'Cash Receipt')
    #UseCaseEventType.create('sale', 'Time Contribution')
    UseCaseEventType.create('distribution', 'Distribution')
    UseCaseEventType.create('distribution', 'Time Contribution')
    UseCaseEventType.create('distribution', 'Cash Disbursement')
    UseCaseEventType.create('val_equation', 'Time Contribution')
    UseCaseEventType.create('val_equation', 'Resource Production')
    UseCaseEventType.create('payout', 'Payout')
    #UseCaseEventType.create('transfer', 'Transfer')
    #UseCaseEventType.create('transfer', 'Reciprocal Transfer')
    #UseCaseEventType.create('available', 'Make Available')
    #UseCaseEventType.create('intrnl_xfer', 'Transfer')
    #UseCaseEventType.create('intrnl_xfer', 'Reciprocal Transfer')
    #UseCaseEventType.create('intrnl_xfer', 'Time Contribution')
    #UseCaseEventType.create('supply_xfer', 'Transfer')
    #UseCaseEventType.create('supply_xfer', 'Reciprocal Transfer')
    #UseCaseEventType.create('supply_xfer', 'Time Contribution')
    #UseCaseEventType.create('demand_xfer', 'Transfer')
    #UseCaseEventType.create('demand_xfer', 'Reciprocal Transfer')
    #UseCaseEventType.create('demand_xfer', 'Time Contribution')

    print("created use case event type associations")

#post_migrate.connect(create_usecase_eventtypes, sender=ValueAccountingAppConfig)


class PatternUseCase(models.Model):
    pattern = models.ForeignKey(ProcessPattern,
        verbose_name=_('pattern'), related_name='use_cases', on_delete=models.CASCADE)
    use_case = models.ForeignKey(UseCase,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('use case'), related_name='patterns')

    def __str__(self):
        use_case_name = ""
        if self.use_case:
            use_case_name = self.use_case.name
        return ": ".join([self.pattern.name, use_case_name])


ORDER_TYPE_CHOICES = (
    ('customer', _('Customer order')),
    ('rand', _('Work order')),
    ('holder', _('Placeholder order')),
)

class OrderManager(models.Manager):

    def customer_orders(self):
        return Order.objects.filter(order_type="customer")

    def rand_orders(self):
        return Order.objects.filter(order_type="rand")

    def open_rand_orders(self):
        orders = self.rand_orders()
        open_orders = []
        for order in orders:
            if order.has_open_processes():
                open_orders.append(order)
            if not order.unordered_processes():
                open_orders.append(order)
        return open_orders

    def closed_work_orders(self):
        orders = self.rand_orders()
        closed_orders = []
        for order in orders:
            if not order.has_open_processes():
                closed_orders.append(order)
        return closed_orders

#todo: Order is used for both of the above types.
#maybe shd be renamed?
class Order(models.Model):
    order_type = models.CharField(_('order type'), max_length=12,
        choices=ORDER_TYPE_CHOICES, default='customer')
    name = models.CharField(_('name'), max_length=255, blank=True,
        help_text=_("appended to process labels for Work orders"))
    receiver = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="purchase_orders", verbose_name=_('receiver'))
    provider = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="sales_orders", verbose_name=_('provider'))
    order_date = models.DateField(_('order date'), default=datetime.date.today)
    due_date = models.DateField(_('due date'))
    description = models.TextField(_('description'), null=True, blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='orders_created', blank=True, null=True, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='orders_changed', blank=True, null=True, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    objects = OrderManager()

    class Meta:
        ordering = ('due_date',)

    def __str__(self):
        provider_name = ""
        process_name = ""
        provider_label = ""
        receiver_label = ""
        process = self.process()
        if process:
            process_name = ", " + process.name
        if self.name:
            process_name = " ".join([" for", self.name])
        if self.provider:
            provider_name = self.provider.nick
            provider_label = ", provider:"
        receiver_name = ""
        if self.receiver:
            receiver_name = self.receiver.nick
            receiver_label = ", receiver:"
        if self.order_type == "customer":
            provider_label = ", Seller:"
            receiver_label = ", Buyer:"
        due_label = " due:"
        if provider_name or receiver_name:
            due_label = ", due:"
        return "".join(
            [self.get_order_type_display(),
            str(self.id),
            process_name,
            provider_label,
            provider_name,
            receiver_label,
            receiver_name,
            due_label,
            self.due_date.strftime('%Y-%m-%d'),
            ])

    def shorter_label_customer_order(self):
        receiver_label = ", buyer:"
        receiver_name = ""
        if self.receiver:
            receiver_name = self.receiver.name
        due_label = " on:"
        return " ".join(
            [self.get_order_type_display(),
            str(self.id),
            receiver_label,
            receiver_name,
            due_label,
            self.due_date.strftime('%Y-%m-%d'),
            ])

    def kanban_label(self):
        name = self.name
        if not name:
            process= self.naming_process()
            if process:
                name = process.name
            else:
                name = str(self.id)

        return "".join(
            [name,
            ", due: ",
            self.due_date.strftime('%Y-%m-%d'),
            ])

    def number_of_processes(self):
        procs = self.unordered_processes()
        return len(list(procs))

    def is_deletable(self):
        answer = True
        for proc in self.unordered_processes():
            if not proc.is_deletable():
                answer = False
                break
        if answer:
            ex = self.exchange()
            if ex:
                answer = ex.is_deletable()
        return answer

    def get_absolute_url(self):
        return reverse('order_schedule', {'order_id': str(self.id),})

    @property #ValueFlows
    def planned(self):
        return self.order_date.isoformat()

    @property #ValueFlows
    def due(self):
        return self.due_date.isoformat()

    @property #ValueFlows
    def note(self):
        return self.description

    @property #ValueFlows
    def plan_name(self):
        name = self.name
        if not name:
            procs = self.all_processes()
            if len(procs) > 0:
                name = procs[0].name
            if not name:
                name = str(self.id)
        return name

    @property #ValueFlows
    def created_by_agent(self):
        agent_user = AgentUser.objects.get(user=self.created_by)
        return agent_user.agent

    def delete_api(self):
        evs = self.all_events()
        if len(evs) == 0:
            trash = []
            pcs = self.producing_commitments()
            if pcs:
                for ct in pcs:
                    ct.delete_dependants()
                self.delete()
            else:
                commitments = Commitment.objects.filter(independent_demand=self)
                if commitments:
                    processes = []
                    for ct in commitments:
                        if ct.process:
                            if ct.process not in processes:
                                processes.append(ct.process)
                        #for event in ct.fulfillment_events.all():
                        #    event.commitment = None
                        #    event.save()
                        ct.delete()
                    for process in processes:
                        process.delete()
                self.delete()
        else:
            raise ValidationError("Cannot delete a plan with economic events recorded.")

    #def is_deletable(self):
    #    if self.all_events():
    #        return False
    #    return True

    #TODO this is a start at something, check if it is still useful
    #assumes the order itself is already saved (adapted from view plan_from_recipe)
    #def create_order_details_from_recipe_api(self, resource_type_id=None, rt_list_id=None, resource_id=None):
    #    resource_types = []
    #    resource_type_lists = []
    #    selected_context_agent = self.provider
    #    forward_schedule = False
    #    resource_driven = False
    #    today = datetime.date.today()

    #    if rt_list_id:
    #        rt_list = ResourceTypeList.objects.get(id=rt_list_id)
    #        if rt_list.recipe_class() == "workflow":
    #            forward_schedule = True
    #        rts_to_produce = [elem.resource_type for elem in rt_list.list_elements.all()]
    #        item_number = 1
    #    elif resource_type_id:
    #        produced_rt = EconomicResourceType.objects.get(id=resource_type_id)
    #        rts_to_produce = [produced_rt,]
    #        if produced_rt.recipe_is_staged():
    #            forward_schedule = True
    #            if produced_rt.recipe_needs_starting_resource():
    #                resource_driven = True
    #    elif resource_id:
    #        resource = EconomicResource.objects.get(id=resource_id)
    #        if resource.resource_type not in rts:
    #            rts.append(resource.resource_type)
    #    else:
    #        raise ValidationError("A resource classification or a resource classification bundle or a resource is required.")

    #    #???
    #    #if forward_schedule:
    #    #    if start_or_due == "start":
    #    #        start_date = due_date
    #    #    else:
    #    #        forward_schedule = False

    #    for produced_rt in rts_to_produce:
    #        if forward_schedule:
    #            if resource_driven:
    #                #demand = produced_rt.generate_staged_work_order_from_resource(resource, order_name, start_date, self.created_by)
    #                produced_rt.generate_staged_work_order_from_resource(resource, order_name, start_date, self.created_by)
    #            else:
    #                if len(rts_to_produce) == 1:
    #                    demand = produced_rt.generate_staged_work_order(order_name, start_date, self.created_by)
    #                else:
    #                    if item_number == 1:
    #                        item_number += 1
    #                        demand = produced_rt.generate_staged_work_order(order_name, start_date, self.created_by)
    #                    else:
    #                        demand = produced_rt.generate_staged_order_item(self, start_date, self.created_by)
    #        else:
    #            ptrt, inheritance = produced_rt.main_producing_process_type_relationship()
    #            et = ptrt.event_type
    #            if et:
    #                commitment = self.add_commitment(
    #                    resource_type=produced_rt,
    #                    #Todo: apply selected_context_agent here? Only if inheritance?
    #                    context_agent=ptrt.process_type.context_agent,
    #                    quantity=ptrt.quantity,
    #                    event_type=et,
    #                    unit=produced_rt.unit,
    #                    description=ptrt.description or "",
    #                    stage=ptrt.stage,
    #                    state=ptrt.state,
    #                    )
    #                commitment.created_by=self.created_by
    #                commitment.save()

    #                #Todo: apply selected_context_agent here? #???
    #                process = commitment.generate_producing_process(self.created_by, [], inheritance=inheritance, explode=True)

    def all_working_agents(self):
        procs = self.all_processes()
        agents = []
        for proc in procs:
            workers = proc.all_working_agents()
            for worker in workers:
                if worker not in agents:
                    agents.append(worker)
        return agents

    def exchange(self):
        exs = Exchange.objects.filter(order=self)
        if exs:
            return exs[0]
        return None

    def node_id(self):
        return "-".join(["Order", str(self.id)])

    def kanban_state(self):
        if not self.has_open_processes():
            return "done"
        if self.has_started_processes():
            return "doing"
        return "planned"

    def timeline_title(self):
        return self.__str__()

    def timeline_description(self):
        return self.description

    def producing_commitments(self):
        return self.commitments.all()

    def order_items(self):
        return self.commitments.all()

    def consumed_input_requirements(self):
        return []

    def used_input_requirements(self):
        return []

    def work_requirements(self):
        return []

    def naming_process(self):
        procs = self.all_processes()
        if not procs:
            procs = list(self.unordered_processes())
        if len(procs) == 1:
            return procs.pop()
        return None

    def process(self): #todo: should this be on order_item?
        answer = None
        #todo: why rand, what difference does it make?
        if self.order_type == 'rand':
            process = None
            for item in self.producing_commitments():
                if item.process:
                    answer = item.process
                    break
        return answer

    def add_commitment(self,
            resource_type,
            context_agent,
            quantity,
            event_type,
            unit,
            description,
            stage=None,
            state=None,
            due=None):
        #todo: needs process and project. Anything else? >>context agent
        #might not be worth refactoring out.
        if not due:
            due=self.due_date
        ct = Commitment(
            order=self,
            independent_demand=self,
            event_type=event_type,
            resource_type=resource_type,
            context_agent=context_agent,
            description=description,
            stage=stage,
            state=state,
            quantity=quantity,
            unit_of_quantity=unit,
            due_date=due)
        ct.save()
        ct.order_item = ct
        ct.save()
        #todo: shd this generate_producing_process?
        return ct

    def create_order_item(self,
            resource_type,
            quantity,
            user):
        #todo pr: may need return inheritance?
        ptrt, inheritance = resource_type.main_producing_process_type_relationship()
        description = ""
        context_agent = None
        stage=None
        state=None
        if ptrt:
            event_type=ptrt.event_type
            stage=ptrt.stage
            state=ptrt.state
            description=ptrt.description
            context_agent=ptrt.process_type.context_agent
        else:
            if self.order_type == "customer":
                #todo exchange redesign fallout
                event_type = EventType.objects.get(name="Give")
                ois = self.order_items()
                if ois:
                    context_agent = ois[0].context_agent
            else:
                #todo wha?
                assert ptrt, 'create_order_item for a work order assumes items with a producing process type'
        commitment = self.add_commitment(
            resource_type=resource_type,
            context_agent=context_agent,
            quantity=quantity,
            event_type=event_type,
            unit=resource_type.unit,
            description=description,
            stage=stage,
            state=state)
        if ptrt:
            commitment.generate_producing_process(user, [], inheritance, explode=True)
        return commitment

    def add_customer_order_item(self,
            resource_type,
            quantity,
            description,
            user,
            stage=None,
            state=None,
            due=None):
        if not due:
            due=self.due_date
        event_type = EventType.objects.get(name="Give")  #(relationship="shipment")
        ct = Commitment(
            order=self,
            independent_demand=self,
            event_type=event_type,
            resource_type=resource_type,
            from_agent=self.provider,
            to_agent=self.receiver,
            context_agent=self.provider,
            description=description,
            stage=stage,
            state=state,
            quantity=quantity,
            unit_of_quantity=resource_type.unit,
            due_date=due,
            created_by=user)
        ct.save()
        ct.order_item = ct
        ct.save()
        ct.generate_producing_process(user, [], inheritance=None, explode=True)
        return ct

    def all_processes(self):
        # this method includes only processes for this order
        processes = Process.objects.filter(plan=self)
        if not processes:
            deliverables = self.commitments.filter(event_type__relationship="out")
            if deliverables:
                processes = [d.process for d in deliverables if d.process]
            else:
                processes = []
                commitments = Commitment.objects.filter(independent_demand=self)
                for c in commitments:
                    if c.process:
                        processes.append(c.process)
                processes = list(set(processes))
        ends = []
        for proc in processes:
            if not proc.next_processes_for_order(self):
                ends.append(proc)
        ordered_processes = []
        for end in ends:
            visited = []
            end.all_previous_processes_for_order(self, ordered_processes, visited, 0)
        ordered_processes.reverse()
        #todo: review bug fixes
        #this code might need more testing for orders with more than one end process
        return ordered_processes

    def unordered_processes(self):
        #this cd be cts = order.dependent_commitments.all()
        # or self.all_dependent_commitments()
        processes = Process.objects.filter(plan=self)
        if not processes:
            cts = Commitment.objects.filter(independent_demand=self)
            processes = set()
            for ct in cts:
                if ct.process:
                    processes.add(ct.process)
        return processes

    def all_dependent_commitments(self):
        # this cd be return order.dependent_commitments.all()
        return Commitment.objects.filter(independent_demand=self)

    def non_work_incoming_commitments(self):
        cts = [ct for ct in self.all_dependent_commitments().exclude(event_type__relationship="out").exclude(event_type__relationship="work")]
        answer = []
        for ct in cts:
            matches = None
            if ct.process:
                pps = ct.process.previous_processes()
                for pp in pps:
                    matches = [oc for oc in pp.outgoing_commitments() if oc.resource_type == ct.resource_type]
                    if matches:
                        break
                if not matches:
                    answer.append(ct)
        return answer

    def all_outgoing_commitments(self):
        cts = [ct for ct in self.all_dependent_commitments().filter(event_type__relationship="out")]
        answer = []
        for ct in cts:
            matches = None
            if ct.process:
                nps = ct.process.next_processes()
                for np in nps:
                    matches = [ic for ic in np.incoming_commitments() if ic.resource_type == ct.resource_type]
                    if matches:
                        break
                if not matches:
                    answer.append(ct)
        return answer

    def non_work_incoming_events(self):
        evts = [evt for evt in self.all_events() if evt.event_type.relationship!="out" and evt.event_type.relationship != "work"]
        answer = []
        for evt in evts:
            matches = None
            if evt.process:
                pps = evt.process.previous_processes()
                for pp in pps:
                    matches = [oevt for oevt in pp.production_events() if oevt.resource_type == evt.resource_type]
                    if matches:
                        break
                if not matches:
                    answer.append(evt)
        return answer

    def all_outgoing_events(self):
        evts = [evt for evt in self.all_events() if evt.event_type.relationship=="out"]
        answer = []
        for evt in evts:
            matches = None
            if evt.process:
                nps = evt.process.next_processes()
                for np in nps:
                    matches = [ievt for ievt in np.incoming_events() if ievt.resource_type == evt.resource_type]
                    if matches:
                        break
                if not matches:
                    answer.append(evt)
        return answer

    def has_open_processes(self):
        answer = False
        processes = self.unordered_processes()
        for process in processes:
            if process.finished == False:
                answer = True
                break
        return answer

    def has_started_processes(self):
        answer = False
        processes = self.unordered_processes()
        for process in processes:
            if process.started:
                answer = True
                break
        return answer

    def last_process_in_order(self):
        processes = self.all_processes()
        if processes:
            return processes[-1]
        else:
            return None

    def first_process_in_order(self):
        processes = list(self.unordered_processes())
        if processes:
            first = processes[0]
            for p in processes:
                if p.start_date < first.start_date:
                    first = p
            return first
        else:
            return None


    def process_types(self):
        pts = []
        for process in self.all_processes():
            if process.process_type:
                pts.append(process.process_type)
        return pts

    def all_events(self):
        processes = self.unordered_processes()
        events = []
        for process in processes:
            events.extend(process.events.all())
        return events

    def all_input_events(self):
        processes = self.unordered_processes()
        events = []
        for process in processes:
            events.extend(process.events.exclude(event_type__relationship="out"))
        return events

    def worked_in_month(self,year, month):
        events = self.all_events()
        for event in events:
            if event.event_type.relationship == "work":
                if event.event_date.year == year and event.event_date.month == month and event.is_contribution == True:
                    return True
        return False

    def context_agents(self):
        items = self.order_items()
        return [item.context_agent for item in items]

    #derives context agents from processes rather than order items for people who don't record outputs
    def plan_context_agents(self):
        processes = self.all_processes()
        return list(set([proc.context_agent for proc in processes]))

    def sale(self):
        sale = None
        if self.order_type == "customer":
            exchange = Exchange.objects.filter(order=self).filter(use_case__identifier="sale")
            sale = exchange[0]
        return sale

    def reschedule_forward(self, delta_days, user):
        self.due_date = self.due_date + datetime.timedelta(days=delta_days)
        self.changed_by = user
        self.save()
        ois = self.order_items()
        for oi in ois:
            if oi.due_date != self.due_date:
                oi.due_date = self.due_date
                oi.save()


class ProcessTypeManager(models.Manager):

    def workflow_process_types(self):
        pts = ProcessType.objects.all()
        workflow_pts = []
        for pt in pts:
            if pt.is_workflow_process_type():
                workflow_pts.append(pt)
        return workflow_pts


class ProcessType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    parent = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('parent'), related_name='sub_process_types', editable=False)
    process_pattern = models.ForeignKey(ProcessPattern,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('process pattern'), related_name='process_types')
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='process_types')
    description = models.TextField(_('description'), blank=True, null=True)
    url = models.CharField(_('url'), max_length=255, blank=True)
    estimated_duration = models.IntegerField(_('estimated duration'),
        default=0, help_text=_("in minutes, e.g. 3 hours = 180"))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='process_types_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='process_types_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = ProcessTypeManager()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        unique_slugify(self, self.name)
        super(ProcessType, self).save(*args, **kwargs)

    @property #ValueFlows
    def note(self):
        return self.description

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    def timeline_title(self):
        return " ".join([self.name, "Process to be planned"])

    def node_id(self):
        return "-".join(["ProcessType", str(self.id)])

    def color(self):
        return "blue"

    def create_process(self, start_date, user, inheritance=None, order=None):
        #pr changed
        end_date = start_date + datetime.timedelta(minutes=self.estimated_duration)
        process = Process(
            name=self.name,
            notes=self.description or "",
            process_type=self,
            process_pattern=self.process_pattern,
            context_agent=self.context_agent,
            url=self.url,
            start_date=start_date,
            end_date=end_date,
            plan=order,
        )
        process.save()
        input_ctypes = self.all_input_resource_type_relationships()
        for ic in input_ctypes:
            ic.create_commitment_for_process(process, user, inheritance)
        output_ctypes = self.produced_resource_type_relationships()
        for oc in output_ctypes:
            oc.create_commitment_for_process(process, user, inheritance)
        #todo: delete next lines, makes awkward process.names?
        #process.name = " ".join([process.name, oc.resource_type.name])
        #process.save()
        return process

    def produced_resource_type_relationships(self):
        #todo pr: needs own_or_parent_recipes
        return self.resource_types.filter(event_type__relationship='out')

    def main_produced_resource_type_relationship(self):
        ptrs = self.produced_resource_type_relationships()
        if ptrs:
            return ptrs[0]
        else:
            return None

    def is_stage(self):
        ct = self.main_produced_resource_type_relationship()
        if ct.stage:
            return True
        return False

    def produced_resource_types(self):
        return [ptrt.resource_type for ptrt in self.produced_resource_type_relationships()]

    def main_produced_resource_type(self):
        prts = self.produced_resource_types()
        if prts:
            return prts[0]
        else:
            return None

    def consumed_and_used_resource_type_relationships(self):
        return self.resource_types.filter(Q(event_type__relationship='consume')|Q(event_type__relationship='use'))

    def consumed_resource_type_relationships(self):
        return self.resource_types.filter(event_type__relationship='consume')

    def used_resource_type_relationships(self):
        return self.resource_types.filter(event_type__relationship='use')

    def cited_resource_type_relationships(self):
        return self.resource_types.filter(event_type__relationship='cite')

    def work_resource_type_relationships(self):
        return self.resource_types.filter(event_type__relationship='work')

    def to_be_changed_resource_type_relationships(self):
        return self.resource_types.filter(event_type__name='To Be Changed')

    def consumed_resource_types(self):
        return [ptrt.resource_type for ptrt in self.consumed_resource_type_relationships()]

    def used_resource_types(self):
        return [ptrt.resource_type for ptrt in self.used_resource_type_relationships()]

    def cited_resource_types(self):
        return [ptrt.resource_type for ptrt in self.cited_resource_type_relationships()]

    def work_resource_types(self):
        return [ptrt.resource_type for ptrt in self.work_resource_type_relationships()]

    def all_input_resource_type_relationships(self):
        return self.resource_types.exclude(event_type__relationship='out').exclude(event_type__relationship='todo')

    def all_input_except_change_resource_type_relationships(self):
        return self.resource_types.exclude(event_type__relationship='out').exclude(event_type__relationship='todo').exclude(event_type__name='To Be Changed')

    def all_input_resource_types(self):
        return [ptrt.resource_type for ptrt in self.all_input_resource_type_relationships()]

    def stream_resource_type_relationships(self):
        return self.resource_types.filter(Q(event_type__name='To Be Changed')|Q(event_type__name='Change')|Q(event_type__name='Create Changeable'))

    def input_stream_resource_type_relationship(self):
        return self.resource_types.filter(event_type__name='To Be Changed')

    def has_create_changeable_output(self):
        if self.produced_resource_type_relationships():
            if self.produced_resource_type_relationships()[0].event_type.name == "Create Changeable":
                return True
            else:
                return False
        else:
            return False

    def is_workflow_process_type(self):
        if self.stream_resource_type_relationships():
            return True
        else:
            if self.resource_types.all().exists():
                return False
            else:
                return True

    def previous_process_types(self):
        return []

    def next_process_types(self):
        return []

    def xbill_parents(self):
        return self.produced_resource_type_relationships()

    def xbill_children(self):
        kids = list(self.consumed_and_used_resource_type_relationships())
        kids.extend(self.cited_resource_type_relationships())
        kids.extend(self.work_resource_type_relationships())
        kids.extend(self.features.all())
        return kids

    def xbill_explanation(self):
        return "Process Type"

    def xbill_change_prefix(self):
        return "".join(["PT", str(self.id)])

    def xbill_change_form(self):
        from valuenetwork.valueaccounting.forms import XbillProcessTypeForm
        qty = Decimal("0.0")
        prtr = self.main_produced_resource_type_relationship()
        if prtr:
            qty = prtr.quantity
        init = {"quantity": qty,}
        return XbillProcessTypeForm(instance=self, initial=init, prefix=self.xbill_change_prefix())

    def recipe_change_form(self):
        from valuenetwork.valueaccounting.forms import RecipeProcessTypeChangeForm
        return RecipeProcessTypeChangeForm(instance=self, prefix=self.xbill_change_prefix())

    def xbill_input_prefix(self):
        return "".join(["PTINPUT", str(self.id)])

    def xbill_consumable_prefix(self):
        return "".join(["PTCONS", str(self.id)])

    def xbill_usable_prefix(self):
        return "".join(["PTUSE", str(self.id)])

    def xbill_citable_prefix(self):
        return "".join(["PTCITE", str(self.id)])

    def xbill_work_prefix(self):
        return "".join(["PTWORK", str(self.id)])

    def xbill_input_rt_prefix(self):
        return "".join(["PTINPUTRT", str(self.id)])

    def xbill_consumable_rt_prefix(self):
        return "".join(["PTCONSRT", str(self.id)])

    def xbill_usable_rt_prefix(self):
        return "".join(["PTUSERT", str(self.id)])

    def xbill_citable_rt_prefix(self):
        return "".join(["PTCITERT", str(self.id)])

    def xbill_input_rt_facet_prefix(self):
        return "".join(["PTINPUTRTF", str(self.id)])

    def xbill_consumable_rt_facet_prefix(self):
        return "".join(["PTCONSRTF", str(self.id)])

    def xbill_usable_rt_facet_prefix(self):
        return "".join(["PTUSERTF", str(self.id)])

    def xbill_citable_rt_facet_prefix(self):
        return "".join(["PTCITERTF", str(self.id)])

    def xbill_input_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeInputForm
        return ProcessTypeInputForm(process_type=self, prefix=self.xbill_input_prefix())

    def xbill_consumable_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeConsumableForm
        return ProcessTypeConsumableForm(process_type=self, prefix=self.xbill_consumable_prefix())

    def xbill_usable_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeUsableForm
        return ProcessTypeUsableForm(process_type=self, prefix=self.xbill_usable_prefix())

    def xbill_citable_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeCitableForm
        return ProcessTypeCitableForm(process_type=self, prefix=self.xbill_citable_prefix())

    def stream_recipe_citable_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeCitableStreamRecipeForm
        return ProcessTypeCitableStreamRecipeForm(process_type=self, prefix=self.xbill_citable_prefix())

    def xbill_work_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeWorkForm
        return ProcessTypeWorkForm(process_type=self, prefix=self.xbill_work_prefix())

    def xbill_input_rt_form(self):
        from valuenetwork.valueaccounting.forms import EconomicResourceTypeAjaxForm
        return EconomicResourceTypeAjaxForm(prefix=self.xbill_input_rt_prefix())

    def xbill_consumable_rt_form(self):
        from valuenetwork.valueaccounting.forms import EconomicResourceTypeAjaxForm
        return EconomicResourceTypeAjaxForm(prefix=self.xbill_consumable_rt_prefix())

    def xbill_usable_rt_form(self):
        from valuenetwork.valueaccounting.forms import EconomicResourceTypeAjaxForm
        return EconomicResourceTypeAjaxForm(prefix=self.xbill_usable_rt_prefix())

    def xbill_citable_rt_form(self):
        from valuenetwork.valueaccounting.forms import EconomicResourceTypeAjaxForm
        return EconomicResourceTypeAjaxForm(prefix=self.xbill_citable_rt_prefix())

    def xbill_input_rt_facet_formset(self):
        return self.create_facet_formset_filtered(slot="in", pre=self.xbill_input_rt_facet_prefix())

    def xbill_consumable_rt_facet_formset(self):
        return self.create_facet_formset_filtered(slot="consume", pre=self.xbill_consumable_rt_facet_prefix())

    def xbill_usable_rt_facet_formset(self):
        return self.create_facet_formset_filtered(slot="use", pre=self.xbill_usable_rt_facet_prefix())

    def xbill_citable_rt_facet_formset(self):
        return self.create_facet_formset_filtered(slot="cite", pre=self.xbill_citable_rt_facet_prefix())

    def stream_process_type_create_prefix(self):
        return "".join(["PTP", str(self.id)])

    def stream_process_type_create_form(self):
        from valuenetwork.valueaccounting.forms import RecipeProcessTypeForm
        rt = self.stream_resource_type()
        #init = {"name": " ".join(["Make", rt.name])}
        #return RecipeProcessTypeForm(initial=init, prefix=self.stream_process_type_create_prefix())
        return RecipeProcessTypeForm(prefix=self.stream_process_type_create_prefix())

    def stream_resource_type(self):
        answer = None
        ptrts = self.resource_types.all()
        for ptrt in ptrts:
            if ptrt.is_change_related():
                answer = ptrt.resource_type
        return answer

    def create_facet_formset_filtered(self, pre, slot, data=None):
        from django.forms.models import formset_factory
        from valuenetwork.valueaccounting.forms import ResourceTypeFacetValueForm
        RtfvFormSet = formset_factory(ResourceTypeFacetValueForm, extra=0)
        init = []
        if self.process_pattern == None:
            facets = Facet.objects.all()
        else:
            #facets = self.process_pattern.facets_by_relationship(slot)
            if slot == "consume":
                facets = self.process_pattern.consumable_facets()
            elif slot == "use":
                facets = self.process_pattern.usable_facets()
            elif slot == "cite":
                facets = self.process_pattern.citable_facets()
        for facet in facets:
            d = {"facet_id": facet.id,}
            init.append(d)
        formset = RtfvFormSet(initial=init, data=data, prefix=pre)
        for form in formset:
            id = int(form["facet_id"].value())
            facet = Facet.objects.get(id=id)
            form.facet_name = facet.name
            if self.process_pattern == None:
                fvs = facet.values.all()
            else:
                fvs = self.process_pattern.facet_values_for_facet_and_relationship(facet, slot)
            fvs = list(set(fvs))
            choices = [(fv.id, fv.value) for fv in fvs]
            form.fields["value"].choices = choices
        return formset

    def xbill_class(self):
        return "process-type"


class ResourceTypeSpecialPrice(models.Model):
    resource_type = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        verbose_name=_('resource type'), related_name='prices')
    identifier = models.CharField(_('identifier'), max_length=128)
    description = models.TextField(_('description'), blank=True, null=True)
    price_per_unit = models.DecimalField(_('price per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    stage = models.ForeignKey(ProcessType, related_name="price_at_stage",
        verbose_name=_('stage'), blank=True, null=True, on_delete=models.SET_NULL)


class ExchangeTypeManager(models.Manager):

    #before deleting this, track down the connections
    def sale_exchange_types(self):
        return ExchangeType.objects.filter(use_case__identifier='sale')

    def internal_exchange_types(self):
        return ExchangeType.objects.filter(use_case__identifier='intrnl_xfer')

    def supply_exchange_types(self):
        return ExchangeType.objects.filter(use_case__identifier='supply_xfer')

    def demand_exchange_types(self):
        return ExchangeType.objects.filter(use_case__identifier='demand_xfer')

    def membership_share_exchange_type(self):
        print("The old membership_share_exchange_type was called!! ")
        loger.info("The old membership_share_exchange_type was called!! ")
        try:
            xt = ExchangeType.objects.get(name='Membership Contribution')
        except ExchangeType.DoesNotExist:
            print("Membership Contribution et does not exist anymore...")
            loger.info("Membership Contribution et does not exist anymore...")
            xt = None
            #raise ValidationError("Membership Contribution does not exist by that name")
        return xt


class ExchangeType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    use_case = models.ForeignKey(UseCase,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('use case'), related_name='exchange_types')
    description = models.TextField(_('description'), blank=True, null=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='exchange_types_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='exchange_types_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='exchange_types')

    objects = ExchangeTypeManager()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        unique_slugify(self, self.name)
        super(ExchangeType, self).save(*args, **kwargs)

    def slots(self):
        return self.transfer_types.all()

    def is_deletable(self):
        answer = True
        if self.exchanges.all():
            answer = False
        return answer

    def transfer_types_non_reciprocal(self):
        return self.transfer_types.filter(is_reciprocal=False)

    def transfer_types_reciprocal(self):
        return self.transfer_types.filter(is_reciprocal=True)

    def transfer_types_inheriting(self):
        return self.transfer_types.filter(inherit_types=True)

    def transfer_types_creating(self):
        return self.transfer_types.filter(can_create_resource=True)

    def show_name(self, agent):
        name = self.name
        if hasattr(self, 'ocp_record_type') and self.ocp_record_type:
            nom = self.ocp_record_type.name
            x_actions = self.ocp_record_type.x_actions()
            for action in x_actions:
                opposite = action.opposite()
                if opposite:
                    if action.clas and opposite.clas:
                        newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                    if name == newname:
                        newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                    if hasattr(agent, 'project') and agent.project:
                        if action.clas == 'buy' or action.clas == 'receive':
                            name = newname
                    else:
                        if action.clas == 'sell' or action.clas == 'give':
                            name = newname
                    #name = newname
        arr = name.split(' ')
        name = arr[0]
        return name


class GoodResourceManager(models.Manager):
    def get_queryset(self):
        return super(GoodResourceManager, self).get_queryset().exclude(quality__lt=0)

class FailedResourceManager(models.Manager):
    def get_queryset(self):
        return super(FailedResourceManager, self).get_queryset().filter(quality__lt=0)

class EconomicResourceManager(models.Manager):

    def virtual_accounts(self):
        resources = EconomicResource.objects.all()
        vas = []
        for resource in resources:
            if resource.resource_type.is_virtual_account():
                vas.append(resource)
        return vas

    def context_agent_virtual_accounts(self):
        vas = self.virtual_accounts()
        cavas = []
        for va in vas:
            if va.owner():
                if va.owner().is_context_agent():
                    cavas.append(va)
        return cavas

    def onhand(self):
        return EconomicResource.objects.filter(quantity__gt=0)

    def all_economic_resources(self):
        return EconomicResource.objects.all()

    def agent_economic_resources(self, agent):
        if agent:
            return agent.resource_relationships.values('resource')
        loger.debug("- Missing agent context!")
        print("- Missing agent context!")
        return None
    #def search(self, agent_id=None, search_string):
    #    agent = None
    #    if agent_id:
    #        agent = EconomicAgent.objects.get(pk=agent_id)
    #    if search_string = "" or search_string is None:
    #        raise ValidationError("Search string is required.")
    #    if agent:
    #        rts = agent.
    #    else:
    #        rts = EconomicResourceType.objects.all()


class EconomicResource(models.Model):
    resource_type = models.ForeignKey(EconomicResourceType,
        verbose_name=_('resource type'), related_name='resources', on_delete=models.CASCADE)
    identifier = models.CharField(_('identifier'), blank=True, max_length=128)
    independent_demand = models.ForeignKey(Order,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="dependent_resources", verbose_name=_('independent demand'))
    order_item = models.ForeignKey("Commitment",
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="stream_resources", verbose_name=_('order item'))
    stage = models.ForeignKey(ProcessType, related_name="resources_at_stage",
        verbose_name=_('stage'), blank=True, null=True, on_delete=models.SET_NULL)
    exchange_stage = models.ForeignKey(ExchangeType, related_name="resources_at_exchange_stage",
        verbose_name=_('exchange stage'), blank=True, null=True, on_delete=models.SET_NULL)
    state = models.ForeignKey(ResourceState, related_name="resources_at_state",
        verbose_name=_('state'), blank=True, null=True, on_delete=models.SET_NULL)
    url = models.CharField(_('url'), max_length=255, blank=True)
    #todo: remove author, in the meantime, don't use it
    author = models.ForeignKey(EconomicAgent, related_name="authored_resources",
        verbose_name=_('author'), blank=True, null=True, on_delete=models.SET_NULL)
    quantity = models.DecimalField(_('quantity'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    quality = models.DecimalField(_('quality'), max_digits=3, decimal_places=0,
        default=Decimal("0"), blank=True, null=True)
    notes = models.TextField(_('notes'), blank=True, null=True)
    photo = ThumbnailerImageField(_("photo"),
        upload_to='photos', blank=True, null=True)
    photo_url = models.CharField(_('photo url'), max_length=255, blank=True)
    access_rules = models.TextField(_('access rules'), blank=True, null=True)
    current_location = models.ForeignKey(Location,
        verbose_name=_('current location'), related_name='resources_at_location',
        blank=True, null=True, on_delete=models.SET_NULL)
    value_per_unit = models.DecimalField(_('value per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    value_per_unit_of_use = models.DecimalField(_('value per unit of use'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    price_per_unit = models.DecimalField(_('price per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.00"))
    created_date = models.DateField(_('created date'), default=datetime.date.today)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='resources_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='resources_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    expiration_date = models.DateField(verbose_name=_('expiration date'), blank=True, null=True)

    objects = EconomicResourceManager()
    goods = GoodResourceManager()
    failures = FailedResourceManager()

    class Meta:
        ordering = ('resource_type', 'identifier',)

    def __str__(self):
        id_str = self.identifier or str(self.id)
        rt_name = self.resource_type.name
        if self.stage:
            rt_name = "@".join([rt_name, self.stage.name])
        return ": ".join([
            rt_name,
            id_str,
        ])

    def get_absolute_url(self):
        return reverse('resource', kwargs={'resource_id': str(self.id),})

    @property #ValueFlows
    def image(self):
        if self.photo_url:
            return self.photo_url
        elif self.photo:
            from valuenetwork.valueaccounting.utils import get_url_starter
            return get_url_starter() + self.photo.url
        else:
            return ""

    @property #ValueFlows
    def note(self):
        return self.notes

    @property #ValueFlows
    def tracking_identifier(self):
        return self.identifier

    @property #ValueFlows  TODO is this still valid???
    def resource_type_name(self):
        return self.resource_type.name

    @property #ValueFlows
    def numeric_value(self):
        return self.quantity

    @property #ValueFlows
    def unit(self):
        return self.resource_type.unit

    @property #ValueFlows
    def category(self):
        if (self.resource_type.behavior == "other"
        or self.resource_type.behavior == "consumed"
        or self.resource_type.behavior == "used"
        or self.resource_type.behavior == "produced"
        or self.resource_type.behavior == "cited"):
            return "INVENTORY"
        if self.resource_type.behavior == "work":
            return "WORK"
        else:
            return "CURRENCY"

    def save_api(self, process=None, event_type=None, commitment=None):
        self.save()
        #logic derived from views
        new_resource = False
        if self.pk:
            new_resource = True
        if new_resource and process and event_type:
            if event_type.relationship == "out":
                if not self.resource_type.substitutable:
                    if commitment:
                        self.independent_demand = commitment.independent_demand
                        self.order_item = commitment.order_item
                    else:
                        self.independent_demand = process.independent_demand()
                    self.save()

    def transfers(self):
        events = self.events.all().filter(Q(event_type__name="Give")|Q(event_type__name="Receive"))
        transfers = []
        for event in events:
            if event.transfer not in transfers:
                transfers.append(event.transfer)
        return transfers

    def label(self):
        return self.identifier or str(self.id)

    def flow_type(self):
        return "Resource"

    def flow_class(self):
        return "resource"

    def class_label(self):
        return "Economic Resource"

    def flow_description(self):
        #rollup stage change
        id_str = self.identifier or str(self.id)
        resource_string = self.resource_type.name
        try:
            stage = self.historical_stage
        except AttributeError:
            stage = self.stage
        if stage:
            resource_string = "@".join([resource_string, stage.name])
        return ": ".join([
                resource_string,
                id_str,
            ])
    def is_digital_currency_resource(self):
        if hasattr(self, 'faircoin_address') and self.faircoin_address.address:
            return True
        else:
            return False

    def address_is_activated(self):
        if hasattr(self, 'faircoin_address'):
            address = self.faircoin_address.address
            if address:
                if address != "address_requested":
                    return True
        return False

    def digital_currency_history(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        history = []
        address = self.faircoin_address.address
        if address:
            history = faircoin_utils.get_address_history(address)
        return history

    def digital_currency_balance(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        bal = 0
        address = self.faircoin_address.address
        if address:
          if not hasattr(self, 'balance'):
            try:
                balance = faircoin_utils.get_address_balance(address)
                balance = balance[0]
                if balance:
                    bal = Decimal(balance) / FAIRCOIN_DIVISOR
                    self.balance = bal
            except:
                bal = "Not accessible now"
          else:
            bal = self.balance
        return bal

    def digital_currency_balance_unconfirmed(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return "Not accessible now"
        bal = 0
        unconfirmed = 0
        address = self.faircoin_address.address
        if address:
          if not hasattr(self, 'newbalance'):
            try:
                balance = faircoin_utils.get_address_balance(address)
                balance1 = balance[0]
                unconfirmed = balance[1]+balance[2] # the response is triple with unmature and unconfirmed (negative)
                newtxs = self.events.filter(faircoin_transaction__tx_state="new")
                newadd = 0
                for ev in newtxs:
                  if Decimal(ev.quantity):
                    if ev.from_agent == self.owner(): # sended fairs
                        newadd -= Decimal(ev.quantity)
                    else: # new received fairs
                        newadd += Decimal(ev.quantity)
                bal = Decimal(balance1+unconfirmed) / FAIRCOIN_DIVISOR
                if newadd:
                    bal += newadd
                self.newbalance = bal
            except:
                bal = "Not accessible now"
          else:
            bal = self.newbalance
        return bal

    def balance_in_tx_state_new(self):
        newtxs = self.events.filter(faircoin_transaction__tx_state="new")
        newadd = 0
        for ev in newtxs:
            if Decimal(ev.quantity):
                if ev.from_agent == self.owner(): # sended fairs
                    newadd -= Decimal(ev.quantity)
                else: # new received fairs
                    newadd += Decimal(ev.quantity)
        return newadd

    def is_wallet_address(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        address = self.faircoin_address.address
        if address:
          if self.is_address_requested():
            return True
          else:
              return faircoin_utils.is_mine(address)

    def is_address_requested(self):
        address = self.faircoin_address.address
        if address == "address_requested":
            return True
        else:
            return False

    def spending_limit(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return 0
        limit = 0
        address = self.faircoin_address.address
        if address and self.is_wallet_address():
            balance = self.digital_currency_balance()
            self.balance = balance
            newbalance = self.digital_currency_balance_unconfirmed()
            self.newbalance = newbalance
            try:
                if balance:
                    if newbalance < balance:
                        bal = newbalance
                    else:
                        bal = balance
                    fee = Decimal(faircoin_utils.network_fee()) / FAIRCOIN_DIVISOR
                    limit = bal - fee
            except:
                limit = Decimal("0.0")
        return limit

    def context_agents(self):
        pes = self.where_from_events()
        cas = [pe.context_agent for pe in pes if pe.context_agent]
        if not cas:
            pts = self.resource_type.producing_process_types()
            cas = [pt.context_agent for pt in pts if pt.context_agent]
        return list(set(cas))

    def shipped_on_orders(self):
        #todo exchange redesign fallout
        orders = []
        #this is insufficient to select shipments
        #sales below is better
        et = EventType.objects.get(name="Give") #was shipment
        shipments = EconomicEvent.objects.filter(resource=self).filter(event_type=et)
        for ship in shipments:
            if ship.exchange.order:
                orders.append(ship.exchange.order)
        return orders

    def sales(self):
        sales = []
        use_case = UseCase.objects.get(identifier="demand_xfer")
        et = EventType.objects.get(name="Give")
        events = EconomicEvent.objects.filter(resource=self).filter(event_type=et)
        for event in events:
            if event.transfer:
                transfer = event.transfer
                if not transfer.is_reciprocal():
                    if transfer.exchange.exchange_type.use_case == use_case:
                        sales.append(event.transfer.exchange)
        return sales

    def value_equations(self):
        ves = []
        cas = self.context_agents()
        for ca in cas:
            ca_ves = ca.own_or_parent_value_equations()
            if ca_ves:
                ves.extend(ca_ves)
        return ves

    def value_explanation(self):
        return "Value per unit is composed of the value of the inputs on the next level:"

    def unit_of_quantity(self):
        return self.resource_type.unit

    def formatted_quantity(self):
        unit = self.unit_of_quantity()
        if unit:
            if unit.symbol:
                answer = "".join([unit.symbol, str(self.quantity)])
            else:
                answer = " ".join([str(self.quantity), unit.abbrev])
        else:
            answer = str(self.quantity)
        return answer

    def allow_payout_by(self, agent, user):
        if self.quantity:
            if user.is_superuser:
                return True
        return False

    def payout_form(self, data=None):
        from valuenetwork.valueaccounting.forms import PayoutForm
        init = {
            "event_date": datetime.date.today(),
            "quantity": self.quantity,
            "max": self.quantity,
            }
        return PayoutForm(prefix=str(self.id), initial=init, data=data)

    def change_form(self):
        from valuenetwork.valueaccounting.forms import EconomicResourceForm
        unit = self.resource_type.unit_of_use
        vpu_help = None
        if unit:
            vpu_help = "Value added when this resource is used for one " + unit.abbrev
        return EconomicResourceForm(instance=self, vpu_help=vpu_help)

    def transform_form(self, data=None):
        from valuenetwork.valueaccounting.forms import TransformEconomicResourceForm
        quantity = self.quantity
        init = {
            "event_date": datetime.date.today(),
            "quantity": self.quantity,
        }
        unit = self.resource_type.unit
        qty_help = ""
        if unit:
            unit_string = unit.abbrev
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return TransformEconomicResourceForm(qty_help=qty_help, prefix=self.form_prefix(), initial=init, data=data)

    #def change_role_formset(self):
    #    from valuenetwork.valueaccounting.forms import ResourceRoleAgentForm
    #    return EconomicResourceForm(instance=self)

    def event_sequence(self):
        events = self.events.all()
        data = {}
        visited = set()
        for e in events:
            if e not in visited:
                visited.add(e)
                candidates = e.previous_events()
                prevs = set()
                for cand in candidates:
                    #if cand not in visited:
                    #    visited.add(cand)
                    prevs.add(cand)
                data[e] = prevs
        return toposort_flatten(data)

    def test_rollup(self, value_equation=None):
        #leave the following line uncommented
        visited = set()
        path = []
        depth = 0
        value_per_unit = self.roll_up_value(path, depth, visited, value_equation)
        print("value_per_unit:", value_per_unit)
        return path

    def compute_value_per_unit(self, value_equation=None):
        visited = set()
        path = []
        depth = 0
        return self.roll_up_value(path, depth, visited, value_equation)

    def roll_up_value(self, path, depth, visited, value_equation=None):
        # EconomicResource method
        #Value_per_unit will be the result of this method.
        depth += 1
        self.depth = depth
        #self.explanation = "Value per unit consists of all the input values on the next level"
        path.append(self)
        value_per_unit = Decimal("0.0")
        #Values of all of the inputs will be added to this list.
        values = []
        #Resource contributions use event.value.
        contributions = self.resource_contribution_events()
        for evt in contributions:
            value = evt.value
            if value_equation:
                br = evt.bucket_rule(value_equation)
                if br:
                    value = br.compute_claim_value(evt)
            evt_vpu = value / evt.quantity
            if evt_vpu:
                values.append([evt_vpu, evt.quantity])
                #padding = ""
                #for x in range(0,depth):
                #    padding += "."
                #print(padding, depth, evt.id, evt)
                #print(padding, "--- evt_vpu: ", evt_vpu)
                #print(padding, "--- values:", values)
            depth += 1
            evt.depth = depth
            path.append(evt)
            depth -= 1
            #todo br: use
            #br = evt.bucket_rule(value_equation)
        #Purchase contributions use event.value.
        #todo dhen_bug: only buys for the same exchange_stage count
        # also, need to get transfers for the same exchange_stage
        # probably also need to chase historical_stage
        buys = self.purchase_events_for_exchange_stage()
        for evt in buys:
            depth += 1
            evt.depth = depth
            path.append(evt)
            value = evt.value
            if evt.transfer:
                if evt.transfer.exchange:
                    #print("value b4:", value)
                    exchange = evt.transfer.exchange
                    value = exchange.roll_up_value(evt, path, depth, visited, value_equation)
                    #print("value after:", value)
            evt_vpu = value / evt.quantity
            if evt_vpu:
                values.append([evt_vpu, evt.quantity])
                #padding = ""
                #for x in range(0,depth):
                #    padding += "."
                #print(padding, depth, evt.id, evt)
                #print(padding, "--- evt_vpu: ", evt_vpu)
                #print(padding, "--- values:", values)
            depth -= 1
        #todo exchange redesign fallout
        #this is obsolete
        """
        xfers = self.transfer_events_for_exchange_stage()
        for evt in xfers:
            depth += 1
            evt.depth = depth
            path.append(evt)
            value = evt.value
            if evt.exchange:
                #print("value b4:", value)
                value = evt.exchange.roll_up_value(evt, path, depth, visited, value_equation)
                #print("value after:", value)
            evt_vpu = value / evt.quantity
            if evt_vpu:
                values.append([evt_vpu, evt.quantity])
                #padding = ""
                #for x in range(0,depth):
                #    padding += "."
                #print(padding, depth, evt.id, evt)
                #print(padding, "--- evt_vpu: ", evt_vpu)
                #print(padding, "--- values:", values)
            depth -= 1
        """
        citations = []
        production_value = Decimal("0.0")
        #rollup stage change
        processes = self.producing_processes_for_historical_stage()
        for process in processes:
            pe_value = Decimal("0.0")
            if process not in visited:
                visited.add(process)
                depth += 1
                process.depth = depth
                #todo share: credit for production events?
                #todo: eliminate production for other resources
                production_qty = process.production_quantity()
                path.append(process)
                #depth += 1
                if production_qty:
                    inputs = process.incoming_events()
                    for ip in inputs:
                        #Work contributions use resource_type.value_per_unit
                        if ip.event_type.relationship == "work":
                            value = ip.quantity * ip.value_per_unit()
                            if value_equation:
                                br = ip.bucket_rule(value_equation)
                                if br:
                                    #value_b4 = value
                                    value = br.compute_claim_value(ip)
                                    #print(br.id, br)
                                    #print(ip)
                                    #print("--- value b4:", value_b4, "value after:", value)
                            ip.value = value
                            ip.save()
                            pe_value += value
                            #padding = ""
                            #for x in range(0,depth):
                            #    padding += "."
                            #print(padding, depth, ip.id, ip)
                            #print(padding, "--- ip.value: ", ip.value)
                            #print(padding, "--- pe_value:", pe_value)
                            ip.depth = depth
                            path.append(ip)
                        #Use contributions use resource value_per_unit_of_use.
                        elif ip.event_type.relationship == "use":
                            if ip.resource:
                                #price changes
                                if ip.price:
                                    ip.value = ip.price
                                else:
                                    ip.value = ip.quantity * ip.resource.value_per_unit_of_use
                                ip.save()
                                pe_value += ip.value
                                #padding = ""
                                #for x in range(0,depth):
                                #    padding += "."
                                #print(padding, depth, ip.id, ip)
                                #print(padding, "--- ip.value: ", ip.value)
                                #print(padding, "--- pe_value:", pe_value)
                                ip.depth = depth
                                path.append(ip)
                                ip.resource.roll_up_value(path, depth, visited, value_equation)
                                #br = ip.bucket_rule(value_equation)
                        #Consume contributions use resource rolled up value_per_unit
                        elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                            ip.depth = depth
                            path.append(ip)
                            #rollup stage change
                            #this is where it starts (I think)
                            value_per_unit = ip.roll_up_value(path, depth, visited, value_equation)
                            ip.value = ip.quantity * value_per_unit
                            ip.save()
                            pe_value += ip.value
                            #padding = ""
                            #for x in range(0,depth):
                            #    padding += "."
                            #print(padding, depth, ip.id, ip)
                            #print(padding, "--- ip.value: ", ip.value)
                            #print(padding, "--- pe_value:", pe_value)
                        #Citations valued later, after all other inputs added up
                        elif ip.event_type.relationship == "cite":
                            ip.depth = depth
                            path.append(ip)
                            if ip.resource_type.unit_of_use:
                                if ip.resource_type.unit_of_use.unit_type == "percent":
                                    citations.append(ip)
                            else:
                                ip.value = ip.quantity
                                pe_value += ip.value

                                #padding = ""
                                #for x in range(0,depth):
                                #    padding += "."
                                #print(padding, depth, ip.id, ip)
                                #print(padding, "--- ip.value: ", ip.value)
                                #print(padding, "--- pe_value:", pe_value)
                            if ip.resource:
                                ip.resource.roll_up_value(path, depth, visited, value_equation)
            production_value += pe_value
        if production_value:
            #Citations use percentage of the sum of other input values.
            for c in citations:
                percentage = c.quantity / 100
                c.value = production_value * percentage
                c.save()
            for c in citations:
                production_value += c.value
                #padding = ""
                #for x in range(0,depth):
                #    padding += "."
                #print(padding, depth, c.id, c)
                #print(padding, "--- c.value: ", c.value)
                #print(padding, "--- production_value:", production_value)
        if production_value and production_qty:
            #print("production value:", production_value, "production qty", production_qty)
            production_value_per_unit = production_value / production_qty
            values.append([production_value_per_unit, production_qty])
        #If many sources of value, compute a weighted average.
        #Multiple sources cd be:
        #    resource contributions, purchases, and multiple production processes.
        if values:
            if len(values) == 1:
                value_per_unit = values[0][0]
            else:
                #compute weighted average
                weighted_values = sum(v[0] * v[1] for v in values)
                weights = sum(v[1] for v in values)
                if weighted_values and weights:
                    value_per_unit = weighted_values / weights
        self.value_per_unit = value_per_unit.quantize(Decimal('.01'), rounding=ROUND_UP)
        self.save()
        #padding = ""
        #for x in range(0,depth):
        #    padding += "."
        #print(padding, depth, self.id, self, "value_per_unit:", self.value_per_unit)
        return self.value_per_unit

    def rollup_explanation(self):
        depth = -1
        visited = set()
        path = []
        queue = []
        self.rollup_explanation_traversal(path, visited, depth)
        return path

    def direct_value_tree(self):
        depth = -1
        visited = set()
        path = []
        queue = []
        self.direct_value_components(path, visited, depth)
        return path

    def rollup_explanation_traversal(self, path, visited, depth):
        depth += 1
        self.depth = depth
        path.append(self)
        depth += 1
        contributions = self.resource_contribution_events()
        for evt in contributions:
            evt.depth = depth
            path.append(evt)
        buys = self.purchase_events()
        for evt in buys:
            evt.depth = depth
            path.append(evt)
        processes = self.producing_processes()
        for process in processes:
            if process not in visited:
                visited.add(process)
                production_qty = sum(pe.quantity for pe in process.production_events())
                if production_qty:
                    inputs = process.incoming_events()
                    for ip in inputs:
                        if ip.event_type.relationship == "work":
                            ip.depth = depth
                            path.append(ip)
                        elif ip.event_type.relationship == "use":
                            ip.depth = depth
                            path.append(ip)
                        elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                            ip.depth = depth
                            path.append(ip)
                            if ip.resource:
                                ip.resource.rollup_explanation_traversal(path, visited, depth)
                        elif ip.event_type.relationship == "cite":
                            ip.depth = depth
                            path.append(ip)

    def direct_value_components(self, components, visited, depth):
        depth += 1
        self.depth = depth
        components.append(self)
        depth += 1
        contributions = self.resource_contribution_events()
        for evt in contributions:
            evt.depth = depth
            components.append(evt)
        buys = self.purchase_events()
        for evt in buys:
            evt.depth = depth
            components.append(evt)
        processes = self.producing_processes()
        for process in processes:
            #todo: make sure this works for >1 process producing the same resource
            if process not in visited:
                visited.add(process)
                production_qty = sum(pe.quantity for pe in process.production_events())
                if production_qty:
                    inputs = process.incoming_events()
                    for ip in inputs:
                        if ip.event_type.relationship == "work":
                            ip.depth = depth
                            components.append(ip)
                        elif ip.event_type.relationship == "use":
                            ip.depth = depth
                            components.append(ip)
                        elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                            ip.depth = depth
                            components.append(ip)
                            #depth += 1
                            if ip.resource:
                                ip.resource.direct_value_components(components, visited, depth)
                            #depth += 1
                        elif ip.event_type.relationship == "cite":
                            ip.depth = depth
                            components.append(ip)

    def test_compute_income_shares(self, value_equation):
        visited = set()
        path = []
        depth = 0
        #value_per_unit = self.roll_up_value(path, depth, visited, value_equation)
        #print("value_per_unit:", value_per_unit)
        #value = self.quantity * value_per_unit
        visited = set()
        shares = []
        quantity = self.quantity or Decimal("1.0")
        self.compute_income_shares(value_equation, quantity, shares, visited)
        total = sum(s.share for s in shares)
        for s in shares:
            s.fraction = s.share / total
        #print("total shares:", total)
        return shares

    def compute_shipment_income_shares(self, value_equation, quantity):
        #visited = set()
        #path = []
        #depth = 0
        #value_per_unit = self.roll_up_value(path, depth, visited, value_equation)
        #print("value_per_unit:", value_per_unit)
        #value = quantity * value_per_unit
        visited = set()
        shares = []
        self.compute_income_shares(value_equation, quantity, shares, visited)
        total = sum(s.share for s in shares)
        #todo: bob: total was zero, unclear if bad data; unclear what fraction should be in that case
        if total:
            for s in shares:
                s.fraction = s.share / total
        else:
            for s in shares:
                s.fraction = 1
        #print("total shares:", total)
        return shares

    def compute_income_shares(self, value_equation, quantity, events, visited):
        #Resource method
        #print("Resource:", self.id, self)
        #print("running quantity:", quantity, "running value:", value)
        contributions = self.resource_contribution_events()
        for evt in contributions:
            br = evt.bucket_rule(value_equation)
            value = evt.value
            if br:
                value = br.compute_claim_value(evt)
            if value:
                vpu = value / evt.quantity
                evt.share = quantity * vpu
                events.append(evt)
                #print(evt.id, evt, evt.share)
                #print("----Event.share:", evt.share, "= evt.value:", evt.value)
        #purchases of resources in value flow can be contributions
        buys = self.purchase_events()
        for evt in buys:
            #if evt.value:
            #    vpu = evt.value / evt.quantity
            #    evt.share = quantity * vpu
            #    events.append(evt)
            if evt.exchange:
                evt.exchange.compute_income_shares(value_equation, evt, quantity, events, visited)
        #todo exchange redesign fallout
        #change transfer_events, that method is obsolete
        #xfers = self.transfer_events()
        #for evt in xfers:
        #    if evt.exchange:
        #       evt.exchange.compute_income_shares(value_equation, evt, quantity, events, visited)
        #income_shares stage change
        processes = self.producing_processes_for_historical_stage()
        try:
            stage = self.historical_stage
        except AttributeError:
            if self.stage:
                processes = [p for p in processes if p.process_type==self.stage]
        for process in processes:
            if process not in visited:
                visited.add(process)
                if quantity:
                    #todo: how will this work for >1 processes producing the same resource?
                    #what will happen to the shares of the inputs of the later processes?
                    production_events = [e for e in process.production_events() if e.resource==self]
                    produced_qty = sum(pe.quantity for pe in production_events)
                    distro_fraction = 1
                    distro_qty = quantity
                    if produced_qty > quantity:
                        distro_fraction = quantity / produced_qty
                        quantity = Decimal("0.0")
                    elif produced_qty <= quantity:
                        distro_qty = produced_qty
                        quantity -= produced_qty
                    for pe in production_events:
                        #todo br
                        value = pe.quantity
                        br = pe.bucket_rule(value_equation)
                        if br:
                            value = br.compute_claim_value(pe)
                        pe.share = value * distro_fraction
                        pe.value = value
                        events.append(pe)
                    if process.context_agent.compatible_value_equation(value_equation):
                        inputs = process.incoming_events()
                        for ip in inputs:
                            #we assume here that work events are contributions
                            if ip.event_type.relationship == "work":
                                if ip.is_contribution:
                                    value = ip.value
                                    br = ip.bucket_rule(value_equation)
                                    if br:
                                        value = br.compute_claim_value(ip)
                                        ip.value = value
                                    ip.share = value * distro_fraction
                                    events.append(ip)
                                    #print(ip.id, ip, ip.share)
                                    #print("----Event.share:", ip.share, "= Event.value:", ip.value, "* distro_fraction:", distro_fraction)
                            elif ip.event_type.relationship == "use":
                                #use events are not contributions, but their resources may have contributions
                                #equip logging changes
                                if ip.resource:
                                    #price changes
                                    if ip.price:
                                        ip.value = ip.price
                                    else:
                                        ip.value = ip.quantity * ip.resource.value_per_unit_of_use
                                    ip.save()

                                    #experiment for equipment maintenance fee
                                    #ip.share = ip.value
                                    #events.append(ip)

                                    value = ip.value
                                    ip_value = value * distro_fraction
                                    d_qty = distro_qty
                                    if ip_value and value:
                                        d_qty = ip_value / value
                                    #d_qty may be the wrong qty to pass into compute_income_shares
                                    #and compute_income_shares may be the wrong method anyway
                                    #Maybe a use event method?
                                    #What we want to do is pass the ip_value down to the exchange...
                                    #Conceptually, we are distributing ip_value to the contributors to the resource!
                                    new_visited = set()
                                    path = []
                                    depth = 0
                                    resource_value = ip.resource.roll_up_value(path, depth, new_visited, value_equation)
                                    ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)
                            elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                                #consume events are not contributions, but their resources may have contributions
                                #equip logging changes
                                new_visited = set()
                                path = []
                                depth = 0

                                value_per_unit = ip.roll_up_value(path, depth, new_visited, value_equation)
                                ip.value = ip.quantity * value_per_unit
                                ip.save()
                                ip_value = ip.value * distro_fraction
                                d_qty = ip.quantity * distro_fraction
                                #if ip_value:
                                    #print("consumption:", ip.id, ip, "ip.value:", ip.value)
                                    #print("----value:", ip_value, "d_qty:", d_qty, "distro_fraction:", distro_fraction)
                                if ip.resource:
                                    #income_shares stage change
                                    ip.compute_income_shares(value_equation, d_qty, events, visited)
                            elif ip.event_type.relationship == "cite":
                                #citation events are not contributions, but their resources may have contributions
                                if ip.resource:
                                    #equip logging changes
                                    if ip.resource_type.unit_of_use:
                                        if ip.resource_type.unit_of_use.unit_type == "percent":
                                            citations.append(ip)
                                    else:
                                        ip.value = ip.quantity
                                    ip.save()
                                    value = ip.value
                                    ip_value = value * distro_fraction
                                    d_qty = distro_qty
                                    if ip_value and value:
                                        d_qty = ip_value / value
                                    #if ip.resource:
                                    #    ip.resource.compute_income_shares(value_equation, d_qty, events, visited)
                                    new_visited = set()
                                    path = []
                                    depth = 0
                                    resource_value = ip.resource.roll_up_value(path, depth, new_visited, value_equation)
                                    ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)

    def compute_income_shares_for_use(self, value_equation, use_event, use_value, resource_value, events, visited):
        #Resource method
        contributions = self.resource_contribution_events()
        for evt in contributions:
            #todo exchange redesign fallout
            br = evt.bucket_rule(value_equation)
            value = evt.value
            if br:
                value = br.compute_claim_value(evt)
            if value:
                vpu = value / evt.quantity
                evt.share = min(vpu, use_value)
                events.append(evt)
        buys = self.purchase_events()
        for evt in buys:
            #this is because purchase_events will duplicate resource_contribution_events
            if evt not in events:
                if evt.exchange:
                    evt.exchange.compute_income_shares_for_use(value_equation, use_event, use_value, resource_value, events, visited)
        processes = self.producing_processes()
        #shd only be one producing process for a used resource..right?
        quantity = self.quantity
        for process in processes:
            if process not in visited:
                visited.add(process)
                if quantity:
                    #todo: how will this work for >1 processes producing the same resource?
                    #what will happen to the shares of the inputs of the later processes?
                    production_events = process.production_events()
                    produced_qty = sum(pe.quantity for pe in production_events)
                    #todo 3d: how to compute?
                    #this fraction stuff only applies to shipped qties
                    #which do not apply here...
                    distro_fraction = 1
                    distro_qty = quantity
                    if produced_qty > quantity:
                        distro_fraction = quantity / produced_qty
                        quantity = Decimal("0.0")
                    elif produced_qty <= quantity:
                        distro_qty = produced_qty
                        quantity -= produced_qty
                    for pe in production_events:
                        value = pe.quantity
                        br = pe.bucket_rule(value_equation)
                        if br:
                            value = br.compute_claim_value(pe)
                        #todo 3d: how to compute?
                        pe.share = value * distro_fraction
                        events.append(pe)
                    if process.context_agent.compatible_value_equation(value_equation):
                        inputs = process.incoming_events()
                        for ip in inputs:
                            #we assume here that work events are contributions
                            if ip.event_type.relationship == "work":
                                if ip.is_contribution:
                                    value = ip.value
                                    br = ip.bucket_rule(value_equation)
                                    if br:
                                        value = br.compute_claim_value(ip)
                                        ip.value = value
                                    #todo 3d: changed
                                    fraction = ip.value / resource_value
                                    ip.share = use_value * fraction
                                    #ip.share = value * distro_fraction
                                    events.append(ip)
                            elif ip.event_type.relationship == "use":
                                #use events are not contributions, but their resources may have contributions
                                if ip.resource:
                                    #price changes
                                    if ip.price:
                                        ip.value = ip.price
                                    else:
                                        ip.value = ip.quantity * ip.resource.value_per_unit_of_use
                                    value = ip.value
                                    ip_value = value * distro_fraction
                                    d_qty = distro_qty
                                    if ip_value and value:
                                        d_qty = ip_value / value
                                    ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)
                            elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                                #consume events are not contributions, but their resources may have contributions
                                ip_value = ip.value * distro_fraction
                                d_qty = ip.quantity * distro_fraction
                                if ip.resource:
                                    ip.resource.compute_income_shares(value_equation, d_qty, events, visited)
                            elif ip.event_type.relationship == "cite":
                                #citation events are not contributions, but their resources may have contributions
                                #todo: use percent or compute_income_shares_for_use?
                                #value = ip.value
                                #ip_value = value * distro_fraction
                                #d_qty = distro_qty
                                #if ip_value and value:
                                #    d_qty = ip_value / value
                                #if ip.resource:
                                #    ip.resource.compute_income_shares(value_equation, d_qty, events, visited)
                                if ip.resource:
                                    value = ip.value
                                    ip_value = value * distro_fraction
                                    d_qty = distro_qty
                                    if ip_value and value:
                                        d_qty = ip_value / value
                                    new_visited = set()
                                    path = []
                                    depth = 0
                                    resource_value = ip.resource.roll_up_value(path, depth, new_visited, value_equation)
                                    ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)

    def direct_share_components(self, components, visited, depth):
        depth += 1
        self.depth = depth
        components.append(self)
        depth += 1
        contributions = self.resource_contribution_events()
        for evt in contributions:
            evt.depth = depth
            components.append(evt)
        buys = self.purchase_events()
        for evt in buys:
            evt.depth = depth
            components.append(evt)
        processes = self.producing_processes()
        for process in processes:
            if process not in visited:
                visited.add(process)
                production_qty = sum(pe.quantity for pe in process.production_events())
                if production_qty:
                    inputs = process.incoming_events()
                    for ip in inputs:
                        if ip.event_type.relationship == "work":
                            ip.depth = depth
                            components.append(ip)
                        elif ip.event_type.relationship == "use":
                            ip.depth = depth
                            components.append(ip)
                        elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                            ip.depth = depth
                            components.append(ip)
                            #depth += 1
                            if ip.resource:
                                ip.resource.direct_value_components(components, visited, depth)
                            #depth += 1
                        elif ip.event_type.relationship == "cite":
                            ip.depth = depth
                            components.append(ip)

    def is_orphan(self):
        o = True
        if self.agent_resource_roles.all():
            o = False
        if self.commitments.all():
            o = False
        if self.events.all():
            o = False
        return o

    def producing_events(self):
        if self.quality:
            if self.quality < 0:
               return self.events.filter(event_type__resource_effect='<')
        return self.events.filter(event_type__relationship='out')

    def producing_processes(self):
        pes = self.producing_events()
        processes = [pe.process for pe in pes if pe.process]
        processes = list(set(processes))
        return processes

    def producing_processes_for_historical_stage(self):
        #rollup stage change
        pes = self.producing_events()
        processes = [pe.process for pe in pes if pe.process]
        processes = list(set(processes))
        if self.stage:
            try:
                processes = [p for p in processes if p.process_type==self.historical_stage]
            except AttributeError:
                processes = [p for p in processes if p.process_type==self.stage]
        return processes

    def producing_events_for_historical_stage(self):
        pes = self.producing_events()
        if self.stage:
            try:
                pes = [pe for pe in pes if pe.process and pe.process.process_type==self.historical_stage]
            except AttributeError:
                pes = [pe for pe in pes if pe.process and pe.process.process_type==self.stage]
        return pes

    def where_from_events(self):
        #todo exchange redesign fallout
        #these are all obsolete
        return self.events.filter(
            Q(event_type__relationship='out')|Q(event_type__relationship='receive')|Q(event_type__relationship='receivecash')
            |Q(event_type__relationship='cash')|Q(event_type__relationship='resource')|Q(event_type__relationship='change')
            |Q(event_type__relationship='distribute')|Q(event_type__relationship='available')|Q(event_type__relationship='transfer'))

    #todo: add transfer?
    def where_to_events(self):
        #todo exchange redesign fallout
        #shipment is obsolete
        return self.events.filter(
            Q(event_type__relationship='in')|Q(event_type__relationship='consume')|Q(event_type__relationship='use')
            |Q(event_type__relationship='cite')|Q(event_type__relationship='pay')|Q(event_type__relationship='shipment')
            |Q(event_type__relationship='shipment')|Q(event_type__relationship='disburse'))

    def last_exchange_event(self):  #todo: could a resource ever go thru the same exchange stage more than once?
        #todo: this works for the moment because I'm storing exchange stage in the resource even if it came out of a process last (dhen)
        events = self.where_from_events().filter(exchange_stage=self.exchange_stage)
        if events:
            return events[0]
        else:
            return None

    def owner_based_on_exchange(self):
        event = self.last_exchange_event()
        if event:
            return event.to_agent
        else:
            return None

    def consuming_events(self):
        return self.events.filter(event_type__relationship='consume')

    def using_events(self):
        return self.events.filter(event_type__relationship="use")

    def resource_contribution_events(self):
        return self.events.filter(is_contribution=True)

    def cash_events(self): #includes cash contributions, donations and loans
        #todo exchange redesign fallout
        rct_et = EventType.objects.get(name="Receive")
        with_xfer = [event for event in self.events.all() if event.transfer and event.event_type==rct_et]
        currencies = [event for event in with_xfer if event.transfer.transfer_type.is_currency]
        return currencies

    def cash_contribution_events(self): #includes only cash contributions
        #todo exchange redesign fallout
        rct_et = EventType.objects.get(name="Receive")
        with_xfer = [event for event in self.events.all() if event.transfer and event.event_type==rct_et]
        contributions = [event for event in with_xfer if event.is_contribution]
        currencies = [event for event in contributions if event.transfer.transfer_type.is_currency]
        return currencies

    def purchase_events(self):
        #todo exchange redesign fallout
        #is this correct?
        rct_et = EventType.objects.get(name="Receive")
        return self.events.filter(event_type=rct_et, is_contribution=False)

    def purchase_events_for_exchange_stage(self):
        if self.exchange_stage:
            return self.purchase_events().filter(exchange_stage=self.exchange_stage)
        else:
            return self.purchase_events()

    def transfer_events(self):
        #obsolete
        #todo exchange redesign fallout
        print("obsolete resource.transfer_event")
        tx_et = EventType.objects.get(name="Receive")
        return self.events.filter(event_type=tx_et)

    def transfer_events_for_exchange_stage(self):
        #obsolete
        #todo exchange redesign fallout
        if self.exchange_stage:
            return self.transfer_events().filter(exchange_stage=self.exchange_stage)
        else:
            return self.transfer_events()

    def available_events(self):
        av_et = EventType.objects.get(name="Make Available")
        return self.events.filter(event_type=av_et)

    def all_usage_events(self):
        #todo exchange redesign fallout
        #cash is obsolete
        return self.events.exclude(event_type__relationship="out").exclude(event_type__relationship="receive").exclude(event_type__relationship="resource").exclude(event_type__relationship="cash")

    def demands(self):
        answer = self.resource_type.commitments.exclude(event_type__relationship="out")
        if self.stage:
            answer = answer.filter(stage=self.stage)
        return answer

    def is_cited(self):
        ces = self.events.filter(event_type__relationship="cite")
        if ces:
            return True
        else:
            return False

    def label_with_cited(self):
        if self.is_cited:
            cited = ' (Cited)'
        else:
            cited = ''
        return (self.identifier or str(self.id)) + cited

    def unsourced_consumption(self):
        if self.consuming_events():
            if not self.where_from_events():
                return True
        return False

    def used_without_value(self):
        if self.using_events():
            if not self.value_per_unit_of_use:
                return True
        return False

    def is_deletable(self):
        if self.events.all():
            return False
        if self.quantity != 0:
            return False
        return True

    def track_lot_forward(self):
        pass


    def bill_of_lots(self):
        flows = self.inputs_to_output()
        lots = []
        for flow in flows:
            if type(flow) is EconomicEvent:
                resource = flow.resource
                if resource:
                    if not resource == self:
                        lots.append(resource)
        lots = list(set(lots))
        lots.append(self)
        return lots

    def inputs_to_output(self):
        flows = self.incoming_value_flows()
        flows.reverse()
        return flows

    def incoming_value_flows(self):
        flows = []
        visited = set()
        depth = 0
        self.depth = depth
        flows.append(self)
        self.incoming_value_flows_dfs(flows, visited, depth)
        return flows

    def process_exchange_flow(self):
        flows = self.incoming_value_flows()
        xnp = [f for f in flows if type(f) is Process or type(f) is Exchange]
        for x in xnp:
            if type(x) is Process:
                x.type="Process"
                x.stage=x.process_type
            else:
                x.type="Exchange"
                x.stage=x.exchange_type
        return xnp

    def incoming_value_flows_dfs(self, flows, visited, depth):
        #Resource method
        if self not in visited:
            visited.add(self)
            resources = []
            events = self.event_sequence()
            events.reverse()
            pet = EventType.objects.get(name="Resource Production")
            #todo exchange redesign fallout
            #xet = EventType.objects.get(name="Transfer")
            #xfer events no longer exist
            #rcpt = EventType.objects.get(name="Receipt")
            rcpt = EventType.objects.get(name="Receive")

            for event in events:
                if event not in visited:
                    visited.add(event)
                    depth += 1
                    event.depth = depth
                    flows.append(event)
                    if event.event_type==rcpt:
                        if event.transfer:
                            exchange = event.transfer.exchange
                            if exchange:
                                if exchange not in visited:
                                    visited.add(exchange)
                                    exchange.depth = depth + 1
                                    flows.append(exchange)
                                    #todo exchange redesign fallout
                                    for pmt in exchange.reciprocal_transfer_events():
                                        pmt.depth = depth + 2
                                        flows.append(pmt)
                        event.incoming_value_flows_dfs(flows, visited, depth)
                    elif event.event_type==pet:
                        process = event.process
                        if process:
                            if process not in visited:
                                visited.add(process)
                                process.depth = depth + 1
                                flows.append(process)
                                for evt in process.incoming_events():
                                    if evt not in visited:
                                        visited.add(evt)
                                        evt.depth = depth + 2
                                        flows.append(evt)
                                        if evt.resource:
                                            if evt.resource == self:
                                                if self.stage and evt.stage:
                                                    self.historical_stage = evt.stage
                                                    self.incoming_value_flows_dfs(flows, visited, depth + 2)
                                            elif evt.resource not in resources:
                                                resources.append(evt.resource)



            for event in self.purchase_events_for_exchange_stage():
                if event not in visited:
                    visited.add(event)
                    event.depth = depth
                    flows.append(event)
                    if event.exchange:
                        exchange = event.exchange
                        exchange.depth = depth + 1
                        flows.append(exchange)
                        for pmt in event.exchange.payment_events():
                            pmt.depth = depth + 2
                            flows.append(pmt)

            for event in self.resource_contribution_events():
                if event not in visited:
                    visited.add(event)
                    event.depth = depth
                    flows.append(event)

            for resource in resources:
                resource.depth = depth + 3
                flows.append(resource)
                resource.incoming_value_flows_dfs(flows, visited, depth + 3)

    def incoming_events(self):
        flows = self.incoming_value_flows()
        events = []
        for flow in flows:
            if type(flow) is EconomicEvent:
                if flow not in events:
                    events.append(flow)
        return events

    def possible_root_events(self):
        root_names = ['Create Changeable', 'Resource Production',  'Receipt', 'Make Available']
        return self.events.filter(event_type__name__in=root_names)

    def value_flow_going_forward(self):
        #todo: needs rework, see next method
        flows = []
        visited = set()
        depth = 0
        self.depth = depth
        flows.append(self)
        self.value_flow_going_forward_dfs(flows, visited, depth)
        events = self.possible_root_events()
        if events:
            processes = []
            exchanges = []
            for event in events:
                flows.insert(0, event)
                if event.process:
                    if event.process not in processes:
                        processes.append(event.process)
                if event.exchange:
                    if event.exchange not in exchanges:
                        exchanges.append(event.exchange)
            for process in processes:
                flows.insert(0, process)
            for exchange in exchanges:
                flows.insert(0, exchange)
        return flows

    def value_flow_going_forward_dfs(self, flows, visited, depth):
        if not self in visited:
            visited.add(self)
            depth += 1
            #todo: this will break, depends on event creation order
            #also, all_usage_events does not include transfers
            #and, needs to consider stage and exchange_stage
            for event in self.all_usage_events().order_by("id"):
                event.depth = depth
                flows.append(event)
                proc = event.process
                exch = event.exchange
                if proc:
                    if not proc in visited:
                        visited.add(proc)
                        depth += 1
                        proc.depth = depth
                        flows.append(proc)
                        depth += 1
                        for evt in proc.production_events():
                            evt.depth = depth
                            flows.append(evt)
                            resource = evt.resource
                            if resource:
                                if resource not in flows:
                                    flows.append(resource)
                                    resource.value_flow_going_forward_dfs(flows, visited, depth)
                if exch:
                    if not exch in visited:
                        visited.add(exch)
                        depth += 1
                        exch.depth = depth
                        flows.append(exch)
                        depth += 1
                        #todo: transfers will be trouble...
                        #for evt in exch.production_events():
                        #    evt.depth = depth
                        #    flows.append(evt)
                        #    if evt.resource:
                        #        evt.resource.value_flow_going_forward_dfs(flows, visited, depth)

    def forward_flow(self):
        flows = []
        visited = []
        depth = 0
        self.depth = depth
        flows.append(self)
        usage_events = self.all_usage_events()

    def staged_process_sequence_beyond_workflow(self):
        #todo: this was created for a DHen report
        # but does not work yet because the converted data
        # has no commitments
        # Plus, it can't be tested and so probably won't work.
        # also, needs to include exchanges
        processes = []
        if not self.stage:
            return processes
        creation_event = None
        events = self.possible_root_events()
        if events:
            creation_event = events[0]
        if not creation_event:
            return processes
        if creation_event.process:
            creation_event.follow_process_chain_beyond_workflow(processes, all_events)

    def value_flow_going_forward_processes(self):
        in_out = self.value_flow_going_forward()
        processes = []
        for index, io in enumerate(in_out):
            if type(io) is Process:
                if io.input_includes_resource(self):
                    processes.append(io)
        return processes

    def receipt(self):
        in_out = self.value_flow_going_forward()
        receipt = None
        et = EventType.objects.get(name='Receive')
        for index, io in enumerate(in_out):
            if type(io) is EconomicEvent:
                if io.event_type == et:
                    receipt = io
        return receipt

    def form_prefix(self):
        return "-".join(["RES", str(self.id)])

    def consumption_event_form(self):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        qty_help = " ".join(["unit:", self.unit_of_quantity().abbrev, ", up to 2 decimal places"])
        init = { "quantity": self.quantity, }
        return InputEventForm(qty_help=qty_help, prefix=prefix, initial=init)

    def use_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        unit = self.resource_type.directional_unit("use")
        qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix, data=data)

    def cite_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        unit = self.resource_type.directional_unit("cite")
        qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix, data=data)

    def input_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        qty_help = " ".join(["unit:", self.unit_of_quantity().abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix, data=data)

    def owner(self): #returns first owner
        #owner_roles = self.agent_resource_roles.filter(role__is_owner=True)
        #if owner_roles:
        #    return owner_roles[0].agent
        owners = self.owners()
        if owners:
            return owners[0]
        else:
            return None

    def owners(self):
        #todo faircoin: possible problem with multiple owners of faircoin_resources?
        #mitigated by requiring owner or superuser to change faircoin resource
        return [arr.agent for arr in self.agent_resource_roles.filter(role__is_owner=True)]

    def is_virtual_account_of(self, agent):
        if self.resource_type.is_virtual_account():
            owners = [arr.agent for arr in self.agent_resource_roles.filter(role__is_owner=True)]
            if agent in owners:
                return True
        return False

    def all_owners(self):
        owner_assns = self.agent_resource_roles.filter(role__is_owner=True)
        owners = []
        for own in owner_assns:
            owners.append(own.agent.nick)
        return owners

    def all_contacts(self):
        return self.agent_resource_roles.filter(is_contact=True)

    def all_contact_agents(self):
        arrs = self.all_contacts()
        answer = []
        for arr in arrs:
            answer.append(arr.agent)
        return answer

    def all_related_agents(self):
        arrs = self.agent_resource_roles.all()
        agent_ids = []
        for arr in arrs:
            agent_ids.append(arr.agent.id)
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def related_agents(self, role):
        arrs = self.agent_resource_roles.filter(role=role)
        agent_ids = []
        for arr in arrs:
            agent_ids.append(arr.agent.id)
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def equipment_users(self, context_agent):
        agent_list = context_agent.context_equipment_users()
        agent_list.extend([arr.agent for arr in self.agent_resource_roles.all()])
        agent_ids = [agent.id for agent in agent_list]
        return EconomicAgent.objects.filter(pk__in=agent_ids)

    def payout_contacts(self):
        """ this method only applies to virtual account resources """
        distributions = self.distribution_events()
        contacts = []
        for d in distributions:
            dex = d.exchange
            disbursements = dex.disbursement_events()
            for dis in disbursements:
                contacts.extend(dis.resource.all_contacts())
        return contacts

    def distribution_events(self):
        return self.events.filter(
            event_type__relationship='distribute')

    def disbursement_events(self):
        return self.events.filter(
            event_type__relationship='disburse')

    def revert_to_previous_stage(self):
        current_stage = self.stage
        cts, inheritance = self.resource_type.staged_commitment_type_sequence()
        for ct in cts:
            if ct.stage == current_stage:
                break
            prev_stage = ct.stage
        self.stage = prev_stage
        self.save()
        return prev_stage


class AgentResourceType(models.Model):
    agent = models.ForeignKey(EconomicAgent, on_delete=models.CASCADE,
        verbose_name=_('agent'), related_name='resource_types')
    resource_type = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        verbose_name=_('resource type'), related_name='agents')
    score = models.DecimalField(_('score'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"),
        help_text=_("the quantity of contributions of this resource type from this agent"))
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='agent_resource_types')
    lead_time = models.IntegerField(_('lead time'),
        default=0, help_text=_("in days"))
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={'unit_type': 'value'},
        verbose_name=_('unit of value'), related_name="agent_resource_value_units")
    value_per_unit = models.DecimalField(_('value per unit'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    description = models.TextField(_('description'), null=True, blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='arts_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='arts_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    def __str__(self):
        return ' '.join([
            self.agent.name,
            self.event_type.label,
            self.resource_type.name,
        ])

    @property #ValueFlows
    def action(self):
        return self.event_type.action

    def label(self):
        return "source"

    def timeline_title(self):
        return " ".join(["Get ", self.resource_type.name, "from ", self.agent.name])

    def inverse_label(self):
        return self.event_type.inverse_label()

    def xbill_label(self):
        #return self.event_type.infer_label()
        return ""

    def xbill_explanation(self):
        return "Possible source"

    def xbill_child_object(self):
        if self.event_type.relationship == 'out':
            return self.agent
        else:
            return self.resource_type

    def xbill_class(self):
        return self.xbill_child_object().xbill_class()

    def xbill_parent_object(self):
        if self.event_type.relationship == 'out':
            return self.resource_type
        else:
            return self.agent

    def node_id(self):
        return "-".join(["AgentResource", str(self.id)])

    def xbill_change_prefix(self):
        return "".join(["AR", str(self.id)])

    def xbill_change_form(self):
        from valuenetwork.valueaccounting.forms import AgentResourceTypeForm
        return AgentResourceTypeForm(instance=self, prefix=self.xbill_change_prefix())

    def total_required(self):
        commitments = Commitment.objects.unfinished().filter(resource_type=self.resource_type)
        return sum(req.quantity_to_buy() for req in commitments)

    def comparative_scores(self):
        scores = AgentResourceType.objects.filter(resource_type=self.resource_type).values_list('score', flat=True)
        average = str((sum(scores) / len(scores)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        return "".join([
            "Min: ", str(min(scores).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
            ", Average: ", average,
            ", Max: ", str(max(scores).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
            ])

class AgentResourceRoleTypeManager(models.Manager):

    def owner_role(self):
        role_types = AgentResourceRoleType.objects.filter(is_owner=True)
        owner_role_type = None
        if role_types:
            return role_types[0]
        else:
            raise ValidationError("No owner AgentResourceRoleType")


class AgentResourceRoleType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    description = models.TextField(_('description'), blank=True, null=True)
    is_owner = models.BooleanField(_('is owner'), default=False)

    objects = AgentResourceRoleTypeManager()

    def __str__(self):
        return self.name


class AgentResourceRole(models.Model):
    agent = models.ForeignKey(EconomicAgent, on_delete=models.CASCADE,
        verbose_name=_('agent'), related_name='agent_resource_roles')
    resource = models.ForeignKey(EconomicResource, on_delete=models.CASCADE,
        verbose_name=_('resource'), related_name='agent_resource_roles')
    role = models.ForeignKey(AgentResourceRoleType, on_delete=models.CASCADE,
        verbose_name=_('role'), related_name='agent_resource_roles')
    is_contact = models.BooleanField(_('is contact'), default=False)
    owner_percentage = models.IntegerField(_('owner percentage'), null=True)

    def __str__(self):
        return " ".join([self.agent.name, self.role.name, self.resource.__str__()])


#todo: rename to CommitmentType
class ProcessTypeResourceType(models.Model):
    process_type = models.ForeignKey(ProcessType, on_delete=models.CASCADE,
        verbose_name=_('process type'), related_name='resource_types')
    resource_type = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        verbose_name=_('resource type'), related_name='process_types')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='process_resource_types')
    stage = models.ForeignKey(ProcessType, related_name="commitmenttypes_at_stage",
        verbose_name=_('stage'), blank=True, null=True, on_delete=models.SET_NULL)
    state = models.ForeignKey(ResourceState, related_name="commitmenttypes_at_state",
        verbose_name=_('state'), blank=True, null=True, on_delete=models.SET_NULL)
    quantity = models.DecimalField(_('quantity'), max_digits=8, decimal_places=2, default=Decimal('0.00'))
    unit_of_quantity = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="process_resource_qty_units")
    description = models.TextField(_('description'), null=True, blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='ptrts_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='ptrts_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    class Meta:
        ordering = ('resource_type',)
        verbose_name = _('commitment type')

    def __str__(self):
        relname = ""
        if self.event_type:
            relname = self.event_type.label
        rt_name = self.resource_type.name
        if self.stage:
            rt_name = "".join([rt_name, "@", self.stage.name])
        return " ".join([self.process_type.name, relname, str(self.quantity), rt_name])

    def inverse_label(self):
        return self.event_type.inverse_label

    def cycle_id(self):
        stage_id = ""
        if self.stage:
            stage_id = str(self.stage.id)
        state_id = ""
        if self.state:
            state_id = str(self.state.id)
        return "-".join([str(self.resource_type.id), stage_id, state_id])

    def is_change_related(self):
        return self.event_type.is_change_related()

    def follow_stage_chain(self, chain):
        if self.event_type.is_change_related():
            if self not in chain:
                chain.append(self)
                if self.event_type.relationship == "out":
                    next_in_chain = ProcessTypeResourceType.objects.filter(
                        resource_type=self.resource_type,
                        stage=self.stage,
                        event_type__resource_effect=">~")
                if self.event_type.relationship == "in":
                    next_in_chain = ProcessTypeResourceType.objects.filter(
                        resource_type=self.resource_type,
                        stage=self.process_type,
                        event_type__resource_effect="~>")
                if next_in_chain:
                    next_in_chain[0].follow_stage_chain(chain)

    def follow_stage_chain_beyond_workflow(self, chain):
        chain.append(self)
        if self.event_type.is_change_related():
            if self.event_type.relationship == "out":
                next_in_chain = self.resource_type.wanting_process_type_relationships_for_stage(self.stage)
            if self.event_type.relationship == "in":
                next_in_chain = ProcessTypeResourceType.objects.filter(
                    resource_type=self.resource_type,
                    stage=self.process_type,
                    event_type__resource_effect="~>")
            if next_in_chain:
                next_in_chain[0].follow_stage_chain_beyond_workflow(chain)

    def create_commitment_for_process(self, process, user, inheritance):
        #pr changed
        #changed for work commitment.due_date
        if self.event_type.relationship == "out" or self.event_type.is_work():
            due_date = process.end_date
        else:
            due_date = process.start_date
        resource_type = self.resource_type
        #todo dhen: this is where species would be used
        if inheritance:
            if resource_type == inheritance.parent:
                resource_type = inheritance.substitute(resource_type)
        unit = self.resource_type.directional_unit(self.event_type.relationship)
        commitment = Commitment(
            process=process,
            stage=self.stage,
            state=self.state,
            description=self.description,
            context_agent=process.context_agent,
            event_type=self.event_type,
            resource_type=resource_type,
            quantity=self.quantity,
            unit_of_quantity=unit,
            due_date=due_date,
            #from_agent=from_agent,
            #to_agent=to_agent,
            created_by=user)
        commitment.save()
        return commitment

    def create_commitment(self, due_date, user):
        unit = self.resource_type.directional_unit(self.event_type.relationship)
        commitment = Commitment(
            stage=self.stage,
            state=self.state,
            description=self.description,
            context_agent=self.process_type.context_agent,
            event_type=self.event_type,
            resource_type=self.resource_type,
            quantity=self.quantity,
            #todo exchange redesign fallout
            unit_of_quantity=unit,
            due_date=due_date,
            #from_agent=from_agent,
            #to_agent=to_agent,
            created_by=user)
        commitment.save()
        return commitment

    def stream_label(self):
        relname = ""
        if self.event_type:
            relname = self.event_type.label
        rt_name = self.resource_type.name
        if self.stage:
            rt_name = "".join([rt_name, "@", self.stage.name])
        abbrev = ""
        if self.unit_of_quantity:
            abbrev = self.unit_of_quantity.abbrev
        return " ".join([relname, str(self.quantity), abbrev, rt_name])

    def xbill_label(self):
        if self.event_type.relationship == 'out':
            #return self.inverse_label()
            return ""
        else:
            abbrev = ""
            if self.unit_of_quantity:
                abbrev = self.unit_of_quantity.abbrev
            return " ".join([self.event_type.label, str(self.quantity), abbrev])

    def xbill_explanation(self):
        if self.event_type.relationship == 'out':
            return "Process Type"
        else:
            return "Input"

    def xbill_child_object(self):
        if self.event_type.relationship == 'out':
            return self.process_type
        else:
            return self.resource_type

    def xbill_class(self):
        return self.xbill_child_object().xbill_class()

    def xbill_parent_object(self):
        if self.event_type.relationship == 'out':
            return self.resource_type
            #if self.resource_type.category.name == 'option':
            #    return self
            #else:
            #    return self.resource_type
        else:
            return self.process_type

    def xbill_parents(self):
        return [self.resource_type, self]

    def node_id(self):
        #todo: where is this used? Did I break it with this change?
        #(adding stage and state)
        answer = "-".join(["ProcessResource", str(self.id)])
        if self.stage:
            answer = "-".join([answer, str(self.stage.id)])
        if self.state:
            answer = "-".join([answer, self.state.name])
        return answer

    def xbill_change_prefix(self):
        return "".join(["PTRT", str(self.id)])

    def xbill_change_form(self):
        from valuenetwork.valueaccounting.forms import ProcessTypeInputForm, ProcessTypeCitableForm, ProcessTypeWorkForm
        if self.event_type.relationship == "work":
            return ProcessTypeWorkForm(instance=self, process_type=self.process_type, prefix=self.xbill_change_prefix())
        elif self.event_type.relationship == "cite":
            return ProcessTypeCitableForm(instance=self, process_type=self.process_type, prefix=self.xbill_change_prefix())
        else:
            return ProcessTypeInputForm(instance=self, process_type=self.process_type, prefix=self.xbill_change_prefix())

class ProcessManager(models.Manager):

    def unfinished(self):
        return Process.objects.filter(finished=False)

    def finished(self):
        return Process.objects.filter(finished=True)

    def current(self):
        return Process.objects.filter(finished=False).filter(start_date__lte=datetime.date.today()).filter(end_date__gte=datetime.date.today())

    def current_or_future(self):
        return Process.objects.filter(finished=False).filter(end_date__gte=datetime.date.today())

    def current_or_future_with_use(self):
        processes = Process.objects.current_or_future()
        ids = []
        use_et = EventType.objects.get(name="Resource use")
        for process in processes:
            if process.process_pattern:
                if use_et in process.process_pattern.event_types():
                    ids.append(process.id)
        return Process.objects.filter(pk__in=ids)


class Process(models.Model):
    name = models.CharField(_('name'), max_length=128)
    parent = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('parent'), related_name='sub_processes', editable=False)
    process_pattern = models.ForeignKey(ProcessPattern,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('process pattern'), related_name='processes')
    process_type = models.ForeignKey(ProcessType,
        blank=True, null=True,
        verbose_name=_('process type'), related_name='processes',
        on_delete=models.SET_NULL)
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='processes')
    plan = models.ForeignKey(Order,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('plan'), related_name='processes')
    url = models.CharField(_('url'), max_length=255, blank=True)
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), blank=True, null=True)
    started = models.DateField(_('started'), blank=True, null=True)
    finished = models.BooleanField(_('finished'), default=False)
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='processes_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='processes_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = ProcessManager()

    class Meta:
        ordering = ('-end_date',)
        verbose_name_plural = _("processes")

    def __str__(self):
        order_name = ""
        order = self.independent_demand()
        if order:
            order_name = order.name
            if order_name:
                order_name = " ".join(["to", order_name])
        return " ".join([
            self.name,
            order_name,
            "starting",
            self.start_date.strftime('%Y-%m-%d'),
            "ending",
            self.end_date.strftime('%Y-%m-%d'),
            ])

    def shorter_label(self):
        return " ".join([
            self.name,
            self.start_date.strftime('%Y-%m-%d'),
            "to",
            self.end_date.strftime('%Y-%m-%d'),
            ])

    def name_with_order(self):
        answer = self.name
        order = self.independent_demand()
        if order:
            order_name = order.name
            if order_name:
                answer = " ".join([self.name, "for", order_name])
        return answer

    def class_label(self):
        return "Process"

    def get_absolute_url(self):
        return reverse('process_details', kwargs={'process_id': str(self.id),})

    def get_notification_url(self):
        if 'work.apps.WorkAppConfig' in settings.INSTALLED_APPS:
            return reverse('process_logging', kwargs={ 'process_id': str(self.id)})
        else:
            return reverse('process_details', kwargs={ 'process_id': str(self.id)})

    def save(self, *args, **kwargs):
        pt_name = ""
        if self.process_type:
            pt_name = self.process_type.name
        slug = "-".join([
            pt_name,
            self.name,
            self.start_date.strftime('%Y-%m-%d'),
        ])
        unique_slugify(self, slug)
        super(Process, self).save(*args, **kwargs)
        for commit in self.commitments.all():
            if commit.context_agent != self.context_agent:
                old_agent = commit.context_agent
                commit.context_agent = self.context_agent
                if commit.from_agent == old_agent:
                    commit.from_agent = self.context_agent
                if commit.to_agent == old_agent:
                    commit.to_agent = self.context_agent
                commit.save()
        for event in self.events.all():
            if event.context_agent != self.context_agent:
                old_agent = event.context_agent
                event.context_agent = self.context_agent
                if event.from_agent == old_agent:
                    event.from_agent = self.context_agent
                if event.to_agent == old_agent:
                    event.to_agent = self.context_agent
                event.save()

    def save_api(self):
        self.save()
        for ct in self.incoming_commitments():
            #changed for work commitment.due_date
            if ct.is_work():
                if ct.due_date != self.end_date:
                    ct.due_date = self.end_date
                    ct.save()
            else:
                if ct.due_date != self.start_date:
                    ct.due_date = self.start_date
                    ct.save()
        for ct in self.outgoing_commitments():
            if ct.due_date != self.end_date:
                ct.due_date = self.end_date
                ct.save()

    @property #ValueFlows
    def planned_start(self):
        return self.start_date

    @property #for api, will propose for ValueFlows
    def planned_finish(self):
        return self.end_date

    @property #ValueFlows
    def planned_duration(self):
        return self.end_date - self.start_date

    #@property #ValueFlows
    #def numeric_duration(self):
    #    return self.end_date - self.start_date #TODO get in tune with VF, get VF resolved

    #@property #ValueFlows
    #def temporal_unit(self):
    #    return "Days" #TODO get in tune with VF, get VF resolved

    @property #ValueFlows
    def is_finished(self):
        return self.finished

    @property #ValueFlows
    def is_started(self):
        return self.started

    @property #ValueFlows
    def note(self):
        return self.notes

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    def worked_in_month(self, year, month):
        return self.events.filter(event_type__relationship='work').filter(event_date__year=year).filter(event_date__month=month).filter(is_contribution=True)

    def get_rts_by_action(self, event_type):
        try:
            from work.models import Project
            proj = Project.objects.get(agent=self.context_agent)
            if proj:
                rt_selection = proj.resource_type_selection
            else:
                rt_selection = "all"
        except:
            rt_selection = "all"
        #items =
        #if rt_selection == "project":
        return rt_selection #temp

    def is_deletable(self):
        if self.events.all():
            return False
        return True

    def set_started(self, date, user):
        if not self.started:
            self.started = date
            self.changed_by=user
            self.save()

    def default_agent(self):
        if self.context_agent:
            return self.context_agent.default_agent()
        return None

    def flow_type(self):
        return "Process"

    def flow_class(self):
        return "process"

    def flow_description(self):
        return self.__str__()

    def node_id(self):
        return "-".join(["Process", str(self.id)])

    def independent_demand(self):
        moc = self.main_outgoing_commitment()
        if moc:
            return moc.independent_demand
        else:
            ics = self.incoming_commitments()
            if ics:
                return ics[0].independent_demand
        return None

    def order_item(self):
        moc = self.main_outgoing_commitment()
        if moc:
            return moc.order_item
        else:
            ics = self.incoming_commitments()
            if ics:
                return ics[0].order_item
        return None

    def timeline_title(self):
        #return " ".join([self.name, "Process"])
        return self.name

    def timeline_description(self):
        if self.notes:
            return self.notes
        elif self.process_type:
            return self.process_type.description
        else:
            return ""

    def is_orphan(self):
        #todo: if agents on graph, stop excluding work
        answer = True
        if self.commitments.exclude(event_type__relationship='work'):
            answer = False
        if self.events.all():
            answer = False
        return answer

    def incoming_commitments(self):
        return self.commitments.exclude(
            event_type__relationship='out')

    def schedule_requirements(self):
        return self.commitments.exclude(
            event_type__relationship='out')

    def outgoing_commitments(self):
        return self.commitments.filter(
            event_type__relationship='out')

    def output_resource_types(self):
        return [c.resource_type for c in self.outgoing_commitments()]

    def production_events(self):
        return self.events.filter(
            event_type__relationship='out')

    def production_quantity(self):
        return sum(pe.quantity for pe in self.production_events())

    def uncommitted_events(self):
        return self.events.filter(commitment=None)

    def uncommitted_production_events(self):
        return self.events.filter(
            event_type__relationship='out',
            commitment=None)

    def uncommitted_consumption_events(self):
        return self.events.filter(
            event_type__relationship='consume',
            commitment=None)

    def uncommitted_use_events(self):
        return self.events.filter(
            event_type__relationship='use',
            commitment=None)

    def uncommitted_process_expense_events(self):
        return self.events.filter(
            event_type__relationship='payexpense',
            commitment=None)

    def uncommitted_citation_events(self):
        return self.events.filter(
            event_type__relationship='cite',
            commitment=None)

    def uncommitted_input_events(self):
        return self.events.filter(
            commitment=None).exclude(event_type__relationship='out')

    def incoming_events(self):
        return self.events.exclude(event_type__relationship='out')

    def uncommitted_work_events(self):
        return self.events.filter(
            event_type__relationship='work',
            commitment=None)

    def has_events(self):
        if self.events.count() > 0:
            return True
        else:
            return False

    def main_outgoing_commitment(self):
        cts = self.outgoing_commitments()
        for ct in cts:
            if ct.order_item:
                return ct
        if cts:
            return cts[0]
        return None

    def input_includes_resource(self, resource):
        inputs = self.incoming_events()
        answer = False
        for event in inputs:
            if event.resource == resource:
                answer = True
                break
        return answer

    def previous_processes(self):
        answer = []
        dmnd = None
        moc = self.main_outgoing_commitment()
        if moc:
            dmnd = moc.order_item
        #output_rts = [oc.resource_type for oc in self.outgoing_commitments()]
        for ic in self.incoming_commitments():
            rt = ic.resource_type
            stage = ic.stage
            state = ic.state
            # this is maybe a better way to block cycles
            for pc in rt.producing_commitments():
                if pc.process != self:
                    if pc.stage == stage and pc.state == state:
                        if dmnd:
                            if pc.order_item == dmnd:
                                answer.append(pc.process)
                        else:
                            if not pc.order_item:
                                if pc.quantity >= ic.quantity:
                                    if pc.due_date <= self.start_date:
                                        answer.append(pc.process)
        for ie in self.incoming_events():
            #todo: check stage of ie.resource != self.process_type
            if ie.resource:
                for evt in ie.resource.producing_events():
                    if evt.process:
                        if evt.process != self:
                            if evt.process not in answer:
                                answer.append(evt.process)
        return answer

    def previous_processes_for_order(self, order):
        #this is actually previous_processes_for_order_item
        answer = []
        dmnd = None
        moc = self.main_outgoing_commitment()
        if moc:
            dmnd = moc.order_item
        #output_rts = [oc.resource_type for oc in self.outgoing_commitments()]
        for ic in self.incoming_commitments():
            rt = ic.resource_type
            stage = ic.stage
            state = ic.state
            # this is maybe a better way to block cycles
            for pc in rt.producing_commitments():
                if pc.process != self:
                    if pc.stage == stage and pc.state == state:
                        if dmnd:
                            if pc.order_item == dmnd:
                                answer.append(pc.process)
        return answer

    def all_previous_processes(self, ordered_processes, visited, depth):
        self.depth = depth * 2
        ordered_processes.append(self)
        output = self.main_outgoing_commitment()
        if not output:
            return []
        depth = depth + 1
        if output.cycle_id() not in visited:
            visited.append(output.cycle_id())
            for process in self.previous_processes():
                process.all_previous_processes(ordered_processes, visited, depth)

    def all_previous_processes_for_order(self, order, ordered_processes, visited, depth):
        #this is actually all_previous_processes_for_order_item
        self.depth = depth * 2
        ordered_processes.append(self)
        output = self.main_outgoing_commitment()
        if not output:
            return []
        depth = depth + 1
        if output.cycle_id() not in visited:
            visited.append(output.cycle_id())
            for process in self.previous_processes_for_order(order):
                process.all_previous_processes_for_order(order, ordered_processes, visited, depth)

    def next_processes(self):
        answer = []
        input_ids = [ic.cycle_id() for ic in self.incoming_commitments()]
        for oc in self.outgoing_commitments():
            dmnd = oc.order_item
            stage = oc.stage
            state = oc.state
            rt = oc.resource_type
            if oc.cycle_id() not in input_ids:
                for cc in rt.wanting_commitments():
                    if cc.stage == stage and cc.state == state:
                        if dmnd:
                            if cc.order_item == dmnd:
                                if cc.process:
                                    if cc.process not in answer:
                                        answer.append(cc.process)
                        else:
                            if not cc.order_item:
                                if cc.quantity >= oc.quantity:
                                    compare_date = self.end_date
                                    if not compare_date:
                                        compare_date = self.start_date
                                    if cc.due_date >= compare_date:
                                        if cc.process:
                                            if cc.process not in answer:
                                                answer.append(cc.process)
        for oe in self.production_events():
            rt = oe.resource_type
            if oe.cycle_id() not in input_ids:
                if oe.resource:
                    for evt in oe.resource.all_usage_events():
                        if evt.process:
                            if evt.process != self:
                                if evt.process not in answer:
                                    answer.append(evt.process)
        return answer

    def next_processes_for_order(self, order):
        answer = []
        input_ids = [ic.cycle_id() for ic in self.incoming_commitments()]
        for oc in self.outgoing_commitments():
            dmnd = oc.order_item
            stage = oc.stage
            state = oc.state
            rt = oc.resource_type
            if oc.cycle_id() not in input_ids:
                #todo: this can be slow for non-sub rts
                for cc in rt.wanting_commitments():
                    if cc.process:
                        if cc.stage == stage and cc.state == state:
                            if dmnd:
                                if cc.order_item == dmnd:
                                    if cc.process not in answer:
                                        answer.append(cc.process)
        return answer


    def consumed_input_requirements(self):
        return self.commitments.filter(
            event_type__relationship='consume'
        )

    def used_input_requirements(self):
        return self.commitments.filter(
            event_type__relationship='use'
        )

    def citation_requirements(self):
        return self.commitments.filter(
            event_type__relationship='cite',
        )

    def work_requirements(self):
        return self.commitments.filter(
            event_type__relationship='work',
        )

    def unfinished_work_requirements(self):
        return self.commitments.filter(
            finished=False,
            event_type__relationship='work',
        )

    def finished_work_requirements(self):
        return self.commitments.filter(
            finished=True,
            event_type__relationship='work',
        )

    def non_work_requirements(self):
        return self.commitments.exclude(
            event_type__relationship='work',
        )

    def non_work_input_requirements(self):
        return self.commitments.exclude(
            event_type__relationship='work').exclude(
            event_type__relationship='out')

    def create_changeable_requirements(self):
        return self.commitments.filter(
        event_type__name="Create Changeable")

    def to_be_changed_requirements(self):
        return self.commitments.filter(
            event_type__name="To Be Changed")

    def changeable_requirements(self):
        return self.commitments.filter(
            event_type__name="Change")

    def paired_change_requirements(self):
        return self.to_be_changed_requirements(), self.changeable_requirements()

    def is_staged(self):
        if self.create_changeable_requirements() or self.changeable_requirements():
            return True
        else:
            return False

    def working_agents(self):
        reqs = self.work_requirements()
        return [req.from_agent for req in reqs if req.from_agent]

    def all_working_agents(self): #from both commitments and events
        agents = self.working_agents()
        work_events = self.work_events()
        for event in work_events:
            agents.append(event.from_agent)
        return set(list(agents))

    def work_events(self):
        return self.events.filter(
            event_type__relationship='work')

    def non_work_input_events(self):
        return self.events.exclude(
            event_type__relationship='work').exclude(
            event_type__relationship='out')

    def unplanned_work_events(self):
        return self.work_events().filter(commitment__isnull=True)

    def unplanned_work_events_condensed(self):
        event_list = self.unplanned_work_events()
        condensed_events = []
        if event_list:
            summaries = {}
            for event in event_list:
                try:
                    key = "-".join([
                        str(event.from_agent.id),
                        str(event.context_agent.id),
                        str(event.resource_type.id),
                        str(event.event_type.id)
                        ])
                    if not key in summaries:
                        summaries[key] = EventSummary(
                            event.from_agent,
                            event.context_agent,
                            event.resource_type,
                            event.event_type,
                            Decimal('0.0'))
                    summaries[key].quantity += event.quantity
                except AttributeError:
                    msg = " ".join(["invalid summary key:", key])
                    assert False, msg
            condensed_events = list(summaries.values())
        return condensed_events

    def outputs(self):
        return self.events.filter(
            event_type__relationship='out',
            quality__gte=0)

    def deliverables(self):
        return [output.resource for output in self.outputs() if output.resource]

    def failed_outputs(self):
        return self.events.filter(
            event_type__relationship='out',
            quality__lt=0)

    def consumed_inputs(self):
        return self.events.filter(
            event_type__relationship='consume')

    def used_inputs(self):
        return self.events.filter(
            event_type__relationship='use')

    def citations(self):
        return self.events.filter(
            event_type__relationship='cite')

    def outputs_from_agent(self, agent):
        answer = []
        for event in self.outputs():
            if event.from_agent == agent:
                answer.append(event)
        return answer

    def citations_by_agent(self, agent):
        answer = []
        for event in self.citations():
            if event.from_agent == agent:
                answer.append(event)
        return answer

    def inputs_consumed_by_agent(self, agent):
        answer = []
        for event in self.consumed_inputs():
            if event.to_agent == agent:
                answer.append(event)
        return answer

    def inputs_used_by_agent(self, agent):
        answer = []
        for event in self.used_inputs():
            if event.to_agent == agent:
                answer.append(event)
        return answer

    def failed_output_qty(self):
        return sum(evt.quantity for evt in self.events.filter(quality__lt=0))

    def failures_from_agent(self, agent):
        answer = []
        for event in self.failed_outputs():
            if event.from_agent == agent:
                answer.append(event)
        return answer

    def order_items(self):
        return []

    def add_commitment(self,
            resource_type,
            demand,
            quantity,
            event_type,
            unit,
            user,
            description,
            order_item=None,
            stage=None,
            state=None,
            from_agent=None,
            to_agent=None,
            order=None,
            ):
        #changed for work commitment.due_date
        if event_type.relationship == "out" or event_type.is_work():
            due_date = self.end_date
        else:
            due_date = self.start_date
        ct = Commitment(
            independent_demand=demand,
            order=order,
            order_item=order_item,
            process=self,
            description=description,
            #Todo: apply selected_context_agent here? Dnly if inheritance?
            #or has that already been set on the process in explode_demands?
            context_agent=self.context_agent,
            event_type=event_type,
            resource_type=resource_type,
            stage=stage,
            state=state,
            quantity=quantity,
            unit_of_quantity=unit,
            due_date=due_date,
            from_agent=from_agent,
            to_agent=to_agent,
            created_by=user)
        ct.save()
        return ct

    def add_stream_commitments(self, last_process, user): #for adding to the end of the order
        last_commitment = last_process.main_outgoing_commitment()
        ets = self.process_pattern.change_event_types()
        for et in ets:
            if et.relationship == "out":
                stage = self.process_type
                order = last_commitment.independent_demand
            else:
                stage = last_process.process_type
                order = None
            ct = self.add_commitment(
                resource_type=last_commitment.resource_type,
                demand=last_commitment.independent_demand,
                order_item=last_commitment.order_item,
                order=order,
                description="",
                quantity=last_commitment.quantity,
                event_type=et,
                unit=last_commitment.unit_of_quantity,
                user=user,
                stage=stage,
            )

    def insert_stream_commitments(self, last_process, user): #for inserting in order (not first and not last process in order)
        last_commitment = last_process.main_outgoing_commitment()
        ets = self.process_pattern.change_event_types()
        for et in ets:
            if et.relationship == "out":
                stage = self.process_type
            else:
                stage = last_process.process_type
            ct = self.add_commitment(
                resource_type=last_commitment.resource_type,
                demand=last_commitment.independent_demand,
                order_item=last_commitment.order_item,
                quantity=last_commitment.quantity,
                description="",
                event_type=et,
                unit=last_commitment.unit_of_quantity,
                user=user,
                stage=stage,
            )

    def insert_first_stream_commitments(self, next_commitment, user): #for inserting as first process in order
        ets = self.process_pattern.change_event_types()
        for et in ets:
            if et.relationship == "out":
                stage = self.process_type
            else:
                stage = None
            ct = self.add_commitment(
                resource_type=next_commitment.resource_type,
                demand=next_commitment.independent_demand,
                order_item=next_commitment.order_item,
                quantity=next_commitment.quantity,
                event_type=et,
                description="",
                unit=next_commitment.unit_of_quantity,
                user=user,
                stage=stage,
            )

    def change_context_agent(self, context_agent):
        self.context_agent = context_agent
        self.save()
        for commit in self.commitments.all():
            commit.context_agent = context_agent
            commit.save()
        for event in self.events.all():
            event.context_agent = context_agent
            event.save()

    def explode_demands(self, demand, user, visited, inheritance):
        """This method assumes the output commitment from this process

            has already been created.

        """
        #todo pr: may need get and use RecipeInheritance object
        pt = self.process_type
        output = self.main_outgoing_commitment()
        order_item = output.order_item
        #if not output:
        visited_id = output.cycle_id()
        if visited_id not in visited:
            visited.append(visited_id)
        for ptrt in pt.all_input_resource_type_relationships():
            if output.stage:
                #if output.resource_type == ptrt.resource_type:
                qty = output.quantity
            else:
                multiplier = output.quantity
                if output.process:
                    if output.process.process_type:
                        main_ptr = output.process.process_type.main_produced_resource_type_relationship()
                        if main_ptr:
                            if main_ptr.quantity:
                                multiplier = output.quantity / main_ptr.quantity
                qty = (multiplier * ptrt.quantity).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                #todo: must consider ratio of PT output qty to PT input qty
            #pr changed
            resource_type = ptrt.resource_type
            #todo dhen: this is where species would be used
            if inheritance:
                if resource_type == inheritance.parent:
                    resource_type = inheritance.substitute(resource_type)
                else:
                    resource_class = output.resource_type.resource_class
                    candidate = resource_type.child_of_class(resource_class)
                    if candidate:
                        resource_type = candidate
            #Todo: apply selected_context_agent here? Dnly if inheritance?
            commitment = self.add_commitment(
                resource_type=resource_type,
                demand=demand,
                description=ptrt.description or "",
                order_item=order_item,
                stage=ptrt.stage,
                state=ptrt.state,
                quantity=qty,
                event_type=ptrt.event_type,
                unit=resource_type.directional_unit(ptrt.event_type.relationship),
                user=user,
            )
            #cycles broken here
            #flow todo: consider order_item for non-substitutables?
            # seemed to work without doing that...?
            visited_id = ptrt.cycle_id()
            if visited_id not in visited:
                visited.append(visited_id)
                qty_to_explode = commitment.net()
                if qty_to_explode:
                    #todo: shd commitment.generate_producing_process?
                    #no, this an input commitment
                    #shd pt create process?
                    #shd pptr create next_commitment, and then
                    #shd next_commitment.generate_producing_process?
                    #pr changed
                    stage = commitment.stage
                    state = commitment.state
                    pptr, inheritance = resource_type.main_producing_process_type_relationship(stage=stage, state=state)
                    if pptr:
                        resource_type = pptr.resource_type
                        #todo dhen: this is where species would be used? Or not?
                        if inheritance:
                            if resource_type == inheritance.parent:
                                resource_type = inheritance.substitute(resource_type)
                        next_pt = pptr.process_type
                        start_date = self.start_date - datetime.timedelta(minutes=next_pt.estimated_duration)
                        next_process = Process(
                            name=next_pt.name,
                            notes=next_pt.description or "",
                            process_type=next_pt,
                            process_pattern=next_pt.process_pattern,
                            #Todo: apply selected_context_agent here? Dnly if inheritance?
                            context_agent=next_pt.context_agent,
                            url=next_pt.url,
                            end_date=self.start_date,
                            start_date=start_date,
                            plan=demand,
                        )
                        next_process.save()
                        #this is the output commitment
                        if output.stage:
                            qty = output.quantity
                        else:
                            #todo: this makes no sense, why did I do that?
                            #temporary insanity or some reason that escapes me now?
                            #ps. prior to this commented-out code, it was
                            #qty = qty_to_explode * pptr.quantity
                            #I did this when making that salsa recipe work.
                            #2014-11-05
                            #if not multiplier:
                            #    multiplier = pptr.quantity
                            #qty = (qty_to_explode * multiplier).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                            qty = qty_to_explode
                        #todo: must consider ratio of PT output qty to PT input qty
                        #Todo: apply selected_context_agent here? Dnly if inheritance?
                        next_commitment = next_process.add_commitment(
                            resource_type=resource_type,
                            stage=pptr.stage,
                            state=pptr.state,
                            demand=demand,
                            order_item=order_item,
                            quantity=qty,
                            event_type=pptr.event_type,
                            unit=resource_type.directional_unit(pptr.event_type.relationship),
                            description=pptr.description or "",
                            user=user,
                        )
                        #todo pr: may need pass RecipeInheritance object
                        next_process.explode_demands(demand, user, visited, inheritance)

    def reschedule_forward(self, delta_days, user):
        if not self.started:
            fps = self.previous_processes()
            if fps:
                slack =  99999
                for fp in fps:
                    slax = self.start_date - fp.end_date
                    slack = min(slack, slax.days)
                slack = max(slack, 0)
                delta_days -= slack
                delta_days = max(delta_days, 0)
                #munge for partial days
                delta_days += 1
        if delta_days:
            if self.started:
                if not self.end_date:
                    self.end_date = self.started + datetime.timedelta(minutes=self.estimated_duration)
                self.end_date = self.end_date + datetime.timedelta(days=delta_days)
            else:
                self.start_date = self.start_date + datetime.timedelta(days=delta_days)
                if self.end_date:
                    self.end_date = self.end_date + datetime.timedelta(days=delta_days)
                else:
                    self.end_date = self.start_date + datetime.timedelta(minutes=self.estimated_duration)
            self.changed_by = user
            self.save()
            self.reschedule_connections(delta_days, user)

    def reschedule_connections(self, delta_days, user):
        for ct in self.incoming_commitments():
            ct.reschedule_forward(delta_days, user)
        for ct in self.outgoing_commitments():
            ct.reschedule_forward(delta_days, user)
        for p in self.next_processes():
            p.reschedule_forward(delta_days, user)

    def too_late(self):
        if self.started:
            if self.finished:
                return False
            else:
                return self.end_date < datetime.date.today()
        else:
            return self.start_date < datetime.date.today()

    def bumped_processes(self):
        return [p for p in self.next_processes() if self.end_date > p.start_date]

    def plan_form_prefix(self):
        return "-".join(["PCF", str(self.id)])

    def schedule_form(self):
        from valuenetwork.valueaccounting.forms import ScheduleProcessForm
        init = {"start_date": self.start_date, "end_date": self.end_date, "notes": self.notes}
        return ScheduleProcessForm(prefix=str(self.id),initial=init)

    def plan_change_form(self):
        from valuenetwork.valueaccounting.forms import PlanProcessForm
        init = {"start_date": self.start_date, "end_date": self.end_date, "name": self.name}
        return PlanProcessForm(prefix=self.plan_form_prefix(),initial=init)

    def insert_process_form(self):
        from valuenetwork.valueaccounting.forms import WorkflowProcessForm
        init = {"start_date": self.start_date, "end_date": self.start_date}
        return WorkflowProcessForm(prefix=str(self.id),initial=init, order_item=self.order_item())

    def roll_up_value(self, path, depth, visited):
        #process method
        #todo rollup
        #Value_per_unit will be the result of this method.
        depth += 1
        self.depth = depth
        #self.explanation = "Value per unit consists of all the input values on the next level"
        path.append(self)
        process_value = Decimal("0.0")
        #Values of all of the inputs will be added to this list.
        values = []
        citations = []
        production_value = Decimal("0.0")

        production_qty = self.production_quantity()
        if production_qty:
            inputs = self.incoming_events()
            for ip in inputs:
                #Work contributions use resource_type.value_per_unit
                if ip.event_type.relationship == "work":
                    ip.value = ip.quantity * ip.value_per_unit()
                    ip.save()
                    process_value += ip.value
                    ip.depth = depth
                    path.append(ip)
                #Use contributions use resource value_per_unit_of_use.
                elif ip.event_type.relationship == "use":
                    if ip.resource:
                        #price changes
                        if ip.price:
                            ip.value = ip.price
                        else:
                            ip.value = ip.quantity * ip.resource.value_per_unit_of_use
                        ip.save()
                        process_value += ip.value
                        ip.resource.roll_up_value(path, depth, visited)
                        ip.depth = depth
                        path.append(ip)
                #Consume contributions use resource rolled up value_per_unit
                elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                    ip.depth = depth
                    path.append(ip)
                    if ip.resource:
                        value_per_unit = ip.resource.roll_up_value(path, depth, visited)
                        ip.value = ip.quantity * value_per_unit
                        ip.save()
                        process_value += ip.value
                #Citations valued later, after all other inputs added up
                elif ip.event_type.relationship == "cite":
                    ip.depth = depth
                    path.append(ip)
                    if ip.resource_type.unit_of_use:
                        if ip.resource_type.unit_of_use.unit_type == "percent":
                            citations.append(ip)
                    else:
                        ip.value = ip.quantity
                    if ip.resource:
                        ip.resource.roll_up_value(path, depth, visited)
        if process_value:
            #These citations use percentage of the sum of other input values.
            for c in citations:
                percentage = c.quantity / 100
                c.value = process_value * percentage
                c.save()
            for c in citations:
                process_value += c.value
        return process_value


    def compute_income_shares(self, value_equation, order_item, quantity, events, visited):
        #Process method
        #print("running quantity:", quantity, "running value:", value)
        if self not in visited:
            visited.add(self)
            if quantity:
                #todo: how will this work for >1 processes producing the same resource?
                #what will happen to the shares of the inputs of the later processes?
                production_events = self.production_events()
                produced_qty = sum(pe.quantity for pe in production_events)
                distro_fraction = 1
                distro_qty = quantity
                if produced_qty > quantity:
                    distro_fraction = quantity / produced_qty
                    quantity = Decimal("0.0")
                elif produced_qty <= quantity:
                    distro_qty = produced_qty
                    quantity -= produced_qty
                for pe in production_events:
                    #todo br
                    value = pe.quantity
                    br = pe.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(pe)
                    pe.share = value * distro_fraction
                    events.append(pe)
                if self.context_agent.compatible_value_equation(value_equation):
                    inputs = self.incoming_events()
                    for ip in inputs:
                        #we assume here that work events are contributions
                        if ip.event_type.relationship == "work":
                            if ip.is_contribution:
                                #todo br
                                value = ip.value
                                br = ip.bucket_rule(value_equation)
                                if br:
                                    value = br.compute_claim_value(ip)
                                    ip.value = value
                                ip.share = value * distro_fraction
                                events.append(ip)
                                #print(ip.id, ip, ip.share)
                                #print("----Event.share:", ip.share, "= Event.value:", ip.value, "* distro_fraction:", distro_fraction)
                        elif ip.event_type.relationship == "use":
                            #use events are not contributions, but their resources may have contributions
                            if ip.resource:
                                #price changes
                                if ip.price:
                                    ip.value = ip.price
                                else:
                                    ip.value = ip.quantity * ip.resource.value_per_unit_of_use
                                value = ip.value
                                ip_value = value * distro_fraction
                                d_qty = distro_qty
                                if ip_value and value:
                                    d_qty = ip_value / value
                                new_visited = set()
                                path = []
                                depth = 0
                                #todo exchange redesign fallout
                                #resource_value was 0
                                resource_value = ip.resource.roll_up_value(path, depth, new_visited, value_equation)
                                ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)
                        elif ip.event_type.relationship == "consume" or ip.event_type.name == "To Be Changed":
                            #consume events are not contributions, but their resources may have contributions
                            ##todo ve test: is this a bug? how does consumption event value get set?
                            #ip_value = ip.value * distro_fraction
                            #if ip_value:
                            d_qty = ip.quantity * distro_fraction
                            if d_qty:
                                #print("consumption:", ip.id, ip, "ip.value:", ip.value)
                                #print("----value:", ip_value, "d_qty:", d_qty, "distro_fraction:", distro_fraction)
                                if ip.resource:
                                    ip.resource.compute_income_shares(value_equation, d_qty, events, visited)
                        elif ip.event_type.relationship == "cite":
                            #citation events are not contributions, but their resources may have contributions
                            #ip_value = ip.value * distro_fraction
                            #if ip_value:
                            #    d_qty = ip_value / value
                            #    if ip.resource:
                            #        ip.resource.compute_income_shares(value_equation, d_qty, events, visited)
                            if ip.resource:
                                value = ip.value
                                ip_value = value * distro_fraction
                                d_qty = distro_qty
                                if ip_value and value:
                                    d_qty = ip_value / value
                                new_visited = set()
                                path = []
                                depth = 0
                                resource_value = ip.resource.roll_up_value(path, depth, new_visited, value_equation)
                                ip.resource.compute_income_shares_for_use(value_equation, ip, ip_value, resource_value, events, visited)


#from general.models import Material_Type, Nonmaterial_Type, Artwork_Type

class TransferType(models.Model):
    name = models.CharField(_('name'), max_length=128)
    sequence = models.IntegerField(_('sequence'), default=0)
    exchange_type = models.ForeignKey(ExchangeType,
        verbose_name=_('exchange type'), related_name='transfer_types', on_delete=models.CASCADE)
    description = models.TextField(_('description'), blank=True, null=True)
    is_contribution = models.BooleanField(_('is contribution'), default=False)
    is_to_distribute = models.BooleanField(_('is to distribute'), default=False)
    is_reciprocal = models.BooleanField(_('is reciprocal'), default=False)
    can_create_resource = models.BooleanField(_('can create resource'), default=False)
    is_currency = models.BooleanField(_('is currency'), default=False)
    give_agent_is_context = models.BooleanField(_('give agent is context'), default=False)
    receive_agent_is_context = models.BooleanField(_('receive agent is context'), default=False)
    give_agent_association_type = models.ForeignKey(AgentAssociationType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('give agent association type'), related_name='transfer_types_give')
    receive_agent_association_type = models.ForeignKey(AgentAssociationType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('receive agent association type'), related_name='transfer_types_receive')
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='transfer_types_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='transfer_types_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    inherit_types = models.BooleanField(_('inherit resource types'), default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('sequence',)

    def is_deletable(self):
        if self.transfers.all():
            return False
        return True

    def facets(self):
        facets = [ttfv.facet_value.facet for ttfv in self.facet_values.all()]
        return list(set(facets))

    def get_resource_types(self):
        answer_ids = []
        if self.inherit_types:
            # TODO
            try:
              if hasattr(self.exchange_type, 'ocp_record_type'):
                oet = self.exchange_type.ocp_record_type
                if hasattr(oet, 'ocpRecordType_ocp_artwork_type'):
                  ort = oet.ocpRecordType_ocp_artwork_type
                  if ort:
                     from work.models import Ocp_Artwork_Type
                     orts = Ocp_Artwork_Type.objects.filter(lft__gte=ort.lft, rght__lte=ort.rght, tree_id=ort.tree_id)
                     answer_ids = [rt.resource_type.id for rt in orts]
                     answer = EconomicResourceType.objects.filter(id__in=answer_ids)
                     if answer:
                        return answer
                     else:
                        raise ValidationError("get_resource_types of "+str(self)+" are not found by rt.ids: "+str(answer_ids)+" of tree: "+str(orts))
            except:
               pass

        tt_facet_values = self.facet_values.all()
        facet_values = [ttfv.facet_value for ttfv in tt_facet_values]
        facets = {}
        for fv in facet_values:
            if fv.facet not in facets:
                facets[fv.facet] = []
            facets[fv.facet].append(fv.value)

        fv_ids = [fv.id for fv in facet_values]
        rt_facet_values = ResourceTypeFacetValue.objects.filter(facet_value__id__in=fv_ids)

        rts = {}
        for rtfv in rt_facet_values:
            rt = rtfv.resource_type
            if rt not in rts:
                rts[rt] = []
            rts[rt].append(rtfv.facet_value)

        matches = []

        for rt, facet_values in list(rts.items()):
            match = True
            for facet, values in list(facets.items()):
                rt_fv = [fv for fv in facet_values if fv.facet == facet]
                if rt_fv:
                    rt_fv = rt_fv[0]
                    if rt_fv.value not in values:
                        match = False
                else:
                    match = False
            if match:
                matches.append(rt)

        answer_ids = [a.id for a in matches]
        answer = EconomicResourceType.objects.filter(id__in=answer_ids)
        return answer

    def to_agents(self, context_agent):
        if self.receive_agent_association_type:
            return context_agent.has_associates_self_or_inherited(self.receive_agent_association_type.identifier)
        else:
            return EconomicAgent.objects.all()

    def to_context_agents(self, context_agent):
        if self.receive_agent_association_type:
            return context_agent.has_associates_self_or_inherited(self.receive_agent_association_type.identifier)
        else:
            return context_agent.related_all_agents_queryset() #EconomicAgent.objects.all()

    def from_agents(self, context_agent):
        if self.give_agent_association_type:
            return context_agent.has_associates_self_or_inherited(self.give_agent_association_type.identifier)
        else:
            return EconomicAgent.objects.all()

    def from_context_agents(self, context_agent):
        if self.give_agent_association_type:
            return context_agent.has_associates_self_or_inherited(self.give_agent_association_type.identifier)
        else:
            return context_agent.related_all_agents_queryset() #EconomicAgent.objects.all()

    def is_incoming(self, exchange, context_agent):
        transfers = exchange.transfers.all()
        jn_req = None
        ttpay = exchange.ttpay()
        if hasattr(exchange, 'join_request') and exchange.join_request:
            jn_req = exchange.join_request
        mem = None
        self.is_income = None
        #print("-tt.is_incoming... ex:"+str(exchange.id)+" tt:"+str(self.id))
        if transfers:
          for tx in transfers:
            if tx.transfer_type == self:
              if tx.to_agent() == context_agent:
                #print("- found agent in tx.to ! tx:"+str(tx.id)+" ag:"+str(context_agent))
                self.is_income = True
                return True
              elif tx.from_agent() == context_agent:
                #print("- found agent in tx.from ! tx:"+str(tx.id)+" ag:"+str(context_agent))
                self.is_income = False
                return False
              else:
                if jn_req:
                    if context_agent == jn_req.agent:
                        if self == ttpay:
                            self.is_income = False
                            return False
                        else:
                            self.is_income = True
                            return True
                    elif context_agent == jn_req.project.agent:
                        if self == ttpay:
                            self.is_income = True
                            return True
                        else:
                            self.is_income = False
                            return False
                    else:
                        print("WARNING context_agent not related the ex.jn_req ?? self(tt):"+str(self.id)+" ex:"+str(exchange.id)+" tx:"+str(tx.id)+" jn_req:"+str(jn_req))
                        loger.info("WARNING context_agent not related the ex.jn_req ?? self(tt):"+str(self.id)+" ex:"+str(exchange.id)+" tx:"+str(tx.id)+" jn_req:"+str(jn_req))
                else:
                    print("... NOT FOUND to or from or jr, ca:"+str(context_agent)+" ex:"+str(exchange.id)+" slot:"+str(self.id)+" tx:"+str(tx.id)+" cms:"+str(len(tx.commitments.all()))+" evs:"+str(len(tx.events.all()))+" "+str(tx))
                    loger.info("... NOT FOUND to or from or jr, ca:"+str(context_agent)+" ex:"+str(exchange.id)+" slot:"+str(self.id)+" tx:"+str(tx.id)+" "+str(tx))
            elif not mem:
                #print("... set mem: "+str(tx.id)+" tt:"+str(tx.transfer_type.id)+" self:"+str(self.id))
                mem = tx
          #if mem:
            #if not mem.is_income == None: # and mem.transfer_type.is_income: #ing(exchange, context_agent): #is_reciprocal:
              #print("- found mem, return False? self:"+str(self.id)+" mem:"+str(mem.id)+" tt:"+str(mem.transfer_type.id)) #+" inco:"+str(mem.transfer_type.is_income)

              #return False
          #else: #if mem:
          #  print("- not found mem, return True ? self:"+str(self.id))
            #return True
        else:
            print("WARN tt:"+str(self.id)+" related exchange without transfers ?? ex:"+str(exchange.id))
            loger.info("WARN tt:"+str(self.id)+" related exchange without transfers ?? ex:"+str(exchange.id))

        print("- not to or from, return is_reciprocal ? "+str(self.is_reciprocal)+" tt(id):"+str(self.id)+" ex:"+str(exchange.id))
        loger.info("- not to or from, return is_reciprocal ? "+str(self.is_reciprocal)+" tt(id):"+str(self.id)+" ex:"+str(exchange.id))
        return self.is_reciprocal

    def is_share(self):
        rel_typ = None
        if self.inherit_types:
            if self.exchange_type.ocp_record_type:
                if self.exchange_type.ocp_record_type.ocpRecordType_ocp_artwork_type:
                    rel_typ = self.exchange_type.ocp_record_type.ocpRecordType_ocp_artwork_type
                    return rel_typ.is_share()

        return rel_typ

    def form_prefix(self):
        return "-".join(["TT", str(self.id)])

    def change_form(self):
        from valuenetwork.valueaccounting.forms import TransferTypeForm
        prefix=self.form_prefix()
        return TransferTypeForm(instance=self, prefix=prefix)

    def show_name(self, agent=None, forced=False):
        name = self.__str__()
        newname = name
        if agent:
          if self.transfers:
            gives = self.transfers.filter(events__from_agent=agent)
            if not gives:
                gives = self.transfers.filter(commitments__from_agent=agent)
            if not gives:
                gives = forced
            takes = self.transfers.filter(events__to_agent=agent)
            if not takes:
                takes = self.transfers.filter(commitments__to_agent=agent)
            if not takes:
                takes = forced

            if hasattr(self.exchange_type, 'ocp_record_type') and self.exchange_type.ocp_record_type:
                x_actions = self.exchange_type.ocp_record_type.x_actions()
                for action in x_actions:
                    opposite = action.opposite()
                    if opposite:
                        if takes and action.clas == 'give':
                            if action.clas and opposite.clas:
                                newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                            if name == newname:
                                newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                            if not name == newname:
                                name = newname
                                break
                        if gives and action.clas == 'receive':
                            if action.clas and opposite.clas:
                                newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                            if name == newname:
                                newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                            if not name == newname:
                                name = newname
                                break
                    #import pdb; pdb.set_trace()
        return name



class TransferTypeFacetValue(models.Model):
    transfer_type = models.ForeignKey(TransferType,
        verbose_name=_('transfer type'), related_name='facet_values', on_delete=models.CASCADE)
    facet_value = models.ForeignKey(FacetValue,
        verbose_name=_('facet value'), related_name='transfer_types', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('transfer_type', 'facet_value')
        ordering = ('transfer_type', 'facet_value')

    def __str__(self):
        return ": ".join([self.transfer_type.name, self.facet_value.facet.name, self.facet_value.value])


class ExchangeManager(models.Manager):


    def demand_exchanges(self, start=None, end=None):
        if start and end:
            exchanges = Exchange.objects.filter(use_case__identifier="demand_xfer").filter(start_date__range=[start, end])
        else:
            exchanges = Exchange.objects.filter(use_case__identifier="demand_xfer")
        #exchs = list(exchanges)
        #exchs.sort(key=lambda x: x.start_date, reverse=True)
        #return exchs
        return exchanges

    def supply_exchanges(self, start=None, end=None):
        if start and end:
            exchanges = Exchange.objects.filter(use_case__identifier="supply_xfer").filter(start_date__range=[start, end])
        else:
            exchanges = Exchange.objects.filter(use_case__identifier="supply_xfer")
        #exchs = list(exchanges)
        #exchs.sort(key=lambda x: x.start_date, reverse=True)
        #return exchs
        return exchanges

    def internal_exchanges(self, start=None, end=None):
        if start and end:
            exchanges = Exchange.objects.filter(use_case__identifier="intrnl_xfer").filter(start_date__range=[start, end])
        else:
            exchanges = Exchange.objects.filter(use_case__identifier="intrnl_xfer")
        return exchanges

    def exchanges_by_date_and_context(self, start, end, agent, exchanges_by_type=None):
        if not exchanges_by_type:
            exchanges_by_type = self.exchanges_by_type(agent)

        count = len(exchanges_by_type)
        #print("- ebdan start: "+str(start)+" end: "+str(end)+" agent: "+str(agent.id)+" exs: "+str(count))

        exs_bdc = exchanges_by_type.filter(start_date__range=[start, end]).order_by('created_date')
        count2 = len(exs_bdc)
        if not count == count2:
            print("- filtered exchanges_by_date_and_context start: "+str(start)+" end: "+str(end)+" agent: "+str(agent)+" count: "+str(count)+" count2: "+str(count2))

        return exs_bdc

    def exchanges_by_type(self, agent):
        agids = [c.id for c in agent.related_contexts()]
        agids2 = agids[:]
        if not agent.id in agids:
            agids.append(agent.id)
        if agent.id in agids2:
            agids2.remove(agent.id)
        otheragids = [c.id for c in EconomicAgent.objects.all().exclude(id__in=agids)]
        print("- ebt agent: "+str(agent)+" ("+str(agent.id)+") context:"+str(agent.is_context)+" agids2: "+str(agids2))

        exs_bt = Exchange.objects.filter(
          Q(transfers__events__isnull=True, transfers__commitments__isnull=True, context_agent__isnull=False, context_agent__id=agent.id) |
          Q(transfers__events__isnull=True, transfers__commitments__isnull=True, exchange_type__context_agent__isnull=False, exchange_type__context_agent__id=agent.id) |
          Q(transfers__events__isnull=False, transfers__events__from_agent__isnull=False, transfers__events__from_agent=agent) |
          Q(transfers__events__isnull=False, transfers__events__to_agent__isnull=False, transfers__events__to_agent=agent) |
          Q(transfers__commitments__isnull=False, transfers__commitments__from_agent__isnull=False, transfers__commitments__from_agent=agent) |
          Q(transfers__commitments__isnull=False, transfers__commitments__to_agent__isnull=False, transfers__commitments__to_agent=agent)
        ).distinct().order_by('exchange_type', 'created_date') #.exclude(
            #~Q(exchange_type__context_agent__isnull=False, exchange_type__context_agent=agent),
            #~Q(context_agent__isnull=False, context_agent__id__in=agids)
        #).order_by(Lower('exchange_type__ocp_record_type__name').asc())

        # bum2: This filter seems not enough (why? its still a MISTERY !?) so we create the id list to exclude exts, depending on is_context

        count = len(exs_bt)
        if agent.is_context:
            #print("- ebt context: "+str(agent)+" 1 exs:"+str(count))
            exs_bt2 = exs_bt.exclude(
                ~Q(exchange_type__context_agent__isnull=False, exchange_type__context_agent=agent),
            #    Q(context_agent__isnull=False, context_agent__id__in=agids2) |
            #    Q(exchange_type__context_agent__isnull=False, exchange_type__context_agent__id__in=agids2)
            ) #.order_by('-start_date')
            count2 = len(exs_bt2)
            if not count == count2:
                print("- filtered exchanges_by_type context: "+str(agent)+" count1:"+str(count)+" count2: "+str(count2))
                if count2:
                    exs_bt = exs_bt2
        else:
            #print("- ebt individual: "+str(agent)+" exs:"+str(count))
            exs_bt = exs_bt.exclude(
                Q(transfers__isnull=True, context_agent__isnull=False, context_agent__id__in=agids2) |
                #Q(transfers__events__isnull=True, transfers__commitments__isnull=True,
                Q(exchange_type__context_agent__isnull=False, exchange_type__context_agent__id__in=otheragids) |
                #Q(transfers__events__isnull=True, transfers__commitments__isnull=True,
                Q(context_agent__isnull=False, context_agent__id__in=otheragids)
            ) #.order_by('-start_date')
            count2 = len(exs_bt)
            if not count == count2:
                print("- filtered exchanges_by_type individual: "+str(agent)+" count:"+str(count)+" coun2: "+str(count2))

        return exs_bt #.order_by(Lower('exchange_type__ocp_record_type__name').asc())


class Exchange(models.Model):
    name = models.CharField(_('name'), blank=True, max_length=128)
    process_pattern = models.ForeignKey(ProcessPattern,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('pattern'), related_name='exchanges')
    use_case = models.ForeignKey(UseCase,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('use case'), related_name='exchanges')
    exchange_type = models.ForeignKey(ExchangeType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('exchange type'), related_name='exchanges')
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='exchanges')
    url = models.CharField(_('url'), max_length=255, blank=True, null=True)
    start_date = models.DateField(_('start date'))
    notes = models.TextField(_('notes'), blank=True)
    supplier = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="exchanges_as_supplier", verbose_name=_('supplier'))
    customer = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="exchanges_as_customer", verbose_name=_('customer'))
    order = models.ForeignKey(Order,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="exchanges", verbose_name=_('order'))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='exchanges_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='exchanges_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = ExchangeManager()

    class Meta:
        ordering = ('-start_date',)
        verbose_name_plural = _("exchanges")

    def __str__(self):
        show_name = ""
        name = ""
        if False and self.name:
            name = self.name
        else:
            if self.customer:
                name = self.customer.nick
            if self.exchange_type:
                if hasattr(self.exchange_type, 'ocp_record_type') and self.exchange_type.ocp_record_type:
                    show_name = str(self.exchange_type.ocp_record_type.name)
                else:
                    show_name = self.exchange_type.name
            else:
                if self.use_case:
                    show_name = self.use_case.name
        return " ".join([
            name,
            show_name,
            str(_("from")),
            self.start_date.strftime('%Y-%m-%d'),
            ])

    def get_absolute_url(self):
        return reverse('exchange_logging', kwargs={
            'exchange_type_id': "0",
            'exchange_id': str(self.id),
        })

    def save(self, *args, **kwargs):
        ext_name = ""
        #if self.exchange_type:
        #    ext_name = self.exchange_type.name
        slug = "-".join([
            self.name,
            self.start_date.strftime('%Y-%m-%d'),
        ])
        unique_slugify(self, slug)
        super(Exchange, self).save(*args, **kwargs)

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    @property #ValueFlows
    def planned_start(self):
        return self.start_date.isoformat()

    @property #ValueFlows
    def note(self):
        return self.notes

    def class_label(self):
        return "Exchange"

    def is_deletable(self):
        answer = True
        if self.events.all():
            answer = False
        if self.transfers.all():
            answer = False
        #elif self.resources.all():
        #    answer = False
        #elif self.commitments.all():
        #    answer = False
        return answer

    def txpay(self):
        ttpay = self.ttpay()
        txpay = None
        for tx in self.transfers.all():
            if tx.transfer_type == ttpay:
                txpay = tx
        return txpay

    def ttpay(self):
        ttpay = None
        for tt in self.exchange_type.transfer_types.all():
            if tt.is_currency:
                ttpay = tt
        return ttpay

    def slots_with_detail(self, context_agent=None):
        slots = self.exchange_type.transfer_types.all()
        slots = list(slots)
        memslot = None
        int_usecase = UseCase.objects.get(identifier="intrnl_xfer")
        transfers = self.transfers.all()
        default_to_agent = None
        default_from_agent = None
        for transfer in transfers:
            if transfer.transfer_type not in slots:
                slots.append(transfer.transfer_type)
            if not default_to_agent:
                if transfer.is_reciprocal():
                    default_to_agent = transfer.from_agent()
                else:
                    default_to_agent = transfer.to_agent()
            if not default_from_agent:
                if transfer.is_reciprocal():
                    default_from_agent = transfer.to_agent()
                else:
                    default_from_agent = transfer.from_agent()
        ttpay = self.ttpay()
        jn_req = None
        receive = False
        if hasattr(self, 'join_request') and self.join_request:
            jn_req = self.join_request
            if context_agent:
                if jn_req.project.agent == context_agent:
                    receive = True

        self.statuss = 'complete'
        for slot in slots:
            slot.xfers = []
            slot.agents_to = []
            slot.agents_from = []
            slot.total = 0
            slot.total_unit = None
            slot.total_com = 0
            slot.total_com_unit = None
            slot.rts = []
            slot.hours = False
            slot.last_date = None
            for transfer in transfers:
                if transfer.transfer_type == slot:
                    rt = transfer.resource_type()
                    slot.xfers.append(transfer)
                    slot.last_date = transfer.last_date()
                    acval = transfer.actual_value(receive)
                    valunit = transfer.unit_of_value()
                    acqua = transfer.actual_quantity(receive)
                    quaunit = transfer.unit_of_quantity()

                    if acval:
                        slot.total += acval
                        slot.total_unit = valunit
                    elif acqua:
                        slot.total += acqua
                        slot.total_unit = quaunit
                    val = transfer.value(receive)
                    if val:
                        if slot.is_currency:
                            if acval > val:
                                val = acval
                                print("- changed val for acval!")
                            slot.total_com += val
                            slot.total_com_unit = valunit
                        else:
                            print("-- found value "+str(val)+" "+str(valunit)+" but not slot.is_currency, SKIP! ex:"+str(self.id)+" slot:"+str(slot.id)+" "+str(slot))
                            loger.info("-- found value "+str(val)+" "+str(valunit)+" but not slot.is_currency, SKIP! ex:"+str(self.id)+" slot:"+str(slot.id)+" "+str(slot))
                    qua = transfer.quantity(receive)
                    if qua and not slot.total_com_unit:
                        if acqua > qua:
                            qua = acqua
                            print("- changed qua for acqua!")
                        slot.total_com += qua
                        slot.total_com_unit = quaunit
                        if not slot.total_com_unit:
                            if rt and not rt in slot.rts:
                                slot.rts.append(rt)

                    if slot.total_com_unit and slot.total_com_unit.name_en == 'Each':
                        slot.total_com_unit = ''
                        if rt and not rt in slot.rts:
                            slot.rts.append(rt)
                    if slot.total_com_unit and slot.total_com_unit.name_en == 'Hours':
                        #slot.total_com_unit = ''
                        slot.hours = True
                        if rt and not rt in slot.rts:
                            slot.rts.append(rt)


                    to = transfer.to_agent()
                    fro = transfer.from_agent()
                    if not to and jn_req:
                        if ttpay.name == slot.name:
                            to = jn_req.project.agent
                            prt = jn_req.payment_unit_rt()
                            if not prt == rt:
                                print("x pay to Change rt:"+str(rt)+" for payment_unit_rt:"+str(prt))
                                rt = prt
                            #slot.total_com = jn_req.total_price()
                            #slot.total_com_unit = ''
                        else:
                            to = jn_req.agent
                            prt = jn_req.project.shares_type()
                            if not prt == rt:
                                #print("x shr to Change rt:"+str(rt)+" for payment_unit_rt:"+str(prt))
                                rt = prt
                            if not receive:
                                slot.total_com = jn_req.payment_amount()
                                print("get the to payment_amount for the slot.total_com: "+str(slot.total_com))
                            slot.total_com_unit = '' # unit is set later because rt is defined
                    if not fro and jn_req:
                        if ttpay.name == slot.name:
                            fro = jn_req.agent
                            prt = jn_req.payment_unit_rt()
                            if not prt == rt:
                                print("x pay from Change rt:"+str(rt)+" for payment_unit_rt:"+str(prt))
                                rt = prt
                            #slot.total_com = jn_req.total_price()
                            #slot.total_com_unit = ''
                        else:
                            fro = jn_req.project.agent
                            prt = jn_req.project.shares_type()
                            if not prt == rt:
                                print("x shr from Change rt:"+str(rt)+" for payment_unit_rt:"+str(prt))
                                rt = prt
                            if not receive:
                                slot.total_com = jn_req.payment_amount()
                                print("get the fro payment_amount for the slot.total_com: "+str(slot.total_com))
                            slot.total_com_unit = ''

                    if not to in slot.agents_to:
                        slot.agents_to.append(to)
                    if not fro in slot.agents_from:
                        slot.agents_from.append(fro)

                    if not slot.total_com_unit:
                        if rt and not rt in slot.rts:
                            print("--- not total_com_unit, add rt:"+str(rt)+" in ex:"+str(self.id)+" slot:"+str(slot.id)+" "+str(slot))
                            slot.rts.append(rt)


            #if slot.total_com_unit and str(slot.total_com_unit) == 'Hours':
            #    print("Hours?"  #slot.total_com_unit = str(slot.total_com_unit)+' '+str(rt))
                #if rt and not rt in slot.rts:
                #    slot.rts.append(rt)


            if slot.rts:
              #print("- slot.rts:"+str(slot.rts))
              if len(slot.rts) > 1:
                print("-- multiple rts: "+str(len(slot.rts))+" for ex:"+str(self)+" slot:"+str(slot.id))
                par = None
                for t in slot.rts:
                    if hasattr(t, 'ocp_artwork_type') and t.ocp_artwork_type:
                        pare = t.ocp_artwork_type.parent

                        if not par:
                            par = pare
                        elif par.id == pare.id:
                            print("--- found parent: "+str(pare))
                            rtz = EconomicResourceType.objects.filter(ocp_artwork_type__id=par.id)
                            if rtz:
                                slot.total_com_unit = "<em>"+str(rtz[0])+"</em>"
                            else:
                                slot.total_com_unit = "<em>"+str(par)+"</em>"
              else:
                slot.total_com_unit = slot.rts[0]
                if hasattr(slot.total_com_unit, 'ocp_artwork_type') and slot.total_com_unit.ocp_artwork_type.is_account():
                    print("--- is account, change slot_com_unit to:"+str(slot.rts[0].unit)+" ex:"+str(self.id)+" slot:"+str(slot.id))
                    slot.total_com_unit = slot.rts[0].unit
                else:
                    if slot.hours:
                        slot.total_com_unit = str(_('hour'))+('s' if slot.total_com > 1 else '')+str(_(' of '))+str(slot.rts[0])
                    else:
                        pass #print("--- not account "+str(slot.total_com_unit))
                #print("-- found one rt:"+str(rt))
            elif slot.total_unit and not slot.total_com_unit:
                slot.total_com_unit = slot.total_unit
            elif hasattr(self, 'join_request'):
                pass #print(#"has jreq, is ok? "+str(self))
            else:
              print("- don't find rts? ex:"+str(self.id)+" slot:"+str(slot.id)+" "+str(slot)+" tot:"+str(slot.total)+" tot_com:"+str(slot.total_com)+" com_unit:"+str(slot.total_com_unit))
              loger.info("- don't find rts? ex:"+str(self.id)+" slot:"+str(slot.id)+" "+str(slot)+" tot:"+str(slot.total)+" tot_com:"+str(slot.total_com)+" com_unit:"+str(slot.total_com_unit))

            if not memslot:
              if slot.is_incoming(self, context_agent): #is_reciprocal:
                slot.default_from_agent = default_to_agent
                slot.default_to_agent = context_agent #default_from_agent
                #print("- slot.is_incoming True, force is_income ? "+str(slot.id))
                slot.is_income = True
              else:
                slot.default_from_agent = context_agent #default_from_agent
                slot.default_to_agent = default_to_agent
                #print("- slot.is_incoming False, force is_income ? "+str(slot.id))
                slot.is_income = False
            else:
                #print("- Flag is_income as oposite of memslot for slot:"+str(slot.id)+" memslot:"+str(memslot.id))
                if memslot.is_income:
                    slot.is_income = False
                else:
                    slot.is_income = True
                slot.default_from_agent = memslot.default_to_agent
                slot.default_to_agent = memslot.default_from_agent

            if slot.is_currency and self.exchange_type.use_case != int_usecase:
                if not slot.give_agent_is_context:
                    slot.default_from_agent = None #logged on agent
                if not slot.receive_agent_is_context:
                    slot.default_to_agent = None #logged on agent

            #print("ex:"+str(self.id)+" slot:"+str(slot.id)+" is_income:"+str(slot.is_income)+" reci:"+str(slot.is_reciprocal)+" memslot:"+str(memslot))

            slot.total = remove_exponent(slot.total)
            slot.total_com = remove_exponent(slot.total_com)
            if slot.total_com_unit and isinstance(slot.total_com_unit, Unit) and slot.total_com_unit.abbrev in settings.CRYPTOS:
                if not self.status() == 'complete':
                    slot.total_com = ('\u2248\u00a0')+str(slot.total_com)

            memslot = slot
            pend = []
            for xf in slot.xfers:
              xf.statuss = xf.status()
              if xf.statuss == 'pending':
                pend.append(xf)
            if len(pend):
              slot.status = pend[0].statuss
            elif slot.xfers:
              slot.status = slot.xfers[0].statuss
            else:
              slot.status = 'empty'
            if not slot.status == 'complete':
                self.statuss = 'pending'
        return slots

    def show_name(self, agent=None, forced=False):
        name = self.__str__()
        if agent:
            name = name.replace(agent.name, '')
            name = name.replace(agent.nick+' ', '')
            print('show_name! '+str(agent.name))
            if agent.is_context and hasattr(agent, 'project'):
                print('show_name!')
                name = name.replace(agent.project.compact_name(), '')
        newname = None
        if forced:
            print(":: FORCED exchange show_name ex:"+str(self.id)+" "+str(self))
            loger.info(":: FORCED exchange show_name ex:"+str(self.id)+" "+str(self))
        trans = self.transfers.all()
        if len(trans) > 1:
            give_ts = self.transfers.filter( Q(events__isnull=False, events__from_agent=agent) |
                                            Q(commitments__isnull=False, commitments__from_agent=agent)
                                           ).exclude(transfer_type__is_currency=False)
            take_ts = self.transfers.filter( Q(events__isnull=False, events__to_agent=agent) |
                                            Q(commitments__isnull=False, commitments__to_agent=agent)
                                           ).exclude(transfer_type__is_currency=False)
            et_name = str(self.exchange_type)
            #action = ''
            #print("ex show_name ag:"+str(agent)+" give_ts:"+str(give_ts)+" take_ts:"+str(take_ts)+" et_name:"+str(et_name))
            if hasattr(self.exchange_type, 'ocp_record_type'):
                et_name = str(self.exchange_type.ocp_record_type)
                actions = self.exchange_type.ocp_record_type.x_actions()
                if actions:
                  for action in actions:
                    opposite = action.opposite()
                    if opposite:
                        if action.clas and opposite.clas:
                            newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                        if name == newname:
                            newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                        if take_ts or forced:
                            if action.clas == 'buy' or action.clas == 'receive':
                                name = newname
                        if give_ts or forced:
                            if action.clas == 'sell' or action.clas == 'give':
                                name = newname

                        #import pdb; pdb.set_trace()
                        #return str(action.clas)+' -> '+str(opposite.clas)+': '+name #+' GIVE: '+str(give_ts)+' - TAKE: '+str(take_ts)
        elif not trans:
            print("WARN Exchange has no transfers ?? ex:"+str(self.id)+" "+str(self))
            loger.info("WARN Exchange has no transfers ?? ex:"+str(self.id)+" "+str(self))
        return name

    def status(self):
        status = '??'
        arr = []
        trans = self.transfers.all()
        tts = self.exchange_type.transfer_types.all()
        for tr in trans:
          if 'pending' in tr.status() or 'empty' in tr.status():
            arr.append(tr)
        if len(arr) < 1 and trans: #len(self.transfers.all()):
            if len(tts) > len(trans):
                status = 'pending'
            else:
                status = trans[0].status() #arr[0] #'complete'
        elif arr:
          status = 'pending' #arr[0].status()
        else:
          status = 'empty'
        return status

    def has_reciprocal(self):
        slots = self.exchange_type.transfer_types.all()
        for slot in slots:
            if slot.is_reciprocal:
                return True
        return False

    def work_events(self):
        return self.events.filter(
            event_type__relationship='work')

    def all_events(self): # renamed from 'events' to avoid manager conflict
        events = self.events.all()
        for transfer in self.transfers.all():
            for event in transfer.events.all():
                if not event in events:
                    events.append(event)
                    print("event without direct exchange... id:"+str(event.id)+" "+str(event))
                    loger.info("event without direct exchange... id:"+str(event.id)+" "+str(event))
        return events

    def xfer_events(self): # the above function fails, so rename and works (now works)
        events = []
        for transfer in self.transfers.all():
            for event in transfer.events.all():
                events.append(event)
        return events

    def xfer_commitments(self):
        commits = []
        for transfer in self.transfers.all():
            for commit in transfer.commitments.all():
                commits.append(commit)
        return commits

    def transfer_events(self):
        #todo exchange redesign fallout?
        #obsolete? or just used wrong?
        #exchange method
        print("obsolete exchange.transfer_event?")
        events = []
        for transfer in self.transfers.all():
            if not transfer.is_reciprocal():
                for event in transfer.events.all():
                    events.append(event)
        return events

    def reciprocal_transfer_events(self):
        #todo exchange redesign fallout?
        #exchange method
        events = []
        for transfer in self.transfers.all():
            if transfer.is_reciprocal():
                for event in transfer.events.all():
                    events.append(event)
        return events

    def can_have_reciprocal_transfers(self):
        ext = self.exchange_type
        if ext.transfer_types_reciprocal():
            return True
        return False

    #todo:not tested
    def transfer_give_events(self):
        #not reciprocal
        events = []
        et_give = EventType.objects.get(name="Give")
        for transfer in self.transfers.all():
            if not transfer.is_reciprocal():
                for event in transfer.events.all():
                    if event.event_type == et_give:
                        events.append(event)
        return events

    #todo:not tested
    def transfer_receive_events(self):
        #not reciprocal
        events = []
        et_receive = EventType.objects.get(name="Receive")
        for transfer in self.transfers.all():
            if not transfer.is_reciprocal():
                for event in transfer.events.all():
                    if event.event_type == et_receive:
                        events.append(event)
        return events

    #todo:not tested
    def reciprocal_transfer_give_events(self):
        events = []
        et_give = EventType.objects.get(name="Give")
        for transfer in self.transfers.all():
            if transfer.is_reciprocal():
                for event in transfer.events.all():
                    if event.event_type == et_give:
                        events.append(event)
        return events

    def payment_events(self):
        events = self.reciprocal_transfer_give_events()
        return [evt for evt in events if evt.transfer.transfer_type.is_currency]

    #todo:not tested
    def reciprocal_transfer_receive_events(self):
        events = []
        et_receive = EventType.objects.get(name="Receive")
        for transfer in self.transfers.all():
            if transfer.is_reciprocal():
                for event in transfer.events.all():
                    if event.event_type == et_receive:
                        events.append(event)
        return events

    #todo: do we need these?  if not, delete
    #def uncommitted_transfer_events(self):
    #    return self.events.filter(
    #        event_type__name='Transfer',
    #        commitment=None)

    #def uncommitted_rec_transfer_events(self):
    #    return self.events.filter(
    #        event_type__name='Reciprocal Transfer',
    #        commitment=None)

    def sorted_events(self):
        events = self.events().order_by("event_type__name")
        return events

    def flow_type(self):
        return "Exchange"

    def flow_class(self):
        return "exchange"

    def flow_description(self):
        return self.__str__()

    def resource_receive_events(self):
        #todo exchange redesign fallout
        if self.use_case.name=="Incoming Exchange":
            return [evt for evt in self.transfer_receive_events() if evt.resource]
        else:
            return []

    def expense_events(self):
        #todo exchange redesign fallout
        if self.use_case.name=="Incoming Exchange":
            return [evt for evt in self.transfer_receive_events() if not evt.resource]
        else:
            return []

    def roll_up_value(self, trigger_event, path, depth, visited, value_equation=None):
        """ Rolling up value from an exchange for a resource.

            trigger_event is a receipt for a resource.
            All of the expenses and work contributions in the Exchange
            must be spread among all of the receipts, with this receipt
            getting its share.
        """

        #exchange method
        values = Decimal("0.0")
        if trigger_event not in visited:
            visited.add(trigger_event)
            depth += 1
            self.depth = depth
            depth += 1
            path.append(self)
            values = Decimal("0.0")
            #todo exchange redesign fallout
            #just guessing at receipts and payments
            # to eliminate error messages
            #Note: trigger_event is also one of the receipts
            receipts = self.resource_receive_events()
            trigger_fraction = 1
            if len(receipts) > 1:
                #what fraction is the trigger_event of the total value of receipts
                rsum = sum(r.value for r in receipts)
                trigger_fraction = trigger_event.value / rsum
            payments = [evt for evt in self.payment_events() if evt.to_agent==trigger_event.from_agent]
            #share =  quantity / trigger_event.quantity
            if len(payments) == 1:
                evt = payments[0]
                value = evt.quantity
                br = evt.bucket_rule(value_equation)
                if br:
                    value = br.compute_claim_value(evt)
                values += value * trigger_fraction
                evt.depth = depth
                path.append(evt)
                if evt.resource:
                    contributions = evt.resource.cash_contribution_events()
                    depth += 1
                    #todo 3d: done, maybe
                    for c in contributions:
                        c.depth = depth
                        path.append(c)
            elif len(payments) > 1:
                total = sum(p.quantity for p in payments)
                for evt in payments:
                    fraction = evt.quantity / total
                    #depth += 1
                    if evt.resource:
                        contributions = evt.resource.cash_contribution_events()
                        #evt.share = evt.quantity * share * fraction * trigger_fraction
                        evt.share = evt.quantity * fraction * trigger_fraction
                        evt.depth = depth
                        path.append(evt)
                        values += evt.share
                        #todo 3d: do multiple payments make sense for cash contributions?
                    else:
                        value = evt.quantity
                        br = evt.bucket_rule(value_equation)
                        if br:
                            value = br.compute_claim_value(evt)
                        evt.share = value * fraction * trigger_fraction
                        evt.depth = depth
                        path.append(evt)
                        values += evt.share
            #todo exchange redesign fallout
            expenses = self.expense_events()
            for ex in expenses:
                ex.depth = depth
                path.append(ex)
                value = ex.value
                values += value * trigger_fraction
                exp_payments = [evt for evt in self.payment_events() if evt.to_agent==ex.from_agent]
                #exp_payments = self.payment_events().filter(to_agent=ex.from_agent)
                for exp in exp_payments:
                    depth += 1
                    exp.depth = depth
                    path.append(exp)
                    depth -= 1
                depth -= 1

            for evt in self.work_events():
                value = evt.quantity
                br = evt.bucket_rule(value_equation)
                if br:
                    value = br.compute_claim_value(evt)
                #evt.share = value * share * trigger_fraction
                evt.share = value * trigger_fraction
                values += evt.share
                evt.depth = depth
                path.append(evt)
        event_value = values
        return event_value

    def compute_income_shares(self, value_equation, trigger_event, quantity, events, visited):
        #exchange method
        if trigger_event not in visited:
            visited.add(trigger_event)

            trigger_fraction = 1
            share =  quantity / trigger_event.quantity
            #todo exchange redesign fallout
            receipts = self.resource_receive_events()
            if receipts:
                if len(receipts) > 1:
                    rsum = sum(r.value for r in receipts)
                    trigger_fraction = trigger_event.value / rsum
            payments = [evt for evt in self.payment_events() if evt.to_agent==trigger_event.from_agent]
            """
            else:
                #todo exchange redesign fallout
                #change transfer_events, that method is obsolete
                xfers = self.transfer_events()
                if xfers:
                    payments = self.cash_receipt_events().filter(from_agent=trigger_event.to_agent)
            """
            if len(payments) == 1:
                evt = payments[0]
                value = evt.quantity
                contributions = []
                if evt.resource:
                    #todo exchange redesign fallout
                    #do cash_contribution_events work?
                    candidates = evt.resource.cash_contribution_events()
                    for cand in candidates:
                        br = cand.bucket_rule(value_equation)
                        if br:
                            cand.value = br.compute_claim_value(cand)
                            if cand.value:
                                contributions.append(cand)
                    for ct in contributions:
                        fraction = ct.quantity / value
                        ct.share = ct.value * share * fraction * trigger_fraction
                        #ct.share = ct.value * fraction * trigger_fraction
                        events.append(ct)
                if not contributions:
                    #if contributions were credited,
                    # do not give credit for payment.
                    br = evt.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(evt)
                    evt.value = value
                    evt.save()
                    evt.share = value * share * trigger_fraction
                    events.append(evt)

            elif len(payments) > 1:
                total = sum(p.quantity for p in payments)
                for evt in payments:
                    fraction = evt.quantity / total
                    #if evt.resource:
                    if evt.resource and not xfers:
                        contributions = evt.resource.cash_contribution_events()
                        evt.share = evt.quantity * share * fraction * trigger_fraction
                        #evt.share = evt.quantity * fraction * trigger_fraction
                        events.append(evt)
                        #todo 3d: do multiple payments make sense for cash contributions?
                        #equip logging changes
                        #apparently: see treatment in compute_income_shares_for_use below
                    else:
                        value = evt.quantity
                        br = evt.bucket_rule(value_equation)
                        if br:
                            value = br.compute_claim_value(evt)
                        evt.value = value
                        evt.save()
                        evt.share = value * share * fraction * trigger_fraction
                        #evt.share = value * fraction * trigger_fraction
                        events.append(evt)

            expenses = self.expense_events()
            for ex in expenses:
                exp_payments = [evt for evt in self.payment_events() if evt.to_agent==ex.from_agent]
                for exp in exp_payments:
                    value = exp.quantity
                    br = exp.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(exp)
                    exp.value = value
                    exp.save()
                    exp.share = value * share * trigger_fraction
                    events.append(exp)

            for evt in self.work_events():
                if evt.is_contribution:
                    value = evt.quantity
                    br = evt.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(evt)
                    #evt.share = value * share * trigger_fraction
                    evt.value = value
                    evt.save()
                    evt.share = value * share * trigger_fraction
                    #evt.share = value * trigger_fraction
                    events.append(evt)

    def compute_income_shares_for_use(self, value_equation, use_event, use_value, resource_value, events, visited):
        #exchange method
        locals = []
        if self not in visited:
            visited.add(self)
            resource = use_event.resource
            trigger_fraction = 1
            #equip logging changes
            #todo exchange redesign fallout
            receipts = self.resource_receive_events()
            #needed?
            #payments = [evt for evt in self.payment_events() if evt.to_agent==trigger_event.from_agent]
            payments = self.payment_events()
            if receipts:
                if len(receipts) > 1:
                    rsum = sum(r.value for r in receipts)
                    #trigger_fraction = use_event.value / rsum
                #payments = self.payment_events().filter(to_agent=trigger_event.from_agent)
                #share =  quantity / trigger_event.quantity
            """
            else:
                #todo exchange redesign fallout
                xfers = self.transfers.all()
                if xfers:
                    #payments = self.cash_receipt_events().filter(from_agent=trigger_event.to_agent)
                    payments = self.reciprocal_transfer_receive_events()
            """
            cost = Decimal("0")
            if payments:
                cost = sum(p.quantity for p in payments)
            #equip logging changes
            #does this make any sense for use events?
            use_share = use_value
            if cost:
                use_share =  use_value / cost
            if len(payments) == 1:
                evt = payments[0]
                contributions = []
                if evt.resource:
                    contributions = evt.resource.cash_contribution_events()
                    for ct in contributions:
                        fraction = ct.quantity / resource_value
                        #todo 3d: changed
                        ct.share = use_value * fraction
                        events.append(ct)
                if not contributions:
                    #if contributions were credited,
                    # do not give credit for payment.
                    value = evt.quantity
                    br = evt.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(evt)
                    #evt.share = value * use_share?
                    evt.share = use_value
                    events.append(evt)
            elif len(payments) > 1:
                total = sum(p.quantity for p in payments)
                for evt in payments:
                    #equip logging changes
                    payment_fraction = evt.quantity / total
                    value = evt.quantity
                    br = evt.bucket_rule(value_equation)
                    if br:
                        value = br.compute_claim_value(evt)
                    if evt.resource:
                        contributions = evt.resource.cash_contribution_events()
                        for ct in contributions:
                            #shd this be based on resource_value or cost/total?
                            resource_fraction = ct.quantity / resource_value
                            #is use_value relevant here? Or use_share (use_value / cost)?
                            #and since we have multiple payments, must consider total!
                            #share_addition = use_value * use_share * resource_fraction * payment_fraction
                            share_addition = use_value * resource_fraction * payment_fraction
                            existing_ct = next((evt for evt in events if evt == ct),0)
                            if existing_ct:
                                existing_ct.share += share_addition

                            else:
                                ct.share = share_addition
                                events.append(ct)
                                locals.append(ct)
                    if not contributions:
                        #if contributions were credited,
                        # do not give credit for payment.
                        #evt.share = value * use_share * payment_fraction
                        evt.share = use_value * payment_fraction
                        events.append(evt)
            for evt in self.work_events():
                value = evt.quantity
                br = evt.bucket_rule(value_equation)
                if br:
                    value = br.compute_claim_value(evt)
                evt.value = value
                #todo 3d: changed
                fraction = value / resource_value
                evt.share = use_value * fraction
                events.append(evt)
            if locals:
                local_total = sum(lo.share for lo in locals)
                delta = use_value - local_total
                if delta:
                    max_share = locals[0]
                    for lo in locals:
                        if lo.share > max_share.share:
                            max_share = lo
                max_share.share = (max_share.share + delta)
                #local_total = sum(lo.share for lo in locals)
                #print("local_total:", local_total)

    def related_agents(self):
        xfers = self.transfers.all()
        agents = []
        for xfer in xfers:
            if xfer.to_agent() not in agents:
                agents.append(xfer.to_agent())
            if not xfer.from_agent() in agents:
                agents.append(xfer.from_agent())
            if not xfer.scope in agents:
                agents.append(xfer.scope)
        return agents



class Transfer(models.Model):
    name = models.CharField(_('name'), blank=True, max_length=128)
    transfer_type = models.ForeignKey(TransferType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('transfer type'), related_name='transfers')
    exchange = models.ForeignKey(Exchange,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('exchange'), related_name='transfers')
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='transfers')
    transfer_date = models.DateField(_('transfer date'))
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='transfers_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='transfers_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = ExchangeManager()

    class Meta:
        ordering = ('transfer_date',)
        verbose_name_plural = _("transfers")

    def __str__(self):
        show_name = ""
        from_name = ""
        to_name = ""
        unit = ""
        resource_string = ""
        qty = ""
        if self.transfer_type:
            show_name = self.transfer_type.name
        event = None
        if self.events.all():
            event = self.events.all()[0]
        if event:
            if event.from_agent:
                from_name = "from " + event.from_agent.name
            if event.to_agent:
                to_name = "to " + event.to_agent.name
            if event.resource_type:
                resource_string = event.resource_type.name
            if event.resource:
                resource_string = event.resource.__str__()
            qty = str(event.quantity)
            if event.unit_of_quantity:
                unit = event.unit_of_quantity.name
        else:
            commits = self.commitments.all()
            if commits:
                commit = commits[0]
                show_name = "(Planned) " + show_name
                if commit.from_agent:
                    from_name = "from " + commit.from_agent.name
                if commit.to_agent:
                    to_name = "to " + commit.to_agent.name
                if commit.resource_type:
                    resource_string = commit.resource_type.name
                qty = str(commit.quantity)
                if commit.unit_of_quantity:
                    unit = commit.unit_of_quantity.name

        if unit in resource_string:
            unit = ''
        if unit == 'Each' and resource_string:
            unit = ''

        return " ".join([
        #    name,
            show_name,
            from_name,
            to_name,
            qty,
            unit,
            resource_string,
            "on",
            self.transfer_date.strftime('%Y-%m-%d'),
            ])


    @property #ValueFlows
    def exchange_agreement(self):
        #VF does not have an exchange unless it is created ahead of time for reciprocal commitments
        exch = self.exchange
        if exch.has_reciprocal():
            return exch
        return None

    @property #ValueFlows
    def planned_date(self):
        return self.transfer_date.isoformat()

    @property #ValueFlows
    def actual_date(self):
        events = self.events.all()
        if events:
            return events[0].event_date.isoformat()
        return None

    @property #ValueFlows
    def note(self):
        return self.notes

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    @property #ValueFlows
    def provider(self):
        events = self.events.all()
        if events:
            return events[0].from_agent
        return None

    @property #ValueFlows
    def receiver(self):
        events = self.events.all()
        if events:
            return events[0].to_agent
        return None

    @property #ValueFlows
    def resource_classifiedAs(self):
        events = self.events.all()
        if events:
            event = events[0]
            return event.resource_type
        return None

    @property #ValueFlows
    def give_resource(self):
        events = self.events.all()
        give_resource = None
        et_give = EventType.objects.get(name="Give")
        if events:
            for ev in events:
                if ev.event_type == et_give:
                    give_resource = ev.resource
        return give_resource

    @property #ValueFlows
    def take_resource(self):
        events = self.events.all()
        take_resource = None
        et_receive = EventType.objects.get(name="Receive")
        if events:
            for ev in events:
                if ev.event_type == et_receive:
                    take_resource = ev.resource
        return take_resource

    @property #ValueFlows
    def unit(self):
        events = self.events.all()
        if events:
            return events[0].unit_of_quantity
        return None

    def last_date(self):
        events = self.events.all().order_by('-event_date')
        if events:
            return events[0].event_date.isoformat()
        commis = self.commitments.all().order_by('-due_date')
        if commis:
            return commis[0].due_date.isoformat()
        return '?'

    def related_agents(self):
        agents = []
        if self.from_agent():
            agents.append(self.from_agent())
        if self.to_agent():
            if self.to_agent() not in agents:
                agents.append(self.to_agent())
        if self.context_agent:
            if self.context_agent not in agents:
                agents.append(self.context_agent)
        return agents

    def resource_type(self):
        rt = None
        rts = []
        events = self.events.all()
        if events:
          for event in events:
            if event.resource:
                if not event.resource.resource_type in rts:
                    rts.append(event.resource.resource_type)
                #break
            if event.resource_type:
                if not event.resource_type in rts:
                    rts.append(event.resource_type)
                #break
        else:
            for commit in self.commitments.all():
                if commit.resource_type:
                    if not commit.resource_type in rts:
                        rts.append(commit.resource_type)
                    #break
        if rts:
            #print("- rts:"+str(rts))
            if len(rts) > 1:
                print("-- multiple rts: "+str(len(rts))+" for tx:"+str(self))
                loger.info("-- multiple rts: "+str(len(rts))+" for tx:"+str(self))
                par = None
                for t in rts:
                    if hasattr(t, 'ocp_artwork_type') and t.ocp_artwork_type:
                        pare = t.ocp_artwork_type.parent()
                        if not par:
                            par = pare
                        elif par == pare:
                            rt = par.resource_type
            else:
                 rt = rts[0]
        else:
            if hasattr(self.exchange, 'join_request') and self.exchange.join_request:
                if self.transfer_type == self.exchange.ttpay():
                    rt = self.exchange.join_request.payment_unit_rt()
                else:
                    rt = self.exchange.join_request.project.shares_type()
            else:
                print("- don't find rts nor jr? self(tx):"+str(self.id)+" ex:"+str(self.exchange.id))
                loger.info("- don't find rts nor jr? self(tx):"+str(self.id)+" ex:"+str(self.exchange.id))
        return rt


    def show_name(self, agent=None, forced=False):
        name = self.__str__()
        newname = name
        if agent:
          if self.events or self.commitments:
            gives = self.events.filter(from_agent=agent)
            if not gives:
                gives = self.commitments.filter(from_agent=agent)
            if not gives:
                gives = forced
            takes = self.events.filter(to_agent=agent)
            if not takes:
                takes = self.commitments.filter(to_agent=agent)
            if not takes:
                takes = forced

            if hasattr(self.exchange.exchange_type, 'ocp_record_type'):
                x_actions = self.exchange.exchange_type.ocp_record_type.x_actions()
                for action in x_actions:
                    opposite = action.opposite()
                    if opposite:
                        if action.clas and opposite.clas:
                            newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                        if name == newname:
                            newname = name.replace(action.name, '<em>'+opposite.name+'</em>')

                        if takes and action.clas == 'give' and not name == newname:
                            name = newname
                            break
                        if gives and action.clas == 'receive' and not name == newname:
                            name = newname
                            break
                    #import pdb; pdb.set_trace()
        return name

    def status(self):
        #print("tx status")
        if self.exchange.exchange_type.use_case.identifier == 'intrnl_xfer':
            need_evts = 1 #2
        else:
            need_evts = 1
        status = '??'
        comits = self.commitments.all_give() #filter(transfer=self)
        events = list(self.events.all_give()) #filter(transfer=self)
        for com in comits:
            for ev in com.fulfillment_events.all_give():
                if not ev in events:
                    print(" append ev:"+str(ev))
                    loger.info(" append ev:"+str(ev))
                    events.append(ev)
        if len(comits):
          if len(events) < len(comits) or not len(events) >= need_evts:
            status = 'pending' #str([ev.id for ev in events])+' '+str([co.id for co in comits])+' tr:'+str(self.id)+' x:'+str(self.exchange.id)+' pending'
          #elif len(events) == len(comits): #need_evts:
          #  if len(comits) > 1:
          #      print(" tx evs and coms count is equal, but more than one commit... ONLY CHECKED first! tx:"+str(self.id)+" ex:"+str(self.exchange.id)+" comits:"+str(comits))
          #      loger.info(" tx evs and coms count is equal, but more than one commit... ONLY CHECKED first! tx:"+str(self.id)+" ex:"+str(self.exchange.id)+" comits:"+str(comits))
          #  comi = comits[0]
          #  if comi.unfilled_quantity():
          #      status = "pending"
          #  else:
          #      status = 'complete'
          else:
            status = 'xx'
            for com in comits:
                if not com.status() == 'complete':
                    status = 'pending'
                elif status == 'xx':
                    status = 'complete'
        elif len(events):
          if len(events) >= need_evts:
            status = 'complete' #str([ev.id for ev in events])+' tr:'+str(self.id)+' x:'+str(self.exchange.id)+' complete'
          else:
            status = 'pending' #str([ev.id for ev in events])+' tr:'+str(self.id)+' x:'+str(self.exchange.id)+' pending'
        else:
          status = 'empty'
        if hasattr(self.exchange, 'join_request') and self.exchange.join_request:
          if not self.transfer_type.is_share():
            if not status == 'pending' and self.exchange.join_request.payment_pending_to_pay():
                status = 'pending'
          else:
            if self.exchange.join_request.pending_shares() and status == 'complete':
                status = 'pending'
        #import pdb; pdb.set_trace()
        return status


    def commit_text(self):
        text = None
        give = None
        receive = None
        unit = ""
        resource = ""
        from_to = ""
        qty = ""
        give_text = ""
        receive_text = ""
        commits = self.commitments.all()
        if commits:
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            for commit in commits:
                if commit.event_type == et_give:
                    give = commit
                elif commit.event_type == et_receive:
                    receive = commit
            either = commits[0]
            if either.resource_type:
                resource = either.resource_type.name + ","
            qty = str(either.quantity)
            if either.unit_of_quantity:
                unit = either.unit_of_quantity.abbrev
                if unit in resource.lower() or unit == "EA":
                    unit = ''
            if give:
                if give.to_agent and give.from_agent:
                    give_text = "GIVE to " + give.to_agent.nick
                elif give.to_agent and not give.from_agent:
                    give_text = "FROM?"
                elif not give.to_agent and give.from_agent:
                    give_text = "GIVE to ??" #from " + give.from_agent.nick
                else:
                    give_text = "??"
            if receive:
                if receive.from_agent and receive.to_agent:
                    receive_text = "RECEIVE from " + receive.from_agent.nick
                elif receive.from_agent and not receive.to_agent:
                    receive_text = "TO?"
                elif not receive.from_agent and receive.to_agent:
                    receive_text = "RECEIVE from ??" # + receive.to_agent.nick
                else:
                    give_text = "??"
            if give:
                from_to = give_text
                if receive:
                    from_to += " "
            if receive:
                from_to = from_to + receive_text
            if either.resource_type and either.unit_of_quantity and either.unit_of_quantity.name == either.resource_type.name:
                text = " ".join([
                  qty,
                  resource,
                  from_to,
                ])
            else:
                text = " ".join([
                  qty,
                  unit,
                  resource,
                  from_to,
                ])
        return text

    def commit_event_text(self):
        text = None
        give = None
        receive = None
        unit = ""
        resource = ""
        from_to = ""
        qty = ""
        give_text = ""
        receive_text = ""
        events = self.events.all()
        if events:
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            for event in events:
                if event.event_type == et_give:
                    give = event
                elif event.event_type == et_receive:
                    receive = event
            either = events[0]
            if either.resource_type:
                resource = either.resource_type.name + ","
            if either.resource:
                resource = str(either.resource) + ","
            qty = str(either.quantity)
            if either.unit_of_quantity:
                unit = either.unit_of_quantity.abbrev
                if unit in resource.lower() or unit == "EA":
                    unit = ''
            if give:
                if give.event_date:
                    give_text = "GIVE on " + str(give.event_date)
            if receive:
                if receive.event_date:
                    receive_text = "RECEIVE on " + str(receive.event_date)
            if give:
                from_to = give_text
                if receive:
                    from_to += ", "
            if receive:
                from_to = from_to + receive_text
            text = " ".join([
                qty,
                unit,
                resource,
                from_to,
                ])
        return text

    def event_text(self):
        text = None
        give = None
        receive = None
        unit = ""
        resource = ""
        from_to = ""
        qty = ""
        give_text = ""
        receive_text = ""
        events = self.events.all()
        if events:
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            for event in events:
                if event.event_type == et_give:
                    give = event
                elif event.event_type == et_receive:
                    receive = event
            either = events[0]
            if either.resource_type:
                resource = either.resource_type.name + ","
            if either.resource:
                resource = str(either.resource) + ","
            qty = str(either.quantity)
            if either.unit_of_quantity:
                unit = either.unit_of_quantity.abbrev
                if unit in resource.lower() or unit == "EA":
                    unit = ''
            if give:
                if give.to_agent:
                    give_text = "GIVE to " + give.to_agent.nick
                if give.event_date:
                    give_text += " on " + str(give.event_date)
            if receive:
                if receive.from_agent:
                    receive_text = "RECEIVE from " + receive.from_agent.nick
                if receive.event_date:
                    receive_text += " on " + str(receive.event_date)
            if give:
                from_to = give_text
                if receive:
                    from_to += ", "
            if receive:
                from_to = from_to + receive_text
            text = " ".join([
                qty,
                unit,
                resource,
                from_to,
                ])
        return text

    def commit_description(self):
        commits = self.commitments.all()
        if commits:
            return commits[0].description
        else:
            return None

    def event_description(self):
        events = self.events.all()
        if events:
            return events[0].description
        else:
            return None

    def save(self, *args, **kwargs):
        if self.id:
            if not self.transfer_type:
                msg = " ".join(["No transfer type on transfer: ", str(self.id)])
                assert False, msg
        if self.transfer_type:
            #if self.events. # try to reach the ocp_resource_type and save the related resource_type
            super(Transfer, self).save(*args, **kwargs)

    def is_reciprocal(self):
        return self.transfer_type.is_reciprocal

    def give_event(self):
        try:
            return self.events.get(event_type__name="Give")
        except EconomicEvent.DoesNotExist:
            return None

    def receive_event(self):
        try:
            return self.events.get(event_type__name="Receive")
        except EconomicEvent.DoesNotExist:
            return None

    def give_commitment(self):
        try:
            return self.commitments.get(event_type__name="Give")
        except Commitment.DoesNotExist:
            return None

    def receive_commitment(self):
        try:
            return self.commitments.get(event_type__name="Receive")
        except Commitment.DoesNotExist:
            return None

    def quantity(self, receive=False):
        if receive:
            events = self.events.filter(event_type__name="Receive")
        else:
            events = self.events.all()
        if events:
            return events[0].quantity
        else:
            commits = self.commitments.all()
            if commits:
                return commits[0].quantity
        return Decimal("0.0")

    def actual_quantity(self, receive=False):
        if receive:
            events = self.events.filter(event_type__name="Receive")
        else:
            events = self.events.all_give()
        if events:
            qty = Decimal("0.0")
            for ev in events:
                if ev.quantity:
                    qty += ev.quantity
            return qty
        return Decimal("0.0")

    def unit_of_quantity(self):
        events = self.events.all()
        if events:
            for ev in events:
                if ev.unit_of_quantity:
                    return ev.unit_of_quantity
        else:
            commits = self.commitments.all()
            if commits:
                for com in commits:
                    if com.unit_of_quantity:
                        return com.unit_of_quantity
        return None

    def value(self, receive=False):
        if receive:
            events = self.events.filter(event_type__name="Receive")
        else:
            events = self.events.all()
        if events:
            return events[0].value
        else:
            commits = self.commitments.all()
            if commits:
                return commits[0].value
        return None

    def actual_value(self, receive=False):
        if receive:
            events = self.events.filter(event_type__name="Receive")
        else:
            events = self.events.all_give()
        if events:
            val = Decimal("0.0")
            for ev in events:
                if ev.value:
                    val += ev.value
            return val
        return Decimal("0.0")

    def unit_of_value(self):
        events = self.events.all()
        if events:
          for ev in events:
            if ev.unit_of_value:
                return ev.unit_of_value
        else:
            commits = self.commitments.all()
            if commits:
                for com in commits:
                    if com.unit_of_value:
                        return com.unit_of_value
        return None

    def from_agent(self):
        frs = []
        events = self.events.all()
        commits = self.commitments.all()
        if events:
            for ev in events:
                if ev.from_agent and not ev.from_agent in frs:
                    frs.append(ev.from_agent)
                    #return ev.from_agent
        if commits:
            for com in commits:
                if com.from_agent and not com.from_agent in frs:
                    frs.append(com.from_agent)
                    #return com.from_agent
        if frs:
            if len(frs) > 1:
                print("WARN! the tx:"+str(self.id)+" has various FROM agents: "+str(frs))
                loger.info("WARN! the tx:"+str(self.id)+" has various FROM agents: "+str(frs))
            return frs[0]

        return None

    def to_agent(self):
        tos = []
        events = self.events.all()
        commits = self.commitments.all()
        if events:
            for ev in events:
                if ev.to_agent and not ev.to_agent in tos:
                    tos.append(ev.to_agent)
                    #return ev.to_agent
        if commits:
            for com in commits:
                if com.to_agent and not com.to_agent in tos:
                    tos.append(com.to_agent)
                    #return com.to_agent
        if tos:
            if len(tos) > 1:
                print("WARN! the tx:"+str(self.id)+" has various TO agents: "+str(tos))
                loger.info("WARN! the tx:"+str(self.id)+" has various TO agents: "+str(tos))
            return tos[0]
        return None

    def resource_type(self):
        events = self.events.all()
        if events:
            event = events[0]
            return event.resource_type
        else:
            commits = self.commitments.all()
            if commits:
                return commits[0].resource_type
        if self.transfer_type.inherit_types:
            pass # TODO
        return None

    def resource_name(self):
        events = self.events.all()
        if events:
            event = events[0]
            resource_string = event.resource_type.name
            if event.resource:
                resource_string = event.resource.__str__()
            return resource_string
        return None

    def resource(self):
        events = self.events.all()
        resource = None
        if events:
            resource = events[0].resource
        return resource

    def is_deletable(self):
        if self.commitments.all():
            return False
        if self.events.all():
            return False
        return True

    def flow_type(self):
        return "Transfer"

    def flow_class(self):
        return "transfer"

    def flow_description(self):
        return self.__str__()

    def give_and_receive_resources(self):
        events = self.events.all()
        give_resource = None
        receive_resource = None
        et_give = EventType.objects.get(name="Give")
        if events:
            for ev in events:
                if ev.event_type == et_give:
                    give_resource = ev.resource
                else:
                    receive_resource = ev.resource
        return give_resource, receive_resource

    def form_prefix(self):
        return "TR" + str(self.id)

    def commit_transfer_form(self):
        from valuenetwork.valueaccounting.forms import TransferForm
        prefix=self.form_prefix()
        init = {
            "event_date": datetime.date.today(),
            "resource_type": self.resource_type(),
            "quantity": self.quantity(),
            "value": self.value(),
            "unit_of_value": self.unit_of_value(),
            "from_agent": self.from_agent(),
            "to_agent": self.to_agent(),
            }
        return TransferForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, posting=False, prefix=prefix)

    def commit_transfer_context_form(self): # bumbum
        from work.forms import ContextTransferForm
        prefix=self.form_prefix()
        init = {
            "event_date": datetime.date.today(),
            "resource_type": self.resource_type(),
            "quantity": self.quantity(),
            "value": self.value(),
            "unit_of_value": self.unit_of_value(),
            "from_agent": self.from_agent(),
            "to_agent": self.to_agent(),
            }
        return ContextTransferForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, resource_type=self.resource_type(), posting=False, prefix=prefix)

    def create_role_formset(self, data=None):
        from valuenetwork.valueaccounting.views import resource_role_agent_formset
        return resource_role_agent_formset(prefix=self.form_prefix(), data=data)


    def change_commitments_form(self):
        from valuenetwork.valueaccounting.forms import TransferCommitmentForm
        prefix = self.form_prefix() + "C"
        commits = self.commitments.all()
        if commits:
            commit = commits[0]
            init = {
                "commitment_date": commit.commitment_date,
                "due_date": commit.due_date,
                "description":commit.description,
                "resource_type": commit.resource_type,
                "quantity": commit.quantity,
                "value": commit.value,
                "unit_of_value": commit.unit_of_value,
                "from_agent": commit.from_agent,
                "to_agent": commit.to_agent,
                }
            return TransferCommitmentForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, posting=False, prefix=prefix)
        return None

    def change_commitments_context_form(self): # bumbum
        from work.forms import ContextTransferCommitmentForm
        prefix = self.form_prefix() + "C"
        #prefix = "ACM" + str(self.transfer_type.id) #self.form_prefix() + "C"
        commits = self.commitments.all()
        if commits:
            commit = commits[0]
            init = {
                "commitment_date": commit.commitment_date,
                "due_date": commit.due_date,
                "description":commit.description,
                "resource_type": commit.resource_type,
                "quantity": commit.quantity,
                "value": commit.value,
                "unit_of_value": commit.unit_of_value,
                "from_agent": commit.from_agent,
                "to_agent": commit.to_agent,
                }
            return ContextTransferCommitmentForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, resource_type=commit.resource_type, posting=False, prefix=prefix)
        return None

    def change_events_form(self):
        from valuenetwork.valueaccounting.forms import TransferForm
        prefix = self.form_prefix() + "E"
        events = self.events.all()
        if events:
            event = events[0]
            from_resource, resource = self.give_and_receive_resources()
            if from_resource and not resource:
                resource = from_resource
            init = {
                "resource": resource,
                "from_resource": from_resource,
                "description": event.description,
                "is_contribution": event.is_contribution,
                "event_reference": event.event_reference,
                "event_date": event.event_date,
                "description":event.description,
                "resource_type": event.resource_type,
                "quantity": event.quantity,
                "value": event.value,
                "unit_of_value": event.unit_of_value,
                "from_agent": event.from_agent,
                "to_agent": event.to_agent,
                }
            return TransferForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, resource_type=event.resource_type, posting=False, prefix=prefix)
        return None

    def change_events_context_form(self):
        from work.forms import ContextTransferForm
        prefix = self.form_prefix() + "E"
        events = self.events.all()
        if events:
            event = events[0]
            from_resource, resource = self.give_and_receive_resources()
            if from_resource and not resource:
                resource = from_resource
            init = {
                "resource": resource,
                "from_resource": from_resource,
                "description": event.description,
                "is_contribution": event.is_contribution,
                "event_reference": event.event_reference,
                "event_date": event.event_date,
                "description":event.description,
                "resource_type": event.resource_type,
                "quantity": event.quantity,
                "value": event.value,
                "unit_of_value": event.unit_of_value,
                "from_agent": event.from_agent,
                "to_agent": event.to_agent,
                }
            return ContextTransferForm(initial=init, transfer_type=self.transfer_type, context_agent=self.context_agent, resource_type=event.resource_type, posting=False, prefix=prefix)
        return None


class Feature(models.Model):
    name = models.CharField(_('name'), max_length=128)
    #todo: replace with ___? something
    #option_category = models.ForeignKey(Category,
    #    verbose_name=_('option category'), related_name='features',
    #    blank=True, null=True,
    #    help_text=_("option selections will be limited to this category"),
    #    limit_choices_to=Q(applies_to='Anything') | Q(applies_to='EconomicResourceType'))
    product = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        related_name="features", verbose_name=_('product'))
    process_type = models.ForeignKey(ProcessType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('process type'), related_name='features')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='features')
    quantity = models.DecimalField(_('quantity'), max_digits=8, decimal_places=2, default=Decimal('0.00'))
    unit_of_quantity = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="feature_units")
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='features_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='features_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return " ".join([self.name, "Feature for", self.product.name])

    def xbill_child_object(self):
        return self

    def xbill_class(self):
        return "feature"

    def xbill_parent_object(self):
        return self.process_type

    def xbill_children(self):
        return self.options.all()

    def xbill_explanation(self):
        return "Feature"

    def xbill_label(self):
        abbrev = ""
        if self.unit_of_quantity:
           abbrev = self.unit_of_quantity.abbrev
        return " ".join([str(self.quantity), abbrev])

    #def xbill_category(self):
    #    return Category(name="features")

    def node_id(self):
        return "-".join(["Feature", str(self.id)])

    def xbill_parents(self):
        return [self.process_type, self]

    def options_form(self):
        from valuenetwork.valueaccounting.forms import OptionsForm
        return OptionsForm(feature=self)

    def options_change_form(self):
        from valuenetwork.valueaccounting.forms import OptionsForm
        option_ids = self.options.values_list('component__id', flat=True)
        init = {'options': option_ids,}
        return OptionsForm(feature=self, initial=init)

    def xbill_change_prefix(self):
        return "".join(["FTR", str(self.id)])

    def xbill_change_form(self):
        from valuenetwork.valueaccounting.forms import FeatureForm
        #return FeatureForm(instance=self, prefix=self.xbill_change_prefix())
        return FeatureForm(instance=self)


class Option(models.Model):
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE,
        related_name="options", verbose_name=_('feature'))
    component = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        related_name="options", verbose_name=_('component'))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='options_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='options_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    class Meta:
        ordering = ('component',)

    def __str__(self):
        return " ".join([self.component.name, "option for", self.feature.name])

    def xbill_child_object(self):
        return self.component

    def xbill_class(self):
        return "option"

    def xbill_parent_object(self):
        return self.feature

    def xbill_children(self):
        return self.component.xbill_children()

    def xbill_explanation(self):
        return "Option"

    def xbill_label(self):
        return ""

    #def xbill_category(self):
    #    return Category(name="features")

    def node_id(self):
        return "-".join(["Option", str(self.id)])

    def xbill_parents(self):
        return [self.feature, self]


class CommitmentManager(models.Manager):

    def unfinished(self):
        return Commitment.objects.filter(finished=False).filter(process__finished=False)

    def finished(self):
        return Commitment.objects.filter(finished=True)

    def todos(self):
        return Commitment.objects.filter(
            event_type__relationship="todo",
            finished=False)

    def finished_todos(self):
        return Commitment.objects.filter(
            event_type__relationship="todo",
            finished=True)

    def to_buy(self):
        #exclude finished
        cts = self.unfinished()
        reqs = cts.filter(
            Q(event_type__relationship='consume')|Q(event_type__relationship='use')).order_by("resource_type__name")
        rts = all_purchased_resource_types()
        answer = []
        for req in reqs:
            qtb = req.quantity_to_buy()
            if qtb > 0:
                if req.resource_type in rts:
                    req.purchase_quantity = qtb
                    answer.append(req)
        return answer

    def all_give(self):
        #print("comm all_give ")
        et_give = EventType.objects.get(name="Give")
        bkp = self.all()
        filtered = self.filter(event_type=et_give)
        if not filtered and bkp:
            internal = bkp.filter(exchange__isnull=False, exchange__exchange_type__use_case__identifier='intrnl_xfer')
            if not internal and bkp:
                internal = bkp.filter(transfer__exchange__isnull=False, transfer__exchange__exchange_type__use_case__identifier='intrnl_xfer')
                #print("x filter using ev tx ex. internal:"+str(len(internal)))
            if internal:
                print("WARN not found 'give' event_type filtered from "+str(self)+", return all! "+str([ev.event_type for ev in bkp]))
                loger.info("WARN not found 'give' event_type filtered from "+str(self)+", return all! ")
            return bkp
        return filtered


class Commitment(models.Model):
    order = models.ForeignKey(Order,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="commitments", verbose_name=_('order'))
    independent_demand = models.ForeignKey(Order,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="dependent_commitments", verbose_name=_('independent demand'))
    order_item = models.ForeignKey("self",
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="stream_commitments", verbose_name=_('order item'))
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        related_name="commitments", verbose_name=_('event type'))
    stage = models.ForeignKey(ProcessType, related_name="commitments_at_stage",
        verbose_name=_('stage'), blank=True, null=True, on_delete=models.SET_NULL)
    exchange_stage = models.ForeignKey(ExchangeType, related_name="commitments_at_exchange_stage",
        verbose_name=_('exchange stage'), blank=True, null=True, on_delete=models.SET_NULL)
    state = models.ForeignKey(ResourceState, related_name="commitments_at_state",
        verbose_name=_('state'), blank=True, null=True, on_delete=models.SET_NULL)
    commitment_date = models.DateField(_('commitment date'), default=datetime.date.today)
    start_date = models.DateField(_('start date'), blank=True, null=True)
    due_date = models.DateField(_('due date'))
    finished = models.BooleanField(_('finished'), default=False)
    from_agent_type = models.ForeignKey(AgentType,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="given_commitments", verbose_name=_('from agent type'))
    from_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="given_commitments", verbose_name=_('from'))
    to_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="taken_commitments", verbose_name=_('to'))
    resource_type = models.ForeignKey(EconomicResourceType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('resource type'), related_name='commitments')
    resource = models.ForeignKey(EconomicResource,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('resource'), related_name='commitments')
    process = models.ForeignKey(Process,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('process'), related_name='commitments')
    exchange = models.ForeignKey(Exchange,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('exchange'), related_name='commitments')
    transfer = models.ForeignKey(Transfer,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="commitments")
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='commitments')
    description = models.TextField(_('description'), null=True, blank=True)
    url = models.CharField(_('url'), max_length=255, blank=True)
    quantity = models.DecimalField(_('quantity'), max_digits=20, decimal_places=9)
    unit_of_quantity = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="commitment_qty_units")
    quality = models.DecimalField(_('quality'), max_digits=3, decimal_places=0, default=Decimal("0"))
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of value'), related_name="commitment_value_units")
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='commitments_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='commitments_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = CommitmentManager()

    class Meta:
        ordering = ('due_date',)

    def __str__(self):
        abbrev = ""
        if self.event_type.relationship == "cite":
            quantity_string = ""
        else:
            quantity_string = str(remove_exponent(self.quantity))
            if self.unit_of_quantity:
                abbrev = self.unit_of_quantity.abbrev
                if hasattr(self, 'exchange') and self.exchange:
                    if hasattr(self.exchange, 'join_request') and self.exchange.join_request:
                        if self.exchange.join_request.is_flexprice():
                            quantity_string = "?" #+str(self.quantity)
        resource_name = ""
        process_name = ""
        if self.resource_type:
            resource_name = self.resource_type.name
            if self.unit_of_quantity:
                if self.unit_of_quantity.name == resource_name:
                    abbrev = ''
                elif self.unit_of_quantity.is_currency():
                    resource_name = ''
                    abbrev = self.unit_of_quantity.name
        if self.process:
            process_name = self.process.name
        if self.order:
            from_agt = 'Unassigned'
            if self.from_agent:
                from_agt = self.from_agent.name
            to_agt = 'Unassigned'
            if self.to_agent:
                to_agt = self.to_agent.name
            if self.event_type.relationship == "out":
                name1 = from_agt
                name2 = to_agt
                prep = "for"
            else:
                name2 = from_agt
                name1 = to_agt
                prep = "from"
            return ' '.join([
                name1,
                self.event_type.name,
                quantity_string,
                abbrev,
                resource_name,
                self.due_date.strftime('%Y-%m-%d'),
                prep,
                name2,
            ])
        else:
            name1 = 'from ?'
            if self.from_agent:
                name1 = 'from '+str(self.from_agent.name)
            name2 = 'to ?'
            if self.to_agent:
                name2 = 'to '+str(self.to_agent.name)

            return ' '.join([
                process_name,
                self.event_type.label,
                quantity_string,
                abbrev,
                resource_name,
                self.due_date.strftime('%Y-%m-%d'),
                name1,
                name2
        ])

    def show_name(self, agent=None, forced=False):
        name = self.__str__()
        newname = name
        if agent:
            gives = self.from_agent == agent
            takes = self.to_agent == agent
            if not self.exchange:
                if not self.transfer.exchange:
                    print("error showing name: not self.exchange?")
                    return "error showing name: not self.exchange?"
                else:
                    loger.warning("The Commitment has no exchange but its transfer has, FIXING!")
                    self.exchange = self.transfer.exchange
                    self.save()
            #print("com:"+str(self.id)+" ag:"+str(agent)+" gives:"+str(gives)+" takes:"+str(takes))
            if hasattr(self.exchange.exchange_type, 'ocp_record_type') and self.exchange.exchange_type.ocp_record_type:
              x_actions = self.exchange.exchange_type.ocp_record_type.x_actions()
              for action in x_actions:
                opposite = action.opposite()
                if opposite:
                    if action.clas and opposite.clas:
                        newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                    if name == newname:
                        newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                    if gives or forced:
                        if action.clas == 'buy' or action.clas == 'receive':
                            name = newname
                    if takes or forced:
                        if action.clas == 'sell' or action.clas == 'give':
                            name = newname
            else:
                print("The comm exchange.exchange_type has not ocp_record_type ? cm:"+str(self.id)+" et:"+str(self.exchange.exchange_type))
                loger.info("The comm exchange.exchange_type has not ocp_record_type ? cm:"+str(self.id)+" et:"+str(self.exchange.exchange_type))
        #else:
        #    print("No agent??")
        return name

    def status(self):
        if self.unfilled_quantity() > 0: # if over-payed this is negative
            return 'pending'
        else:
            if self.fulfilling_events():
                return 'complete'
            else:
                return 'pending'

    @property #ValueFlows
    def action(self):
        return self.event_type.action

    @property #ValueFlows
    def numeric_value(self):
        return self.quantity

    @property #ValueFlows
    def unit(self):
        return self.unit_of_quantity

    @property #ValueFlows
    def planned_start(self):
        return self.start_date.isoformat()

    @property #ValueFlows
    def committed_on(self):
        return self.commitment_date.isoformat()

    @property #ValueFlows
    def due(self):
        return self.due_date.isoformat()

    @property #ValueFlows
    def is_finished(self):
        return self.finished

    @property #ValueFlows
    def note(self):
        return self.description

    @property #ValueFlows
    def provider(self):
        return self.from_agent

    @property #ValueFlows
    def receiver(self):
        return self.to_agent

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    @property #ValueFlows
    def involves(self):
        return self.resource

    @property #ValueFlows
    def resource_classified_as(self):
        return self.resource_type

    @property #ValueFlows
    def input_of(self):
        if not self.event_type.relationship == "out":
            return self.process
        return None

    @property #ValueFlows
    def output_of(self):
        if self.event_type.relationship == "out":
            return self.process
        return None

    @property #ValueFlows
    def is_plan_deliverable(self):
        if self.order:
            return True
        else:
            return False

    def shorter_label(self):
        quantity_string = str(self.quantity)
        resource_name = ""
        abbrev = ""
        if self.unit_of_quantity:
           abbrev = self.unit_of_quantity.abbrev
        if self.resource_type:
            resource_name = self.resource_type.name
        return ' '.join([
            quantity_string,
            abbrev,
            resource_name,
        ])

    def save(self, *args, **kwargs):
        from_id = "Unassigned"
        if self.from_agent:
            from_id = str(self.from_agent.id)
        slug = "-".join([
            str(self.event_type.id),
            from_id,
            self.due_date.strftime('%Y-%m-%d'),
        ])
        unique_slugify(self, slug)
        #notify_here?
        super(Commitment, self).save(*args, **kwargs)

    def save_api(self):
        if not self.order_item:
            if self.process:
                self.order_item = self.process.order_item()
                #TODO: why did I do this?  how to handle processes that are part of a plan but have no deliverables?
                #if not self.order_item:
                #    raise ValidationError("Cannot find deliverable in this process chain, cannot save.")
        if self.pk:
            self.handle_commitment_changes()
        self.save()

    #duplicated/modified from views to support the api
    def handle_commitment_changes(self):
        old_ct = Commitment.objects.get(pk=self.pk)
        new_rt = self.resource_type
        old_demand = old_ct.independent_demand
        new_demand = self.independent_demand
        new_qty = self.quantity
        propagators = []
        explode = True
        if old_ct.event_type.relationship == "out":
            dependants = old_ct.process.incoming_commitments()
            propagators.append(old_ct)
            if new_qty != old_ct.quantity:
                explode = False
        else:
            dependants = old_ct.associated_producing_commitments()
        old_rt = old_ct.resource_type
        order_item = old_ct.order_item

        if not propagators:
            for dep in dependants:
                if order_item:
                    if dep.order_item == order_item:
                        propagators.append(dep)
                        explode = False
                else:
                    #changed for work commitment.due_date
                    if dep.is_work():
                        if dep.due_date == old_ct.process.due_date:
                            if dep.quantity == old_ct.quantity:
                                propagators.append(dep)
                                explode = False
                    else:
                        if dep.due_date == old_ct.process.start_date:
                            if dep.quantity == old_ct.quantity:
                                propagators.append(dep)
                                explode = False
        if new_rt != old_rt:
            for ex_ct in old_ct.associated_producing_commitments():
                if ex_ct.order_item == order_item:
                    ex_ct.delete_dependants()
            old_ct.delete()
            explode = True
        elif new_qty != old_ct.quantity:
            delta = new_qty - old_ct.quantity
            for pc in propagators:
                if new_demand != old_demand:
                    self.propagate_changes(pc, delta, old_demand, new_demand, [])
                else:
                    self.propagate_qty_change(pc, delta, [])
        else:
            if new_demand != old_demand:
                #this is because we are just changing the order
                delta = Decimal("0")
                for pc in propagators:
                    self.propagate_changes(pc, delta, old_demand, new_demand, [])
                explode = False

        return explode

    #duplicated/modified from views to support the api
    def propagate_qty_change(self, commitment, delta, visited):
        process = commitment.process
        if commitment not in visited:
            visited.append(commitment)
            for ic in process.incoming_commitments():
                if ic.event_type.relationship != "cite":
                    input_ctype = ic.commitment_type()
                    output_ctype = commitment.commitment_type()
                    ratio = input_ctype.quantity / output_ctype.quantity
                    new_delta = (delta * ratio).quantize(Decimal('.01'), rounding=ROUND_UP)

                    ic.quantity += new_delta
                    ic.save()
                    rt = ic.resource_type
                    pcs = ic.associated_producing_commitments()
                    if pcs:
                        oh_qty = 0
                        if rt.substitutable:
                            if ic.event_type.resource_effect == "-":
                                oh_qty = rt.onhand_qty_for_commitment(ic)
                        if oh_qty:
                            delta_delta = ic.quantity - oh_qty
                            new_delta = delta_delta
                    order_item = ic.order_item
                    for pc in pcs:
                        if pc.order_item == order_item:
                            self.propagate_qty_change(pc, new_delta, visited)
        commitment.quantity += delta
        commitment.save()

    #duplicated/modified from views to support the api
    def propagate_changes(self, commitment, delta, old_demand, new_demand, visited):
        process = commitment.process
        order_item = commitment.order_item
        if process not in visited:
            visited.append(process)
            for ic in process.incoming_commitments():
                ratio = ic.quantity / commitment.quantity
                new_delta = (delta * ratio).quantize(Decimal('.01'), rounding=ROUND_UP)
                ic.quantity += new_delta
                ic.order_item = order_item
                ic.save()
                rt = ic.resource_type
                for pc in ic.associated_producing_commitments():
                    if pc.order_item == order_item:
                        self.propagate_changes(pc, new_delta, old_demand, new_demand, visited)
        commitment.quantity += delta
        commitment.independent_demand = new_demand
        commitment.save()

    def label(self):
        return self.event_type.get_relationship_display()

    def class_label(self):
        return " ".join(["Commitment for", self.label()])

    def cycle_id(self):
        stage_id = ""
        if self.stage:
            stage_id = str(self.stage.id)
        state_id = ""
        if self.state:
            state_id = str(self.state.id)
        return "-".join([str(self.resource_type.id), stage_id, state_id])

    def resource_type_node_id(self):
        answer = "-".join(["ProcessResource", self.cycle_id()])
        return answer

    def commitment_type(self):
        rt = self.resource_type
        pt = None
        if self.process:
            pt = self.process.process_type
        if pt:
            try:
                return ProcessTypeResourceType.objects.get(
                    resource_type=rt, process_type=pt)
            except ProcessTypeResourceType.DoesNotExist:
                return None
        return None

    def feature_label(self):
        if not self.order:
            return ""
        features = self.resource_type.features.all()
        if not features:
            return ""
        inputs = [ct.resource_type for ct in self.process.incoming_commitments()]
        selected_options = []
        for feature in features:
            options = feature.options.all()
            for option in options:
                if option.component in inputs:
                    selected_options.append(option.component)
        names = ', '.join([so.name for so in selected_options])
        prefix = "with option"
        if len(selected_options) > 1:
              prefix = "with options"
        return " ".join([prefix, names])

    def timeline_title(self):
        quantity_string = str(self.quantity)
        from_agt = 'Unassigned'
        if self.from_agent:
            from_agt = self.from_agent.name
        process = "Unknown"
        if self.process:
            process = self.process.name
        return ' '.join([
            self.resource_type.name,
            'from',
            from_agt,
            'to',
            process,
        ])

    def form_prefix(self):
        return "-".join(["CT", str(self.id)])

    def invite_form_prefix(self):
        return "-".join(["invite", str(self.id)])

    def commitment_form(self):
        from valuenetwork.valueaccounting.forms import CommitmentForm
        prefix=self.form_prefix()
        return CommitmentForm(instance=self, prefix=prefix)

    def join_form_prefix(self):
        return "-".join(["JOIN", str(self.id)])

    def join_form(self):
        from valuenetwork.valueaccounting.forms import CommitmentForm
        prefix = self.join_form_prefix()
        init = {
            "start_date": datetime.date.today,
            "unit_of_quantity": self.unit_of_quantity,
            "description": "Explain how you propose to help.",
            }
        return CommitmentForm(initial=init, prefix=prefix)

    def change_form(self):
        from valuenetwork.valueaccounting.forms import ChangeCommitmentForm
        prefix=self.form_prefix()
        return ChangeCommitmentForm(instance=self, prefix=prefix)

    def process_form(self):
        from valuenetwork.valueaccounting.forms import ProcessForm
        start_date = self.start_date
        if not start_date:
            start_date = self.due_date
        name = " ".join(["Produce", self.resource_type.name])
        init = {
            "name": name,
            "context_agent": self.context_agent,
            "start_date": start_date,
            "end_date": self.due_date,
            }
        prefix=self.form_prefix()
        return ProcessForm(initial=init, prefix=prefix)

    def change_work_form(self):
        from valuenetwork.valueaccounting.forms import WorkCommitmentForm
        prefix=self.form_prefix()
        pattern = None
        if self.process:
            pattern = self.process.process_pattern
        return WorkCommitmentForm(instance=self, pattern=pattern, prefix=prefix)

    def invite_collaborator_form(self):
        from valuenetwork.valueaccounting.forms import InviteCollaboratorForm
        prefix=self.invite_form_prefix()
        unit = self.resource_type.unit
        qty_help = ""
        if unit:
            rt_name = self.resource_type.name
            unit_string = unit.abbrev
            qty_help = " ".join(["Type of work:", rt_name, ", unit:", unit.abbrev, ", up to 2 decimal places"])
        form = InviteCollaboratorForm(
            qty_help=qty_help,
            prefix=prefix)

        return form

    def can_add_to_resource(self):
        #todo: figure out how to allow for workflow stream resources
        #easy way: edit previous change event
        #hard way: a new change event (or is that really a change event?)
        if self.resource_type.substitutable:
            if not self.stage:
                return True
        return False

    def addable_resources(self):
        if self.can_add_to_resource():
            if self.onhand():
                return True
        return False

    def resource_create_form(self, data=None):
        if self.resource_type.inventory_rule == "yes":
            from valuenetwork.valueaccounting.forms import ProduceEconomicResourceForm
            init = {
                "from_agent": self.from_agent,
                "quantity": self.quantity,
                "unit_of_quantity": self.resource_type.unit,
            }
            return ProduceEconomicResourceForm(prefix=self.form_prefix(), initial=init, data=data)
        else:
            from valuenetwork.valueaccounting.forms import UninventoriedProductionEventForm
            init = {
                "from_agent": self.from_agent,
                "quantity": self.quantity,
            }
            unit = self.resource_type.unit
            qty_help = ""
            if unit:
                unit_string = unit.abbrev
                qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
            return UninventoriedProductionEventForm(qty_help=qty_help, prefix=self.form_prefix(), initial=init, data=data)

    def resource_transform_form(self, data=None):
        from valuenetwork.valueaccounting.forms import TransformEconomicResourceForm
        quantity = self.quantity
        resources = self.resources_ready_to_be_changed()
        if resources:
            quantity = resources[0].quantity
        init = {
            "from_agent": self.from_agent,
            "event_date": datetime.date.today(),
            "quantity": quantity,
        }
        unit = self.resource_type.unit
        qty_help = ""
        if unit:
            unit_string = unit.abbrev
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return TransformEconomicResourceForm(qty_help=qty_help, prefix=self.form_prefix(), initial=init, data=data)

    def select_resource_form(self, data=None):
        from valuenetwork.valueaccounting.forms import SelectResourceForm
        init = {
            "quantity": self.quantity,
            #"unit_of_quantity": self.resource_type.unit,
        }
        return SelectResourceForm(prefix=self.form_prefix(), resource_type=self.resource_type, initial=init, data=data)

    def resource_change_form(self):
        resource = self.output_resource()
        if resource:
            return resource.change_form(self.form_prefix())
        else:
            return self.resource_type.resource_create_form(self.form_prefix())

    def todo_change_form(self):
        from valuenetwork.valueaccounting.forms import TodoForm
        prefix=self.form_prefix()
        return TodoForm(instance=self, prefix=prefix)

    def work_todo_change_form(self):
        from work.forms import WorkTodoForm
        agent=self.to_agent #poster of todo
        prefix=self.form_prefix()
        patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
        if patterns:
            pattern = patterns[0].pattern
            todo_form = WorkTodoForm(agent=agent, pattern=pattern, instance=self, prefix=prefix)
        else:
            todo_form = WorkTodoForm(agent=agent, instance=self, prefix=prefix)
        return todo_form

    #obsolete?
    """
    def work_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import TimeEventForm, InputEventForm
        prefix=self.form_prefix()
        unit = self.resource_type.unit
        if unit.unit_type == "time":
            return TimeEventForm(prefix=prefix, data=data)
        else:
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
            return InputDistributionEventForm(qty_help=qty_help, prefix=prefix, data=data)
    """

    def input_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        qty_help = " ".join(["unit:", self.unit_of_quantity.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix, data=data)

    def input_event_form_init(self, init=None, data=None):
        from valuenetwork.valueaccounting.forms import InputEventAgentForm
        prefix=self.form_prefix()
        qty_help = ""
        unit = self.resource_type.unit
        if unit:
            if unit.abbrev:
                unit_string = unit.abbrev
            else:
                unit_string = unit.name
            qty_help = " ".join(["unit:", unit_string, ", up to 2 decimal places"])
        if init:
            return InputEventAgentForm(qty_help=qty_help, context_agent=self.context_agent, prefix=prefix, initial=init, data=data)
        else:
            return InputEventAgentForm(qty_help=qty_help, context_agent=self.context_agent, prefix=prefix, data=data)

    def consumption_event_form(self):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        qty_help = " ".join(["unit:", self.unit_of_quantity.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix)

    #obsolete
    def old_use_event_form(self):
        from valuenetwork.valueaccounting.forms import TimeEventForm, InputEventForm
        prefix=self.form_prefix()
        unit = self.resource_type.directional_unit("use")
        if unit.unit_type == "time":
            return TimeEventForm(prefix=prefix)
        else:
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
            return InputEventForm(qty_help=qty_help, prefix=prefix)

    def use_event_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        prefix=self.form_prefix()
        unit = self.resource_type.directional_unit("use")
        qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, prefix=prefix, data=data)

    def resources_ready_to_be_changed(self):
        resources = []
        if self.event_type.stage_to_be_changed():
            if self.resource_type.substitutable:
                resources = EconomicResource.objects.filter(
                    resource_type=self.resource_type,
                    stage=self.stage)
            else:
                resources = EconomicResource.objects.filter(
                    resource_type=self.resource_type,
                    stage=self.stage,
                    order_item=self.order_item)
        return resources

    def fulfilling_events(self):
        return self.fulfillment_events.all()

    def fulfilling_events_condensed(self):
        event_list = self.fulfillment_events.all()
        condensed_events = []
        if event_list:
            summaries = {}
            for event in event_list:
                try:
                    key = "-".join([
                        str(event.from_agent.id),
                        str(event.context_agent.id),
                        str(event.resource_type.id),
                        str(event.event_type.id)
                        ])
                    if not key in summaries:
                        summaries[key] = EventSummary(
                            event.from_agent,
                            event.context_agent,
                            event.resource_type,
                            event.event_type,
                            Decimal('0.0'))
                    summaries[key].quantity += event.quantity
                except AttributeError:
                    msg = " ".join(["invalid summary key:", key])
                    assert False, msg
            condensed_events = list(summaries.values())
        return condensed_events


    #obsolete
    def fulfilling_shipment_events(self):
        return self.fulfillment_events.filter(event_type__name="Shipment")

    def todo_event(self):
        events = self.fulfilling_events()
        if events:
            return events[0]
        else:
            return None

    def is_deletable(self):
        if self.fulfilling_events():
            return False
        else:
            return True

    def delete_dependants(self):
        trash = []
        if self.event_type.relationship == "out":
            collect_trash(self, trash)
        else:
            collect_lower_trash(self, trash)
        for proc in trash:
            if proc.outgoing_commitments().count() <= 1:
                proc.delete()

    def fulfilling_events_from_agent(self, agent):
        return self.fulfillment_events.filter(from_agent=agent)

    def failed_outputs(self):
        answer = []
        events = self.process.failed_outputs()
        for event in events:
            if event.resource_type == self.resource_type:
                answer.append(event)
        return answer

    def failed_output_qty(self):
        return sum(evt.quantity for evt in self.failed_outputs())

    def agent_has_labnotes(self, agent):
        if self.fulfillment_events.filter(from_agent=agent):
            return True
        else:
            return False

    def fulfilled_quantity(self):
        return sum(evt.quantity for evt in self.fulfilling_events())

    def unfilled_quantity(self):
        return self.quantity - self.fulfilled_quantity()

    def remaining_formatted_quantity(self):
        qty = self.unfilled_quantity()
        unit = self.unit_of_quantity
        if unit:
            if unit.symbol:
                answer = "".join([unit.symbol, str(qty)])
            else:
                answer = " ".join([str(qty), unit.abbrev])
        else:
            answer = str(qty)
        return answer

    def is_fulfilled(self):
        if self.unfilled_quantity():
            return False
        return True

    def onhand(self):
        answer = []
        rt = self.resource_type
        if self.stage:
            resources = EconomicResource.goods.filter(
                stage=self.stage,
                resource_type=rt)
        else:
            resources = EconomicResource.goods.filter(resource_type=rt)
        if not rt.substitutable:
            resources = resources.filter(order_item=self.order_item)
        for resource in resources:
            if resource.quantity > 0:
                answer.append(resource)
            else:
                if self.fulfillment_events.filter(resource=resource):
                    answer.append(resource)
        return answer

    def onhand_for_citation(self):
        answer = []
        rt = self.resource_type
        if self.stage:
            resources = EconomicResource.goods.filter(
                stage=self.stage,
                resource_type=rt)
        else:
            resources = EconomicResource.goods.filter(resource_type=rt)
        for resource in resources:
            if resource.quantity > 0:
                answer.append(resource)
            else:
                if self.fulfillment_events.filter(resource=resource):
                    answer.append(resource)
        return answer

    def onhand_with_fulfilled_quantity(self):
        resources = self.onhand()
        for resource in resources:
            events = self.fulfillment_events.filter(resource=resource)
            resource.fulfilled_quantity = sum(evt.quantity for evt in events)
        return resources

    def consumable_resources(self):
        answer = []
        if self.event_type.consumes_resources():
            events = self.fulfillment_events.all()
            event_resources = [event.resource for event in events]
            event_resources = set(event_resources)
            resources = self.resource_type.all_resources()
            for r in resources:
                if r.quantity:
                    answer.append(r)
                else:
                    if r in event_resources:
                        answer.append(r)
        return answer

    def quantity_to_buy(self):
        return self.net()

    def net(self):
        rt = self.resource_type
        if not rt.substitutable:
            return self.quantity
        oh_qty = rt.onhand_qty_for_commitment(self)
        if oh_qty >= self.quantity:
            return 0
        sked_qty = rt.scheduled_qty_for_commitment(self)
        if self.event_type.resource_effect == "-":
            remainder = self.quantity - oh_qty
            if sked_qty >= remainder:
                return Decimal("0")
            return remainder - sked_qty
        else:
            if oh_qty + sked_qty:
                return Decimal("0")
            elif self.event_type.resource_effect == "=":
                return Decimal("1")
            else:
                return self.quantity

    def net_for_order(self):
        #this method does netting after an order has been scheduled
        #see tiddler Bug 2105-01-25
        rt = self.resource_type
        stage = self.stage
        due_date = self.due_date
        if not rt.substitutable:
            if stage:
                onhand = rt.onhand_for_stage(stage)
            else:
                onhand = rt.onhand()
            oh_qty = sum(oh.quantity for oh in onhand if oh.order_item==self.order_item)
        else:
            oh_qty = rt.onhand_qty_for_commitment(self)
        if oh_qty >= self.quantity:
            return 0
        sked_rcts = rt.producing_commitments().filter(due_date__lte=self.due_date)
        if stage:
            sked_rcts = sked_rcts.filter(stage=stage)
            priors = rt.consuming_commitments_for_stage(stage).filter(due_date__lt=due_date)
        else:
            priors = rt.consuming_commitments().filter(due_date__lt=due_date)
        if not rt.substitutable:
            sked_qty = sum(sr.quantity for sr in sked_rcts if sr.order_item==self.order_item)
        else:
            sked_qty = sum(sr.quantity for sr in sked_rcts)
        sked_qty = sked_qty - sum(p.quantity for p in priors)
        avail = oh_qty + sked_qty
        remainder = self.quantity - avail
        if remainder < 0:
            remainder = Decimal("0")
        if self.event_type.resource_effect == "-":
            return remainder
        else:
            if not remainder:
                return Decimal("0")
            elif self.event_type.resource_effect == "=":
                return Decimal("1")
            else:
                return remainder

    def needs_production_process(self):
        #I know > 0 is unnecessary, just being explicit
        if self.net_for_order() > 0:
            return True
        return False

    def creates_resources(self):
        return self.event_type.creates_resources()

    def consumes_resources(self):
        return self.event_type.consumes_resources()

    def is_change_related(self):
        return self.event_type.is_change_related()

    def applies_stage(self):
        return self.event_type.applies_stage()

    def changes_stage(self):
        return self.event_type.changes_stage()

    def output_resources(self):
        answer = None
        if self.event_type.relationship == "out":
            answer = [event.resource for event in self.fulfilling_events()]
        return answer

    def output_resource(self):
        #todo: this is a hack, cd be several resources
        answer = None
        if self.event_type.relationship == "out":
            events = self.fulfilling_events()
            if events:
                event = events[0]
                answer = event.resource
        return answer

    def is_shipment(self):
        if self.order:
            if self.order.order_type == "customer":
                exchange = self.order.exchange()
                if exchange:
                    if exchange.use_case.identifier == "demand_xfer":
                        if self.event_type.name == "Give":
                            return True
        return False

    def generate_producing_process(self, user, visited, inheritance=None, explode=False):

        """ This method is usually used in recipe explosions.

            inheritance is optional, can be positional or keyword arg. It means
            the recipe in use was inherited from a parent.
            explode is also optional. If used by a caller, and inheritance is not used,
            explode must be a keyword arg.
        """
        qty_required = self.quantity
        rt = self.resource_type
        should_net = False
        if self.order:
            if self.order.order_type == "customer":
                should_net = True
        else:
            should_net = True
        if should_net:
            qty_required = self.net()
        process=None
        if qty_required:
            #pr changed
            ptrt, inheritance = rt.main_producing_process_type_relationship(stage=self.stage, state=self.state)
            if ptrt:
                resource_type = self.resource_type
                if self.is_shipment():
                    producing_commitment = Commitment(
                        resource_type=resource_type,
                        independent_demand=self.independent_demand,
                        order_item=self,
                        event_type=ptrt.event_type,
                        context_agent=self.context_agent,
                        stage=ptrt.stage,
                        state=ptrt.state,
                        quantity=self.quantity,
                        unit_of_quantity=resource_type.unit,
                        due_date=self.due_date,
                        created_by=user)
                    producing_commitment.save()
                else:
                    producing_commitment = self
                pt = ptrt.process_type
                start_date = self.due_date - datetime.timedelta(minutes=pt.estimated_duration)
                process = Process(
                    name=pt.name,
                    notes=pt.description or "",
                    process_type=pt,
                    process_pattern=pt.process_pattern,
                    #Todo: apply selected_context_agent here?
                    #only if inheritance?
                    context_agent=pt.context_agent,
                    url=pt.url,
                    end_date=self.due_date,
                    start_date=start_date,
                    plan=self.independent_demand,
                    created_by=user,
                )
                process.save()
                producing_commitment.process=process
                producing_commitment.context_agent = process.context_agent
                producing_commitment.to_agent = self.context_agent
                producing_commitment.save()
                if explode:
                    demand = self.independent_demand
                    process.explode_demands(demand, user, visited, inheritance)
        return process

    def sources(self):
        arts = self.resource_type.producing_agent_relationships()
        for art in arts:
            art.order_release_date = self.due_date - datetime.timedelta(days=art.lead_time)
            art.too_late = art.order_release_date < datetime.date.today()
            art.commitment = self
        return arts

    def possible_work_users(self):
        if self.context_agent:
            srcs = self.resource_type.work_agents()
            members = self.context_agent.all_members_list()
            agents = [agent for agent in srcs if agent in members]
            users = [a.user() for a in agents if a.user()]
            return [u.user for u in users]
        else:
            return []

    def workers(self):
        answer = []
        if self.event_type.relationship=="work":
            answer = [evt.from_agent for evt in self.fulfilling_events() if evt.from_agent]
            if self.from_agent:
                answer.append(self.from_agent)
        return list(set(answer))

    def reschedule_forward(self, delta_days, user):
        self.due_date = self.due_date + datetime.timedelta(days=delta_days)
        self.changed_by = user
        self.save()
        order = self.order
        if order:
            order.reschedule_forward(delta_days, user)
        #find related shipment commitments
        else:
            demand = self.independent_demand
            oi = self.order_item
            if oi != self:
                if oi.resource_type == self.resource_type:
                    if oi.stage == self.stage:
                        oi.order.reschedule_forward(delta_days, user)

    def reschedule_forward_from_source(self, lead_time, user):
        lag = datetime.date.today() - self.due_date
        delta_days = lead_time + lag.days + 1
        #todo: next line may need to be removed
        #if process.reschedule_connections is revived
        self.reschedule_forward(delta_days, user)
        self.process.reschedule_forward(delta_days, user)

    def associated_wanting_commitments(self):
        wanters = self.resource_type.wanting_commitments().exclude(id=self.id)
        if self.stage:
            wanters = wanters.filter(stage=self.stage)
        return [ct for ct in wanters if ct.order_item == self.order_item]

    def associated_producing_commitments(self):
        if self.stage:
            producers = self.resource_type.producing_commitments().filter(stage=self.stage).exclude(id=self.id)
        else:
            producers = self.resource_type.producing_commitments().exclude(id=self.id)
        #todo: this shd just be a filter, but need to test the change, so do later
        return [ct for ct in producers if ct.order_item == self.order_item]

    def active_producing_commitments(self):
        if self.stage:
            return self.resource_type.active_producing_commitments().filter(
                stage=self.stage)
        else:
            return self.resource_type.active_producing_commitments()

    def scheduled_receipts(self):
        rt = self.resource_type
        if rt.substitutable:
            return self.active_producing_commitments()
        else:
            return self.associated_producing_commitments()

    def is_change_related(self):
        return self.event_type.is_change_related()

    def is_work(self):
        return self.event_type.is_work()

    def remove_order(self):
        self.order = None
        self.save()

    def update_stage(self, process_type):
        self.stage = process_type
        self.save()

    def process_chain(self):
        processes = []
        self.process.all_previous_processes(processes, [], 0)
        return processes

    def find_order_item(self):
        #this is a temporary method for data migration after the flows branch is deployed
        answer = None
        if self.independent_demand:
            ois = self.independent_demand.order_items()
            if ois:
                if ois.count() == 1:
                    return ois[0]
                else:
                    return ois

    def unique_processes_for_order_item(self, visited):
        unique_processes = []
        all_processes = self.all_processes_in_my_order_item()
        for process in all_processes:
            if process not in visited:
                visited.add(process)
                unique_processes.append(process)
        return unique_processes

    def all_processes_in_my_order_item(self):
        ordered_processes = []
        order_item = self.order_item
        if order_item:
            order = self.independent_demand
            if order:
                processes = order.all_processes()
                for p in processes:
                    if p.order_item() == order_item:
                        ordered_processes.append(p)
        return ordered_processes

    def last_process_in_my_order_item(self):
        processes = self.all_processes_in_my_order_item()
        if processes:
            return processes[-1]
        else:
            return None

    def is_order_item(self):
        if self.order:
            return True
        else:
            return False

    def is_workflow_order_item(self):
        if self.process and self.order:
            return self.process.is_staged()
        else:
            return False

    def process_types(self):
        pts = []
        for process in self.all_processes_in_my_order_item():
            if process.process_type:
                pts.append(process.process_type)
        return list(set(pts))

    def available_workflow_process_types(self):
        all_pts = ProcessType.objects.workflow_process_types()
        my_pts = self.process_types()
        available_pt_ids = []
        for pt in all_pts:
            if pt not in my_pts:
                available_pt_ids.append(pt.id)
        return ProcessType.objects.filter(id__in=available_pt_ids)

    def workflow_quantity(self):
        if self.is_workflow_order_item():
            return self.quantity
        else:
            return None

    def workflow_unit(self):
        if self.is_workflow_order_item():
            return self.unit_of_quantity
        else:
            return None

    def change_commitment_quantities(self, qty):
        if self.is_workflow_order_item():
            processes = self.process_chain()
            for process in processes:
                for commitment in process.commitments.all():
                    if commitment.is_change_related():
                        commitment.quantity = qty
                        commitment.save()
                    elif commitment.is_work():
                        if commitment.quantity == self.workflow_quantity() and commitment.unit_of_quantity == self.workflow_unit():
                            commitment.quantity = qty
                            commitment.save()
        return self

    def change_workflow_project(self, project):
        if self.is_workflow_order_item():
            processes = self.process_chain()
            for process in processes:
                #process.context_agent = project
                #process.save()
                process.change_context_agent(context_agent=project)
        return self

    def adjust_workflow_commitments_process_added(self, process, user): #process added to the end of the order item
        last_process = self.last_process_in_my_order_item()
        process.add_stream_commitments(last_process=last_process, user=user)
        last_commitment = last_process.main_outgoing_commitment()
        last_commitment.remove_order()
        return self

    def adjust_workflow_commitments_process_inserted(self, process, next_process, user):
        all_procs = self.all_processes_in_my_order_item()
        process_index = all_procs.index(next_process)
        if process_index > 0:
            last_process = all_procs[process_index - 1]
        else:
            last_process = None
        next_commitment = next_process.to_be_changed_requirements()[0]
        if last_process:
            process.insert_stream_commitments(last_process=last_process, user=user)
        else:
            process.insert_first_stream_commitments(next_commitment=next_commitment, user=user)
        next_commitment.update_stage(process.process_type)
        return self

    def adjust_workflow_commitments_process_deleted(self, process, user):
        all_procs = self.all_processes_in_my_order_item()
        process_index = all_procs.index(process)
        last_process = None
        next_commitment = None
        if process_index > 0:
            last_process = all_procs[process_index - 1]
        if process == self.last_process_in_my_order_item():
            if last_process:
                last_commitment = last_process.main_outgoing_commitment()
                last_commitment.order = self.order
                last_commitment.order_item = last_commitment
                last_commitment.save()
                #change the order item in dependent commitments
                #before deleting the last process
                if self.order_item == self:
                    dependent_commitments = Commitment.objects.filter(order_item=self)
                    for dc in dependent_commitments:
                        dc.order_item = last_commitment
                        dc.save()
        else:
            next_process = all_procs[process_index + 1]
            next_commitment = next_process.to_be_changed_requirements()[0]
        if last_process and next_commitment:
            next_commitment.update_stage(last_process.process_type)
        return None

    def compute_income_fractions(self, value_equation):
        """Returns a list of contribution events for an order_item,

        where each event has event.share and event.fraction.
        event.share is that event's share based on its
        proportional contribution to the order_item's resource value.
        event.fraction is that event's fraction of the total shares.

        Commitment (order_item) method.

        """
        events = self.fulfilling_events()
        resources = []
        resource = None
        shares = []
        total = 0
        for event in events:
            if event.resource:
                if event.resource not in resources:
                    resources.append(event.resource)
        if resources:
            if len(resources) == 1:
                resource = resources[0]
            else:
                #does not handle different resources per order_item yet.
                msg = " ".join([self.__str__(), "has different resources, not handled yet."])
                assert False, msg
        if resource:
            shares = self.compute_income_fractions_for_resource(value_equation, resource)
        else:
            shares = self.compute_income_fractions_for_process(value_equation)
        if shares:
            total = sum(s.share for s in shares)
        if total:
            for s in shares:
                s.fraction = s.share / total
        #print("total shares:", total)
        return shares

    def compute_income_fractions_for_resource(self, value_equation, resource):
        #print("*** rollup up resource value")
        visited = set()
        path = []
        depth = 0
        #value_per_unit = resource.roll_up_value(path, depth, visited, value_equation)
        #print("resource value_per_unit:", value_per_unit)
        #value = self.quantity * value_per_unit
        visited = set()
        #print("*** computing income shares")
        shares = []
        resource.compute_income_shares(value_equation, self.quantity, shares, visited)
        return shares

    def compute_income_fractions_for_process(self, value_equation):
        #Commitment (order_item) method
        shares = []
        visited = set()
        path = []
        depth = 0
        #todo: handle shipment commitments with no process
        p = self.process
        if p:
            #print("*** rollup up process value")
            #value = p.roll_up_value(path, depth, visited, value_equation)
            #print("processvalue:", value)
            visited = set()
            #print("*** computing income shares")
            p.compute_income_shares(value_equation, self, self.quantity, shares, visited)
        else:
            production_commitments = self.get_production_commitments_for_shipment()
            if production_commitments:
                #todo: later, work out how to handle multiple production commitments
                pc = production_commitments[0]
                p = pc.process
                if p:
                    visited = set()
                    p.compute_income_shares(value_equation, self, self.quantity, shares, visited)

        return shares

    def get_production_commitments_for_shipment(self):
        production_commitments = []
        if self.event_type.name == "Shipment":
            production_commitments = Commitment.objects.filter(
                order_item=self,
                event_type__relationship="out",
                resource_type=self.resource_type)
        return production_commitments


#todo: not used.
class Reciprocity(models.Model):
    """One Commitment reciprocating another.

    The EconomicAgents in the reciprocal commitments
    must be opposites.
    That is, the from_agent of one commitment must be
    the to-agent of the other commitment, and vice versa.
    Reciprocal commitments have a M:M relationship:
    that is, one commitment can be reciprocated by many other commitments,
    and the other commitment can reciprocate many initiating commitments.

    """
    initiating_commitment = models.ForeignKey(Commitment, on_delete=models.CASCADE,
        related_name="initiated_commitments", verbose_name=_('initiating commitment'))
    reciprocal_commitment = models.ForeignKey(Commitment, on_delete=models.CASCADE,
        related_name="reciprocal_commitments", verbose_name=_('reciprocal commitment'))
    reciprocity_date = models.DateField(_('reciprocity date'), default=datetime.date.today)

    class Meta:
        ordering = ('reciprocity_date',)

    def __str__(self):
        return ' '.join([
            'inititating commmitment:',
            self.initiating_commmitment.__str__(),
            'reciprocal commmitment:',
            self.reciprocal_commitment.__str__(),
            self.reciprocity_date.strftime('%Y-%m-%d'),
        ])

    def clean(self):
        if self.initiating_commitment.from_agent.id != self.reciprocal_commitment.to_agent.id:
            raise ValidationError('Initiating commitment from_agent must be the reciprocal commitment to_agent.')
        if self.initiating_commitment.to_agent.id != self.reciprocal_commitment.from_agent.id:
            raise ValidationError('Initiating commitment to_agent must be the reciprocal commitment from_agent.')


class SelectedOption(models.Model):
    commitment = models.ForeignKey(Commitment, on_delete=models.CASCADE,
        related_name="options", verbose_name=_('commitment'))
    option = models.ForeignKey(Option, on_delete=models.CASCADE,
        related_name="commitments", verbose_name=_('option'))

    class Meta:
        ordering = ('commitment', 'option')

    def __str__(self):
        return " ".join([self.option.name, "option for", self.commitment.resource_type.name])

def check_summary(agent, context_agent, resource_type, event_type):
    events = EconomicEvent.objects.filter(
        from_agent=agent,
        context_agent=context_agent,
        resource_type=resource_type,
        event_type=event_type,
        is_contribution=True)
    total = sum(event.quantity for event in events)
    try:
        summary = CachedEventSummary.objects.filter(
            agent=agent,
            context_agent=context_agent,
            resource_type=resource_type,
            event_type=event_type)
        if summary.count() > 1:
            sids = [str(s.id) for s in summary]
            sidstring = ",".join(sids)
            return " ".join(["More than one Summary. Ids:", sidstring, "Event total:", str(total)])
        summary = summary[0]
        if summary.quantity != total:
            return " ".join(["summary.quantity:", str(summary.quantity), "event total:", str(total)])
    except CachedEventSummary.DoesNotExist:
        return " ".join(["Summary does not exist. Event total:", str(total)])
    return "ok"

def check_events_for_summary(summary):
    events = EconomicEvent.objects.filter(
        from_agent=summary.agent,
        context_agent=summary.context_agent,
        resource_type=summary.resource_type,
        event_type=summary.event_type,
        is_contribution=True)
    total = sum(event.quantity for event in events)
    if summary.quantity != total:
        return " ".join(["summary.quantity:", str(summary.quantity), "event total:", str(total)])
    return "ok"

def update_summary(agent, context_agent, resource_type, event_type):
    events = EconomicEvent.objects.filter(
        from_agent=agent,
        context_agent=context_agent,
        resource_type=resource_type,
        event_type=event_type,
        is_contribution=True)
    total = sum(event.quantity for event in events)
    summary, created = CachedEventSummary.objects.get_or_create(
        agent=agent,
        context_agent=context_agent,
        resource_type=resource_type,
        event_type=event_type)
    summary.quantity = total
    if summary.quantity:
        summary.save()
    else:
        summary.delete()


#todo: not used
#class Compensation(models.Model):
    """One EconomicEvent compensating another.

    The EconomicAgents in the exchanging events
    must be opposites.
    That is, the from_agent of one event must be
    the to-agent of the other event, and vice versa.
    Both events must use the same unit of value.
    Compensation events have a M:M relationship:
    that is, one event can be compensated by many other events,
    and the other events can compensate many initiating events.

    Compensation is an REA Duality.

    """
#    initiating_event = models.ForeignKey(EconomicEvent,
#        related_name="initiated_compensations", verbose_name=_('initiating event'))
#    compensating_event = models.ForeignKey(EconomicEvent,
#        related_name="compensations", verbose_name=_('compensating event'))
#    compensation_date = models.DateField(_('compensation date'), default=datetime.date.today)
#    compensating_value = models.DecimalField(_('compensating value'), max_digits=8, decimal_places=2)

#    class Meta:
#        ordering = ('compensation_date',)

#    def __str__(self):
#        value_string = '$' + str(self.compensating_value)
#        return ' '.join([
#            'inititating event:',
#            self.initiating_event.__str__(),
#            'compensating event:',
#            self.compensating_event.__str__(),
#            'value:',
#            value_string,
#        ])

#    def clean(self):
#        if self.initiating_event.from_agent.id != self.compensating_event.to_agent.id:
#            raise ValidationError('Initiating event from_agent must be the compensating event to_agent.')
#        if self.initiating_event.to_agent.id != self.compensating_event.from_agent.id:
#            raise ValidationError('Initiating event to_agent must be the compensating event from_agent.')
#        #if self.initiating_event.unit_of_value.id != self.compensating_event.unit_of_value.id:
#        #    raise ValidationError('Initiating event and compensating event must have the same units of value.')


PERCENTAGE_BEHAVIOR_CHOICES = (
    ('remaining', _('Remaining percentage')),
    ('straight', _('Straight percentage')),
)

class ValueEquation(models.Model):
    name = models.CharField(_('name'), max_length=255, blank=True)
    context_agent = models.ForeignKey(EconomicAgent, on_delete=models.CASCADE,
        limit_choices_to={"is_context": True,},
        related_name="value_equations", verbose_name=_('context agent'))
    description = models.TextField(_('description'), null=True, blank=True)
    percentage_behavior = models.CharField(_('percentage behavior'),
        max_length=12, choices=PERCENTAGE_BEHAVIOR_CHOICES, default='straight',
        help_text=_('Remaining percentage uses the %% of the remaining amount to be distributed.  Straight percentage uses the %% of the total distribution amount.'))
    live = models.BooleanField(_('live'), default=False,
        help_text=_("Make this value equation available for use in real distributions."))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='value_equations_created', blank=True, null=True, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('edit_value_equation', {'value_equation_id': str(self.id),})

    def is_deletable(self):
        if self.distributions.all() or self.live:
            return False
        else:
            return True

    def run_value_equation_and_save(self, distribution, money_resource, amount_to_distribute, serialized_filters, events_to_distribute=None):
        distribution_events, contribution_events = self.run_value_equation(
            amount_to_distribute=amount_to_distribute,
            serialized_filters=serialized_filters)
        context_agent = self.context_agent
        testing = False
        if context_agent.name == "test context agent":
            testing = True
        for dist_event in distribution_events:
            va = None
            #todo faircoin distribution
            to_agent = dist_event.to_agent
            if money_resource.is_digital_currency_resource() and 'faircoin' in settings.INSTALLED_APPS:
                #if testing:
                    # TODO faircoin distribution: shd put this into models
                    # faircoins are the only digital currency we handle now
                va = to_agent.faircoin_resource()
                if va:
                    if va.resource_type != money_resource.resource_type:
                        raise ValidationError(" ".join([
                            money_resource.identifier,
                            va.identifier,
                            "digital currencies do not match."]))

                else:
                    if testing:
                        address = to_agent.create_fake_faircoin_address()
                    else:
                        address = to_agent.request_faircoin_address()
                    va = to_agent.faircoin_resource()
                if va:
                    dist_event.resource = va
                    dist_event.resource_type = va.resource_type
                    dist_event.unit_of_quantity = va.resource_type.unit
                else:
                    raise ValidationError(dist_event.to_agent.nick + ' needs faircoin address, unable to create one.')
            else:
                vas = dist_event.to_agent.virtual_accounts()
                if vas:
                    for vacct in vas:
                        if vacct.resource_type.unit == money_resource.resource_type.unit:
                            va = vacct
                            break
                if not va:
                    va = dist_event.to_agent.create_virtual_account(resource_type=money_resource.resource_type)
                if va:
                    dist_event.resource = va
                    dist_event.resource_type = va.resource_type
                    dist_event.unit_of_quantity = va.resource_type.unit
                else:
                    raise ValidationError(dist_event.to_agent.nick + ' needs a virtual account, unable to create one.')
        et = EventType.objects.get(name='Cash Disbursement')
        #distribution.save() #?? used to be exchange; was anything changed?
        buckets = {}
        for bucket in self.buckets.all():
            filter = serialized_filters.get(bucket.id) or "{}"
            filter = simplejson.loads(filter)
            bucket_rules = {}
            for br in bucket.bucket_rules.all():
                filter_rule = simplejson.loads(br.filter_rule)
                br_dict = {
                    "event_type": br.event_type.name,
                    "filter_rule": filter_rule,
                    "claim creation equation": br.claim_creation_equation,
                }
                bucket_rules[br.id] = br_dict
            bucket_dict = {
                "name": bucket.name,
                "filter": filter,
                "bucket_rules": bucket_rules,
            }
            buckets[bucket.id] = bucket_dict
        content = {"buckets": buckets}
        json = simplejson.dumps(content, ensure_ascii=False, indent=4)
        #dist_ve = DistributionValueEquation(
        #    distribution_date = exchange.start_date,
        #   exchange = exchange,
        #    value_equation_link = self,
        #    value_equation_content = json, #todo
        #)
        #dist_ve.save()
        distribution.value_equation_link = self
        distribution.value_equation_content = json
        distribution.save()
        if money_resource.owner():
            fa = money_resource.owner()
        else:
            fa = self.context_agent
        distributed = sum(de.quantity for de in distribution_events)
        disbursement_event = EconomicEvent(
            event_type=et,
            event_date=distribution.distribution_date,
            from_agent=fa,
            to_agent=self.context_agent,
            context_agent=self.context_agent,
            distribution=distribution,
            #quantity=amount_to_distribute,
            quantity=distributed,
            unit_of_quantity=money_resource.resource_type.unit,
            #value=amount_to_distribute,
            value=distributed,
            unit_of_value=money_resource.resource_type.unit,
            is_contribution=False,
            resource_type=money_resource.resource_type,
            resource=money_resource,
        )
        #todo faircoin distribution
        disbursement_event.save()
        if not money_resource.is_digital_currency_resource():
            #money_resource.quantity -= amount_to_distribute
            money_resource.quantity -= distributed
            money_resource.save()
        if events_to_distribute:
            if len(events_to_distribute) == 1:
                cr = events_to_distribute[0]
                crd = IncomeEventDistribution(
                    distribution_date=distribution.distribution_date,
                    income_event=cr,
                    distribution_ref=distribution,
                    #quantity=amount_to_distribute,
                    quantity=distributed,
                    unit_of_quantity=cr.unit_of_quantity,
                )
                crd.save()
            else:
                for cr in events_to_distribute:
                    crd = IncomeEventDistribution(
                        distribution_date=distribution.distribution_date,
                        income_event=cr,
                        distribution_ref=distribution,
                        quantity=cr.quantity,
                        unit_of_quantity=cr.unit_of_quantity,
                    )
                    crd.save()
        #if input_distributions:
        #    for ind in input_distributions:
        #        ied = IncomeEventDistribution(
        #            distribution_date=distribution.distribution_date,
        #            income_event=ind,
        #            distribution=distribution,
        #            quantity=ind.quantity,
        #            unit_of_quantity=ind.unit_of_quantity,
        #        )
        #        ied.save()
        for dist_event in distribution_events:
            dist_event.distribution = distribution
            dist_event.event_date = distribution.distribution_date
            dist_event.save()
            #todo faircoin distribution
            #digital_currency_resources for to_agents were created earlier in this method
            if dist_event.resource.is_digital_currency_resource() and 'faircoin' in settings.INSTALLED_APPS:
                address_origin = self.context_agent.faircoin_address()
                address_end = dist_event.resource.faircoin_address.address
                # what about network_fee?
                #handle when tx is broadcast
                quantity = dist_event.quantity
                state = "new"
                if testing:
                    tx_hash, broadcasted = faircoin_utils.send_fake_faircoins(address_origin, address_end, quantity)
                    state = "pending"
                    if broadcasted:
                        state = "broadcast"
                else:
                    from faircoin.models import FaircoinTransaction
                    dist_event_tx = FaircoinTransaction(
                        event=dist_event,
                        #tx_hash=tx_hash,
                        tx_state=state,
                        to_address=address_end,
                    )
                    dist_event_tx.save()
            to_resource = dist_event.resource
            to_resource.quantity += dist_event.quantity
            to_resource.save()
            for dist_claim_event in dist_event.dist_claim_events:
                claim_from_contribution = dist_claim_event.claim
                if claim_from_contribution.new == True:
                    claim_from_contribution.unit_of_value = dist_event.unit_of_quantity
                    claim_from_contribution.date = distribution.distribution_date
                    claim_from_contribution.save()
                    ce_for_contribution = dist_claim_event.claim.claim_event
                    ce_for_contribution.claim = claim_from_contribution
                    ce_for_contribution.unit_of_value = dist_event.unit_of_quantity
                    ce_for_contribution.claim_event_date = distribution.distribution_date
                    ce_for_contribution.save()
                dist_claim_event.claim = claim_from_contribution
                dist_claim_event.event = dist_event
                dist_claim_event.unit_of_value = dist_event.unit_of_quantity
                dist_claim_event.claim_event_date = distribution.distribution_date
                dist_claim_event.save()

        return distribution

    def run_value_equation(self, amount_to_distribute, serialized_filters):
        #start_time = time.time()
        atd = amount_to_distribute
        detail_sums = []
        claim_events = []
        contribution_events = []
        for bucket in self.buckets.all():
            bucket_amount =  bucket.percentage * amount_to_distribute / 100
            amount = amount_to_distribute - bucket_amount
            if amount < 0:
                bucket_amount = bucket_amount - amount
            amount_distributed = 0
            if bucket_amount > 0:
                if bucket.distribution_agent:
                    sum_a = str(bucket.distribution_agent.id) + "~" + str(bucket_amount)
                    detail_sums.append(sum_a)
                    amount_distributed = bucket_amount
                else:
                    serialized_filter = serialized_filters.get(bucket.id)
                    if serialized_filter:
                        ces, contributions = bucket.run_bucket_value_equation(amount_to_distribute=bucket_amount, context_agent=self.context_agent, serialized_filter=serialized_filter)
                        for ce in ces:
                            detail_sums.append(str(ce.claim.has_agent.id) + "~" + str(ce.value))
                            amount_distributed += ce.value
                        claim_events.extend(ces)
                        contribution_events.extend(contributions)
            if self.percentage_behavior == "remaining":
                amount_to_distribute = amount_to_distribute - amount_distributed
        agent_amounts = {}
        for dtl in detail_sums:
            detail = dtl.split("~")
            if detail[0] in agent_amounts:
                amt = agent_amounts[detail[0]]
                agent_amounts[detail[0]] = amt + Decimal(detail[1])
            else:
                agent_amounts[detail[0]] = Decimal(detail[1])
        et = EventType.objects.get(name='Distribution')
        distribution_events = []
        for agent_id in agent_amounts:
            distribution_event = EconomicEvent(
                event_type = et,
                event_date = datetime.date.today(),
                from_agent = self.context_agent,
                to_agent = EconomicAgent.objects.get(id=int(agent_id)),
                context_agent = self.context_agent,
                quantity = agent_amounts[agent_id].quantize(Decimal('.01'), rounding=ROUND_HALF_UP),
                is_contribution = False,
                is_to_distribute = True,
            )
            agent_claim_events = [ce for ce in claim_events if ce.claim.has_agent.id == int(agent_id)]
            for ce in agent_claim_events:
                ce.event = distribution_event
            distribution_event.dist_claim_events = agent_claim_events
            distribution_events.append(distribution_event)
        #clean up rounding errors
        distributed = sum(de.quantity for de in distribution_events)
        delta = atd - distributed
        if delta:
            if self.percentage_behavior == "remaining":
                if abs(delta) > .05:
                    delta = 0
        if delta and distribution_events:
            max_dist = distribution_events[0]
            for de in distribution_events:
                if de.quantity > max_dist.quantity:
                    max_dist = de
            max_dist.quantity = (max_dist.quantity + delta).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            claim_events = max_dist.dist_claim_events
            for ce in claim_events:
                if ce.value > abs(delta):
                    ce.value += delta
                    claim = ce.claim
                    if claim.value_equation_bucket_rule.claim_rule_type == "debt-like":
                        claim.value += delta
                        if claim.value < 0:
                            claim.value = 0
                    break
        #end_time = time.time()
        #print("run_value_equation elapsed time was %g seconds" % (end_time - start_time))
        return distribution_events, contribution_events


class DistributionManager(models.Manager):

    def distributions(self, start=None, end=None):
        if start and end:
            dists = Distribution.objects.filter(distribution_date__range=[start, end])
        else:
            dists = Distribution.objects.all()
        return dists

class Distribution(models.Model):
    name = models.CharField(_('name'), blank=True, max_length=128)
    process_pattern = models.ForeignKey(ProcessPattern,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('pattern'), related_name='distributions')
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        limit_choices_to={"is_context": True,},
        verbose_name=_('context agent'), related_name='distributions')
    url = models.CharField(_('url'), max_length=255, blank=True, null=True)
    distribution_date = models.DateField(_('distribution date'))
    notes = models.TextField(_('notes'), blank=True)
    value_equation = models.ForeignKey(ValueEquation,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('value equation link'), related_name='distributions')
    value_equation_content = models.TextField(_('value equation formulas used'), null=True, blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='distributions_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='distributions_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)
    slug = models.SlugField(_("Page name"), editable=False)

    objects = DistributionManager()

    class Meta:
        ordering = ('-distribution_date',)
        verbose_name_plural = _("distributions")

    def __str__(self):
        show_name = "Distribution"
        name = ""
        if self.name:
            name = self.name + ","
        return " ".join([
            name,
            show_name,
            "starting",
            self.distribution_date.strftime('%Y-%m-%d'),
            ])

    def deserialize_value_equation_content(self):
        return simplejson.loads(self.value_equation_content)

    def buckets(self):
        dict = self.deserialize_value_equation_content()
        bucket_dict = dict["buckets"]
        buckets = []
        for key, value in list(bucket_dict.items()):
            bucket = ValueEquationBucket.objects.get(id=key)
            bucket.value = value
            buckets.append(bucket)
        return buckets

    def bucket_rules(self):
        buckets = self.buckets()
        answer = []
        for bucket in buckets:
            rules = bucket.value.get("bucket_rules")
            if rules:
                for key, value in list(rules.items()):
                    rule = ValueEquationBucketRule.objects.get(id=key)
                    rule.value = value
                    answer.append(rule)
        return answer

    def orders(self):
        buckets = self.buckets()
        orders = []
        for b in buckets:
            filter = b.value.get("filter")
            if filter:
                method = filter.get("method")
                if method:
                    if method == "Order":
                        oids = filter["orders"]
                        for oid in oids:
                            orders.append(Order.objects.get(id=oid))
        return orders

    def shipments(self):
        buckets = self.buckets()
        shipments = []
        for b in buckets:
            filter = b.value.get("filter")
            if filter:
                method = filter.get("method")
                if method:
                    if method == "Shipment":
                        ship_ids = filter["shipments"]
                        for sid in ship_ids:
                            shipments.append(EconomicEvent.objects.get(id=sid))
        return shipments

    def distribution_events(self):
        return self.events.filter(
            event_type__relationship='distribute')

    def disbursement_events(self):
        return self.events.filter(
            event_type__relationship='disburse')

    def distribution_total(self):
        dists = self.distribution_events()
        total = 0
        for dist in dists:
            total += dist.quantity
        return total

    def disbursement_total(self):
        disbs = self.disbursement_events()
        total = 0
        for disb in disbs:
            total += disb.quantity
        return total

    def flow_type(self):
        return "Distribution"

    def flow_class(self):
        return "distribution"

    def flow_description(self):
        return self.__str__()


class EconomicEventManager(models.Manager):

    def virtual_account_events(self, start_date=None, end_date=None):
        if start_date and end_date:
            events = EconomicEvent.objects.filter(resource__resource_type__behavior="account", event_date__gte=start_date, event_date__lte=end_date)
        elif start_date:
            events = EconomicEvent.objects.filter(resource__resource_type__behavior="account", event_date__gte=start_date)
        elif end_date:
            events = EconomicEvent.objects.filter(resource__resource_type__behavior="account", event_date__lte=end_date)
        else:
            events = EconomicEvent.objects.filter(resource__resource_type__behavior="account")
        return events

    def contributions(self):
        return EconomicEvent.objects.filter(is_contribution=True)

    def all_give(self, agent=None):
        #print("event all_give")
        et_give = EventType.objects.get(name="Give")
        bkp = self.all()
        filtered = self.filter(event_type=et_give)
        if not filtered and bkp:
            #print("x bkp: "+str(bkp))
            internal = bkp.filter(exchange__isnull=False, exchange__exchange_type__use_case__identifier='intrnl_xfer')
            if not internal and bkp:
                internal = bkp.filter(transfer__exchange__isnull=False, transfer__exchange__exchange_type__use_case__identifier='intrnl_xfer')
                #print("x filter using ev tx ex. internal:"+str(len(internal)))
            if internal:
                print("WARN not found 'give' event_type (internal) filtered from "+str(self)+", return all! "+str(bkp))
                loger.info("WARN not found 'give' event_type (internal) filtered from "+str(self)+", return all! "+str(bkp))
            return bkp
        if agent:
            givin = bkp.filter(to_agent=agent)
            if not givin:
                filtered = bkp.filter(event_type__name="Receive")
        return filtered

    def related_agent(self, agent=None):
        evs = []
        if agent:
            tos = self.filter(to_agent=agent)
            if tos:
                evs.append(tos)
            fms = self.filter(from_agent=agent)
            if fms:
                evs.append(fms)
            cns = self.filter(context_agent=agent)
            if cns:
                evs.append(cns)
        return evs



"""TX_STATE_CHOICES = (
    ('new', _('New')),
    ('pending', _('Pending')),
    ('broadcast', _('Broadcast')),
    ('confirmed', _('Confirmed')),
    ('external', _('External')),
    ('error', _('Error')),
)"""

class EconomicEvent(models.Model):
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        related_name="events", verbose_name=_('event type'))
    event_date = models.DateField(_('event date'))
    from_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="given_events", verbose_name=_('from'))
    to_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="taken_events", verbose_name=_('to'))
    resource_type = models.ForeignKey(EconomicResourceType, on_delete=models.CASCADE,
        verbose_name=_('resource type'), related_name='events')
    resource = models.ForeignKey(EconomicResource,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('resource'), related_name='events')
    exchange_stage = models.ForeignKey(ExchangeType, related_name="events_creating_exchange_stage",
        verbose_name=_('exchange stage'), blank=True, null=True, on_delete=models.SET_NULL)
    process = models.ForeignKey(Process,
        blank=True, null=True,
        verbose_name=_('process'), related_name='events',
        on_delete=models.SET_NULL)
    exchange = models.ForeignKey(Exchange,
        blank=True, null=True,
        verbose_name=_('exchange'), related_name='events',
        on_delete=models.SET_NULL)
    transfer = models.ForeignKey(Transfer,
        blank=True, null=True,
        related_name="events", verbose_name=_('transfer'),
        on_delete=models.SET_NULL)
    distribution = models.ForeignKey(Distribution,
        blank=True, null=True,
        related_name="events", verbose_name=_('distribution'),
        on_delete=models.SET_NULL)
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True,
        limit_choices_to={"is_context": True,},
        related_name="events", verbose_name=_('context agent'),
        on_delete=models.SET_NULL)
    url = models.CharField(_('url'), max_length=255, blank=True)
    description = models.TextField(_('description'), null=True, blank=True)
    quantity = models.DecimalField(_('quantity'), max_digits=20, decimal_places=9)
    unit_of_quantity = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="event_qty_units")
    quality = models.DecimalField(_('quality'), max_digits=3, decimal_places=0, default=Decimal("0"))
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of value'), related_name="event_value_units")
    price = models.DecimalField(_('price'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_price = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of price'), related_name="event_price_units")
    commitment = models.ForeignKey(Commitment, blank=True, null=True,
        verbose_name=_('fulfills commitment'), related_name="fulfillment_events",
        on_delete=models.SET_NULL)
    is_contribution = models.BooleanField(_('is contribution'), default=False)
    is_to_distribute = models.BooleanField(_('is to distribute'), default=False)
    accounting_reference = models.ForeignKey(AccountingReference, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('accounting reference'), related_name="events",
        help_text=_('optional reference to an accounting grouping'))
    event_reference = models.CharField(_('reference'), max_length=128, blank=True, null=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='events_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='events_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)

    slug = models.SlugField(_("Page name"), editable=False)

    objects = EconomicEventManager()

    class Meta:
        ordering = ('-event_date', '-pk')

    def __str__(self):
        if self.unit_of_quantity:
            quantity_string = " ".join([str(remove_exponent(self.quantity)), self.unit_of_quantity.abbrev])
        else:
            quantity_string = str(remove_exponent(self.quantity))
        from_agt = 'Unassigned'
        if self.from_agent:
            from_agt = self.from_agent.name
        to_agt = 'Unassigned'
        if self.recipient():
            to_agt = self.recipient().name
        resource_string = self.resource_type.name
        if self.resource:
            if self.resource.resource_type.is_account():
                resource_string = ''
                if self.unit_of_quantity:
                    quantity_string = " ".join([str(remove_exponent(self.quantity)), self.unit_of_quantity.name])
                if self.quantity > 1:
                    quantity_string += 's'
            else:
                resource_string = self.resource.__str__()
        if self.unit_of_quantity and self.unit_of_quantity.is_currency():
            resource_string = ''
            quantity_string = " ".join([str(remove_exponent(self.quantity)), self.unit_of_quantity.name])

        event_name = self.event_type.name
        #if self.exchange_type_item_type:
        #    event_name = self.exchange_type_item_type.name
        return ' '.join([
            event_name,
            self.event_date.strftime('%Y-%m-%d'),
            'from',
            from_agt,
            'to',
            to_agt,
            quantity_string,
            resource_string,
        ])

    def mirror_event(self):
        mirr = None
        if not hasattr(self, 'mirror'):
            mir = EconomicEvent.objects.filter(
                from_agent=self.from_agent,
                to_agent=self.to_agent,
                resource_type=self.resource_type,
                resource=self.resource,
                event_date=self.event_date,
                unit_of_quantity=self.unit_of_quantity,
                unit_of_value=self.unit_of_value)
            for mi in mir:
                if not mi == self:
                    self.mirror = mi
                    mirr = mi
            return mirr
        else:
            return self.mirror

    def show_name(self, agent=None, forced=False):
        name = self.__str__()
        newname = name
        if agent:
            gives = self.from_agent == agent
            takes = self.to_agent == agent
            mirr = self.mirror_event()
            if takes and mirr:
                name = mirr.__str__()
                newname = name
            if not hasattr(self, 'exchange') or not self.exchange:
                if not hasattr(self.transfer, 'exchange') or not self.transfer.exchange:
                    loger.info("error showing name: not self.exchange? ev:"+str(self.id))
                    return "error showing name: not self.exchange?"
                else:
                    loger.warning("The Event has no exchange but its transfer has it, FIXING!")
                    self.exchange = self.transfer.exchange
                    self.save()
            if hasattr(self.exchange.exchange_type, 'ocp_record_type') and self.exchange.exchange_type.ocp_record_type:
              x_actions = self.exchange.exchange_type.ocp_record_type.x_actions()
              for action in x_actions:
                opposite = action.opposite()
                if opposite:
                    if action.clas and opposite.clas:
                        newname = name.replace(str(action.clas), '<em>'+opposite.clas+'</em>')
                    if name == newname:
                        newname = name.replace(action.name, '<em>'+opposite.name+'</em>')
                    if gives or forced:
                        if action.clas == 'buy' or action.clas == 'receive':
                            name = newname
                    if takes or forced:
                        if action.clas == 'sell' or action.clas == 'give':
                            name = newname
                    if not takes and not gives:
                        if not self.from_agent and not self.to_agent:
                            print("The event has no 'to' nor 'from' agents ?? ev:"+str(self.id)+" "+str(self))
                            loger.warning("The event has no 'to' nor 'from' agents ?? ev:"+str(self.id)+" "+str(self))
                        elif self.to_agent == agent.parent() and self.faircoin_transaction: # only used when a fairaccount is inherited from parent
                            if action.clas == 'sell' or action.clas == 'give':
                                name = newname
                        elif self.from_agent == agent.parent() and self.faircoin_transaction:
                            if action.clas == 'buy' or action.clas == 'receive':
                                name = newname
                        else:
                            print("no gives nor takes? "+str(self.id)+" ag:"+str(agent)+" to:"+str(self.to_agent)+" from:"+str(self.from_agent))


            else:
                if self.from_agent and self.to_agent:
                    name = '?'+name
                print("The ev:"+str(self.id)+" exchange.exchange_type has not ocp_record_type ? ag:"+str(agent)+" gives:"+str(gives)+" takes:"+str(takes)+" ex:"+str(self.exchange.id)+" et:"+str(self.exchange.exchange_type.id)+" "+str(self.exchange.exchange_type))
        return name



    @property #ValueFlows
    def action(self):
        return self.event_type.action

    @property #ValueFlows
    def numeric_value(self):
        return self.quantity

    @property #ValueFlows
    def unit(self):
        return self.unit_of_quantity

    @property #ValueFlows
    def start(self):
        return self.event_date.isoformat()

    #@property #ValueFlows
    #def numeric_duration(self):
    #    if self.event_type.name == "Resource use" or self.event_type.name == "Time Contribution":
    #        return self.quantity
    #    else:
    #        return None

    #@property #ValueFlows
    #def temporal_unit(self):
    #    if self.event_type.name == "Resource use" or self.event_type.name == "Time Contribution":
    #        return self.unit_of_quantity
    #    else:
    #        return None

    @property #ValueFlows
    def note(self):
        return self.description

    @property #ValueFlows
    def provider(self):
        return self.from_agent

    @property #ValueFlows
    def receiver(self):
        return self.to_agent

    @property #ValueFlows
    def scope(self):
        return self.context_agent

    @property #ValueFlows
    def affects(self):
        return self.resource

    @property #ValueFlows
    def affected_resource_classified_as(self):
        return self.resource_type

    #@property #ValueFlows TODO not in VF now
    #def work_category(self):
    #    if self.resource_type.behavior == "work":
    #        return self.resource_type
    #    return None

    @property #ValueFlows
    def input_of(self):
        if not self.event_type.relationship == "out":
            return self.process
        return None

    @property #ValueFlows
    def output_of(self):
        if self.event_type.relationship == "out":
            return self.process
        return None

    def undistributed_description(self):
        if self.unit_of_quantity:
            quantity_string = " ".join([str(self.undistributed_amount()), self.unit_of_quantity.abbrev])
        else:
            quantity_string = str(self.undistributed_amount())
        from_agt = 'Unassigned'
        if self.from_agent:
            from_agt = self.from_agent.name
        to_agt = 'Unassigned'
        if self.recipient():
            to_agt = self.recipient().name
        resource_string = self.resource_type.name
        if self.resource:
            resource_string = self.resource.__str__()
        return ' '.join([
            self.event_type.name,
            self.event_date.strftime('%Y-%m-%d'),
            'from',
            from_agt,
            'to',
            to_agt,
            quantity_string,
            resource_string,
        ])

    def save(self, *args, **kwargs):
        from_agt = 'Unassigned'
        agent = self.from_agent
        context_agent = self.context_agent
        resource_type = self.resource_type
        event_type = self.event_type
        delta = self.quantity

        agent_change = False
        project_change = False
        resource_type_change = False
        context_agent_change = False
        event_type_change = False

        if self.pk:
            prev_agent = self.from_agent
            prev_context_agent = self.context_agent
            prev_resource_type = self.resource_type
            prev_event_type = self.event_type
            prev = EconomicEvent.objects.get(pk=self.pk)
            if prev.quantity != self.quantity:
                delta = self.quantity - prev.quantity
            if prev.from_agent != self.from_agent:
                agent_change = True
                prev_agent = prev.from_agent
            if prev.context_agent != self.context_agent:
                context_agent_change = True
                prev_context_agent = prev.context_agent
            if prev.resource_type != self.resource_type:
                resource_type_change = True
                prev_resource_type = prev.resource_type
            if prev.event_type != self.event_type:
                event_type_change = True
                prev_event_type = prev.event_type
        if agent:
            from_agt = agent.name
            if delta:
                #todo ART: bugs in this code cause dup records
                if self.event_type.relationship == "work" or self.event_type.related_to == "agent":
                    try:
                        art, created = AgentResourceType.objects.get_or_create(
                            agent=agent,
                            resource_type=resource_type,
                            event_type=event_type)
                    except:
                        #todo: this shd not happen, but it does...
                        arts = AgentResourceType.objects.filter(
                            agent=agent,
                            resource_type=resource_type,
                            event_type=event_type)
                        art = arts[0]
                    art.score += delta
                    art.save()

        slug = "-".join([
            str(self.event_type.name),
            from_agt,
            self.event_date.strftime('%Y-%m-%d'),
        ])
        unique_slugify(self, slug)
        super(EconomicEvent, self).save(*args, **kwargs)
        update_summary(agent, context_agent, resource_type, event_type)
        if agent_change or resource_type_change or context_agent_change or event_type_change:
            update_summary(prev_agent, prev_context_agent, prev_resource_type, prev_event_type)

        #for handling faircoin
        #if self.resource:
        #    if self.resource.resource_type.is_virtual_account():
                #call the faircoin method here, pass the event info needed

    def save_api(self, user, old_quantity=None, old_resource=None, create_resource=False): #additional logic from views
        if create_resource:
            self.resource.save_api(process=self.process, event_type=self.event_type, commitment=self.commitment)
            self.resource = self.resource
        self.save()
        process = self.process
        if process:
            process.set_started(self.event_date, user)
        if self.resource and not create_resource:
            self.update_resource(old_quantity=old_quantity, old_resource=old_resource)

    def delete(self, *args, **kwargs):
        if self.is_contribution:
            agent = self.from_agent
            context_agent = self.context_agent
            resource_type = self.resource_type
            event_type = self.event_type
            if agent and context_agent and resource_type:
                try:
                    summary = CachedEventSummary.objects.get(
                        agent=agent,
                        context_agent=context_agent,
                        resource_type=resource_type,
                        event_type=event_type)
                    summary.quantity -= self.quantity
                    if summary.quantity:
                        summary.save()
                    else:
                        summary.delete()
                except CachedEventSummary.DoesNotExist:
                    pass
        super(EconomicEvent, self).delete(*args, **kwargs)

    def delete_api(self): #additional logic from views
        self.delete()
        self.delete_resource_effects()

    def update_resource(self, old_quantity=None, old_resource=None):
        # This should work for new or changed events (changed quantity only),
        # but not for deletes.
        # It also *only works for adding to existing resources*.
        # If the resource has not been created yet,
        # and assigned to the event,
        # this method will not create it.
        # delta is for event changes, quantity only.

        #import pdb; pdb.set_trace()
        #has_new_resource = False
        #if old_quantity:
        #    delta = self.quantity - old_quantity
        #else:
        #    delta = 0
        #if old_resource:
        #    if self.resource == old_resource:
        #        old_resource = None
        #    else:
        #        has_new_resource = True

        resource = self.resource
        if resource:
            #quantity = delta or self.quantity
            if self.consumes_resources():
                if old_resource:
                    if resource != old_resource:
                        old_resource.quantity = old_resource.quantity + old_quantity
                        old_resource.save()
                        resource.quantity = resource.quantity - self.quantity
                    else:
                        changed_qty = self.quantity - old_quantity
                        if changed_qty != 0:
                            resource.quantity = resource.quantity - changed_qty
                else:
                    resource.quantity = resource.quantity - self.quantity
                resource.save()
                #resource.quantity -= quantity
                #resource.save()
            if self.creates_resources():
                if old_resource:
                    if resource != old_resource:
                        old_resource.quantity = old_resource.quantity - old_quantity
                        old_resource.save()
                        resource.quantity = resource.quantity + self.quantity
                    else:
                        changed_qty = self.quantity - old_quantity
                        if changed_qty != 0:
                            resource.quantity = resource.quantity + changed_qty
                else:
                    resource.quantity = resource.quantity + self.quantity
                resource.save()
                #resource.quantity += quantity
                #resource.save()
        else:
            if old_resource:
                if self.consumes_resources():
                    old_resource.quantity = old_resource.quantity + old_qty
                    old_resource.save()
                if self.creates_resources():
                    old_resource.quantity = old_resource.quantity - old_qty
                    old_resource.save()

    def delete_resource_effects(self):
        # This might work for deleted events
        #import pdb; pdb.set_trace()
        resource = self.resource
        if resource:
            quantity = self.quantity
            if self.consumes_resources():
                resource.quantity += quantity
                resource.save()
            if self.creates_resources():
                resource.quantity -= quantity
                resource.save()
            if self.changes_stage():
                process = self.process
                if process:
                    #this needs a lot of testing
                    tbcs = process.to_be_changed_requirements.filter(
                        resource_type=resource.resource_type)
                    if tbcs:
                        tbc = tbcs[0]
                        tbc_evts = tbc.fulfilling_events.filter(
                            resource=resource)
                        if tbc_evts:
                            tbc_evt = tbc_evts[0]
                            resource.quantity = tbc_evt.quantity
                            tbc_evt.delete()
                        resource.stage = tbc.stage
                        resource.save()
                    else:
                        resource.revert_to_previous_stage()

    def is_double_validated(self):
        from validation import models
        count = self.validations.count()
        if count > 1:
            return True
        else:
            return False

    def due_date(self):
        if self.commitment:
            return self.commitment.due_date
        else:
            return self.event_date


    def previous_events(self):
        """ Experimental method:
        Trying to use properties of events to determine event sequence.
        Can't count on dates or event ids.
        This is currently for the DHen resource_flow_report
        and takes advantage of DHen data shape.
        For example, Consumption events will have no successors.
        Receives will have no prevs except a Give event
        in the same Transfer.
        Will most likely not work (yet) more generally.
        """
        prevs = []
        #todo exchange redesign fallout
        give = EventType.objects.get(name="Give")
        ret = EventType.objects.get(name="Receive")
        cet = EventType.objects.get(name="Resource Consumption")
        if self.event_type == ret:
            if self.transfer:
                give_evt = self.transfer.give_event()
                if give_evt:
                    prevs.append(give_evt)
                return prevs
        resource = self.resource
        if resource:
            candidates = resource.events.all()
            prevs = candidates.filter(to_agent=self.from_agent).exclude(event_type=give)
            prevs = prevs.exclude(event_type=cet)
            if self.event_type == give:
                if self.transfer:
                    prevs = prevs.exclude(transfer=self.transfer)
        return prevs

    def next_events(self):
        nexts = []
        resource = self.resource
        if resource:
            candidates = resource.events.all()
            nexts = candidates.filter(from_agent=self.to_agent).exclude(id=self.id)
        return nexts

    def transaction_state(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        state = self.faircoin_transaction.tx_state
        new_state = None
        if state == "external" or state == "pending" or state == "broadcast":
            tx = self.faircoin_transaction.tx_hash
            if tx:
                confirmations, timestamp = faircoin_utils.get_confirmations(tx)
                if confirmations:
                    if confirmations > 0:
                        if state != "broadcast":
                            new_state = "broadcast"
                    if confirmations > 2:
                        new_state = "confirmed"
        if new_state:
            state = new_state
            fairtx = self.faircoin_transaction
            fairtx.tx_state = new_state
            fairtx.save()
        return state

    def to_faircoin_address(self):
        if 'faircoin' not in settings.INSTALLED_APPS:
            return None
        if self.resource.is_digital_currency_resource():
            event_reference = self.event_reference
            if event_reference:
                answer = event_reference
                to_resources = EconomicResource.objects.filter(faircoin_address__address=event_reference)
                if to_resources:
                    answer = to_resources[0].identifier
        return answer

    def seniority(self):
        return (datetime.date.today() - self.event_date).days

    def value_per_unit(self):
        if self.resource:
            return self.resource.value_per_unit
        if self.from_agent:
            arts = AgentResourceType.objects.filter(
                agent=self.from_agent,
                resource_type=self.resource_type,
                event_type=self.event_type)
            if arts:
                art = arts[0]
                if art.value_per_unit:
                    return art.value_per_unit
        return self.resource_type.value_per_unit

    #obsolete
    def value_explanation(self):
        if self.process:
            p_qty = self.process.production_quantity()
        if self.event_type.relationship == "work":
            vpu = self.resource_type.value_per_unit
            value = vpu * self.quantity
            if p_qty:
                value = value / p_qty
                return " ".join([
                    "Value per parent unit:", str(value),
                    "= Resource Type value per unit:", str(vpu),
                    "* Event quantity:", str(self.quantity),
                    "/ Process production qty:", str(p_qty),
                    ])
            else:
                return " ".join([
                    "Value:", str(value),
                    "= Resource Type value per unit:", str(vpu),
                    "* Event quantity:", str(self.quantity)
                    ])
        elif self.event_type.relationship == "use":
            #todo: needs price changes
            vpu = self.resource.value_per_unit_of_use
            value = vpu * self.quantity
            if p_qty:
                value = value / p_qty
                return " ".join([
                    "Value per parent unit:", str(value),
                    "= Resource value per unit of use:", str(vpu),
                    "* Event quantity:", str(self.quantity),
                    "/ Process production qty:", str(p_qty),
                    ])
            else:
                return " ".join([
                    "Value:", str(value),
                    "= Resource value per unit of use:", str(vpu),
                    "* Event quantity:", str(self.quantity)
                    ])
        elif self.event_type.relationship == "consume":
            vpu = self.resource.value_per_unit
            value = vpu * self.quantity
            if p_qty:
                value = value / p_qty
                return " ".join([
                    "Value per parent unit:", str(value),
                    "= Resource value per unit:", str(vpu),
                    "* Event quantity:", str(self.quantity),
                    "/ Process production qty:", str(p_qty),
                    ])
            else:
                return " ".join([
                    "Value:", str(value),
                    "= Resource value per unit:", str(vpu),
                    "* Event quantity:", str(self.quantity)
                    ])
        elif self.event_type.relationship == "cite":
            percent = False
            if self.resource_type.unit_of_use:
                if self.resource_type.unit_of_use.unit_type == "percent":
                    percent = True
            if percent:
                return "".join([
                    "Value per parent unit: ", str(self.value),
                    " = ", str(self.quantity),
                    "% of sum of the values of the other inputs to the process",
                    ])
            else:
                return " ".join([
                    "Value:", str(self.value),
                    "= Event quantity:", str(self.quantity),
                    ])
        elif self.event_type.relationship == "resource":
            vpu = self.resource.value_per_unit
            value = vpu * self.quantity
            return " ".join([
                "Value:", str(value),
                "= Resource value per unit:", str(vpu),
                "* Event quantity:", str(self.quantity)
                ])
        elif self.event_type.relationship == "receive":
            vpu = self.resource.value_per_unit
            value = vpu * self.quantity
            return " ".join([
                "Value:", str(value),
                "= Resource value per unit:", str(vpu),
                "* Event quantity:", str(self.quantity)
                ])
        elif self.event_type.relationship == "out":
            return "Value per unit is composed of the value of the inputs on the next level:"
        return ""

    def incoming_value_flows_dfs(self, flows, visited, depth):
        # EconomicEvent method
        #todo dhen_bug:
        if self.event_type.relationship=="receive":
            if self.transfer:
                exchange = self.transfer.exchange
                if exchange:
                    if exchange not in visited:
                        visited.add(exchange)
                        exchange.depth = depth + 1
                        flows.append(exchange)
                        for pmt in exchange.reciprocal_transfer_events():
                            pmt.depth = depth + 2
                            flows.append(pmt)
        if self.resource:
            depth = depth + 1
            #the exclude clause tries to head off infinite loops
            prevs = self.resource.events.filter(to_agent=self.from_agent).exclude(from_agent=self.from_agent)
            for prev in prevs:
                if prev not in visited:
                    visited.add(prev)
                    prev.depth = depth
                    flows.append(prev)
                    prev.incoming_value_flows_dfs(flows, visited, depth)

    def roll_up_value(self, path, depth, visited, value_equation):
        # EconomicEvent method
        #rollup stage change
        stage = None
        #what is no commitment? Can that happen with staged events?
        if self.commitment:
            stage = self.commitment.stage
        if stage:
            self.resource.historical_stage = stage
        #todo 3d:
        return self.resource.roll_up_value(path, depth, visited, value_equation)

    def compute_income_shares(self, value_equation, d_qty, events, visited):
        # EconomicEvent method
        #income_shares stage change
        stage = None
        #what is no commitment? Can that happen with staged events?
        if self.commitment:
            stage = self.commitment.stage
        if stage:
            self.resource.historical_stage = stage
        #todo 3d:
        return self.resource.compute_income_shares(value_equation, d_qty, events, visited)

    def bucket_rule(self, value_equation):
        brs = ValueEquationBucketRule.objects.filter(
            value_equation_bucket__value_equation=value_equation,
            event_type=self.event_type)
        candidates = []
        for br in brs:
            if br.claim_creation_equation:
                filter = br.filter_rule_deserialized()
                if filter:
                    rts = filter.get('resource_types')
                    if rts:
                        if self.resource_type in rts:
                            br.filter = filter
                            candidates.append(br)
                    pts = filter.get('process_types')
                    if pts:
                        if self.process:
                            if self.process.process_type:
                                if self.process.process_type in pts:
                                    br.filter = filter
                                    candidates.append(br)
                else:
                    br.filter = filter
                    candidates.append(br)
        if not candidates:
            return None
        candidates = list(set(candidates))
        if len(candidates) == 1:
            return candidates[0]
        filtered = [c for c in candidates if c.filter]
        if not filtered:
            return candidates[0]
        best_fit = []
        if filtered:
            if len(filtered) == 1:
                return filtered[0]
            for f in filtered:
                pts = f.filter.get("process_types")
                rts = filter.get('resource_types')
                if pts and rts:
                    f.score = 2
                    best_fit.append(f)
                elif pts:
                    f.score = 1.5
                    better = [b for b in best_fit if b.score > 1.5]
                    if not better:
                        best_fit.append(f)
                elif rts:
                    if not best_fit:
                        f.score = 1
                        best_fit.append(f)
        if best_fit:
            #todo: necessary? I doubt it...
            #best_fit = list(set(best_fit))
            #todo: this (below) must be mediated by which VE
            #if len(best_fit) > 1:
            if len(best_fit) == 1:
                return best_fit[0]
            return best_fit[0]
        return None

    def bucket_rule_for_context_agent(self):
        bucket_rule = None
        if self.context_agent:
            ves = self.context_agent.live_value_equations()
            for ve in ves:
                bucket_rule = self.bucket_rule(ve)
                if bucket_rule:
                    break
        return bucket_rule

    def claims(self):
        claim_events = self.claim_events.all()
        claims = [ce.claim for ce in claim_events]
        return list(set(claims))

    def outstanding_claims(self):
        claim_events = self.claim_events.all()
        claims = [ce.claim for ce in claim_events if ce.claim.value > Decimal("0.0")]
        return list(set(claims))

    def created_claim(self):
        cc = None
        claim_events = self.claim_events.all()
        for ce in claim_events:
            if ce.event_effect == "+":
                cc = ce.claim
                cc.claim_event = ce
                break
        return cc

    def outstanding_claims_for_bucket_rule(self, bucket_rule):
        claims = self.outstanding_claims()
        return [claim for claim in claims if claim.value_equation_bucket_rule==bucket_rule]

    def create_claim(self, bucket_rule):
        #claims = self.outstanding_claims_for_bucket_rule(bucket_rule)
        #if claims:
        if self.created_claim():
            return self.created_claim()
        else:
            order = None
            if self.commitment:
                order = self.commitment.independent_demand
            else:
                if self.process:
                    order = self.process.independent_demand()
            claim_value = bucket_rule.compute_claim_value(self)
            claim = Claim(
                order=order,
                value_equation_bucket_rule=bucket_rule,
                claim_date=datetime.date.today(),
                has_agent=self.from_agent,
                against_agent=self.to_agent,
                context_agent=self.context_agent,
                unit_of_value=self.unit_of_value,
                value=claim_value,
                original_value=claim_value,
                claim_creation_equation=bucket_rule.claim_creation_equation,
            )
            claim.save()
            claim_event = ClaimEvent(
                event=self,
                claim=claim,
                claim_event_date=datetime.date.today(),
                value=claim_value,
                unit_of_value=self.unit_of_value,
                event_effect="+",
            )
            claim_event.save()
            #claim_event.update_claim()
            return claim

    def get_unsaved_contribution_claim(self, bucket_rule):
        claim = self.created_claim()
        if claim:
            claim.new = False
            return claim
        else:
            value = bucket_rule.compute_claim_value(self)
            against_agent = self.to_agent
            if self.event_type.name == "Payment":
                against_agent = self.context_agent
            claim = Claim(
                value_equation_bucket_rule=bucket_rule,
                claim_date=datetime.date.today(),
                has_agent=self.from_agent,
                against_agent=against_agent,
                context_agent=self.context_agent,
                value=value,
                unit_of_value=self.unit_of_value,
                original_value=value,
                claim_creation_equation=bucket_rule.claim_creation_equation,
            )
            claim_event = ClaimEvent(
                event=self,
                claim=claim,
                claim_event_date=datetime.date.today(),
                value=value,
                unit_of_value=self.unit_of_value,
                event_effect="+",
            )
            claim.claim_event = claim_event
            claim.new = True
            return claim

    def get_unsaved_context_agent_claim(self, against_agent, bucket_rule):
        #changed for contextAgentDistributions
        #todo: how to find created_context_agent_claims?
        #claim = self.created_claim()
        #if claim:
        #    claim.new = False
        #    return claim

        value = bucket_rule.compute_claim_value(self)
        claim = Claim(
            #order=order,
            value_equation_bucket_rule=bucket_rule,
            claim_date=datetime.date.today(),
            has_agent=self.context_agent,
            against_agent=against_agent,
            context_agent=self.context_agent,
            value=value,
            unit_of_value=self.unit_of_value,
            original_value=value,
            claim_creation_equation=bucket_rule.claim_creation_equation,
        )
        claim_event = ClaimEvent(
            event=self,
            claim=claim,
            claim_event_date=datetime.date.today(),
            value=value,
            unit_of_value=self.unit_of_value,
            event_effect="+",
        )
        claim.claim_event = claim_event
        claim.new = True
        return claim

    def undistributed_amount(self):
        #todo: partial
        #et_cr = EventType.objects.get(name="Cash Receipt")
        #et_id = EventType.objects.get(name="Distribution")
        if self.is_to_distribute:
            crd_amounts = sum(d.quantity for d in self.distributions.all())
            return self.quantity - crd_amounts
        else:
            return Decimal("0.0")

    def is_undistributed(self):
        #todo: partial
        #et_cr = EventType.objects.get(name="Cash Receipt")
        #et_id = EventType.objects.get(name="Distribution")
        #if self.event_type == et_cr or self.event_type == et_id:
        #    crds = self.distributions.all()
        #    if crds:
        #        return False
        #    else:
        #        return True
        #else:
        #    return False
        if self.undistributed_amount():
            return True
        else:
            return False

    def shorter_label(self):
        if self.unit_of_quantity:
            quantity_string = " ".join([str(self.quantity), self.unit_of_quantity.abbrev])
        else:
            quantity_string = str(self.quantity)
        agt_string = ""
        if self.from_agent != self.to_agent:
            from_agt = 'Unassigned'
            if self.from_agent:
                from_agt = self.from_agent.nick
            to_agt = 'Unassigned'
            if self.recipient():
                to_agt = self.recipient().nick
            agt_string = ' to '.join([from_agt, to_agt])
        rname = self.resource_type.name
        if self.resource:
            rname = self.resource.resource_type.name
        return ' '.join([
            agt_string,
            rname,
            quantity_string,
        ])

    def default_agent(self):
        if self.context_agent:
            return self.context_agent.default_agent()
        return None

    def cycle_id(self):
        stage_id = ""
        state_id = ""
        if self.resource:
            if self.resource.stage:
                stage_id = str(self.resource.stage.id)
            if self.resource.state:
                state_id = str(self.resource.state.id)
        return "-".join([str(self.resource_type.id), stage_id, state_id])

    def class_label(self):
        return "Economic Event"

    def recipient(self):
        return self.to_agent or self.default_agent()

    def flow_type(self):
        if self. transfer:
            return self.transfer.transfer_type.name
        else:
            return self.event_type.name
        """
        answer = self.event_type.name
        if answer=="Receive":
            if self.transfer:
                if self.transfer.is_reciprocal():
                    answer = self.transfer.transfer_type.name
        return answer
        """

    def flow_class(self):
        return self.event_type.relationship

    def flow_description(self):
        quantity_string = ""
        if self.event_type.relationship != "cite":
            if self.unit_of_quantity:
                quantity_string = " ".join([str(self.quantity), self.unit_of_quantity.abbrev])
            else:
                quantity_string = str(self.quantity)
        from_agt = ''
        if self.from_agent:
            from_agt = ' '.join(["from", self.from_agent.name])
        to_agt = ''
        if self.to_agent:
            to_agt = ' '.join(["to", self.to_agent.name])
        resource_string = self.resource_type.name
        if self.resource:
            #rollup stage change
            id_str = self.resource.identifier or str(self.resource.id)
            if self.commitment:
                stage = self.commitment.stage
                if stage:
                    resource_string = "@".join([resource_string, stage.name])
            resource_string = ": ".join([
                    resource_string,
                    id_str,
                ])
        return ' '.join([
            self.event_date.strftime('%Y-%m-%d'),
            from_agt,
            to_agt,
            quantity_string,
            resource_string,
        ])

    #compensation methods obsolete
    #def my_compensations(self):
    #    return self.initiated_compensations.all()

    #def compensation(self):
    #    return sum(c.compensating_value for c in self.my_compensations())

    #def value_due(self):
    #    return self.value - self.compensation()

    #def is_compensated(self):
    #    if self.value_due() > 0:
    #        return False
    #    return True

    def claimed_amount(self): #for contribution events
        if self.is_contribution:
            if self.created_claim():
                return self.created_claim().original_value
            else:
                return None
        else:
            return None

    def owed_amount(self): #for contribution events
        if self.is_contribution:
            if self.claimed_amount():
                return self.created_claim().value
            else:
                return None
        else:
            return None

    def distributed_amount(self): #for contribution events
        if self.is_contribution:
            if self.created_claim():
                return self.created_claim().original_value - self.created_claim().value
        else:
            return Decimal("0.0")

    def unit(self):
        if self.unit_of_quantity:
            return self.unit_of_quantity.symbol if self.unit_of_quantity.symbol else self.unit_of_quantity.abbrev
        elif self.resource_type.unit:
            return self.resource_type.unit.symbol if self.resource_type.unit.symbol else self.resource_type.unit.abbrev
        else:
            return "unit?"

    def own_or_resource_type_unit(self):
        if self.unit_of_quantity:
            return self.unit_of_quantity
        else:
            return self.resource_type.unit

    def quantity_formatted(self):
        return " ".join([
            str(self.quantity.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
            self.unit(),
            ])

    def distribution_quantity_formatted(self):
        unit = self.own_or_resource_type_unit()
        qty_string = str(self.quantity.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        if unit.symbol:
            return "".join([
                unit.symbol,
                qty_string,
                ])
        else:
            return " ".join([
                qty_string,
                unit,
                ])

    def value_formatted_decimal(self):
        val = self.value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if self.unit_of_value:
            if self.unit_of_value.symbol:
                value_string = "".join([self.unit_of_value.symbol, str(val)])
            else:
                value_string = " ".join([str(val), self.unit_of_value.abbrev])
        else:
            value_string = str(val)
        return value_string

    def price_formatted_decimal(self):
        val = self.price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if self.unit_of_price:
            if self.unit_of_price.symbol:
                price_string = "".join([self.unit_of_price.symbol, str(val)])
            else:
                price_string = " ".join([str(val), self.unit_of_price.abbrev])
        else:
            price_string = str(val)
        return price_string

    def form_prefix(self):
        return "-".join(["EVT", str(self.id)])

    def work_event_change_form(self, data=None):
        unit = self.unit_of_quantity
        if not unit:
            unit = self.resource_type.unit
        prefix = self.form_prefix()
        qty_help = "up to 2 decimal places"
        if unit:
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        from valuenetwork.valueaccounting.forms import InputEventAgentForm
        return InputEventAgentForm(qty_help=qty_help, context_agent=self.context_agent, instance=self, prefix=prefix, data=data)

    def change_form_old(self, data=None):
        from valuenetwork.valueaccounting.forms import TimeEventForm, InputEventForm
        unit = self.unit_of_quantity
        if not unit:
            unit = self.resource_type.unit
        prefix = self.form_prefix()
        if unit.unit_type == "time":
            return TimeEventForm(instance=self, prefix=prefix, data=data)
        else:
            qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
            return InputEventForm(qty_help=qty_help, instance=self, prefix=prefix, data=data)

    def change_form(self, data=None):
        from valuenetwork.valueaccounting.forms import InputEventForm
        unit = self.unit_of_quantity
        if not unit:
            unit = self.resource_type.unit
        prefix = self.form_prefix()
        qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
        return InputEventForm(qty_help=qty_help, instance=self, prefix=prefix, data=data)

    def distribution_change_form(self, data=None):
        from valuenetwork.valueaccounting.forms import DistributionEventForm
        prefix = self.form_prefix()
        return DistributionEventForm(instance=self, prefix=prefix, data=data)

    def disbursement_change_form(self, data=None):
        from valuenetwork.valueaccounting.forms import DisbursementEventForm
        prefix = self.form_prefix()
        return DisbursementEventForm(instance=self, prefix=prefix, data=data)

    #def exchange_change_form(self, data=None):
    #    from valuenetwork.valueaccounting.forms import ExchangeEventForm
    #    unit = self.unit_of_quantity
    #    if not unit:
    #        unit = self.resource_type.unit
    #    prefix = self.form_prefix()
    #    qty_help = " ".join(["unit:", unit.abbrev, ", up to 2 decimal places"])
    #    return ExchangeEventForm(qty_help=qty_help, instance=self, prefix=prefix, data=data)

    def unplanned_work_event_change_form(self):
        from valuenetwork.valueaccounting.forms import UnplannedWorkEventForm
        return UnplannedWorkEventForm(instance=self, prefix=str(self.id))

    def change_date_form(self):
        from valuenetwork.valueaccounting.forms import EventChangeDateForm
        return EventChangeDateForm(instance=self, prefix=str(self.id))

    def change_quantity_form(self):
        from valuenetwork.valueaccounting.forms import EventChangeQuantityForm
        return EventChangeQuantityForm(instance=self, prefix=str(self.id))

    def doer(self):
        if self.event_type.consumes_resources():
            return self.to_agent
        else:
            return self.from_agent

    def does_todo(self):
        if self.commitment:
            if self.commitment.event_type.relationship == "todo":
                return True
        return False

    def creates_resources(self):
        return self.event_type.creates_resources()

    def consumes_resources(self):
        return self.event_type.consumes_resources()

    def is_change_related(self):
        return self.event_type.is_change_related()

    def applies_stage(self):
        return self.event_type.applies_stage()

    def changes_stage(self):
        return self.event_type.changes_stage()

    def follow_process_chain_beyond_workflow(self, chain, all_events):
        #todo: this was created for a DHen report
        # but does not work yet because the converted data
        # has no commitments
        # Plus, it can't be tested and so probably won't work.
        if self.event_type.is_change_related():
            if self.process not in chain:
                chain.append(self.process)
                stage = self.process.process_type
                if stage:
                    if self.event_type.relationship == "out":
                        next_candidates = all_events.filter(
                            commitment__stage=stage,
                            event_type__relationship="in")
                        if next_candidates:
                            next_in_chain = next_candidates[0]
                    if self.event_type.relationship == "in":
                        next_candidates = self.process.events.filter(
                            resource_type=self.resource_type,
                            stage=stage,
                            event_type__relationship="out")
                    if next_in_chain:
                        next_in_chain[0].follow_stage_chain_beyond_workflow(chain)

    def compute_income_fractions_for_process(self, value_equation):
        #EconomicEvent (shipment) method
        shares = []
        #todo exchange redesign fallout
        # shipment events are no longer event_type.name == "Shipment"
        # they are et.name == "Give"
        if self.event_type.name == "Give":
            commitment = self.commitment
            #problem: if the shipment event with no (an uninventoried) resource has no commitment,
            #we can't find the process it came from.
            if commitment:
                production_commitments = commitment.get_production_commitments_for_shipment()
                if production_commitments:
                    visited = set()
                    path = []
                    depth = 0
                    #todo: later, work out how to handle multiple production commitments
                    pc = production_commitments[0]
                    p = pc.process
                    if p:
                        visited = set()
                        p.compute_income_shares(value_equation, self, self.quantity, shares, visited)

        return shares

    def get_shipment_commitment_for_production_event(self):
        if self.event_type.relationship == "out":
            if self.commitment:
                return self.commitment.order_item
        return None

    def get_shipment_commitment_for_distribution_event(self):
        if self.event_type.name == "Distribution":
            claims = self.claims()
            if claims:
                claim = claims[0]
                event = claim.creating_event()
                return event.get_shipment_commitment_for_production_event()
        return None

    def get_shipment_for_distribution(self):
        the_shipment = None
        if self.event_type.name == "Distribution":
            ship_ct = self.get_shipment_commitment_for_distribution_event()
            if ship_ct:
                ex = self.exchange
                dve = ex.distribution_value_equation()
                ship_evts = dve.shipments()
                for se in ship_evts:
                    if se.commitment:
                        if ship_ct == se.commitment:
                            the_shipment = se
        return the_shipment

    def get_order_for_distribution(self):
        the_order = None
        if self.event_type.name == "Distribution":
            ex = self.exchange
            dve = ex.distribution_value_equation()
            orders = dve.orders()
            if orders:
                the_order = orders[0]
        return the_order

    def independent_demand(self):
        if self.commitment:
            return self.commitment.independent_demand
        else:
            return self.process.independent_demand()

    def order_item(self):
        if self.commitment:
            return self.commitment.order_item
        else:
            return self.process.order_item()



#obsolete
class DistributionValueEquation(models.Model):
    '''
    Distribution itself is currently implemented using Exchange.  This is not totally correct from an REA point
    of view.  It groups events that apply to many earlier exchanges. If we were using subclasses, it might be that
    EconomicInteraction is the superclass of Process, Exchange, and Distribution.

    This class holds the remaining information for a Distribution.
    '''
    distribution_date = models.DateField(_('distribution date'))
    exchange = models.ForeignKey(Exchange,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('exchange'), related_name='value_equation')
    value_equation_link = models.ForeignKey(ValueEquation,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('value equation link'), related_name='distributions_ve')
    value_equation_content = models.TextField(_('value equation formulas used'), null=True, blank=True)

    def deserialize_value_equation_content(self):
        return simplejson.loads(self.value_equation_content)

    def buckets(self):
        dict = self.deserialize_value_equation_content()
        bucket_dict = dict["buckets"]
        buckets = []
        for key, value in list(bucket_dict.items()):
            bucket = ValueEquationBucket.objects.get(id=key)
            bucket.value = value
            buckets.append(bucket)
        return buckets

    def bucket_rules(self):
        buckets = self.buckets()
        answer = []
        for bucket in buckets:
            rules = bucket.value.get("bucket_rules")
            if rules:
                for key, value in list(rules.items()):
                    rule = ValueEquationBucketRule.objects.get(id=key)
                    rule.value = value
                    answer.append(rule)
        return answer

    def orders(self):
        buckets = self.buckets()
        orders = []
        for b in buckets:
            filter = b.value.get("filter")
            if filter:
                method = filter.get("method")
                if method:
                    if method == "Order":
                        oids = filter["orders"]
                        for oid in oids:
                            orders.append(Order.objects.get(id=oid))
        return orders

    def shipments(self):
        buckets = self.buckets()
        shipments = []
        for b in buckets:
            filter = b.value.get("filter")
            if filter:
                method = filter.get("method")
                if method:
                    if method == "Shipment":
                        ship_ids = filter["shipments"]
                        for sid in ship_ids:
                            shipments.append(EconomicEvent.objects.get(id=sid))
        return shipments


FILTER_METHOD_CHOICES = (
    ('order', _('Order')),
    ('shipment', _('Shipment or Delivery')),
    ('dates', _('Date range')),
    ('process', _('Process')),
)

class ValueEquationBucket(models.Model):
    name = models.CharField(_('name'), max_length=32)
    sequence = models.IntegerField(_('sequence'), default=0)
    value_equation = models.ForeignKey(ValueEquation, on_delete=models.CASCADE,
        verbose_name=_('value equation'), related_name='buckets')
    filter_method =  models.CharField(_('filter method'), null=True, blank=True,
        max_length=12, choices=FILTER_METHOD_CHOICES)
    percentage = models.DecimalField(_('bucket percentage'), max_digits=8, decimal_places=2, default=Decimal("0.0"))
    distribution_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="value_equation_buckets", verbose_name=_('distribution agent'))
    filter_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="value_equation_filter_buckets", verbose_name=_('filter agent'))
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='buckets_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='buckets_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    class Meta:
        ordering = ('sequence',)

    def __str__(self):
        return ' '.join([
            'Bucket',
            str(self.sequence),
            '-',
            str(self.percentage) + '%',
            '-',
            self.name,
        ])

    def run_bucket_value_equation(self, amount_to_distribute, context_agent, serialized_filter):
        #start_time = time.time()
        rules = self.bucket_rules.all()
        claim_events = []
        contribution_events = []
        bucket_events = self.gather_bucket_events(context_agent=context_agent, serialized_filter=serialized_filter)
        #tot = Decimal("0.0")
        for vebr in rules:
            vebr_events = vebr.filter_events(bucket_events)
            contribution_events.extend(vebr_events)
            #hours = sum(e.quantity for e in vebr_events)
            #print(vebr.filter_rule_deserialized(), "hours:", hours)
            #tot += hours

        #print("total vebr hours:", tot)
        claims = self.claims_from_events(contribution_events)
        if claims:
            total_amount = 0
            for claim in claims:
                total_amount = total_amount + claim.share
            if total_amount > 0:
                portion_of_amount = amount_to_distribute / total_amount
            else:
                portion_of_amount = Decimal("0.0")
            if self.value_equation.percentage_behavior == "remaining":
                if portion_of_amount > 1:
                    portion_of_amount = Decimal("1.0")
            ces = self.create_distribution_claim_events(claims=claims, portion_of_amount=portion_of_amount)
            claim_events.extend(ces)
        #end_time = time.time()
        #print("run_bucket_value_equation elapsed time was %g seconds" % (end_time - start_time))
        return claim_events, contribution_events

    def gather_bucket_events(self, context_agent, serialized_filter):
        #start_time = time.time()
        ve = self.value_equation
        events = []
        filter = ""
        if self.filter_method == 'dates':
            from valuenetwork.valueaccounting.forms import DateRangeForm
            form = DateRangeForm()
            bucket_filter = form.deserialize(serialized_filter)
            start_date = None
            end_date = None
            bucket_context_agent = None
            if "start_date" in bucket_filter:
                start_date = bucket_filter["start_date"]
                filter = "".join([
                    filter,
                    "Start date: ",
                    start_date.strftime('%Y-%m-%d')
                    ])
            if "end_date" in bucket_filter:
                end_date = bucket_filter["end_date"]
                filter = " ".join([
                    filter,
                    "End date:",
                    end_date.strftime('%Y-%m-%d')
                    ])
            if "context_agent" in bucket_filter:
                bucket_context_agent = bucket_filter["context_agent"]
                filter = "".join([
                    filter,
                    "Context agent: ",
                    bucket_context_agent.nick
                    ])
            if start_date and end_date:
                events = EconomicEvent.objects.filter(event_date__range=(start_date, end_date))
            elif start_date:
                events = EconomicEvent.objects.filter(event_date__gte=start_date)
            elif end_date:
                events = EconomicEvent.objects.filter(event_date__gte=end_date)
            if bucket_context_agent:
                #import pdb; pdb.set_trace()
                # FairCoop Open Coop Work specific !!!
                agents = bucket_context_agent.with_all_sub_agents() #includes self
                event_list = []
                for event in events:
                    if event.context_agent in agents and event.is_double_validated() and event.is_contribution == True: #probably don't need that last check
                        event_list.append(event)
                events = event_list
                #EconomicEvent.objects.filter(context_agent=bucket_context_agent)
            else:
                events = events.filter(context_agent=context_agent)
            for evt in events:
                br = evt.bucket_rule(ve)
                value = evt.value
                if br:
                    value = br.compute_claim_value(evt)
                if value:
                    vpu = value / evt.quantity
                    evt.share = evt.quantity * vpu

        elif self.filter_method == 'order':
            from valuenetwork.valueaccounting.forms import OrderMultiSelectForm
            form = OrderMultiSelectForm(context_agent=context_agent)
            bucket_filter = form.deserialize(serialized_filter)
            orders = bucket_filter["orders"]
            if orders:
                order_string = ", ".join([str(o.id) for o in orders])
                filter = "".join([
                    "Orders: ",
                    order_string,
                    ])
            events = []
            for order in orders:
                for order_item in order.order_items():
                    #todo 3d: one method to chase
                    oi_events = order_item.compute_income_fractions(ve)
                    events.extend(oi_events)
                exchanges = Exchange.objects.filter(order=order)
                for exchange in exchanges:
                    for payment in exchange.payment_events(): #todo: fix!
                        events.append(payment)
                    for work in exchange.work_events():
                        events.append(work)
        elif self.filter_method == 'shipment':
            from valuenetwork.valueaccounting.forms import ShipmentMultiSelectForm
            form = ShipmentMultiSelectForm(context_agent=context_agent)
            bucket_filter = form.deserialize(serialized_filter)
            shipment_events = bucket_filter["shipments"]
            if shipment_events:
                ship_string = ", ".join([str(s.id) for s in shipment_events])
                filter = "".join([
                    "Shipments: ",
                    ship_string,
                    ])
            #lots = [e.resource for e in shipment_events]
            events = []
            #tot = Decimal("0.0")
            for ship in shipment_events:
                resource = ship.resource
                qty = ship.quantity
                #todo 3d: two methods to chase
                if resource:
                    events.extend(resource.compute_shipment_income_shares(ve, qty)) #todo: fix
                else:
                    events.extend(ship.compute_income_fractions_for_process(ve))
                #hours = sum(e.quantity for e in events)
                #print(ship, "hours:", hours)
                #tot += hours

            #print("total event hours:", tot)
        elif self.filter_method == 'process':
            #todo exchange redesign fallout
            from valuenetwork.valueaccounting.forms import ProcessMultiSelectForm
            form = ProcessMultiSelectForm(context_agent=context_agent)
            bucket_filter = form.deserialize(serialized_filter)
            processes = bucket_filter["processes"]
            if processes:
                process_string = ", ".join([str(proc.id) for proc in processes])
                filter = "".join([
                    "Processes: ",
                    process_string,
                    ])
            events = []
            visited = set()
            for proc in processes:
                order_item = None
                qty = sum(pe.quantity for pe in proc.production_events())
                if not qty:
                    qty = Decimal("1.0")
                proc_events = []
                #visited = set()
                proc.compute_income_shares(ve, order_item, qty, proc_events, visited)
                events.extend(proc_events)

        for event in events:
            event.filter = filter
        #end_time = time.time()
        #print("gather_bucket_events elapsed time was %g seconds" % (end_time - start_time))
        return events

    def claims_from_events(self, events):
        claims = []
        for event in events:
            fraction = 1
            if event.value:
                try:
                    fraction = event.share / event.value
                except AttributeError:
                    pass
            existing_claim = next((c for c in claims if c.event == event),0)
            if existing_claim:
                claim = existing_claim
                addition = claim.original_value * fraction
                claim.share += addition
            else:
                if not event.context_agent.compatible_value_equation(self.value_equation):
                    context_agent = self.value_equation.context_agent
                    claim = event.get_unsaved_context_agent_claim(context_agent, event.vebr)
                else:
                    claim = event.get_unsaved_contribution_claim(event.vebr)
                if claim.value:
                    claim.share = claim.original_value * fraction
                    claim.event = event
                    claims.append(claim)
        return claims

    def create_distribution_claim_events(self, portion_of_amount, claims):
        claim_events = []
        #if claims == None:
        #    claims = self.gather_claims()
        for claim in claims:
            distr_amt = claim.share * portion_of_amount
            distr_amt = distr_amt.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            #if distr_amt > claim.value:
            #    distr_amt = claim.value
            if claim.value_equation_bucket_rule.claim_rule_type == "debt-like":
                claim.value = claim.value - distr_amt
            elif claim.value_equation_bucket_rule.claim_rule_type == "once":
                claim.value = 0
            claim.event.distr_amt = distr_amt
            unit_of_value = ""
            if claim.event.unit_of_value:
                unit_of_value = claim.event.unit_of_value.abbrev
            excuse = ""
            if portion_of_amount < 1:
                percent = (portion_of_amount * 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                excuse = "".join([
                    ", but the distribution amount covered only ",
                    str(percent),
                    "% of the claims for this bucket",
                    ])
            share = claim.share.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            sel = ""
            reason = ""
            obj = ""
            if "Orders" in claim.event.vebr.filter:
                obj = "order"
                sel = " to the selected orders"
            if "Shipments" in claim.event.vebr.filter:
                obj = "shipment"
                sel = " to the selected shipments"
            if share < claim.value:
                reason = " The reason the value added is less than the contribution value is that the contribution's value was not all used for this deliverable."
            claim.event.explanation = "".join([
                "This contribution added ", str(share), " ", unit_of_value,
                " of value",
                sel,
                excuse,
                ".",
                reason,
                ])

            claim_event = ClaimEvent(
                claim = claim,
                value = distr_amt,
                unit_of_value = claim.unit_of_value,
                event_effect = "-",
            )
            claim_events.append(claim_event)
        return claim_events

    def change_form(self):
        from valuenetwork.valueaccounting.forms import ValueEquationBucketForm
        return ValueEquationBucketForm(instance=self, prefix=str(self.id))

    def rule_form(self):
        from valuenetwork.valueaccounting.forms import ValueEquationBucketRuleForm
        return ValueEquationBucketRuleForm(prefix=str(self.id))

    def rule_filter_form(self):
        from valuenetwork.valueaccounting.forms import BucketRuleFilterSetForm
        ca = None
        pattern = None
        if self.value_equation.context_agent:
            ca = self.value_equation.context_agent
        uc = UseCase.objects.get(identifier='val_equation')
        patterns = ProcessPattern.objects.usecase_patterns(use_case=uc)
        if patterns.count() > 0:
            pattern = patterns[0]
        return BucketRuleFilterSetForm(prefix=str(self.id), context_agent=ca, event_type=None, pattern=pattern)

    def filter_entry_form(self, data=None):
        form = None
        if self.filter_method == "order":
            from valuenetwork.valueaccounting.forms import OrderMultiSelectForm
            if data == None:
                form = OrderMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent)
            else:
                form = OrderMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent, data=data)
        elif self.filter_method == "shipment":
            from valuenetwork.valueaccounting.forms import ShipmentMultiSelectForm #todo: fix
            if data == None:
                form = ShipmentMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent)
            else:
                form = ShipmentMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent, data=data)
        elif self.filter_method == "process":
            from valuenetwork.valueaccounting.forms import ProcessMultiSelectForm
            if data == None:
                form = ProcessMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent)
            else:
                form = ProcessMultiSelectForm(prefix=str(self.id), context_agent=self.value_equation.context_agent, data=data)
        elif self.filter_method == "dates":
            from valuenetwork.valueaccounting.forms import DateRangeForm
            if data == None:
                form = DateRangeForm(prefix=str(self.id))
            else:
                form = DateRangeForm(prefix=str(self.id), data=data)
        return form


DIVISION_RULE_CHOICES = (
    ('percentage', _('Percentage')),
    ('fifo', _('Oldest first')),
)

CLAIM_RULE_CHOICES = (
    ('debt-like', _('Until paid off')),
    ('equity-like', _('Forever')),
    ('once', _('One distribution')),
)

class ValueEquationBucketRule(models.Model):
    value_equation_bucket = models.ForeignKey(ValueEquationBucket, on_delete=models.CASCADE,
        verbose_name=_('value equation bucket'), related_name='bucket_rules')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        related_name="bucket_rules", verbose_name=_('event type'))
    filter_rule = models.TextField(_('filter rule'), null=True, blank=True)
    #todo: thinking we can get rid of division_rule, see if we have requirement
    division_rule =  models.CharField(_('division rule'),
        max_length=12, choices=DIVISION_RULE_CHOICES)
    claim_rule_type = models.CharField(_('claim rule type'),
        max_length=12, choices=CLAIM_RULE_CHOICES)
    claim_creation_equation = models.TextField(_('claim creation equation'),
        null=True, blank=True)
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='rules_created', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    changed_by = models.ForeignKey(User, verbose_name=_('changed by'),
        related_name='rules_changed', blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    created_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    changed_date = models.DateField(auto_now=True, blank=True, null=True, editable=False)

    def __str__(self):
        return ' '.join([
            'rule for:',
            self.value_equation_bucket.__str__(),
            '-',
            self.event_type.name,
        ])

    def filter_rule_deserialized(self):
        if self.filter_rule:
            from valuenetwork.valueaccounting.forms import BucketRuleFilterSetForm
            form = BucketRuleFilterSetForm(prefix=str(self.id), context_agent=None, event_type=None, pattern=None)
            return form.deserialize(json=self.filter_rule)
        else:
            return self.filter_rule

    def filter_events(self, events):
        json = self.filter_rule_deserialized()
        process_types = []
        resource_types = []
        if 'process_types' in list(json.keys()):
            process_types = json['process_types']
        if 'resource_types' in list(json.keys()):
            resource_types = json['resource_types']
        vebr_filter = self.filter_rule_display_list()
        events = [e for e in events if e.event_type==self.event_type]
        if process_types:
            events_with_processes = [e for e in events if e.process]
            events = [e for e in events_with_processes if e.process.process_type in process_types]
        if resource_types:
            events = [e for e in events if e.resource_type in resource_types]
        for e in events:
            e.vebr = self
            e.vebr.filter = vebr_filter + " " + e.filter
        return events

    def normalize_equation(self):
        eq = self.claim_creation_equation.split(" ")
        for i, x in enumerate(eq):
            eq[i] = x.replace("_","")
            try:
                y = Decimal(x)
                eq[i] = "".join(["Decimal('", x, "')"])
            except InvalidOperation:
                continue
        s = " "
        return s.join(eq)

    def compute_claim_value(self, event):
        equation = self.normalize_equation()
        safe_list = ['math',]
        safe_dict = dict([ (k, locals().get(k, None)) for k in safe_list ])
        safe_dict['Decimal'] = Decimal
        safe_dict['quantity'] = event.quantity
        safe_dict['valuePerUnit'] = event.value_per_unit()
        safe_dict['pricePerUnit'] = event.resource_type.price_per_unit
        if event.resource:
            safe_dict['valuePerUnitOfUse'] = event.resource.value_per_unit_of_use
        safe_dict['value'] = event.value
        #safe_dict['importance'] = event.importance()
        #safe_dict['reputation'] = event.from_agent.reputation
        #safe_dict['seniority'] = Decimal(event.seniority())
        value = eval(equation, {"__builtins__":None}, safe_dict)
        return value

    def default_equation(self):
        et = self.event_type
        return et.default_event_value_equation()

    def filter_rule_display_list(self):
        json = self.filter_rule_deserialized()
        pts = []
        rts = []
        if 'process_types' in list(json.keys()):
            pts = json['process_types']
        if 'resource_types' in list(json.keys()):
            rts = json['resource_types']
        filter = ""
        #for pt in pts:
        #    filter += pt.name + ", "
        #for rt in rts:
        #    filter += rt.name + ","
        if pts:
            filter = ", ".join([pt.name for pt in pts])
        if pts and rts:
            filter = ", ".join(filter, [pt.name for pt in pts])
        elif rts:
            filter = ", ".join([rt.name for rt in rts])
        return filter

    def test_results(self):
        fr = self.filter_rule_deserialized()
        pts = []
        rts = []
        if 'process_types' in list(fr.keys()):
            pts = fr['process_types']
        if 'resource_types' in list(fr.keys()):
            rts = fr['resource_types']
        events = EconomicEvent.objects.filter(context_agent=self.value_equation_bucket.value_equation.context_agent, event_type=self.event_type)
        if pts:
            events = events.filter(process__process_type__in=pts)
        if rts:
            events = events.filter(resource_type__in=rts)
        return events

    def change_form(self):
        from valuenetwork.valueaccounting.forms import ValueEquationBucketRuleForm
        return ValueEquationBucketRuleForm(prefix="vebr" + str(self.id), instance=self)

    def change_filter_form(self):
        from valuenetwork.valueaccounting.forms import BucketRuleFilterSetForm
        ca = None
        pattern = None
        if self.value_equation_bucket.value_equation.context_agent:
            ca = self.value_equation_bucket.value_equation.context_agent
        uc = UseCase.objects.get(identifier='val_equation')
        patterns = ProcessPattern.objects.usecase_patterns(use_case=uc)
        if patterns.count() > 0:
            pattern = patterns[0]
        json = self.filter_rule_deserialized()
        return BucketRuleFilterSetForm(prefix="vebrf" + str(self.id), initial=json, context_agent=ca, event_type=self.event_type, pattern=pattern)


class IncomeEventDistribution(models.Model):
    distribution_date = models.DateField(_('distribution date'))
    #next field obsolete
    distribution = models.ForeignKey(Exchange,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('distribution'), related_name='cash_receipts', default=None)
    distribution_ref = models.ForeignKey(Distribution,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('distribution'), related_name='income_events')
    income_event = models.ForeignKey(EconomicEvent, on_delete=models.CASCADE,
        related_name="distributions", verbose_name=_('income event'))
    quantity = models.DecimalField(_('quantity'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_quantity = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit'), related_name="units")


class Claim(models.Model):
    value_equation_bucket_rule = models.ForeignKey(ValueEquationBucketRule,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="claims", verbose_name=_('value equation bucket rule'))
    claim_date = models.DateField(_('claim date'))
    has_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="has_claims", verbose_name=_('has'))
    against_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="claims_against", verbose_name=_('against'))
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True,
        limit_choices_to={"is_context": True,},
        related_name="claims", verbose_name=_('context agent'),
        on_delete=models.SET_NULL)
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of value'), related_name="claim_value_units")
    original_value = models.DecimalField(_('original value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    claim_creation_equation = models.TextField(_('creation equation'), null=True, blank=True)

    slug = models.SlugField(_("Page name"), editable=False)

    class Meta:
        ordering = ('claim_date',)

    def __str__(self):
        if self.unit_of_value:
            if self.unit_of_value.symbol:
                value_string = "".join([self.unit_of_value.symbol, str(self.value)])
            else:
                value_string = " ".join([str(self.value), self.unit_of_value.abbrev])
        else:
            value_string = str(self.value)
        has_agt = 'Unassigned'
        if self.has_agent:
            has_agt = self.has_agent.nick
        against_agt = 'Unassigned'
        if self.against_agent:
            against_agt = self.against_agent.nick
        return ' '.join([
            'Claim',
            has_agt,
            'has against',
            against_agt,
            'for',
            value_string,
            'from',
            self.claim_date.strftime('%Y-%m-%d'),
        ])

    def creating_event(self):
        event = None
        claim_events = self.claim_events.all()
        for ce in claim_events:
            if ce.event_effect == "+":
                event = ce.event
                break
        return event

    def format_value(self, value):
        if self.unit_of_value:
            if self.unit_of_value.symbol:
                value_string = "".join([self.unit_of_value.symbol, str(value)])
            else:
                value_string = " ".join([str(value), self.unit_of_value.abbrev])
        else:
            value_string = str(value)
        return value_string

    def original_value_formatted(self):
        value = self.original_value
        return self.format_value(value)

    def value_formatted(self):
        value = self.value
        return self.format_value(value)

    def distribution_events(self):
        return self.claim_events.filter(event__event_type__name="Distribution")


EVENT_EFFECT_CHOICES = (
    ('+', _('increase')),
    ('-', _('decrease')),
 )

class ClaimEvent(models.Model):
    event = models.ForeignKey(EconomicEvent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="claim_events", verbose_name=_('claim event'))
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE,
        related_name="claim_events", verbose_name=_('claims'))
    claim_event_date = models.DateField(_('claim event date'), default=datetime.date.today)
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2)
    unit_of_value = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('unit of value'), related_name="claim_event_value_units")
    event_effect = models.CharField(_('event effect'),
        max_length=12, choices=EVENT_EFFECT_CHOICES)

    class Meta:
        ordering = ('claim_event_date',)

    def __str__(self):
        if self.unit_of_value:
            value_string = " ".join([str(self.value), self.unit_of_value.abbrev])
        else:
            value_string = str(self.value)
        if self.event:
            event_str = self.event.__str__()
        else:
            event_str = "none"
        return ' '.join([
            'event:',
            event_str,
            'affecting claim:',
            self.claim.__str__(),
            'value:',
            value_string,
        ])

    def update_claim(self):
        if self.event_effect == "+":
            self.claim.value += self.value
        else:
            self.claim.value -= self.value
        self.claim.save()

    def value_formatted(self):
        value = self.value
        if self.unit_of_value:
            if self.unit_of_value.symbol:
                value_string = "".join([self.unit_of_value.symbol, str(value)])
            else:
                value_string = " ".join([str(value), self.unit_of_value.abbrev])
        else:
            value_string = str(value)
        return value_string


class EventSummary(object):
    def __init__(self, agent, context_agent, resource_type, event_type, quantity, value=Decimal('0.0')):
        self.agent = agent
        self.context_agent = context_agent
        self.resource_type = resource_type
        self.event_type = event_type
        self.quantity = quantity
        self.value=value

    def key(self):
        return "-".join([
            str(self.agent.id),
            str(self.resource_type.id),
            str(self.project.id),
            str(self.event_type.id),
            ])

    def quantity_formatted(self):
        return self.quantity.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


#todo: this model is obsolete and can be deleted
#as soon as we also remove the value equation demo page, view, etc.
class CachedEventSummary(models.Model):
    agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        related_name="cached_events", verbose_name=_('agent'))
    context_agent = models.ForeignKey(EconomicAgent,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('context agent'), related_name='context_cached_events')
    resource_type = models.ForeignKey(EconomicResourceType,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('resource type'), related_name='cached_events')
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE,
        verbose_name=_('event type'), related_name='cached_events')
    resource_type_rate = models.DecimalField(_('resource type rate'), max_digits=8, decimal_places=2, default=Decimal("1.0"))
    importance = models.DecimalField(_('importance'), max_digits=3, decimal_places=0, default=Decimal("1"))
    reputation = models.DecimalField(_('reputation'), max_digits=8, decimal_places=2,
        default=Decimal("1.00"))
    quantity = models.DecimalField(_('quantity'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))
    value = models.DecimalField(_('value'), max_digits=8, decimal_places=2,
        default=Decimal("0.0"))

    class Meta:
        ordering = ('agent', 'context_agent', 'resource_type')

    def __str__(self):
        agent_name = "Unknown"
        if hasattr(self, 'agent'):
            if self.agent:
                agent_name = self.agent.name
        context_agent_name = "Unknown"
        if hasattr(self, 'context_agent') and self.context_agent:
            context_agent_name = self.context_agent.name
        resource_type_name = "Unknown"
        if hasattr(self, 'resource_type') and self.resource_type:
            resource_type_name = self.resource_type.name
        return ' '.join([
            'Agent:',
            agent_name,
            'Context:',
            context_agent_name,
            'Resource Type:',
            resource_type_name,
        ])

    @classmethod
    def summarize_events(cls, context_agent):
        #todo: this code is obsolete, we don't want to roll up sub-projects anymore
        all_subs = context_agent.with_all_sub_agents()
        event_list = EconomicEvent.objects.filter(context_agent__in=all_subs)
        summaries = {}
        for event in event_list:
            key = "-".join([str(event.from_agent.id), str(event.context_agent.id), str(event.resource_type.id)])
            if not key in summaries:
                summaries[key] = EventSummary(event.from_agent, event.context_agent, event.resource_type, Decimal('0.0'))
            summaries[key].quantity += event.quantity
        summaries = list(summaries.values())
        for summary in summaries:
            ces = cls(
                agent=summary.agent,
                context_agent=summary.context_agent,
                resource_type=summary.resource_type,
                resource_type_rate=summary.resource_type.value_per_unit,
                #importance=summary.project.importance, todo: need this in agent?
                quantity=summary.quantity,
            )
            ces.save()
        return cls.objects.all()

    @classmethod
    def summarize_all_events(cls):
        old_summaries = CachedEventSummary.objects.all()
        old_summaries.delete()
        event_list = EconomicEvent.objects.filter(is_contribution="true")
        summaries = {}
        #todo: very temporary hack
        context_agent = EconomicAgent.objects.get(name_en="Not defined")
        for event in event_list:
            #todo: very temporary hack
            if not event.context_agent:
                event.context_agent=context_agent
                event.save()
            try:
                key = "-".join([
                    str(event.from_agent.id),
                    str(event.context_agent.id),
                    str(event.resource_type.id),
                    str(event.event_type.id)
                    ])
                if not key in summaries:
                    summaries[key] = EventSummary(
                        event.from_agent,
                        event.context_agent,
                        event.resource_type,
                        event.event_type,
                        Decimal('0.0'))
                summaries[key].quantity += event.quantity
            except AttributeError:
                msg = " ".join(["invalid summary key:", key])
                assert False, msg
        summaries = list(summaries.values())
        for summary in summaries:
            ces = cls(
                agent=summary.agent,
                context_agent=summary.context_agent,
                resource_type=summary.resource_type,
                event_type=summary.event_type,
                resource_type_rate=summary.resource_type.value_per_unit,
                quantity=summary.quantity,
            )
            ces.save()
        return cls.objects.all()


    def quantity_formatted(self):
        return self.quantity.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    def value_formatted(self):
        return self.value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    def quantity_label(self):
        #return " ".join([self.resource_type.name, self.resource_type.unit.abbrev])
        return self.resource_type.name
