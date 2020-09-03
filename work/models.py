#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.db import models, connection
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib import messages
from django.conf import settings
from django.shortcuts import get_object_or_404

import decimal # import Decimal
from django.utils.translation import ugettext_lazy as _

from easy_thumbnails.fields import ThumbnailerImageField

from valuenetwork.valueaccounting.models import *
from fobi.models import FormEntry

from django_nine.versions import DJANGO_LTE_1_5
from fobi.contrib.plugins.form_handlers.db_store.models import SavedFormDataEntry
import simplejson as json
import random
import hashlib

from django_comments.models import Comment
from general.models import UnitRatio
from faircoin import utils as faircoin_utils

from mptt.fields import TreeForeignKey

if "pinax.notifications" in settings.INSTALLED_APPS:
    from pinax.notifications import models as notification
else:
    notification = None

import logging
loger = logging.getLogger("ocp")

def get_site_name(request=None):
    if request:
        domain = request.get_host()
        try:
            obj = settings.PROJECTS_LOGIN
            for pro in obj:
                if obj[pro]['domains']:
                    if domain in obj[pro]['domains']:
                        proj = get_object_or_404(Project, fobi_slug=pro)
                        if proj:
                            return proj.agent.name
        except:
            pass
    return Site.objects.get_current().name



MEMBERSHIP_TYPE_CHOICES = (
    #('participant', _('project participant (no membership)')),
    ('individual', _('individual membership (min 1 share)')),
    ('collective', _('collective membership (min 2 shares)')),
)

REQUEST_STATE_CHOICES = (
    ('new', _('new')),
    ('accepted', _('accepted')),
    ('declined', _('declined')),
)

class MembershipRequest(models.Model):
    request_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    name = models.CharField(_('Name'), max_length=255)
    surname = models.CharField(_('Surname (for individual memberships)'), max_length=255, blank=True)
    requested_username = models.CharField(_('Requested username'), max_length=32)
    email_address = models.EmailField(_('Email address'), max_length=96,)
    phone_number = models.CharField(_('Phone number'), max_length=32, blank=True, null=True)
    address = models.CharField(_('Where do you live?'), max_length=255, blank=True)
    native_language = models.CharField(_('Languages'), max_length=255, blank=True)
    type_of_membership = models.CharField(_('Type of membership'),
        max_length=12, choices=MEMBERSHIP_TYPE_CHOICES,
        default="individual")
    number_of_shares = models.IntegerField(_('Number of shares'),
        default=1,
        help_text=_("How many shares would you like to underwrite? Each share is worth 30 Euros"))
    description = models.TextField(_('Description'),
        help_text=_("Describe your project or collective and the skills or abilities you can offer the cooperative"))
    website = models.CharField(_('Website'), max_length=255, blank=True)
    fairnetwork = models.CharField(_('FairNetwork username'), max_length=255, blank=True,
        help_text = _("The username you use in the FairNetwork at <a href='https://fair.coop' target='_blank'>fair.coop</a>"))
    usefaircoin = models.CharField(_('UseFaircoin profile'), max_length=255, blank=True,
        help_text = _("If you are in the directory at <a href='https://use.fair-coin.org' target='_blank'>use.fair-coin.org</a> please add the URL to your profile."))
    fairmarket = models.CharField(_('FairMarket shop'), max_length=255, blank=True,
        help_text = _("If you have an online shop at <a href='https://market.fair.coop' target='_blank'>market.fair.coop</a> please add the URL to your fair shop."))
    known_member = models.CharField(_('Are there any FairCoop participant(s) who can give references about you? If so, who?'), max_length=255, blank=True)
    comments_and_questions = models.TextField(_('Comments and questions'), blank=True,)

    agent = models.ForeignKey(EconomicAgent,
        verbose_name=_('agent'), related_name='membership_requests',
        blank=True, null=True,
        help_text=_("this membership request became this EconomicAgent"),
        on_delete=models.SET_NULL)
    state = models.CharField(_('state'),
        max_length=12, choices=REQUEST_STATE_CHOICES,
        default='new', editable=False)

    def __str__(self):
        return self.name

    def fdc(self):
        return EconomicAgent.objects.freedom_coop()



JOINING_STYLE_CHOICES = (
    ('subscription', _('subscription')),
    ('shares', _('shares')),
    ('moderated', _('moderated')),
    ('autojoin', _('autojoin')),
)

VISIBILITY_CHOICES = (
    ('private', _('private')),
    ('FCmembers', _('only FC members')),
    ('public', _('public')),
)

SELECTION_CHOICES = (
    ('project', _('your project')),
    #('related', _('all related projects')),
    ('all', _('all platform')),
)

class Project(models.Model):
    agent = models.OneToOneField(EconomicAgent,
        verbose_name=_('agent'), related_name='project', on_delete=models.CASCADE)
    joining_style = models.CharField(_('joining style'),
        max_length=12, choices=JOINING_STYLE_CHOICES,
        default="autojoin")
    auto_create_pass = models.BooleanField(_('auto create users'),
        #null=True,
        #verbose_name=_("auto create user+agents and confirm email"),
        default=False
    )
    visibility = models.CharField(_('visibility'),
        max_length=12, choices=VISIBILITY_CHOICES,
        default="FCmembers")
    resource_type_selection = models.CharField(_('resource type selection'),
        max_length=12, choices=SELECTION_CHOICES,
        default="all")
    fobi_slug = models.CharField(_('custom form slug'),
        max_length=255, blank=True)

    def __str__(self):
        return _('Project: ') + self.agent.name

    def is_moderated(self):
        if self.joining_style in ['moderated','shares','subscription']:
            return True
        return False #self.joining_style == 'moderated'

    def is_public(self):
        return self.visibility == 'public'

    def fobi_form(self):
        if self.fobi_slug:
            try:
                entry = FormEntry.objects.get(slug=self.fobi_slug)
                return entry
            except:
                pass
        return False

    def rts_with_clas(self, clas=None):
        rts_with_clas = []
        rts = list(set([arr.resource.resource_type for arr in self.agent.resource_relationships()]))
        for rt in rts:
            if hasattr(rt, 'ocp_artwork_type') and rt.ocp_artwork_type and rt.ocp_artwork_type.clas:
                if clas:
                    if clas == rt.ocp_artwork_type.clas:
                        rts_with_clas = rt
                else:
                    rts_with_clas.append(rt)
        return rts_with_clas

    """def shares_account_type(self):
        at = None
        form = self.fobi_form()
        if form:
            fields = form.formelemententry_set.all()
            for fi in fields:
                data = json.loads(fi.plugin_data)
                name = data.get('name')
                for rt in self.rts_with_clas():
                    if rt.ocp_artwork_type.clas == name: # matches the rt clas identifier with the fobi field name
                        at = rt
        return at"""

    def shares_type(self):
        st = None
        if self.joining_style == 'shares':
          at = self.shares_account_type()
          if at:
            if hasattr(at, 'ocp_artwork_type') and at.ocp_artwork_type:
                if hasattr(at.ocp_artwork_type, 'rel_nonmaterial_type') and at.ocp_artwork_type.rel_nonmaterial_type:
                    if hasattr(at.ocp_artwork_type.rel_nonmaterial_type, 'resource_type') and at.ocp_artwork_type.rel_nonmaterial_type.resource_type:
                        st = at.ocp_artwork_type.rel_nonmaterial_type.resource_type
                    else:
                        print("ERROR: The at.ocp_artwork_type.rel_nonmaterial_type: "+str(at.ocp_artwork_type.rel_nonmaterial_type)+" has no 'resource_type' !")
                        loger.error("ERROR: The at.ocp_artwork_type.rel_nonmaterial_type: "+str(at.ocp_artwork_type.rel_nonmaterial_type)+" has no 'resource_type' !")
                else:
                    print("ERROR: The at.ocp_artwork_type: "+str(at.ocp_artwork_type)+" has no 'rel_nonmaterial_type' !")
                    loger.error("ERROR: The at.ocp_artwork_type: "+str(at.ocp_artwork_type)+" has no 'rel_nonmaterial_type' !")
            else:
                print("ERROR: The at: "+str(at)+" has no 'ocp_artwork_type' !")
                loger.error("ERROR: The at: "+str(at)+" has no 'ocp_artwork_type' !")
          else:
            print("ERROR: The project has no shares_account_type? pro:"+str(self.agent.nick))
            loger.error("ERROR: The project has no shares_account_type? pro:"+str(self.agent.nick))
        return st

    def share_types(self):
        shr_ts = []
        if self.is_moderated() and self.fobi_slug:
            form = self.fobi_form()
            if form:
              fields = form.formelemententry_set.all()
              for fi in fields:
                data = json.loads(fi.plugin_data)
                name = data.get('name')
                for rt in self.rts_with_clas():
                    if rt.ocp_artwork_type.clas == name: # matches the rt clas identifier with the fobi field name
                        choi = data.get('choices')
                        if choi:
                            opts = choi.split('\r\n')
                            for op in opts:
                                opa = op.split(',')
                                shr_ts.append(opa[1].strip())
                        else:
                            #import pdb; pdb.set_trace()
                            text = data.get('help_text')
                            opts = text.split('\r\n')
                            for op in opts:
                                shr_ts.append(op.strip(' /'))

            if len(shr_ts):
                return shr_ts
        return False

    def share_totals(self):
        shr_ts = self.share_types()
        shares_res = None
        total = 0
        self.holders = 0
        if shr_ts:
            rts = self.rts_with_clas()
            shr_rt = None
            for rt in rts:
                if rt.ocp_artwork_type.general_unit_type:
                    if rt.ocp_artwork_type.general_unit_type.clas == self.fobi_slug+'_shares':
                        shr_rt = rt
            if shr_rt:
                shares_res = EconomicResource.objects.filter(resource_type=shr_rt)
        if shares_res:
            for res in shares_res:
                if res.price_per_unit:
                    total += res.price_per_unit
                    self.holders += 1
        return total

    def share_holders(self):
        if self.share_totals():
            return self.holders

    def payment_options(self):
        pay_opts = []
        if self.is_moderated() and self.fobi_slug:
            form = self.fobi_form()
            if form:
              fields = form.formelemententry_set.all()
              for fi in fields:
                data = json.loads(fi.plugin_data)
                name = data.get('name')
                if name == "payment_mode": # name of the fobi field
                    choi = data.get('choices')
                    if choi:
                        opts = choi.split('\r\n')
                        for op in opts:
                            opa = op.split(',')
                            key = opa[0].strip()
                            val = opa[1].strip()
                            ok = '<span class="error">config pending!</span>'
                            gates = self.payment_gateways()
                            if gates:
                                try:
                                    gate = gates[key]
                                except:
                                    gate = None
                                if gate:
                                    ok = '<span style="color:#090">ok:</span>'
                                    if 'html' in gate:
                                        if not isinstance(gate['html'], str) and not isinstance(gate['html'], str):
                                            html = gate['html']
                                            html = str(html) #.decode('utf-8')
                                        else:
                                            html = gate['html']
                                        ok += ' <ul style="padding: 0 0 10px 15px;"><li style="list-style:none;">'+html+'</li></ul>'
                                    else:
                                        ok = "Error: no html?"
                                else:
                                    ok = "Error: no gate?"
                            pay_opts.append("<b>"+val+'</b> &nbsp;'+ok)
              return pay_opts
        return False

    def background_url(self):
        back = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                back = settings.PROJECTS_LOGIN[self.fobi_slug]['background_url']
            except:
                pass
        return back

    def custom_css(self):
        css = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                css = settings.PROJECTS_LOGIN[self.fobi_slug]['css']
            except:
                pass
        return css

    def custom_js(self):
        js = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                js = settings.PROJECTS_LOGIN[self.fobi_slug]['js']
            except:
                pass
        return js

    def custom_html(self):
        html = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                html = settings.PROJECTS_LOGIN[self.fobi_slug]['html']
            except:
                pass
        return html

    def services(self):
        serv = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                serv = settings.PROJECTS_LOGIN[self.fobi_slug]['services']
            except:
                pass
        return serv

    def custom_login(self):
        resp = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                resp = settings.PROJECTS_LOGIN[self.fobi_slug]
            except:
                pass
        return resp

    def custom_smtp(self):
        resp = False
        if settings.PROJECTS_LOGIN and self.fobi_slug:
            try:
                resp = settings.PROJECTS_LOGIN[self.fobi_slug]['smtp']
            except:
                pass
        return resp


    def payment_gateways(self):
        gates = False
        if settings.PAYMENT_GATEWAYS and self.fobi_slug:
            try:
                gates = settings.PAYMENT_GATEWAYS[self.fobi_slug]
            except:
                pass
        return gates

    def fobi_items_keys(self):
        fobi_keys = []
        form = self.fobi_form()
        if form:
            fields = form.formelemententry_set.all()
            for fi in fields:
                if fi.plugin_data:
                    data = json.loads(fi.plugin_data)
                    name = data.get('name')
                    fobi_keys.append(name)
                else:
                    print("WARN: No plugin_data for field: "+str(fi)+" of the form: "+str(form.id))
        return fobi_keys

    def subscription_rt(self):
        rt = None
        sut = self.subscription_unit()
        if sut:
            surts = EconomicResourceType.objects.filter(name_en=self.compact_name()+" Subscription")
            if not surts:
                surts = EconomicResourceType.objects.filter(name_en=self.agent.nick_en+" Subscription")
            if not surts:
                surts = EconomicResourceType.objects.filter(name_en=self.agent.nick_es+" Subscription")
            if not surts:
                surts = EconomicResourceType.objects.filter(name_en=self.agent.nick+" Subscription")
            if surts:
                rt = surts[0]
        return rt

    def subscription_unit(self):
        unit = None
        if self.joining_style == 'subscription':
          if not hasattr(self, 'subscript_unit'):
            for key in self.fobi_items_keys():
                if key:
                    keyarr = key.split('_')
                    if len(keyarr) == 2:
                        if keyarr[0] == 'amount': # fieldname specially defined for subscription amount and base currency
                            unit = Unit.objects.get(abbrev=keyarr[1])
            if not unit:
                print("ERROR: Subscription Unit not found!! keys: "+str(self.fobi_items_keys()))
                loger.error("ERROR: Subscription Unit not found!! keys: "+str(self.fobi_items_keys()))
            else:
                self.subscript_unit = unit
          else:
            unit = self.subscript_unit
        return unit

    def shares_account_type(self):
        account_type = None
        if self.is_moderated() and self.fobi_slug:
            rts = self.rts_with_clas() #list(set([arr.resource.resource_type for arr in self.agent.resource_relationships()]))
            keys = self.fobi_items_keys()
            for rt in rts:
                for key in keys:
                    if key == rt.ocp_artwork_type.clas: # fieldname is the artwork type clas, project has shares of this type
                        account_type = rt
                        break
                if account_type:
                    break
            if not account_type and self.joining_style == 'shares':
                print("WARN: Can't find any account_type for project: "+str(self))
        return account_type

    def active_payment_options_obj(self):
        pay_opts = []
        if self.is_moderated() and self.fobi_slug:
            form = self.fobi_form()
            if form:
              fields = form.formelemententry_set.all()
              for fi in fields:
                data = json.loads(fi.plugin_data)
                name = data.get('name')
                if name == "payment_mode": # name of the fobi field
                    choi = data.get('choices')
                    if choi:
                        opts = choi.split('\r\n')
                        for op in opts:
                            opa = op.split(',')
                            key = opa[0].strip()
                            val = opa[1].strip()
                            gates = self.payment_gateways()
                            if gates:
                                try:
                                    gate = gates[key]
                                except:
                                    gate = None
                                if gate is not None:
                                    pay_opts.append([key, val])
        return pay_opts

    def compact_name(self):
        name = self.agent.name_en.title()
        arr = name.split()
        name = ''.join(arr)
        return name

    def abbrev_name(self):
        name = self.agent.name_en
        arr = name.split()
        abbr = ''
        for a in arr:
            abbr += a[:1]
        if len(abbr) < 3:
            arr = name.split()
            if len(arr[0]) > len(arr[1]): # a case like Freedom Coop, to became FdC
                first = arr[0]
                pos = int(len(first)/2)+1
                half = first[pos:pos+1]
                abbr = arr[0][:1]+half+arr[1][:1]
        return abbr

    def multiwallet_auth(self): # is for checking payments via botc-wallet (which requires auth).
        auth = None
        if self.agent.need_multicurrency():
            if 'multicurrency' in settings.INSTALLED_APPS:
                from multicurrency.models import MulticurrencyAuth
                try:
                    oauths = MulticurrencyAuth.objects.filter(agent=self.agent)
                except MulticurrencyAuth.DoesNotExist:
                    raise PermissionDenied
                if len(oauths) > 1:
                    for oau in oauths:
                        if 'wallet' in oau.auth_user:
                            auth = oau
                    if not auth:
                        print("More than one oauth for this project! return only the first. Agent:"+str(self.agent))
                        loger.warning("More than one oauth for this project! return only the first. Agent:"+str(self.agent))
                        auth = oauths[0]
                elif oauths:
                    auth = oauths[0]
                if not auth:
                    print("Not found any oauth for project: "+str(self.agent))
                    loger.error("Not found any oauth for project: "+str(self.agent))
        return auth



class SkillSuggestion(models.Model):
    skill = models.CharField(_('skill'), max_length=128,
        help_text=_("A new skill that you want to offer that is not already listed"))
    suggested_by = models.ForeignKey(User, verbose_name=_('suggested by'),
        related_name='skill_suggestion', blank=True, null=True,
        editable=False, on_delete=models.SET_NULL)
    suggestion_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    resource_type = models.ForeignKey(EconomicResourceType,
        verbose_name=_('resource_type'), related_name='skill_suggestions',
        blank=True, null=True,
        on_delete=models.SET_NULL,
        help_text=_("this skill suggestion became this ResourceType"))
    state = models.CharField(_('state'),
        max_length=12, choices=REQUEST_STATE_CHOICES,
        default='new', editable=False)


    def __str__(self):
        return self.skill

    def form_prefix(self):
        return "".join(["SS", str(self.id)])

    def resource_type_form(self):
        from valuenetwork.valueaccounting.forms import SkillSuggestionResourceTypeForm
        init = {
            "name": self.skill,
            }
        return SkillSuggestionResourceTypeForm(initial=init, prefix=self.form_prefix())





WALLET = faircoin_utils.is_connected()

USER_TYPE_CHOICES = (
    #('participant', _('project participant (no membership)')),
    ('individual', _('individual')),
    ('collective', _('collective')),
)


