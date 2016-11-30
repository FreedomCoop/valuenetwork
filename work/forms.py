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


class ProjectAgentCreateForm(forms.ModelForm):
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'required-field input-xlarge',}))
    nick = forms.CharField(
        label="ID",
        help_text="Must be unique, and no more than 32 characters",
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


class MembershipRequestForm(forms.ModelForm):
    captcha = CaptchaField()

    class Meta:
        model = MembershipRequest
        exclude = ('agent',)

    def clean(self):
        #import pdb; pdb.set_trace()
        data = super(MembershipRequestForm, self).clean()
        type_of_membership = data["type_of_membership"]
        number_of_shares = data["number_of_shares"]
        if type_of_membership == "collective":
            if int(number_of_shares) < 2:
                msg = "Number of shares must be at least 2 for a collective."
                self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(MembershipRequestForm, self)._clean_fields()
        for name, value in self.cleaned_data.items():
            self.cleaned_data[name] = bleach.clean(value)


class WorkProjectSelectionFormOptional(forms.Form):
    context_agent = forms.ChoiceField()

    def __init__(self, context_agents, *args, **kwargs):
        super(WorkProjectSelectionFormOptional, self).__init__(*args, **kwargs)
        self.fields["context_agent"].choices = [('', '--All My Projects--')] + [(proj.id, proj.name) for proj in context_agents]

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
        widget=forms.Select(attrs={'class': 'chzn-select'}))
    due_date = forms.DateField(widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'todo-description input-xlarge',}))
    url = forms.URLField(required=False, widget=forms.TextInput(attrs={'class': 'url input-xlarge',}))

    class Meta:
        model = Commitment
        fields = ('from_agent', 'context_agent', 'resource_type', 'due_date', 'description', 'url')

    def __init__(self, agent, pattern=None, *args, **kwargs): #agent is posting agent
        super(WorkTodoForm, self).__init__(*args, **kwargs)
        contexts = agent.related_contexts()
        self.fields["context_agent"].choices = list(set([(ct.id, ct) for ct in contexts]))
        peeps = [agent,]
        from_agent_choices = [('', 'Unassigned'), (agent.id, agent),]
        #import pdb; pdb.set_trace()
        for context in contexts:
            if agent.is_manager_of(context):
                peeps.extend(context.task_assignment_candidates())
        if len(peeps) > 1:
            peeps = list(OrderedDict.fromkeys(peeps))
        from_agent_choices = [('', 'Unassigned')] + [(peep.id, peep) for peep in peeps]

        self.fields["from_agent"].choices = from_agent_choices
        #import pdb; pdb.set_trace()
        if pattern:
            self.pattern = pattern
            #self.fields["resource_type"].choices = [(rt.id, rt) for rt in pattern.todo_resource_types()]
            self.fields["resource_type"].queryset = pattern.todo_resource_types()


class ProjectCreateForm(AgentCreateForm):
    # override fields for EconomicAgent model
    agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.filter(is_context=True),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))

    is_context = None # projects are always context_agents, hide the field

    # fields for Project model
    joining_style = forms.ChoiceField()
    visibility = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super(ProjectCreateForm, self).__init__(*args, **kwargs)
        self.fields["joining_style"].choices = [(js[0], js[1]) for js in JOINING_STYLE_CHOICES]
        self.fields["visibility"].choices = [(vi[0], vi[1]) for vi in VISIBILITY_CHOICES]

    def clean(self):
        #import pdb; pdb.set_trace()
        data = super(ProjectCreateForm, self).clean()
        url = data["url"]
        if not url[0:3] == "http":
          data["url"] = "http://" + url
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(ProjectCreateForm, self)._clean_fields()
        for name, value in self.cleaned_data.items():
            self.cleaned_data[name] = bleach.clean(value)

    class Meta: #(AgentCreateForm.Meta):
        model = Project #EconomicAgent
        #removed address and is_context
        fields = ('name', 'nick', 'agent_type', 'description', 'url', 'email', 'joining_style', 'visibility', 'fobi_slug')
        #exclude = ('is_context',)


