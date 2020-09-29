import sys
import datetime
from decimal import *
from collections import OrderedDict

import bleach
from captcha.fields import CaptchaField

from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from valuenetwork.valueaccounting.models import *
from work.models import *
from valuenetwork.valueaccounting.forms import *
from account.forms import LoginForm
from general.models import Unit_Type

from django.shortcuts import get_object_or_404

#from general.models import Record_Type, Material_Type, Nonmaterial_Type, Artwork_Type
from mptt.forms import TreeNodeChoiceField
from work.utils import *




#     P R O F I L E


class WorkAgentCreateForm(AgentCreateForm):
    # override fields for EconomicAgent model
    agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.all(), #filter(is_context=False),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))

    is_context = None # projects are always context_agents, hide the field
    #nick = None
    # fields for Project model
    #joining_style = forms.ChoiceField()
    #visibility = forms.ChoiceField()

    def __init__(self, agent=None, *args, **kwargs):
        super(WorkAgentCreateForm, self).__init__(*args, **kwargs)
        if agent:
            #print("- agent: "+str(agent)+' - context? '+str(agent.agent_type.is_context))
            if agent.agent_type.is_context:
                self.fields["agent_type"].queryset = AgentType.objects.filter(is_context=True)
                self.fields["agent_type"].initial = agent.agent_type
            else:
                self.fields["agent_type"].queryset = AgentType.objects.filter(is_context=False)
                self.fields["agent_type"].initial = agent.agent_type
        else:
            self.fields["agent_type"].queryset = AgentType.objects.filter(is_context=True)
        #self.fields["joining_style"].choices = [(js[0], js[1]) for js in JOINING_STYLE_CHOICES]
        #self.fields["visibility"].choices = [(vi[0], vi[1]) for vi in VISIBILITY_CHOICES]


    class Meta: #(AgentCreateForm.Meta):
        model = EconomicAgent
        #removed address and is_context
        fields = ('name', 'nick', 'agent_type', 'description', 'url', 'email', 'phone_primary',)
        #exclude = ('is_context',)

    def clean(self):
        data = super(WorkAgentCreateForm, self).clean()
        nick = data["nick"]
        name = data["name"]
        email = data['email']
        if nick and name and email:
            ags = EconomicAgent.objects.filter(nick=nick).exclude(email=email).exclude(name=name)
            if ags:
                #print("- ERROR nick present! ")
                self.add_error('nick', _("This nickname is already present in the system."))
            ags = EconomicAgent.objects.filter(name=name).exclude(email=email).exclude(nick=nick)
            if ags:
                #print("- ERROR name present! ")
                self.add_error('name', _("This name is already present in the system."))
            ags = EconomicAgent.objects.filter(email=email).exclude(nick=nick).exclude(name=name)
            if ags and not self.instance.is_context:
                #print("- ERROR email present! ")
                self.add_error('email', _("This email is already present in the system."))
        else:
            if not email:
                pass
            else:
                pass #print("- ERROR clean WorkAgentCreateForm ! data: "+str(data))


    def _clean_fields(self):
        super(WorkAgentCreateForm, self)._clean_fields()
        for name, value in list(self.cleaned_data.items()):
            pass #self.cleaned_data[name] = bleach.clean(value)



class UploadAgentForm(forms.ModelForm):
    photo_url = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}))

    class Meta:
        model = EconomicAgent
        fields = ('photo', 'photo_url')



class SkillSuggestionForm(forms.ModelForm):
    skill = forms.CharField(
        label = "Other",
        help_text = _("Your skill suggestions will be sent to Freedom Coop Admins"),
        )

    class Meta:
        model = SkillSuggestion
        fields = ('skill',)


class AddUserSkillForm(forms.Form):
    skill_type = TreeNodeChoiceField(
        queryset=Ocp_Skill_Type.objects.all(),
        empty_label=None,
        level_indicator='. ',
        required=False,
        widget=forms.Select(
          attrs={'class': 'id_skill_type chzn-select',
                     'multiple':'',
                     'data-placeholder':_("search Skill type...")}
        )
    )

    def __init__(self, agent, *args, **kwargs):
        super(AddUserSkillForm, self).__init__(*args, **kwargs)
        if agent:
            context_ids = [c.id for c in agent.related_all_agents()]
            if not agent.id in context_ids:
                context_ids.append(agent.id)
            self.fields["skill_type"].queryset = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')




#     M E M B E R S H I P


class MembershipRequestForm(forms.ModelForm):
    if settings.TESTING:
        captcha = None
    else:
        captcha = CaptchaField(help_text=_("Is a math operation: Please put the result (don't copy the symbols)"))

    class Meta:
        model = MembershipRequest
        exclude = ('agent', 'state',)

    def clean(self):
        data = super(MembershipRequestForm, self).clean()
        type_of_membership = data["type_of_membership"]
        number_of_shares = data["number_of_shares"]
        if type_of_membership == "collective":
            if int(number_of_shares) < 2:
                msg = "Number of shares must be at least 2 for a collective."
                self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(MembershipRequestForm, self)._clean_fields()
        for name, value in list(self.cleaned_data.items()):
            self.cleaned_data[name] = bleach.clean(value)





#     P R O J E C T


class ProjectCreateForm(forms.ModelForm):
    # override fields for EconomicAgent model
    '''agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.filter(is_context=True),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))

    is_context = None # projects are always context_agents, hide the field
    '''

    # fields for Project model
    joining_style = forms.ChoiceField(widget=forms.Select(
        attrs={'class': 'chzn-select'}))
    auto_create_pass = forms.BooleanField(
        required = False,
        label = _("&nbsp;Auto create user+agent and confirm email:"),
        help_text="For 'moderated' joining style:<br>- If you want to manually control which requests don't seem spam (recommended) before creating their user+agent and confirm the email, leave this unchecked. <br>- If you don't expect spam registers, check this to speed up the process.",
    )
    visibility = forms.ChoiceField(widget=forms.Select(
        attrs={'class': 'chzn-select'}))
    resource_type_selection = forms.ChoiceField(label=_("Resource type visibility:"), widget=forms.Select(
        attrs={'class': 'chzn-select'}))
    fobi_slug = forms.CharField(
        required = False,
        label = _("Custom project url slug:"),
        help_text = _("Used to reach your custom join form, but after the custom fields has been defined by you and configured by OCP Admins. Only works if the project has a 'moderated' joining style."),
        )

    def __init__(self, agent=None, *args, **kwargs):
        super(ProjectCreateForm, self).__init__(*args, **kwargs)
        if agent:
            self.fields["fobi_slug"].initial = str(agent.slug)
        self.fields["joining_style"].choices = [(js[0], js[1]) for js in JOINING_STYLE_CHOICES]
        self.fields["visibility"].choices = [(vi[0], vi[1]) for vi in VISIBILITY_CHOICES]
        self.fields["resource_type_selection"].choices = [(rts[0], rts[1]) for rts in SELECTION_CHOICES]

    def clean(self):
        data = super(ProjectCreateForm, self).clean()
        #url = data["url"]
        #if not url[0:3] == "http":
        #    pass #data["url"] = "http://" + url
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(ProjectCreateForm, self)._clean_fields()
        for name, value in list(self.cleaned_data.items()):
            self.cleaned_data[name] = bleach.clean(value)

    class Meta: #(AgentCreateForm.Meta):
        model = Project #EconomicAgent
        #removed address and is_context
        fields = ('joining_style', 'visibility', 'resource_type_selection', 'fobi_slug', 'auto_create_pass')
        #exclude = ('is_context',)