class JoinRequest(models.Model):
    # common fields for all projects
    project = models.ForeignKey(Project,
        verbose_name=_('project'), related_name='join_requests',
        on_delete=models.CASCADE,
        #blank=True, null=True,
        help_text=_("this join request is for joining this Project"))

    request_date = models.DateField(auto_now_add=True, blank=True, null=True, editable=False)
    type_of_user = models.CharField(_('Type of user'),
        max_length=12, choices=USER_TYPE_CHOICES,
        default="individual",
        help_text=_("* Required fields"))
    name = models.CharField(_('Name'), max_length=255)
    surname = models.CharField(_('Surname (for individual join requests)'), max_length=255, blank=True)
    requested_username = models.CharField(_('Username'), max_length=32, help_text=_("If you have already an account in OCP, you can login before filling this form to have this project in the same account, or you can choose another username and email to have it separate."))
    email_address = models.EmailField(_('Email address'), max_length=96,)
    #    help_text=_("this field is optional, but we can't contact you via email without it"))
    phone_number = models.CharField(_('Phone number'), max_length=32, blank=True, null=True)
    address = models.CharField(_('Town/Region where you are based'), max_length=255, blank=True, null=True)
    website = models.CharField(_('Website'), max_length=255, blank=True, null=True)
    #native_language = models.CharField(_('Languages'), max_length=255, blank=True)

    #description = models.TextField(_('Description'),
    #    help_text=_("Describe your collective or the personal skills you can offer to the project"))

    agent = models.ForeignKey(EconomicAgent,
        verbose_name=_('agent'), related_name='project_join_requests',
        blank=True, null=True, on_delete=models.CASCADE,
        help_text=_("this join request became this EconomicAgent"))

    fobi_data = models.OneToOneField(SavedFormDataEntry,
        verbose_name=_('custom fobi entry'), related_name='join_request',
        blank=True, null=True, on_delete=models.CASCADE,
        help_text=_("this join request is linked to this custom form (fobi SavedFormDataEntry)"))

    state = models.CharField(_('state'),
        max_length=12, choices=REQUEST_STATE_CHOICES,
        default='new', editable=False)

    exchange = models.OneToOneField(Exchange,
        verbose_name=_('exchange'), related_name='join_request',
        blank=True, null=True, on_delete=models.SET_NULL,
        help_text=_("this join request is linked to this Ocp Exchange"))

    """notes = models.CharField(_('request notes'),
        max_length=255, null=True, blank=True)"""

    def fobi_slug(self):
      if self.project.fobi_slug:
        return self.project.fobi_slug
      return False

    def __str__(self):
        return self.name+":"+self.state

    def form_prefix(self):
        return "".join(["JR", str(self.id)])

    def full_name(self):
        if self.surname:
            answer = " ".join([self.name, self.surname])
        else:
            answer = self.name
        return answer

    def agent_type(self):
        if self.type_of_user == "individual":
            answer = AgentType.objects.individual_type()
        else:
            answer = None
        return answer

    def agent_form(self):
        from work.forms import ProjectAgentCreateForm
        init = {
            "name": self.full_name(),
            "nick": self.requested_username,
            "email": self.email_address,
            }
        agent_type = self.agent_type()
        if agent_type:
            init["agent_type"] = agent_type
        return ProjectAgentCreateForm(initial=init, prefix=self.form_prefix())

    def agent_relation(self):
        if self.agent and self.project:
            aas = self.agent.is_associate_of.filter(has_associate=self.project.agent)
            if len(aas) == 1:
                return aas[0]
            else:
                for aa in aas:
                    if aa.association_type.association_behavior == 'manager':
                        return aa
                return 'Error'
        return None

    def agent_shares_account(self):
        agshac = None
        shrtyp = self.payment_account_type()
        if self.agent and shrtyp:
            agshac = self.agent.owned_resource_of_type(shrtyp)
        return agshac

    def fobi_items_keys(self):
        fobi_headers = []
        fobi_keys = []
        if self.fobi_data and self.fobi_data.pk:
            self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
            if not self.entries:
                loger.debug("++ jnreq:"+str(self.id)+" has no fobi entries ?? ++")
                return fobi_keys
            entry = self.entries[0]
            form_headers = json.loads(entry.form_data_headers)
            for elem in self.fobi_data.form_entry.formelemententry_set.all().order_by('position'):
                if not elem.plugin_data:
                    continue
                data = json.loads(elem.plugin_data)
                nam = data.get('name')
                if nam:
                    if not nam in form_headers:
                        form_headers[nam] = data.get('label')
                    if not form_headers[nam] in fobi_headers:
                        fobi_headers.append(form_headers[nam])
                    if not nam in fobi_keys:
                        fobi_keys.append(nam)
                else:
                    pass
            self.form_headers = fobi_headers
        return fobi_keys

    def fobi_items_data(self):
        self.items_data = None
        if self.fobi_data and self.fobi_data.pk:
            self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
            if self.entries:
                entry = self.entries[0]
                self.data = json.loads(entry.saved_data)
                self.items = self.data.items()
                self.items_data = []
                for key in self.fobi_items_keys():
                    self.items_data.append(self.data.get(key))
        return self.items_data

    def payment_regularity(self):
        if not self.project.joining_style == 'subscription':
            return None
        answer = {}
        data2 = None
        if self.project.is_moderated() and self.fobi_data:
            for key in self.fobi_items_keys():
                if key == "regularity": # fieldname specially defined in the fobi form
                    self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
                    entry = self.entries[0]
                    self.data = json.loads(entry.saved_data)
                    val = self.data.get(key)
                    #import pdb; pdb.set_trace()
                    answer['val'] = val
                    for elem in self.fobi_data.form_entry.formelemententry_set.all(): #filter(plugin_data_en__isnull=False):
                        data2 = json.loads(elem.plugin_data)
                        nam = data2.get('name')
                        if nam == key:
                          choi = data2.get('choices') # works with radio or select
                          if choi:
                            opts = choi.split('\r\n')
                            for op in opts:
                                opa = op.split(',')
                                #print('op:'+op)
                                if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                    answer['key'] = opa[0].strip()
                          else:
                            raise ValidationError("The regularity field has no choices? "+str(data2))
                        if not 'key' in answer and hasattr(elem, 'plugin_data_en'):
                            #print("not key? "+str(elem.plugin_data_en))
                            data3 = json.loads(elem.plugin_data_en)
                            nam = data3.get('name')
                            if nam == key:
                              choi = data3.get('choices') # works with radio or select
                              if choi:
                                opts = choi.split('\r\n')
                                for op in opts:
                                    opa = op.split(',')
                                    #print('op1:'+op)
                                    if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                        answer['key'] = opa[0].strip()
                              else:
                                raise ValidationError("The regularity field has no choices 2? "+str(data3))
                        if not 'key' in answer and hasattr(elem, 'plugin_data_es'):
                            #print("not key? "+str(elem.plugin_data_en))
                            data4 = json.loads(elem.plugin_data_es)
                            nam = data4.get('name')
                            if nam == key:
                              choi = data4.get('choices') # works with radio or select
                              if choi:
                                opts = choi.split('\r\n')
                                for op in opts:
                                    opa = op.split(',')
                                    #print('op1:'+op)
                                    if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                        answer['key'] = opa[0].strip()
                              else:
                                raise ValidationError("The regularity field has no choices 3? "+str(data4))
                        #print('answer:'+str(answer))

                    if 'key' not in answer:
                        raise ValidationError("can't find the regularity key! answer: "+str(data2)+' val: '+val)
            if 'key' not in answer or 'val' not in answer:
                print("Can't find the regularity key! answer: "+str(answer)+" keys:"+str(self.fobi_items_keys()))
                loger.warning("Can't find the regularity key! answer: "+str(answer)+" keys:"+str(self.fobi_items_keys()))
                #pass #raise ValidationError("can't find the payment_option key! data2: "+str(data2)) #answer key: "+str(answer['key'])+' val: '+str(answer['val'])+" for jn_req: "+str(self))
        return answer

    def pending_shares(self): # also used for subscriptions
        answer = ''
        account_type = self.payment_account_type()
        #balance = 0
        amount = self.payment_amount()

        balance = self.total_shares()
        subrt = self.subscription_rt()
        if subrt and not balance:
            pendpay = self.pending_payments()
            if pendpay == 0:
                balance = amount

        #import pdb; pdb.set_trace()
        if amount:
            answer = amount - balance
            if answer > 0:
                return int(answer)
            else:
                #import pdb; pdb.set_trace()
                return 0

        return False #'??'

    def total_shares(self):
        account_type = self.payment_account_type() #None
        balance = 0

        if self.agent and account_type:
            arrs = self.agent.resource_relationships()
            user_rts = list(set([arr.resource.resource_type for arr in arrs]))
            for rt in user_rts:
                if rt == account_type: #.ocp_artwork_type:
                    rss = list(set([arr.resource for arr in arrs]))
                    for rs in rss:
                        if rs.resource_type == rt:
                            balance = int(rs.price_per_unit) # TODO: update the price_per_unit with wallet balance
        return balance

    def pending_payments(self):
        amount = self.payment_amount()
        if self.agent:
          if self.project.joining_style == 'subscription':
            subrt = self.project.subscription_rt()
            arrs = self.agent.resource_relationships()
            user_rts = list(set([arr.resource.resource_type for arr in arrs]))
            for rt in user_rts:
                if rt == subrt: #.ocp_artwork_type:
                    rss = list(set([arr.resource for arr in arrs]))
                    for rs in rss:
                        if rs.resource_type == rt:
                            expires = rs.expiration_date
                            today = datetime.date.today()
                            if expires:
                                if today >= expires:
                                    return amount
                                else:
                                    return 0
          else:
            return self.pending_shares()
        return amount


    def subscription_resource(self):
        if self.project.joining_style == 'subscription':
            subrt = self.project.subscription_rt()
            if self.agent:
                agsubres = self.agent.owned_resource_of_type(subrt)
                if agsubres:
                    return agsubres
        return None


    def multiwallet_user(self, username=None):
        answer = ''
        mkey = "multiwallet_username" # fieldname specially defined in the fobi form

        if self.project.is_moderated() and self.fobi_data and self.project.agent.need_multicurrency():
            self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
            entry = self.entries[0]
            self.data = json.loads(entry.saved_data)
            if mkey in self.data:
                answer = self.data.get(mkey)
            #import pdb; pdb.set_trace()
            if username:
                if not username == answer:
                    if self.fobi_data.pk:
                        self.data[mkey] = username
                        entry.saved_data = json.dumps(self.data)

                        headers = json.loads(entry.form_data_headers)
                        if not mkey in headers:
                            #print("Update fobi header! "+mkey+": "+username)
                            loger.warning("Update fobi header! "+mkey+": "+username)
                            for elm in entry.form_entry.formelemententry_set.all():
                                pdata = json.loads(elm.plugin_data)
                                if mkey == pdata['name']:
                                    headers[mkey] = pdata['label']
                        entry.form_data_headers = json.dumps(headers)
                        entry.save()
                        answer = username
        return answer

    def multiwallet_auth(self): # not used yet, is for checking payments via botc-wallet (which requires auth) but still not works so step back to blockchain.com json service.
        auth = None
        if self.project.agent.need_multicurrency() and self.agent:
            if 'multicurrency' in settings.INSTALLED_APPS:
                from multicurrency.models import MulticurrencyAuth
                try:
                    oauths = MulticurrencyAuth.objects.filter(agent=self.agent)
                except MulticurrencyAuth.DoesNotExist:
                    raise PermissionDenied
                if len(oauths) > 1:
                    print("More than one oauth for this agent! return only the first. Agent:"+str(self.agent))
                    loger.warning("More than one oauth for this agent! return only the first. Agent:"+str(self.agent))
                if oauths:
                    auth = oauths[0]
                else:
                    print("Not found any oauth for agent: "+str(self.agent))
                    loger.error("Not found any oauth for agent: "+str(self.agent))
        return auth

    def payment_option(self):
        answer = {}
        #data2 = None
        if self.project.is_moderated() and self.fobi_data:
            for key in self.fobi_items_keys():
                if key == "payment_mode": # fieldname specially defined in the fobi form
                    self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
                    entry = self.entries[0]
                    self.data = json.loads(entry.saved_data)
                    val = self.data.get(key)
                    #import pdb; pdb.set_trace()
                    answer['val'] = val
                    #answer['key'] = key
                    for elem in self.fobi_data.form_entry.formelemententry_set.all(): #filter(plugin_data_en__isnull=False):
                        data2 = json.loads(elem.plugin_data)
                        nam = data2.get('name')
                        if nam == key:
                          choi = data2.get('choices') # works with radio or select
                          if choi:
                            opts = choi.split('\r\n')
                            for op in opts:
                                opa = op.split(',')
                                #print('op:'+op)
                                if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                    answer['key'] = opa[0].strip()
                          else:
                            raise ValidationError("The payment mode field has no choices? "+str(data2))
                        if not 'key' in answer:
                            #print("Can't find payment mode key in elem.plugin_data, try langs....")
                            plugdata = None
                            for lan in settings.LANGUAGES:
                                if hasattr(elem, 'plugin_data_'+lan[0]):
                                    plugdata = getattr(elem, 'plugin_data_'+lan[0])
                                    if not plugdata:
                                        continue
                                    data3 = json.loads(plugdata)
                                    nam = data3.get('name')
                                    if nam == key:
                                      choi = data3.get('choices') # works with radio or select
                                      if choi:
                                        opts = choi.split('\r\n')
                                        for op in opts:
                                            opa = op.split(',')
                                            #print('op1:'+op)
                                            if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                                answer['key'] = opa[0].strip()
                                                break
                                      else:
                                        raise ValidationError("The payment mode field has no choices 2? "+str(data3))
                                    if 'key' in answer:
                                        break


                            """
                                #loger.info("found1 elem.plugin_data_CA: ") #+str(plugdata))
                            elif hasattr(elem, 'plugin_data_es') and elem.plugin_data_es:
                                plugdata = elem.plugin_data_es
                                #loger.info("found1 elem.plugin_data_ES: ") #+str(plugdata))
                            elif hasattr(elem, 'plugin_data_en') and elem.plugin_data_en:
                                plugdata = elem.plugin_data_en
                                #loger.info("found1 elem.plugin_data_EN: ") #+str(plugdata))
                            else:
                                raise ValidationError("Can't find translations of plugin_data for elem: "+str(elem))
                            #print("not key? "+str(elem.plugin_data_en)) """


                        """if not answer.has_key('key'):
                            loger.info("Can't find payment mode key in elem.plugin_data in second round try third ...")
                            plugdata = None
                            if hasattr(elem, 'plugin_data_en') and elem.plugin_data_en:
                                plugdata = elem.plugin_data_en
                                #loger.info("found2 elem.plugin_data_EN: ") #+str(plugdata))
                            elif hasattr(elem, 'plugin_data_es') and elem.plugin_data_es:
                                plugdata = elem.plugin_data_es
                                #loger.info("found2 elem.plugin_data_ES: ") #+str(plugdata))
                            elif hasattr(elem, 'plugin_data_ca') and elem.plugin_data_ca:
                                plugdata = elem.plugin_data_ca
                                #loger.info("found2 elem.plugin_data_CA: ") #+str(plugdata))
                            else:
                                raise ValidationError("Can't find translations of plugin_data for elem: "+str(elem))
                            #print("not key? "+str(elem.plugin_data_en))
                            data3 = json.loads(plugdata)
                            nam = data3.get('name')
                            if nam == key:
                              choi = data3.get('choices') # works with radio or select
                              if choi:
                                opts = choi.split('\r\n')
                                for op in opts:
                                    opa = op.split(',')
                                    #print('op1:'+op)
                                    if val.strip() == opa[1].strip() or val.strip() == opa[0].strip():
                                        answer['key'] = opa[0].strip()
                              else:
                                raise ValidationError("The payment mode field has no choices 3? "+str(data3))
                        #print('answer:'+str(answer))"""


                    if 'key' not in answer:
                        raise ValidationError("can't find the payment_mode key! data3: "+str(data3)+' val: '+val)
            if 'key' not in answer or 'val' not in answer:
                #print("Can't find the payment_mode key! answer: "+str(answer)+" keys:"+str(self.fobi_items_keys()))
                #loger.warning("Can't find the payment_mode key! answer: "+str(answer)+" keys:"+str(self.fobi_items_keys()))
                pass #raise ValidationError("can't find the payment_option key! data2: "+str(data2)) #answer key: "+str(answer['key'])+' val: '+str(answer['val'])+" for jn_req: "+str(self))
        return answer

    def share_price(self):
        shrtyp = self.project.shares_type()
        if shrtyp:
            price = shrtyp.price_per_unit
            unit = shrtyp.unit_of_price
            requnit = self.payment_unit()
            amount = price
            if not requnit == unit and price and requnit:
                #from work.utils import remove_exponent
                if hasattr(self, 'ratio'):
                    amount = price / self.ratio
                    #print("using CACHED ratio at share_price!")
                    #loger.warning("using CACHED ratio at share_price!")
                else:
                    from work.utils import convert_price
                    amount, ratio = convert_price(price, unit, requnit, self)
                    self.ratio = ratio
                amount = amount.quantize(settings.DECIMALS)
            if not amount == price:
                pass #print("Changed the price!")
            return amount
        return False

    def show_share_price(self):
        unit = self.payment_unit()
        txt = str(self.share_price())+" "
        if unit.symbol:
            txt += unit.symbol
        else:
            txt += unit.abbrev
        return txt

    def total_price(self):
        #decimal.getcontext().prec = settings.CRYPTO_DECIMALS
        unit = self.payment_unit()
        shtype = self.project.shares_type()
        if shtype:
            shunit = shtype.unit_of_price
            shprice = shtype.price_per_unit
            amount = amountpay = self.payment_amount() * shprice
        else:
            shunit = self.subscription_unit()
            amount = amountpay = self.payment_amount()
        if not unit == shunit and amount: #unit.abbrev == 'fair':
            #amountpay = round(decimal.Decimal(self.payment_amount() * self.share_price()), 10)
            from work.utils import convert_price, remove_exponent
            amountpay, ratio = convert_price(amount, shunit, unit, self)
            self.ratio = ratio
            amountpay = remove_exponent(amountpay)
        return amountpay

    def show_total_price(self):
        txt = str(self.total_price())+' '+self.show_payment_unit()
        if self.is_flexprice():
            txt = '\u2248 '+txt
        return txt

    def payment_url(self):
        payopt = self.payment_option()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj:
                if 'url' in obj:
                    return obj['url']
        return False

    def payment_gateway(self):
        url = self.payment_url()
        if url:
            arr = url.split('/')
            if len(arr) > 2:
                return arr[2]

        popt = self.payment_option()
        if popt and 'key' in popt:
            return popt['key']
        return None

    def payment_margin(self):
        payopt = self.payment_option()
        margin = Decimal("0.0")
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    print("WARN Can't find the key '"+str(payopt['key'])+"' in PAYMENT_GATEWAYS object for slug "+str(self.project.fobi_slug))
                    loger.info("WARN Can't find the key '"+str(payopt['key'])+"' in PAYMENT_GATEWAYS object for slug "+str(self.project.fobi_slug))
                    pass
                if obj and 'margin' in obj:
                    margin = Decimal(obj['margin'])
        return margin

    def payment_html(self):
        payopt = self.payment_option()
        fairrs = None
        if self.agent:
            fairrs = self.agent.faircoin_resource()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    print("WARN Can't find the key '"+str(payopt['key'])+"' in PAYMENT_GATEWAYS object for slug "+str(self.project.fobi_slug))
                    loger.info("WARN Can't find the key '"+str(payopt['key'])+"' in PAYMENT_GATEWAYS object for slug "+str(self.project.fobi_slug))
                    pass
            if obj and obj['html']:
                if payopt['key'] == 'faircoin':
                  balance = 0
                  txt = ''
                  amount = None
                  if self.project.agent.need_faircoins():
                    if not self.agent:
                        txt = str(_("Once you log in and change your password, you'll be able to top-up your internal Faircoin account and proceed to pay the membership shares."))
                        return txt

                    addr = self.agent.faircoin_address()
                    wallet = WALLET
                    price = faircoin_utils.share_price_in_fairs(self)
                    amount = decimal.Decimal(self.pending_shares() * price)
                    amopend = decimal.Decimal(self.payment_pending_amount())
                    netfee = faircoin_utils.network_fee_fairs()

                    if fairrs:
                      if addr:
                        if not addr == "address_requested":
                          if wallet:
                            is_wallet_address = faircoin_utils.is_mine(addr)
                            if is_wallet_address:
                              balance = fairrs.faircoin_address.balance()
                              if balance != None:
                                if round(balance, settings.CRYPTO_DECIMALS) < round(amopend, settings.CRYPTO_DECIMALS):
                                    txt = '<b>'+str(_("Your ocp faircoin balance is not enough to pay this shares, still missing: %(f)s <br/>"
                                                      +" You can send them to your account %(ac)s and then pay the shares") %
                                                      {'f':"<span class='error'>"+str(round(decimal.Decimal(amopend - balance), settings.CRYPTO_DECIMALS))+" fair</span>", 'ac':' </b> '+addr+' <b> '})
                                elif amopend:
                                    txt = '<b>'+str(_("Your actual faircoin balance is enough. You can pay the shares now!"))
                                    txt += "</b> &nbsp;<a href='"+str(reverse('manage_faircoin_account', args=(fairrs.id,)))
                                    txt += "' class='btn btn-primary'>"+str(_("Faircoin account"))+"</a>"
                              else:
                                txt = str(_("Can't find the balance of your faircoin account:"))+' '+addr
                            else:
                              txt = str(_("The agent faircoin address is not from the same wallet!"))
                          else:
                            txt = str(_("The OCP wallet is not available now, try later."))
                        else:
                            txt = str(_("The account is requested and should be available in less than a minute... please refresh the page!"))
                      else:
                        txt = str(_("No faircoin address?"))
                    else:
                      txt = str(_("This agent don't have an OCP Faircoin Account yet."))

                    if not balance or not amount:
                      txt = "<span class='error'>"+txt+"</span>"

                    amtopay = "<br>"+str(_("Amount to pay"))+": <b> "+str(round(amount, settings.CRYPTO_DECIMALS))+" ƒ "
                    amispay = self.payment_payed_amount()
                    if amispay > 0:
                      if amopend:
                        amtopay += "- "+str(amispay)+" ƒ payed = "+str(round(amopend, settings.CRYPTO_DECIMALS))+' ƒ pending'
                      else:
                        amtopay += " ("+str(_("payed"))+" "+str(amispay)+" ƒ)"
                    amtopay += "</b>"

                    if not isinstance(obj['html'], str) and not isinstance(obj['html'], str):
                        html = obj['html']
                        html = str(html) #.decode('utf-8')
                    else:
                        html = obj['html']

                    return html+amtopay+"<br>"+txt

                  else:
                    # don't need internal faircoin
                    return obj['html']
                else:
                    return obj['html']
            else:
                print("There's no obj or 'html' obj key: "+str(obj))
                loger.info("There's no obj or 'html' obj key: "+str(obj))
        else:
            print("No settings obj gateways or no payment option: "+str(payopt))
            loger.info("No settings obj gateways or no payment option:, paypot: "+str(payopt))
        return False

    def payment_amount(self): # TODO rename to payment_shares
        amount = 0
        shat = self.project.shares_account_type()
        if self.project.is_moderated() and self.fobi_data:
          if shat:
            for key in self.fobi_items_keys():
                if key == shat.ocp_artwork_type.clas: # fieldname is the artwork type clas, project has shares of this type
                    self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
                    entry = self.entries[0]
                    self.data = json.loads(entry.saved_data)
                    val = self.data.get(key)
                    for elem in self.fobi_data.form_entry.formelemententry_set.all():
                        data = json.loads(elem.plugin_data)
                        choi = data.get('choices')
                        if choi:
                            opts = choi.split('\r\n')
                            for op in opts:
                                opa = op.split(',')
                                #import pdb; pdb.set_trace()
                                if type(val) is str and opa[1].encode('utf-8').strip() == val.encode('utf-8').strip():
                                    amount = int(opa[0])
                                    break
                        elif type(val) is int and val:
                            amount = val
                            break
                        elif type(val) is str and val:
                            amount = int(val)
                            break
          else:
            for key in self.fobi_items_keys():
                keyarr = key.split('_')
                if 'amount' in str(keyarr[0]): # fieldname specially defined for subscription amount and base currency
                    #shunit = Unit.objects.get(abbrev=keyarr[1])
                    self.entries = SavedFormDataEntry.objects.filter(pk=self.fobi_data.pk).select_related('form_entry')
                    entry = self.entries[0]
                    self.data = json.loads(entry.saved_data)
                    val = self.data.get(key)
                    if val:
                        if type(val) is int:
                            amount = val
                            break
                        elif type(val) is str:
                            amount = int(val)
                            break
                        else:
                            print("*?* type:"+str(type(val))+" val:"+str(val))
                            loger.warning("*?* type:"+str(type(val))+" val:"+str(val))
                    else:
                        print("*?* no val for 'amount'? data:"+str(self.data))
                        loger.warning("*?* no val for 'amount'? data:"+str(self.data))
                else:
                    pass #print("keyarr[0]: "+str(keyarr[0]))
                    #import pdb; pdb.set_trace()
        return amount

    def payment_payed_amount(self):
        if hasattr(self, 'exchange') and self.exchange:
            txpay = self.exchange.txpay()
            if txpay:
                return txpay.actual_quantity()
            else:
                return 0
        else:
            return 0

    def payment_pending_amount(self):
        shares = self.payment_amount()
        unit = self.payment_unit()
        unit_rt = self.payment_unit_rt()
        shtype = self.project.shares_type()
        if shtype:
            shunit = shtype.unit_of_price
            amount2 = shtype.price_per_unit * self.pending_shares()
        else:
            shunit = self.subscription_unit()
            amount2 = self.pending_shares()
        amountpay = amount2
        if hasattr(self, 'pending_amount'):
            amountpay = self.pending_amount
            print("Using CACHED pending_amount!! "+str(amountpay))
            loger.info("Using CACHED pending_amount!! "+str(amountpay))
        else:
            if not shunit == unit and amount2 and unit: #unit.abbrev == 'fair':
                from work.utils import convert_price
                amountpay, ratio = convert_price(amount2, shunit, unit, self)
                self.ratio = ratio
                self.pending_amount = amountpay

        amispay = self.payment_payed_amount()
        pendamo = amountpay
        if shtype and amispay > 0 and amountpay:
            pendamo = decimal.Decimal(amountpay) - amispay
        if not pendamo or pendamo < 0:
            pendamo = 0
        return round(pendamo, settings.CRYPTO_DECIMALS)

    def payment_pending_to_pay(self):
        return round((self.pending_shares() * self.share_price()), settings.CRYPTO_DECIMALS)

    def subscription_unit(self):
        unit = None
        if self.project.joining_style == 'subscription':
          if not hasattr(self, 'subscript_unit'):
            for key in self.fobi_items_keys():
                keyarr = key.split('_')
                if keyarr[0] == 'amount': # fieldname specially defined for subscription amount and base currency
                    unit = Unit.objects.get(abbrev=keyarr[1])
            if not unit:
                print("ERROR: Subscription Unit not found!! keys: "+str(self.fobi_items_keys()))
                loger.error("ERROR: Subscription Unit not found!! keys: "+str(self.fobi_items_keys()))
            else:
                self.subscript_unit = unit
          else:
            unit = self.subscript_unit
        return unit

    def subscription_rt(self):
        return self.project.subscription_rt()

    def is_flexprice(self):
        unit = self.payment_unit()
        if unit and unit.abbrev in settings.CRYPTOS:
            return True
        return False

    def payment_account_type(self):
        account_type = None
        if self.project.is_moderated() and self.fobi_data:
            rts = self.project.rts_with_clas() #list(set([arr.resource.resource_type for arr in self.project.agent.resource_relationships()]))
            for rt in rts:
                if rt.ocp_artwork_type:
                    for key in self.fobi_items_keys():
                        if key == rt.ocp_artwork_type.clas: # fieldname is the artwork type clas, project has shares of this type
                            account_type = rt
        return account_type


    def payment_secret(self):
        payopt = self.payment_option()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj and 'secret' in obj:
                return obj['secret']
        return False

    def payment_tokenorder(self):
        payopt = self.payment_option()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj and 'tokenorder' in obj:
                return obj['tokenorder']
        return False

    def payment_algorithm(self):
        payopt = self.payment_option()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj and 'algorithm' in obj:
                return obj['algorithm']
        return False

    def payment_token(self):
        secret = self.payment_secret()
        email = self.email_address
        amount = self.pending_shares()

        order = self.payment_tokenorder()
        algor = self.payment_algorithm()
        orderr = order.split('+')
        strin = ''
        token_obj = False
        if len(orderr) > 2:
            for fld in orderr:
                if fld == 'secret':
                    strin += secret
                elif fld == 'email':
                    strin += email
                elif fld == 'amount':
                    strin += str(amount)

            if algor == 'bcrypt':
                import bcrypt
                #from passlib.hash import bcrypt
                #if isinstance(strin, str):
                #    strin = bytes(strin, 'utf-8')
                self.salt = bcrypt.gensalt(prefix=b"2a")
                token_obj = bcrypt.hashpw(strin.encode('utf-8'), self.salt)#, 'utf8') #bcrypt.hash(strin)
            else:
                raise ValidationError("Token hashing algorithm not implemented or not understood: "+algor)
        else:
            raise ValidationError("Token fields order below 3: "+str(len(orderr))+"  "+('+'.join(orderr)))

        return token_obj #.hexdigest()

    def payment_fees(self):
        payopt = self.payment_option()
        amount = self.payment_amount()
        fees = 0
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj and obj['fees']:
                percent = float(obj['fees']['percent'])
                fixed = float(obj['fees']['fixed'])
                unit = obj['fees']['unit']
                payer = obj['fees']['payer']

                if percent:
                    fees += amount * percent / 100

                # TODO check unit type of payment

                if fixed:
                    fees += fixed

        return fees

    def payment_fees_payer(self):
        payopt = self.payment_option()
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    pass
            if obj and obj['fees']:
                payer = obj['fees']['payer']
                if payer == 'user':
                    return self.agent
                elif payer == 'project':
                    return self.project.agent
        return None

    def payment_total_with_fees(self):
        return self.pending_shares() + self.payment_fees()

    def show_payment_unit(self):
        unit = self.payment_unit()
        txt = 'error'
        if unit.symbol:
            txt = unit.symbol
        else:
            txt = unit.abbrev
        return txt

    def payment_unit(self, askmargin=None):
        payopt = self.payment_option()
        unit = None
        obj = None
        if settings.PAYMENT_GATEWAYS and payopt:
            gates = settings.PAYMENT_GATEWAYS
            if self.project.fobi_slug and gates[self.project.fobi_slug]:
                try:
                    obj = gates[self.project.fobi_slug][payopt['key']]
                except:
                    raise ValidationError("Can't find a payment gateway for slug "+self.project.fobi_slug+" named "+str(payopt))
            else:
                raise ValidationError("Can't find payment gateways for slug "+self.project.fobi_slug)

            if obj:
                try:
                    unit = Unit.objects.get(abbrev=obj['unit'].lower())
                except:
                    raise ValidationError("Can't find the payment Unit with abbrev = "+obj['unit'].lower())
                if askmargin:
                    if 'margin' in obj and obj['margin']:
                        return unit, obj['margin']
                    else:
                        loger.error("Askmargin in payment_unit, but the margin is not set for currency: "+str(unit)+" at project: "+str(self.project.agent))
                        return unit, None
                        #raise ValidationError("To ask for a margin of amount repair it must be first defined in the project settings for this gateway.")
        if askmargin:
            return unit, None
        return unit

    def payment_unit_rt(self):
        unit = self.payment_unit()
        if not unit:
            return None
        elif not unit.gen_unit:
            raise ValidationError("The Unit has not any gen_unit: "+str(unit))
        unit_rts = EconomicResourceType.objects.filter(ocp_artwork_type__general_unit_type__id=unit.gen_unit.unit_type.id)
        if unit_rts:
            if len(unit_rts) > 1:
                if self.payment_gateway() == 'cash':
                    clas = '_cash'
                else:
                    clas = '_digital'
                try:
                    unit_rt = unit_rts.get(ocp_artwork_type__clas__contains=clas)
                except:
                    raise ValidationError("None of the unit_rts is related an ocp_artwork_type with a clas that contains '"+clas+"'!! rts:"+str(unit_rts))
            else:
                unit_rt = unit_rts[0]
        else:
            raise ValidationError("The unit is not related any resource type: "+str(unit.gen_unit.unit_type))
        return unit_rt


    def exchange_type(self):
        et = None
        recs = []
        if self.exchange:
            return self.exchange.exchange_type

        payopt = self.payment_option()
        rt = self.payment_account_type()
        if 'key' in payopt:
          if rt and rt.ocp_artwork_type:
            recordts = Ocp_Record_Type.objects.filter(
                ocpRecordType_ocp_artwork_type=rt.ocp_artwork_type.rel_nonmaterial_type,
                exchange_type__isnull=False)
            if not recordts:
                recordts = Ocp_Record_Type.objects.filter(
                    ocpRecordType_ocp_artwork_type=rt.ocp_artwork_type,
                    exchange_type__isnull=False)
            if len(recordts) > 0:
                for rec in recordts:
                    ancs = rec.get_ancestors(True,True)
                    if payopt['key'] == 'faircoin':
                        for an in ancs:
                            if an.clas == 'fair_economy':
                                recs.append(rec)
                    elif payopt['key'] in ('transfer','ccard','cash','debit','botcw'):
                        for an in ancs:
                            if an.clas == 'fiat_economy':
                                recs.append(rec)
                    elif payopt['key'] in settings.CRYPTOS:
                        for an in ancs:
                            if an.clas == 'crypto_economy':
                                recs.append(rec)
                    else:
                        raise ValidationError("Payment mode not known: "+str(payopt['key'])+" at JR:"+str(self.id)+" pro:"+str(self.project))
                if len(recs) > 1:
                    for rec in recs:
                        ancs = rec.get_ancestors(True,True)
                        for an in ancs:
                            if 'buy' == an.clas:
                                et = rec.exchange_type
                elif recs:
                    et = recs[0].exchange_type

                #import pdb; pdb.set_trace()
                if not et or not len(recs):
                    raise ValidationError("Can't find the exchange_type related the payment option: "+payopt['key']+" . The related account type ("+str(rt.ocp_artwork_type)+") has recordts: "+str(recordts))
            elif recordts:
                raise ValidationError("found ocp_record_type's ?? : "+str(recordts)) # pass #et = recordts[0].exchange_type
            else:
                pass #raise ValidationError("not found any ocp_record_type related: "+str(rt.ocp_artwork_type))
          else:
            if self.subscription_unit():
                rt = self.project.subscription_rt()
                if rt:
                    recordts = Ocp_Record_Type.objects.filter(
                        ocpRecordType_ocp_artwork_type=rt.ocp_artwork_type,
                        exchange_type__isnull=False)
                    if not recordts:
                        recordts = Ocp_Record_Type.objects.filter(
                            ocpRecordType_ocp_artwork_type=rt.ocp_artwork_type.rel_nonmaterial_type,
                            exchange_type__isnull=False)
                    if len(recordts) > 0:
                        for rec in recordts:
                            ancs = rec.get_ancestors(True,True)
                            if payopt['key'] == 'faircoin':
                                for an in ancs:
                                    if an.clas == 'fair_economy':
                                        recs.append(rec)
                            elif payopt['key'] in ('transfer','ccard','cash','debit','botcw'):
                                for an in ancs:
                                    if an.clas == 'fiat_economy':
                                        recs.append(rec)
                            elif payopt['key'] in settings.CRYPTOS:
                                for an in ancs:
                                    if an.clas == 'crypto_economy':
                                        recs.append(rec)
                            else:
                                raise ValidationError("Payment mode not known: "+str(payopt['key'])+" at JR:"+str(self.id)+" pro:"+str(self.project))
                        if len(recs) > 1:
                            for rec in recs:
                                ancs = rec.get_ancestors(True,True)
                                for an in ancs:
                                    if 'buy' == an.clas:
                                        et = rec.exchange_type
                        elif recs:
                            et = recs[0].exchange_type

                        #import pdb; pdb.set_trace()
                        if not et or not len(recs):
                            raise ValidationError("Can't find the exchange_type related the payment option: "+payopt['key']+" . The related account type ("+str(rt.ocp_artwork_type)+") has recordts: "+str(recordts))
                    elif recordts:
                        raise ValidationError("found ocp_record_type's ?? : "+str(recordts)) # pass #et = recordts[0].exchange_type
                    else:
                        pass
                else:
                    # not rt
                    return 'error'
            else:
                raise ValidationError("not rt or not rt.ocp_artwork_type : "+str(rt))
        else: # no payopt, can be if no payment defined
            pass #raise ValidationError("no payment option key? "+str(payopt))
        #et.crypto = self.crypto
        return et


    def create_exchange(self, notes=None, exchange=None):
        ex = None
        et = self.exchange_type()
        pro = self.project.agent
        dt = self.request_date
        ag = self.agent

        if et and pro and dt:
            if exchange:
                ex = exchange
            elif self.exchange:
                ex = self.exchange
            else:
                exs = Exchange.objects.exchanges_by_type(ag)
                ex = None
                oldet = None
                old_fdc_ets = ExchangeType.objects.filter(name='Membership Contribution')
                if old_fdc_ets:
                    oldet = old_fdc_ets[0]
                for e in exs:
                    if e.exchange_type == et:
                        ex = e
                        break
                    if oldet and e.exchange_type == oldet and self.project.fobi_slug == 'freedom-coop':
                        ex = e
                        loger.info("- FOUND old fdc et, use that exchange: "+str(ex))
                        break
                if ex:
                    print("- found old Exchange!! "+str(ex))
                    loger.info("- found old Exchange!! "+str(ex))
                else:
                    ex, created = Exchange.objects.get_or_create(
                        exchange_type=et,
                        context_agent=pro,
                        start_date=dt,
                        use_case=et.use_case,
                        supplier=pro,
                        customer=ag,
                    )
                    if created:
                        print("- created Exchange: "+str(ex))
                        loger.info("- created Exchange: "+str(ex))

                if ag and ag.user() and ag.user().user:
                    ex.created_by = ag.user().user
            if not ex.exchange_type == et:
                print("- Edited exchange exchange_type: "+str(ex.exchange_type)+" -> "+str(et))
                loger.info("- Edited exchange exchange_type: "+str(ex.exchange_type)+" -> "+str(et))
                ex.exchange_type = et
            if not ex.start_date == dt:
                print("- Edited exchange start_date: "+str(ex.start_date)+" -> "+str(dt))
                loger.info("- Edited exchange start_date: "+str(ex.start_date)+" -> "+str(dt))
                #ex.start_date = dt
            if not ex.created_date == dt:
                print("- Edited exchange created_date: "+str(ex.created_date)+" -> "+str(dt))
                loger.info("- Edited exchange created_date: "+str(ex.created_date)+" -> "+str(dt))
                #ex.created_date = dt
            ex.supplier = pro
            ex.customer = ag
            if not ex.use_case == et.use_case:
                print("- CHANGE exchange USE_CASE ? from "+str(ex.use_case)+" to "+str(et.use_case))
                loger.info("- CHANGE exchange USE_CASE ? from "+str(ex.use_case)+" to "+str(et.use_case))

            ex.name = ag.nick+' '+et.name
            ex.use_case = et.use_case
            ex.context_agent = pro

            if notes and not notes in ex.notes:
                ex.notes += notes

            ex.save()
            self.exchange = ex
            self.save()

            # create transfer types
            xt = ex.exchange_type
            tts = xt.transfer_types.all()
            if not tts:
                raise ValidationError("This exchange type has not transfer types: "+str(xt))
            elif len(tts) < 2:
                raise ValidationError("This exchange type has less than 2 transfer types: "+str(xt))

            #tt_share = tts.get(name__contains="Share")
            #tt_pay = tts.get(name__contains="Payment")

            xfers = ex.transfers.all()
            if len(xfers) < len(tts):
                for tt in tts:
                    xfer_name = tt.name
                    try:
                        xfer = xfers.get(transfer_type=tt)
                    except:
                        #if tt.is_reciprocal:
                        #    xfer_name = xfer_name + " from " + from_agent.nick
                        #else:
                        #    xfer_name = xfer_name + " of " + rt.name

                        xfer, created = Transfer.objects.get_or_create(
                            name=xfer_name,
                            transfer_type = tt,
                            exchange = ex,
                            context_agent = pro,
                            transfer_date = dt, #atetime.date.today(),
                        )
                        if created:
                            print("- created Transfer: "+str(xfer))
                            loger.info("- created Transfer: "+str(xfer))
                            if ag and ag.user() and ag.user().user:
                                xfer.created_by = ag.user().user
                        elif ag and ag.user() and ag.user().user:
                            xfer.edited_by = ag.user().user
                    if not xfer.name == xfer_name:
                        print("- fix tx name! "+str(xfer.name)+" -> "+str(xfer_name))
                        loger.info("- fix tx name! "+str(xfer.name)+" -> "+str(xfer_name))
                        xfer.name = xfer_name
                    coms = xfer.commitments.all()
                    evts = xfer.events.all()
                    if coms or evts:
                        print("WARN! - the tx has coms:"+str(len(coms))+" or has evts:"+str(len(evts)))
                        loger.info("WARN! - the tx:"+str(xfer.id)+" has coms:"+str(len(coms))+" or has evts:"+str(len(evts)))

                    xfer.save()
            elif xfers:
                for xf in xfers:
                    if not xf.transfer_type in tts:
                        coms = xf.commitments.all()
                        evts = xf.events.all()
                        # FdC migration
                        if xf.transfer_type.name == "Receive Membership Fee":
                            print("- Switch old xf.tt to paytt, xf:"+str(xf))
                            loger.info("- Switch old xf.tt to paytt, xf:"+str(xf))
                            paytt = tts.get(name__icontains="payment")
                            xf.transfer_type = paytt
                            xf.save()
                            continue
                        elif "Share" in xf.transfer_type.name:
                            print("- Switch old xf.tt to shrtt, xf:"+str(xf))
                            loger.info("- Switch old xf.tt to shrtt, xf:"+str(xf))
                            paytt = tts.get(name__icontains="payment")
                            for tt in tts:
                                if not tt == paytt: # must be shares tt
                                    shrtt = tt
                                    xf.transfer_type = shrtt
                                    xf.save()
                                    break
                            continue
                        else:
                            print("-WARNIN the transfer tt is not known to this ex? "+str(xf.transfer_type)+" coms:"+str(coms)+" evts:"+str(evts))
                            loger.info("-WARNIN the transfer tt is not known to this ex? "+str(xf.transfer_type)+" coms:"+str(coms)+" evts:"+str(evts))
                        if not evts and not coms:
                            print("- delete empty transfer: "+str(xf))
                            loger.info("- delete empty transfer: "+str(xf))
                            if xf.is_deletable():
                                xf.delete()
                        elif coms:
                            print("- the transfer has commitments!! TODO "+str(xf))
                            loger.info("- the transfer has commitments!! TODO "+str(xf))
                        elif evts:
                            for ev in evts:
                                print("- found event:"+str(ev.id)+" "+str(ev)+" to:"+str(ev.to_agent)+" from:"+str(ev.from_agent)+" ca:"+str(ev.context_agent)+" rs:"+str(ev.resource)+" rt:"+str(ev.resource_type)+" fairtx:"+str(ev.faircoin_transaction))
                                loger.info("- found event:"+str(ev.id)+" "+str(ev)+" to:"+str(ev.to_agent)+" from:"+str(ev.from_agent)+" ca:"+str(ev.context_agent)+" rs:"+str(ev.resource)+" rt:"+str(ev.resource_type)+" fairtx:"+str(ev.faircoin_transaction))

        return ex

    def create_subscription_resource(self):
        subrt = self.subscription_rt()
        #un = self.subscript_unit()
        role = AgentResourceRoleType.objects.get(is_owner=True, name_en="Owner")
        agsubres = self.subscription_resource()
        if not agsubres:
            agsubres, c = EconomicResource.objects.get_or_create(
                resource_type=subrt,
                identifier=subrt.name_en+" of "+self.agent.nick_en,
                quantity=1
            )
            if c:
                print("- created EconomicResource: "+str(agsubres))
                loger.info("- created EconomicResource: "+str(agsubres))
        agsubres.identifier = subrt.name_en+" of "+self.agent.nick_en
        agsubres.quantity = 1
        agsubres.unit_of_quantity = Unit.objects.get(name_en="Each")
        agsubres.expiration_date = datetime.date.today() + self.subscription_expiration_delta()
        agsubres.save()
        if role:
            rra, c = AgentResourceRole.objects.get_or_create(
                agent=self.agent,
                role = role,
                resource = agsubres
            )
            if c:
                print("- created AgentResourceRole: "+str(rra))
                loger.info("- created AgentResourceRole: "+str(rra))
            rra.is_contact = False
            rra.save()
        return agsubres


    def subscription_expiration_delta(self):
        delta = None
        regu = self.payment_regularity()
        if regu and regu['key']:
            if regu['key'] == 'month':
                delta = datetime.timedelta(days=30)
            elif regu['key'] == 'quarter':
                delta = datetime.timedelta(days=91)
            elif regu['key'] == 'semester':
                delta = datetime.timedelta(days=182)
            elif regu['key'] == 'year':
                delta = datetime.timedelta(days=365)
        if not delta:
            raise ValidationError("Can't build delta! "+str(regu))
        return delta

    def check_subscription_expiration(self):
        agsubres = self.subscription_resource()
        ex = self.exchange
        if agsubres and ex:
            print("------ check_subscription_expiration ("+self.agent.nick+" at "+self.project.agent.nick+") ------")
            expdt = agsubres.expiration_date
            today = datetime.date.today()
            if today >= expdt:
                coms = None
                txpay = ex.txpay()
                for tx in ex.transfers.all():
                    if tx == txpay:
                        coms = tx.commitments.all()
                        evts = tx.events.all()
                if coms:
                    comfils = []
                    for com in coms:
                        if com.fulfillment_events.all():
                            comfils.append(com)
                    #print("COMFILS: "+str(comfils))
                    if len(comfils) == len(coms):
                        newdate = expdt + self.subscription_expiration_delta()
                        et_give = EventType.objects.get(name="Give")
                        et_receive = EventType.objects.get(name="Receive")
                        newcom, c = Commitment.objects.get_or_create(
                            event_type = et_give,
                            commitment_date = newdate,
                            due_date = newdate, # + datetime.timedelta(days=7), # TODO custom process delaytime by project
                            resource_type = self.payment_unit_rt(), # shtype, #account_type,
                            exchange = ex,
                            transfer = txpay,
                            exchange_stage = ex.exchange_type,
                            context_agent = self.project.agent,
                            quantity = self.payment_pending_amount(),
                            unit_of_quantity = self.payment_unit(),
                            from_agent = self.agent,
                            to_agent = self.project.agent
                        )
                        if c:
                            print("- created Commitment: "+str(newcom))
                            loger.info("- created Commitment: "+str(newcom))

                        newcom2, c = Commitment.objects.get_or_create(
                            event_type = et_receive,
                            commitment_date = newdate,
                            due_date = newdate, # + datetime.timedelta(days=7), # TODO custom process delaytime by project
                            resource_type = self.payment_unit_rt(), # shtype, #account_type,
                            exchange = ex,
                            transfer = txpay,
                            exchange_stage = ex.exchange_type,
                            context_agent = self.project.agent,
                            quantity = self.payment_pending_amount(),
                            unit_of_quantity = self.payment_unit(),
                            from_agent = self.agent,
                            to_agent = self.project.agent
                        )
                        if c:
                            print("- created Commitment2: "+str(newcom2))
                            loger.info("- created Commitment2: "+str(newcom2))




    def update_payment_status(self, status=None, gateref=None, notes=None, request=None, realamount=None, txid=None):
        account_type = self.payment_account_type()
        balance = 0
        amount = self.payment_amount()
        unit, margin = self.payment_unit(True) # arg: ask unit margin to settings obj
        unit_rt = self.payment_unit_rt()
        subtyp = self.project.subscription_rt()
        shtype = self.project.shares_type()
        pendshrs = self.pending_shares()
        shrunit = None
        if account_type:
            shrunit = account_type.unit_of_price
        if shtype:
            shunit = shtype.unit_of_price
            amount2 = shtype.price_per_unit * pendshrs
            if not pendshrs:
                amount2 = 0
        elif subtyp:
            shunit = self.subscription_unit()
            amount2 = amount
            shtype = subtyp
            shrunit = Unit.objects.get(name_en="Each")

        if not shunit:
            raise ValidationError("Can't find the unit_of_price of the project share type or subscription! pro: "+str(self.project))

        amountpay = amount2

        pendamo = self.payment_pending_amount()

        if not txid:
            from work.utils import convert_price
            if not shunit == unit and amount2: #unit.abbrev == 'fair':
                amountpay, ratio = convert_price(amount2, shunit, unit, self)
                self.ratio = ratio
            if not amountpay:
                amountpay, ratio = convert_price(amount, shunit, unit, self)
                self.ratio = ratio

            if amount2 and status == 'pending':
              if not amount == amountpay:
                print("Repair amount! "+str(amount)+" -> "+str(amount2)+" -> "+str(amountpay))
                loger.info("Repair amount! "+str(amount)+" -> "+str(amount2)+" -> "+str(amountpay))
                #raise ValidationError("Can't deal yet with partial payments... "+str(amount)+" <> "+str(amount2)+" amountpay:"+str(amountpay))
                #amount = amountpay
            elif not amount2 and status == 'complete':
                print("No pending shares but something is missing, recheck! "+str(self))
                loger.info("No pending shares but something is missing, recheck! "+str(self))

            if not pendamo == amountpay:
                print("WARN diferent amountpay:"+str(amountpay)+" and pendamo:"+str(pendamo)+" ...which is better? jr:"+str(self.id))
                loger.info("WARN diferent amountpay:"+str(amountpay)+" and pendamo:"+str(pendamo)+" ...which is better? jr:"+str(self.id))
        if realamount:
            if isinstance(realamount, str) or isinstance(realamount, str):
                if ',' in realamount:
                    realamount = realamount.replace(',', '.')
            realamount = decimal.Decimal(realamount)
            amountpay = realamount

        if status:
            if self.agent:
                user = None
                if self.agent.user():
                    user = self.agent.user().user
                agshac = self.agent_shares_account()
                agsubac = self.subscription_resource()
                shtotal = self.total_shares()
                pendshr = self.pending_shares()
                #shrunit = account_type.unit_of_price
                if not agshac and subtyp: # is subscription
                    if agsubac: # agent already has the subscres
                        pass #agshac = agsubac

                    elif status == 'complete' or status == 'published':
                        agsubac = self.create_subscription_resource()
                        #agshac = agsubac

                    shtotal = 1
                    pendshr = 1
                    amount = 1

                if not self.exchange:
                    ex = self.create_exchange(notes)
                    #raise ValidationError("The exchange has been created? "+str(ex))
                    #return HttpResponse('error')
                else:
                    ex = self.exchange


                et_give = EventType.objects.get(name="Give")
                et_receive = EventType.objects.get(name="Receive")

                xfers = ex.transfers.all()
                tts = ex.exchange_type.transfer_types.all()
                if len(xfers) < len(tts):
                    print("WARNING, some transfers are missing! repair? ")
                    loger.warning("WARNING, some transfers are missing! repair? ")
                    return False

                xfer_pay = None
                xfer_share = None
                try:
                    xfer_pay = xfers.get(transfer_type__is_currency=True)
                except:
                    raise ValidationError("Can't get a transfer type with is_currency in the exchange: "+str(ex)+" xfers:"+str(xfers))
                try:
                    xfer_share = xfers.get(transfer_type__inherit_types=True) #exchange_type__ocp_record_type__ocpRecordType_ocp_artwork_type__resource_type__isnull=False)
                except:
                    raise ValidationError("Can't get a transfer type related shares in the exchange: "+str(ex)+" xfers:"+str(xfers))

                if xfer_pay:
                    xfer_pay.notes += str(datetime.date.today())+' '+str(self.payment_gateway())+': '+status+'. '
                    xfer_pay.save()

                msg = ''
                if amount and xfer_pay:
                    evts = xfer_pay.events.all()
                    coms = xfer_pay.commitments.all()
                    commit_pay = None
                    commit_pay2 = None
                    if len(coms):
                        # if has various commitments? TODO
                        commit_pay = coms[0]
                        if len(coms) > 1 and coms[1]:
                          commit_pay2 = coms[1]
                        if not commit_pay2:
                          commit_pay2 = commit_pay

                    if status == 'complete' or status == 'published':

        #       C O M P L E T E

                        if len(evts) and not subtyp:
                            if txid:
                                pass #raise ValidationError("complete with txid a xfer_pay with existent events?? evts:"+str(evts))
                            print("The payment transfer already has events! "+str(len(evts)))
                            loger.warning("The payment transfer already has events! "+str(len(evts)))
                            for evt in evts:
                                if evt.event_type == et_give:
                                    fairtx = None
                                    if hasattr(evt, 'faircoin_transaction') and evt.faircoin_transaction:
                                        fairtx = evt.faircoin_transaction.id
                                    print("...repair event? qty:"+str(evt.quantity)+" tx:"+str(evt.transfer.name)+" rt:"+str(evt.resource_type)+" ca:"+str(evt.context_agent)+" from:"+str(evt.from_agent)+" to:"+str(evt.to_agent))
                                    print("...amountpay:"+str(amountpay)+" unitofqty:"+str(evt.unit_of_quantity)+" fairtx:"+str(fairtx)+" rs:"+str(evt.resource))
                                    if not evt.quantity and amountpay and not fairtx and evt.transfer == xfer_pay:
                                        print("CHANGED evt:"+str(evt.id)+" qty:0 to "+str(amountpay))
                                        loger.info("CHANGED evt:"+str(evt.id)+" qty:0 to "+str(amountpay))
                                        evt.quantity = amountpay
                                        evt.save()
                                if txid and evt.unit_of_quantity.is_currency():
                                    print("Transfer with a txid, REPAIR? unit:"+unit.abbrev+" project:"+self.project.agent.nick)
                                    loger.info("Transfer with a txid, REPAIR? unit:"+unit.abbrev+" project:"+self.project.agent.nick)
                                    if margin and pendamo and pendamo > margin:
                                        print("The pending amount is larger than the defined margin! Can't repair the found event. pendamo:"+str(pendamo))
                                        loger.warning("The pending amount is larger than the defined margin! Can't repair the found event. pendamo:"+str(pendamo)+" evt:"+str(evt))
                                        messages.error(request, "The pending amount is larger than the defined margin! Can't repair the found event...")
                                        return False
                                    if unit.abbrev == "fair" and self.project.agent.nick == "BotC":
                                        if hasattr(evt, 'multiwallet_transaction'):
                                            tx = evt.multiwallet_transaction
                                        else:
                                            from multicurrency.models import MultiwalletTransaction
                                            tx, created = MultiwalletTransaction.objects.get_or_create(
                                                tx_id = txid,
                                                event = evt)
                                            if created:
                                                print("- created MultiwalletTransaction (repair evt): "+str(tx))
                                                loger.info("- created MultiwalletTransaction (repair evt): "+str(tx))
                                        oauth = self.project.multiwallet_auth()
                                        msg = tx.update_data(oauth, request, realamount)
                                        if not msg == '':
                                            #tx.delete()
                                            messages.error(request, msg, extra_tags='safe')
                                            return False


                        elif amountpay and pendamo:
                            if subtyp:
                                commit_pays = coms.filter(fulfillment_events__isnull=True)
                                if commit_pays and len(commit_pays) == 2:
                                    for com in commit_pays:
                                        if com.event_type == et_give:
                                            commit_pay = com
                                        elif com.event_type == et_receive:
                                            commit_pay2 = com
                                else:
                                    print("There are no commitments to fulfill?")
                                    loger.info("There are no commitments to fulfill?")
                                    return False
                            event_res = event_res2 = None
                            if unit.abbrev == 'fair' and self.project.agent.need_faircoins():
                                if not self.agent.faircoin_resource() or not self.agent.faircoin_resource().faircoin_address.is_mine():
                                    print("The agent uses internal faircoins, but not agent fairaccount or is not mine, don't create events if unit is faircoin. SKIP! pro:"+str(self.project.agent))
                                    loger.info("The agent uses internal faircoins, but not agent fairaccount or is not mine, don't create events if unit is faircoin. SKIP! pro:"+str(self.project.agent))
                                    return False
                                else:
                                    event_res = self.agent.faircoin_resource()
                                    event_res2 = self.project.agent.faircoin_resource()
                            elif self.is_flexprice():
                                if txid:
                                    if 'multicurrency' in settings.INSTALLED_APPS:
                                        if unit.abbrev == "fair" and self.project.agent.nick == "BotC":
                                            from multicurrency.models import MultiwalletTransaction
                                        else:
                                            from multicurrency.models import BlockchainTransaction
                                    else:
                                        raise ValidationError("Can't manage blockchain txs without the multicurrency app installed!")
                                    if realamount:
                                        if not isinstance(realamount, decimal.Decimal):
                                            realamount = decimal.Decimal(realamount)
                                        amountpay = realamount
                                        gateref = txid
                                        if commit_pay:
                                            if not commit_pay.quantity == amountpay:
                                                print("Changed quantity of the payment commit_pay for the real amount! "+str(commit_pay.quantity)+" -> "+str(amountpay))
                                                loger.info("Changed quantity of the payment commit_pay for the real amount! "+str(commit_pay.quantity)+" -> "+str(amountpay))
                                            commit_pay.quantity = amountpay
                                            commit_pay.save()
                                        if commit_pay2 and not commit_pay2 == commit_pay:
                                            if not commit_pay2.quantity == amountpay:
                                                print("Changed quantity of the payment commit_pay2 for the real amount! "+str(commit_pay2.quantity)+" -> "+str(amountpay))
                                                loger.info("Changed quantity of the payment commit_pay2 for the real amount! "+str(commit_pay2.quantity)+" -> "+str(amountpay))
                                            commit_pay2.quantity = amountpay
                                            commit_pay2.save()
                                    else:
                                        print("Update payment for is_flexprice without the real_amount! "+str(self))
                                        loger.error("Update payment for is_flexprice without the real_amount! "+str(self))
                                        return False
                                else:
                                    print("Update payment for is_flexprice without a txid! "+str(self))
                                    loger.error("Update payment for is_flexprice without a txid! "+str(self))
                                    return False

                            evt, created = EconomicEvent.objects.get_or_create(
                                event_type = et_give,
                                event_date = datetime.date.today(),
                                resource_type = unit_rt,
                                resource = event_res,
                                transfer = xfer_pay,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = amountpay,
                                unit_of_quantity = unit,
                                #value = amount,
                                #unit_of_value = account_type.unit_of_price,
                                from_agent = self.agent,
                                to_agent = self.project.agent,
                                is_contribution = xfer_pay.transfer_type.is_contribution,
                                is_to_distribute = xfer_pay.transfer_type.is_to_distribute,
                                event_reference = gateref,
                                created_by = user,
                                commitment = commit_pay,
                                exchange = ex,
                            )
                            if created:
                                print(" created Event: "+str(evt))
                                loger.info(" created Event: "+str(evt))

                            if txid:
                                if unit.abbrev == "fair" and self.project.agent.nick == "BotC":
                                    tx, created = MultiwalletTransaction.objects.get_or_create(
                                        tx_id = txid,
                                        event = evt)
                                    if created:
                                        print("- created MultiwalletTransaction: "+str(tx))
                                        loger.info("- created MultiwalletTransaction: "+str(tx))
                                    oauth = self.project.multiwallet_auth()
                                    msg = tx.update_data(oauth, request, realamount)
                                    if not msg == '':
                                        tx.event.delete()
                                        tx.delete()
                                        if evt.id:
                                            evt.delete()
                                        messages.error(request, msg, extra_tags='safe')
                                        return False

                                else:
                                    tx, created = BlockchainTransaction.objects.get_or_create(
                                        tx_hash = txid,
                                        event = evt)
                                    if created:
                                        print("- created BlockchainTransaction: "+str(tx))
                                        loger.info("- created BlockchainTransaction: "+str(tx))
                                    msg = tx.update_data(realamount) #, self.multiwallet_auth())
                                    if not msg == '':
                                        tx.event.delete()
                                        tx.delete()
                                        if evt.id:
                                            evt.delete()
                                        messages.error(request, msg, extra_tags='safe')
                                        return False


                            evt2, created = EconomicEvent.objects.get_or_create(
                                event_type = et_receive,
                                event_date = datetime.date.today(),
                                resource_type = unit_rt,
                                resource = event_res2,
                                transfer = xfer_pay,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = amountpay,
                                unit_of_quantity = unit,
                                #value = amountpay,
                                #unit_of_value = unit,
                                from_agent = self.agent,
                                to_agent = self.project.agent,
                                is_contribution = xfer_pay.transfer_type.is_contribution,
                                is_to_distribute = xfer_pay.transfer_type.is_to_distribute,
                                event_reference = gateref,
                                created_by = user,
                                commitment = commit_pay2,
                                exchange = ex,
                            )
                            if created:
                                print(" created Event2: "+str(evt2))
                                loger.info(" created Event2: "+str(evt2))

                            if txid:
                                if unit.abbrev == "fair" and self.project.agent.nick == "BotC":
                                    tx2, created = MultiwalletTransaction.objects.get_or_create(
                                        tx_id = txid,
                                        event = evt2)
                                    if created:
                                        print("- created MultiwalletTransaction (evt2): "+str(tx2))
                                        loger.info("- created MultiwalletTransaction (evt2): "+str(tx2))
                                    oauth = self.project.multiwallet_auth()
                                    msg = tx2.update_data(oauth, request, realamount)
                                    if not msg == '':
                                        tx2.event.delete()
                                        tx2.delete()
                                        if evt2.id:
                                            evt2.delete()
                                        messages.error(request, msg, extra_tags='safe')
                                        return False
                                else:
                                    tx2, created = BlockchainTransaction.objects.get_or_create(
                                        tx_hash = txid,
                                        event = evt2)
                                    if created:
                                        print("- created BlockchainTransaction: "+str(tx2))
                                        loger.info("- created BlockchainTransaction: "+str(tx2))
                                    msg = tx2.update_data(realamount) #, self.multiwallet_auth())
                                    if not msg == '':
                                        tx2.event.delete()
                                        tx2.delete()
                                        if evt2.id:
                                            evt2.delete()
                                        messages.error(request, msg)
                                        return False

                        if xfer_share:
                            evts = xfer_share.events.all()
                            coms = xfer_share.commitments.all()
                            commit_share = None
                            commit_share2 = None
                            if len(coms):
                                # if has various commitments? TODO
                                commit_share = coms[0]
                                if len(coms) > 1 and coms[1]:
                                  commit_share2 = coms[1]
                                if not commit_share2:
                                  commit_share2 = commit_share
                        else:
                            print("ERROR: Can't find xfer_share!! "+str(self))
                            loger.error("ERROR: Can't find xfer_share!! "+str(self))
                            messages.error(request, "ERROR: Can't find xfer_share!! "+str(self))

                        # create commitments for shares
                        if not commit_share and self.pending_shares() and not evts:
                            commit_share, created = Commitment.objects.get_or_create(
                                event_type = et_give,
                                commitment_date = datetime.date.today(),
                                due_date = datetime.date.today(), # + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                resource_type = shtype, #account_type,
                                exchange = ex,
                                transfer = xfer_share,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = amount,
                                unit_of_quantity = shrunit,
                                #value = amountpay,
                                #unit_of_value = unit, #account_type.unit_of_price,
                                from_agent = self.project.agent,
                                to_agent = self.agent,
                                #description = description,
                                created_by = user,
                            )
                            if created:
                                print("- created Commitment:"+str(commit_share.id)+" "+str(commit_share))
                                loger.info("- created Commitment:"+str(commit_share.id)+" "+str(commit_share))

                            if not commit_share2:
                                commit_share2, created = Commitment.objects.get_or_create(
                                    event_type = et_receive,
                                    commitment_date = datetime.date.today(),
                                    due_date = datetime.date.today(), # + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                    resource_type = shtype, #account_type,
                                    exchange = ex,
                                    transfer = xfer_share,
                                    exchange_stage = ex.exchange_type,
                                    context_agent = self.project.agent,
                                    quantity = amount,
                                    unit_of_quantity = shrunit,
                                    #value = amount,
                                    #unit_of_value = account_type.unit_of_price,
                                    from_agent = self.project.agent,
                                    to_agent = self.agent,
                                    #description = description,
                                    created_by = user,
                                )
                                if created:
                                    print("- created Commitment2: "+str(commit_share2))
                                    loger.info("- created Commitment2: "+str(commit_share2))


                        if agsubac:
                            expdt = agsubac.expiration_date
                            delta = self.subscription_expiration_delta()
                            if datetime.date.today() > expdt:
                                agsubac.expiration_date = expdt + delta
                                agsubac.save()
                            agshac = agsubac

                        # create share events
                        if not evts and msg == '':
                          if self.pending_shares():
                            sh_evt, created = EconomicEvent.objects.get_or_create(
                                event_type = et_give,
                                event_date = datetime.date.today(),
                                resource_type = shtype, #account_type,
                                resource=agshac,
                                transfer = xfer_share,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = pendshr,
                                unit_of_quantity = shrunit,
                                #value = amountpay,
                                #unit_of_value = unit, #account_type.unit_of_price,
                                from_agent = self.project.agent,
                                to_agent = self.agent,
                                is_contribution = xfer_share.transfer_type.is_contribution,
                                is_to_distribute = xfer_share.transfer_type.is_to_distribute,
                                #event_reference = gateref,
                                created_by = user,
                                commitment = commit_share,
                                exchange = ex,
                            )
                            if created:
                                print("- created Event: "+str(sh_evt))
                                loger.info("- created Event: "+str(sh_evt))

                            sh_evt2, created = EconomicEvent.objects.get_or_create(
                                event_type = et_receive,
                                event_date = datetime.date.today(),
                                resource_type = shtype, #account_type,
                                resource=agshac,
                                transfer = xfer_share,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = pendshr,
                                unit_of_quantity = shrunit,
                                #value = amountpay,
                                #unit_of_value = unit, #account_type.unit_of_price,
                                from_agent = self.project.agent,
                                to_agent = self.agent,
                                is_contribution = xfer_share.transfer_type.is_contribution,
                                is_to_distribute = xfer_share.transfer_type.is_to_distribute,
                                #event_reference = gateref,
                                created_by = user,
                                commitment = commit_share2,
                                exchange = ex,
                            )
                            if created:
                                print("- created Event2: "+str(sh_evt2))
                                loger.info("- created Event2: "+str(sh_evt2))

                            # transfer shares
                            user_rts = list(set([arr.resource.resource_type for arr in self.agent.resource_relationships()]))
                            for rt in user_rts:
                                if rt == account_type: # match the account type to update the value
                                    rss = list(set([arr.resource for arr in self.agent.resource_relationships()]))
                                    for rs in rss:
                                        if rs.resource_type == rt:
                                            note = "Added "+str(amount)+" on "+str(datetime.date.today())+". "
                                            if rs.notes:
                                                rs.notes += note
                                            else:
                                                rs.notes = note
                                            rs.price_per_unit += sh_evt.quantity # update the price_per_unit with payment amount
                                            rs.save()
                                            print("Transfered new shares to the agent's shares account: "+str(sh_evt.quantity)+" "+str(rs))
                                            loger.info("Transfered new shares to the agent's shares account: "+str(sh_evt.quantity)+" "+str(rs))
                                            if request:
                                                messages.info(request, "Transfered new shares to the agent's shares account: "+str(sh_evt.quantity)+" "+str(rs))
                          else: # not pending_shares and not share events
                            date = agshac.created_date
                            print("No pending shares and no events related shares. REPAIR! total_shares:"+str(shtotal)+" date:"+str(date))
                            loger.info("No pending shares and no events related shares. REPAIR! total_shares:"+str(shtotal)+" date:"+str(date))

                            sh_evt, created = EconomicEvent.objects.get_or_create(
                                event_type = et_give,
                                event_date = date,
                                resource_type = shtype, #account_type,
                                resource = agshac,
                                transfer = xfer_share,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = shtotal,
                                unit_of_quantity = shrunit,
                                #value = amountpay,
                                #unit_of_value = unit, #account_type.unit_of_price,
                                from_agent = self.project.agent,
                                to_agent = self.agent,
                                is_contribution = xfer_share.transfer_type.is_contribution,
                                is_to_distribute = xfer_share.transfer_type.is_to_distribute,
                                #event_reference = gateref,
                                created_by = user,
                                commitment = commit_share,
                                exchange = ex,
                            )
                            if created:
                                print("- created missing shares Event: "+str(sh_evt))
                                loger.info("- created missing shares Event: "+str(sh_evt))

                            sh_evt2, created = EconomicEvent.objects.get_or_create(
                                event_type = et_receive,
                                event_date = date,
                                resource_type = shtype, #account_type,
                                resource = agshac,
                                transfer = xfer_share,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = shtotal,
                                unit_of_quantity = shrunit,
                                #value = amountpay,
                                #unit_of_value = unit, #account_type.unit_of_price,
                                from_agent = self.project.agent,
                                to_agent = self.agent,
                                is_contribution = xfer_share.transfer_type.is_contribution,
                                is_to_distribute = xfer_share.transfer_type.is_to_distribute,
                                #event_reference = gateref,
                                created_by = user,
                                commitment = commit_share2,
                                exchange = ex,
                            )
                            if created:
                                print("- created missing shares Event2: "+str(sh_evt2))
                                loger.info("- created missing shares Event2: "+str(sh_evt2))

                        elif not self.subscription_unit():
                            print("The shares transfer already has Events!! "+str(len(evts)))
                            loger.warning("The shares transfer already has Events!! "+str(len(evts)))
                            for ev in evts:
                                rt_u = ev.resource_type.ocp_artwork_type.general_unit_type.unit_set.first().ocp_unit
                                print("...repair shr_evt? "+str(ev.id)+" qty:"+str(ev.quantity)+" uq:"+str(ev.unit_of_quantity)+" / val:"+str(ev.value)+" uv:"+str(ev.unit_of_value)+" rt:"+str(ev.resource_type)+" rt_u:"+str(rt_u)+" from:"+str(ev.from_agent)+" to:"+str(ev.to_agent))
                                loger.info("...repair shr_evt? "+str(ev.id)+" qty:"+str(ev.quantity)+" uq:"+str(ev.unit_of_quantity)+" / val:"+str(ev.value)+" uv:"+str(ev.unit_of_value)+" rt:"+str(ev.resource_type)+" rt_u:"+str(rt_u)+" from:"+str(ev.from_agent)+" to:"+str(ev.to_agent))
                            return False


                        return True

                    elif status == 'pending':

        #        P E N D I N G

                        if not commit_pay and self.payment_pending_amount():
                            commit_pay, created = Commitment.objects.get_or_create(
                                event_type = et_give,
                                commitment_date = datetime.date.today(),
                                due_date = datetime.date.today() + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                resource_type = unit_rt,
                                exchange = ex,
                                transfer = xfer_pay,
                                exchange_stage = ex.exchange_type,
                                context_agent = self.project.agent,
                                quantity = amountpay,
                                unit_of_quantity = unit,
                                #value = amount,
                                #unit_of_value = account_type.unit_of_price,
                                from_agent = self.agent,
                                to_agent = self.project.agent,
                                #description = description,
                                created_by = user,
                            )
                            if created:
                                print("- created Commitment: "+str(commit_pay))
                                loger.info("- created Commitment: "+str(commit_pay))
                            if not commit_pay2:
                                commit_pay2, created = Commitment.objects.get_or_create(
                                    event_type = et_receive,
                                    commitment_date = datetime.date.today(),
                                    due_date = datetime.date.today() + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                    resource_type = unit_rt,
                                    exchange = ex,
                                    transfer = xfer_pay,
                                    exchange_stage = ex.exchange_type,
                                    context_agent = self.project.agent,
                                    quantity = amountpay,
                                    unit_of_quantity = unit,
                                    #value = amountpay,
                                    #unit_of_value = unit,
                                    from_agent = self.agent,
                                    to_agent = self.project.agent,
                                    #description = description,
                                    created_by = user,
                                )
                                if created:
                                    print("- created Commitment2: "+str(commit_pay2))
                                    loger.info("- created Commitment2: "+str(commit_pay2))

                        if xfer_share:
                            evts = xfer_share.events.all()
                            coms = xfer_share.commitments.all()
                            commit_share = None
                            commit_share2 = None
                            if len(coms):
                                # if has various commitments? TODO
                                commit_share = coms[0]
                                if len(coms) > 1 and coms[1]:
                                  commit_share2 = coms[1]
                                if not commit_share2:
                                  commit_share2 = commit_share

                            # create commitments for shares if payed
                            if not commit_share and not self.payment_pending_amount() and not evts:
                                commit_share, created = Commitment.objects.get_or_create(
                                    event_type = et_give,
                                    commitment_date = datetime.date.today(),
                                    due_date = datetime.date.today() + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                    resource_type = shtype, #account_type,
                                    exchange = ex,
                                    transfer = xfer_share,
                                    exchange_stage = ex.exchange_type,
                                    context_agent = self.project.agent,
                                    quantity = amount,
                                    unit_of_quantity = shrunit,
                                    #value = amountpay,
                                    #unit_of_value = unit,
                                    from_agent = self.project.agent,
                                    to_agent = self.agent,
                                    #description = description,
                                    created_by = user,
                                )
                                if created:
                                    print("- created Commitment: "+str(commit_share))
                                    loger.info("- created Commitment: "+str(commit_share))

                                if not commit_share2:
                                    commit_share2, created = Commitment.objects.get_or_create(
                                        event_type = et_receive,
                                        commitment_date = datetime.date.today(),
                                        due_date = datetime.date.today() + datetime.timedelta(days=7), # TODO custom process delaytime by project
                                        resource_type = shtype, #account_type,
                                        exchange = ex,
                                        transfer = xfer_share,
                                        exchange_stage = ex.exchange_type,
                                        context_agent = self.project.agent,
                                        quantity = amount,
                                        unit_of_quantity = shrunit,
                                        #value = amount,
                                        #unit_of_value = account_type.unit_of_price,
                                        from_agent = self.project.agent,
                                        to_agent = self.agent,
                                        #description = description,
                                        created_by = user,
                                    )
                                    if created:
                                        print("- created Commitment2: "+str(commit_share2))
                                        loger.info("- created Commitment2: "+str(commit_share2))

                        return True

                    else:
                        raise ValidationError("The status is not implemented: "+str(status))
                        #return False
                else:
                    raise ValidationError("There's not amount ("+str(amount)+") or xfer_pay? "+str(xfer_pay))
            else:
                raise ValidationError("The join request has no agent yet! ")
                #return False
        else:
            raise ValidationError("The update payment has no status! "+str(self))
            #return False

    def create_useragent_randompass(self, request=None, hash_func=hashlib.sha256):
        from work.forms import ProjectAgentCreateForm # if imported generally it breaks other imports, requires a deep imports rebuild TODO
        randpass = hash_func(str(random.SystemRandom().getrandbits(64))).hexdigest()[:settings.RANDOM_PASSWORD_LENGHT]

        at = None
        password = None
        name = self.name
        if self.type_of_user == 'individual':
            at = get_object_or_404(AgentType, party_type='individual', is_context=False)
            if self.surname:
                name += ' '+self.surname
        elif self.type_of_user == 'collective':
            at = get_object_or_404(AgentType, party_type='team', is_context=True)
        else:
            raise ValidationError("The 'type_of_user' field is not understood for this request: "+str(self))

        reqdata = {'name':name,
                   'email':self.email_address,
                   'nick':self.requested_username,
                   'password':randpass,
                   'agent_type':at.id,
        }

        form = ProjectAgentCreateForm(data=reqdata) #prefix=jn_req.form_prefix())
        if form.is_valid():
            data = form.cleaned_data
            agent = form.save(commit=False)
            try:
                if request.user.agent.agent:
                    agent.created_by=request.user
            except:
                pass
            if not agent.is_individual():
                agent.is_context=True

            # or import utils set_lang_defaults(agent) avoiding the circular import
            if not agent.name_en and agent.name:
                agent.name_en = agent.name
            if not agent.nick_en and agent.nick:
                agent.nick_en = agent.nick
            if not agent.email_en and agent.email:
                agent.email_en = agent.email
            if not agent.url_en and agent.url:
                agent.url_en = agent.url
            if not agent.phone_primary_en and agent.phone_primary:
                agent.phone_primary_en = agent.phone_primary
            if not agent.photo_url_en and agent.photo_url:
                agent.photo_url_en = agent.photo_url
            if not agent.address_en and agent.address:
                agent.address_en = agent.address

            agent.save()
            self.agent = agent
            self.save()
            project = self.project
            # add relation candidate
            if project.shares_account_type():
                ass_type = get_object_or_404(AgentAssociationType, identifier="member")
            else:
                ass_type = get_object_or_404(AgentAssociationType, identifier="participant")
            ass = AgentAssociation.objects.filter(is_associate=self.agent, has_associate=self.project.agent)
            if ass_type and not ass:
                aa = AgentAssociation(
                    is_associate=agent,
                    has_associate=project.agent,
                    association_type=ass_type,
                    state="potential",
                    )
                aa.save()
            password = data["password"]
            if password:
                username = data["nick"]
                email = data["email"]
                if username:
                    user = User(
                        username=username,
                        email=email,
                        )
                    user.set_password(password)
                    user.save()
                    au = AgentUser(
                        agent = agent,
                        user = user)
                    au.save()

                    name = data["name"]

                    con_typ = ContentType.objects.get(model='joinrequest')

                    comm = Comment(
                        content_type=con_typ,
                        object_pk=self.pk,
                        user_name=self.project.agent.nick,
                        user_email=self.project.agent.email,
                        submit_date=datetime.date.today(),
                        comment=_("%(pass)s is the initial random password for agent %(user)s, used to verify the email address %(mail)s") % {'pass': password, 'user': username, 'mail': email},
                        site=Site.objects.get_current()
                    )
                    comm.save()

                    if notification:
                        from work.utils import set_user_notification_by_type
                        sett = set_user_notification_by_type(agent.user().user, "work_new_account", True)
                        #managers = project.agent.managers()
                        users = [agent.user().user]
                        #for manager in managers:
                        #    if manager.user():
                        #        users.append(manager.user().user)
                        #users = User.objects.filter(is_staff=True)
                        if users:
                            site_name = project.agent.nick #get_site_name(request)
                            try:
                                notification.send_now(
                                    users,
                                    "work_new_account",
                                    {"name": name,
                                    "username": username,
                                    "password": password,
                                    "site_name": site_name,
                                    "context_agent": project.agent,
                                    "request_host": request.get_host(),
                                    "current_site": request.get_host(),
                                    }
                                )
                            except:
                                if request:
                                    messages.error(request, str(_("Email failed! The destination address seems not real (or there's another email error): "))+str(email))
                                loger.error("Email failed! The destination address seems not real (or there's another email error): "+str(email))

                                aa.delete()
                                self.agent = None
                                self.save()
                                au.delete()
                                comm.delete()
                                coms = Comment.objects.filter(object_pk=self.id)
                                if coms:
                                    for com in coms:
                                        pass #print("delete other comment? "+str(com))
                                        #com.delete()
                                if agent.user():
                                    if agent.user().user:
                                        print("x Deleted user: "+str(agent.user().user))
                                        if request and request.user.is_staff:
                                            messages.info(request, "x Deleted user: "+str(agent.user().user))
                                        agent.user().user.delete()
                                    else:
                                        print("there's no user? "+str(agent.user()))
                                else:
                                    usrs = User.objects.filter(email=email)
                                    if usrs:
                                        if len(usrs) > 1:
                                            print("WARN! There are multiple User's with the email: "+str(email)+" usrs:"+str(usrs))
                                            if request and request.user.is_staff:
                                                messages.info(request, "WARN! There are multiple User's with the email: "+str(email))
                                            for us in usrs:
                                                if us.username == self.requested_username:
                                                    #import pdb; pdb.set_trace()
                                                    if not hasattr(us, 'agent') or not us.agent:
                                                        print("DELETED user "+str(us))
                                                        if request and request.user.is_staff:
                                                            messages.info(request, "x Deleted one of the users: "+str(us))
                                                        us.delete()
                                                    else:
                                                        print("WARNING! the user has an agent? "+str(us.agent))
                                                else:
                                                    print("SKIP, User with same wrong email but different username: "+str(us))
                                                    if request:
                                                        messages.info(request, "SKIP! User with same wrong email but different username: "+str(us))
                                        else:
                                            usr = usrs[0]
                                            print("Delete this user? "+str(usr))
                                            if not hasattr(usr, 'agent') or not usr.agent:
                                                print("DELETED User "+str(usr))
                                                if request and request.user.is_staff:
                                                    messages.info(request, "x Deleted User: "+str(usr))
                                                usr.delete()
                                    else:
                                        print("There's no User with such email? ")

                                if agent.is_deletable():
                                    print("x Deleted agent: "+str(agent))
                                    if request and request.user.is_staff:
                                        messages.info(request, "x Deleted Agent: "+str(agent))
                                    agent.delete()
                                else:
                                    if request:
                                        messages.warning(request, _("The agent can't be deleted! ")+str(agent))

                                    raise ValidationError("agent cant be deleted: "+str(agent))

                                return None

                        else:
                            raise ValidationError("There are no users to send the work_new_account details? "+str(username))
                    else:
                        raise ValidationError("The notification service is not available?! ")
                else:
                    raise ValidationError("There's a problem with the username: "+str(username))
            else:
                raise ValidationError("There's some problem with the random password: "+str(password))
        else:
            raise ValidationError("The form to autocreate user+agent from the join request is not valid. "+str(form.errors))
        return password

    def check_user_pass(self, showpass=False):
        if hasattr(self, 'agent') and self.agent and self.agent.user():
          con_typ = ContentType.objects.get(model='joinrequest')
          coms = Comment.objects.filter(content_type=con_typ, object_pk=self.pk)
          for c in coms:
            first = c.comment.split(' ')[0]
            if len(first) == settings.RANDOM_PASSWORD_LENGHT:
                if self.agent.user().user.check_password(first):
                    if showpass:
                        return first
                    else:
                        return _("WARNING!")
        else:
            return _("ERROR!")
        return False

    def duplicated(self):
        if self.agent:
            reqs = JoinRequest.objects.filter(project=self.project, agent=self.agent)
            if len(reqs) > 1:
                for req in reqs:
                    if not req == self:
                        return req
            elif reqs:
                return False
            else:
                raise ValidationError("This join_request is wrong! id:"+str(self.id)+" req:"+str(self)+" ag:"+str(self.agent)+" pro:"+str(self.project))
        else:
            reqs = JoinRequest.objects.filter(project=self.project, requested_username=self.requested_username)
            if len(reqs) > 1:
                for req in reqs:
                    if not req == self:
                        return req
            elif reqs:
                return False
            else:
                raise ValidationError("This join_request is wrong! req:"+str(self.id)+" requested_username:"+str(self.requested_username)+" name:"+str(self.name)+" email:"+str(self.email_address)+" date:"+str(self.request_date)+" pro:"+str(self.project))