class WorkAgentCreateForm(AgentCreateForm):
    # override fields for EconomicAgent model
    agent_type = forms.ModelChoiceField(
        queryset=AgentType.objects.all(), #filter(is_context=True),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))

    is_context = None # projects are always context_agents, hide the field
    nick = None
    # fields for Project model
    #joining_style = forms.ChoiceField()
    #visibility = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super(WorkAgentCreateForm, self).__init__(*args, **kwargs)
        #self.fields["joining_style"].choices = [(js[0], js[1]) for js in JOINING_STYLE_CHOICES]
        #self.fields["visibility"].choices = [(vi[0], vi[1]) for vi in VISIBILITY_CHOICES]


    class Meta: #(AgentCreateForm.Meta):
        model = EconomicAgent
        #removed address and is_context
        fields = ('name', 'agent_type', 'description', 'url', 'email', 'address', 'phone_primary',)
        #exclude = ('is_context',)


class WorkCasualTimeContributionForm(forms.ModelForm):
    resource_type = WorkModelChoiceField(
        queryset=EconomicResourceType.objects.filter(behavior="work"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'chzn-select'}))
    context_agent = forms.ModelChoiceField(
        queryset=EconomicAgent.objects.open_projects(),
        label=_("Context"),
        empty_label=None,
        widget=forms.Select(attrs={'class': 'chzn-select'}))
    event_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'class': 'item-date date-entry',}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'item-description',}))
    url = forms.URLField(required=False, widget=forms.TextInput(attrs={'class': 'url',}))
    quantity = forms.DecimalField(required=False,
        widget=DecimalDurationWidget,
        help_text="hrs, mins")

    class Meta:
        model = EconomicEvent
        fields = ('event_date', 'resource_type', 'context_agent', 'quantity', 'is_contribution', 'url', 'description')


# public join form
class JoinRequestForm(forms.ModelForm):
    captcha = CaptchaField()

    project = None
    '''forms.ModelChoiceField(
        queryset=Project.objects.filter(joining_style='moderated', visibility='public'),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))'''

    class Meta:
        model = JoinRequest
        exclude = ('agent', 'project', 'fobi_data',)

    def clean(self):
        #import pdb; pdb.set_trace()
        data = super(JoinRequestForm, self).clean()
        type_of_user = data["type_of_user"]
        #number_of_shares = data["number_of_shares"]
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(JoinRequestForm, self)._clean_fields()
        for name, value in self.cleaned_data.items():
            self.cleaned_data[name] = bleach.clean(value)


class JoinRequestInternalForm(forms.ModelForm):
    captcha = None #CaptchaField()

    project = None
    '''forms.ModelChoiceField(
        queryset=Project.objects.filter(joining_style='moderated', visibility='public'),
        empty_label=None,
        widget=forms.Select(
        attrs={'class': 'chzn-select'}))'''

    class Meta:
        model = JoinRequest
        exclude = ('agent', 'project', 'fobi_data', 'type_of_user', 'name', 'surname', 'requested_username', 'email_address', 'phone_number', 'address',)

    def clean(self):
        #import pdb; pdb.set_trace()
        data = super(JoinRequestInternalForm, self).clean()
        #type_of_user = data["type_of_user"]
        #number_of_shares = data["number_of_shares"]
        #if type_of_user == "collective":
            #if int(number_of_shares) < 2:
            #    msg = "Number of shares must be at least 2 for a collective."
            #    self.add_error('number_of_shares', msg)

    def _clean_fields(self):
        super(JoinRequestInternalForm, self)._clean_fields()
        for name, value in self.cleaned_data.items():
            self.cleaned_data[name] = bleach.clean(value)


class JoinAgentSelectionForm(forms.Form):
    created_agent = AgentModelChoiceField(
        queryset=EconomicAgent.objects.without_join_request(),
        required=False)


class ProjectSelectionFilteredForm(forms.Form):
    context_agent = forms.ChoiceField()

    def __init__(self, agent, *args, **kwargs):
        super(ProjectSelectionFilteredForm, self).__init__(*args, **kwargs)
        projects = agent.managed_projects()
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


class ExchangeNavForm(forms.Form):
    exchange_type = forms.ModelChoiceField(
        queryset=ExchangeType.objects.all(),
        #empty_label=None,
        widget=forms.Select(
            attrs={'class': 'exchange-selector chzn-select'}))

    def __init__(self, agent=None, *args, **kwargs):
        super(ExchangeNavForm, self).__init__(*args, **kwargs)
        if agent:
          context_ids = [c.id for c in agent.related_all_contexts()]
          if not agent.id in context_ids:
            context_ids.append(agent.id)
          self.fields["exchange_type"].queryset = ExchangeType.objects.filter(context_agent__id__in=context_ids)
          if not self.fields["exchange_type"].queryset:
            self.fields["exchange_type"] = False


class ExchangeContextForm(forms.ModelForm):
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
        #import pdb; pdb.set_trace()
        self.fields["member"].queryset = agent.invoicing_candidates()