class AssociationForm(forms.Form):
    member = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'chzn-select input-xlarge'}))
    new_association_type = forms.ModelChoiceField(
        queryset=AgentAssociationType.objects.member_types(),
        label=_("Choose a new relationship"),
        empty_label=_("------ (inactive)"),
        required=False,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}),
    )

    def __init__(self, agent, *args, **kwargs):
        super(AssociationForm, self).__init__(*args, **kwargs)
        self.fields["member"].choices = [(assoc.id, assoc.is_associate.name + ' - ' + assoc.association_type.name) for assoc in agent.member_associations()]




class ValidateNameForm(forms.Form):
    agent_id = forms.IntegerField()
    name = forms.CharField()
    surname = forms.CharField(required=False)
    typeofuser = forms.CharField()


#     J O I N   R E Q U E S T S


# public join form
class JoinRequestForm(forms.ModelForm):
    captcha = CaptchaField(help_text=_("Is a math operation: Please put the result (don't copy the symbols)"))

    project = forms.CharField(
        required=True,
        widget=forms.HiddenInput()
    )
    exchange = None
    '''forms.ModelChoiceField(
        queryset=Project.objects.filter(joining_style='moderated', visibility='public'),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))'''

    class Meta:
        model = JoinRequest
        exclude = ('agent', 'project', 'fobi_data', 'exchange')

    def clean(self):
        data = super(JoinRequestForm, self).clean()
        if not 'requested_username' in data:
            self.add_error('requested_username', _("This field is required."))
            return
        username = data["requested_username"]
        typeofuser = data["type_of_user"]
        email = data["email_address"]
        nome = data["name"]
        surname = data["surname"]
        projid = data["project"]
        if not projid:
            self.add_error('project', _("The project is missing??"))
            raise ValidationError("The project is missing??")
        else:
            proj = Project.objects.get(id=projid)

        if typeofuser == 'individual':
            if not surname:
                self.add_error('surname', _("Please put your Surname if you are an individual."))
                return
            exist_name = EconomicAgent.objects.filter(name_en__iexact=nome+' '+surname)
            if not exist_name:
                exist_name = User.objects.filter(first_name__iexact=nome, last_name__iexact=surname)
            if len(exist_name) > 0:
                pass #self.add_error('name', _("This name and surname is already used by another user, do you want to differentiate anyhow?"))
                #self.add_error('surname', _("This name and surname is already used by another user, do you want to differentiate anyhow?"))
        elif typeofuser == 'collective':
            exist_name = EconomicAgent.objects.filter(name_en__iexact=nome)
            if len(exist_name) > 0:
                self.add_error('name', _("This name is already used by another agent, do yo want to diferentiate anyhow? "))
        else:
            self.add_error('type_of_user', _("Bad type of user??"))

        exist_user = EconomicAgent.objects.filter(nick_en__iexact=username)

        #+str(exist_name[0].nick))
        if len(exist_user) > 0:
            if not exist_user[0].nick_en == username:
                self.add_error('requested_username', _("A too similar username already exists. Please login here with your OCP credentials or choose another username."))
            else:
                self.add_error('requested_username', _("The username already exists. Please login here to join this project or choose another username."))
        else:
            exist_request = JoinRequest.objects.filter(requested_username__iexact=username, project=projid)
            if len(exist_request) > 0:
                self.add_error('requested_username', _("This username is already used in another request to join this same project. Please wait for an answer before applying again. ")) #+str(exist_request[0].project)) #+' pro:'+str(projid))

        exist_email = EconomicAgent.objects.filter(email__iexact=email)

        if not exist_email:
            exist_request = JoinRequest.objects.filter(email_address__iexact=email) #, project=projid)
            if exist_request:
                for req in exist_request:
                    if req.project.id == projid:
                        self.add_error('email_address', _("The email address is already registered in the system as a request to join this same project. Please wait for an answer before applying again."))
                    else:
                        pass #self.add_error('email_address', _("The email address is already registered in the system as a request to join another project: ")+str(req.project))

            exist_user = User.objects.filter(email__iexact=email)
            if exist_user:
                for usr in exist_user:
                    self.add_error('email_address', _("The email address is already registered in the system for another user without agent?? ")) #+str(usr.username))
        else:
            if len(exist_email) > 1:
                self.add_error('email_address', _("The email address is already registered in the system for various agents! Please login here and we'll try to solve this:"))
                print("DUPLICATE email agent: "+str(exist_email))
            else:
                if not exist_email[0].nick_en == username:
                    self.add_error('email_address', _("The email address is already registered in the system for another username. To join this project please login here with your existent OCP username.")) #+str(exist_email[0].nick))
                else:
                    self.add_error('email_address', _("The email address is already registered in the system with same username. To join this project please login here:"))


        #print("- projid: "+str(projid))
        #type_of_user = data["type_of_user"]
        #number_of_shares = data["number_of_shares"]
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(JoinRequestForm, self)._clean_fields()
        for name, value in list(self.cleaned_data.items()):
            self.cleaned_data[name] = bleach.clean(value)

    def __init__(self, project=None, api_key=None, *args, **kwargs):
        super(JoinRequestForm, self).__init__(*args, **kwargs)
        if project:
            self.fields['project'].initial = project.id
        if api_key:
            del self.fields['captcha'] #.disabled = True #None


class JoinRequestInternalForm(forms.ModelForm):
    captcha = None #CaptchaField()

    project = None
    exchange = None
    '''forms.ModelChoiceField(
        queryset=Project.objects.filter(joining_style='moderated', visibility='public'),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))'''

    class Meta:
        model = JoinRequest
        exclude = ('agent', 'project', 'exchange', 'fobi_data', 'type_of_user', 'name', 'surname', 'requested_username', 'email_address', 'phone_number', 'address', 'website',)

    def clean(self):
        data = super(JoinRequestInternalForm, self).clean()
        #type_of_user = data["type_of_user"]
        #number_of_shares = data["number_of_shares"]
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(JoinRequestInternalForm, self)._clean_fields()
        for name, value in list(self.cleaned_data.items()):
            self.cleaned_data[name] = bleach.clean(value)



class JoinAgentSelectionForm(forms.Form):
    created_agent = AgentModelChoiceField(
        queryset=EconomicAgent.objects.all(), #without_join_request(),
        required=False)

    def __init__(self, project=None, *args, **kwargs):
        super(JoinAgentSelectionForm, self).__init__(*args, **kwargs)
        if project:
            self.fields['created_agent'].queryset = EconomicAgent.objects.without_join_request()
        else:
            self.fields['created_agent'].queryset = EconomicAgent.objects.without_join_request()