class NewFeature(models.Model):
    name = models.CharField(_('name'), max_length=24)
    deployment_date = models.DateField(_("deployment date"),)
    description = models.TextField(_('Description'),)
    permissions = models.TextField(_('permissions'), blank=True, null=True,)
    url = models.CharField(_('url'), max_length=255, blank=True,)
    screenshot = ThumbnailerImageField(_("screenshot"),
        upload_to='photos', blank=True, null=True,)

    class Meta:
        ordering = ('-deployment_date',)

    def __str__(self):
        return self.name


# Generic agent MetaInfo model to store json or texts
# meta types: 'total_transfers'

class MetaInfo(models.Model):
    agent = models.ForeignKey(EconomicAgent, related_name="metainfo", on_delete=models.CASCADE)
    type = models.CharField(_("type"), max_length=128)
    text = models.TextField(_("text"), blank=True, null=True)
    created_date = models.DateField(auto_now_add=True, editable=False)
    changed_date = models.DateField(auto_now=True, editable=False)

    class Meta:
        ordering = ('agent', '-changed_date')

    def __str__(self):
        return self.agent.nick+' '+self.type+' '+str(self.changed_date)



class InvoiceNumber(models.Model):
    invoice_number = models.CharField(_('invoice number'), max_length=128)
    invoice_date = models.DateField(_("invoice date"),)
    year = models.IntegerField(_("year"),)
    quarter = models.IntegerField(_("quarter"),)
    sequence = models.IntegerField(_("sequence"),)
    description = models.TextField(_('Description'), blank=True,null=True)
    member = models.ForeignKey(EconomicAgent, related_name="invoice_numbers",
        verbose_name=_('member'), on_delete=models.CASCADE)
    exchange = models.ForeignKey(Exchange,
        blank=True, null=True, on_delete=models.SET_NULL,
        verbose_name=_('exchange'), related_name='invoice_numbers')
    created_by = models.ForeignKey(User, verbose_name=_('created by'),
        related_name='invoice_numbers_created', editable=False, on_delete=models.CASCADE)
    created_date = models.DateField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ('-invoice_date', "-sequence",)

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if self.year:
            year = self.year
        else:
            year = self.invoice_date.year
            self.year = year
        if self.quarter:
            quarter = self.quarter
        else:
            month = self.invoice_date.month
            quarter = (month-1)//3 + 1
            self.quarter = quarter
        if self.sequence:
            sequence = self.sequence
        else:
            prevs = InvoiceNumber.objects.filter(
                year=year,
                quarter=quarter).order_by("-sequence")
            if prevs:
                sequence = prevs[0].sequence + 1
            else:
                sequence = 1
            self.sequence = sequence
        self.invoice_number = "/".join([
            str(year),
            str(quarter),
            str(sequence),
            str(self.member.id),
            ])
        super(InvoiceNumber, self).save(*args, **kwargs)