class WorkEventContextAgentForm(forms.ModelForm):
    event_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    resource_type = WorkModelChoiceField(
        queryset=EconomicResourceType.objects.filter(behavior="work"),
        label="Type of work done",
        #empty_label=None,
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
        fields = ('event_date', 'resource_type','quantity', 'description', 'from_agent', 'is_contribution')

    def __init__(self, context_agent=None, *args, **kwargs):
        super(WorkEventContextAgentForm, self).__init__(*args, **kwargs)
        #import pdb; pdb.set_trace()
        if context_agent:
            self.context_agent = context_agent
            self.fields["from_agent"].queryset = context_agent.related_all_contexts_queryset()


class ContextTransferForm(forms.Form):
    event_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    to_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transferred to",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    from_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transferred from",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    quantity = forms.DecimalField(
        label="Quantity transferred",
        initial=1,
        widget=forms.TextInput(attrs={'class': 'quantity input-small',}))
    resource_type = forms.ModelChoiceField(
        queryset=EconomicResourceType.objects.all(),
        #empty_label=None,
        widget=forms.Select(
            attrs={'class': 'resource-type-for-resource chzn-select'}))
    resource = ResourceModelChoiceField(
        queryset=EconomicResource.objects.none(),
        label="Resource transferred (optional if not inventoried)",
        required=False,
        widget=forms.Select(attrs={'class': 'resource input-xlarge chzn-select',}))
    from_resource = ResourceModelChoiceField(
        queryset=EconomicResource.objects.none(),
        label="Resource transferred from (optional if not inventoried)",
        required=False,
        widget=forms.Select(attrs={'class': 'resource input-xlarge chzn-select',}))
    value = forms.DecimalField(
        label="Value (total, not per unit)",
        initial=0,
        required=False,
        widget=forms.TextInput(attrs={'class': 'quantity value input-small',}))
    unit_of_value = forms.ModelChoiceField(
        empty_label=None,
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

    def __init__(self, transfer_type=None, context_agent=None, resource_type=None, posting=False, *args, **kwargs):
        super(ContextTransferForm, self).__init__(*args, **kwargs)
        #import pdb; pdb.set_trace()
        if transfer_type:
            rts = transfer_type.get_resource_types()
            self.fields["resource_type"].queryset = rts
            if posting:
                self.fields["resource"].queryset = EconomicResource.objects.all()
                self.fields["from_resource"].queryset = EconomicResource.objects.all()
            else:
                if rts:
                    if resource_type:
                        self.fields["resource"].queryset = EconomicResource.objects.filter(resource_type=resource_type)
                        self.fields["from_resource"].queryset = EconomicResource.objects.filter(resource_type=resource_type)
                    else:
                        self.fields["resource"].queryset = EconomicResource.objects.filter(resource_type=rts[0])
                        self.fields["from_resource"].queryset = EconomicResource.objects.filter(resource_type=rts[0])
            if context_agent:
                self.fields["to_agent"].queryset = transfer_type.to_context_agents(context_agent)
                self.fields["from_agent"].queryset = transfer_type.from_context_agents(context_agent)


class ContextTransferCommitmentForm(forms.Form):
    commitment_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    due_date = forms.DateField(required=True,
        widget=forms.TextInput(attrs={'class': 'input-small date-entry',}))
    to_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transfer to",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    from_agent = forms.ModelChoiceField(
        required=False,
        queryset=EconomicAgent.objects.all(),
        label="Transfer from",
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    quantity = forms.DecimalField(
        label="Quantity",
        initial=1,
        widget=forms.TextInput(attrs={'class': 'quantity input-small',}))
    resource_type = forms.ModelChoiceField(
        queryset=EconomicResourceType.objects.all(),
        #empty_label=None,
        widget=forms.Select(
            attrs={'class': 'resource-type-for-resource chzn-select'}))
    value = forms.DecimalField(
        label="Value (total, not per unit)",
        initial=0,
        required=False,
        widget=forms.TextInput(attrs={'class': 'value quantity input-small',}))
    unit_of_value = forms.ModelChoiceField(
        empty_label=None,
        required=False,
        queryset=Unit.objects.filter(unit_type='value'),
        widget=forms.Select(
            attrs={'class': 'chzn-select'}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'item-description',}))

    def __init__(self, transfer_type=None, context_agent=None, posting=False, *args, **kwargs):
        super(ContextTransferCommitmentForm, self).__init__(*args, **kwargs)
        #import pdb; pdb.set_trace()
        if transfer_type:
            self.fields["resource_type"].queryset = transfer_type.get_resource_types()
            if context_agent:
                self.fields["to_agent"].queryset = transfer_type.to_context_agents(context_agent)
                self.fields["from_agent"].queryset = transfer_type.from_context_agents(context_agent)



class ResourceRoleContextAgentForm(forms.ModelForm):
    id = forms.CharField(required=False, widget=forms.HiddenInput)
    role = forms.ModelChoiceField(
        queryset=AgentResourceRoleType.objects.all(),
        required=False,
        widget=forms.Select(
            attrs={'class': 'select-role chzn-select'}))
    agent = AgentModelChoiceField(
        queryset=EconomicAgent.objects.resource_role_agents(),
        required=False,
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
          context_agents = context_agent.related_all_contexts_queryset() # EconomicAgent.objects.context_agents() #
          self.fields["agent"].queryset = context_agents


class NewContextExchangeTypeForm(forms.ModelForm):
    use_case = forms.ModelChoiceField(
        queryset=UseCase.objects.exchange_use_cases(),
        empty_label=None,
        widget=forms.Select(
            attrs={'class': 'use-case chzn-select'}))
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'input-xlarge',})) # not required now, to be set in the next page

    class Meta:
        model = ExchangeType
        fields = ('use_case', 'name')