class ProjectAgentCreateForm(forms.ModelForm):
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'required-field input-xlarge',}))
    nick = forms.CharField(
        label=_("Nickname"),
        help_text=_("Must be unique, and no more than 32 characters"),
        widget=forms.TextInput(attrs={'class': 'nick required-field',}))
    email = forms.EmailField(required=False, widget=forms.TextInput(attrs={'class': 'email input-xxlarge',}))
    #address = forms.CharField(
    #    required=False,
    #    label="Work location",
    #    help_text="Enter address for a new work location. Otherwise, select existing location on map.",
    #    widget=forms.TextInput(attrs={'class': 'input-xxlarge',}))
    url = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'input-xxlarge',}))
    agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.all(),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))
    #is_context = forms.BooleanField(
    #    required=False,
    #    label="Is a context agent",
    #    widget=forms.CheckboxInput())
    password = forms.CharField(label=_("Password"),
        help_text=_("Login password"),
        widget=forms.PasswordInput(attrs={'class': 'password',}))

    class Meta:
        model = EconomicAgent
        #removed address and is_context
        fields = ('name', 'nick', 'agent_type', 'description', 'url', 'email')









#     E X C H A N G E S


class ExchangeNavForm(forms.Form):
    #get_et = False
    used_exchange_type = forms.ModelChoiceField(
          queryset=ExchangeType.objects.none(),  #ExchangeType.objects.all(),
          empty_label='', #'. . .',
          #level_indicator='. ',
          required=False,
          widget=forms.Select(
              attrs={'class': 'id_used_exchange_type chzn-select-single',
                     'data-placeholder':_("used Exchange type...")}
          )
    )
    exchange_type = TreeNodeChoiceField( #forms.ModelChoiceField(
          queryset=Ocp_Record_Type.objects.none(),  #ExchangeType.objects.all(),
          empty_label=None, #'. . .',
          level_indicator='. ',
          required=False,
          widget=forms.Select(
              attrs={'class': 'id_exchange_type chzn-select',
                     'multiple':'',
                     'data-placeholder':_("search Exchange type...")}
          )
    )

    resource_type = TreeNodeChoiceField(
        queryset=Ocp_Artwork_Type.objects.all(),
        empty_label=None,
        level_indicator='. ',
        required=False,
        widget=forms.Select(
          attrs={'class': 'id_resource_type chzn-select',
                     'multiple':'',
                     'data-placeholder':_("search Resource type...")}
        )
    )
    skill_type = TreeNodeChoiceField(
        queryset=Ocp_Skill_Type.objects.all(),
        empty_label=None,
        level_indicator='. ',
        required=False,
        widget=forms.Select(
          attrs={'class': 'id_skill_type chzn-select',
                     'multiple':'',
                     'data-placeholder':_("search Skill type...")}
        )
    )

    def __init__(self, agent=None, exchanges=None, *args, **kwargs):
        super(ExchangeNavForm, self).__init__(*args, **kwargs)
        try:
            gen_et = Ocp_Record_Type.objects.get(clas='ocp_exchange')
            if agent:
                contexts = agent.related_all_agents()
                context_ids = [c.id for c in contexts]
                if not agent.id in context_ids:
                    context_ids.append(agent.id)
                if gen_et:
                    self.fields["exchange_type"].label = 'Contexts: '+str(contexts)

                    hidden_ets = Ocp_Record_Type.objects.filter( Q(exchange_type__isnull=False), Q(exchange_type__context_agent__isnull=False),  ~Q(exchange_type__context_agent__id__in=context_ids) )
                    hidden_etids = []
                    for het in hidden_ets:
                      dhets = het.get_descendants(True) # true = include self
                      for det in dhets:
                        hidden_etids.append(det.id)


                    self.fields["exchange_type"].queryset = Ocp_Record_Type.objects.filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id).exclude( Q(id__in=hidden_etids) ).order_by('tree_id','lft') #Q(exchange_type__isnull=False), Q(exchange_type__context_agent__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids) )


                    self.fields["resource_type"].queryset = Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft') #| Q(resource_type__context_agent__isnull=True) )
                    self.fields["skill_type"].queryset = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft') #| Q(resource_type__context_agent__isnull=True) )

                if not exchanges:
                    #today = datetime.date.today()
                    #end =  today
                    #start = today - datetime.timedelta(days=365)
                    exchanges = Exchange.objects.exchanges_by_type(agent) #date_and_context(start, end, agent) #filter(Q(context_agent=agent), Q(transfers__events__from_agent=agent), Q(transfers__events__to_agent=agent))
                ex_types = [ex.exchange_type.id for ex in exchanges]
                self.fields["used_exchange_type"].queryset = ExchangeType.objects.filter(id__in=ex_types)

        except:
            #pass
            self.fields["exchange_type"].label = 'ERROR! contexts: '+str(agent.related_all_agents())
            self.fields["exchange_type"].queryset = Ocp_Record_Type.objects.none() #all()


    def clean(self):
        data = super(ExchangeNavForm, self).clean()
        uext = data["used_exchange_type"]
        ext = data["exchange_type"]
        if not ext and not uext:
          self.add_error('exchange_type', "An exchange type is required.")

        return data



class ContextExchangeTypeForm(forms.Form):  # used only for editing
    name = forms.CharField(
        #required=False,
        label=_("Name (automatic?)"),
        #editable=False,
        widget=forms.TextInput(attrs={'class': 'url input-xlarge', }), #'disabled':''}),
    )
    parent_type = TreeNodeChoiceField(
        queryset=Ocp_Record_Type.objects.all(),
        empty_label=None,
        level_indicator='. ',
        required=False,
        widget=forms.Select(
          attrs={'class': 'chzn-select',
                     'data-placeholder':_("search Exchange type...")}
        )
    )
    resource_type = TreeNodeChoiceField(
        queryset=Ocp_Artwork_Type.objects.all(),
        empty_label='. . .',
        level_indicator='. ',
        required=False,
        label=_("Related Resource type"),
        widget=forms.Select(
          attrs={'class': 'chzn-select',
                     'data-placeholder':_("search Resource type...")}
        )
    )
    skill_type = TreeNodeChoiceField(
        queryset=Ocp_Skill_Type.objects.all(),
        empty_label='. . .',
        level_indicator='. ',
        required=False,
        label=_("Related skill Service time"),
        widget=forms.Select(
          attrs={'class': 'chzn-select',
                     'data-placeholder':_("search Skill service...")}
        )
    )
    context_agent = forms.ModelChoiceField(
        empty_label=None,
        queryset=EconomicAgent.objects.none(),
        help_text=_('If the exchange type is only useful for your project or a parent sector collective, choose a smaller context here.'),
        widget=forms.Select(
            attrs={'class': 'id_context_agent chzn-select-single'}),
    )
    edid = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    #class Meta:
    #    fields = ('resource_type', 'skill_type')

    def __init__(self, agent=None, *args, **kwargs):
        super(ContextExchangeTypeForm, self).__init__(*args, **kwargs)
        try:
            gen_et = Ocp_Record_Type.objects.get(clas='ocp_exchange')
            if agent:
                context_ids = [c.id for c in agent.related_all_agents()]
                if not agent.id in context_ids:
                    context_ids.append(agent.id)
                if gen_et:
                    #self.fields["parent_exchange_type"].label = 'Contexts: '+str(agent.related_all_agents())
                    self.fields["parent_type"].queryset = Ocp_Record_Type.objects.filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id).exclude( Q(exchange_type__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')

                    self.fields["resource_type"].queryset = Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) | Q(resource_type__context_agent__isnull=True) ).order_by('tree_id','lft')
                    self.fields["skill_type"].queryset = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) | Q(resource_type__context_agent__isnull=True) ).order_by('tree_id','lft')

                    self.fields["context_agent"].queryset = agent.related_all_contexts_queryset(agent)
                    #self.fields["context_agent"].initial = self.fields["context_agent"].queryset.last()
                #exchanges = Exchange.objects.filter(context_agent=agent)
                #ex_types = [ex.exchange_type.id for ex in exchanges]
                #self.fields["used_exchange_type"].queryset = ExchangeType.objects.filter(id__in=ex_types)

        except:
            #pass
            self.fields["parent_type"].label = 'ERROR! contexts: '+str(agent.related_all_agents())
            self.fields["parent_type"].queryset = Ocp_Record_Type.objects.none() #all()