from general.models import Record_Type, Artwork_Type, Job, Unit_Type #, Material_Type, Nonmaterial_Type
from mptt.models import TreeManager


class Ocp_Artwork_TypeManager(TreeManager):

    def get_shares_type(self):
        shr_typs = Ocp_Artwork_Type.objects.filter(clas='shares')
        if shr_typs and len(shr_typs) > 1:
            raise ValidationError("There's more than one Ocp_Artwork_Type with the clas 'shares'!")
        elif shr_typs and shr_typs[0]:
            return shr_typs[0]
        else:
            raise ValidationError("The Ocp_Artwork_Type with clas 'shares' is not found!")

    def get_material_type(self):
        mat_typs = Ocp_Artwork_Type.objects.filter(clas='Material')
        if mat_typs and len(mat_typs) > 1:
            raise ValidationError("There's more than one Ocp_Artwork_Type with the clas 'Material'!")
        elif mat_typs and mat_typs[0]:
            return mat_typs[0]
        else:
            raise ValidationError("The Ocp_Artwork_Type with clas 'Material' is not found!")

    def get_nonmaterial_type(self):
        non_typs = Ocp_Artwork_Type.objects.filter(clas='Nonmaterial')
        if non_typs and len(non_typs) > 1:
            raise ValidationError("There's more than one Ocp_Artwork_Type with the clas 'Nonmaterial'!")
        elif non_typs and non_typs[0]:
            return non_typs[0]
        else:
            raise ValidationError("The Ocp_Artwork_Type with clas 'Nonmaterial' is not found!")

    def get_account_type(self):
        acc_typs = Ocp_Artwork_Type.objects.filter(clas='accounts')
        if acc_typs and len(acc_typs) > 1:
            raise ValidationError("There's more than one Ocp_Artwork_Type with the clas 'accounts'!")
        elif acc_typs and acc_typs[0]:
            return acc_typs[0]
        else:
            raise ValidationError("The Ocp_Artwork_Type with clas 'accounts' is not found!")

    def update_from_general(self): # TODO, if general.Artwork_Type (or Type) changes independently, update the subclass with new items
        return False

    """def update_to_general(self, table=None, ide=None): # update material and non-material general tables if not matching
        if table and ide:
            if table == 'Material_Type':
                try:
                    genm = Material_Type.objects.get(id=ide)
                except:
                    if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                        with connection.cursor() as cursor:
                            cursor.execute("PRAGMA foreign_keys=OFF")
                            cursor.execute("INSERT INTO general_material_type (materialType_artwork_type_id) VALUES (%s)", [ide])
                            cursor.execute("PRAGMA foreign_keys=ON")
                            return Material_Type.objects.get(id=ide)
            elif table == 'Nonmaterial_Type':
                try:
                    genm = Nonmaterial_Type.objects.get(id=ide)
                except:
                    if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                        with connection.cursor() as cursor:
                            cursor.execute("PRAGMA foreign_keys=OFF")
                            cursor.execute("INSERT INTO general_nonmaterial_type (nonmaterialType_artwork_type_id) VALUES (%s)", [ide])
                            cursor.execute("PRAGMA foreign_keys=ON")
                            return Nonmaterial_Type.objects.get(id=ide)
            else:
                raise ValidationError("Unknown table for update_to_general ! "+table)

        else: # update all
            pass
            ocp_mat = Ocp_Artwork_Type.objects.get(clas='Material')
            ocp_mats_c = ocp_mat.get_descendant_count() # self not included, like at general_material_type
            gen_mats_c = Material_Type.objects.count()
            if not ocp_mats_c == gen_mats_c:
                ocp_mats = ocp_mat.get_descendants()
                gen_mats = Material_Type.objects.all()
                for ocpm in ocp_mats:
                    try:
                        genm = Material_Type.objects.get(id=ocpm.id)
                    except:
                        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                            with connection.cursor() as cursor:
                                cursor.execute("PRAGMA foreign_keys=OFF")
                                cursor.execute("INSERT INTO general_material_type (materialType_artwork_type_id) VALUES (%s)", [ocpm.id])
                                cursor.execute("PRAGMA foreign_keys=ON")
    """