class NewResourceTypeForm(forms.Form):
    name = forms.CharField(
        label=_("Name of the Resource Type"),
        widget=forms.TextInput(attrs={'class': 'unique-name input-xxlarge',}),
    )
    resource_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Artwork_Type.objects.all(), #none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        empty_label='', #_('. . .'),
        level_indicator='. ',
        label=_("Parent resource type"),
        widget=forms.Select(
            attrs={'class': 'id_resource_type input-xlarge chzn-select', 'data-placeholder':_("search Resource type...")}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description input-xxlarge', 'rows': 5,})
    )
    context_agent = forms.ModelChoiceField(
        empty_label=None,
        queryset=EconomicAgent.objects.none(),
        help_text=_('If the resource type is only useful for your project or a parent sector collective, choose a smaller context here.'),
        widget=forms.Select(
            attrs={'class': 'id_context_agent chzn-select'}),
    )
    substitutable = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_('Check this if any resource of this type can be substituted for any other resource of this same type.'),
        widget=forms.CheckboxInput()
    )
    unit_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Unit_Type.objects.all(),
        required=False,
        empty_label='', #_('. . .'),
        level_indicator='. ',
        label=_("Unit of measure"),
        help_text=_("Choose 'Each' to refer a sigle unit as a piece, or the main used Unit of accounting or measure for the resources of this type, or leave empty if unsure."),
        widget=forms.Select(
            attrs={'class': 'id_unit_type chzn-select-single', 'data-placeholder':_("search Unit type...")}
        ) #, 'multiple': ''}),
    )
    price_per_unit = forms.DecimalField(
        required=False,
        max_digits=8, decimal_places=2,
        label=_("Fixed Faircoin price per each unit?"),
        help_text=_('Set only if all the resources of this type will have a fixed Faircoin price.'),
        widget=forms.TextInput(attrs={'value': '0.0', 'class': 'price'}),
    )
    related_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Artwork_Type.objects.all(), #none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        required=False,
        empty_label='', #_('. . .'),
        level_indicator='. ',
        label=_("Has a main related resource type from another branch?"),
        help_text=_('If this resource type is mainly related another resource type from a different branch, choose it here.'),
        widget=forms.Select(
            attrs={'class': 'id_related_type input-xlarge chzn-select-single', 'data-placeholder':_("search Resource type...")}),
    )
    parent = forms.ModelChoiceField(
        empty_label='', #_('. . .'),
        queryset=EconomicResourceType.objects.none(),
        required=False,
        label=_("Inherit a Recipe from another resource type?"),
        help_text=_('If the resource type must inherit a Recipe from another resource type, choose it here.'),
        widget=forms.Select(
            attrs={'class': 'id_parent chzn-select-single', 'data-placeholder':_("search Resource type with Recipe...")}),
    )
    url = forms.CharField(
        required=False,
        label=_("Any related page URL for the type?"),
        widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}),
    )
    photo_url = forms.CharField(
        required=False,
        label=_("Any photo URL of the resource type?"),
        widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}),
    )
    edid = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    def __init__(self, agent=None, *args, **kwargs):
        super(NewResourceTypeForm, self).__init__(*args, **kwargs)
        self.fields["substitutable"].initial = settings.SUBSTITUTABLE_DEFAULT
        self.fields["parent"].queryset = possible_parent_resource_types()
        self.fields["unit_type"].queryset = Ocp_Unit_Type.objects.all().exclude(clas='faircoin').order_by('tree_id','lft') #(Q(clas__contains='currency') | Q(parent__clas__contains='currency'))
        if agent:
            context_ids = [c.id for c in agent.related_all_agents()]
            if not agent.id in context_ids:
                context_ids.append(agent.id)
            self.fields["context_agent"].queryset = agent.related_all_contexts_queryset(agent)
            self.fields["context_agent"].initial = self.fields["context_agent"].queryset.last()

            self.fields["resource_type"].queryset = Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')
            self.fields["related_type"].queryset = Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')

    def clean(self):
        data = super(NewResourceTypeForm, self).clean()
        price = data["price_per_unit"]
        if not price:
          data["price_per_unit"] = "0.0"
        if hasattr(data, 'edid'):
          edid = data['edid']
        else:
          edid = ''
        if hasattr(data, 'name'):
          name_rts = Ocp_Artwork_Type.objects.filter(name=data["name"])
          if not name_rts:
            name_rts = Ocp_Artwork_Type.objects.filter(name_en=data["name"])
          if name_rts.count() and edid == '':
            self.add_error('name', "<b>"+data["name"]+"</b> already exists!")
          elif not edid == '' and edid.split('_')[1] != str(name_rts[0].id):
            self.add_error('name', "<b>"+data["name"]+"</b> already exists! "+edid.split('_')[1]+' = '+str(name_rts[0].id))
        return data



class NewSkillTypeForm(forms.Form):
    name = forms.CharField(
        label=_("Name of the new Skill Type"),
        widget=forms.TextInput(attrs={'class': 'unique-name input-xxlarge',}),
    )
    verb = forms.CharField(
        label=_("Verb of the action (infinitive)"),
        widget=forms.TextInput(attrs={'class': 'unique-name input-large',}),
    )
    gerund = forms.CharField(
        label=_("Gerund of the verb"),
        widget=forms.TextInput(attrs={'class': 'unique-name input-large',}),
    )
    parent_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Skill_Type.objects.none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        empty_label=_('. . .'),
        level_indicator='. ',
        label=_("Parent skill type"),
        widget=forms.Select(
            attrs={'class': 'ocp-resource-type input-xlarge chzn-select id_skill_type'}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description input-xxlarge', 'rows': 5,})
    )
    related_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Artwork_Type.objects.none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        required=False,
        empty_label='', #_('. . .'),
        level_indicator='. ',
        label=_("Has a main related material or non-material resource type?"),
        help_text=_('If this skill type is mainly related a resource type or branch, choose it here.'),
        widget=forms.Select(
            attrs={'class': 'ocp-resource-type input-xlarge chzn-select-single', 'data-placeholder':_("search Resource type...")}),
    )
    context_agent = forms.ModelChoiceField(
        empty_label=None,
        queryset=EconomicAgent.objects.none(),
        help_text=_('If the skill is only useful for your project or a parent sector collective, choose a smaller context here.'),
        widget=forms.Select(
            attrs={'class': 'chzn-select'}),
    )
    unit_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Unit_Type.objects.all(),
        required=False,
        empty_label='', #_('. . .'),
        level_indicator='. ',
        label=_("Unit of time measure"),
        help_text=_("Choose Hours or another time related unit to measure the skill service."),
        widget=forms.Select(
            attrs={'class': 'chzn-select-single', 'data-placeholder':_("search Unit type...")}
        ) #, 'multiple': ''}),
    )
    price_per_unit = forms.DecimalField(
        required=False,
        max_digits=8, decimal_places=2,
        label=_("Fixed Faircoin price per each unit?"),
        help_text=_('Set only if all the service time of this type will have a fixed Faircoin price.'),
        widget=forms.TextInput(attrs={'value': '0.0', 'class': 'price'}),
    )
    url = forms.CharField(
        required=False,
        label=_("Any related URL for the Skill?"),
        widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}),
    )
    photo_url = forms.CharField(
        required=False,
        label=_("Any photo URL of the skill type?"),
        widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}),
    )
    edid = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    def __init__(self, agent=None, *args, **kwargs):
        super(NewSkillTypeForm, self).__init__(*args, **kwargs)
        time = get_object_or_404(Ocp_Unit_Type, clas='time_currency')
        self.fields["unit_type"].queryset = Ocp_Unit_Type.objects.filter(lft__gt=time.lft, rght__lt=time.rght, tree_id=time.tree_id).order_by('tree_id','lft') #all().exclude(clas='faircoin') #(Q(clas__contains='currency') | Q(parent__clas__contains='currency'))
        if agent:
            context_ids = [c.id for c in agent.related_all_agents()]
            if not agent.id in context_ids:
                context_ids.append(agent.id)
            contexts = agent.related_all_contexts_queryset(agent, False) # 2nd arg: include childs
            initial = contexts.last()
            for ag in contexts:
              if ag.is_root():
                initial = ag
            self.fields["context_agent"].queryset = contexts
            self.fields["context_agent"].initial = initial #self.fields["context_agent"].queryset.last()

            self.fields["parent_type"].queryset = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')
            self.fields["related_type"].queryset = Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')

    def clean(self):
        data = super(NewSkillTypeForm, self).clean()
        price = data["price_per_unit"]
        if not price:
          data["price_per_unit"] = "0.0"
        if hasattr(data, 'edid'):
          edid = data['edid']
        else:
          edid = ''
        if hasattr(data, 'name'):
          name_sts = Ocp_Skill_Type.objects.filter(name=data["name"])
          if name_sts.count() and edid == '':
            self.add_error('name', "<b>"+data["name"]+"</b> already exists!")
          elif not edid == '' and edid.split('_')[1] != name_sts[0].id:
            self.add_error('name', "<b>"+data["name"]+"</b> already exists! "+str(data['edid'])+' = '+str(name_sts[0].id))
        return data









#     E X C H A N G E   L O G G I N G


class ExchangeContextForm(forms.ModelForm): # used in exchange-logging page
    start_date = forms.DateField(required=True,
        label=_("Date"),
        widget=forms.TextInput(attrs={'class': 'item-date date-entry',}))
    notes = forms.CharField(required=False,
        label=_("Comments"),
        widget=forms.Textarea(attrs={'class': 'item-description',}))
    url = forms.CharField(required=False,
        label=_("Link to receipt(s)"),
        widget=forms.TextInput(attrs={'class': 'url input-xxlarge',}))

    class Meta:
        model = Exchange
        fields = ('start_date', 'url', 'notes')