class Ocp_Artwork_Type(Artwork_Type):
    general_artwork_type = models.OneToOneField(
      Artwork_Type,
      on_delete=models.CASCADE,
      primary_key=True,
      parent_link=True
    )

    def get_Q_material_type():
        mat_typ = Ocp_Artwork_Type.objects.get_material_type()
        if mat_typ:
            return {'lft__gt':mat_typ.lft, 'rght__lt':mat_typ.rght, 'tree_id':mat_typ.tree_id}
        else:
            return {}

    rel_material_type = TreeForeignKey(
      'self',
      on_delete=models.SET_NULL,
      verbose_name=_('related material_type'),
      related_name='rel_types_material',
      blank=True, null=True,
      help_text=_("a related General Material Type"),
      limit_choices_to=get_Q_material_type
    )

    def get_Q_nonmaterial_type():
        non_typ = Ocp_Artwork_Type.objects.get_nonmaterial_type()
        if non_typ:
            return {'lft__gt':non_typ.lft, 'rght__lt':non_typ.rght, 'tree_id':non_typ.tree_id}
        else:
            return {}

    rel_nonmaterial_type = TreeForeignKey(
      'self',
      on_delete=models.SET_NULL,
      verbose_name=_('related nonmaterial_type'),
      related_name='rel_types_nonmaterial',
      blank=True, null=True,
      help_text=_("a related General Non-material Type"),
      limit_choices_to=get_Q_nonmaterial_type
    )
    facet = models.OneToOneField(
      Facet,
      on_delete=models.CASCADE,
      verbose_name=_('ocp facet'),
      related_name='ocp_artwork_type',
      blank=True, null=True,
      help_text=_("a related OCP Facet")
    )
    facet_value = models.ForeignKey(
      FacetValue,
      on_delete=models.CASCADE,
      verbose_name=_('ocp facet_value'),
      related_name='ocp_artwork_type',
      blank=True, null=True,
      help_text=_("a related OCP FacetValue")
    )
    resource_type = models.OneToOneField(
      EconomicResourceType,
      on_delete=models.CASCADE,
      verbose_name=_('ocp resource_type'),
      related_name='ocp_artwork_type',
      blank=True, null=True,
      help_text=_("a related OCP ResourceType")
    )
    context_agent = models.ForeignKey(EconomicAgent, # this field should be used only if there's no resource_type
      verbose_name=_('context agent'),               # and is needed to hide the category name by context
      on_delete=models.CASCADE,
      related_name='ocp_artwork_types',
      blank=True, null=True,
      help_text=_("a related OCP context EconomicAgent")
    )
    general_unit_type = TreeForeignKey(
        Unit_Type,
        on_delete=models.CASCADE,
        verbose_name=_('general unit_type'),
        related_name='ocp_artwork_types',
        blank=True, null=True,
        help_text=_("a related General Unit Type")
    )

    objects = Ocp_Artwork_TypeManager()

    class Meta:
      verbose_name= _('Type of General Artwork/Resource')
      verbose_name_plural= _('o-> Types of General Artworks/Resources')

    def __str__(self):
      try:
        if self.resource_type:
          return self.name+' <' #+'  ('+self.resource_type.name+')'
      except:
        return self.name+' !!'
      if self.facet_value:
          return self.name+':'#  ('+self.facet_value.value+')'
      elif self.facet:
          return self.name+'  ('+self.facet.name+')'
      else:
          return self.name


    def is_share(self):
        shr_typ = Ocp_Artwork_Type.objects.get_shares_type()
        shr_cur = Ocp_Unit_Type.objects.get_shares_currency()
        if shr_typ:
            # mptt: get_ancestors(ascending=False, include_self=False)
            ancs = self.get_ancestors(True, True)
            for an in ancs:
                if an.id == shr_typ.id:
                    return self
            if self.rel_nonmaterial_type:
                ancs = self.rel_nonmaterial_type.get_ancestors(True, True)
                for an in ancs:
                    if an.id == shr_typ.id:
                        return self.rel_nonmaterial_type #Ocp_Artwork_Type.objects.get(id=self.rel_nonmaterial_type.id)
            if self.general_unit_type and shr_cur:
                ancs = self.general_unit_type.get_ancestors(True, True)
                for an in ancs:
                    if an.id == shr_cur.id:
                        return self.general_unit_type #Ocp_Artwork_Type.objects.get(id=self.rel_nonmaterial_type.id)

        return False

    def is_account(self):
        acc_typ = Ocp_Artwork_Type.objects.get_account_type()
        if acc_typ:
            # mptt: get_ancestors(ascending=False, include_self=False)
            ancs = self.get_ancestors(True, True)
            for an in ancs:
                if an.id == acc_typ.id:
                    return self
        else:
            raise ValidationError("Can't get the ocp artwork type with clas 'accounts'")
        return False

    def is_currency(self):
        ancs = self.get_ancestors(True,True)
        cur = ancs.filter(clas__icontains='currency')
        if cur:
            return True
        return False




class Ocp_Skill_TypeManager(TreeManager):

    def update_from_general(self): # TODO, if general.Job changes independently, update the subclass with new items
        return False


class Ocp_Skill_Type(Job):
    general_job = models.OneToOneField(
      Job,
      on_delete=models.CASCADE,
      primary_key=True,
      parent_link=True
    )
    resource_type = models.OneToOneField(
      EconomicResourceType,
      on_delete=models.CASCADE,
      verbose_name=_('ocp resource_type'),
      related_name='ocp_skill_type',
      blank=True, null=True,
      help_text=_("a related OCP ResourceType")
    )
    facet = models.OneToOneField( # only root nodes can have unique facets
      Facet,
      on_delete=models.CASCADE,
      verbose_name=_('ocp facet'),
      related_name='ocp_skill_type',
      blank=True, null=True,
      help_text=_("a related OCP Facet")
    )
    facet_value = models.OneToOneField( # only some tree folders can have unique facet_values
      FacetValue,
      on_delete=models.CASCADE,
      verbose_name=_('ocp facet_value'),
      related_name='ocp_skill_type',
      blank=True, null=True,
      help_text=_("a related OCP FacetValue")
    )
    ocp_artwork_type = TreeForeignKey(
      Ocp_Artwork_Type,
      on_delete=models.SET_NULL,
      verbose_name=_('ocp artwork_type'),
      related_name='ocp_skill_types',
      blank=True, null=True,
      help_text=_("a related Ocp Artwork Type")
    )
    event_type = models.OneToOneField( # only for verbs that are ocp event types
      EventType,
      on_delete=models.SET_NULL,
      verbose_name=_('ocp event_type'),
      related_name='ocp_skill_type',
      blank=True, null=True,
      help_text=_("a related OCP EventType")
    )

    objects = Ocp_Skill_TypeManager()

    class Meta:
      verbose_name= _('Type of General Skill Resources')
      verbose_name_plural= _('o-> Types of General Skill Resources')

    def __str__(self):
      if self.resource_type:
        if self.ocp_artwork_type and not self.ocp_artwork_type.name.lower() in self.get_gerund().lower():
          return self.get_gerund()+' - '+self.ocp_artwork_type.name.lower()+' <'
        else:
          return self.get_gerund()+' <' #name #+'  ('+self.resource_type.name+')'
      elif self.facet_value:
        return self.get_gerund() #+'  ('+self.facet_value.value+')'
      else:
        return self.get_gerund()

    def get_gerund(self):
      if self.gerund:
        return self.gerund.title()
      elif self.verb:
        return self.verb
      else:
        return self.name

    def opposite(self):
        rel = self.rel_jobs1.filter(relation__clas='oppose')
        if rel:
            return rel[0].job2
        #import pdb; pdb.set_trace()
        return False