class WorkEventContextAgentForm(forms.ModelForm):
    event_date = forms.DateField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',})
    )
    ocp_skill_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Skill_Type.objects.none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        empty_label=_('. . .'),
        label="Type of work done",
        level_indicator='. ',
        widget=forms.Select(
            attrs={'class': 'ocp-skill-type input-xlarge chzn-select'})
    )
    resource_type = WorkModelChoiceField(
        queryset=EconomicResourceType.objects.filter(behavior="work"),
        label="Type of work done",
        #empty_label=None,
        required=False,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    quantity = forms.DecimalField(required=True,
        label="Hours, up to 2 decimal places",
        widget=forms.TextInput(attrs={'class': 'quantity input-small',}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description',}))
    from_agent = forms.ModelChoiceField(
        required=True,
        queryset=EconomicAgent.objects.all(),
        label="Work done by",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    is_contribution = forms.BooleanField(
        required=False,
        initial=True,
        label="Can be used in a value equation",
        widget=forms.CheckboxInput())

    class Meta:
        model = EconomicEvent
        fields = ('event_date', 'ocp_skill_type', 'resource_type','quantity', 'description', 'from_agent', 'is_contribution')

    def __init__(self, context_agent=None, *args, **kwargs):
        super(WorkEventContextAgentForm, self).__init__(*args, **kwargs)
        if context_agent:
            #self.context_agent = context_agent
            self.fields["from_agent"].queryset = context_agent.related_all_agents_queryset()
            context_ids = [c.id for c in context_agent.related_all_agents()]
            if not context_agent.id in context_ids:
                context_ids.append(context_agent.id)
            self.fields["ocp_skill_type"].queryset = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')
        if list(kwargs.items()):
            for name, value in list(kwargs.items()):
              if name == 'instance':
                self.fields["ocp_skill_type"].initial = get_ocp_st_from_rt(value.resource_type)
                #self.fields["ocp_skill_type"].label += " :"+str(value.from_agent) #get_ocp_st_from_rt(kwargs.items()[0][1])) #str(kwargs.items())
                self.fields["from_agent"].initial = value.from_agent
                #break #kwargs['instance'])

    def clean(self):
        data = super(WorkEventContextAgentForm, self).clean()
        ocp_st = data["ocp_skill_type"]
        ini_rt = data["resource_type"]
        if ocp_st:
          if not ini_rt:
            rt = get_rt_from_ocp_st(ocp_st)
            if rt:
              data["resource_type"] = rt
              del data["ocp_skill_type"]
            else:
              self.add_error('ocp_skill_type', "This type is too general, try a more specific")
        else:
          self.add_error('ocp_skill_type', "There is a problem with this ocp_skill_type!")
        return data



class ContextTransferForm(forms.Form):
    event_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    to_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transferred to",
        empty_label=_('. . .'), #None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    from_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transferred from",
        empty_label=_('. . .'), #None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    quantity = forms.DecimalField(
        label="Quantity transferred",
        initial=1,
        widget=forms.TextInput(attrs={'class': 'quantity input-small',}))

    ocp_resource_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Artwork_Type.objects.none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        empty_label=_('. . .'),
        level_indicator='. ',
        widget=forms.Select(
            attrs={'class': 'ocp-resource-type-for-resource input-xlarge'})
    )

    resource_type = forms.ModelChoiceField(
        queryset=EconomicResourceType.objects.all(),
        label="Facets:",
        #empty_label=None,
        required=False,
        widget=forms.Select(
            attrs={'class': 'resource-type-for-resource chzn-select'})
    )

    resource = ResourceModelChoiceField(
        queryset=EconomicResource.objects.none(),
        label="Resource transferred (optional if not inventoried)",
        required=False,
        empty_label=_('. . .'),
        widget=forms.Select(attrs={'class': 'resource input-xlarge chzn-select',}))
    from_resource = ResourceModelChoiceField(
        queryset=EconomicResource.objects.none(),
        label="Resource transferred from (optional if not inventoried)",
        required=False,
        empty_label=_('. . .'),
        widget=forms.Select(attrs={'class': 'resource input-xlarge chzn-select',}))
    value = forms.DecimalField(
        label="Value (total, not per unit)",
        initial=0,
        required=False,
        widget=forms.TextInput(attrs={'class': 'quantity value input-small',}))
    unit_of_value = forms.ModelChoiceField(
        empty_label=_('. . .'), #None,
        required=False,
        queryset=Unit.objects.filter(unit_type='value'),
        widget=forms.Select(attrs={'class': 'chzn-select',}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description',}))
    is_contribution = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput())
    is_to_distribute = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput())
    event_reference = forms.CharField(
        required=False,
        label="Reference",
        widget=forms.TextInput(attrs={'class': 'input-xlarge',}))
    identifier = forms.CharField(
        required=False,
        label="<b>Create the resource:</b><br><br>Identifier",
        help_text="For example, lot number or serial number.",
        widget=forms.TextInput(attrs={'class': 'item-name',}))
    url = forms.URLField(
        required=False,
        label="URL",
        widget=forms.TextInput(attrs={'class': 'url input-xlarge',}))
    photo_url = forms.URLField(
        required=False,
        label="Photo URL",
        widget=forms.TextInput(attrs={'class': 'url input-xlarge',}))
    current_location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        empty_label=_('. . .'),
        label=_("Current Resource Location"),
        widget=forms.Select(attrs={'class': 'input-medium chzn-select',}))
    notes = forms.CharField(
        required=False,
        label="Resource Notes",
        widget=forms.Textarea(attrs={'class': 'item-description',}))
    access_rules = forms.CharField(
        required=False,
        label="Resource Access Rules",
        widget=forms.Textarea(attrs={'class': 'item-description',}))


    def __init__(self, transfer_type=None, context_agent=None, resource_type=None, ocp_resource_type=None, posting=False, *args, **kwargs):
        super(ContextTransferForm, self).__init__(*args, **kwargs)

        if transfer_type:
            rts = transfer_type.get_resource_types()
            if resource_type:
              self.fields["resource_type"].queryset = EconomicResourceType.objects.filter(id=resource_type.id)
            else:
              self.fields["resource_type"].queryset = rts
            if posting:
                self.fields["resource"].queryset = EconomicResource.objects.all()
                self.fields["from_resource"].queryset = EconomicResource.objects.all()
            else:
                if resource_type:
                    try:
                        self.fields["resource"].queryset = EconomicResource.objects.filter(resource_type=resource_type).filter(agent_resource_roles__agent__id=context_agent.id)
                    except:
                        self.fields["resource"].queryset = EconomicResource.objects.filter(resource_type=resource_type)
                    self.fields["from_resource"].queryset = EconomicResource.objects.filter(resource_type=resource_type)
                elif rts:
                    self.fields["resource"].queryset = EconomicResource.objects.filter(resource_type=rts[0]).filter(agent_resource_roles__agent__id=context_agent.id)
                    self.fields["from_resource"].queryset = EconomicResource.objects.filter(resource_type=rts[0])
                else:
                    self.fields['quantity'].label += " RT?" #+str(resource_type)
            if context_agent:
                self.fields["to_agent"].queryset = transfer_type.to_context_agents(context_agent)
                self.fields["from_agent"].queryset = transfer_type.from_context_agents(context_agent)

            facetvalues = [ttfv.facet_value.value for ttfv in transfer_type.facet_values.all()]
            #self.fields["ocp_resource_type"].label += "(Facets: "+', '.join(facetvalues)+")"

            #self.fields["ocp_resource_type"].label += init_resource_types()

            if hasattr(self.fields, 'ocp_resource_type'):
              for fv in facetvalues:
                self.fields["ocp_resource_type"].label += " FV:"+fv
                try:
                    gtyp = Ocp_Artwork_Type.objects.get(facet_value__value=fv)
                    self.fields["ocp_resource_type"].label += " R:"+str(gtyp.name)
                except:
                    pass
                #self.fields["ocp_resource_type"].label += " FV:"+fv

                try:
                    gtyp = Ocp_Skill_Type.objects.get(facet_value__value=fv)
                    self.fields["ocp_resource_type"].label += " S:"+str(gtyp.name)
                except:
                    pass


              for facet in transfer_type.facets():
                if facet.clas == "Material_Type":
                    #gen_mts = Material_Type.objects.all()
                    #ocp_mts =  Ocp_Material_Type.objects.all()
                    #if not gen_mts.count() == ocp_mts.count():
                    #  self.fields["ocp_resource_type"].label += " !Needs Update! (ocpMT:"+str(ocp_mts.count())+" gen:"+str(gen_mts.count())+")"
                    #  update = update_from_general(facet.clas)
                    #  self.fields["ocp_resource_type"].label += "UPDATE: "+str(update)

                    if resource_type:
                       try:
                          self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                       except:
                          self.fields["ocp_resource_type"].label += " INITIAL? "+str(self.fields["ocp_resource_type"].initial)


                elif facet.clas == "Nonmaterial_Type":
                    #gen_nts = Nonmaterial_Type.objects.all()
                    #ocp_nts =  Ocp_Nonmaterial_Type.objects.all()
                    #if not gen_nts.count() == ocp_nts.count():
                    #   self.fields["ocp_resource_type"].label += " !Needs Update! (ocpMT:"+str(ocp_nts.count())+" gen:"+str(gen_nts.count())+")"
                    #   update = update_from_general(facet.clas)
                    #   self.fields["ocp_resource_type"].label += " UPDATE: "+str(update)

                    if resource_type:
                       try:
                          self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                       except:
                          self.fields["ocp_resource_type"].label += " INITIAL? "+str(self.fields["ocp_resource_type"].initial)

                elif facet.clas == "Skill_Type":
                    #gen_sts = Job.objects.all()
                    #ocp_sts =  Ocp_Skill_Type.objects.all()
                    #if not gen_sts.count() == ocp_sts.count():
                    #   self.fields["ocp_resource_type"].label += " !Needs Update! (ocpST:"+str(ocp_sts.count())+" gen:"+str(gen_sts.count())+")"
                    #   update = update_from_general(facet.clas)
                    #   self.fields["ocp_resource_type"].label += " UPDATE: "+str(update)

                    if resource_type:
                       try:
                          self.fields["ocp_resource_type"].initial = Ocp_Skill_Type.objects.get(resource_type=resource_type)
                       except:
                          self.fields["ocp_resource_type"].label += " INITIAL? "+str(self.fields["ocp_resource_type"].initial)

                elif facet.clas == "Currency_Type":
                    if resource_type:
                       try:
                          self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                       except:
                          self.fields["ocp_resource_type"].label += " INITIAL? "+str(self.fields["ocp_resource_type"].initial)
                else:
                    self.fields['quantity'].label += " ERROR: this facet is what? "+str(facet) #pass
            else:
                if resource_type:
                    if resource_type.name_en == "Faircoin Ocp Account":
                        resource_type = EconomicResourceType.objects.get(name_en="FairCoin")

                    try:
                        self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                    except:
                        self.fields["ocp_resource_type"].label = " INITIAL? "+str(resource_type)
                else:
                    self.fields['quantity'].label += " ERROR: this form has not ocp_resource_type field, RT:"+str(resource_type)

            resini = self.fields["resource"].queryset.first()
            if resini:
                print("++ found resource initial, get rt: "+str(resini))
                self.fields["ocp_resource_type"].queryset = Ocp_Artwork_Type.objects.filter(resource_type=resini.resource_type)
                self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resini.resource_type)
                #self.fields["ocp_resource_type"].label = str(self.fields["ocp_resource_type"].initial)
            else:
                try:
                    self.fields["ocp_resource_type"].queryset = transfer_type.exchange_type.ocp_record_type.get_ocp_resource_types(transfer_type=transfer_type)
                    if resource_type:
                        self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                except:
                    self.fields["ocp_resource_type"].label = "  Sorry, this exchange type is not yet related to any resource types..."

        else: # no transfer type, rise error TODO
          pass

    def clean(self):
        data = super(ContextTransferForm, self).clean()
        #import pdb; pdb.set_trace()
        if not 'ocp_resource_type' in data:
          self.add_error('ocp_resource_type', "There's no resource_type?")
          return data
        ocp_rt = data["ocp_resource_type"]
        ini_rt = data["resource_type"]
        if ocp_rt:
          if not ini_rt:
            rt = get_rt_from_ocp_rt(ocp_rt)
            if rt:
              data["resource_type"] = rt
            else:
              self.add_error('ocp_resource_type', "This type is too general, try a more specific")
        else:
          self.add_error('ocp_resource_type', "There is a problem with this ocp_resource_type!")
        return data



class ContextTransferCommitmentForm(forms.Form):
    commitment_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    due_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    to_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transfer to",
        empty_label=_('. . .'),
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    from_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transfer from",
        empty_label=_('. . .'),
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    quantity = forms.DecimalField(
        label="Quantity",
        initial=1,
        widget=forms.TextInput(attrs={'class': 'quantity input-small',}))

    ocp_resource_type = TreeNodeChoiceField( #forms.ModelChoiceField(
        queryset=Ocp_Artwork_Type.objects.none(), #filter(lft__gt=gen_et.lft, rght__lt=gen_et.rght, tree_id=gen_et.tree_id),
        empty_label=_('. . .'),
        level_indicator='. ',
        widget=forms.Select(
            attrs={'class': 'ocp-resource-type-for-resource input-xlarge chzn-select'})
    )

    resource_type = forms.ModelChoiceField(
        queryset=EconomicResourceType.objects.all(),
        empty_label=_('. . .'),
        required=False,
        widget=forms.Select(
            attrs={'class': 'resource-type-for-resource chzn-select'}))

    value = forms.DecimalField(
        label="Value (total, not per unit)",
        initial=0,
        required=False,
        widget=forms.TextInput(attrs={'class': 'value quantity input-small',}))
    unit_of_value = forms.ModelChoiceField(
        required=False,
        empty_label=_('. . .'),
        queryset=Unit.objects.filter(unit_type='value'),
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description',}))

    def __init__(self, transfer_type=None, context_agent=None, resource_type=None, ocp_resource_type=None, posting=False, *args, **kwargs):
        super(ContextTransferCommitmentForm, self).__init__(*args, **kwargs)
        if transfer_type:
            self.fields["resource_type"].queryset = transfer_type.get_resource_types()
            #if context_agent:
            #    self.fields["to_agent"].queryset = transfer_type.to_context_agents(context_agent)
            #    self.fields["from_agent"].queryset = transfer_type.from_context_agents(context_agent)

            facetvalues = [ttfv.facet_value.value for ttfv in transfer_type.facet_values.all()]
            #if facetvalues:
              #self.fields["ocp_resource_type"].label = "(Facets: "+', '.join(facetvalues)+")"

            try:
              self.fields["ocp_resource_type"].queryset = transfer_type.exchange_type.ocp_record_type.get_ocp_resource_types(transfer_type=transfer_type)
            except:
              self.fields["ocp_resource_type"].label = "  Sorry, this exchange type is not yet related to any resource types..."

            if resource_type:
                try:
                    self.fields["ocp_resource_type"].initial = Ocp_Artwork_Type.objects.get(resource_type=resource_type)
                except:
                  if hasattr(self.fields, 'ocp_resource_type'):
                    self.fields["ocp_resource_type"].label += " INITIAL? "+str(self.fields["ocp_resource_type"].initial)
            else:
                if hasattr(self.fields, 'ocp_resource_type'):
                  self.fields["ocp_resource_type"].label += " FALTA RT! " #+str(resource_type)


    def clean(self):
        data = super(ContextTransferCommitmentForm, self).clean()
        #if not hasattr(data, 'ocp_resource_type'):
        #  ocp_rt = None
        #else:
        ocp_rt = data["ocp_resource_type"]
        #if not hasattr(data, 'resource_type'):
        #  ini_rt = None
        #else:
        ini_rt = data["resource_type"]
        if ocp_rt:
          if not ini_rt:
            rt = get_rt_from_ocp_rt(ocp_rt)
            if rt:
              data["resource_type"] = rt
            else:
              self.add_error('ocp_resource_type', "This type is too general, try a more specific")
        else:
          self.add_error('ocp_resource_type', "There is not resource_type, it is a required field")
        return data



class ResourceRoleContextAgentForm(forms.ModelForm):
    id = forms.CharField(required=False, widget=forms.HiddenInput)
    role = forms.ModelChoiceField(
        queryset=AgentResourceRoleType.objects.all(),
        required=False,
        empty_label=_('. . .'),
        widget=forms.Select(
            attrs={'class': 'select-role chzn-select'}))
    agent = AgentModelChoiceField(
        queryset=EconomicAgent.objects.resource_role_agents(),
        required=False,
        empty_label=_('. . .'),
        widget=forms.Select(
            attrs={'class': 'select-agent chzn-select'}))
    is_contact = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput())

    class Meta:
        model = AgentResourceRole
        fields = ('id', 'role', 'agent', 'is_contact')

    def __init__(self, context_agent=None, *args, **kwargs):
        super(ResourceRoleContextAgentForm, self).__init__(*args, **kwargs)
        if context_agent:
          context_agents = context_agent.related_all_agents_queryset() # EconomicAgent.objects.context_agents() #
          self.fields["agent"].queryset = context_agents