class Ocp_Record_TypeManager(TreeManager):

    def update_from_general(self): # TODO, if general.Record_Type changes independently, update the subclass with new items
        return False


class Ocp_Record_Type(Record_Type):
    general_record_type = models.OneToOneField(
        Record_Type,
        on_delete=models.CASCADE,
        primary_key=True,
        parent_link=True
    )
    exchange_type = models.OneToOneField(
        ExchangeType,
        on_delete=models.CASCADE,
        blank=True, null=True,
        verbose_name=_('ocp exchange type'),
        related_name='ocp_record_type'
    )
    ocpRecordType_ocp_artwork_type = TreeForeignKey(
        Ocp_Artwork_Type,
        on_delete=models.CASCADE,
        verbose_name=_('general artwork_type'),
        related_name='ocp_record_types',
        blank=True, null=True,
        help_text=_("a related General Artwork Type")
    )
    ocp_skill_type = TreeForeignKey(
        Ocp_Skill_Type,
        on_delete=models.CASCADE,
        verbose_name=_('general skill_type'),
        related_name='ocp_record_types',
        blank=True, null=True,
        help_text=_("a related General Skill Type")
    )
    '''event_type = models.ForeignKey( # only for verbs that are ocp event types
      EventType,
      on_delete=models.SET_NULL,
      verbose_name=_('ocp event_type'),
      related_name='ocp_skill_type',
      blank=True, null=True,
      help_text=_("a related OCP EventType")
    )'''

    objects = Ocp_Record_TypeManager()

    class Meta:
        verbose_name= _('Type of General Record')
        verbose_name_plural= _('o-> Types of General Records')

    def __str__(self):
      if self.exchange_type:
        return self.name+' <' #+'  ('+self.resource_type.name+')'
      else:
        return self.name

    def context_agent(self):
      if self.exchange_type:
        if self.exchange_type.context_agent:
          return self.exchange_type.context_agent
      return None

    def get_ocp_resource_types(self, transfer_type=None):
        answer = None
        if transfer_type:
          if transfer_type.inherit_types:
            answer = Ocp_Artwork_Type.objects.filter(lft__gte=self.ocpRecordType_ocp_artwork_type.lft, rght__lte=self.ocpRecordType_ocp_artwork_type.rght, tree_id=self.ocpRecordType_ocp_artwork_type.tree_id).order_by('tree_id','lft')
          else:
            facetvalues = [ttfv.facet_value.value for ttfv in transfer_type.facet_values.all()]
            Mtyp = False
            Ntyp = False
            try:
                Mtyp = Artwork_Type.objects.get(clas="Material")
                Ntyp = Artwork_Type.objects.get(clas="Nonmaterial")
            except:
                pass

            Rids = []
            Sids = []
            for fv in facetvalues:
                try:
                    gtyps = Ocp_Artwork_Type.objects.filter(facet_value__value=fv)
                    for gtyp in gtyps:
                      subids = [typ.id for typ in Ocp_Artwork_Type.objects.filter(lft__gt=gtyp.lft, rght__lt=gtyp.rght, tree_id=gtyp.tree_id)]
                      Rids += subids+[gtyp.id]
                except:
                    pass

                try:
                    gtyp = Ocp_Skill_Type.objects.get(facet_value__value=fv)
                    subids = [typ.id for typ in Ocp_Skill_Type.objects.filter(lft__gt=gtyp.lft, rght__lt=gtyp.rght, tree_id=gtyp.tree_id)]
                    Sids += subids+[gtyp.id]
                except:
                    pass

            for facet in transfer_type.facets():
                if facet.clas == "Material_Type" or facet.clas == "Nonmaterial_Type" or facet.clas == "Currency_Type":
                    if Rids:
                        Rtys = Ocp_Artwork_Type.objects.filter(id__in=Rids).order_by('tree_id','lft') #.order_by('tree_id','lft')
                        #if Nids: # and Ntyp:
                        #    Mtys = Artwork_Type.objects.filter(id__in=Nids+Mids) #+[Ntyp.id, Mtyp.id])
                        answer = Rtys
                    else:
                        answer = Ocp_Artwork_Type.objects.all()

                elif facet.clas == "Skill_Type":
                    if Sids:
                        Stys = Ocp_Skill_Type.objects.filter(id__in=Sids).order_by('tree_id','lft')
                        #if Mids: # and Mtyp:
                        #    Ntys = Artwork_Type.objects.filter(id__in=Mids+Nids) #+[Ntyp.id, Mtyp.id])
                        answer = Stys
                    else:
                        answer = Ocp_Skill_Type.objects.all()

                #elif facet.clas == "Currency_Type":
                #    pass
                else:
                    pass

        if not answer:
          return Ocp_Artwork_Type.objects.none()

        return answer

    def x_actions(self):
        try:
            x_act = Ocp_Skill_Type.objects.get(clas='exchange')
            x_acts = Ocp_Skill_Type.objects.filter(lft__gt=x_act.lft, rght__lt=x_act.rght, tree_id=x_act.tree_id)
            return x_acts
        except:
            return []





from general.models import Unit as Gene_Unit
from general.models import Type

class Ocp_Unit_TypeManager(TreeManager):

    def get_shares_currency(self):
        shr_typs = Ocp_Unit_Type.objects.filter(clas='shares_currency')
        if shr_typs and len(shr_typs) > 1:
            raise ValidationError("There's more than one Ocp_Unit_Type with the clas 'shares_currency'!")
        elif shr_typs and shr_typs[0]:
            return shr_typs[0]
        else:
            raise ValidationError("The Ocp_Unit_Type with 'shares_currency' clas is not found!")

    def update_from_general(self): # TODO, if general.Unit_Type changes independently, update the subclass with new items
        return False


class Ocp_Unit_Type(Unit_Type):

    objects = Ocp_Unit_TypeManager()

    class Meta:
        proxy = True
        verbose_name= _('Type of General Unit')
        verbose_name_plural= _('o-> Types of General Units')

    def __str__(self):
        us = self.units()
        if self.children.count():
            if len(us) == 1:
                return self.name+': <' #+'  ('+self.resource_type.name+')'
            else:
                return self.name+': '
        else:
            if len(us) == 1:
                return self.name+' <' #+'  ('+self.resource_type.name+')'
            else:
                return self.name

    def units(self):
        us = []
        if self.unit_set:
            for u in self.unit_set.all():
                us.append(u)
        return us

    def ocp_unit(self):
        us = self.units()
        if us:
            if us[0].ocp_unit:
                return us[0].ocp_unit
            else:
                raise ValidationError("The first unit related this Ocp_Unit_Type has not 'ocp_unit' - us[0]: "+str(us[0]))
        return None




#from django.db.models.signals import post_migrate
#from work.apps import WorkAppConfig


def fill_empty_languages(**kwargs):

    from django.core.management import call_command
    import modeltranslation

    lang = settings.LANGUAGE_CODE
    print("default LANG: "+lang)
    try:
        ocp = EconomicAgent.objects.filter(nick='OCP')
        if hasattr(ocp, 'nick_en'):
            print("OCP en:"+str(ocp.nick_en))
    except:
        print("OCP still has not translatable fields. SKIP!")
        return
    call_command('update_translation_fields') #, interactive=True)

    for lan in settings.LANGUAGES:
        if not lan[0] == lang:
            print("other LANG: "+lan[0])
            modeltranslation.management.commands.update_translation_fields.DEFAULT_LANGUAGE = lan[0]
            call_command('update_translation_fields') #, interactive=True)

    modeltranslation.management.commands.update_translation_fields.DEFAULT_LANGUAGE = lang
    print("---- Language's empty strings has been filled with the default language string to keep uniqueness. ----")



def create_unit_types(**kwargs):

    atnet = AgentType.objects.filter(name="Network")
    if not atnet:
        atnet, c = AgentType.objects.get_or_create(
            name="Network",
            party_type="network",
            is_context=True)
        if c:
            print("- created AgentType: Network")
    else:
        atnet = atnet[0]
    ocp = EconomicAgent.objects.filter(nick='OCP')
    if not ocp:
        print("- 'OCP' nick not found, fill from nick_en!")
        ocp = EconomicAgent.objects.filter(nick_en='OCP')
        if not ocp:
            ocp, c = EconomicAgent.objects.get_or_create(
                nick="OCP",
                name="General OCP",
                agent_type=atnet)
            if c:
                print("- created EconomicAgent: OCP")
        ocp.nick = 'OCP'
        ocp.save()
    else:
        ocp = ocp[0]
        if not ocp.nick_es:
            ocp.nick_es = ocp.nick_en
            ocp.save()
            print("- missing nick_es! fill it: "+ocp.nick_es)
        if not ocp.nick_ca:
            ocp.nick_ca = ocp.nick_en
            ocp.save()
            print("- missing nick_ca! fill it: "+ocp.nick_ca)

    atcop = AgentType.objects.filter(name="Cooperative")
    if not atcop:
        atcop, c = AgentType.objects.get_or_create(
            name="Cooperative",
            party_type="organization",
            is_context=True)
        if c:
            print("- created AgentType: Cooperative")
    else:
        atcop = atcop[0]

    fdc = EconomicAgent.objects.filter(nick='Freedom Coop')
    if not fdc:
        print("- 'Freedom Coop' nick not found, fill from nick_en!")
        fdc = EconomicAgent.objects.filter(nick_en='Freedom Coop')
        if not fdc:
            fdc, c = EconomicAgent.objects.get_or_create(
                name='Freedom Coop', nick='Freedom Coop',
                agent_type=atcop, is_context=True)
            if c: print("t- created EconomicAgent: 'Freedom Coop'")

        fdc.nick = 'Freedom Coop'
        fdc.save()
    else:
        fdc = fdc[0]
        if not fdc.nick_es:
            fdc.nick_es = fdc.nick_en
            fdc.save()
            print("- missing nick_es! fill it: "+fdc.nick_es)
        if not fdc.nick_ca:
            fdc.nick_ca = fdc.nick_en
            fdc.save()
            print("- missing nick_ca! fill it: "+fdc.nick_ca)

    print("Analizing the unit types in the system...")
    # Each
    ocp_eachs = Unit.objects.filter(name_en='Each')
    if ocp_eachs:
        ocp_each = ocp_eachs[0]
    else:
        ocp_each, created = Unit.objects.get_or_create(
            name_en='Each',
            unit_type='quantity',
            abbrev='u.')
        if created:
            print("- created Unit: 'Each' (u.)")
    ocp_each.abbrev = 'u.'
    ocp_each.save()

    gen_artwt, created = Type.objects.get_or_create(name_en="Artwork", clas='Artwork')
    if created:
        print("- created root general Type: 'Artwork'")
    gen_unitt, created = Artwork_Type.objects.get_or_create(name_en="Unit", parent=gen_artwt, clas='Unit')
    if created:
        print("- created general Artwork_Type: 'Unit'")
    each_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Each',
        parent=gen_unitt
    )
    if created:
        print("- created Ocp_Unit_type: 'Each'")
    each_typ.clas = 'each'
    each_typ.save()

    each = Gene_Unit.objects.filter(ocp_unit=ocp_each)
    if not each:
        each = Gene_Unit.objects.filter(name='Each')
    if not each:
        each, created = Gene_Unit.objects.get_or_create(
            name='Unit',
            code='u',
            unit_type=each_typ
        )
        if created:
            print("- created General.Unit for Each: 'Unit'")
    else:
        each = each[0]
    each.ocp_unit = ocp_each
    each.save()

    # Percent
    ocp_percs = Unit.objects.filter(name_en='Percent')
    if ocp_percs:
        ocp_perc = ocp_percs[0]
    else:
        ocp_perc, created = Unit.objects.get_or_create(
            name_en='Percent',
            unit_type='percent',
            abbrev='Pct')
        if created:
            print("- created Unit: 'Percent'")
    ocp_perc.symbol = '%'
    ocp_perc.save()

    perc_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Percent',
        parent=gen_unitt
    )
    if created:
        print("- created Ocp_Unit_type: 'Percent'")
    perc_typ.clas = 'percent'
    perc_typ.save()

    perc = Gene_Unit.objects.filter(ocp_unit=ocp_perc)
    if not perc:
        perc, created = Gene_Unit.objects.get_or_create(
            name='percent',
            code='%',
            unit_type=perc_typ,
            ocp_unit=ocp_perc
        )
        if created:
            print("- created General.Unit for Percent: 'percent'")

    # Hours
    ocp_hours = Unit.objects.filter(name_en='Hour')
    if ocp_hours:
        ocp_hour = ocp_hours[0]
        ocp_hour.name_en = 'Hours'
        ocp_hour.save()
    else:
        ocp_hours = Unit.objects.filter(name_en='Hours')
        if ocp_hours:
            ocp_hour = ocp_hours[0]
        else:
            ocp_hour, created = Unit.objects.get_or_create(
                name_en='Hours',
                unit_type='time',
                abbrev='Hr')
            if created:
                print("- created Unit: 'Hours'")

    gen_time_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Time',
        parent=gen_unitt
    )
    if created:
        print("- created Ocp_Unit_Type: 'Time'")
    gen_time_typ.clas = 'time_currency'
    gen_time_typ.save()

    hour = Gene_Unit.objects.filter(name='Hour')
    if not hour:
        hour, created = Gene_Unit.objects.get_or_create(
            name='Hour',
            code='h',
            unit_type=gen_time_typ
        )
        if created:
            print("- created General.Unit for Hours: 'Hour'")
    else:
        hour = hour[0]
    hour.ocp_unit = ocp_hour
    hour.save()

    # Days
    ocp_days = Unit.objects.filter(name_en='Day')
    if ocp_days:
        ocp_day = ocp_days[0]
    else:
        ocp_days = Unit.objects.filter(name_en='Days')
        if ocp_days:
            ocp_day = ocp_days[0]
        else:
            ocp_day, created = Unit.objects.get_or_create(
                name_en='Day',
                unit_type='time',
                abbrev='day')
            if created:
                print("- created Unit: 'Day'")

    days = Gene_Unit.objects.filter(name='Day')
    if not days:
        day, created = Gene_Unit.objects.get_or_create(
            name='Day',
            code='dd',
            unit_type=gen_time_typ
        )
    else:
        day = days[0]
    day.ocp_unit = ocp_day
    day.save()


    # Kilos
    ocp_kilos = Unit.objects.filter(name_en='Kilos')
    if ocp_kilos:
        ocp_kilos = ocp_kilos[0]
    else:
        ocp_kilos = Unit.objects.filter(name_en='Kilo')
        if ocp_kilos:
            ocp_kilos = ocp_kilos[0]
        else:
            ocp_kilos, created = Unit.objects.get_or_create(
                name_en='Kilos',
                unit_type='weight',
                abbrev='Kg')
            if created:
                print("- created Unit: 'Kilos'")
    ocp_kilos.name_en = 'Kilos'
    ocp_kilos.abbrev = 'Kg'
    ocp_kilos.save()

    gen_weight_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Weight',
        parent=gen_unitt
    )
    if created:
        print("- created Ocp_Unit_Type: 'Weight'")

    kilos = Gene_Unit.objects.filter(name='Kilogram')
    if not kilos:
        kilo, created = Gene_Unit.objects.get_or_create(
            name='Kilogram',
            code='Kg',
            unit_type=gen_weight_typ
        )
        if created:
            print("- created General.Unit for Kilos: 'Kilogram'")
    else:
        kilo = kilos[0]
    kilo.ocp_unit = ocp_kilos
    kilo.save()


    # FacetValues

    curfacet, created = Facet.objects.get_or_create(
        name="Currency")
    if created:
        print("- created Facet: 'Currency'")
    curfacet.clas = "Currency_Type"
    curfacet.description = "This facet is to group types of currencies, so a resource type can act as a currency of certain type if wears any of this values"
    curfacet.save()


    shrfvs = FacetValue.objects.filter(value='Project Shares')
    fv_shs = FacetValue.objects.filter(value='CoopShares')
    shrfv = None
    if fv_shs and shrfvs:
        fv_sh = fv_shs[0]
        rtfvs = ResourceTypeFacetValue.objects.filter(facet_value=fv_sh)
        shrfv = shrfvs[0]
        rtfvs2 = ResourceTypeFacetValue.objects.filter(facet_value=shrfv)
        if not rtfvs and rtfvs2: # CoopShares is not used
            print("- Deleted FacetValue: "+str(fv_sh))
            loger.info("- Deleted FacetValue: "+str(fv_sh))
            fv_sh.delete()
        elif not rtfvs2 and rtfvs: # Project Shares is not used
            shrfv = fv_sh
        elif rtfvs and rtfvs2:
            for rtfv in rtfvs:
                print("- changed ResourceTypeFacetValue fv from: "+str(rtfv.facet_value)+" to: "+str(shrfv)+" for rt: "+str(rtfv.resource_type))
                loger.info("- changed ResourceTypeFacetValue fv from: "+str(rtfv.facet_value)+" to: "+str(shrfv)+" for rt: "+str(rtfv.resource_type))
                rtfv.facet_value = shrfv
                rtfv.save()
            #raise ValidationError("Both FacetValues has related resource_types!? "+str(fv_sh)+" <-> "+str(shrfv))
        else:
            print("- Deleted FacetValue: "+str(shrfv))
            loger.info("- Deleted FacetValue: "+str(shrfv))
            shrfv.delete()
            shrfv = fv_sh
    elif fv_shs and not shrfvs:
        shrfv = fv_shs[0]
    elif not fv_shs and shrfvs:
        shrfv = shrfvs[0]

    if not shrfv:
        shrfv, created = FacetValue.objects.get_or_create(
            facet=curfacet,
            value="Project Shares")
        if created:
            print("- created FacetValue: 'Project Shares'")
    shrfv.facet = curfacet
    shrfv.value = "Project Shares"
    shrfv.save()

    nonfacet, created = Facet.objects.get_or_create(
        name="Non-material",
        clas="Nonmaterial_Type")
    if created:
        print("- created Facet: 'Non-material'")
    fvmoney, created = FacetValue.objects.get_or_create(
        facet=nonfacet,
        value='Money')
    if created:
        print("- created FacetValue: 'Money'")

    fairfv, created = FacetValue.objects.get_or_create(value="Fair currency", facet=curfacet)
    if created:
        print("- created FacetValue: 'Fair currency'")

    fiatfv, created = FacetValue.objects.get_or_create(value="Fiat currency", facet=curfacet)
    if created:
        print("- created FacetValue: 'Fiat currency'")

    cryptfv, created = FacetValue.objects.get_or_create(value="Crypto currency", facet=curfacet)
    if created:
        print("- created FacetValue: 'Crypto currency'")




    #   F a i r C o i n

    ocp_fairs = Unit.objects.filter(name='FairCoin')
    if not ocp_fairs:
        ocp_fairs = Unit.objects.filter(name='Faircoin')
    if ocp_fairs:
        if len(ocp_fairs) > 1:
            print("ERROR: More than one Unit named 'Faircoin'!! please delete the non-used one and retry: "+str(ocp_fairs))
            if len(ocp_fairs) == 2:
                if ocp_fairs[0].id < ocp_fairs[1].id:
                    print("DELETED the more recent Unit: "+str(ocp_fairs[1]))
                    ocp_fairs[1].delete()
                    ocp_fair = ocp_fairs[0]
            #raise ValidationError("ERROR: More than one Unit named 'Faircoin'!! please delete the non-used one and retry"+str(ocp_fairs))
        else:
            ocp_fair = ocp_fairs[0]
    else:
        ocp_fair, created = Unit.objects.get_or_create(name_en='FairCoin', unit_type='value')
        if created:
            print("- created a main ocp Unit: 'FairCoin'!")
    ocp_fair.abbrev = 'fair'
    ocp_fair.unit_type = 'value'
    ocp_fair.symbol = "ƒ"
    ocp_fair.save()

    gen_curr_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Currency',
        parent=gen_unitt
    )
    if created:
        print("- created Ocp_Unit_Type: 'Currency'")
    gen_curr_typ.clas = 'currency'
    gen_curr_typ.save()

    gen_crypto_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Crypto Currency',
        parent=gen_curr_typ
    )
    if created:
        print("- created Ocp_Unit_Type: 'Crypto Currency'")

    gen_fair_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Faircoins',
        parent=gen_crypto_typ
    )
    if created:
        print("- created Ocp_Unit_Type: 'Faircoins'")
    gen_fair_typ.clas = 'faircoin'
    gen_fair_typ.save()

    fairs = Gene_Unit.objects.filter(name='FairCoin')
    if not fairs:
        fair, created = Gene_Unit.objects.get_or_create(
            name='FairCoin',
            code='ƒ'
        )
        if created:
            print("- created General.Unit for FairCoin: 'FairCoin'")
    else:
        fair = fairs[0]
    fair.code = 'ƒ'
    fair.unit_type = gen_fair_typ
    fair.ocp_unit = ocp_fair
    fair.save()

    ocp_fair_rts = EconomicResourceType.objects.filter(name_en='FairCoin')
    if not ocp_fair_rts:
        ocp_fair_rt, created = EconomicResourceType.objects.get_or_create(
            name_en='FairCoin')
        if created:
            print("- created EconomicResourceType: 'FairCoin'")
    else:
        if len(ocp_fair_rts) > 1:
            raise ValidationError("There are more than one EconomicResourceType named 'FairCoin'.")
        ocp_fair_rt = ocp_fair_rts[0]
    ocp_fair_rt.unit = ocp_fair
    ocp_fair_rt.unit_of_use = ocp_fair
    #ocp_fair_rt.unit_of_value = ocp_fair
    #ocp_fair_rt.value_per_unit = 1
    #ocp_fair_rt.value_per_unit_of_use = 1
    ocp_fair_rt.price_per_unit = 1
    ocp_fair_rt.unit_of_price = ocp_fair
    ocp_fair_rt.substitutable = True
    ocp_fair_rt.inventory_rule = 'yes'
    ocp_fair_rt.behavior = 'dig_curr'
    ocp_fair_rt.save()

    for fv in ocp_fair_rt.facets.all():
        if not fv.facet_value == fairfv and not fv.facet_value == fvmoney:
            print("- deleted: "+str(fv))
            fv.delete()
    ocp_fair_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=ocp_fair_rt,
        facet_value=fairfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(ocp_fair_rtfv))

    ocp_fair_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=ocp_fair_rt,
        facet_value=fvmoney)
    if created:
        print("- created ResourceTypeFacetValue: "+str(ocp_fair_rtfv))


    nonmat_typs = Ocp_Artwork_Type.objects.filter(clas='Nonmaterial')
    if nonmat_typs:
        if len(nonmat_typs) > 1:
            raise ValidationError("There are more than one Ocp_Artwork_Type with clas 'Nonmaterial' ?!")
        nonmat_typ = nonmat_typs[0]
    else:
        nonmat_typ, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Non-material',
            parent=gen_artwt,
            clas='Nonmaterial')
        if created:
            print("- created Ocp_Artwork_Type: 'Non-material'")

    digart_typ, created = Ocp_Artwork_Type.objects.get_or_create(
        name_en='Digital artwork',
        parent=nonmat_typ)
    if created:
        print("- created Ocp_Artwork_Type: 'Digital artwork'")
    digcur_typs = Ocp_Artwork_Type.objects.filter(name_en='digital Currencies')
    if not digcur_typs:
        digcur_typ, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='digital Currencies',
            parent=digart_typ)
        if created:
            print("- created Ocp_Artwork_Types: 'digital Currencies'")
    else:
        digcur_typ = digcur_typs[0]
    digcur_typ.clas = 'currency'
    digcur_typ.save()

    fair_rts = Ocp_Artwork_Type.objects.filter(name_en='FairCoin')
    if not fair_rts:
        fair_rt, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='FairCoin',
            parent=digcur_typ)
        if created:
            print("- created Ocp_Artwork_Types: 'FairCoin'")
    else:
        fair_rt = fair_rts[0]
    fair_rt.clas = 'fair_digital'
    fair_rt.resource_type = ocp_fair_rt
    fair_rt.general_unit_type = gen_fair_typ
    fair_rt.save()


    #    F a i r c o i n   O c p   A c c o u n t

    fairacc_rts = EconomicResourceType.objects.filter(name_en='Faircoin Ocp Account')
    if not fairacc_rts:
        fairacc_rt, created = EconomicResourceType.objects.get_or_create(
            name_en='Faircoin Ocp Account')
        if created:
            print("- created EconomicResourceType: 'Faircoin Ocp Account'")
    else:
        fairacc_rt = fairacc_rts[0]
    fairacc_rt.unit = ocp_fair
    fairacc_rt.unit_of_use = ocp_fair
    fairacc_rt.unit_of_value = ocp_fair
    #fairacc_rt.value_per_unit = 1
    fairacc_rt.value_per_unit_of_use = 1 #Decimal('1.00')
    #fairacc_rt.price_per_unit = 1
    fairacc_rt.unit_of_price = ocp_fair
    fairacc_rt.substitutable = True
    #fairacc_rt.inventory_rule = 'yes'
    fairacc_rt.behavior = 'dig_acct'
    fairacc_rt.save()

    print("- "+str(fairacc_rt)+" FV's: "+str([fv.facet_value.value+', ' for fv in fairacc_rt.facets.all()]))

    digacc_typs = Ocp_Artwork_Type.objects.filter(name_en='digital Account')
    if not digacc_typs:
        digacc_typs = Ocp_Artwork_Type.objects.filter(name_en='digital Accounts')
    if not digacc_typs:
        digacc_typ, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='digital Accounts',
            parent=digart_typ)
        if created:
            print("- created Ocp_Artwork_Types: 'digital Accounts'")
    else:
        digacc_typ = digacc_typs[0]
    digacc_typ.name_en = 'digital Accounts'
    digacc_typ.clas = 'accounts'
    digacc_typ.parent = digart_typ
    digacc_typ.save()

    facc_rts = Ocp_Artwork_Type.objects.filter(name_en='Faircoin Ocp Account')
    if not facc_rts:
        facc_rt, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Faircoin Ocp Account',
            parent=digacc_typ)
        if created:
            print("- created Ocp_Artwork_Types: 'Faircoin Ocp Account'")
    else:
        facc_rt = facc_rts[0]
    facc_rt.clas = 'fair_ocp_account'
    facc_rt.resource_type = fairacc_rt
    #facc_rt.general_unit_type = gen_fair_typ
    facc_rt.save()


    # connect Faircoin   E x c h a n g e   T y p e s

    int_usecase = UseCase.objects.get(name="Internal Exchange")
    out_usecase = UseCase.objects.get(name="Outgoing Exchange")
    inc_usecase = UseCase.objects.get(name="Incoming Exchange")

    intfairets = ExchangeType.objects.filter(name="Transfer FairCoins")
    if not intfairets:
        intfairets = ExchangeType.objects.filter(name="Transfer Faircoins")
    if intfairets:
        intfairet = intfairets[0]
        if len(intfairets) > 1:
            print("Repeated ET, delete? "+str(intfairets[1].id))
    else:
        intfairet, c = ExchangeType.objects.get_or_create(
            name="Transfer Faircoins",
            use_case=int_usecase)
        if c:
            print("- created new ExchangeType: "+str(intfairet))
    intfairet.use_case = int_usecase
    intfairet.name = "Transfer Faircoins"
    intfairet.save()

    intfairtts = intfairet.transfer_types.all()
    if intfairtts:
        intfairtt = intfairtts[0]
        print("- found first intTT id:"+str(intfairtt.id)+" name:"+str(intfairtt)+" txs:"+str(len(intfairtt.transfers.all())))
    if len(intfairtts) > 1:
        for tt in intfairtts:
            if not tt == intfairtt:
                txs = tt.transfers.all()
                print(" - found other intTT id:"+str(tt.id)+" name:"+str(tt)+" txs:"+str(txs))
                for tx in txs:
                    print("- REPAIRED transfer_type of the tx:"+str(tx.id)+" from:"+str(tx.transfer_type.id)+" to:"+str(intfairtt.id))
                    tx.transfer_type = intfairtt
                    tx.save()
                if tt.is_deletable():
                    if not tt.facet_values.all():
                        print("- DELETE intTT ? id:"+str(tt.id))
                        tt.delete()

    extfairets = ExchangeType.objects.filter(name="Send FairCoins")
    if not extfairets:
        extfairets = ExchangeType.objects.filter(name="Send Faircoins")
    if extfairets:
        extfairet = extfairets[0]
        if len(extfairets) > 1:
            print("Repeated ET, delete? "+str(extfairets[1].id))
    else:
        extfairet = ExchangeType(
            use_case=out_usecase,
            name="Send Faircoins"
        )
    extfairet.name = "Send Faircoins"
    extfairet.use_case = out_usecase
    extfairet.save()

    extfairtts = extfairet.transfer_types.all()
    if extfairtts:
        extfairtt = extfairtts[0]
        print("- found first extTT id:"+str(extfairtt.id)+" name:"+str(extfairtt)+" txs:"+str(len(extfairtt.transfers.all())))
    if len(extfairtts) > 1:
        for tt in extfairtts:
            if not tt == extfairtt:
                txs = tt.transfers.all()
                print(" - found other extTT id:"+str(tt.id)+" name:"+str(tt)+" txs:"+str(txs))
                for tx in txs:
                    print("- REPAIRED transfer_type of the tx:"+str(tx.id)+" from:"+str(tx.transfer_type.id)+" to:"+str(extfairtt.id))
                    tx.transfer_type = extfairtt
                    tx.save()
                if tt.is_deletable():
                    if not tt.facet_values.all():
                        print("- DELETE extTT ? id:"+str(tt.id))
                        tt.delete()

    incfairets = ExchangeType.objects.filter(name="Receive FairCoins")
    if not incfairets:
        incfairets = ExchangeType.objects.filter(name="Receive Faircoins")
    if incfairets:
        incfairet = incfairets[0]
        if len(incfairets) > 1:
            print("Repeated ET, delete? "+str(incfairets[1].id))
    else:
        incfairet, c = ExchangeType.objects.get_or_create(
            name="Receive Faircoins",
            use_case=inc_usecase)
        if c:
            print("- created ExchangeType: "+str(incfairet))
    incfairet.name = "Receive Faircoins"
    incfairet.use_case = inc_usecase
    incfairet.save()

    incfairtts = incfairet.transfer_types.all()
    if incfairtts:
        incfairtt = incfairtts[0]
        print("- found first incTT id:"+str(incfairtt.id)+" name:"+str(incfairtt)+" txs:"+str(len(incfairtt.transfers.all())))
    if len(incfairtts) > 1:
        for tt in incfairtts:
            if not tt == incfairtt:
                txs = tt.transfers.all()
                print(" - found other incTT id:"+str(tt.id)+" name:"+str(tt)+" txs:"+str(txs))
                for tx in txs:
                    print("- REPAIRED transfer_type of the tx:"+str(tx.id)+" from:"+str(tx.transfer_type.id)+" to:"+str(incfairtt.id))
                    tx.transfer_type = incfairtt
                    tx.save()
                if tt.is_deletable():
                    if not tt.facet_values.all():
                        print("- DELETE incTT ? id:"+str(tt.id))
                        tt.delete()

    genrec = Artwork_Type.objects.get(clas="Record")
    ocprecs = Artwork_Type.objects.filter(clas='ocp_record')
    if not ocprecs:
        ocprecs = Artwork_Type.objects.filter(name_en='OCP Record')
        print("- found OCP Record as an Artwork_Type by name")

    if ocprecs:
        ocprec = ocprecs[0]
    else:
        ocprec, c = Artwork_Type.objects.get_or_create(
            name_en="OCP Record",
            clas="ocp_record",
            parent=genrec)
        if c:
            print("- created Artwork_Type: "+str(ocprec))
    ocprec.clas = 'ocp_record'
    ocprec.name_en = "OCP Record"
    ocprec.parent = genrec
    ocprec.save()


    ocpexts = Ocp_Record_Type.objects.filter(clas='ocp_exchange')
    if ocpexts:
        ocpext = ocpexts[0]
    else:
        ocpext, c = Ocp_Record_Type.objects.get_or_create(
            name_en="OCP ExchangeType",
            clas="ocp_exchange",
            parent=ocprec)
        if c:
            print("- created Ocp_Record_Type: "+str(ocpext))


    gen_gifts = Ocp_Record_Type.objects.filter(name_en__icontains="Gift Economy")
    if gen_gifts:
        gen_gift = gen_gifts[0]
    else:
        gen_gift, c = Ocp_Record_Type.objects.get_or_create(
            name_en="Gift Economy:",
            parent=ocpext)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_gift))
    gen_gift.name_en = "Gift Economy:"
    gen_gift.clas = "gift_economy"
    gen_gift.save()

    gen_gives = Ocp_Record_Type.objects.filter(name_en__icontains="Give gift")
    if gen_gives:
        gen_give = gen_gives[0]
    else:
        gen_give, c = Ocp_Record_Type.objects.get_or_create(
            name_en="Give gift:",
            parent=gen_gift)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_give))
    gen_give.name_en = "Give gift:"
    gen_give.clas = "give"
    gen_give.parent = gen_gift
    gen_give.save()

    gen_nmats = Ocp_Record_Type.objects.filter(name_en__icontains="give Non-material resources")
    if gen_nmats:
        gen_nmat = gen_nmats[0]
    else:
        gen_nmat, c = Ocp_Record_Type.objects.get_or_create(
            name_en="give Non-material resources",
            parent=gen_give)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_nmat))
    gen_nmat.name_en = "give Non-material resources"
    gen_nmat.parent = gen_give
    gen_nmat.ocpRecordType_ocp_artwork_type = nonmat_typ
    gen_nmat.save()

    oldet = ExchangeType.objects.filter(name="give FairCoin donation")
    if oldet:
        oldet = oldet[0]
        if not oldet.is_deletable():
            print("WARN! there's also a 'give FairCoin donation' ExchangeType! not deletable. usecase:"+str(oldet.use_case)+" exs:"+str(len(oldet.exchanges.all()))+" <> "+str(len(intfairet.exchanges.all())))
            if oldet.use_case == int_usecase:
                for ex in oldet.exchanges.all():
                    print("internal? edit ex:"+str(ex.id))
                return
            elif oldet.use_case == out_usecase:
                for ex in oldet.exchanges.all():
                    print("outgoing: EDITED et of ex:"+str(ex.id))
                    ex.exchange_type = extfairet
                    ex.save()
            elif oldet.use_case == inc_usecase:
                for ex in oldet.exchanges.all():
                    print("incoming? edit ex:"+str(ex.id))
                return
        else:
            print("- DELETED ExchangeType: "+str(oldet.id)+" "+str(oldet))
            oldet.delete()

    gen_fairints = Ocp_Record_Type.objects.filter(name_en__icontains="give FairCoin donation (via ocp)")
    if not gen_fairints:
        gen_fairints = Ocp_Record_Type.objects.filter(name_en__icontains="give FairCoin donation")
    if gen_fairints:
        if len(gen_fairints) > 1:
            print("WARNING there is more than one gen_fairint ? "+str(gen_fairints))
            return
        gen_fairint = gen_fairints[0]
    else:
        gen_fairint, c = Ocp_Record_Type.objects.get_or_create(
            name_en="give FairCoin donation (via ocp)",
            parent=gen_nmat)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_fairint))
    gen_fairint.name_en = "give FairCoin donation (via ocp)"
    gen_fairint.parent = gen_nmat
    gen_fairint.ocpRecordType_ocp_artwork_type = fair_rt # facc_rt ?
    gen_fairint.exchange_type = intfairet
    gen_fairint.save()

    gen_fairouts = Ocp_Record_Type.objects.filter(name_en__icontains="give FairCoin donation (external)")
    if gen_fairouts:
        gen_fairout = gen_fairouts[0]
    else:
        gen_fairout, c = Ocp_Record_Type.objects.get_or_create(
            name_en="give FairCoin donation (external)",
            parent=gen_nmat)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_fairout))
    gen_fairout.name_en = "give FairCoin donation (external)"
    gen_fairout.parent = gen_nmat
    gen_fairout.ocpRecordType_ocp_artwork_type = fair_rt
    gen_fairout.exchange_type = extfairet
    gen_fairout.save()

    gen_receives = Ocp_Record_Type.objects.filter(name_en__contains="Receive gift")
    if gen_receives:
        if len(gen_receives) > 1:
            print("WARNING: There is more than one gen_receives: "+str(gen_receives))
        gen_receive = gen_receives[0]
    else:
        gen_receive, c = Ocp_Record_Type.objects.get_or_create(
            name_en="Receive gift:",
            parent=gen_gift)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_receive))
    gen_receive.name_en = "Receive gift:"
    gen_receive.parent = gen_gift
    gen_receive.description = "Branch of exchange types only used when there's no way to identify the sending 'from' agent in the system"
    gen_receive.save()

    gen_recnons = Ocp_Record_Type.objects.filter(name_en__icontains="receive Non-material resources")
    if gen_recnons:
        if len(gen_recnons) > 1:
            print("WARNING: There is more than one gen_recnons: "+str(gen_recnons))
        gen_recnon = gen_recnons[0]
    else:
        gen_recnon, c = Ocp_Record_Type.objects.get_or_create(
            name_en="receive Non-material resources",
            parent=gen_receive)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_recnon))
    gen_recnon.name_en = "receive Non-material resources"
    gen_recnon.parent = gen_receive
    gen_recnon.ocpRecordType_ocp_artwork_type = nonmat_typ
    gen_recnon.save()

    gen_recfairs = Ocp_Record_Type.objects.filter(name_en__icontains="receive Faircoin donation")
    if not gen_recfairs:
        gen_recfairs = Ocp_Record_Type.objects.filter(name_en__icontains="receive Faircoin")
    if gen_recfairs:
        if len(gen_recfairs) > 1:
            print("WARNING: Theres is more than one gen_recfairs: "+str(gen_recfairs))
        gen_recfair = gen_recfairs[0]
    else:
        gen_recfair, c = Ocp_Record_Type.objects.get_or_create(
            name_en="receive Faircoin donation",
            parent=gen_recnon)
        if c:
            print("- created Ocp_Record_Type: "+str(gen_recfair))
    gen_recfair.name_en = "receive Faircoin donation"
    gen_recfair.parent = gen_recnon
    gen_recfair.ocpRecordType_ocp_artwork_type = fair_rt
    gen_recfair.exchange_type = incfairet
    gen_recfair.save()





    #    E u r o s

    ocp_euros = Unit.objects.filter(name='Euro')
    if ocp_euros:
        if len(ocp_euros) > 1:
            print("ERROR: More than one Unit named 'Euro'!! please delete the non-used one and retry: "+str(ocp_euros))
            if len(ocp_euros) == 2:
                if ocp_euros[0].id < ocp_euros[1].id:
                    print("DELETED the more recent Unit: "+str(ocp_euros[1]))
                    ocp_euros[1].delete()
                    ocp_euro = ocp_euros[0]
            #raise ValidationError("ERROR: More than one Unit named 'Euro'!! please delete the non-used one and retry"+str(ocp_euros))
        else:
            ocp_euro = ocp_euros[0]
    else:
        ocp_euro, created = Unit.objects.get_or_create(
            name='Euro',
            unit_type='value',
            abbrev='eur'
        )
        if created:
            print("- created Unit: 'Euro'")
    ocp_euro.name = 'Euro'
    ocp_euro.unit_type = 'value'
    ocp_euro.abbrev = 'eur'
    ocp_euro.symbol = '€'
    ocp_euro.save()

    gen_fiat_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Fiat Currency',
        parent=gen_curr_typ
    )
    if created:
        print("- created Ocp_Unit_Type: 'Fiat Currency'")

    gen_euro_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name_en='Euros',
        parent=gen_fiat_typ
    )
    if created:
        print("- created Ocp_Unit_Type: 'Euros'")
    gen_euro_typ.clas = 'euro'
    gen_euro_typ.save()

    euros = Gene_Unit.objects.filter(name='Euro')
    if not euros:
        euro, created = Gene_Unit.objects.get_or_create(
            name='Euro',
            code='€'
        )
        if created:
            print("- created General.Unit for Euros: 'Euro'")
    else:
        euro = euros[0]
    euro.code = '€'
    euro.unit_type = gen_euro_typ
    euro.ocp_unit = ocp_euro
    euro.save()

    ocp_euro_rts = EconomicResourceType.objects.filter(name__icontains='Euro')
    if len(ocp_euro_rts) == 1:
        if ocp_euro_rts[0].name == 'Euro':
            digi_rt = ocp_euro_rts[0]
            digi_rt.name = 'Euro digital'
            digi_rt.save()
        else:
            raise ValidationError("There is only one rt related Euro but is not 'Euro': "+str(ocp_euro_rts[0]))
    elif len(ocp_euro_rts) > 1:
        digi_rt = ocp_euro_rts.get(name_en='Euro digital')
        if not digi_rt:
            raise ValidationError("Can't find a ResourceType named 'Euro digital' rts: "+str(ocp_euro_rts))
        digi_rt.unit = ocp_euro
        digi_rt.unit_of_use = ocp_euro
        #digi_rt.unit_of_value = ocp_euro
        #digi_rt.value_per_unit = 1
        #digi_rt.value_per_unit_of_use = 1
        digi_rt.price_per_unit = 1
        digi_rt.unit_of_price = ocp_euro
        digi_rt.substitutable = True
        digi_rt.inventory_rule = 'yes'
        digi_rt.behavior = 'dig_curr'
        digi_rt.save()
        cash_rt = ocp_euro_rts.get(name_en='Euro cash')
        if not cash_rt:
            raise ValidationError("Can't find a ResourceType named 'Euro cash' rts: "+str(ocp_euro_rts))
        cash_rt.unit = ocp_euro
        cash_rt.unit_of_use = ocp_euro
        #cash_rt.unit_of_value = ocp_euro
        #cash_rt.value_per_unit = 1
        #cash_rt.value_per_unit_of_use = 1
        cash_rt.price_per_unit = 1
        cash_rt.unit_of_price = ocp_euro
        cash_rt.substitutable = True
        cash_rt.inventory_rule = 'yes'
        cash_rt.behavior = 'other'
        cash_rt.save()
    else:
        digi_rt, created = EconomicResourceType.objects.get_or_create(
            name_en='Euro digital',
            unit=ocp_euro,
            unit_of_use=ocp_euro,
            price_per_unit = 1,
            unit_of_price=ocp_euro,
            substitutable=True,
            inventory_rule='yes',
            behavior='dig_curr')
        if created:
            print("- created EconomicResourceType: 'Euro digital'")
        cash_rt, created = EconomicResourceType.objects.get_or_create(
            name_en='Euro cash',
            unit=ocp_euro,
            unit_of_use=ocp_euro,
            price_per_unit=1,
            unit_of_price=ocp_euro,
            substitutable=True,
            inventory_rule='yes',
            behavior='other')
        if created:
            print("- created EconomicResourceType: 'Euro cash'")

        #raise ValidationError("There are not ResourceTypes containing 'Euro' in the name!: "+str(ocp_euro_rts))


    artw_euros = Ocp_Artwork_Type.objects.filter(name__icontains="Euro")
    if len(artw_euros) > 1:
        digi = artw_euros.get(name_en='Euro digital')
        if digi:
            digi.clas = 'euro_digital'
            digi.resource_type = digi_rt
            digi.general_unit_type = gen_euro_typ
            digi.save()
        else:
            raise ValidationError("Can't find an Ocp_Artwork_Type named 'Euro digital' artw: "+str(artw_euros))
        cash = artw_euros.get(name_en='Euro cash')
        if cash:
            cash.clas = 'euro_cash'
            cash.resource_type = cash_rt
            cash.general_unit_type = gen_euro_typ
            cash.save()
        else:
            raise ValidationError("Can't find an Ocp_Artwork_Type named 'Euro cash' artw: "+str(artw_euros))
    elif len(artw_euros) == 1:
        raise ValidationError("There is only one Ocp_Artwork_Type containing 'Euro' in the name (should find 'Euro digital' and 'Euro cash': "+str(artw_euros))
    else:
        #raise ValidationError("There are not 2 Ocp_Artwork_Types containing 'Euro' in the name (should find 'Euro digital' and 'Euro cash': "+str(artw_euros))

        digi, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Euro digital',
            parent=digcur_typ,
        )
        if created:
            print("- created Ocp_Artwork_Type: 'Euro digital'")
        digi.clas='euro_digital'
        digi.resource_type = digi_rt
        digi.general_unit_type = gen_euro_typ
        digi.save()


        mat_typs = Ocp_Artwork_Type.objects.filter(clas='Material')
        if mat_typs:
            if len(mat_typs) > 1:
                raise ValidationError("There are more than one Ocp_Artwork_Type with clas 'Material' ?!")
            mat_typ = mat_typs[0]
        else:
            mat_typ, created = Ocp_Artwork_Type.objects.get_or_create(
                name_en='Material',
                parent=gen_artwt,
                clas='Material')
            if created:
                print("- created Ocp_Artwork_Type: 'Material'")

        phycur_typs = Ocp_Artwork_Type.objects.filter(name_en='physical Currencies')
        if not phycur_typs:
            phycur_typ, created = Ocp_Artwork_Type.objects.get_or_create(
                name_en='physical Currencies',
                parent=mat_typ)
            if created:
                print("- created Ocp_Artwork_Types: 'physical Currencies'")
        else:
            phycur_typ = phycur_typs[0]
        phycur_typ.clas = 'currency'
        phycur_typ.save()

        cash, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Euro cash',
            parent=phycur_typ)
        if created:
            print("- created Ocp_Artwork_Type: 'Euro cash'")
        cash.clas = 'euro_cash'
        cash.resource_type = cash_rt
        cash.general_unit_type = gen_euro_typ
        cash.save()



    print("- "+str(digi_rt)+" FV's: "+str([fv.facet_value.value+', ' for fv in digi_rt.facets.all()]))
    print("- "+str(cash_rt)+" FV's: "+str([fv.facet_value.value+', ' for fv in cash_rt.facets.all()]))

    # euro digi FV
    for fv in digi_rt.facets.all():
        if not fv.facet_value == fiatfv and not fv.facet_value == fvmoney:
            print("- deleted: "+str(fv))
            fv.delete()
    digi_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=digi_rt,
        facet_value=fiatfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(digi_rtfv))

    digi_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=digi_rt,
        facet_value=fvmoney)
    if created:
        print("- created ResourceTypeFacetValue: "+str(digi_rtfv))

    # euro cash FV
    for fv in cash_rt.facets.all():
        if not fv.facet_value == fiatfv and not fv.facet_value == fvmoney:
            print("- deleted: "+str(fv))
            fv.delete()
    cash_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=cash_rt,
        facet_value=fiatfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(cash_rtfv))

    cash_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=cash_rt,
        facet_value=fvmoney)
    if created:
        print("- created ResourceTypeFacetValue: "+str(cash_rtfv))



    # Check UnitRatio eur-fair
    urs = UnitRatio.objects.filter(in_unit=euro, out_unit=fair)
    if not urs:
        urs = UnitRatio.objects.filter(in_unit=fair, out_unit=euro)
    if not urs:
        ur, c = UnitRatio.objects.get_or_create(
            in_unit=euro,
            out_unit=fair,
            rate=decimal.Decimal('1.2')
        )
        if c:
            print("- created UnitRatio: "+str(ur))
            #loger.info("- created UnitRatio: "+str(ur))
    elif len(urs) == 1:
        ur = urs[0]
    else:
        print("x More than one UnitRatio with euro and fair? "+str(urs))
        loger.warning("x More than one UnitRatio with euro and fair? "+str(urs))
    ur.in_unit = euro
    ur.out_unit = fair
    ur.rate = decimal.Decimal('1.2')
    ur.save()



    #   C r y p t o s   B i t c o i n

    ocp_btc, created = Unit.objects.get_or_create(name='Bitcoin', unit_type='value')
    if created:
        print("- created a main ocp Unit: 'Bitcoin'")
    ocp_btc.abbrev = 'btc'
    ocp_btc.unit_type = 'value'
    ocp_btc.save()

    gen_btc_typ, created = Ocp_Unit_Type.objects.get_or_create(
        name='Bitcoins',
        parent=gen_crypto_typ
    )
    if created:
        print("- created Ocp_Unit_Type: 'Bitcoins'")
    gen_btc_typ.clas = 'bitcoin'
    gen_btc_typ.save()

    btcs = Gene_Unit.objects.filter(name='Bitcoin')
    if not btcs:
        btc, created = Gene_Unit.objects.get_or_create(
            name='Bitcoin',
            code='btc'
        )
        if created:
            print("- created General.Unit for Bitcoin: 'Bitcoin'")
    else:
        btc = btcs[0]
    btc.code = 'btc'
    btc.unit_type = gen_btc_typ
    btc.ocp_unit = ocp_btc
    btc.save()

    ocp_btc_rts = EconomicResourceType.objects.filter(name='Bitcoin')
    if not ocp_btc_rts:
        ocp_btc_rt, created = EconomicResourceType.objects.get_or_create(
            name='Bitcoin')
        if created:
            print("- created EconomicResourceType: 'Bitcoin'")
    else:
        ocp_btc_rt = ocp_btc_rts[0]
    ocp_btc_rt.unit = ocp_btc
    ocp_btc_rt.unit_of_use = ocp_btc
    #ocp_btc_rt.unit_of_value = ocp_fair
    #ocp_btc_rt.value_per_unit = 1
    #ocp_btc_rt.value_per_unit_of_use = 1
    ocp_btc_rt.price_per_unit = 1
    ocp_btc_rt.unit_of_price = ocp_btc
    ocp_btc_rt.substitutable = True
    ocp_btc_rt.inventory_rule = 'yes'
    ocp_btc_rt.behavior = 'dig_curr'
    ocp_btc_rt.save()

    for fv in ocp_btc_rt.facets.all():
        if not fv.facet_value == cryptfv and not fv.facet_value == fvmoney:
            print("- deleted: "+str(fv))
            fv.delete()
    ocp_btc_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=ocp_btc_rt,
        facet_value=cryptfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(ocp_btc_rtfv))

    ocp_btc_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=ocp_btc_rt,
        facet_value=fvmoney)
    if created:
        print("- created ResourceTypeFacetValue: "+str(ocp_btc_rtfv))


    btc_rts = Ocp_Artwork_Type.objects.filter(name='Bitcoin')
    if not btc_rts:
        btc_rt, created = Ocp_Artwork_Type.objects.get_or_create(
            name='Bitcoin',
            parent=digcur_typ)
        if created:
            print("- created Ocp_Artwork_Types: 'Bitcoin'")
    else:
        btc_rt = btc_rts[0]
    btc_rt.clas = 'btc_digital'
    btc_rt.resource_type = ocp_btc_rt
    btc_rt.general_unit_type = gen_btc_typ
    btc_rt.save()



    #   S h a r e s

    gen_share_typs = Ocp_Unit_Type.objects.filter(name_en='Shares')
    if not gen_share_typs:
        gen_share_typs = Ocp_Unit_Type.objects.filter(name_en='Shares currency')
    if not gen_share_typs:
        gen_share_typ, created = Ocp_Unit_Type.objects.get_or_create(
            name_en='Shares currency',
            parent=gen_curr_typ)
        if created:
            print("- created Ocp_Unit_Type: 'Shares currency'")
    else:
        gen_share_typ = gen_share_typs[0]
    gen_share_typ.name_en = 'Shares currency'
    gen_share_typ.parent = gen_curr_typ
    gen_share_typ.clas = 'shares_currency'
    gen_share_typ.save()


    artw_share = Ocp_Artwork_Type.objects.filter(name_en='Share')
    if not artw_share:
        artw_share = Ocp_Artwork_Type.objects.filter(name_en='Shares')
    if not artw_share:
        artw_sh, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Shares',
            parent=digcur_typ)
        if created:
            print("- created Ocp_Artwork_Type branch: 'Shares'")
    else:
        artw_sh = artw_share[0]
    artw_sh.name_en = 'Shares'
    artw_sh.clas = 'shares'
    artw_sh.parent = digcur_typ
    artw_sh.resource_type = None
    artw_sh.general_unit_type = gen_share_typ
    artw_sh.save()



    ## FreedomCoop

    fdc_ag = EconomicAgent.objects.filter(nick="Freedom Coop")
    if not fdc_ag:
        fdc_ag = EconomicAgent.objects.filter(nick="FreedomCoop")
    if not fdc_ag:
        print("- WARNING: the FreedomCoop agent don't exist, not created any unit for shares")
        return
    else:
        fdc_ag = fdc_ag[0]

    ocp_shares = Unit.objects.filter(name_en='Share')
    if not ocp_shares:
        ocp_shares = Unit.objects.filter(name_en='FreedomCoop Share')
    if not ocp_shares:
        ocp_share, created = Unit.objects.get_or_create(
            name_en='FreedomCoop Share',
            unit_type='value',
            abbrev='FdC'
        )
        if created:
            print("- created OCP Unit: 'FreedomCoop Share'")
    else:
        ocp_share = ocp_shares[0]
    ocp_share.name_en = 'FreedomCoop Share'
    ocp_share.unit_type = 'value'
    ocp_share.abbrev = 'FdC'
    ocp_share.save()

    gen_fdc_typs = Ocp_Unit_Type.objects.filter(name_en='FreedomCoop Shares')
    if not gen_fdc_typs:
        gen_fdc_typ, created = Ocp_Unit_Type.objects.get_or_create(
            name_en='FreedomCoop Shares',
            parent=gen_share_typ)
        if created:
            print("- created Ocp_Unit_Type: 'FreedomCoop Shares'")
    else:
        gen_fdc_typ = gen_fdc_typs[0]
    gen_fdc_typ.clas = 'freedom-coop_shares'
    gen_fdc_typ.save()

    fdc_share, created = Gene_Unit.objects.get_or_create(
        name='FreedomCoop Share',
        code='FdC')
    if created:
        print("- created General.Unit: 'FreedomCoop Share'")
    fdc_share.code = 'FdC'
    fdc_share.unit_type = gen_fdc_typ
    fdc_share.ocp_unit = ocp_share
    fdc_share.save()

    ocp_share_rts = EconomicResourceType.objects.filter(name_en='FreedomCoop Share')
    if not ocp_share_rts:
        ocp_share_rts = EconomicResourceType.objects.filter(name_en='Membership Share')
    if not ocp_share_rts:
        ocp_share_rts = EconomicResourceType.objects.filter(name_en='Share')
    if ocp_share_rts:
        if len(ocp_share_rts) > 1:
            raise ValidationError("There's more than one 'FreedomCoop Share' ?? "+str(ocp_share_rts))
        share_rt = ocp_share_rts[0]
    else:
        share_rt, created = EconomicResourceType.objects.get_or_create(
            name_en='FreedomCoop Share')
        if created:
            print("- created EconomicResourceType: 'FreedomCoop Share'")
    share_rt.name_en = 'FreedomCoop Share'
    share_rt.unit = ocp_share
    share_rt.inventory_rule = 'yes'
    share_rt.behavior = 'other'
    share_rt.context_agent = fdc_ag
    if not share_rt.price_per_unit:
        print("- Added first FdC share price to 30 eur")
        share_rt.price_per_unit = 30
    elif not share_rt.price_per_unit == 30:
        check_new_rt_price(share_rt)
    share_rt.unit_of_price = ocp_euro
    share_rt.save()

    for fv in share_rt.facets.all():
        if not fv.facet_value == shrfv:
            print("- delete: "+str(fv))
            fv.delete()
    share_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=share_rt,
        facet_value=shrfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(share_rtfv))


    artw_fdcs = Ocp_Artwork_Type.objects.filter(name_en="Share")
    if not artw_fdcs:
        artw_fdcs = Ocp_Artwork_Type.objects.filter(name_en="Membership Share")
    if not artw_fdcs:
        artw_fdcs = Ocp_Artwork_Type.objects.filter(name_en="FreedomCoop Share")
    if artw_fdcs:
        artw_fdc = artw_fdcs[0]
    else:
        artw_fdc, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='FreedomCoop Share',
            parent = Type.objects.get(id=artw_sh.id)
        )
        if created:
            print("- created Ocp_Artwork_Type: 'FreedomCoop Share'")
    artw_fdc.parent = Type.objects.get(id=artw_sh.id)
    artw_fdc.resource_type = share_rt
    artw_fdc.general_unit_type = Unit_Type.objects.get(id=gen_fdc_typ.id)
    artw_fdc.save()


    arrts = AgentResourceRoleType.objects.filter(is_owner=True)
    if len(arrts) > 1:
        for ar in arrts:
            print("WARN! More than one is_owner? "+str(ar))
            if ar.name_en == 'Owner':
                arrt = ar
    elif arrts:
        arrt = arrts[0]
    else:
        arrt, c = AgentResourceRoleType.objects.get_or_create(name='Owner', is_owner=True)
        if c: print("- created AgentResourceRoleType: "+str(arrt))


    ## BankOfTheCommons

    """boc_ag = EconomicAgent.objects.filter(nick="BoC")
    if not boc_ag:
        boc_ag = EconomicAgent.objects.filter(nick="BotC")
    if not boc_ag:
        print("- WARNING: the BotC agent don't exist, not created any unit for shares")
        return
    else:
        boc_ag = boc_ag[0]

    ocpboc_shares = Unit.objects.filter(name_en='BankOfTheCommons Share')
    if not ocpboc_shares:
        ocpboc_share, created = Unit.objects.get_or_create(
            name='BankOfTheCommons Share',
            unit_type='value',
            abbrev='BotC'
        )
        if created:
            print("- created OCP Unit: 'BankOfTheCommons Share (BotC)'")
    else:
        ocpboc_share = ocpboc_shares[0]
    ocpboc_share.name = 'BankOfTheCommons Share'
    ocpboc_share.unit_type = 'value'
    ocpboc_share.abbrev = 'BotC'
    ocpboc_share.save()

    gen_boc_typs = Ocp_Unit_Type.objects.filter(name_en='BankOfTheCommons Shares')
    if not gen_boc_typs:
        gen_boc_typ, created = Ocp_Unit_Type.objects.get_or_create(
            name='BankOfTheCommons Shares',
            parent=gen_share_typ)
        if created:
            print("- created Ocp_Unit_Type: 'BankOfTheCommons Shares'")
    else:
        gen_boc_typ = gen_boc_typs[0]
    gen_boc_typ.clas = 'bank-of-the-commons_shares'
    gen_boc_typ.save()


    boc_share, created = Gene_Unit.objects.get_or_create(
        name='BankOfTheCommons Share',
        code='BotC')
    if created:
        print("- created General.Unit: 'BankOfTheCommons Share'")
    boc_share.code = 'BotC'
    boc_share.unit_type = gen_boc_typ
    boc_share.ocp_unit = ocpboc_share
    boc_share.save()

    share_rts = EconomicResourceType.objects.filter(name_en__icontains="BankOfTheCommons Share").exclude(name_en__icontains="Account")
    if not share_rts:
        share_rts = EconomicResourceType.objects.filter(name_en__icontains="Bank of the Commons Share").exclude(name_en__icontains="Account")
    if share_rts:
        if len(share_rts) > 1:
            raise ValidationError("There are more than 1 EconomicResourceType named: 'BankOfTheCommons Share'")
        share_rt = share_rts[0]
    else:
        share_rt, created = EconomicResourceType.objects.get_or_create(
            name='Bank of the Commons Share',
            unit=ocp_each,
            inventory_rule='yes',
            behavior='other'
        )
        if created:
            print("- created EconomicResourceType: 'Bank of the Commons Share'")
    share_rt.name = "Bank of the Commons Share"
    share_rt.unit = ocpboc_share
    share_rt.inventory_rule = 'yes'
    share_rt.behavior = 'other'
    share_rt.context_agent = boc_ag
    share_rt.price_per_unit = 1
    share_rt.unit_of_price = ocp_euro
    share_rt.save()

    for fv in share_rt.facets.all():
        if not fv.facet_value == shrfv:
            print("- delete: "+str(fv))
            fv.delete()
    share_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=share_rt,
        facet_value=shrfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(share_rtfv))

    artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains="BankOfTheCommons Share").exclude(name_en__icontains="Account")
    if not artw_bocs:
        artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains="Bank of the Commons Share").exclude(name_en__icontains="Account")
    if artw_bocs:
        if len(artw_bocs) > 1:
            raise ValidationError("There are more than 1 Ocp_Artwork_Type named: 'BankOfTheCommons Share' ")
        artw_boc = artw_bocs[0]
    else:
        artw_boc, created = Ocp_Artwork_Type.objects.get_or_create(
            name='Bank of the Commons Share',
            parent=Type.objects.get(id=artw_sh.id)
        )
        if created:
            print("- created Ocp_Artwork_Type: 'Bank of the Commons Share'")
    artw_boc.name = "Bank of the Commons Share"
    artw_boc.parent = Type.objects.get(id=artw_sh.id)
    artw_boc.resource_type = share_rt
    artw_boc.general_unit_type = Unit_Type.objects.get(id=gen_boc_typ.id)
    artw_boc.save()"""


    print("...end of the units analisys.")