class ContextExternalAgent(AgentCreateForm): #forms.ModelForm):
    # tune model fields
    address = forms.CharField(
        required=False,
        #label="Address",
        #help_text="Enter address for a new work location. Otherwise, select existing location on map.",
        widget=forms.TextInput(attrs={'class': 'input-xxlarge',})
    )
    url = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-xxlarge',})
    )
    agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.all(),
        #required=False,
        empty_label='. . .',
        label=_("Agent type (required)"),
        widget=forms.Select(
        attrs={'class': 'chzn-select'})
    )

    is_context = None

    class Meta:
        model = EconomicAgent
        fields = ('name', 'nick', 'description', 'agent_type', 'url', 'email', 'address', 'phone_primary')






#    T A S K S


class WorkTodoForm(forms.ModelForm):
    from_agent = forms.ModelChoiceField(
        required=False,
        #queryset=EconomicAgent.objects.individuals(),
        queryset=EconomicAgent.objects.with_user(),
        label="Assigned to",
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    resource_type = WorkModelChoiceField(
        queryset=EconomicResourceType.objects.filter(behavior="work"),
        label="Type of work",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    context_agent = forms.ModelChoiceField(
        queryset=EconomicAgent.objects.context_agents(),
        label=_("Context"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'chzn-select context-selector'}))
    due_date = forms.DateField(widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea()) #attrs={'class': 'todo-description input-xlarge',}))
    url = forms.URLField(required=False, widget=forms.TextInput(attrs={'class': 'url input-xlarge',}))

    class Meta:
        model = Commitment
        fields = ('from_agent', 'context_agent', 'resource_type', 'due_date', 'description', 'url')

    def __init__(self, agent, context_agent=None, pattern=None, *args, **kwargs): #agent is posting agent
        super(WorkTodoForm, self).__init__(*args, **kwargs)
        commitment_instance = None
        if 'instance' in kwargs:
            commitment_instance = kwargs['instance']
            commitment_context = commitment_instance.context_agent
        contexts = agent.related_contexts()
        self.fields["context_agent"].choices = list(set([(ct.id, ct) for ct in contexts]))
        peeps = [agent,]
        from_agent_choices = [('', 'Unassigned'), (agent.id, agent),]
        for context in contexts:
            if agent.is_manager_of(context):
                peeps.extend(context.task_assignment_candidates())
        if len(peeps) > 1:
            peeps = list(OrderedDict.fromkeys(peeps))
        from_agent_choices = [('', 'Unassigned')] + [(peep.id, peep) for peep in peeps]
        self.fields["from_agent"].choices = from_agent_choices
        if pattern:
            self.pattern = pattern
            #self.fields["resource_type"].choices = [(rt.id, rt) for rt in pattern.todo_resource_types()]
            rts = pattern.todo_resource_types()
        else:
            rts = EconomicResourceType.objects.filter(behavior="work")
        if commitment_instance:
            ca = commitment_context
        else:
            ca = ca = self.fields["context_agent"].choices[0][1]
        if context_agent:
            ca = context_agent
        try:
            if ca.project.resource_type_selection == "project":
                rts = rts.filter(context_agent=ca)
            else:
                rts = rts.filter(context_agent=None)
        except:
            rts = rts.filter(context_agent=None)
        self.fields["resource_type"].queryset = rts


class WorkCasualTimeContributionForm(forms.ModelForm):
    resource_type = WorkModelChoiceField(
        queryset=EconomicResourceType.objects.filter(behavior="work"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'chzn-select'}))
    context_agent = forms.ModelChoiceField(
        queryset=EconomicAgent.objects.context_agents(),
        label=_("Context"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'chzn-select context-selector'}))
    event_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'class': 'item-date date-entry',}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'item-description',}))
    url = forms.URLField(required=False, widget=forms.TextInput(attrs={'class': 'url',}))
    #todo: shd be changed to qty of unit
    quantity = forms.DecimalField(required=False,
        widget=DecimalDurationWidget,
        help_text="hrs, mins")

    class Meta:
        model = EconomicEvent
        fields = ('event_date', 'context_agent', 'resource_type', 'quantity', 'is_contribution', 'url', 'description')




#    W O R K   O R D E R   P L A N


class WorkProjectSelectionFormOptional(forms.Form):
    context_agent = forms.ChoiceField(
        required=False,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))

    def __init__(self, context_agents, *args, **kwargs):
        super(WorkProjectSelectionFormOptional, self).__init__(*args, **kwargs)
        self.fields["context_agent"].choices = [('', '--All My Projects--')] + [(proj.id, proj.name) for proj in context_agents]







class ProjectSelectionFilteredForm(forms.Form):
    context_agent = forms.ChoiceField()

    def __init__(self, agent, *args, **kwargs):
        super(ProjectSelectionFilteredForm, self).__init__(*args, **kwargs)
        projects = agent.related_contexts_queryset()
        if projects:
            self.fields["context_agent"].choices = [(proj.id, proj.name) for proj in projects]



class OrderSelectionFilteredForm(forms.Form):
    demand = forms.ModelChoiceField(
        queryset=Order.objects.exclude(order_type="holder"),
        label="Add to an existing order (optional)",
        required=False)

    def __init__(self, provider=None, *args, **kwargs):
        super(OrderSelectionFilteredForm, self).__init__(*args, **kwargs)
        if provider:
            self.fields["demand"].queryset = provider.sales_orders.all()





#     I N V O I C E


class InvoiceNumberForm(forms.ModelForm):
    member = forms.ModelChoiceField(
        queryset=EconomicAgent.objects.none(),
        label=_("for Freedom Coop Member:"),
        empty_label=None,
        )

    class Meta:
        model = InvoiceNumber
        fields = ('member', 'description', )

    def __init__(self, agent, *args, **kwargs):
        super(InvoiceNumberForm, self).__init__(*args, **kwargs)
        self.fields["member"].queryset = agent.invoicing_candidates()


#   V A L U E   E Q U A T I O N

class VESandboxForm(forms.Form):
    #value_equation = forms.ModelChoiceField(
    #    queryset=ValueEquation.objects.all(),
    #    label=_("Value Equation"),
    #    empty_label=None,
    #    widget=forms.Select(
    #        attrs={'class': 've-selector'}))
    amount_to_distribute = forms.DecimalField(required=False,
        widget=forms.TextInput(attrs={'value': '0.00', 'class': 'money quantity input-small'}))

class VEForm(forms.ModelForm):
    #context_agent = forms.ModelChoiceField(
    #    queryset=EconomicAgent.objects.context_agents(),
    #    required=True,
    #    empty_label=None,
    #    widget=forms.Select(attrs={'class': 'chzn-select',}))
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'input-xlarge required-field',}))
    description = forms.CharField(required=False,
        widget=forms.Textarea(attrs={'class': 'item-description',}))

    class Meta:
        model = ValueEquation
        fields = ('name', 'description', 'percentage_behavior')