#post_migrate.connect(create_unit_types, sender=WorkAppConfig)



def rebuild_trees(**kwargs):
    uts = Unit_Type.objects.rebuild()
    print("rebuilded Unit_Type")

#post_migrate.connect(rebuild_trees)



from general.models import Relation

def create_exchange_skills(**kwargs):
    doin, created = Ocp_Skill_Type.objects.get_or_create(
        name="Doing", verb="to do", gerund="doing"
    )
    if created:
        print("Created main skill type: Doing")
    x_act, created = Ocp_Skill_Type.objects.get_or_create(
        name="Exchanging", verb="to exchange", gerund="exchanging", clas='exchange',
        parent=doin
    )
    if created:
        print("Created skill type: Exchanging")
    give, created = Ocp_Skill_Type.objects.get_or_create(
        name="Give", verb="to give", gerund="giving", clas='give',
        parent=x_act
    )
    if created:
        print("Created skill type: Give")
    receive, created = Ocp_Skill_Type.objects.get_or_create(
        name="Receive", verb="to receive", gerund="receiving", clas='receive',
        parent=x_act
    )
    if created:
        print("Created skill type: Receive")
    sell, created = Ocp_Skill_Type.objects.get_or_create(
        name="Sell", verb="to sell", gerund="selling", clas='sell',
        parent=x_act
    )
    if created:
        print("Created skill type: Sell")
    buy, created = Ocp_Skill_Type.objects.get_or_create(
        name="Buy", verb="to buy", gerund="buying", clas='buy',
        parent=x_act
    )
    if created:
        print("Created skill type: Buy")



    jjob, created = Relation.objects.get_or_create(
        name=":Relation Job-Job",
        clas="rel_job_jobs"
    )
    if created:
        print("Created the main Job-Job relation branch")
    oppose, created = Relation.objects.get_or_create(
        name="opposes", verb="to oppose", clas='oppose',
        parent=jjob
    )
    if created:
        print("Created the opposing relation")


    rel, created = give.rel_jobs1.get_or_create(
        job1=give, job2=receive, relation=oppose)
    if created:
        print("Created the Relation give<>receive")
    rel, created = receive.rel_jobs1.get_or_create(
        job1=receive, job2=give, relation=oppose)
    if created:
        print("Created the Relation receive<>give")
    rel, created = sell.rel_jobs1.get_or_create(
        job1=sell, job2=buy, relation=oppose)
    if created:
        print("Created the Relation sell<>buy")
    rel, created = buy.rel_jobs1.get_or_create(
        job1=buy, job2=sell, relation=oppose)
    if created:
        print("Created the Relation buy<>sell")


#post_migrate.connect(create_exchange_skills, sender=WorkAppConfig)



def check_new_rt_price(rt=None, **kwargs):
    if not rt:
        return
    exs = []
    coms = rt.commitments.all()
    evts = rt.events.all()

    pro = sht = None
    if rt.context_agent:
        if hasattr(rt.context_agent, 'project') and rt.context_agent.project:
            pro = rt.context_agent.project
            jrs = pro.join_requests.all()
            for jr in jrs:
                #print(" : jr:"+str(jr.id)+" "+str(jr))
                if jr.exchange:
                    #print(" : : ex:"+str(jr.exchange))
                    exs.append(jr.exchange)
    else:
        print("check_new_rt_price: No rt.context_agent?? rt:"+str(rt))
        loger.error("check_new_rt_price: No rt.context_agent?? rt:"+str(rt))

    if pro:
        sht = pro.shares_type()
        if not sht:
            print("check_new_rt_price: No Project Share Type?? rt:"+str(rt))
            loger.error("check_new_rt_price: No Project Share Type?? rt:"+str(rt))
    else:
        print("check_new_rt_price: No Project?? rt:"+str(rt))
        loger.error("check_new_rt_price: No Project?? rt:"+str(rt))

    print("check_new_rt_price: rt:"+str(rt.id)+" "+str(rt)+", price_per_unit:"+str(rt.price_per_unit)+" coms:"+str(len(coms))+" evts:"+str(len(evts))+" ca:"+str(rt.context_agent)+" sht:"+str(sht))
    loger.info("check_new_rt_price... rt:"+str(rt.id)+" "+str(rt)+", price_per_unit:"+str(rt.price_per_unit)+" coms:"+str(len(coms))+" evts:"+str(len(evts))+" ca:"+str(rt.context_agent)+" sht:"+str(sht))


    if not sht == rt:
        print(":: rt is not the share_type of the project? rt:"+str(rt)+" <> "+str(sht)+" pro:"+str(pro)+" rt.ca:"+str(rt.context_agent))
        return
    #exs = rt.context_agent.exchanges.all()
    for ex in exs:
        #print(": : ex:"+str(ex.id)+" "+str(ex))
        txpay = ex.txpay()
        for tx in ex.transfers.all():
            if tx == txpay:
                cms = tx.commitments.all()
                evs = tx.events.all()
                #print(" : tx:"+str(tx.id)+" qty:"+str(tx.quantity())+" u:"+str(tx.unit_of_quantity())+" rt:"+str(tx.resource_type())+" cms:"+str(len(cms))+" evs:"+str(len(evs))+" "+str(tx))
                if cms and not evs:
                    for cm in cms:
                        jrpend = jrpend2 = ex.join_request.payment_pending_amount()
                        jrunit = ex.join_request.payment_unit()
                        jrurt = ex.join_request.payment_unit_rt()
                        #print(" : : cm:"+str(cm.id)+" rt:"+str(cm.resource_type)+" qty:"+str(cm.quantity)+" uq:"+str(cm.unit_of_quantity)+" jrpend:"+str(jrpend))
                        if jrunit == cm.unit_of_quantity and cm.resource_type == jrurt:
                            if not round(cm.quantity, 2) == round(jrpend, 2):
                                print("- changed commitment quantity of "+str(round(cm.quantity, 2))+" for "+str(round(jrpend, 2))+" because share price has changed. Pro:"+str(pro.agent)+" cm:"+str(cm.id)+" tx:"+str(tx.id)+" ex:"+str(ex.id))
                                loger.info("- changed commitment quantity of "+str(round(cm.quantity, 2))+" for "+str(round(jrpend, 2))+" because share price has changed. Pro:"+str(pro.agent)+" cm:"+str(cm.id)+" tx:"+str(tx.id)+" ex:"+str(ex.id))
                                cm.quantity = jrpend2
                                cm.save()


    for ev in evts:
        if not ev.exchange:
          if ev.transfer:
            if ev.transfer.exchange:
                ev.exchange = ev.transfer.exchange
                ev.save()
                print(":: FIXED missing exchange:"+str(ev.exchange.id)+" for event:"+str(ev.id)+" "+str(ev))
                loger.info(":: FIXED missing exchange:"+str(ev.exchange.id)+" for event:"+str(ev.id)+" "+str(ev))
            else:
                print(":: Orphan event.transfer? tx:"+str(ev.transfer.id)+": "+str(ev.transfer))
                loger.info(":: Orphan event.transfer? tx:"+str(ev.transfer.id)+": "+str(ev.transfer))
          else:
            print(":: Orphan event ?? "+str(ev.id)+" "+str(ev))
            loger.info(":: Orphan event ?? "+str(ev.id)+" "+str(ev))

        #print(":: ev:"+str(ev.id)+" tx:"+str(ev.transfer.id)+" ex:"+str(ev.exchange)+" com:"+str(ev.commitment))

        if ev.commitment and not ev.commitment in coms:
            print(":: add ev.comm not in coms: "+str(ev.commitment))
            loger.info(":: add ev.comm not in coms: "+str(ev.commitment))

        txpay = ev.exchange.txpay()
        for tx in ev.exchange.transfers.all():
            if tx == txpay:
                pass #print("::: found txpay: "+str(tx))

    return


"""
def migrate_freedomcoop_memberships(**kwargs):
    fdc = Project.objects.filter(fobi_slug='freedom-coop')
    if fdc:
        fdc = fdc[0].agent
    if fdc:
        form_entry = None
        try:
            form_entry = FormEntry.objects.get(slug=fdc.project.fobi_slug)
        except:
            pass
        if form_entry:
            form_element_entries = form_entry.formelemententry_set.all()[:]

        else:
            print("FdC migration error: no form entries")

        old_reqs = MembershipRequest.objects.all()
        new_reqs = fdc.project.join_requests.all()
        print("FdC reqs: old-"+str(len(old_reqs))+" <> new-"+str(len(new_reqs)))
        for orq in old_reqs:
            nrq, created = JoinRequest.objects.get_or_create(
                project=fdc.project,
                request_date=orq.request_date,
                type_of_user=orq.type_of_membership,
                name=orq.name,
                surname=orq.surname,
                requested_username=orq.requested_username,
                email_address=orq.email_address,
                phone_number=orq.phone_number,
                address=orq.address,
                agent=orq.agent,
                state=orq.state
            )
            if created:
                print("created FdC JoinRequest: "+nrq.requested_username+" ("+nrq.email_address+")")

post_migrate.connect(migrate_freedomcoop_memberships)
"""
