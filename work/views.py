#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
from decimal import Decimal

from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import formset_factory, modelformset_factory, inlineformset_factory, BaseModelFormSet
from django.forms import ValidationError
import json as simplejson
from collections import OrderedDict
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import validators
from django.utils.translation import ugettext, ugettext_lazy as _

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.forms import *
from valuenetwork.valueaccounting.service import ExchangeService
from work.forms import *
from work.utils import *
from valuenetwork.valueaccounting.views import *
from faircoin import utils as faircoin_utils
from faircoin.models import FaircoinTransaction

from fobi.models import FormEntry
from general.models import Artwork_Type #, Unit_Type

import logging
loger = logging.getLogger("ocp")

if "pinax.notifications" in settings.INSTALLED_APPS:
    from pinax.notifications import models as notification
else:
    notification = None

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

def get_url_starter(request=None):
    if request:
        domain = request.get_host()
    else:
        domain = Site.objects.get_current().domain
    return "".join(["https://", domain])

def work_home(request):

    return render(request, "work_home.html", {
        "help": get_help("work_home"),
    })


@login_required
def my_dashboard(request):
    agent = get_agent(request)
    for pro in agent.managed_projects():
        if hasattr(pro, 'project') and pro.project:
            if not pro.email and pro.project.is_moderated() and pro.project.join_requests:
                messages.warning(request, _("Please provide an email for the project \"{0}\" to use as a remitent for its moderated joining process notifications!").format(pro.name))

    return render(request, "work/my_dashboard.html", {
        "agent": agent,
    })


def new_features(request):
    new_features = NewFeature.objects.all()

    return render(request, "work/new_features.html", {
        "new_features": new_features,
        "photo_size": (256, 256),
    })

def map(request):
    agent = get_agent(request)
    locations = Location.objects.all()
    nolocs = Location.objects.filter(latitude=0.0)
    latitude = settings.MAP_LATITUDE
    longitude = settings.MAP_LONGITUDE
    zoom = settings.MAP_ZOOM
    return render(request, "work/map.html", {
        "agent": agent,
        "locations": locations,
        "nolocs": nolocs,
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
        "help": get_help("work_map"),
    })

def change_language(request):
    agent = get_agent(request)
    if "language" in request.POST:
        lang = request.POST['language']
        if lang:
            account = request.user.account
            account.language = lang
            account.save()
        else:
            messages.warning(request, "There's no language??")
    else:
        messages.warning(request, "No language in post??")
    next = request.POST['next']
    if not next:
        next = '/'
    return redirect(next)


#    P R O F I L E

@login_required
def profile(request):
    agent = get_agent(request)
    return members_agent(request, agent.id)



@login_required
def change_personal_info(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'work/no_permission.html')
    change_form = WorkAgentCreateForm(instance=agent, data=request.POST or None)
    if request.method == "POST":
        if change_form.is_valid():
            agent = change_form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))

@login_required
def upload_picture(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'work/no_permission.html')
    form = UploadAgentForm(instance=agent, data=request.POST, files=request.FILES)
    if form.is_valid():
        data = form.cleaned_data
        agt = form.save(commit=False)
        agt.changed_by=request.user
        agt.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))

@login_required
def add_worker_to_location(request, location_id, agent_id):
    if location_id and agent_id:
        location = get_object_or_404(Location, id=location_id)
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        agent.primary_location = location
        agent.save()
        return HttpResponseRedirect('/%s/'
            % ('work/profile'))
    else:
        return HttpResponseRedirect('/%s/'
            % ('work/map'))

@login_required
def add_location_to_worker(request, agent_id):
    if request.method == "POST":
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        data = request.POST
        address = data["address"]
        longitude = data["agentLongitude"]
        latitude = data["agentLatitude"]
        location, created = Location.objects.get_or_create(
            latitude=latitude,
            longitude=longitude,
            address=address)
        if created:
            location.name = address
            location.save()
        agent.primary_location = location
        agent.save()
        return HttpResponseRedirect('/%s/'
            % ('work/profile'))
    else:
        return HttpResponseRedirect('/%s/'
            % ('work/map'))


#   P R O F I L E   S K I L L S

@login_required
def update_skills(request, agent_id):
    if request.method == "POST":
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        user_agent = get_agent(request)
        if not user_agent:
            return render(request, 'work/no_permission.html')

        et_work = EventType.objects.get(name="Time Contribution")
        arts = agent.resource_types.filter(event_type=et_work)
        old_skill_rts = []
        for art in arts:
            old_skill_rts.append(art.resource_type)
        new_skills_list = request.POST.getlist('skillChoice')
        new_skill_rts = []
        for rt_id in new_skills_list:
            skill = EconomicResourceType.objects.get(id=int(rt_id))
            new_skill_rts.append(skill)
        for skill in old_skill_rts:
            if skill not in new_skill_rts:
                arts = AgentResourceType.objects.filter(agent=agent).filter(resource_type=skill)
                if arts:
                    art = arts[0]
                    art.delete()
        for skill in new_skill_rts:
            if skill not in old_skill_rts:
                art = AgentResourceType(
                    agent=agent,
                    resource_type=skill,
                    event_type=et_work,
                    created_by=request.user,
                )
                art.save()
        other_form = SkillSuggestionForm(data=request.POST)
        if other_form.is_valid():
            suggestion = other_form.save(commit=False)
            suggestion.suggested_by = request.user
            suggestion.save()
            try:
                suggester = request.user.agent.agent
            except:
                suggester = request.user
            if notification:
                users = User.objects.filter(is_staff=True)
                suggestions_url = get_url_starter(request) + "/accounting/skill-suggestions/"
                if users:
                    site_name = get_site_name(request)
                    notification.send(
                        users,
                        "work_skill_suggestion",
                        {"skill": suggestion.skill,
                        "suggested_by": suggester.name,
                        "suggestions_url": suggestions_url,
                        "site_name": site_name,
                        "current_site": request.get_host(),
                        }
                    )

    return HttpResponseRedirect('/%s/'
        % ('work/profile'))


'''
@login_required
def register_skills(request):
    agent = get_agent(request)
    skills = EconomicResourceType.objects.filter(behavior="work")

    return render(request, "work/register_skills.html", {
        "agent": agent,
        "skills": skills,
    })
'''

#    M E M B E R S H I P



@login_required
def share_payment_fair(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    agent_account = agent.faircoin_resource()
    balance = agent_account.digital_currency_balance()
    pro_agent = None
    req = None
    if request.method == "POST":
        try:
            req_id = request.POST.get('join_request')
            req = JoinRequest.objects.get(id=req_id)
            pro_agent = req.project.agent #EconomicAgent.objects.get(id=cont_id)
            #loger.warning("Found the context agent of the share's payment: "+str(cont_id))
            #return True
        except:
            loger.warning("Can't find the context agent of the share's payment!")
            return False
    if pro_agent and req:
      #candidate_membership = agent.candidate_membership(pro_agent)
      share = pro_agent.project.shares_type() #EconomicResourceType.objects.membership_share()
      share_price = faircoin_utils.share_price_in_fairs(req)
      number_of_shares = req.pending_shares() #resource.owner().number_of_shares()
      share_price = share_price * number_of_shares
      pend_amount = req.payment_pending_amount()
      if not share_price == pend_amount:
        print("Switch share_price:"+str(share_price)+" to pending_amount:"+str(pend_amount)+" for req:"+str(req))
        loger.warning("Switch share_price:"+str(share_price)+" to pending_amount:"+str(pend_amount)+" for req:"+str(req))
        share_price = Decimal(pend_amount)

      wallet = faircoin_utils.is_connected()
      netfee = faircoin_utils.network_fee_fairs()
      fair_rt = faircoin_utils.faircoin_rt()
      cand_shacc = req.agent_shares_account()
      if not cand_shacc:
            raise ValidationError("Can't find the candidate share's account of type: "+str(pro_agent.shares_account_type()))
      if not wallet:
            messages.error(request, 'Sorry, payment with faircoin is not available now. Try later.')
      elif round(Decimal(share_price), settings.CRYPTO_DECIMALS) <= round(balance, settings.CRYPTO_DECIMALS):
        #pay_to_id = settings.SEND_MEMBERSHIP_PAYMENT_TO
        pay_to_agent = pro_agent #EconomicAgent.objects.get(nick=pay_to_id)
        pay_to_account = pay_to_agent.faircoin_resource()
        quantity = Decimal(share_price)
        address_origin = agent_account.faircoin_address.address
        address_end = pay_to_account.faircoin_address.address
        xt = req.exchange_type() #ExchangeType.objects.membership_share_exchange_type()
        if not xt:
            raise ValidationError("Can't find the exchange_type related the jn_req! "+str(req))

        #tts = xt.transfer_types.all()
        #tt_share = tts.get(name__contains="Share")
        #tt_fee = tts.get(name__contains="Fee")
        from_agent = agent
        to_resource = pay_to_account
        to_agent = pay_to_agent
        #et_give = EventType.objects.get(name="Give")
        #et_receive = EventType.objects.get(name="Receive")
        date = datetime.date.today()
        #fc = EconomicAgent.objects.freedom_coop()

        exchange = req.exchange
        if not exchange:
            updated = req.update_payment_status('pending')
            if not updated:
                raise ValidationError("Error updating the payment status to pending. jr:"+str(req.id))
            exchange = req.exchange
            #raise ValidationError("Can't find the exchange related the shares payment!")
        evts = exchange.all_events()
        if evts:
            raise ValidationError("The exchange already has events? "+str(evts))



        state =  "new"

        updated = req.update_payment_status('complete', address_end, address_origin, request)
        if not updated:
            raise ValidationError("Error updating the payment status to complete.")
        evts = req.exchange.all_events()
        for ev in evts:
            if ev.resource_type == req.payment_unit_rt() and ev.resource_type == fair_rt:
                fairtx = FaircoinTransaction(
                    event = ev,
                    tx_state = state,
                    to_address = address_end,
                    amount = quantity,
                    minus_fee = True,
                )
                fairtx.save()
                print("- created FaircoinTransaction: "+str(fairtx))
                loger.info("- created FaircoinTransaction: "+str(fairtx))
                if not ev.event_reference == address_end:
                    ev.event_reference = address_end
                    print("-- added event_reference to ev:"+str(ev.id)+" "+str(ev))
                    loger.info("-- added event_reference to ev:"+str(ev.id)+" "+str(ev))
                if not ev.description:
                    ev.description = ev.transfer.transfer_type.name
                    print("-- added description to ev:"+str(ev.id)+" "+str(ev))
                    loger.info("-- added description to ev:"+str(ev.id)+" "+str(ev))
                if not ev.from_agent:
                    ev.from_agent = from_agent
                    print("-- added from_agent to ev:"+str(ev.id)+" ag:"+str(agent))
                    loger.info("-- added from_agent to ev:"+str(ev.id)+" ag:"+str(agent))
                if not ev.to_agent:
                    ev.to_agent = to_agent
                    print("-- added to_agent to ev:"+str(ev.id)+" ag:"+str(agent))
                    loger.info("-- added to_agent to ev:"+str(ev.id)+" ag:"+str(agent))

                ev.save()
                break

        messages.info(request, _("You've payed the shares with your faircoins! The exchange is now complete and the shares has been transfered."))

        #resource = agent_account


      else:
          loger.error("No enough funds... req:"+str(req.id)+" ag:"+str(req.agent)+" pro:"+str(pro_agent)+" netfee: "+str(netfee)+" ƒ")
          messages.error(request, "No enough funds... maybe missing the network fee? "+str(netfee)+" ƒ")

    else: # not req or not pro_agent
        loger.warning("Can't find pro_agent:"+str(pro_agent)+" or req:"+str(req))
        raise ValidationError("Can't find pro_agent:"+str(pro_agent)+" or req:"+str(req))
        #messages.error(request,
        #    'Sorry, payment with faircoin is not available now. Try later.')

    return redirect('project_feedback', agent_id=req.agent.id, join_request_id=req.id) #HttpResponseRedirect('/%s/'
        #% ('work/home'))


"""
def membership_request(request):
    membership_form = MembershipRequestForm(data=request.POST or None)
    if request.method == "POST":
        if membership_form.is_valid():
            human = True
            data = membership_form.cleaned_data
            type_of_membership = data["type_of_membership"]
            number_of_shares = data["number_of_shares"]
            name = data["name"]
            surname = data["surname"]
            description = data["description"]
            mbr_req = membership_form.save()

            event_type = EventType.objects.get(relationship="todo")
            description = "Create an Agent and User for the Membership Request from "
            description += name
            membership_url= get_url_starter() + "/accounting/membership-request/" + str(mbr_req.id) + "/"
            context_agent=EconomicAgent.objects.get(nick=settings.SEND_MEMBERSHIP_PAYMENT_TO)
            resource_types = EconomicResourceType.objects.filter(behavior="work")
            rts = resource_types.filter(
                Q(name__icontains="Admin")|
                Q(name__icontains="Coop")|
                Q(name__icontains="Work"))
            if rts:
                rt = rts[0]
            else:
                rt = resource_types[0]

            task = Commitment(
                event_type=event_type,
                description=description,
                resource_type=rt,
                context_agent=context_agent,
                url=membership_url,
                due_date=datetime.date.today(),
                quantity=Decimal("1")
                )
            task.save()


            if notification:
                users = User.objects.filter(is_staff=True)
                if users:
                    site_name = get_site_name()
                    notification.send(
                        users,
                        "work_membership_request",
                        {"name": name,
                        "surname": surname,
                        "type_of_membership": type_of_membership,
                        "description": description,
                        "site_name": site_name,
                        "current_site": request.get_host(),
                        "membership_url": membership_url,
                        }
                    )

            return HttpResponseRedirect('/%s/'
                % ('membershipthanks'))
    return render(request, "work/membership_request.html", {
        "help": get_help("work_membership_request"),
        "membership_form": membership_form,
    })
"""

def membership_discussion(request, membership_request_id):
    user_agent = get_agent(request)
    mbr_req = get_object_or_404(MembershipRequest, pk=membership_request_id)
    allowed = False
    if user_agent:
        if user_agent.membership_request() == mbr_req or request.user.is_staff:
            allowed = True
    if not allowed:
        return render(request, 'work/no_permission.html')

    fdc = Project.objects.filter(fobi_slug='freedom-coop')
    if fdc:
        fdc = fdc[0].agent
        for jr in mbr_req.agent.project_join_requests.all():
            if jr.project.agent == fdc:
                print("Already existent join request!! "+str(jr))
                loger.info("Already existent join request!! "+str(jr))
                #return project_feedback(request, agent_id=fdc.id, join_request_id=jr.id)
                #migrate_fdc_shares(request, jr)
                return HttpResponseRedirect(reverse('project_feedback', args=(fdc.id, jr.pk)))

        form_entry = fdc.project.fobi_form()

        if form_entry:
            form_element_entries = form_entry.formelemententry_set.all()[:]

            # This is where the most of the magic happens. Our form is being built
            # dynamically.
            FormClass = assemble_form_class(
                form_entry,
                form_element_entries = form_element_entries,
                request = request
            )
            obj = {}
            for fil in form_element_entries:
                filnam = json.loads(fil.plugin_data)['name']
                if filnam == 'languages':
                    obj[filnam] = mbr_req.native_language
                if filnam == 'freedomcoopshares':
                    obj[filnam] = mbr_req.number_of_shares
                if filnam == 'fairnetwork_username':
                    obj[filnam] = mbr_req.fairnetwork
                if filnam == 'usefaircoin_profile':
                    obj[filnam] = mbr_req.usefaircoin
                if filnam == 'fairmarket_shop':
                    obj[filnam] = mbr_req.fairmarket
                if filnam == 'otherfaircoopparticipantsreferences':
                    obj[filnam] = mbr_req.known_member
                if filnam == 'comments_and_questions':
                    obj[filnam] = mbr_req.comments_and_questions
                if filnam == 'description':
                    obj[filnam] = mbr_req.description
                if filnam == 'website':
                    obj[filnam] = mbr_req.website
                if filnam == 'payment_mode':
                    obj[filnam] = 'faircoin'
            #print("OBJ: "+str(obj))
            print("FdC shares: "+str(fdc.project.share_types()))
            loger.info("FdC shares: "+str(fdc.project.share_types()))
            #print("FdC req_date: "+str(mbr_req.request_date))

            fobi_form = FormClass(obj, request.FILES)

            fire_form_callbacks(form_entry=form_entry, request=request, form=fobi_form, stage=CALLBACK_BEFORE_FORM_VALIDATION)
            if fobi_form.is_valid():
                #print("valid!")
                jn_req, created = JoinRequest.objects.get_or_create(
                    project=fdc.project,
                    request_date=mbr_req.request_date,
                    type_of_user=mbr_req.type_of_membership,
                    name=mbr_req.name,
                    surname=mbr_req.surname,
                    requested_username=mbr_req.requested_username,
                    email_address=mbr_req.email_address,
                    phone_number=mbr_req.phone_number,
                    address=mbr_req.address,
                    agent=mbr_req.agent,
                    state=mbr_req.state
                )
                if created:
                    print("- created JoinRequest for FdC migration: "+str(jn_req))
                    loger.info("- created JoinRequest for FdC migration: "+str(jn_req))
                jn_req.created_date = mbr_req.request_date
                jn_req.request_date = mbr_req.request_date
                jn_req.state = mbr_req.state


                # fobi form
                field_name_to_label_map, cleaned_data = get_processed_form_data(
                    fobi_form,
                    form_element_entries
                )
                fob_dat, created = SavedFormDataEntry.objects.get_or_create(
                    form_entry = form_entry,
                    user = mbr_req.agent.user().user if mbr_req.agent.user() else None,
                    form_data_headers = json.dumps(field_name_to_label_map),
                    saved_data = json.dumps(cleaned_data),
                    created = mbr_req.request_date
                )
                if created:
                    print("- created fobi SavedFormDataEntry for FdC migration: "+str(json.dumps(cleaned_data)))
                    loger.info("- created fobi SavedFormDataEntry for FdC migration: "+str(json.dumps(cleaned_data)))

                jn_req.fobi_data = fob_dat
                jn_req.save()

                con_typ = ContentType.objects.get(model='membershiprequest')
                jr_con_typ = ContentType.objects.get(model='joinrequest')
                coms = Comment.objects.filter(content_type=con_typ, object_pk=mbr_req.id)
                #print("Comments: "+str(coms))
                for com in coms:
                    jn_com, created = Comment.objects.get_or_create(
                        content_type=jr_con_typ,
                        object_pk=jn_req.pk,
                        user_name=com.user_name,
                        user_email=com.user_email,
                        submit_date=com.submit_date,
                        comment=com.comment,
                        site=com.site
                    )
                    if created:
                        print("- created Comment for JoinRequest (FdC migration): "+str(jn_req.id)+" by "+str(jn_com.user_name)+" to join "+str(jn_req.project.agent.nick)) #com.comment.encode('utf-8'))
                        loger.info("- created Comment for JoinRequest (FdC migration): "+str(jn_req.id)+" by "+str(jn_com.user_name)+" to join "+str(jn_req.project.agent.nick)) #com.comment.encode('utf-8')))

                messages.info(request, _("The old FdC membership request has been converted to the new modular join_request system, copying all the fields and the comments in the thread."))

                request.auto_resource = create_user_accounts(request, jn_req.agent, jn_req.project)
                #if not auto_resource == '':
                #    messages.warning(request, auto_resource)

                migrate_fdc_shares(request, jn_req)

                return project_feedback(request, agent_id=fdc.id, join_request_id=jn_req.id)
                #return HttpResponseRedirect(reverse('project_feedback', args=(fdc.id, jn_req.id)))
            else:
                print("Fobi form not valid: "+str(fobi_form.errors))
                loger.error("Fobi form not valid: "+str(fobi_form.errors))
        else:
            print("ERROR form_entry not found")
            loger.error("ERROR form_entry not found")
    else:
        print("ERROR FdC not found")
        loger.error("ERROR FdC not found")

    return render(request, "work/membership_request_with_comments.html", {
        "help": get_help("membership_request"),
        "mbr_req": mbr_req,
        "user_agent": user_agent,
    })


def migrate_fdc_shares(request, jr):
    fdc = Project.objects.filter(fobi_slug='freedom-coop')
    if len(fdc) == 1:
        fdc = fdc[0].agent
    else:
        raise ValidationError("More than one or none projects with fobi_slug 'freedom-coop'")
    if not fdc == jr.project.agent:
        #loger.warning("skip migrate, is not a FdC joinrequest")
        return
    user_agent = get_agent(request)
    shacct = fdc.project.shares_account_type()
    shrtyp = fdc.project.shares_type()
    if not jr.agent:
        #raise ValidationError("Missing the join-request agent??")
        return
    mems = jr.agent.membership_requests.all()
    if len(mems) > 1:
        raise ValidationError("More than one membership request to migrate?! agent:"+str(jr.agent))
    elif not mems:
        pass
    else:
        mem = mems[0]
        if not mem.state == 'accepted':
            print("FdC membership still not accepted! "+str(mem))
            loger.info("FdC membership still not accepted! "+str(mem))
        if False and not jr.state == mem.state:
            print("- FdC update state of jn_req: "+str(mem.state))
            loger.info("- FdC update state of jn_req: "+str(jr))
            #messages.warning(request, "- FdC update state of jn_req: "+str(jr))
            jr.state = mem.state
            jr.save()

    aamem = AgentAssociationType.objects.get(identifier="member")
    agrel = None
    agrels = jr.agent.is_associate_of.filter(has_associate=jr.project.agent).exclude(association_type__association_behavior='manager')
    if len(agrels) == 1:
        agrel = agrels[0]
        if agrel.state == 'active' and not jr.state == 'accepted':
            agrel.state = 'potential'
            agrel.save()
            print("WRONG member Relation! without accepted jn_req should be 'candidate': "+str(agrel))
            loger.info("WRONG member Relation! without accepted jn_req should be 'candidate': "+str(agrel))
            if user_agent in fdc.managers():
                messages.warning(request, "Converted the agent relation to 'candidate' because the join request is not accepted yet.")
        elif agrel.state == 'candidate':
            agrel.state = 'potential'
            agrel.save()
            print("Changed 'candidate' for 'potential' state of the agent relation: "+str(agrel))
        if not agrel.association_type == aamem:
            print("WRONG agent association type! "+str(agrel.association_type)+" now converted to 'member': "+str(jr))
            loger.info("WRONG agent association type! "+str(agrel.association_type)+" now converted to 'member': "+str(jr))
            if user_agent in fdc.managers():
                messages.warning(request, "WRONG agent association type! "+str(agrel.association_type)+" now converted to 'member': "+str(jr))
            agrel.association_type = aamem
            agrel.save()
    elif not agrels:
        agrel, created = AgentAssociation.objects.get_or_create(
            has_associate = jr.project.agent,
            is_associate = jr.agent,
            state = 'potential',
            association_type = aamem)
        if created:
            print("- created missing AgentAssociation: "+str(agrel))
            loger.info("- created missing AgentAssociation: "+str(agrel))
            messages.info(request, "- created missing AgentAssociation: "+str(agrel))
    else:
        #agrels = jr.agent.is_associate_of.all() #filter(has_associate=jr.project.agent)
        print("FdC migrating agent has more than one relation with FdC?? "+str(agrels)+" jr:"+str(jr))
        loger.info("FdC migrating agent has more than one relation with FdC?? "+str(agrels)+" jr:"+str(jr))
        messages.error(request, "FdC migrating agent has more than one relation with FdC?? "+str(agrels)) #+" jr:"+str(jr))

    fdcshrt = EconomicResourceType.objects.membership_share()
    shs = []
    arrs = jr.agent.resource_relationships()
    res = list(set([arr.resource for arr in arrs]))
    account = None
    for rs in res:
        if rs.resource_type == shacct:
            account = rs
        if rs.resource_type == fdcshrt:
            shs.append(rs)
    if account:
        if len(shs) > 0:
            #print(shs)
            tot = 0
            for sh in shs:
                tot += sh.quantity
            account.price_per_unit = tot
            account.save()
            loger.info("FdC shares had been migrated to the new system for agent "+str(jr.agent)+" shs:"+str(shs))
            messages.warning(request, "FdC shares had been migrated to the new system for agent "+str(jr.agent))
            for sh in shs:
                for ar in arrs:
                    if ar.resource == sh:
                        account.created_date = sh.created_date
                        account.save()
                        for ev in sh.events.all():
                            ev.resource = account
                            ev.save()
                        sh.quantity = 0
                        ar.delete()
                        if sh.is_deletable():
                            sh.delete()
                        else:
                            loger.info("WARN! The old Share can't be deleted? sh:"+str(sh.id)+" sh.__dict__: "+str(sh.__dict__))
                        loger.info("FdC shares of the old system has been deleted, now they are as the value of the new FdC Shares Account for agent: "+str(jr.agent))
                        messages.warning(request, "FdC shares of the old system has been deleted, now they are as the value of the new FdC Shares Account for agent: "+str(jr.agent))

        else:
            print("FdC migrating agent has no old owned shares: "+str(jr.agent)+' jr.state:'+str(jr.state)) #share:'+str(fdcshrt)+' unit:'+str(shacct.unit_of_price)
            loger.info("FdC migrating agent has no old owned shares: "+str(jr.agent)+' jr.state:'+str(jr.state)) #+' share:'+str(fdcshrt)+' unit:'+str(shacct.unit_of_price))
            if jr.state == 'accepted' and not account.price_per_unit:
                jr.state = 'new'
                jr.save()
                print("WRONG STATE! jr without shares should be 'new' or 'declined': "+str(jr))
                loger.info("WRONG STATE! jr without shares should be 'new' or 'declined': "+str(jr))
                messages.warning(request, "Converted the join request state to 'new' because the member has no shares yet.")

                if agrel.state == 'active' or not agrel.association_type == aamem:
                    agrel.state = 'potential'
                    agrel.association_type = aamem
                    agrel.save()
                    print("- Repaired also an AgentAssociation 'active' state! like the jn_req, is now candidate ('potential') "+str(agrel))
                    loger.info("- Repaired also an AgentAssociation 'active' state! like the jn_req, is now candidate ('potential') "+str(agrel))
                    messages.warning(request, "- Repaired also an AgentAssociation 'active' state! like the jn_req, is now candidate ('potential') "+str(agrel))

            # transfer shares if payed
            if user_agent in fdc.managers() or user_agent == fdc or request.user.is_superuser:
              if jr.pending_shares() and jr.payment_payed_amount() >= jr.total_price():

                print("Found payed tx but shares missing, TRANSFER project shares! jr:"+str(jr))

    else:
        #print(str(shacct)+' not in res: '+str(res))
        loger.info("Can't migrate FdC shares before user has shares account! jr:"+str(jr.id)+" ag:"+str(jr.agent))
        if user_agent in fdc.managers() or request.user.is_superuser:
            messages.warning(request, "Can't migrate FdC shares before user has shares account! "+str(jr.agent))

    et = jr.exchange_type()
    if not et:
        print("Can't migrate FdC shares before the joinrequest has an exchange type! "+str(jr.agent))
        loger.info("Can't migrate FdC shares before the joinrequest has an exchange type! "+str(jr.agent))
        if user_agent in fdc.managers():
            messages.warning(request, "Can't migrate FdC shares before the joinrequest has an exchange type! "+str(jr.agent))
        return

    if et.context_agent and not et.context_agent == fdc:
        print("- Change exchange_type context agent to FdC! "+str(et.context_agent))
        loger.info("- Change exchange_type context agent to FdC! "+str(et.context_agent))
        et.context_agent = fdc
        et.save()
    elif not et.context_agent:
        print("- Add exchange_type context_agent to FdC! "+str(et)) #.context_agent)
        loger.info("- Add exchange_type context_agent to FdC! "+str(et)) #.context_agent))
        et.context_agent = fdc
        et.save()
    tts = et.transfer_types.all()
    paytt = None
    shrtt = None
    for tt in tts:
        #print("-- tt: "+str(tt))
        if "payment" in tt.name:
            paytt = tt
        else:
            shrtt = tt
    if not paytt:
        print("Can't find a transfer type about 'payment' in the exchange type: "+str(et)+". Abort!")
        loger.error("Can't find a transfer type about 'payment' in the exchange type: "+str(et)+" Abort!")
        return
    if not shrtt:
        print("Can't find a transfer type about 'shares' in the exchange type: "+str(et)+". Abort!")
        loger.error("Can't find a transfer type about 'shares' in the exchange type: "+str(et)+" Abort!")
        return

    et_give = EventType.objects.get(name="Give")
    et_receive = EventType.objects.get(name="Receive")
    unit_rt = jr.payment_unit_rt()
    unit = jr.payment_unit()
    fairres = jr.agent.faircoin_resource()

    exs = Exchange.objects.exchanges_by_type(jr.agent)
    exmem = None
    for ex in exs:
      #if ex.exchange_type == et:
        txs = ex.transfers.all()
        coms = ex.xfer_commitments()
        evnz = ex.xfer_events()
        txtps = ex.exchange_type.transfer_types.all()
        #print("-Found exchange: "+str(ex.id)+": "+str(ex)+" ca: "+str(ex.context_agent)+" coms: "+str(len(coms))+" evnz:"+str(len(evnz))+" paytt:"+str(paytt.id)+" shrtt:"+str(shrtt.id))
        #loger.debug("-Found exchange: "+str(ex.id)+": "+str(ex)+" ca: "+str(ex.context_agent)+" coms: "+str(len(coms))+" evnz:"+str(len(evnz))+" paytt:"+str(paytt.id)+" shrtt:"+str(shrtt.id))
        txpay = None
        txshr = None
        for txtp in txtps:
          for tx in txs:
            if tx.transfer_type == txtp:
              if txtp == paytt:
                txpay = tx
              if txtp == shrtt:
                txshr = tx
        if not txpay and not txshr:
            if ex.exchange_type == et:
                print("-Error! no txpay nor txshr but same et, recreate exchange? "+str(ex))
                loger.info("-Error! no txpay nor txshr but same et, recreate exchange? "+str(ex))
                note = 'repaired '+str(datetime.date.today())+'. '
                #jr.create_exchange(note, ex)
            else:
                #print("--Not found txpay with paytt:"+str(paytt.id)+" nor txshr with shrtt:"+str(shrtt.id)+" SKIP! ex:"+str(ex.id)+" "+str(ex))
                #loger.debug("--Not found txpay with paytt:"+str(paytt.id)+" nor txshr with shrtt:"+str(shrtt.id)+" SKIP! ex:"+str(ex.id)+" "+str(ex))
                continue
        elif not txpay or not txshr:
            print("- - found just one tx? (will rebuild) txpay:"+str(txpay)+" txshr:"+str(txshr))
            loger.debug("- - found just one tx? (will rebuild) txpay:"+str(txpay)+" txshr:"+str(txshr))

        for txtp in txtps:
          txtp.found = None
          for tx in txs:
            if tx.transfer_type == txtp:
              txtp.found = tx
              if tx.to_agent() == fdc: #and tx.from_agent():
                print("------------------")
                if exmem and ex.exchange_type == exmem.exchange_type:
                    print("DUPLICATE exchanges? "+str(ex.id)+": txs:"+str(len(ex.transfers.all()))+": cms:"+str(len(ex.commitments.all()))+": evs:"+str(len(ex.events.all()))+" <> "+str(exmem.id)+": txs:"+str(len(exmem.transfers.all()))+": cms:"+str(len(exmem.commitments.all()))+": evs:"+str(len(exmem.events.all())))
                    loger.info("DUPLICATE exchanges? "+str(ex.id)+" <> "+str(exmem.id))
                    memcms = exmem.commitments.all()
                    memevs = exmem.events.all()
                    memtxs = exmem.transfers.all()
                    jrmem = None
                    jrex = None
                    if hasattr(exmem, 'join_request'):
                        jrmem = exmem.join_request
                    if hasattr(ex, 'join_request'):
                        jrex = ex.join_request


                    for tf in ex.transfers.all():
                        if not tf in memtxs:
                            print("- Found transfer related a duplicate exchange, merge to the same unique exchange of this type! "+str(tx))
                            loger.info("Found transfer related a duplicate exchange, merge to the same unique exchange of this type! "+str(tx))
                            for mtx in memtxs:
                                coms = mtx.commitments.all()
                                evts = mtx.events.all()
                                if mtx.transfer_type == tf.transfer_type:
                                    koms = tf.commitments.all()
                                    evns = tf.events.all()
                                    print("-- Found same transfer_type: "+str(tf.transfer_type)+" - id:"+str(tf.id)+" in mtx:"+str(mtx.id)+" coms:"+str(len(koms))+" evns:"+str(len(evns)))
                                    loger.info("-- Found same transfer_type: "+str(tf.transfer_type)+" - id:"+str(tf.id)+" in mtx:"+str(mtx.id)+" coms:"+str(len(koms))+" evns:"+str(len(evns)))
                                    if koms:
                                        print("--- Merge comment to the transfer of the duplicate exchange? TODO coms: "+str(koms))
                                        loger.info("--- Merge comment to the transfer of the duplicate exchange? TODO coms: "+str(koms))
                                    if evns:
                                        for ev in evns:
                                          if not ev in evts:
                                            print("--- tx ca:"+str(tf.context_agent)+" txdate:"+str(tf.transfer_date)+" crdate:"+str(tf.created_date)) #+" notes:"+str(tf.notes)
                                            print("--- mtx ca:"+str(mtx.context_agent)+" txdate:"+str(mtx.transfer_date)+" crdate:"+str(mtx.created_date)) #+" notes:"+str(mtx.notes)
                                            print("--- ev ca:"+str(ev.context_agent)+" qty:"+str(ev.quantity)+" u:"+str(ev.unit_of_quantity)+" rs:"+str(ev.resource))
                                            for e in evts:
                                                print("---- mtx.ev: "+str(e.id)+" ca:"+str(e.context_agent)+" qty:"+str(e.quantity)+" u:"+str(e.unit_of_quantity)+" rs:"+str(e.resource))
                                            print("--- Merged event to the transfer of the duplicated exchange! evid:"+str(ev.id)+" txid:"+str(tf.id)+" exid:"+str(ex.id)+" --> txid:"+str(mtx.id)+" exid:"+str(exmem.id)+" evs:"+str(len(memevs)))
                                            loger.info("--- Merged event to the transfer of the duplicated exchange! evid:"+str(ev.id)+" txid:"+str(tf.id)+" exid:"+str(ex.id)+" --> txid:"+str(mtx.id)+" exid:"+str(exmem.id)+" evs:"+str(len(memevs)))
                                            if not jr.exchange == exmem:
                                                print("WARN: Not changed the join_request to the other exchange! SKIP.")
                                                loger.info("WARN: Not changed the join_request to the other exchange! SKIP.")
                                                continue
                                            mtx.notes = "merged events on "+str(tf.created_date)+" from exchange id:"+str(ex.id)+" and transfer id:"+str(ev.transfer.id)
                                            ev.transfer = mtx
                                            ev.exchange = exmem
                                            ev.context_agent = jr.project.agent
                                            ev.save()
                                            mtx.save()
                                            #tf.delete()
                                    else:
                                        print("-- Can't find events for this transfer: "+str(tf))
                                        loger.info("-- Can't find events for this transfer: "+str(tf))

                    if not jrmem and jrex:
                        jrex.exchange = exmem
                        jrex.save()
                        print("- Updated join_request exchange from id:"+str(ex.id)+" to id:"+str(exmem.id))
                        loger.info("- Updated join_request exchange from id:"+str(ex.id)+" to id:"+str(exmem.id))

                    return

                elif not exmem:
                    exmem = ex


                print("- Found exchange: "+str(ex.id)+" tx:"+str(tx.id)+" "+str(tx)+" tx-qty:"+str(tx.actual_quantity())+" tx-val:"+str(tx.actual_value())+" tx-ca:"+str(tx.context_agent)+" tx-coms:"+str(len(tx.commitments.all()))+" tx-evts:"+str(len(tx.events.all())))
                loger.info("- Found exchange: "+str(ex.id)+" tx:"+str(tx.id)+" "+str(tx)+" tx-qty:"+str(tx.actual_quantity())+" tx-val:"+str(tx.actual_value())+" tx-ca:"+str(tx.context_agent)+" tx-coms:"+str(len(tx.commitments.all()))+" tx-evts:"+str(len(tx.events.all())))


                if not ex.exchange_type == et:
                    print("- Changed et: "+str(ex.exchange_type)+" -> "+str(et)+" (ca:"+str(et.context_agent)+")")
                    loger.warning("- Changed et: "+str(ex.exchange_type)+" -> "+str(et)+" (ca:"+str(et.context_agent)+")")
                    ex.exchange_type = et
                    ex.save()
                    messages.warning(request, "- Changed et: "+str(ex.exchange_type)+" -> "+str(et)+" for the exchange: "+str(ex))
                if not ex.name == et.name or not ex.context_agent == fdc:
                    print("- Changed ex.name: "+str(ex))
                    loger.warning("- Changed ex.name: "+str(ex))
                    ex.name = et.name
                    ex.context_agent = fdc
                    ex.save()
                    messages.warning(request, "- Changed ex.name: "+str(ex))

                #print("nom: "+str(nom) # - Trans: "+str(tx.transfer_type.name)+" to:"+str(tx.to_agent().name)+' from:'+str(tx.from_agent().name))
                if not tx.name == paytt.name or not tx.transfer_type == paytt:
                    print("-- Changed tt:"+str(tx.transfer_type)+" -> "+str(paytt))
                    loger.warning("-- Changed tt:"+str(tx.transfer_type)+" -> "+str(paytt))
                    tx.transfer_type = paytt
                    tx.name = paytt.name
                    tx.save()
                    messages.warning(request, "-- Changed tt:"+str(tx.transfer_type)+" -> "+str(paytt))

                if not jr.exchange:
                    jr.exchange = ex
                    print("- Connected exchange to join request: "+str(ex))
                    loger.warning("- Connected exchange to join request: "+str(ex))
                    jr.save()
                    messages.warning(request, "- Connected exchange to join request: "+str(ex))
                for tt in ex.transfers.all():
                    if not tt.transfer_type == paytt and not tt.transfer_type == shrtt:
                        if not tt.events.all() and not tt.commitments.all():
                            print("- delete empty transfer: "+str(tt.id))
                            loger.warning("- delete empty transfer: "+str(tt.id))
                            messages.warning(request, "- delete empty transfer: "+str(tt))
                            if tt.is_deletable():
                                tt.delete()
                        else:
                            print("WARNING: Not deleted Transfer because has events or shares!! "+str(tt))
                            loger.error("WARNING: Not deleted Transfer because has events or shares!! "+str(tt))

                evnts = tx.events.all()
                for evt in evnts:
                    fairtx = None
                    if hasattr(evt, 'faircoin_transaction') and evt.faircoin_transaction:
                        fairtx = evt.faircoin_transaction.id
                        #print("Careful! this event:"+str(evt.id)+" is related a fair_tx:"+str(fairtx))
                        #loger.info("Careful! this event:"+str(evt.id)+" is related a fair_tx:"+str(fairtx))
                    #print("Evt: action:"+str(evt.action)+" unit:"+str(evt.unit())+" fairtx:"+str(fairtx)+" state:"+str(fairtx.tx_state)+" hash:"+str(fairtx.tx_hash))
                    if evt.event_type: # == et_give:
                        if not evt.resource_type == unit_rt:
                            print("- change resource_type? "+str(evt.resource_type)+" -> "+str(unit_rt)+" et:"+str(evt.exchange_stage))
                            loger.info("- change resource_type? "+str(evt.resource_type)+" -> "+str(unit_rt)+" et:"+str(evt.exchange_stage))
                        #if not evt.resource == fairres:
                        #    print("- Don't change event resource: "+str(evt.resource)+" -> "+str(fairres))
                        if not evt.exchange:
                            print("- add exchange to event? "+str(evt)+" ex:"+str(tx.exchange))
                            loger.info("- add exchange to event? "+str(evt)+" ex:"+str(tx.exchange))
                        if not evt.to_agent == fdc:
                            print("- change event to_agent to FdC! "+str(evt.to_agent))
                            loger.info("- change event to_agent to FdC! "+str(evt.to_agent))
                            #evt.to_agent = fdc
                        sh_unit = None
                        if not fairtx:
                          if evt.resource_type.ocp_artwork_type:
                            if evt.resource_type.ocp_artwork_type.general_unit_type:
                                genut = evt.resource_type.ocp_artwork_type.general_unit_type
                                ocput = Ocp_Unit_Type.objects.get(id=genut.id)
                                if ocput:
                                    us = ocput.units()
                                    #print("-- Found shr unit_type: "+str(ocput)+" units:"+str(us))
                                    #loger.debug("-- Found shr unit_type: "+str(ocput)+" units:"+str(us))
                                    if us:
                                        sh_unit = us[0]
                                    else:
                                        print("-- Error: Can't find units for the unit_type: "+str(ocput)+" for event:"+str(evt.id))
                                        loger.error("-- Error: Can't find units for the unit_type: "+str(ocput)+" for event:"+str(evt.id))
                                else:
                                    print("-- Error: Can't find Ocp_Unit_Type with id:"+str(genut.id)+" ut:"+str(genut)+" for event:"+str(evt.id))
                                    loger.error("-- Error: Can't find Ocp_Unit_Type with id:"+str(genut.id)+" ut:"+str(genut)+" for event:"+str(evt.id))
                            else:
                                print("-- Error: The event resource_type.ocp_artwork_type has no general_unit_type? oat:"+str(evt.resource_type.ocp_artwork_type)+" for event:"+str(evt.id))
                                loger.error("-- Error: The event resource_type.ocp_artwork_type has no general_unit_type? oat:"+str(evt.resource_type.ocp_artwork_type)+" for event:"+str(evt.id))
                          else:
                            print("-- The event resource_type has no ocp_artwork_type? rt:"+str(evt.resource_type)+" for event:"+str(evt.id))
                            loger.error("-- The event resource_type has no ocp_artwork_type? rt:"+str(evt.resource_type)+" for event:"+str(evt.id))
                        else:
                            #print("- the event has fairtx! id:"+str(evt.id)+" "+str(evt))
                            #loger.info("- the event has fairtx! id:"+str(evt.id)+" "+str(evt))
                            pass
                        if not sh_unit and not fairtx:
                            print("x Not found share unit in the event, SKIP! id:"+str(evt.id)+" "+str(evt))
                            loger.error("x Not found share unit in the event, SKIP! id:"+str(evt.id)+" "+str(evt))
                            continue
                        if not unit_rt:
                            print("x Not found unit_rt in the event, SKIP! id:"+str(evt.id)+" "+str(evt))
                            loger.error("x Not found unit_rt in the event, SKIP! id:"+str(evt.id)+" "+str(evt))
                            continue

                        evt.exchange = ex
                        evt.exchange_stage = et
                        evt.context_agent = fdc
                        if tx.transfer_type == paytt:
                            if not evt.resource_type == unit_rt:
                                print("-- CHANGED pay_evt:"+str(evt.id)+" resource_type from "+str(evt.resource_type)+" to "+str(unit_rt))
                                loger.info("-- CHANGED pay_evt:"+str(evt.id)+" resource_type from "+str(evt.resource_type)+" to "+str(unit_rt))
                            if not evt.unit_of_quantity == unit:
                                print("-- CHANGED pay_evt:"+str(evt.id)+" unitofqty from "+str(evt.unit_of_quantity)+" to "+str(unit))
                                loger.info("-- CHANGED pay_evt:"+str(evt.id)+" unitofqty from "+str(evt.unit_of_quantity)+" to "+str(unit))
                            evt.resource_type = unit_rt
                            evt.unit_of_quantity = unit
                        elif tx.transfer_type == shrtt and sh_unit:
                            if not evt.resource_type == shrtyp:
                                print("-- CHANGED pay_evt:"+str(evt.id)+" resource_type from "+str(evt.resource_type)+" to "+str(shrtyp))
                                loger.info("-- CHANGED pay_evt:"+str(evt.id)+" resource_type from "+str(evt.resource_type)+" to "+str(shrtyp))
                            if not evt.unit_of_quantity == sh_unit:
                                print("-- CHANGED pay_evt:"+str(evt.id)+" unitofqty from "+str(evt.unit_of_quantity)+" to "+str(sh_unit))
                                loger.info("-- CHANGED pay_evt:"+str(evt.id)+" unitofqty from "+str(evt.unit_of_quantity)+" to "+str(sh_unit))
                            evt.resource_type = shrtyp
                            evt.unit_of_quantity = sh_unit
                        else:
                            raise ValidationError("Transfer with an unknown transfer_type: "+str(tx.transfer_type)+" or nor sh_unit:"+str(sh_unit))
                        evt.save()
                comms = tx.commitments.all()
                if not comms:
                    pass #print("The Transfer has no commitments! "+str(tx))
                else:
                    print("The Transfer has commitments... txid:"+str(tx.id)+" coms: "+str(comms))
                    loger.warning("The Transfer has commitments... txid:"+str(tx.id)+" coms: "+str(comms))
                    for comm in comms:
                        if not comm.resource_type == unit_rt:
                            print("- change comm resource_type? "+str(comm.resource_type)+" -> "+str(unit_rt)+" comm:"+str(comm.id)+" ex:"+str(ex.id)+" tx:"+str(tx.id)+" et:"+str(comm.exchange_stage))
                            loger.info("- change comm resource_type? "+str(comm.resource_type)+" -> "+str(unit_rt)+" comm:"+str(comm.id)+" ex:"+str(ex.id)+" tx:"+str(tx.id)+" et:"+str(comm.exchange_stage))
                        #if not comm.resource == fairres:
                        #    print("- Don't change commitment resource: "+str(comm.resource)+" -> "+str(fairres))
                        if not comm.exchange:
                            print("- add exchange to commitment? "+str(comm)+" ex:"+str(comm.exchange))
                            loger.info("- add exchange to commitment? "+str(comm)+" ex:"+str(comm.exchange))
                        if not comm.to_agent == fdc:
                            print("- change commitment to_agent to FdC! "+str(comm.to_agent))
                            loger.info("- change commitment to_agent to FdC! "+str(comm.to_agent))
                            #evt.to_agent = fdc
                        sh_unit = None
                        if comm.resource_type.ocp_artwork_type:
                            if comm.resource_type.ocp_artwork_type.general_unit_type:
                                genut = comm.resource_type.ocp_artwork_type.general_unit_type
                                ocput = Ocp_Unit_Type.objects.get(id=genut.id)
                                if ocput:
                                    us = ocput.units()
                                    #print("-- Found shr unit_type: "+str(ocput)+" units:"+str(us))
                                    #loger.debug("-- Found shr unit_type: "+str(ocput)+" units:"+str(us))
                                    if us:
                                        sh_unit = us[0]
                                    else:
                                        print("-- Error: Can't find units for the unit_type: "+str(ocput)+" for commitment:"+str(comm.id))
                                        loger.error("-- Error: Can't find units for the unit_type: "+str(ocput)+" for commitment:"+str(comm.id))
                                else:
                                    print("-- Error: Can't find Ocp_Unit_Type with id:"+str(genut.id)+" ut:"+str(genut)+" for commitment:"+str(comm.id))
                                    loger.error("-- Error: Can't find Ocp_Unit_Type with id:"+str(genut.id)+" ut:"+str(genut)+" for commitment:"+str(comm.id))
                            else:
                                print("-- Error: The commitment resource_type.ocp_artwork_type has no general_unit_type? oat:"+str(comm.resource_type.ocp_artwork_type)+" for commitment:"+str(comm.id))
                                loger.error("-- Error: The commitment resource_type.ocp_artwork_type has no general_unit_type? oat:"+str(comm.resource_type.ocp_artwork_type)+" for commitment:"+str(comm.id))
                        else:
                            print("-- The commitment resource_type has no ocp_artwork_type? rt:"+str(comm.resource_type)+" for commitment:"+str(comm.id))
                            loger.error("-- The commitment resource_type has no ocp_artwork_type? rt:"+str(comm.resource_type)+" for commitment:"+str(comm.id))

                        if not sh_unit and not fairtx:
                            print("x Not found share unit in the commitment, SKIP! id:"+str(comm.id)+" "+str(comm))
                            loger.error("x Not found share unit in the commitment, SKIP! id:"+str(comm.id)+" "+str(comm))
                            continue
                        if not unit_rt:
                            print("x Not found unit_rt in the commitment, SKIP! id:"+str(comm.id)+" "+str(comm))
                            loger.error("x Not found unit_rt in the commitment, SKIP! id:"+str(comm.id)+" "+str(comm))
                            continue

                        comm.context_agent = fdc
                        comm.exchange = ex
                        comm.exchange_stage = et
                        if tx.transfer_type == paytt:
                            if not comm.resource_type == unit_rt:
                                print("-- CHANGED pay_comm:"+str(comm.id)+" resource_type from "+str(comm.resource_type)+" to "+str(unit_rt))
                                loger.info("-- CHANGED pay_comm:"+str(comm.id)+" resource_type from "+str(comm.resource_type)+" to "+str(unit_rt))
                            if not comm.unit_of_quantity == unit:
                                print("-- CHANGED pay_comm:"+str(comm.id)+" unitofqty from "+str(comm.unit_of_quantity)+" to "+str(unit))
                                loger.info("-- CHANGED pay_comm:"+str(comm.id)+" unitofqty from "+str(comm.unit_of_quantity)+" to "+str(unit))
                            comm.resource_type = unit_rt
                            comm.unit_of_quantity = unit
                        elif tx.transfer_type == shrtt and sh_unit:
                            if not comm.resource_type == shrtyp:
                                print("-- CHANGED pay_comm:"+str(comm.id)+" resource_type from "+str(comm.resource_type)+" to "+str(shrtyp))
                                loger.info("-- CHANGED pay_comm:"+str(comm.id)+" resource_type from "+str(comm.resource_type)+" to "+str(shrtyp))
                            if not comm.unit_of_quantity == sh_unit:
                                print("-- CHANGED pay_comm:"+str(comm.id)+" unitofqty from "+str(comm.unit_of_quantity)+" to "+str(sh_unit))
                                loger.info("-- CHANGED pay_comm:"+str(comm.id)+" unitofqty from "+str(comm.unit_of_quantity)+" to "+str(sh_unit))
                            comm.resource_type = shrtyp
                            comm.unit_of_quantity = sh_unit
                        else:
                            raise ValidationError("Transfer with an unknown transfer_type: "+str(tx.transfer_type)+" or nor sh_unit:"+str(sh_unit)+" in commitment:"+str(comm.id))
                        comm.save()

                        if not comm.fulfilling_events() and evnts:
                            print("Warning! events to connect to the commitment? comm:"+str(comm.id)+" "+str(comm)+" evnts:"+str(evnts))
                            for ev in evnts:
                                if not ev.commitment == comm:
                                    if comm.resource_type == ev.resource_type:
                                        print("- CONNECTED evt of same tx to the comm:"+str(comm.id)+" evt:"+str(ev.id)+" tx:"+str(tx.id)+" ex:"+str(ex.id))
                                        loger.info("- CONNECTED evt of same tx to the comm:"+str(comm.id)+" evt:"+str(ev.id)+" tx:"+str(tx.id)+" ex:"+str(ex.id))
                                        messages.info(request, "- CONNECTED evt of same tx to the comm:"+str(comm.id)+" evt:"+str(ev.id)+" tx:"+str(tx.id)+" ex:"+str(ex.id))
                                        ev.commitment = comm
                                        ev.save()
                                    else:
                                        print("- tx evt not related the tx commitment, CONNECT as fulfilling_evt ?? Different RT, SKIP! com:"+str(comm.id)+" ev:"+str(ev.id)+" "+str(ev))
                                        loger.info("- tx evt not related the tx commitment, CONNECT as fulfilling_evt ?? Different RT, SKIP! com:"+str(comm.id)+" comrt:"+str(comm.resource_type)+" ev:"+str(ev.id)+" evrt:"+str(ev.resource_type)) #+" "+str(ev))



              elif tx.from_agent() == fdc:
                print(" - Found transfer FROM FdC: "+str(tx.id)+": "+str(tx)+" tx_typ:"+str(tx.transfer_type.id)+" (shtt:"+str(shrtt.id)+") is_shr:"+str(tx.transfer_type.is_share()))
                loger.info("- Found transfer FROM FdC: "+str(tx.id)+": "+str(tx)+" tx_typ:"+str(tx.transfer_type.id)+" (shtt:"+str(shrtt.id)+") is_shr:"+str(tx.transfer_type.is_share()))
                #messages.info(request, "- Found transfer FROM FdC: "+str(tx)+" tx_typ:"+str(tx.transfer_type)+" (shtt:"+str(shrtt.id)+") is_shr:"+str(tx.transfer_type.is_share()))
                txevs = tx.events.all()
                txcms = tx.commitments.all()
                if txcms:
                  for com in txcms:
                    comevs = com.fulfilling_events()
                    #print("TODO -- com: "+str(com)+" comevs:"+str(comevs))
                    #loger.info("TODO -- com: "+str(com)+" comevs:"+str(comevs))
                    if comevs:
                      for ev in comevs:
                        if not ev in evnz:
                            print("- - BAD event, missing connection to exchange. Repair! id:"+str(ev.id)+" "+str(ev))
                            loger.warning("- - BAD event, missing connection to exchange. Repair! id:"+str(ev.id)+" "+str(ev))
                            ev.exchange = ex
                            ev.save()
                    else:
                        print("- - TODO com: "+str(com)+" without events, com_id:"+str(com.id))
                        loger.info("- - TODO com: "+str(com)+", without events, com_id:"+str(com.id))

                else:
                  for evt in txevs:
                    rel_rt = evt.resource.resource_type.ocp_artwork_type.rel_nonmaterial_type
                    if rel_rt:
                        rel_rt = rel_rt.resource_type
                        #print("--- rel_rt:"+str(rel_rt))
                        if not rel_rt == evt.resource_type:
                            print(" - CHANGED the resource_type of the event "+str(evt.id)+" from '"+str(evt.resource_type)+"' to '"+str(rel_rt)+"'")
                            loger.info(" - CHANGE resource_type of the event "+str(evt.id)+" from '"+str(evt.resource_type)+"' to '"+str(rel_rt)+"'")
                            messages.info(request, " - CHANGE resource_type of the event "+str(evt.id)+" from '"+str(evt.resource_type)+"' to '"+str(rel_rt)+"'")
                            evt.resource_type = rel_rt
                            evt.save()
                        if not tx.transfer_type == shrtt and rel_rt and txshr:
                            print(" -- CHANGED the event transfer from '"+str(tx)+"' to '"+str(txshr)+"', evt:"+str(evt.id))
                            loger.info(" -- CHANGED the event transfer from '"+str(tx)+"' to '"+str(txshr)+"', evt:"+str(evt.id))
                            messages.info(request, " -- CHANGED the event transfer from '"+str(tx)+"' to '"+str(txshr)+"', evt:"+str(evt.id))
                            evt.transfer = txshr
                            evt.save()
                    #print("-- evt: "+str(evt.id)+" - "+str(evt)+" rt:"+str(evt.resource_type)+" rs_rt:"+str(evt.resource.resource_type)+" rel_rt:"+str(rel_rt)+" txshr:"+str(txshr.id)+" txpay:"+str(txpay.id))


              elif tx.to_agent() == fdc.parent():
                evs = tx.events.all()
                cms = tx.commitments.all()
                print("Found exchange related to FdC parent! "+str(tx)+" ca:"+str(tx.context_agent)+" evts:"+str(len(evs))+" coms:"+str(len(cms)))
                loger.info("Found exchange related to FdC parent! "+str(tx))
                for ev in evs:
                    if ev.to_agent == fdc.parent():
                        print("- found event related fdc parent! change to_agent to fdc... "+str(ev)+" fairtx:"+str(ev.faircoin_transaction.tx_state)+" to: "+str(ev.faircoin_transaction.to_address))
                        loger.info("- found event related fdc parent! change to_agent to fdc... "+str(ev)+" fairtx:"+str(ev.faircoin_transaction.tx_state)+" to: "+str(ev.faircoin_transaction.to_address))
                        messages.info(request, "- found event related fdc parent! change to_agent to fdc... "+str(ev)+" fairtx:"+str(ev.faircoin_transaction.tx_state)+" to: "+str(ev.faircoin_transaction.to_address))
                        ev.to_agent = fdc
                        ev.save()
                    if ev.from_agent == fdc.parent():
                        print("- found event related fdc parent! change from_agent to fdc... SKIP!"+str(ev))
                        loger.info("- found event related fdc parent! change from_agent to fdc... SKIP! "+str(ev)+" fairtx:"+str(ev.faircoin_transaction.tx_state)+" to: "+str(ev.faircoin_transaction.to_address))
                        ev.from_agent = fdc
                        #ev.save()
                for cm in cms:
                    if cm.to_agent == fdc.parent():
                        print("- found commitment related fdc parent! change to_agent to fdc... "+str(cm))
                        loger.info("- found commitment related fdc parent! change to_agent to fdc... "+str(cm))
                        messages.info(request, "- found commitment related fdc parent! change to_agent to fdc... "+str(cm))
                        cm.to_agent = fdc
                        cm.save()
                    if cm.from_agent == fdc.parent():
                        print("- found commitment related fdc parent! change from_agent to fdc... SKIP! "+str(cm))
                        loger.info("- found commitment related fdc parent! change from_agent to fdc... SKIP! "+str(cm))
                        cm.from_agent = fdc
                        #cm.save()
                return
              elif tx.from_agent() == fdc.parent():
                print("Found exchange related from FdC parent! ex:"+str(ex.id)+" tx:"+str(tx.id)+" "+str(tx))
                loger.info("Found exchange related from FdC parent! ex:"+str(ex.id)+" tx:"+str(tx.id)+" "+str(tx))
                txcoms = tx.commitments.all()
                txevts = tx.events.all()
                if tx.transfer_type == shrtt: # is share
                    for txcom in txcoms:
                        if not txcom.from_agent == fdc:
                            print("- CHANGED txcom.from_agent to FdC in shrtt! (was "+str(txcom.from_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txcom:"+str(txcom.id)+" "+str(txcom))
                            loger.info("- CHANGED txcom.from_agent to FdC in shrtt! (was "+str(txcom.from_agent)+")ex:"+str(ex.id)+" tx:"+str(tx.id)+" txcom:"+str(txcom.id)+" "+str(txcom))
                            txcom.from_agent = fdc
                            txcom.save()
                        for ev in txcom.fulfilling_events():
                            if not ev.from_agent == fdc:
                                print("- CHANGED txcom.event.from_agent to FdC in shrtt! (was "+str(ev.from_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" ev:"+str(ev.id)+" "+str(ev))
                                loger.info("- CHANGED txcom.event.from_agent to FdC in shrtt! (was "+str(ev.from_agent)+")ex:"+str(ex.id)+" tx:"+str(tx.id)+" ev:"+str(ev.id)+" "+str(ev))
                                ev.from_agent = fdc
                                ev.save()
                    for txevt in txevts:
                        if not txevt.from_agent == fdc:
                            print("- CHANGED txevt.from_agent to FdC in shrtt! (was "+str(txevt.from_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txevt:"+str(txevt.id)+" "+str(txevt))
                            loger.info("- CHANGED txevt.from_agent to FdC in shrtt! (was "+str(txevt.from_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txevt:"+str(txevt.id)+" "+str(txevt))
                            txevt.from_agent = fdc
                            txevt.save()
                elif tx.transfer_type == paytt: # is payment
                    for txcom in txcoms:
                        if not txcom.to_agent == fdc:
                            print("- CHANGED txcom.to_agent to FdC in shrtt! (was "+str(txcom.to_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txcom:"+str(txcom.id)+" "+str(txcom))
                            loger.info("- CHANGED txcom.to_agent to FdC in shrtt! (was "+str(txcom.to_agent)+")ex:"+str(ex.id)+" tx:"+str(tx.id)+" txcom:"+str(txcom.id)+" "+str(txcom))
                            txcom.to_agent = fdc
                            txcom.save()
                        for ev in txcom.fulfilling_events():
                            if not ev.to_agent == fdc:
                                print("- CHANGED txcom.event.to_agent to FdC in shrtt! (was "+str(ev.to_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" ev:"+str(ev.id)+" "+str(ev))
                                loger.info("- CHANGED txcom.event.to_agent to FdC in shrtt! (was "+str(ev.to_agent)+")ex:"+str(ex.id)+" tx:"+str(tx.id)+" ev:"+str(ev.id)+" "+str(ev))
                                ev.to_agent = fdc
                                ev.save()
                    for txevt in txevts:
                        if not txevt.to_agent == fdc:
                            print("- CHANGED txevt.to_agent to FdC in shrtt! (was "+str(txevt.to_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txevt:"+str(txevt.id)+" "+str(txevt))
                            loger.info("- CHANGED txevt.to_agent to FdC in shrtt! (was "+str(txevt.to_agent)+") ex:"+str(ex.id)+" tx:"+str(tx.id)+" txevt:"+str(txevt.id)+" "+str(txevt))
                            txevt.to_agent = fdc
                            txevt.save()

              else:
                txcoms = tx.commitments.all()
                txevts = tx.events.all()
                print("Another tx? "+str(tx)+" id:"+str(tx.id)+" ex:"+str(tx.exchange.id)+" tt:"+str(tx.transfer_type.id)+" to:"+str(tx.to_agent())+" from:"+str(tx.from_agent())+" ca:"+str(tx.context_agent)+" coms:"+str(len(txcoms))+" evts:"+str(len(txevts)))
                loger.debug("Another tx? "+str(tx)+" id:"+str(tx.id)+" ex:"+str(tx.exchange.id)+" tt:"+str(tx.transfer_type.id)+" to:"+str(tx.to_agent())+" from:"+str(tx.from_agent())+" ca:"+str(tx.context_agent)+" coms:"+str(len(txcoms))+" evts:"+str(len(txevts)))
                if not tx.context_agent and tx.transfer_type == shrtt:
                    print("- ADDED context_agent FdC to shrtt tx:"+str(tx.id)+" ex:"+str(ex.id))
                    loger.info("- ADDED context_agent FdC to shrtt tx:"+str(tx.id)+" ex:"+str(ex.id))
                    tx.context_agent = fdc
                    tx.save()
                if tx.context_agent == fdc:
                    if tx.transfer_type == shrtt:
                        if jr.total_shares():
                            print("- FOUND tx related shares without to-from related fdc, but the agent has shares! Add event? tx:"+str(tx.id)+" jr:"+str(jr.id)+" shares:"+str(jr.total_shares()))
                            loger.info("- FOUND tx related shares without to-from related fdc, but the agent has shares! Add event? tx:"+str(tx.id)+" jr:"+str(jr.id)+" shares:"+str(jr.total_shares()))
                            evs = EconomicEvent.objects.filter(to_agent=jr.agent, from_agent=fdc)
                            if evs:
                              for ev in evs:
                                print("- - found event:"+str(ev.id)+" "+str(ev))
                                loger.debug("- - found event:"+str(ev.id)+" "+str(ev))
                                continue
                            else:
                                print("Call update_payment_status complete to repair the missing share event... jr:"+str(jr.id))
                                loger.info("Call update_payment_status complete to repair the missing share event... jr:"+str(jr.id))
                                jr.update_payment_status('complete')
                        else:
                            if not jr.payment_pending_amount():
                                print("- CREATE missing Commitment for Shares...")
                                jr.update_payment_status('pending')
                            else:
                                print("- FOUND tx related shares without to-from related fdc, but the agent has no shares! Add commitment? tx:"+str(tx.id)+" jr:"+str(jr.id))
                                loger.info("- FOUND tx related shares without to-from related fdc, but the agent has no shares! Add commitment? tx:"+str(tx.id)+" jr:"+str(jr.id))


                    elif tx.transfer_type == paytt:
                        if not txcoms and not txevts:
                            exevts = tx.exchange.xfer_events()
                            print("- empty paytt tx:"+str(tx.id)+" "+str(tx)+" ex.evts:"+str(len(exevts)))
                            loger.info("- empty paytt tx:"+str(tx.id)+" "+str(tx)+" ex.evts:"+str(len(exevts)))
                            for exev in exevts:
                                print("- - found event:"+str(exev.id)+" "+str(exev)+" tx:"+str(exev.transfer.id)+" fairtx:"+str(exev.faircoin_transaction))
                                loger.info("- - found event:"+str(exev.id)+" "+str(exev)+" tx:"+str(exev.transfer.id)+" fairtx:"+str(exev.faircoin_transaction))
                                if exev.faircoin_transaction and not exev.transfer == tx:
                                    print("- - CHANGED exev.transfer? "+str(exev.transfer)+" -> "+str(exev.transfer.transfer_type.name)+" tt:"+str(exev.transfer.transfer_type.id))
                                    loger.info("- - CHANGED exev.transfer? "+str(exev.transfer)+" -> "+str(exev.transfer.transfer_type.name)+" tt:"+str(exev.transfer.transfer_type.id))
                                    exev.transfer.transfer_type = paytt
                                    exev.transfer.name = paytt.name
                                    exev.transfer.save()
                                    if tx.is_deletable():
                                        print("- - DELETED tx:"+str(tx.id)+" "+str(tx))
                                        loger.info("- - DELETED tx:"+str(tx.id)+" "+str(tx))
                                        tx.delete()


            else:
                pass #print("Other tt: "+str(tt))

          if not txtp.found and et == ex.exchange_type:
            print("WARN: Missing transfer! "+str(txtp)+' pending:'+str(jr.pending_shares())+", Recreate exchange! et:"+str(et))
            loger.warning("WARN: Missing transfer! "+str(txtp)+' pending:'+str(jr.pending_shares())+", Recreate exchange!")
            messages.warning(request, "WARN: Missing transfer! "+str(txtp)+' pending:'+str(jr.pending_shares())+", Recreate exchange!")
            note = 'repaired '+str(datetime.date.today())+'. '
            ex = jr.create_exchange(note, ex)

    if exmem:
        if not jr.pending_shares():
            pass #print("Update payment status! exid:"+str(exmem.id))
            #jr.update_payment_status('complete')
        else:
            pass

    exs2 = Exchange.objects.filter(exchange_type=et, events__isnull=True)
    print()
    print("exs2: "+str(len(exs2)))
    for ex in exs2:
        kms = ex.xfer_commitments()
        evs = ex.xfer_events()
        if not kms:
            jr2 = None
            if hasattr(ex, 'join_request') and ex.join_request:
                jr2 = ex.join_request
            if not jr2 and not kms and not evs:
                print("- delete empty Exchange: id:"+str(ex.id)+" - "+str(ex)+" ca:"+str(ex.context_agent)) #+" JR:"+str(jr2)
                loger.info("- delete empty Exchange: id:"+str(ex.id)+" - "+str(ex)+" ca:"+str(ex.context_agent)) #+" JR:"+str(jr2))
                messages.info(request, "- delete empty Exchange: id:"+str(ex.id)+" - "+str(ex)+" ca:"+str(ex.context_agent)) #+" JR:"+str(jr2))
                for tr in ex.transfers.all():
                    print("-- delete empty Transfer: id:"+str(tr.id)+" - "+str(tr)+" ca:"+str(tr.context_agent)+" coms:"+str(len(tr.commitments.all()))+" evts:"+str(len(tr.events.all()))+" notes:"+str(tr.notes))
                    loger.info("-- delete empty Transfer: id:"+str(tr.id)+" - "+str(tr)+" ca:"+str(tr.context_agent)+" coms:"+str(len(tr.commitments.all()))+" evts:"+str(len(tr.events.all()))+" notes:"+str(tr.notes))
                    messages.info(request, "-- delete empty Transfer: id:"+str(tr.id)+" - "+str(tr)+" ca:"+str(tr.context_agent)+" coms:"+str(len(tr.commitments.all()))+" evts:"+str(len(tr.events.all()))+" notes:"+str(tr.notes))
                    if tr.is_deletable():
                        tr.delete()
                if ex.is_deletable():
                    ex.delete()

    return



def run_fdc_scripts(request, agent):
    if not agent.name == "Freedom Coop":
        raise ValidationError("This is only intended for Freedom Coop agent migration")
    fdc = agent
    if not hasattr(fdc, 'project'): return
    user_agent = get_agent(request)

    print("............ start run_fdc_scripts ("+str(agent)+") .............")
    loger.info("............ start run_fdc_scripts ("+str(agent)+") .............")
    acctyp = fdc.project.shares_account_type()
    shrtyp = fdc.project.shares_type()
    oldshr = EconomicResourceType.objects.membership_share()

    if not shrtyp:
        messages.error(request, "The FdC project still has not a shares_type ?")
        return
    if not acctyp:
        messages.error(request, "The FdC project still has not a shares_account_type ?")
        #raise ValidationError("The FdC project still has not a shares_account_type ?")
        return
    if not acctyp.context_agent == fdc:
        print("Change context_agent of the shares account to fdc!! "+str(acctyp))
        loger.info("Change context_agent of the shares account to fdc!! "+str(acctyp))
        acctyp.context_agent = fdc
        acctyp.save()
    if not shrtyp.context_agent == fdc:
        print("Change context_agent of the shares type to fdc!! "+str(shrtyp))
        loger.info("Change context_agent of the shares type to fdc!! "+str(shrtyp))
        shrtyp.context_agent = fdc
        shrtyp.save()

    # fix fdc memberships associations
    agids = MembershipRequest.objects.filter(agent__isnull=False).values_list('agent')
    ags = EconomicAgent.objects.filter(pk__in=agids)
    partis = fdc.participants()
    candis = fdc.candidates()
    aamem = AgentAssociationType.objects.get(identifier="member")
    aapar = AgentAssociationType.objects.get(identifier="participant")
    for ag in ags:
        agshacs = ag.agent_resource_roles.filter(
            role__is_owner=True,
            resource__resource_type=acctyp)
        if len(agshacs) == 1:
            agshac = agshacs[0]
            if not agshac.resource.identifier == fdc.nick+" shares account for "+ag.name:
                #print("- Edit resource name: "+str(agshac.resource))
                loger.info("- Edit resource name: "+str(agshac.resource))
                agshac.resource.identifier = fdc.nick+" shares account for "+ag.name
                agshac.resource.save()
                agshac.save()
                messages.info(request, "- Edited resource identifier: "+str(agshac.resource))
        elif agshacs:
            #print("More than one agent_resource_role related the shares account? "+str(agshacs))
            loger.error("More than one agent_resource_role related the shares account? "+str(agshacs))
            messages.error(request, "More than one agent_resource_role related the shares account? "+str(agshacs))

        if not ag in partis and not ag in candis:
            reqs = ag.membership_requests.all()
            if len(reqs) > 1:
                loger.warning("ERROR-SKIP: There are more than one FdC membership requests for agent "+str(ag)+"'. Solve duplicates? "+str(reqs))
                messages.error(request, "There are more than one FdC membership requests for agent "+str(ag)+"'. Solve duplicates? "+str(reqs))
                continue
            relags = list(rel.has_associate for rel in ag.is_associate_of.all())
            if fdc.parent() in relags:
                rels = ag.is_associate_of.filter(has_associate=fdc.parent())
                rel = None
                if len(rels) > 1:
                    #raise ValidationError("Found more than one association with FdC parent !? "+str(rels))
                    for re in rels:
                        if re.association_type == aamem:
                            rel = re
                        else:
                            print("NOTE agent "+str(ag)+" has another association type with FdC parent: "+str(re)+" state:"+str(re.state))
                            loger.info("NOTE agent "+str(ag)+" has another association type with FdC parent: "+str(re)+" state:"+str(re.state))
                elif rels:
                    rel = rels[0]
                if rel:
                    print("FOUND fdc parent ("+str(fdc.parent())+") in related agents, REPAIR rel:"+str(rel)+" state:"+str(rel.state))
                    loger.info("FOUND fdc parent ("+str(fdc.parent())+") in related agents, REPAIR rel:"+str(rel)+" state:"+str(rel.state))
                    ress = list(arr.resource.resource_type for arr in ag.agent_resource_roles.all())
                    if acctyp in ress or oldshr in ress:
                        if rel.state == "active":
                            agas, created = AgentAssociation.objects.get_or_create(
                                is_associate=ag,
                                has_associate=fdc,
                                association_type=aamem,
                                state=rel.state
                            )
                            if created:
                                print("- created new active AgentAssociation: "+str(agas))
                                loger.info("- created new active AgentAssociation: "+str(agas))
                                messages.info(request, "- created new active AgentAssociation: "+str(agas))
                            else:
                                if rel.association_type == aamem and rel.has_associate == fdc.parent():
                                    rel.association_type = aapar
                                    rel.save()
                                    #print("- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                                    loger.info("- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                                    messages.info(request, "- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                                else:
                                    pass #print("- DON'T REPAIR? rel:"+str(rel)+" state:"+str(rel.state))
                                    #loger.info("- DON'T REPAIR? rel:"+str(rel)+" state:"+str(rel.state))
                        else:
                            print("- Found FdC shares but relation with FdC parent is not 'active': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                            loger.info("- Found FdC shares but relation with FdC parent is not 'active': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                            messages.error(request, "- Found FdC shares but relation with FdC parent is not 'active': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                    else: # missing shares
                        if rel.state == 'candidate' or rel.state == 'potential':
                            agas, created = AgentAssociation.objects.get_or_create(
                                is_associate=ag,
                                has_associate=fdc,
                                association_type=aamem,
                                state=rel.state
                            )
                            if created:
                                print("- created new candidate AgentAssociation: "+str(agas))
                                loger.info("- created new candidate AgentAssociation: "+str(agas))
                                messages.info(request, "- created new candidate AgentAssociation: "+str(agas))
                            if rel.association_type == aamem and agas:
                                print("- deleted relation: "+str(rel))
                                loger.warning("- deleted relation: "+str(rel))
                                messages.warning(request, "- deleted relation: "+str(rel))
                                rel.delete() #association_type = aapar
                                #rel.save()
                        elif rel.state == 'active':
                            if rel.association_type == aamem:
                                rel.association_type = aapar
                                rel.save()
                                print("- REPAIRED agent active association with FdC parent to 'participant' (was 'member'): "+str(rel))
                                loger.info("- REPAIRED agent active association with FdC parent to 'participant' (was 'member'): "+str(rel))
                                messages.info(request, "- REPAIRED agent active association with FdC parent to 'participant' (was 'member'): "+str(rel))
                            if not fdc in relags:
                                agas, created = AgentAssociation.objects.get_or_create(
                                    is_associate=ag,
                                    has_associate=fdc,
                                    association_type=aamem,
                                    state='potential'
                                )
                                if created:
                                    print("- created new candidate AgentAssociation (no shares): "+str(agas))
                                    loger.info("- created new candidate AgentAssociation (no shares): "+str(agas))
                                    messages.info(request, "- created new candidate AgentAssociation (no shares): "+str(agas))
                        else:
                            print("- Missing FdC shares but relation with FdC parent is not 'candidate': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                            loger.info("- Missing FdC shares but relation with FdC parent is not 'candidate': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                            messages.error(request, "Missing FdC shares but relation with FdC parent is not 'candidate': SKIP repair! "+str(rel)+" state:"+str(rel.state))
                else: # missing rel
                    print("ERROR Not found a relation with FdC parent for agent: "+str(ag))
                    loger.info("ERROR Not found a relation with FdC parent for agent: "+str(ag))
            elif fdc in relags:
                rels = ag.is_associate_of.filter(has_associate=fdc)
                rel = None
                if len(rels) > 1:
                    #raise ValidationError("More than one relation with FdC ?? "+str(rels))
                    for re in rels:
                        if re.association_type == aamem:
                            rel = re
                        else:
                            print("NOTE agent "+str(ag)+" has another association type with FdC: "+str(re)+" state:"+str(re.state))
                            loger.info("NOTE agent "+str(ag)+" has another association type with FdC: "+str(re)+" state:"+str(re.state))
                elif rels:
                    rel = rels[0]
                if rel:
                    if rel.association_type.name == 'Participant':
                        rel.association_type = aamem
                        rel.save()
                        print("- REPAIRED agent association with FdC to 'member' (was participant): "+str(rel)+" state:"+str(rel.state))
                        loger.info("- REPAIRED agent association with FdC to 'member' (was participant): "+str(rel)+" state:"+str(rel.state))
                        messages.info(request, "- REPAIRED agent association with FdC to 'member' (was participant): "+str(rel)+" state:"+str(rel.state))
                    elif not rel.association_type == aamem:
                        print("WARNING! Another type of association with FdC is found! "+str(rel)+" state:"+str(rel.state))
                        loger.info("WARNING! Another type of association with FdC is found! "+str(rel)+" state:"+str(rel.state))
                else:
                    raise ValidationError("IMPOSSIBLE! FdC is related this agent? "+str(ag))
            else: # No relation with FdC or its parent
                print("- Not found agent "+str(ag)+" in participants or candidates of FdC (but has membership request: "+str(ag.membership_requests.all().values_list('name', 'state'))+"), found: "+str(ag.is_associate_of.all()))
                ress = list(rel.resource.resource_type for rel in ag.agent_resource_roles.all())
                if not acctyp in ress and not oldshr in ress:
                    #print("- Not found "+str(acctyp)+" nor any old "+str(oldshr)+" in the agent resources" #: "+str(ress))
                    reqs = ag.membership_requests.all()
                    if len(reqs) > 1:
                        raise ValidationError("There are more than one FdC membership requests for agent "+str(ag))
                    for req in reqs:
                        if req.state == 'accepted': # Error: accepted without shares
                            print("Found accepted membership request but the agent '"+str(ag)+"' is not member of FdC (or its parent) and has not any FdC shares, SKIP repair! Relations: "+str(relags)+" - Resources: "+str(ress))
                            messages.error(request,
                                "Found accepted <a href='"+str(reverse('membership_discussion',
                                args=(req.id,)))+"'>membership request</a> but the agent <b>"+str(ag)
                                +"</b> is not member of FdC (or its parent) and has no FdC shares. CREATE candidate relation and REPAIR request state to 'new'! ",
                                extra_tags='safe') # Relations: "+str(relags)+" - Resources: "+str(ress))
                            agas, created = AgentAssociation.objects.get_or_create(
                                is_associate=ag,
                                has_associate=fdc,
                                association_type=aamem,
                                state='potential'
                            )
                            if created:
                                #print("- Created new association as FdC candidate (no shares found): "+str(agas))
                                loger.info("- Created new association as FdC candidate (no shares found): "+str(agas.is_associate.nick))
                                messages.info(request, "- Created new association as FdC candidate (no shares found): "+str(agas.is_associate.nick))
                            req.state = 'new'
                            req.save()
                        elif req.state == 'declined':
                            print("Found declined membership request, don't do nothing? "+str(req))
                            loger.info("Found declined membership request, don't do nothing? "+str(req))
                        elif req.state == 'new':
                            print("FOUND new membership request for agent: "+str(ag)+" with no shares, repair association!")
                            loger.info("FOUND new membership request for agent: "+str(ag)+" with no shares, repair association!")
                            agas, created = AgentAssociation.objects.get_or_create(
                                is_associate=ag,
                                has_associate=fdc,
                                association_type=aamem,
                                state='potential'
                            )
                            if created:
                                print("- Created new association as FdC candidate: "+str(agas))
                                loger.info("- Created new association as FdC candidate: "+str(agas))
                                messages.info(request, "- Created new association as FdC candidate: "+str(agas))
                else:
                    if user_agent == agent or user_agent in agent.managers or request.user.is_staff:
                        print("- Found FdC shares of agent "+str(ag)+" (with a membership request) but not found any relation with FdC or its parent: SKIP repair")
                        loger.info("- Found FdC shares of agent "+str(ag)+" (with a membership request) but not found any relation with FdC or its parent: SKIP repair")
                        messages.warning(request, "- Found FdC shares of agent "+str(ag)+" (with a membership request) but not found any relation with FdC or its parent: SKIP repair")


        else: # is found in candidates or participants

            reqs = ag.membership_requests.all()
            if len(reqs) > 1:
                loger.warning("ERROR-SKIP: There are more than one FdC membership requests for agent "+str(ag)+"'. Solve duplicates? "+str(reqs))
                messages.error(request, "There are more than one FdC membership requests for agent "+str(ag)+"'. Solve duplicates? "+str(reqs))
                continue
            relags = list(rel.has_associate for rel in ag.is_associate_of.all())
            if fdc.parent() in relags:
                rels = ag.is_associate_of.filter(has_associate=fdc.parent())
                rel = None
                if len(rels) > 1:
                    #raise ValidationError("Found more than one association with FdC parent !? "+str(rels))
                    for re in rels:
                        if re.association_type == aamem:
                            rel = re
                        else:
                            pass #print("NOTE agent "+str(ag)+" has another association type with FdC parent: "+str(re)+" state:"+str(re.state))
                            #loger.info("NOTE agent "+str(ag)+" has another association type with FdC parent: "+str(re)+" state:"+str(re.state))
                elif rels:
                    rel = rels[0]
                if rel:
                    #print("FOUND fdc parent ("+str(fdc.parent())+") in related agents, REPAIR rel:"+str(rel)+" state:"+str(rel.state))
                    #loger.info("FOUND fdc parent ("+str(fdc.parent())+") in related agents, REPAIR rel:"+str(rel)+" state:"+str(rel.state))
                    if rel.association_type == aamem: #and rel.has_associate == fdc.parent():
                        rel.association_type = AgentAssociationType.objects.get(identifier="participant")
                        rel.save()
                        print("- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                        loger.info("- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                        messages.info(request, "- REPAIRED agent association with FdC parent to 'participant' (was 'member'): "+str(rel)+" state:"+str(rel.state))
                    else:
                        pass #print("- DON'T REPAIR? rel:"+str(rel)+" state:"+str(rel.state))
                        #loger.info("- DON'T REPAIR? rel:"+str(rel)+" state:"+str(rel.state))



    pcandis = fdc.parent().has_associates.all()
    for ag in pcandis:
        if not ag.is_associate in ags:
            if ag.association_type == aamem or not ag.state == 'active':
                ag.association_type = aamem
                ag.has_associate = fdc
                ag.save()
                print("- Repaired candidate of fdc-parent was not related fdc: "+str(ag)+" state:"+str(ag.state))
                loger.info("- Repaired candidate of fdc-parent was not related fdc: "+str(ag)+" state:"+str(ag.state))
                messages.info(request, "- Repaired candidate of fdc-parent was not related fdc: "+str(ag)+" state:"+str(ag.state))
        else:
            if ag.state == 'potential' or ag.state == 'candidate':
                if ag.is_associate in candis:
                    print("- deleted relation! "+str(ag)+" state:"+str(ag.state))
                    loger.info("- deleted relation! "+str(ag)+" state:"+str(ag.state))
                    messages.warning(request, "- deleted relation! "+str(ag)+" state:"+str(ag.state))
                    ag.delete()
                else:
                    print("--- delete relation? "+str(ag)+" state:"+str(ag.state))
            else:
                pass #print("-- delete relation? "+str(ag)+" state:"+str(ag.state))

    tot_mem = MembershipRequest.objects.all()
    tot_jrq = JoinRequest.objects.filter(project=fdc.project)
    pend = len(tot_mem) - len(tot_jrq)
    if pend and request.user.agent.agent in fdc.managers():
        messages.error(request, "Membership Requests pending to MIGRATE to the new generic JoinRequest system: <b>"+str(pend)+"</b>", extra_tags='safe')

    print("............ end run_fdc_scripts ("+str(agent)+") .............")
    loger.info("............ end run_fdc_scripts ("+str(agent)+") .............")




#    P R O J E C T S

@login_required
def your_projects(request):
    agent = get_agent(request)
    agent_form = WorkAgentCreateForm()
    proj_form = ProjectCreateForm() #initial={'agent_type': 'Project'})
    projects = agent.related_contexts()
    managed_projects = agent.managed_projects()
    join_projects = Project.objects.all() #filter(joining_style="moderated", visibility!="private")

    next = "/work/your-projects/"
    allowed = False
    if agent:
        if agent.is_active_freedom_coop_member() or request.user.is_staff or agent.is_participant() or managed_projects:
            allowed = True
    if not allowed:
        return render(request, 'work/no_permission.html')

    for node in projects:
        aats = []
        for aat in node.agent_association_types():
          #if aat.association_behavior != "child":
          aat.assoc_count = node.associate_count_of_type(aat.identifier)
          assoc_list = node.all_has_associates_by_type(aat.identifier)
          for assoc in assoc_list:
            association = AgentAssociation.objects.filter(is_associate=assoc, has_associate=node, association_type=aat)[0]#
            assoc.state = association.state
          aat.assoc_list = assoc_list
          if not aat in aats:
            aats.append(aat)
        node.aats = aats

    '''roots = [p for p in projects if not p.is_root()] # if p.is_root()

    for root in roots:
        root.nodes = root.child_tree()
        annotate_tree_properties(root.nodes)
        for node in root.nodes:
            aats = []
            for aat in node.agent_association_types():
                #if aat.association_behavior != "child":
                    aat.assoc_count = node.associate_count_of_type(aat.identifier)
                    assoc_list = node.all_has_associates_by_type(aat.identifier)
                    for assoc in assoc_list:
                        association = AgentAssociation.objects.get(is_associate=assoc, has_associate=node, association_type=aat)#
                        assoc.state = association.state
                    aat.assoc_list = assoc_list
                    if not aat in aats:
                      aats.append(aat)
            node.aats = aats'''

    return render(request, "work/your_projects.html", {
        "projects": projects,
        "help": get_help("your_projects"),
        "agent": agent,
        "agent_form": agent_form,
        "proj_form": proj_form,
        "managed_projects": managed_projects,
        "join_projects": join_projects,
    })


@login_required
def create_your_project(request):
    user_agent = get_agent(request)
    if not user_agent or not user_agent.is_active_freedom_coop_member:
        return render(request, 'work/no_permission.html')
    if request.method == "POST":
        agn_form = WorkAgentCreateForm(agent=None, data=request.POST)
        if agn_form.is_valid():
            agent = agn_form.save(commit=False)
            agent.created_by=request.user
            agent.is_context=True
            #agent.save()
            pro_form = ProjectCreateForm(agent=agent, data=request.POST)
            if pro_form.is_valid():
                agent.save()
                project = pro_form.save(commit=False)
                project.agent = agent
                project.save()

            association_type = AgentAssociationType.objects.get(identifier="manager")
            fc_aa = AgentAssociation(
                is_associate=user_agent,
                has_associate=agent,
                association_type=association_type,
                state="active",
                )
            fc_aa.save()

            fc = EconomicAgent.objects.freedom_coop_projects()
            association_type = AgentAssociationType.objects.get(identifier="child")
            fc_aa = AgentAssociation(
                is_associate=agent,
                has_associate=fc,
                association_type=association_type,
                state="active",
                )
            fc_aa.save()

            return HttpResponseRedirect('/%s/%s/'
                % ('work/agent', agent.id))
    return HttpResponseRedirect("/work/your-projects/")




#    A G E N T   P A G E

@login_required
def members_agent(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent or not user_agent.is_participant: # or not agent in user_agent.related_all_agents(): # or not user_agent.is_active_freedom_coop_member:
        return render(request, 'work/no_permission.html')

    print("--------- start members_agent ("+str(agent)+") ----------")
    loger.info("--------- start members_agent ("+str(agent)+") ----------")
    if agent.nick == "Freedom Coop": run_fdc_scripts(request, agent)

    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True

    if user_agent.project_join_requests:
      for req in user_agent.project_join_requests.all():
        if req.project.agent == agent:
          user_agent.req = req
          break

    user_agent.assos = user_agent.is_associate_of.filter(has_associate=agent)
    if user_agent.assos:
        if len(user_agent.assos) > 1:
            print("- WARN: agent with multiple Relations with the context! "+str(user_agent.assos))
            loger.warning("- WARN: agent with multiple Relations with the context! "+str(user_agent.assos))

    try:
        project = agent.project
    except:
        project = False

    if project:# and not request.POST:
        #init = {"joining_style": project.joining_style, "visibility": project.visibility, "resource_type_selection": project.resource_type_selection, "fobi_slug": project.fobi_slug }
        pro_form = ProjectCreateForm(instance=project, agent=agent, data=request.POST or None) #, initial=init)
    elif agent.is_individual():
        pro_form = None
    else:
        pro_form = ProjectCreateForm(agent=agent, data=request.POST or None) #AgentCreateForm(instance=agent)

    agn_form = WorkAgentCreateForm(instance=agent, agent=agent, data=request.POST or None)

    if user_is_agent or user_agent in agent.managers() or request.user.is_superuser:
      if request.method == "POST":
        oldnick = agent.nick
        nick = agent.nick
        name = agent.name
        oldemail = agent.email
        usr = agent.my_user()
        #usremail = usr.email if usr else None

        if agent.is_individual():
            #agn_form = WorkAgentCreateForm(instance=agent, data=request.POST)
            if agn_form.is_valid():
                agent = agn_form.save(commit=False)
                data = agn_form.cleaned_data
                nick = data['nick']
                name = data['name']
                agent.is_context = False #True
                #agent.save()
            else:
                pass #nick = agent.nick
                #name = agent.name
        else:
            if not project:
              pass #pro_form = ProjectCreateForm(request.POST)
              #if pro_form.is_valid():
              #  project = pro_form.save(commit=False)
              #  project.agent = agent
              #  project.save()
            else:
              pass #pro_form = ProjectCreateForm(instance=project, data=request.POST)

            #agn_form = WorkAgentCreateForm(instance=agent, data=request.POST)
            if agn_form.is_valid() and pro_form.is_valid():
                project = pro_form.save(commit=False)
                prodata = pro_form.cleaned_data
                agent = agn_form.save(commit=False)
                project.agent = agent
                if not prodata["auto_create_pass"]:
                    project.auto_create_pass = False
                project.save()
                data = agn_form.cleaned_data
                nick = data['nick']
                name = data['name']
                agent.is_context = True
                #print("- pro data: "+str(prodata))
                #print("- form nick "+str(nick))
                #print("- form name "+str(name))
                #url = data["url"]
                #if url and not url[0:3] == "http":
                #    pass #data["url"] = "http://" + url
                #agent.url = data["url"]
            else:
                pass # errors
        if not nick == oldnick: # if changed the nick, check user and rename resources
            othe = User.objects.filter(username=nick)
            usr = agent.my_user()
            if usr:
                if othe:
                    messages.error(request, "There's another User with that username.")
                    nick = oldnick
                else:
                    usr.username = nick
                    usr.save()

            rss = EconomicResource.objects.filter(identifier__icontains=oldnick+' ')
            if rss:
                for rs in rss:
                    arr = rs.identifier.split(oldnick+' ')
                    if len(arr) == 2:
                        ownrs = arr[1].split(' '+oldnick)
                        if len(ownrs) > 1:
                            rs.identifier = nick+' '+ownrs[0]+' '+nick
                        else:
                            rs.identifier = nick+' '+arr[1]
                        rs.save()
                    else:
                        print("- ERROR, resource with strange name? "+str(rs))
                        loger.warning("- ERROR, resource with strange name? "+str(rs))

            rss = EconomicResource.objects.filter(identifier__icontains=' '+oldnick)
            if rss:
                for rs in rss:
                    arr = rs.identifier.split(' '+oldnick)
                    if len(arr) == 2:
                        #print("-1 rs.identifier: "+rs.identifier)
                        rs.identifier = arr[0]+' '+nick
                        #print("-2 rs.identifier: "+rs.identifier)
                        rs.save()
                    else:
                        print("- ERROR, resource with strange name? "+str(rs))
                        loger.warning("- ERROR, resource with strange name? "+str(rs))
        agent.name = name
        agent.nick = nick
        if not oldemail == agent.email and usr:
            if not usr.email == agent.email:
                loger.info("- Changed also the agent's User email to "+str(agent.email))
                usr.email = agent.email
                usr.save()

        # ensure the english string is set
        agent = set_lang_defaults(agent)

        agent.save()
        #print("- saved agent "+str(agent))
      else:
        pass # not POST
    else:
        pass # not permission

    """ not used yet...
    nav_form = InternalExchangeNavForm(data=request.POST or None)
    if agent:
        if request.method == "POST":
            if nav_form.is_valid():
                data = nav_form.cleaned_data
                ext = data["exchange_type"]
            return HttpResponseRedirect('/%s/%s/%s/%s/'
                % ('work/exchange', ext.id, 0, agent.id))
    """

    context_ids = [c.id for c in agent.related_all_agents()]
    if not agent.id in context_ids:
        context_ids.append(agent.id)
    user_form = None

    if not agent.username():
        init = {"username": agent.nick,}
        user_form = UserCreationForm(initial=init)

    assn_form = AssociationForm(agent=agent)

    is_associated_with = agent.all_is_associates().order_by('association_type__name', 'state', Lower('is_associate__name'))

    has_associations = None #agent.all_has_associates().order_by('association_type__name', 'state', Lower('is_associate__name'))


    headings = []
    member_hours_recent = []
    member_hours_stats = []
    individual_stats = []
    member_hours_roles = []
    roles_height = 400

    membership_request = agent.membership_request()
    entries = []
    fobi_name = 'None'

    et_work = EventType.objects.get(name="Time Contribution")

    if agent.is_individual():

        has_associations = agent.has_associates.all().order_by('association_type__name', 'state', Lower('is_associate__name'))

        contributions = agent.given_events.filter(is_contribution=True)
        agents_stats = {}
        for ce in contributions:
            agents_stats.setdefault(ce.resource_type, Decimal("0"))
            agents_stats[ce.resource_type] += ce.quantity
        for key, value in list(agents_stats.items()):
            individual_stats.append((key, value))
        individual_stats.sort(key=lambda x: x[1], reverse=True)

        skills = EconomicResourceType.objects.filter(behavior="work")
        arts = agent.resource_types.filter(event_type=et_work)
        agent.skills = []
        agent.suggested_skills = []
        if agent.user():
            user = agent.user().user
            suggestions = user.skill_suggestion.all()
            agent.suggested_skills = [sug.resource_type for sug in suggestions]
        for art in arts:
            agent.skills.append(art.resource_type)
        for skil in agent.skills:
            skil.checked = True
            if skil in agent.suggested_skills:
                skil.thanks = True
        for skill in skills:
            skill.checked = False
            if skill in agent.skills:
                skill.checked = True
            if skill in agent.suggested_skills:
                skill.thanks = True

    elif agent.is_context_agent():

        #has_associations = agent.has_associates.all()

        try:
          fobi_name = get_object_or_404(FormEntry, slug=agent.project.fobi_slug)
          entries = agent.project.join_requests.filter(agent__isnull=True, state='new').order_by('request_date')
        except:
          entries = []

        """
        subs = agent.with_all_sub_agents()
        end = datetime.date.today()
        #end = end - datetime.timedelta(days=77)
        start =  end - datetime.timedelta(days=60)
        events = EconomicEvent.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs,
            event_date__range=(start, end))

        if events:
            agents_stats = {}
            for event in events:
                agents_stats.setdefault(event.from_agent.name, Decimal("0"))
                agents_stats[event.from_agent.name] += event.quantity
            for key, value in list(agents_stats.items()):
                member_hours_recent.append((key, value))
            member_hours_recent.sort(key=lambda x: x[1], reverse=True)


        ces = CachedEventSummary.objects.filter(
            event_type__relationship="work",
            context_agent__in=subs)

        if ces.count():
            agents_stats = {}
            for ce in ces:
                agents_stats.setdefault(ce.agent.name, Decimal("0"))
                agents_stats[ce.agent.name] += ce.quantity
            for key, value in list(agents_stats.items()):
                member_hours_stats.append((key, value))
            member_hours_stats.sort(key=lambda x: x[1], reverse=True)

            agents_roles = {}
            roles = [ce.quantity_label() for ce in ces]
            roles = list(set(roles))
            for ce in ces:
                if ce.quantity:
                    name = ce.agent.name
                    row = [name, ]
                    for i in range(0, len(roles)):
                        row.append(Decimal("0.0"))
                        key = ce.agent.name
                    agents_roles.setdefault(key, row)
                    idx = roles.index(ce.quantity_label()) + 1
                    agents_roles[key][idx] += ce.quantity
            headings = ["Member",]
            headings.extend(roles)
            for row in list(agents_roles.values()):
                member_hours_roles.append(row)
            member_hours_roles.sort(key=lambda x: x[0])
            roles_height = len(member_hours_roles) * 20
        """

    #artwork = get_object_or_404(Artwork_Type, clas="Material")
    add_skill_form = AddUserSkillForm(agent=agent, data=request.POST or None)
    Stype_form = NewSkillTypeForm(agent=agent, data=request.POST or None)
    Stype_tree = Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ).order_by('tree_id','lft')

    upload_form = UploadAgentForm(instance=agent)

    auto_resource = create_user_accounts(request, agent)

    related_rts = []
    if agent.project_join_requests:
        for req in agent.project_join_requests.all():
            if req.subscription_unit():
                req.check_subscription_expiration()

            if req.project.agent in user_agent.managed_projects() or user_agent is req.project.agent:
                rtsc = req.project.rts_with_clas()
                rts = list(set([arr.resource.resource_type for arr in agent.resource_relationships()]))
                for rt in rtsc:
                    if rt in rts:
                        related_rts.append(rt)

    dups = check_duplicate_agents(request, agent)

    fixes = check_empty_langs(request, agent)
    if fixes:
        print("Fixed "+str(fixes)+" emapty strings for agent: "+agent.name)

    asso_childs = agent.has_associates.filter(association_type__association_behavior__in=['child','peer'], state="active").count() #.order_by(Lower('is_associate__name'))
    asso_chil = agent.has_associates.filter(association_type__association_behavior__in=['child','peer'], state="active").first()
    if user_is_agent or user_agent in agent.managers():
        asso_declin = agent.has_associates.filter(state="inactive").count() #.order_by(Lower('is_associate__name'))
        asso_decl = agent.has_associates.filter(state="inactive").first()
        asso_candid = agent.has_associates.filter(state="potential").count() #.order_by(Lower('is_associate__name'))
        asso_cand = agent.has_associates.filter(state="potential").first()
    else:
        asso_declin = 0
        asso_decl = None
        asso_candid = 0
        asso_cand = None
    asso_coords = agent.has_associates.filter(association_type__association_behavior__in=['manager','custodian'], state="active").count() #.order_by(Lower('is_associate__name'))
    asso_coor = agent.has_associates.filter(association_type__association_behavior__in=['manager','custodian'], state="active").first()
    asso_members = agent.has_associates.filter(association_type__association_behavior='member', state="active").count() #.order_by(Lower('is_associate__name'))
    asso_memb = agent.has_associates.filter(association_type__association_behavior='member', state="active").first()

    asso_states = ['active','inactive','potential']
    asso_behaviors = [i[0] for i in ASSOCIATION_BEHAVIOR_CHOICES]

    if hasattr(agent, 'project') and agent.project.is_moderated():
        if not agent.email and user_agent in agent.managers():
            messages.error(request, _("Please provide an email for the project to use as a remitent for the moderated joining process notifications!"))
        proshacct = agent.project.shares_account_type()
        for ass in has_associations:
            ag = ass.is_associate
            ag.jn_reqs = ag.project_join_requests.filter(project=agent.project)
            ag.oldshares = ag.owned_shares(agent)
            ag.newshares = 0
            acc = ag.owned_shares_accounts(proshacct)
            if acc:
                ag.newshares = int(acc[0].price_per_unit)


    assobj = {'childs':asso_childs,
              'chil':asso_chil,
              'declins':asso_declin,
              'decl':asso_decl,
              'candids':asso_candid,
              'cand':asso_cand,
              'coords':asso_coords,
              'coor':asso_coor,
              'members':asso_members,
              'memb':asso_memb,
              'behaviors':asso_behaviors,
              'states':asso_states}

    if not has_associations:
        has_associations = asso_childs + asso_members + asso_candid + asso_declin

    if hasattr(agent, 'project') and agent.project.is_moderated():
        if not agent.email and user_agent in agent.managers():
            messages.error(request, _("Please provide an email for the project to use as a remitent for the moderated joining process notifications!"))


    print("--------- end members_agent ("+str(agent)+") ----------")
    loger.info("--------- end members_agent ("+str(agent)+") ----------")

    return render(request, "work/members_agent.html", {
        "agent": agent,
        "membership_request": membership_request,
        "photo_size": (128, 128),
        "agn_form": agn_form,
        "pro_form": pro_form,
        "user_form": user_form,
        #"nav_form": nav_form,
        "assn_form": assn_form,
        "upload_form": upload_form,
        "user_agent": user_agent,
        "user_is_agent": user_is_agent,
        "has_associations": has_associations,
        "assobj": assobj,
        "is_associated_with": is_associated_with,
        "headings": headings,
        #"member_hours_recent": member_hours_recent,
        #"member_hours_stats": member_hours_stats,
        #"member_hours_roles": member_hours_roles,
        "individual_stats": individual_stats,
        "roles_height": roles_height,
        #"help": get_help("members_agent"),
        "form_entries": entries,
        "fobi_name": fobi_name,
        "add_skill_form": add_skill_form,
        "Stype_tree": Stype_tree,
        "Stype_form": Stype_form,
        "auto_resource": auto_resource,
        "related_rts": related_rts,
        "units": Unit.objects.filter(unit_type='value').exclude(name_en__icontains="share"),
    })


@login_required
def view_agents_list(request, agent_id):
    assocs = None
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent or not user_agent.is_participant: # or not agent in user_agent.related_all_agents(): # or not user_agent.is_active_freedom_coop_member:
        return render(request, 'work/no_permission.html')

    if request.POST:
        behavior = request.POST['behavior']
        state = request.POST['state']
        number = int(request.POST['number'])
        ready = int(request.POST['ready'])

        ofset = 10    # TUNE as wished

        maxim = ready+ofset
        if maxim > number:
            maxim = number

        if behavior == 'child':
            behaviors = [behavior, 'peer']
        elif behavior == 'manager':
            behaviors = [behavior, 'custodian']
        else:
            behaviors = [behavior]
        #print('ready: '+str(ready)+' maxim:'+str(maxim))
        assocs = agent.has_associates.filter(association_type__association_behavior__in=behaviors,
                                             state=state).order_by(Lower('is_associate__name'))[ready:maxim]

    if hasattr(agent, 'project') and agent.project.is_moderated():
        proshacct = agent.project.shares_account_type()
        for ass in assocs:
            ag = ass.is_associate
            ag.jn_reqs = ag.project_join_requests.filter(project=agent.project)
            if proshacct:
                ag.oldshares = ag.owned_shares(agent)
                ag.newshares = 0
                acc = ag.owned_shares_accounts(proshacct)
                if acc:
                    ag.newshares = int(acc[0].price_per_unit)

    return render(request, 'work/_agent_list.html', {
            'assocs': assocs,
            'agent': agent,
            'user_agent': user_agent,
            'no_shares': ['child', 'peer']
        })


def check_empty_langs(request, agent):
    fixed = 0
    if agent.photo_url == 'None':
        agent.photo_url = ''
        agent.save()
        print("Fixed 'None' as string in the photo_url (now is '') ! "+agent.name)
        loger.info("Fixed 'None' as string in the photo_url (now is '') ! "+agent.name)

    for lan, nom in settings.LANGUAGES:
        #print('lan: '+lan+'  name: '+getattr(agent, 'name_'+lan, 'EMPTY?'))
        imgurl = getattr(agent, 'photo_url_'+lan, None)
        if imgurl == 'None':
            setattr(agent, 'photo_url_'+lan, agent.photo_url)
            agent.save()
            print("Fixed 'None' as string in the photo_url (now is '"+agent.photo_url+"') ! "+agent.name)
            loger.info("Fixed 'None' as string in the photo_url (now is '"+agent.photo_url+"') ! "+agent.name)

        if not getattr(agent, 'name_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'name_'+ln, None)
                if nam and not getattr(agent, 'name_'+lan, None):
                    setattr(agent, 'name_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'name_"+lan+"' from 'name_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'name_"+lan+"' from 'name_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'nick_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'nick_'+ln, None)
                if nam and not getattr(agent, 'nick_'+lan, None):
                    setattr(agent, 'nick_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'nick_"+lan+"' from 'nick_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'nick_"+lan+"' from 'nick_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'email_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'email_'+ln, None)
                if nam and not getattr(agent, 'email_'+lan, None):
                    setattr(agent, 'email_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'email_"+lan+"' from 'email_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'email_"+lan+"' from 'email_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'url_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'url_'+ln, None)
                if nam and not getattr(agent, 'url_'+lan, None):
                    setattr(agent, 'url_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'url_"+lan+"' from 'url_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'url_"+lan+"' from 'url_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'photo_url_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'photo_url_'+ln, None)
                if nam and not getattr(agent, 'photo_url_'+lan, None):
                    setattr(agent, 'photo_url_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'photo_url_"+lan+"' from 'photo_url_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'photo_url_"+lan+"' from 'photo_url_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'phone_primary_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'phone_primary_'+ln, None)
                if nam and not getattr(agent, 'phone_primary_'+lan, None):
                    setattr(agent, 'phone_primary_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'phone_primary_"+lan+"' from 'phone_primary_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'phone_primary_"+lan+"' from 'phone_primary_"+ln+"' ! "+nam)
                    fixed += 1

        if not getattr(agent, 'address_'+lan, None):
            langs = settings.LANGUAGES[:]
            langs.remove((lan, nom))
            for ln, nm in langs:
                nam = getattr(agent, 'address_'+ln, None)
                if nam and not getattr(agent, 'address_'+lan, None):
                    setattr(agent, 'address_'+lan, nam)
                    agent.save()
                    loger.info("FIXED 'address_"+lan+"' from 'address_"+ln+"'! "+nam)
                    messages.warning(request, "FIXED 'address_"+lan+"' from 'address_"+ln+"' ! "+nam)
                    fixed += 1

    return fixed



@login_required
def edit_relations(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if user_agent in agent.managers() or request.user.is_superuser:
        assn_form = AssociationForm(agent=agent,data=request.POST)
        if assn_form.is_valid():
            member_assn = AgentAssociation.objects.get(id=int(request.POST.get("member")))
            if request.POST.get("new_association_type"):
                assn_type = AgentAssociationType.objects.get(id=int(request.POST.get("new_association_type")))
                member_assn.association_type = assn_type
                member_assn.save()
            elif member_assn and agent.project:
                # check there's no join request
                reqs = agent.project.join_requests.filter(agent=member_assn.subject) # .subject is the new VF property (is_associate)
                if reqs:
                    messages.error(request, _("Can't disable the relation because there's still a join-request for this agent."))
                    #raise ValidationError("Can't disable the relation because there's still a join-request: "+str(reqs))
                else:
                    member_assn.state = 'inactive'
                    member_assn.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))


@login_required
def assign_skills(request, agent_id):
    if request.method == "POST":
        agent = get_object_or_404(EconomicAgent, id=agent_id)
        user_agent = get_agent(request)
        if not user_agent:
            return render(request, 'work/no_permission.html')
        et_work = EventType.objects.get(name="Time Contribution")
        arts = agent.resource_types.filter(event_type=et_work)
        old_skill_rts = []
        for art in arts:
            old_skill_rts.append(art.resource_type)

        add_skill_form = AddUserSkillForm(agent=agent, data=request.POST)
        if add_skill_form.is_valid() and request.POST.get('skill_type'):
            skill_type = Ocp_Skill_Type.objects.get(id=int(request.POST.get('skill_type')))
            if not skill_type.resource_type:
                #pass # TODO create it?
                #out = None
                root = EconomicAgent.objects.root_ocp_agent()
                new_rt = EconomicResourceType(
                  name=skill_type.name,
                  description=skill_type.description,
                  #unit=out,
                  #price_per_unit=data["price_per_unit"],
                  substitutable=False, #data["substitutable"],
                  context_agent=root,
                  #url=data["url"],
                  #photo_url=data["photo_url"],
                  #parent=data["parent"],
                  created_by=request.user,
                  behavior="work",
                  inventory_rule="never",
                )
                new_rt.save()
                skill_type.resource_type = new_rt
                skill_type.save()

            if skill_type.resource_type in old_skill_rts:
                pass # TODO already assigned warn or hide from choices
            else:
                art = AgentResourceType(
                    agent=agent,
                    resource_type=skill_type.resource_type,
                    event_type=et_work,
                    created_by=request.user,
                )
                art.save()

        new_skills_list = request.POST.getlist('skillChoice')
        if new_skills_list:
            new_skill_rts = []
            for rt_id in new_skills_list:
                skill = EconomicResourceType.objects.get(id=int(rt_id))
                new_skill_rts.append(skill)

            #import pdb; pdb.set_trace()
            for skill in old_skill_rts:
                if skill not in new_skill_rts:
                    arts = AgentResourceType.objects.filter(agent=agent).filter(resource_type=skill)
                    if arts:
                        art = arts[0]
                        art.delete()
            """for skill in new_skill_rts:
                if skill not in old_skill_rts:
                    art = AgentResourceType(
                        agent=agent,
                        resource_type=skill,
                        event_type=et_work,
                        created_by=request.user,
                    )
                    #art.save()"""

    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))



@login_required
def change_your_project(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'work/no_permission.html')
    elif user_agent == agent or user_agent in agent.managers():
        if request.method == "POST":
          oldnick = agent.nick
          if agent.is_individual():
            agn_form = WorkAgentCreateForm(instance=agent, data=request.POST)
            if agn_form.is_valid():
                agent = agn_form.save(commit=False)
                data = agn_form.cleaned_data
                nick = data['nick']
                name = data['name']
                agent.is_context = False #True
                #agent.save()
          else:
            try:
              project = agent.project
            except:
              project = False
            if not project:
              pro_form = ProjectCreateForm(agent=agent, data=request.POST)
              if pro_form.is_valid():
                project = pro_form.save(commit=False)
                project.agent = agent
                project.save()
            else:
              pro_form = ProjectCreateForm(instance=project, agent=agent, data=request.POST)

            agn_form = WorkAgentCreateForm(instance=agent, data=request.POST)
            if agn_form.is_valid() and pro_form.is_valid():
                project = pro_form.save(commit=False)
                agent = agn_form.save(commit=False)
                project.agent = agent
                project.save()
                data = agn_form.cleaned_data
                nick = data['nick']
                name = data['name']
                agent.is_context = True
                #print("- form nick "+str(nick))
                #print("- form name "+str(name))
                #url = data["url"]
                #if url and not url[0:3] == "http":
                #    pass #data["url"] = "http://" + url
                #agent.url = data["url"]
          if not nick == oldnick: # if changed the nick, rename resources
            rss = EconomicResource.objects.filter(identifier__icontains=agent.nick+' ')
            if rss:
                for rs in rss:
                    arr = rs.identifier.split(agent.nick+' ')
                    if len(arr) == 2:
                        ownrs = arr[1].split(' '+agent.nick)
                        if len(ownrs) > 1:
                            rs.identifier = nick+' '+ownrs[0]+' '+nick
                        else:
                            rs.identifier = nick+' '+arr[1]
                        rs.save()
                    else:
                        print("- ERROR, resource with strange name? "+str(rs))

            rss = EconomicResource.objects.filter(identifier__icontains=' '+agent.nick)
            if rss:
                for rs in rss:
                    arr = rs.identifier.split(' '+agent.nick)
                    if len(arr) == 2:
                        #print("-1 rs.identifier: "+rs.identifier)
                        rs.identifier = arr[0]+' '+nick
                        #print("-2 rs.identifier: "+rs.identifier)
                        rs.save()
                    else:
                        print("- ERROR, resource with strange name? "+str(rs))
          agent.name = name
          agent.nick = nick
          agent.save()
          #print("- saved agent "+str(agent))

    return HttpResponseRedirect('/%s/%s/'
        % ('work/agent', agent.id))


@login_required
def create_user_accounts(request, agent, project=None):
    loger.info("------ create_user_accounts (start) ------")
    auto_resource = ''
    user_agent = get_agent(request)
    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True
    for jnreq in agent.project_join_requests.all():
        if jnreq.check_user_pass():
            auto_resource += _("The Accounts needed for this agent (related {0}) as not been created because the user's email is not confirmed yet (has not changed his/her initial password)").format(jnreq.project.agent.nick)+''
    if not auto_resource == '':
        return auto_resource

    is_associated_with = agent.all_is_associates()
    #import pdb; pdb.set_trace()
    for ag in is_associated_with:
        if hasattr(ag.has_associate, 'project'):
          if project and not project.agent == ag.has_associate:
            #if request.user.is_superuser: auto_resource += _("Skip accounts creation for ")+str(ag.has_associate)+"<br>"
            continue
          if user_agent == ag.has_associate or user_agent in ag.has_associate.managers() or user_agent in agent.managers() or user_is_agent:
            rtsc = ag.has_associate.project.rts_with_clas()
            for rt in rtsc:
              if rt.context_agent == ag.has_associate:
                is_account = False
                ancs = rt.ocp_artwork_type.get_ancestors(True, True)
                for anc in ancs:
                    if anc.clas == 'accounts':
                        is_account = True
                if is_account:
                    rts = list(set([arr.resource.resource_type for arr in agent.resource_relationships()]))
                    if not rt in rts:
                        res = ag.has_associate.agent_resource_roles.filter(resource__resource_type=rt)[0].resource
                        if res.resource_type.name_en == "Faircoin Ocp Account":
                            #if request.user.is_superuser: auto_resource += _("Not cloning a Faircoin Ocp Account: ")+res.identifier+'<br>'
                            continue
                        resarr = res.identifier.split(ag.has_associate.nick_en)
                        if len(resarr) > 1: # and not ag.has_associate.nick == 'Freedom Coop':
                            res.id = None
                            res.pk = None
                            if not resarr[1]:
                                auto_resource += _("To participate in")+" <b>"+ag.has_associate.name+"</b> "
                                auto_resource += _("you need a")+" \"<b>"+rt.name+"</b>\"... "
                                auto_resource += _("BUT there's a problem with the naming of the project's account: ")+str(resarr)
                                break
                            res.identifier = ag.has_associate.nick_en+resarr[1]+agent.nick #.identifier.split(ag.has_associate.nick)
                            res.quantity = 1
                            res.price_per_unit = 0
                            res.save()
                            rol = AgentResourceRoleType.objects.filter(is_owner=True)[0]
                            arr = AgentResourceRole(
                                agent=agent,
                                resource=res,
                                role=rol,
                                owner_percentage=100
                            )
                            arr.save()
                            #import pdb; pdb.set_trace()
                            auto_resource += _("To participate in")+" <b>"+ag.has_associate.name+"</b> "
                            auto_resource += _("you need a")+" \"<b>"+rt.name+"</b>\"... "
                            auto_resource += _("It has been created for agent <b>{0}</b> automatically!").format(ag.is_associate.name)+"<br />"
                    else:
                        pass
                        """
                        ress = agent.resource_relationships() #list(set([arr.resource for arr in agent.resource_relationships()]))
                        res = ress.get(resource__resource_type=rt).resource
                        resarr = res.identifier.split(ag.has_associate.nick)
                        if len(resarr) < 2:
                            resarr = res.identifier.split(ag.has_associate.name)
                        if len(resarr) < 2:
                            resarr = res.identifier.split('BoC')
                            auto_resource += "..trying to repair BoC nick to BotC in resources identifiers...<br>"
                        if len(resarr) == 2:
                            if agent.nick in resarr[1]:
                                res.identifier = ag.has_associate.nick+resarr[1]
                            else:
                                res.identifier = ag.has_associate.nick+resarr[1]+agent.nick
                            res.quantity = 1
                            res.save()
                            #auto_resource += _("Updated the name of the account: ")+str(res)
                        elif len(resarr) == 3:
                            if agent.nick in resarr[1]:
                                res.identifier = ag.has_associate.nick+resarr[1]
                            else:
                                res.identifier = ag.has_associate.nick+resarr[1]+agent.nick
                            res.quantity = 1
                            res.save()
                            auto_resource += _("Updated the name of the project's account: ")+str(res)
                        else:
                            auto_resource += _("There's a problem with the naming of the account: ")+str(res)+"<br>"
                            break
                        """
              elif rt.name_en == "Faircoin Ocp Account" and rt.context_agent.nick_en == "OCP":
                pass
              else:
                pass
                #print("- rt with another context_agent, SKIP! rt:"+str(rt)+" ca:"+str(rt.context_agent)+" ass:"+str(ag.has_associate)+" agent:"+str(agent))
                #loger.info("- rt with another context_agent, SKIP! rt:"+str(rt)+" ca:"+str(rt.context_agent)+" ass:"+str(ag.has_associate)+" agent:"+str(agent))
          else:
            pass # no permission
        else:
          pass # no project

    loger.info("------ create_user_accounts (end) ------")
    return auto_resource


def check_duplicate_agents(request, agent):
    loger.info("------ start check_duplicate_agents ("+str(agent)+") ------")
    repair_duplicate_agents(request, agent)
    ags = agent.all_has_associates()
    user_agent = request.user.agent.agent
    if user_agent in agent.managers() or user_agent == agent or request.user.is_staff:
      if ags:
        copis = None
        aamem = AgentAssociationType.objects.get(identifier="member")
        aapar = AgentAssociationType.objects.get(identifier="participant")
        try:
            aasel = AgentAssociationType.objects.get(identifier="selfemployed")
        except:
            aasel = AgentAssociationType.objects.get(identifier="Coop Worker")
            aasel.identifier = "selfemployed"
            aasel.save()
            loger.info("- CHANGED AgentAssociationType identifier 'Coop Worker' to 'selfemployed'!")


        for ag in ags:
            copis = EconomicAgent.objects.filter(name=ag.is_associate.name)
            if not copis:
                copis = EconomicAgent.objects.filter(name_en=ag.is_associate.name_en)
            if not copis:
                copis = EconomicAgent.objects.filter(name_en=ag.is_associate.name)
            if not copis:
                copis = EconomicAgent.objects.filter(name=ag.is_associate.name_en)
            if len(copis) > 1:
                cases = []
                usrs = ''
                for co in copis:
                    users = co.users.all()
                    if users and request.user.is_superuser:
                        if len(users) > 1 or not str(users[0].user) == str(co.nick):
                            usrs = ' (user'+('s!' if len(users)>1 else '')+': '+(', '.join([str(us.user) for us in users]))+')'
                        else:
                            usrs = ' (=user)'
                    else:
                        usrs = ''
                    cases.append('<b><a href="'+reverse('members_agent', args={co.id})+'">'+co.nick+'</a></b>'+str(usrs)+" ("+str(co.agent_type)+")")
                cases = ' and '.join(cases)
                messages.error(request, _("WARNING: The Name '<b>{0}</b>' is set for various agents: ").format(co.name)+cases, extra_tags='safe')

            '''if ag.is_associate.email and request.user.is_superuser:
                copis = EconomicAgent.objects.filter(email=ag.is_associate.email)
                if len(copis) > 1:
                    cases = []
                    usrs = ''
                    for co in copis:
                        users = co.users.all()
                        if users:
                            if len(users) > 1 or not str(users[0].user) == str(co.nick):
                                usrs = ' (user'+('s!' if len(users)>1 else '')+': '+(', '.join([str(us.user) for us in users]))+')'
                            else:
                                usrs = ' (=user)'
                        cases.append('<b><a href="'+reverse('members_agent', args={co.id})+'">'+co.nick+'</a></b>'+str(usrs))
                    cases = ' and '.join(cases)
                    messages.warning(request, _("WARNING: The Email '<b>{0}</b>' is set for various agents: ").format(co.email)+cases, extra_tags='safe')
            '''

            if hasattr(agent, 'project'):
                if agent.project.shares_type(): # if project has shares, participants should become members
                    if ag.association_type == aapar:
                        ag.association_type = aamem
                        ag.save()
                        loger.info(_("- Changed 'participant' for 'member' because the {0} project has shares, for agent {1} (status: {2})").format(agent, ag.is_associate, ag.state))
                        messages.info(request, _("- Changed 'participant' for 'member' because the {0} project has shares, for agent {1} (status: {2})").format(agent, ag.is_associate, ag.state))
                if ag.association_type == aasel:
                    if agent.project.shares_type():
                        ag.association_type = aamem
                        loger.info(_("- Changed 'selfemployed' for 'member' for agent {0} (status: {1})").format(ag.is_associate, ag.state))
                        messages.info(request, _("- Changed 'selfemployed' for 'member' for agent {0} (status: {1})").format(ag.is_associate, ag.state))
                    else:
                        ag.association_type = aapar
                        loger.info(_("- Changed 'selfemployed' for 'participant' for agent {0} (status: {1})").format(ag.is_associate, ag.state))
                        messages.info(request, _("- Changed 'selfemployed' for 'participant' for agent {0} (status: {1})").format(ag.is_associate, ag.state))
                    ag.save()

                aas = AgentAssociation.objects.filter(is_associate=ag.is_associate, has_associate=agent, association_type=ag.association_type )
                if len(aas) > 1:
                    #print(More than one AgentAssociation? "+str(aas))
                    for aa in aas:
                        if not aa == ag:
                            if not aa.state == 'active':
                                aa.delete()
                                print("- Deleted a duplicate relation! "+str(ag))
                                loger.info("- Deleted a duplicate relation! "+str(ag))
                                messages.info(request, "- Deleted a duplicate relation! "+str(ag))
                            else:
                                print("Error: The found duplicated AgentAssociation is active, not deleted! "+str(aa))
                                loger.warning("Error: The found duplicated AgentAssociation is active, not deleted! "+str(aa))

        loger.info("------ end check_duplicate_agents ("+str(agent)+") ------")
        if copis: #len(copis) > 1:
            return copis
    return None


def repair_duplicate_agents(request, agent):
    if request.user.is_superuser:
      copis = EconomicAgent.objects.filter(name=agent.name).order_by('id')
      if len(copis) > 1:
        cases = []
        usrs = ''
        mem = 0
        main = None
        out = "<table><tr>"
        for co in copis:
            users = co.users.all()
            if users and request.user.is_superuser:
                if len(users) > 1 or not unicode(users[0].user) == unicode(co.nick):
                    usrs = ' (user'+('s!' if len(users)>1 else '')+': '+(', '.join([unicode(us.user) for us in users]))+')'
                else:
                    usrs = ' (=user)'
            else:
                usrs = ' (no user)'
            tps = []
            obs = 0
            props = []
            for att in dir(co):
              if hasattr(co, att):
                met = getattr(co, att)
                #txt = str(met)
                try:
                    res = met.all()
                    if len(res): #len(txt) > 0 and not txt == '>': # and not str(met) in tps:
                        its = []
                        for rs in res:
                            txt = ''+str(rs.id)
                            if att == "is_associate_of":
                                txt += " to "+rs.has_associate.nick+" ("+str(rs.state)+")"
                            its.append(txt)
                        its = ', '.join(its)
                        tps.append('- <em>'+att+'</em>: '+str(len(res))+' - ids['+its+']') #+str(txt)+' Res:')
                        obs += len(res)
                except:
                    #if not att[0] == '_' and len(txt) > 1:
                    pass #tps.append(att+': '+str(txt))
            tps = '<br>'.join(tps)
            for pro in co.__dict__:
                fld = getattr(co, pro)
                if not fld == None and not fld == '':
                    if not isinstance(fld, str):
                        fld = str(fld)
                    props.append('<em>'+pro+'</em>: &nbsp;<b>'+fld+'</b>')
            pros = '<br>'.join(props)
            if obs > mem:
                mem = obs
                main = co
            cases.append('<td style="padding-right:2em; vertical-align:top;"><b><a href="'
                         +reverse('members_agent', args={co.id})+'">'+co.nick+'</a> id:'+str(co.id)+'</b>'
                         +usrs+" ("+str(co.agent_type)+")"+' objects: <b>'+str(obs)+'</b><br>'+tps+'<br><br>'
                         +pros+'</td>')
        actions = ""
        if main:
            actions = "</tr><tr><td><b>main is "+main.nick+"?</b> "
            for co in copis:
                if not co == main:
                    pass #actions += "merge all of "+str(co.nick)+" to main? "
            actions += "</td>"
        cases = ''.join(cases)
        cases = out+cases+actions+'</tr></table>'
        messages.error(request, _("WARNING: The Name '<b>{0}</b>' is set for various agents: ").format(co.name)+cases, extra_tags='safe')
      else:
        pass #messages.info(request, _("No duplicates!"))




#   J O I N A P R O J E C T

from fobi.dynamic import assemble_form_class
from fobi.settings import GET_PARAM_INITIAL_DATA, DEBUG
from fobi.constants import (
    CALLBACK_BEFORE_FORM_VALIDATION,
    CALLBACK_FORM_VALID_BEFORE_SUBMIT_PLUGIN_FORM_DATA,
    CALLBACK_FORM_VALID, CALLBACK_FORM_VALID_AFTER_FORM_HANDLERS,
    CALLBACK_FORM_INVALID
)
from fobi.base import (
    fire_form_callbacks, run_form_handlers, form_element_plugin_registry,
    form_handler_plugin_registry, submit_plugin_form_data, get_theme,
    get_processed_form_data
)
#from fobi.base import (
#    FormHandlerPlugin, form_handler_plugin_registry, get_processed_form_data
#)




def home(request):
    #import pdb; pdb.set_trace()
    return HttpResponseRedirect('/account/login/')


from account.forms import LoginUsernameForm
from django.contrib.auth import authenticate, login

def project_login(request, form_slug = False):
    #import pdb; pdb.set_trace()
    if form_slug:
        project = get_object_or_404(Project, fobi_slug=form_slug)
        if request.user.is_authenticated:
            return members_agent(request, agent_id=project.agent.id)

    form = LoginUsernameForm(data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                agent = user.agent.agent
                req = JoinRequest.objects.filter(project=project, agent=agent)
                if len(req) > 1:
                    #pass # TODO raise error, create notice or repair the multiple join requests of this agent with this project
                    raise ValidationError("This agent has more than one request to join this project! "+str(req))
                elif len(req) == 0:
                    # redirect to the internal joinaproject form
                    return HttpResponseRedirect(reverse('project_joinform', args=(project.agent.id,)))

                elif len(req) == 1:
                    if req[0].pending_shares(): # and req[0].payment_url():
                        return HttpResponseRedirect(reverse('project_feedback', args=(agent.id, req[0].pk)))
                    elif req[0].check_user_pass():
                        return HttpResponseRedirect(reverse('project_feedback', args=(agent.id, req[0].pk)))
                    else:
                        pass #raise ValidationError("This agent has only one request to this project but something is wrong "+str(req[0].check_user_pass()))

                #return HttpResponse(str(agent.nick))
                # Redirect to a success page.
                return HttpResponseRedirect(reverse('my_dashboard'))
            else:
                pass

    return render(request, "work/project_login.html", {
                "project": project,
                "form": form,
                "form_slug": form_slug,
                "redirect_field_name": "next",
                "redirect_field_value": "project_login", #+form_slug,
            })

"""def joinaproject_thanks(request, form_slug = False):
    if form_slug:
      project = Project.objects.get(fobi_slug=form_slug)

    return render(request, "work/joinaproject_thanks.html", {
            "project": project,
           })"""

import simplejson as json
from django.utils.html import escape, escapejs
from django.views.decorators.csrf import csrf_exempt
from django.template.defaultfilters import striptags

@csrf_exempt
def joinaproject_request(request, form_slug = False):
    if form_slug and form_slug == 'freedom-coop':
        pass #return redirect('membership_request')

    fobi_form = False
    cleaned_data = False
    form = False
    if form_slug:
        project = get_object_or_404(Project, fobi_slug=form_slug)
        try:
            user_agent = request.user.agent.agent
            if user_agent and request.user.is_authenticated: # and user_agent.is_active_freedom_coop_member or request.user.is_staff:
                return joinaproject_request_internal(request, project.agent.id)
        except:
            user_agent = False

        # exception meanwhile
        #if form_slug == 'freedom-coop' and not user_agent:
        #    return redirect('membership_request')
        #

        if not project or project.visibility != "public": # or not user_agent:
            return HttpResponseRedirect('/%s/' % ('home'))

        join_form = JoinRequestForm(data=request.POST or None, project=project)

        fobi_slug = project.fobi_slug
        form_entry = None
        try:
            form_entry = FormEntry.objects.get(slug=fobi_slug)
        except:
            print("ERROR: Not found the FormEntry with fobi_slug: "+fobi_slug)
            loger.error("ERROR: Not found the FormEntry with fobi_slug: "+fobi_slug)
            #pass

        form_element_entries = form_entry.formelemententry_set.all()[:]
        form_entry.project = project

        # This is where the most of the magic happens. Our form is being built
        # dynamically.
        FormClass = assemble_form_class(
            form_entry,
            form_element_entries = form_element_entries,
            request = request
        )


    if request.method == "POST":
        fobi_form = FormClass(request.POST, request.FILES)
        #form_element_entries = form_entry.formelemententry_set.all()[:]
        #field_name_to_label_map, cleaned_data = get_processed_form_data(
        #    fobi_form, form_element_entries,
        #)

        wallet_user = None
        api_key = None
        try:
          jdata = json.loads(request.body.decode("utf-8"))
          if 'ocp_api_key' in jdata and jdata['ocp_api_key']:
            POST = {}
            for key, val in list(jdata.items()):
                POST[ key ] = val
            wallet_user = jdata['wallet_user']
            api_key = jdata['ocp_api_key']
            if api_key:
                if 'multicurrency' in settings.INSTALLED_APPS:
                    from multicurrency.models import MulticurrencyAuth
                    from multicurrency.utils import ChipChapAuthConnection
                else:
                    raise ValidationError("The multicurrency app is not installed")
                connection = ChipChapAuthConnection.get()
                if not connection.ocp_api_key:
                    raise ValidationError("The multicurrency connection has not an ocp_api_key!")
                if not api_key == connection.ocp_api_key:
                    loger.error("The api_key don't match ?? ")
                    raise ValidationError("The api_key don't match ?? ")
            else:
                loger.error("The request have not api_key ?? ")
                raise ValidationError("The request have not api_key ?? ")

            fobi_form = FormClass(POST, request.FILES)
            join_form = JoinRequestForm(data=POST, project=project, api_key=True)
            #import pdb; pdb.set_trace()
          else:
            pass #loger.error("Can't find the ocp_api_key in sent data!")
            #raise ValidationError("Can't find the ocp_api_key in sent data!")
        except:
            pass
        if join_form.is_valid():
            human = True
            data = join_form.cleaned_data
            type_of_user = data["type_of_user"]
            name = data["name"]
            surname = data["surname"]

            """
            email = data["email_address"]
            requser = data["requested_username"]
            existuser = None
            existemail = None
            exist_user = EconomicAgent.objects.filter(nick=requser) #User.objects.filter(username=requser)
            exist_email = EconomicAgent.objects.filter(email=email)
            if len(exist_user) > 0:
                existuser = exist_user[0]
            if len(exist_email) > 0:
                existemail = exist_email[0]
            login_form = None
            if existuser or existemail:
                login_form = WorkLoginUsernameForm(initial={'username': requser}) # data=request.POST or None,
            """

            jn_req = join_form.save(commit=False)
            jn_req.project = project


            #request.POST._mutable = True
            #request.POST['join_request'] = str(jn_req.pk)

            if form_slug:
              #fobi_form = FormClass(request.POST, request.FILES)

              # Fire pre form validation callbacks
              fire_form_callbacks(form_entry=form_entry, request=request, form=fobi_form, stage=CALLBACK_BEFORE_FORM_VALIDATION)
              if fobi_form.is_valid():
                #return HttpResponseRedirect('/%s/' % ('joinaprojectthanks'))

                # Fire form valid callbacks, before handling submitted plugin form data.
                fobi_form = fire_form_callbacks(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    stage = CALLBACK_FORM_VALID_BEFORE_SUBMIT_PLUGIN_FORM_DATA
                )

                # Fire plugin processors
                fobi_form = submit_plugin_form_data(form_entry=form_entry,
                                               request=request, form=fobi_form)

                # Fire form valid callbacks
                fobi_form = fire_form_callbacks(form_entry=form_entry,
                                           request=request, form=fobi_form,
                                           stage=CALLBACK_FORM_VALID)

                # Run all handlers
                handler_responses, handler_errors = run_form_handlers(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    form_element_entries = form_element_entries
                )

                # Warning that not everything went ok.
                if handler_errors:
                    for handler_error in handler_errors:
                        messages.warning(
                            request,
                            _("Error occured: {0}."
                              "").format(handler_error)
                        )


                # Fire post handler callbacks
                fire_form_callbacks(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    stage = CALLBACK_FORM_VALID_AFTER_FORM_HANDLERS
                    )

                #messages.info(
                #    request,
                #    _("Form {0} was submitted successfully.").format(form_entry.name)
                #)

                field_name_to_label_map, cleaned_data = get_processed_form_data(
                    fobi_form,
                    form_element_entries
                )

                #for key, value in cleaned_data.items():
                #    if key == "join_request": #isinstance(value, (datetime.datetime, datetime.date)):
                #        cleaned_data[key] = jn_req.pk #value.isoformat() if hasattr(value, 'isoformat') else value

                saved_form_data_entry = SavedFormDataEntry(
                    form_entry = form_entry,
                    user = request.user if request.user and request.user.pk else None,
                    form_data_headers = json.dumps(field_name_to_label_map),
                    saved_data = json.dumps(cleaned_data)
                    )
                saved_form_data_entry.save()
                #jn_req = JoinRequest.objects.get(pk=jn_req.pk)
                jn_req.fobi_data = saved_form_data_entry
                #messages.info(
                #    request,
                #    _("JoinRequest {0} was submitted successfully. {1}").format(jn.fobi_data, saved_form_data_entry.pk)
                #)
                if jn_req.fobi_data:
                    jn_req.save()


                    event_type = EventType.objects.get(relationship="todo")
                    join_url = get_url_starter(request) + "/work/agent/" + str(jn_req.project.agent.id) +"/feedback/"+str(jn_req.id)
                    context_agent = jn_req.project.agent

                    if jn_req.payment_url() or jn_req.multiwallet_user() or jn_req.project.auto_create_pass: # its a credit card payment (or botc multiwallet), create the user and the agent

                        password = jn_req.create_useragent_randompass(request or None)
                        if not password:

                            join_form.add_error('email_address', "Seems like the address don't exist?")
                            jn_req.fobi_data.delete()
                            jn_req.delete()

                            return render(request, "work/joinaproject_request.html", {
                                "help": get_help("work_join_request"),
                                "join_form": join_form,
                                "fobi_form": fobi_form,
                                "project": project,
                                #"post": escapejs(json.dumps(request.POST)),
                            })

                        description = "Check the automatically created Agent and User for the Join Request of "
                        description += name+' '
                        description += "with random password: "+password

                    else:
                        description = "Create an Agent and User for the Join Request from "
                        description += name

                    resource_types = EconomicResourceType.objects.filter(behavior="work")
                    rts = resource_types.filter(
                        Q(name__icontains="Admin")|
                        Q(name__icontains="Coop")|
                        Q(name__icontains="Work"))
                    if rts:
                        rt = rts[0]
                    else:
                        rt = resource_types[0]

                    task = Commitment(
                        event_type=event_type,
                        description=description,
                        resource_type=rt,
                        context_agent=context_agent,
                        url=join_url,
                        due_date=datetime.date.today(),
                        quantity=Decimal("1")
                        )
                    task.save()


                    if notification:
                        managers = jn_req.project.agent.managers()
                        users = []
                        for manager in managers:
                          if manager.user():
                            users.append(manager.user().user)
                        if users:
                            site_name = jn_req.project.agent.nick #get_site_name(request)
                            notification.send(
                                users,
                                "work_join_request",
                                {"name": name,
                                "surname": surname,
                                "type_of_user": type_of_user,
                                "description": description,
                                "site_name": site_name,
                                "current_site": request.get_host(),
                                "join_url": join_url,
                                "context_agent": context_agent,
                                "request_host": request.get_host(),
                                }
                            )

                    if api_key:
                        # return json to the botc call
                        return HttpResponse('{"join_request_id": '+str(jn_req.id)
                                            +', "ocp_agent_id": '+str(jn_req.agent.id if jn_req.agent else 0)
                                            +', "multiwallet_username": "'+str(wallet_user)+'"}', content_type="application/json")
                    else:
                        return render(request, "work/joinaproject_thanks.html", {
                            "project": project,
                            "jn_req": jn_req,
                            #"existuser": existuser,
                            #"existemail": existemail,
                            #"login_form": login_form
                            #"fobi_form": fobi_form,
                            #"field_map": field_name_to_label_map,
                            #"post": escapejs(json.dumps(request.POST)),
                        })
                else:
                    # no fobi data?
                    if api_key:
                        errs = '"missing_fields": "The custom fields are not found ??"'
                        return HttpResponse('{"errors": {'+str(errs)+'}}', content_type="application/json")
                    pass
              else:
                # fobi errors
                # send errors as json if api_key call
                if api_key:
                    errs = ''
                    for err in list(fobi_form.errors.items()):
                        errs += '"'+striptags(err[0])+'": "'+striptags(err[1])+'"'
                    #import pdb; pdb.set_trace()
                    return HttpResponse('{"errors": {'+str(errs)+'}}', content_type="application/json")
                pass

            else:
                # no slug?
                if api_key:
                    errs = '"missing_slug": "The custom form slug is not found ??"'
                    return HttpResponse('{"errors": {'+str(errs)+'}}', content_type="application/json")
                pass
        else:
            # form not valid
            # send errors as json if api_key call
            if api_key:
                errs = ''
                for err in list(join_form.errors.items()):
                    errs += '"'+striptags(err[0])+'": "'+striptags(err[1])+'"'
                #import pdb; pdb.set_trace()
                return HttpResponse('{"errors": {'+str(errs)+'}}', content_type="application/json")
            pass
    else:
        kwargs = {'initial': {'fobi_initial_data':form_slug} }
        fobi_form = FormClass(**kwargs)

    return render(request, "work/joinaproject_request.html", {
        "help": get_help("work_join_request"),
        "join_form": join_form,
        "fobi_form": fobi_form,
        "project": project,
        "post": escapejs(json.dumps(request.POST)),
    })


@login_required
def joinaproject_request_internal(request, agent_id = False):
    proj_agent = get_object_or_404(EconomicAgent, id=agent_id)
    project = proj_agent.project
    form_slug = project.fobi_slug
    usr_agent = request.user.agent.agent
    #if form_slug and form_slug == 'freedom-coop':
    #    if not usr_agent:
    #        return redirect('membership_request')
    reqs = JoinRequest.objects.filter(project=project, agent=usr_agent)

    join_form = JoinRequestInternalForm(data=request.POST or None)
    fobi_form = False
    cleaned_data = False
    form = False
    if form_slug:
      #project = Project.objects.get(fobi_slug=form_slug)
      fobi_slug = project.fobi_slug
      try:
          form_entry = FormEntry.objects.get(slug=fobi_slug)
          form_element_entries = form_entry.formelemententry_set.all()[:]
          #form_entry.project = project
      except:
          return render(request, 'work/no_permission.html') # TODO a better message

      # This is where the most of the magic happens. Our form is being built
      # dynamically.
      FormClass = assemble_form_class(
          form_entry,
          form_element_entries = form_element_entries,
          request = request
      )
    else:
      return render(request, 'work/no_permission.html') # TODO a better message

    if request.method == "POST":
        fobi_form = FormClass(request.POST, request.FILES)
        #form_element_entries = form_entry.formelemententry_set.all()[:]
        #field_name_to_label_map, cleaned_data = get_processed_form_data(
        #    fobi_form, form_element_entries,
        #)

        if join_form.is_valid():
            human = True
            data = join_form.cleaned_data
            type_of_user = usr_agent.agent_type #data["type_of_user"]
            name = usr_agent.name #data["name"]
            surname = "" # usr_agent.surname #data["surname"] # TODO? there's no surname in agent nor in the internal join form
            #description = data["description"]

            jn_req = join_form.save(commit=False)
            jn_req.project = project
            if usr_agent:
              jn_req.agent = usr_agent
              jn_req.name = usr_agent.name
            #jn_req.save()

            #request.POST._mutable = True
            #request.POST['join_request'] = str(jn_req.pk)

            if fobi_form: #form_slug:
              #fobi_form = FormClass(request.POST, request.FILES)

              # Fire pre form validation callbacks
              fire_form_callbacks(form_entry=form_entry, request=request, form=fobi_form, stage=CALLBACK_BEFORE_FORM_VALIDATION)
              if fobi_form.is_valid():
                #return HttpResponseRedirect('/%s/' % ('joinaprojectthanks'))

                # Fire form valid callbacks, before handling submitted plugin form data.
                fobi_form = fire_form_callbacks(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    stage = CALLBACK_FORM_VALID_BEFORE_SUBMIT_PLUGIN_FORM_DATA
                )

                # Fire plugin processors
                fobi_form = submit_plugin_form_data(form_entry=form_entry,
                                               request=request, form=fobi_form)

                # Fire form valid callbacks
                fobi_form = fire_form_callbacks(form_entry=form_entry,
                                           request=request, form=fobi_form,
                                           stage=CALLBACK_FORM_VALID)

                # Run all handlers
                handler_responses, handler_errors = run_form_handlers(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    form_element_entries = form_element_entries
                )

                # Warning that not everything went ok.
                if handler_errors:
                    for handler_error in handler_errors:
                        messages.warning(
                            request,
                            _("Error occured: {0}."
                              "").format(handler_error)
                        )


                # Fire post handler callbacks
                fire_form_callbacks(
                    form_entry = form_entry,
                    request = request,
                    form = fobi_form,
                    stage = CALLBACK_FORM_VALID_AFTER_FORM_HANDLERS
                    )

                messages.info(
                    request,
                    _("Form {0} was submitted successfully.").format(form_entry.name)
                )

                field_name_to_label_map, cleaned_data = get_processed_form_data(
                    fobi_form,
                    form_element_entries
                )

                saved_form_data_entry = SavedFormDataEntry(
                    form_entry = form_entry,
                    user = request.user if request.user and request.user.pk else None,
                    form_data_headers = json.dumps(field_name_to_label_map),
                    saved_data = json.dumps(cleaned_data)
                    )
                saved_form_data_entry.save()
                #jn_req = JoinRequest.objects.get(pk=jn_req.pk)
                jn_req.fobi_data = saved_form_data_entry
                #messages.info(
                #    request,
                #    _("JoinRequest {0} was submitted successfully. {1}").format(jn.fobi_data, saved_form_data_entry.pk)
                #)
                if jn_req.fobi_data:
                    jn_req.save()

                    # add relation candidate
                    if jn_req.agent:
                        if jn_req.project.shares_account_type():
                            ass_type = get_object_or_404(AgentAssociationType, identifier="member")
                        else:
                            ass_type = get_object_or_404(AgentAssociationType, identifier="participant")
                        ass = AgentAssociation.objects.filter(is_associate=jn_req.agent, has_associate=jn_req.project.agent)
                        if ass_type and not ass:
                          fc_aa = AgentAssociation(
                            is_associate=jn_req.agent,
                            has_associate=jn_req.project.agent,
                            association_type=ass_type,
                            state="potential",
                            )
                          fc_aa.save()

                    description = "A new Join Request from OCP user "
                    description += name
                    join_url = get_url_starter(request) + "/work/agent/" + str(jn_req.project.agent.id) +"/join-requests/"

                    #omit task-commitment?

                    if notification:
                        managers = jn_req.project.agent.managers()
                        users = []
                        for manager in managers:
                          if manager.user():
                            users.append(manager.user().user)
                        if users:
                            site_name = jn_req.project.agent.nick #get_site_name(request)
                            notification.send(
                                users,
                                "work_join_request",
                                {"name": name,
                                "surname": surname,
                                "type_of_user": type_of_user,
                                "description": description,
                                "site_name": site_name,
                                "current_site": request.get_host(),
                                "join_url": join_url,
                                "context_agent": proj_agent,
                                "request_host": request.get_host(),
                                }
                            )

                    return HttpResponseRedirect(reverse('members_agent', args=(proj_agent.id,))) #'/%s/' % ('work/your-projects'))

            else:
                raise ValidationError("Can't find the fobi form? jn_req:"+str(jn_req.id))
                #jn_req.save()

    else:
        kwargs = {'initial': {'fobi_initial_data':form_slug} }
        fobi_form = FormClass(**kwargs)

    return render(request, "work/joinaproject_request_internal.html", {
        "help": get_help("work_join_request_internal"),
        "join_form": join_form,
        "fobi_form": fobi_form,
        "project": project,
        "post": escapejs(json.dumps(request.POST)),
        "reqs": reqs,
    })

@login_required
def edit_form_field_data(request, joinrequest_id):
    user_agent = request.user.agent.agent
    req = JoinRequest.objects.get(id=joinrequest_id)
    if req:
      if user_agent in req.project.agent.managers() or user_agent == req.project.agent:
        if request.method == 'POST':
            key = request.POST['id']
            val = request.POST['value']
            if ';' in val:
                val = val.split(';')
            loger.debug("Key:"+str(key)+" Val:"+str(val))
            if req.fobi_data and req.fobi_data.pk:
                req.entries = SavedFormDataEntry.objects.filter(pk=req.fobi_data.pk).select_related('form_entry')
                entry = req.entries[0]
                req.data = json.loads(entry.saved_data)
                if key in req.data:
                    old = req.data[key]
                req.data[key] = val
                entry.saved_data = json.dumps(req.data)

                req.headers = json.loads(entry.form_data_headers)
                if not key in req.headers:
                    print("Fix fobi header! "+key)
                    for elm in entry.form_entry.formelemententry_set.all():
                        pdata = json.loads(elm.plugin_data)
                        if key == pdata['name']:
                            req.headers[key] = pdata['label']
                entry.form_data_headers = json.dumps(req.headers)
                entry.save()
                #import pdb; pdb.set_trace()
                return HttpResponse("Ok", content_type="text/plain")
    return HttpResponse("Fail", content_type="text/plain")


from django.http import HttpResponse
from django.utils.encoding import iri_to_uri

class HttpResponseTemporaryRedirect(HttpResponse):
    status_code = 307

    def __init__(self, redirect_to):
        HttpResponse.__init__(self)
        self['Location'] = iri_to_uri(redirect_to)

import requests

#@mod.route('/payment-url/', methods=['GET', 'POST'])
def payment_url(request, paymode, join_request_id):
    #import pdb; pdb.set_trace()
    url = ''
    payload = {}
    req = get_object_or_404(JoinRequest, pk=join_request_id)
    if settings.PAYMENT_GATEWAYS and paymode:
        gates = settings.PAYMENT_GATEWAYS
        if req.project.fobi_slug and gates[req.project.fobi_slug]:
            url = gates[req.project.fobi_slug][paymode]['url']
            payload = {'order_id': str(join_request_id),
                       'amount': req.pending_shares(),
                       'first_name': req.name,
                       'last_name': req.surname,
                       'email': req.email_address,
                       'lang': 'en',
            }
    if payload['amount'] and not url == '':
        #r = requests.post(url, data=payload) #, allow_redirects=True)
        #import urllib
        #params = urllib.urlencode(payload)
        request.method = "POST"
        request.POST = payload #params
        #resp = HttpResponse(r) #r, content_type="text/html")
        #resp['Location'] = r.url

        #return resp
        return HttpResponse(requests.post(url, data=payload))
        #return redirect(r.url, code=307)
        #return HttpResponseRedirect( url + '&order_id=' + join_request_id + '&amount=' + str(req.pending_shares()) + '&first_name=' + req.name + '&last_name=' + req.surname + '&email=' + req.email_address)
    return HttpResponse('Gateway not properly configured, contact an admin')


def project_total_shares(request, project_slug=None):
    project = False
    if project_slug:
        project = get_object_or_404(Project, fobi_slug=project_slug.strip('/'))

    return render(request, "work/project_shares_totals.html", {
        "project": project,
        "total_shares": project.share_totals(),
        "total_holders": project.share_holders(),
    })



@csrf_exempt
def member_total_shares(request):
    # needs a custom fobi text field (optional) in the form, like 'multiwallet_user', to store the botc username string
    if 'multicurrency' in settings.INSTALLED_APPS:
        from multicurrency.models import MulticurrencyAuth
        from multicurrency.utils import ChipChapAuthConnection
    else:
        raise ValidationError("The multicurrency app is not installed")
    connection = ChipChapAuthConnection.get()
    if not connection.ocp_api_key:
        raise ValidationError("The multicurrency connection has not an ocp_api_key!")
    if not request.method == 'POST':
        raise ValidationError("The call has no POST data?")
    data = json.loads(request.body)
    api_key = data['ocp_api_key']
    if not api_key or not connection.ocp_api_key == api_key:
        raise ValidationError("The given api-key is not valid!! "+str(api_key))
    project_slug = data['project_slug']
    wallet_user = data['wallet_user']
    agent_id = data['ocp_agent_id']
    project = False
    if project_slug:
        project = get_object_or_404(Project, fobi_slug=project_slug.strip('/'))
    else:
        loger.warning("Can't find the project with slug: "+str(project_slug))
        return HttpResponse('{"error": "not found the project with this slug"}', content_type='application/json')
    if wallet_user:
        if project.is_moderated() and project.fobi_slug:
            fobi_form = project.fobi_form()
            shrtyp = project.shares_type()
            texplug = SavedFormDataEntry.objects.filter(form_entry__id=fobi_form.id, saved_data__contains='"'+wallet_user+'"')
            jnreq = None
            if len(texplug) == 1:
                jnreq = texplug[0].join_request
                if agent_id and jnreq.agent and not str(jnreq.agent.id) == agent_id:
                    loger.error("The agent id not match the join_request agent? "+str(agent_id))
                    #return HttpResponse('{"error": "The agent id not match the join_request agent?"}', content_type='application/json')
                    raise ValidationError("The agent id not match the join_request agent? "+str(agent_id))
            elif not texplug:
                multiauth = MulticurrencyAuth.objects.filter(auth_user=wallet_user)
                if multiauth:
                    if len(multiauth) == 1:
                        jnreq = JoinRequest.objects.filter(project=project, agent=multiauth.agent)
                        if jnreq:
                            if len(jnreq) == 1:
                                # TODO update fobi field 'multiwallet_user' with auth_user
                                jnreq = jnreq[0] #return HttpResponse('{"owned_shares": '+str(jnreq[0].total_shares())+', "requested_shares": '+str(jnreq[0].payment_amount())+'}', content_type='application/json')
                            else:
                                loger.error("More than one jnreq for this agent ?? "+str(jnreq))
                                raise ValidationError("More than one jnreq for this agent ?? "+str(jnreq))
                    else:
                        loger.error("More than one multiauth for this agent ?? "+str(multiauth))
                        raise ValidationError("More than one multiauth for this agent ?? "+str(multiauth))
            else:
                loger.warning("There's more than one request with wallet_user: "+str(wallet_user))
                return HttpResponse('{"error": "more than one request with this wallet_user"}', content_type='application/json')
            #import pdb; pdb.set_trace()

            if not jnreq:
                return HttpResponse('{"error": "join_request not found"}', content_type='application/json')

            return HttpResponse('{"owned_shares": '+str(jnreq.total_shares())
                                +', "requested_shares": '+str(jnreq.payment_amount())
                                +', "wallet_user": "'+str(wallet_user)
                                +'", "gateway": "'+str(jnreq.payment_gateway())
                                +'", "share_model": {"price": '+str(shrtyp.price_per_unit)
                                +', "price_unit": "'+str(shrtyp.unit_of_price.abbrev)
                                +'", "name": "'+str(shrtyp.unit.name)
                                +'", "abbrev": "'+str(shrtyp.unit.abbrev)
                                +'"}}', content_type='application/json')


        else:
            loger.warning("The project is not moderated or has no fobi_slug: "+str(project))
            return HttpResponse('{"error": "the project is not moderated or has no fobi_slug"}', content_type='application/json')
    else:
        loger.warning("The wallet_user string is required! project: "+str(project_slug))
        return HttpResponse('{"error": "the wallet_user string is required"}', content_type='application/json')


@csrf_exempt
def project_update_payment_status(request, project_slug=None):
    project = False
    if project_slug:
        project = get_object_or_404(Project, fobi_slug=project_slug.strip('/'))
    if project and request.POST:
        user_agent = request.user.agent.agent
        if user_agent == project.agent or user_agent in project.agent.managers():
            pass
        else:
            raise ValidationError("User not allowed to do this.")

        req_id = request.POST["order_id"]
        price = request.POST["price"]
        status = request.POST["status"]
        email = request.POST["email"]
        lang = request.POST["lang"]
        token = request.POST["token"]
        unit = request.POST["unit"]
        gateref = request.POST["reference"]

        req = None
        unit_rt = None

        try:
            req = get_object_or_404(JoinRequest, id=req_id*1)
        except:
            raise ValidationError("Can't find a join request with id: "+str(req_id))
            #return HttpResponse('error')

        if req:
            account_type = req.payment_account_type()
            balance = 0
            amount = req.payment_amount()

            if not token == req.payment_token():
                pass #raise ValidationError("The token is not valid! "+str(token))
                #return HttpResponse('error')

            if not project == req.project:
                raise ValidationError("The project is not the request project! "+str(project)+" != "+str(req.project))
                #return HttpResponse('error')

            if not str(amount) == str(price):
                raise ValidationError("The payment amount and the request amount are not equal! price:"+str(price)+" amount:"+str(amount))
                #return HttpResponse('error')

            if not email == req.email_address:
                raise ValidationError("The payment email and the request email are not equal! email:"+str(email)+" reqemail:"+str(req.email_address))
                #return HttpResponse('error')

            if not account_type:
                raise ValidationError("The payment is not related any account type?")
                #return HttpResponse('error')

            if not gateref:
                raise ValidationError("The payment is not related any gateway reference?")
                #return HttpResponse('error')

            if not unit:
                raise ValidationError("The payment is not related any unit?")
            else:
                try:
                    unit = Unit.objects.get(abbrev=unit.lower())
                except:
                    raise ValidationError("Not found a Unit with abbreviation: "+unit.lower())
                punit = req.payment_unit()
                if not unit == punit:
                    raise ValidationError("The unit in the post is not the same as in the join_request!! "+str(unit)+" != "+str(punit))

            done = req.update_payment_status(status, gateref)
            if done:
                return redirect('project_feedback', agent_id=req.project.agent.id, join_request_id=req.id)
            else:
                raise ValidationError("Unkown error updating the status of the payment")

        else:
            raise ValidationError("Can't find a false join request: "+str(req))
            return HttpResponse('error')

    else:
        raise ValidationError("Can't find a project or request:POST: "+str(request.POST))
        return HttpResponse('error')



from django.middleware import csrf

@login_required
def join_requests(request, agent_id):
    user_agent = request.user.agent.agent
    agent = EconomicAgent.objects.get(pk=agent_id)
    managing = False
    if user_agent == agent or user_agent in agent.managers():
        pass
    else:
        raise ValidationError("User not allowed to see this page.")
    print("-------------- start join_requests ("+str(agent)+") (user:"+str(user_agent)+") ----------------")
    loger.debug("-------------- start join_requests ("+str(agent)+") (user:"+str(user_agent)+") ----------------")
    state = "new"
    state_form = RequestStateForm(
        initial={"state": "new",},
        data=request.POST or None)

    if request.method == "POST":
        if state_form.is_valid():
            data = state_form.cleaned_data
            state = data["state"]

    project = agent.project
    requests =  JoinRequest.objects.filter(state=state, project=project).order_by('pk').reverse() #'request_date')
    agent_form = JoinAgentSelectionForm(project=project)

    fobi_slug = project.fobi_slug
    fobi_headers = []
    fobi_keys = []

    if fobi_slug and requests:
        form_entry = FormEntry.objects.get(slug=fobi_slug)
        if user_agent == project.agent or user_agent in project.agent.managers():
            managing = True
        #req = requests.last()

        for req in requests:
            #print("--- req1: "+str(req)+" ----")
            if req.fobi_data and req.fobi_data.pk:
                fobi_keys = req.fobi_items_keys()
                fobi_headers = req.form_headers
                break


    if project.is_moderated() and not agent.email:
        messages.error(request, _("Please provide an email for the \"{0}\" project to use as a remitent for the moderated joining process notifications!").format(agent.name))

    print("-------------- end join_requests ("+str(agent)+") (user:"+str(user_agent)+") ----------------")
    loger.debug("-------------- end join_requests ("+str(agent)+") (user:"+str(user_agent)+") ----------------")

    return render(request, "work/join_requests.html", {
        "help": get_help("join_requests"),
        "requests": requests,
        "state_form": state_form,
        "state": state,
        "agent_form": agent_form,
        "project": project,
        "fobi_headers": fobi_headers,
    })



from django_datatables_view.base_datatable_view import BaseDatatableView

class JoinreqListJson(BaseDatatableView):

    # define the columns that will be returned
    columns = ['actions', 'request_date', 'name', 'requested_username', 'type_of_user', 'email_address', 'phone_number', 'address', 'website']

    order_columns = ['', 'request_date', 'name', 'requested_username', 'type_of_user', 'email_address', '', '', '']

    # set max limit of records returned, this is used to protect our site if someone tries to attack our site
    # and make it return huge amount of data
    max_display_length = 500

    def get(self, request, agent_id, *args, **kwargs):
        self.user_agent = request.user.agent.agent
        if not hasattr(self, 'agent'):
            agent_id = self.kwargs['agent_id']
            self.agent = EconomicAgent.objects.get(id=agent_id)
        if not hasattr(self, 'state'):
            self.state = self.kwargs['state']
        if not hasattr(self, 'csrf_token_field'):
            csrf_token = csrf.get_token(request)
            self.csrf_token_field = '<input type="hidden" name="csrfmiddlewaretoken" value="'+csrf_token+'"> '
        if not hasattr(self, 'com_content_type'):
            self.com_content_type = ContentType.objects.get(model="joinrequest")

        if hasattr(self.agent, 'project') and self.agent.project:
            if not hasattr(self, 'proshrtyps'):
                self.proshrtyps = self.agent.project.share_types()
            if not hasattr(self, 'subscrunit'):
                self.subscrunit = self.agent.project.subscription_unit()
            self.fobi_keys = self.agent.project.fobi_items_keys()
            if self.fobi_keys:
                for key in self.fobi_keys:
                    if not key in self.columns:
                        #print("add col: "+key)
                        self.columns.append(key)
                    if not key in self.order_columns:
                        #print("add ord-col: "+key)
                        self.order_columns.append(key)

        else:
            self.proshrtyps = None
            self.subscrunit = None

        return super().get(request, *args, **kwargs)

    def get_initial_queryset(self):
        if self.agent.project:
            return self.agent.project.join_requests.filter(state=self.state)
        else:
            return None

    def filter_queryset(self, qs):

        return qs

    def render_column(self, row, column):
        # We want to render user as a custom column
        if column == 'actions':
            row.actions += "JELOW"
            return row.actions #escape('{0} {1}'.format(row.customer_firstname, row.customer_lastname))
        else:
            return super(JoinreqListJson, self).render_column(row, column)

    def prepare_results(self, qs):
        # prepare list with output column data
        # queryset is already paginated here
        #print('--- prepare results (start) ----') #cols: '+str(self.columns))
        project = self.agent.project
        agent_form = JoinAgentSelectionForm(project=project)

        fobi_slug = project.fobi_slug
        fobi_headers = []
        #fobi_keys = []

        json_data = []

        if fobi_slug:
          form_entry = FormEntry.objects.get(slug=fobi_slug)
          if self.user_agent == project.agent or self.user_agent in project.agent.managers():
            managing = True

          for req in qs:
            req.possible_agent = False
            if not hasattr(req, 'agent') and req.requested_username:
                try:
                    req.possible_agent = EconomicAgent.objects.get(nick_en=req.requested_username)
                except:
                    pass
            if hasattr(req, 'fobi_data') and hasattr(req.fobi_data, 'pk'):
              req.items_data = req.fobi_items_data()
            else:
              req.entries = []

            # calculate the actions table cell to speedup the template
            req.actions = ''
            chekpass = req.check_user_pass()
            payamount = req.payment_amount()
            totalshrs = req.total_shares()
            pendshrs = req.pending_shares()
            reqstatus = ''
            if req.exchange:
                reqstatus = req.exchange.status()

            pendpays = req.pending_payments()
            subscres = req.subscription_resource()

            req.mail = '<a class="longtext" href="mailto:'+req.email_address+'">'+req.email_address+'</a>'
            req.webs = ''
            if req.website:
                req.webs = req.website
            req.phon = req.phone_number
            req.addr = req.address

            if req.agent:
                req.nam = '<a href="{% url "members_agent" agent_id=req.agent.id %}">'+req.agent.name+'</a>'
                if not req.name and not req.surname:
                    arr = req.agent.name.split(' ')
                    if len(arr) > 1:
                        req.name = arr[0]
                        req.surname = arr[1]
                    else:
                        req.name = req.agent.name
                    loger.info("- added missing name to the jnreq: "+str(req))
                    req.save()

                req.nick = '<a href="{% url "members_agent" agent_id=req.agent.id %}"><b><em>'+req.agent.nick+'</em></b></a>'
                if not req.requested_username:
                    req.requested_username = req.agent.nick
                    loger.info("- added missing username to the jnreq: "+str(req))
                    req.save()

                req.typ = req.agent.agent_type.name
                if not req.typ.lower() == req.type_of_user.lower():
                    req.typ += ' ('+req.type_of_user+')'
                if not req.agent.email == req.email_address:
                    if req.email_address:
                        req.mail += " <span class='longtext small'><em>("+req.agent.email+")</em></span>"
                    elif req.agent.email:
                        req.email_address = req.agent.email
                        req.save()
                        loger.info("- added missing agent email in join-request: "+str(req))
                        req.mail = '<em><a class="longtext" href="mailto:'+req.agent.email+'">'+req.agent.email+'</a></em>'
                if req.agent.url and not req.agent.url == req.website:
                    if req.website:
                        req.webs += ' <em>('+req.agent.url+')</em>'
                    else:
                        req.webs = '<em>'+req.agent.url+'</em>'
                if req.agent.phone_primary and not req.agent.phone_primary == req.phone_number:
                    if req.phone_number:
                        req.phon += " <em>("+req.agent.phone_primary+")</em>"
                    else:
                        req.phon = '<em>'+req.agent.phone_primary+'</em>'
                if req.agent.primary_location and not req.address:
                    req.addr = '<em>'+str(req.agent.primary_location)+'</em>'

            else:
                req.nam = req.name+' '+req.surname
                req.nam.strip()
                if req.requested_username:
                    req.nick = req.requested_username
                else:
                    req.nick = '??'
                req.typ = req.type_of_user

            if req.check_user_pass():
                req.mail += '<br /><span class="error">'+str(_("not verified"))+'</span>'

            #print("------- build actions ---")
            deleteform = '<form class="action-form" id="delete-form'+str(req.id)+'" method="POST" '
            deleteform += 'action="'+reverse("delete_request", args=(req.id,))+'" >'
            deleteform += self.csrf_token_field
            deleteform += '<input type="submit" class="btn btn-mini btn-danger" name="submit" value="'+str(_("Delete"))+'" /></form>'

            declineform = '<form class="action-form" id="decline-form'+str(req.id)+'" method="POST" '
            declineform += 'action="'+reverse("decline_request", args=(req.id,))+'" >'
            declineform += self.csrf_token_field
            declineform += '<input type="submit" class="btn btn-mini btn-warning" name="submit" value="'+str(_("Decline"))+'" /></form>'


            if not req.fobi_data:
                req.actions = '<span class="error">ERROR!</span> &nbsp;'
            if chekpass:
                req.actions += '<span class="error">'+str(_("Not Valid yet!"))+'</span> &nbsp;'
            elif self.proshrtyps or self.subscrunit:
              if req.fobi_data:
                if req.agent:
                    if self.proshrtyps:
                        req.actions += '<span style="display: inline-block;">'
                        req.actions += '<i class="icon-tags" style="color:#444;" title="'+str(payamount)+' '+str(_("Shares"))+'"></i>'
                        req.actions += '&nbsp;'+str(payamount)+'</span> &nbsp;'
                    elif self.subscrunit:
                        if pendpays: req.actions += '<span class="error">'
                        req.actions += str(payamount)+'&nbsp;'
                        req.actions += str(self.subscrunit.name)+' / '+str(req.payment_regularity()['key'])+'&nbsp;'
                        if pendpays: req.actions += '</span>'
                    if pendshrs:
                        if totalshrs:
                            req.actions += '<span class="complete">'+str(totalshrs)+'</span>&nbsp;+&nbsp;<span class="error">'+str(req.pending_shares())+'</span>'
                        else:
                            if pendpays:
                                if subscres:
                                    req.actions += '<span class="">'+str(_("Expired"))+'</span>'
                                    req.actions += '<br><span class="">'+str(_("by"))+' '+str(req.subscription_resource().expiration_date)+'</span> '
                                else:
                                    pass #req.actions += '<br><span class="error small">'+unicode(_("Never payed"))+'</span>'
                            elif self.subscrunit:
                                req.actions += '<span class="complete">'+str(_("Valid"))+'</span>'
                                req.actions += '<br><span class="">'+str(_("until"))+' '+str(req.subscription_resource().expiration_date)+'</span> '
                            else:
                                req.actions += '<span class="error">'+str(totalshrs)+'</span> '
                    else:
                        if not totalshrs == payamount:
                            req.actions += '<span class="complete">'+str(totalshrs)+'</span> '
                        else:
                            req.actions += '<em class="complete"></em>'
                    #req.actions += '<br />'
                if reqstatus:
                    req.actions += '<a href="'+reverse("exchange_logging_work", args=(req.project.agent.id, 0, req.exchange.id))+'"'
                    req.actions += ' class="'+str(reqstatus)+'" >'+str(reqstatus.title())+'</a> '
                elif pendshrs:
                    if not req.payment_option()['key'] == 'ccard' and req.agent and req.exchange_type() and not req.state == 'declined':
                        if managing:
                            req.actions += '<form class="action-form" id="status-form'+str(req.id)+'" '
                            req.actions += 'action="'+reverse("update_share_payment", args=(req.id,))+'" method="POST" >'
                            req.actions += self.csrf_token_field
                            req.actions += '<input type="hidden" name="status" value="pending"> '
                            req.actions += '<input type="submit" class="btn btn-mini btn-primary" name="submit" '
                            req.actions += ' value="'+str(_("Set as Pending"))+'" title="ExchangeType: '+str(req.exchange_type())+'" '
                            if chekpass:
                                req.actions += 'disabled="disabled" '
                            req.actions += ' /></form>'

                    if self.user_agent.user().user.is_superuser:
                        pass
                        #req.actions += '<span class="help-text" style="font-size:0.8em">ET: '+str(req.exchange_type())
                        #req.actions += ' <br />UT: '+str(req.payment_unit())+' RT: '+str(req.payment_unit_rt())+'</span><br />'
              else:
                # not fobi_data
                print(("Not fobi_data for req: "+str(req.id)))

            else:
                # not proshrtyps nor subscrunit
                print(("Not proshrtyps nor subscrunit for req: "+str(req.id)))

            dup = req.duplicated()
            if dup:
                req.actions += '<em class="error">'+str(_("Duplicated!"))+'</em>'
                req.actions += '('+str(_("see the other"))+' <a href="'+reverse('project_feedback', args=(req.project.agent.id, dup.id))+'" >'
                req.actions += str(_("request"))+'</a>) <br /> '+str(_("This request:"))+' '
                req.actions += deleteform

            ncom = len(Comment.objects.filter(content_type=self.com_content_type, object_pk=req.pk))
            req.actions += '<a class="btn btn-info btn-mini-icon" href="'+reverse('project_feedback', args=(req.project.agent.id, req.id))+'">'
            req.actions += '<i class="icon-comment" title="Feedback"></i><span class="small"> '+str(ncom)+'</span></a>&nbsp;'

            if self.state == "declined":
                req.actions += '<form class="action-form" id="undecline-form'+str(req.id)+'" method="POST" '
                req.actions += 'action="'+reverse("undecline_request", args=(req.id,))+'" >'
                req.actions += self.csrf_token_field
                req.actions += '<input type="submit" class="btn btn-mini btn-primary" name="submit" value="'+str(_("Undecline"))+'" /></form>'

                req.actions += deleteform

            elif self.state == "accepted":
                req.actions += declineform

            elif req.fobi_data:
                if req.agent:
                    if not pendshrs or not self.proshrtyps:
                        if not self.subscrunit:
                          if not chekpass:
                            req.actions += '<form class="action-form" id="accept-form'+str(req.id)+'" method="POST" '
                            req.actions += 'action="'+reverse("accept_request", args=(req.id,))+'" >'
                            req.actions += self.csrf_token_field
                            req.actions += '<input type="submit" class="btn btn-mini btn-primary" name="submit" value="'+str(_("Accept Member"))+'" /></form>'

                    if chekpass:
                        if req.agent.is_deletable():
                            req.actions += ' &nbsp; <span class="help-text">'+str(_("Wait to confirm, or delete agent, user and request"))+':</span>'
                            req.actions += '<form style="display: inline;" class="delete-agent-form indent" id="delete-agent-form'+str(req.id)+'" '
                            req.actions += 'action="'+reverse("delete_request_agent_and_user", args=(req.id,))+' " method="POST" >'
                            req.actions += self.csrf_token_field
                            req.actions += '<button style="display: inline;"  class="btn btn-danger btn-mini" title="Delete all" >'+str(_("Delete all"))+'</button></form>'
                        elif self.user_agent.user().user.is_superuser:
                            req.actions += ' &nbsp; (agent no deletable)'
                    else:
                        req.actions += declineform

                else:
                    posag = req.possible_agent
                    if posag:
                        req.actions += '<br>"<a href="'+reverse('members_agent', args=(posag.id,))+'">'+str(posag)+'</a>" '+str(_("is taken, choose this agent?"))
                        req.actions += '<a href="'+reverse("connect_agent_to_join_request", args=(posag.id, req.id))+'" class="btn btn-primary" '
                        req.actions += 'style="margin-bottom:20px;">'+str(_("Connect to"))+' '+str(posag)+'</a> <br />'

                    req.actions += '<form class="action-form" id="create-form'+str(req.id)+'" '
                    req.actions += 'action="'+reverse("confirm_request", args=(req.id,))+'" method="POST" >'
                    req.actions += self.csrf_token_field
                    req.actions += '<input type="submit" class="btn btn-mini btn-primary" name="submit" value="'+str(_("Confirm Email"))+'" /> '
                    req.actions += '<span class="help-text">'+str(_("sends random pass and creates user+agent"))+'</span></form>'

                    req.actions += deleteform

            else:
                req.actions += deleteform

            #print("------ end build actions ---")
            camps = [
                req.actions,
                req.request_date.strftime("%Y-%m-%d"), # %H:%M  #escape(item.number),  # escape HTML for security reasons
                req.nam, #"{0} {1}".format(item.customer_firstname, item.customer_lastname)),  # escape HTML for security reasons
                req.nick,
                req.typ,
                req.mail,
                req.phon,
                req.addr,
                req.webs
            ]

            if hasattr(req, 'items_data'):
                camps = camps + req.items_data
                #for val in req.items_data:
                #    camps = camps + .append([val])
            else:
                for val in self.fobi_keys:
                    camps = camps + ["<span class='error'>"+str(_("missing"))+"</span>"]

            json_data.append(camps)


            #print("json_data: "+str(json_data))
          # endfor
        #print('--- prepare results (end) ----')

        return json_data


    """
    jnreqs = None
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not user_agent or not agent.project or not agent in user_agent.managed_projects():
        return render(request, 'work/no_permission.html')

    if request.POST:
        draw = int(request.POST['draw'])
        start = request.POST['start']
        length = request.POST['length']
        search = request.POST['search']
        columns = request.POST['columns']
        order = request.POST['order']
        ordcol1 = order[0]

        state = request.POST['state']

        jnreqnum = agent.project.join_requests.count()

        jnreqs = agent.project.join_requests.filter(state=state).order_by(ordcol1)

        com_content_type = ContentType.objects.get(model="joinrequest")
        csrf_token = csrf.get_token(request)
        csrf_token_field = '<input type="hidden" name="csrfmiddlewaretoken" value="'+csrf_token+'"> '

        proshrtyps = agent.project.share_types()
        subscrunit = agent.project.subscription_unit()

        data = []

        for req in jnreqs:

            data.append(
                [
                    req.actions,
                    req.request_date,
                    req.name,
                    req.nick,
                    req.typ,
                    req.mail
                ]
            )

            #print("---- end req: "+str(req)+" ----")


    return render(request, 'work/_jnreq_list.html', {
            'jnreqs': jnreqs,
            'agent': agent,
            'user_agent': user_agent,
            'draw': draw,
            'recordsTotal': jnreqnum,
            'recordsFiltered': len(jnreqs),
            'data': data,
            'error': error
        })
"""


'''@login_required
def join_request(request, join_request_id):
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'work/no_permission.html')
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    init = {
        "name": " ".join([mbr_req.name, mbr_req.surname]),
        "nick": mbr_req.requested_username,
        #"description": mbr_req.description,
        "email": mbr_req.email_address,
        "url": mbr_req.website,
        }
    if mbr_req.type_of_user == "individual":
        at = AgentType.objects.filter(party_type="individual")
        if at:
            at = at[0]
            init["agent_type"] = at
    agent_form = AgentCreateForm(initial=init)
    nicks = '~'.join([
        agt.nick for agt in EconomicAgent.objects.all()])
    return render(request, "work/join_request.html", {
        "help": get_help("join_request"),
        "mbr_req": mbr_req,
        "agent_form": agent_form,
        "user_agent": user_agent,
        "nicks": nicks,
    })
'''

@login_required
def decline_request(request, join_request_id):
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    mbr_req.state = "declined"
    mbr_req.save()
    if mbr_req.agent and mbr_req.project:
        # modify relation to active
        ass_type = AgentAssociationType.objects.get(identifier="participant")
        aass = AgentAssociation.objects.filter(is_associate=mbr_req.agent, has_associate=mbr_req.project.agent, association_type=ass_type)
        if len(aass) > 1:
            ass = aass[0]
            aass[1].delete()
        else:
            ass, created = AgentAssociation.objects.get_or_create(is_associate=mbr_req.agent, has_associate=mbr_req.project.agent, association_type=ass_type)
        ass.state = "potential"
        ass.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', mbr_req.project.agent.id, 'join-requests'))

@login_required
def undecline_request(request, join_request_id):
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    mbr_req.state = "new"
    mbr_req.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', mbr_req.project.agent.id, 'join-requests'))

@login_required
def delete_request(request, join_request_id):
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    if mbr_req.fobi_data:
        fd = get_object_or_404(SavedFormDataEntry, id=mbr_req.fobi_data.id)
        fd.delete()
    if mbr_req.agent:
      pass # delete user and agent?
    mbr_req.delete()

    if 'next' in request.POST and request.POST['next']:
        slug = request.POST['next']
        if slug == 'project':
            slug = ''
        if slug == 'feedback':
            slug = 'feedback/'+str(jn_req.id)
    else:
        slug = 'join-requests'

    return HttpResponseRedirect('/%s/%s/%s'
        % ('work/agent', mbr_req.project.agent.id, slug))

@login_required
def delete_request_agent_and_user(request, join_request_id):
    req = get_object_or_404(JoinRequest, pk=join_request_id)
    if req.agent:
        rs = req.agent.resource_relationships()
        usr = req.agent.user().user
        if rs:
            raise ValidationError("The agent has resources, you cannot delete it! "+str(req.agent)+" / req: "+str(req))
        if usr:
            if usr.is_staff or usr.is_superuser:
                raise ValidationError("You can'n delete a staff member!! "+str(usr))
            if usr.account:
                pass #usr.account.delete()
            else:
                raise ValidationError("The user has not an 'account' to delete: "+str(usr)+" / req: "+str(req))
            if req.agent.is_deletable():
                req.agent.delete()
            else:
                raise ValidationError("The agent of this request is not deletable! "+str(req.agent)+" / req: "+str(req))
            usr.delete()
        else:
            raise ValidationError("The agent of this request has no User to delete! "+str(req.agent)+" / req: "+str(req))
    else:
        raise ValidationError("The request has no agent! "+str(req))
    req.delete()

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', req.project.agent.id, 'join-requests'))

@login_required
def confirm_request(request, join_request_id):
    jn_req = get_object_or_404(JoinRequest, pk=join_request_id)
    if jn_req.agent:
        raise ValidationError("This request already has an agent !!!")
    if not jn_req.project:
        raise ValidationError("This request has no project ??!!!")
    if not jn_req.project.agent.email:
        messages.warning(request, _("The project is missing its own Email Address! (needed to send notifications to users from the project)"))
        #raise ValidationError("The project is missing an Email Address !! (needed to send notifications to users)")
    user_agent = get_agent(request)
    if not user_agent in jn_req.project.agent.managers():
        raise ValidationError("You don't have permission to do this !!!")

    jn_req.create_useragent_randompass(request)

    if 'next' in request.POST and request.POST['next']:
        slug = request.POST['next']
        if slug == 'project':
            slug = ''
        if slug == 'feedback':
            slug = 'feedback/'+str(jn_req.id)
    else:
        slug = 'join-requests'

    return HttpResponseRedirect('/%s/%s/%s'
        % ('work/agent', jn_req.project.agent.id, slug))

@login_required
def accept_request(request, join_request_id):
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    mbr_req.state = "accepted"
    mbr_req.save()

    # modify relation to active
    aas = AgentAssociation.objects.filter(is_associate=mbr_req.agent, has_associate=mbr_req.project.agent)
    association = None
    if mbr_req.project.shares_type():
        association_type = AgentAssociationType.objects.get(identifier="member")
        if len(aas) == 1 and not aas[0].association_type == association_type and not aas[0].association_type.identifier == 'manager':
            association = aas[0]
            association.association_type = association_type
            association.save()
            loger.warning("Changed the association_type from 'participant' to 'member' because the project involves shares.")
            messages.warning(request, "Changed the association_type from 'participant' to 'member' because the project involves shares.")
    else:
        association_type = AgentAssociationType.objects.get(identifier="participant")
    if not association:
        association, created = AgentAssociation.objects.get_or_create(
            is_associate=mbr_req.agent, has_associate=mbr_req.project.agent, association_type=association_type)
        if created:
            print("- created AgentAssociation: "+str(association))
            loger.info("- created AgentAssociation: "+str(association))
    association.state = "active"
    association.save()
    messages.info(request, "Modified agent association to 'active': "+str(association))

    return redirect('project_feedback', agent_id=mbr_req.project.agent.id, join_request_id=join_request_id)
    #HttpResponseRedirect('/%s/%s/%s/'
    #    % ('work/project-feedback', mbr_req.project.agent.id, join_request_id))

@login_required
def update_share_payment(request, join_request_id):
    jn_req = get_object_or_404(JoinRequest, pk=join_request_id)
    if not jn_req.agent:
        raise ValidationError("This request has no agent ?!!")
    if not jn_req.project:
        raise ValidationError("This request has no project ??!!!")
    user_agent = get_agent(request)
    if user_agent in jn_req.project.agent.managers() or user_agent == jn_req.project.agent:
        pass
    else:
        raise ValidationError("You don't have permission to do this !!!")
    if request.method == "POST":
        status = request.POST.get("status")
        gateref = request.POST.get("reference")
        notes = request.POST.get("notes")
        realamount = request.POST.get("real_amount")
        txid = request.POST.get("tx_id")
        next = request.POST.get("next")
        if not next:
            next = "project_feedback"
        if status:
            jn_req.update_payment_status(status, gateref, notes, request, realamount, txid)
        else:
            raise ValidationError("Missing status ("+str(status)+") !") # or gateway reference ("+str(gateref)+") !")
    else:
        raise ValidationError("The request has no POST data!")

    return redirect(next, agent_id=jn_req.project.agent.id, join_request_id=jn_req.id) #'/%s/%s/%s/'
        #% ('work/agent', jn_req.project.agent.id, 'join-requests'))


from itertools import chain

@login_required
def create_account_for_join_request(request, join_request_id):
    if request.method == "POST":
        jn_req = get_object_or_404(JoinRequest, pk=join_request_id)
        form = ProjectAgentCreateForm(prefix=jn_req.form_prefix(), data=request.POST or None)
        if form.is_valid():
            data = form.cleaned_data
            agent = form.save(commit=False)
            agent.created_by=request.user
            if not agent.is_individual():
                agent.is_context=True
            agent.save()
            jn_req.agent = agent
            jn_req.save()
            project = jn_req.project
            # add relation candidate
            ass_type = get_object_or_404(AgentAssociationType, identifier="participant")
            if ass_type:
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
                    #agent.request_faircoin_address()

                    name = data["name"]
                    if notification:
                        managers = project.agent.managers()
                        sett = set_user_notification_by_type(agent.user().user, "work_new_account", True)
                        users = [agent.user().user,]
                        for manager in managers:
                            if manager.user():
                                users.append(manager.user().user)
                        #users = User.objects.filter(is_staff=True)
                        if users:
                            #allusers = chain(users, agent)
                            #users = list(users)
                            #users.append(agent.user)
                            site_name = project.agent.nick #get_site_name(request)
                            notification.send(
                                users,
                                "work_new_account",
                                {"name": name,
                                "username": username,
                                "password": password,
                                "site_name": site_name,
                                "current_site": request.get_host(),
                                "context_agent": project.agent,
                                "request_host": request.get_host(),
                                }
                            )

            return HttpResponseRedirect('/%s/%s/%s/'
                % ('work/agent', project.agent.id, 'join-requests'))

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', jn_req.project.agent.id, 'join-requests'))

@login_required
def join_project(request, project_id):
    if request.method == "POST":
        project = get_object_or_404(EconomicAgent, pk=project_id)
        user_agent = get_agent(request)
        association_type = AgentAssociationType.objects.get(identifier="participant")
        aas = AgentAssociation.objects.filter(is_associate=user_agent, has_associate=project)
        if aas:
            if len(aas) > 1:
                raise ValidationError("This agent ("+str(user_agent)+") has more than one existent relations with the project: "+str(project))
            else:
                aa = aas[0]
                aa.association_type = association_type
                aa.state = 'active'
                aa.save()
        else:
            aa = AgentAssociation(
                is_associate=user_agent,
                has_associate=project,
                association_type=association_type,
                state="active",
            )
            aa.save()

    return HttpResponseRedirect("/work/your-projects/")

@login_required
def resend_candidate_credentials(request, joinrequest_id):
    user_agent = get_agent(request)
    jn_req = get_object_or_404(JoinRequest, pk=joinrequest_id)
    project = jn_req.project
    allowed = False
    if user_agent and jn_req and project == jn_req.project:
      if user_agent.is_staff() or user_agent in project.agent.managers() or user_agent is project.agent:
        allowed = True
    if not allowed:
        return render(request, 'work/no_permission.html')

    password = jn_req.check_user_pass(True)
    if notification:
        sett = set_user_notification_by_type(jn_req.agent.user().user, "work_new_account", True)
        #print("sett: "+str(sett))
        """
        from email.MIMEMultipart import MIMEMultipart
        from email.MIMEText import MIMEText
        fromaddr = project.agent.email
        toaddr = jn_req.agent.email
        msg = MIMEMultipart()
        msg['From'] = fromaddr
        msg['To'] = toaddr
        msg['Subject'] = _("OCP credentials for %(nick)s to join %(pro)s") % {'nick':jn_req.agent.nick, 'pro':project.agent.name}
        body = _("New OCP Account created for %(usr)s to join %(pro)s \n\nUsername: %(usrnam)s\nPassword: %(pas)s\n\nYou can log in at %(url)s\n\nWelcome to the Open Collaborative Platform!") % {'usr':jn_req.agent.name, 'pro': project.agent.name, 'usrnam':jn_req.agent.nick, 'pas':password, 'url':'https://'+request.get_host()}
        msg.attach(MIMEText(body, 'plain'))
        import smtplib
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        text = msg.as_string()
        server.sendmail(fromaddr, toaddr, text)"""

        users = [jn_req.agent.user().user,]
        if users:
            site_name = project.agent.nick #get_site_name(request)
            notification.send_now(
                users,
                "work_new_account",
                {"name": jn_req.agent.name,
                 "username": jn_req.agent.nick,
                 "password": password,
                 "site_name": site_name,
                 "current_site": request.get_host(),
                 "context_agent": project.agent,
                 "request_host": request.get_host(),
                }
            )
        else:
            raise ValidationError("There are no users to send the work_new_account details? "+str(username))
    else:
        raise ValidationError("The notification service is not available?! ")

    next = request.POST.get("next")
    if not next:
        next = "project_feedback"

    messages.warning(request, _('The email with the user credentials was sended again.'))
    return redirect(next, agent_id=jn_req.project.agent.id, join_request_id=jn_req.id)



@login_required
def project_feedback(request, agent_id, join_request_id):
    user_agent = get_agent(request)
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    jn_req = get_object_or_404(JoinRequest, pk=join_request_id)
    if not hasattr(agent, 'project'):
        project = jn_req.project
    else:
        project = agent.project
    allowed = False
    if user_agent and jn_req and project == jn_req.project:
      if user_agent.is_staff() or user_agent in agent.managers():
        allowed = True
      elif jn_req.agent == request.user.agent.agent: #in user_agent.joinaproject_requests():
        allowed = True
    if not allowed:
        return render(request, 'work/no_permission.html')

    migrate_fdc_shares(request, jn_req)

    if jn_req.subscription_unit():
        jn_req.check_subscription_expiration()

    fobi_slug = project.fobi_slug
    fobi_headers = []
    fobi_keys = []

    out_text = ''

    if fobi_slug:
        form_entry = FormEntry.objects.get(slug=fobi_slug)
        #req = jn_req
        if jn_req.fobi_data and jn_req.fobi_data.pk:
            jn_req.entries = SavedFormDataEntry.objects.filter(pk=jn_req.fobi_data.pk)
            jn_req.entry = jn_req.entries[0]
            jn_req.form_headers = json.loads(jn_req.entry.form_data_headers)

            jn_req.data = json.loads(jn_req.entry.saved_data)
            jn_req.elem_typs = {}
            jn_req.elem_choi = {}
            for elem in jn_req.fobi_data.form_entry.formelemententry_set.all().order_by('position'):
                data = json.loads(elem.plugin_data)#, 'utf-8')
                nam = data.get('name')
                choi = data.get('choices')
                #pos = elem.position
                if nam:
                    if choi:
                        if elem.plugin_uid == "select_multiple":
                            jn_req.elem_typs[nam] = "select_multiple"
                        else:
                            jn_req.elem_typs[nam] = 'select'
                        opts = choi.split('\r\n')
                        obj = {}
                        for op in opts:
                            arr = op.split(', ')
                            #if jn_req.data[nam] == arr[1]:
                            #    #obj['selected'] = arr[1]
                            #    obj[str(arr[0])] = arr[1]
                            #else:
                            if len(arr) == 2 and arr[0] and arr[1]:
                                obj[str(arr[0])] = arr[1]
                            elif len(arr) == 1:
                                selected = ''
                                if len(jn_req.data[nam]):
                                    for val in jn_req.data[nam]:
                                        if val == op:
                                            selected = ":selected"
                                obj[str(op)] = op+' '+selected
                            else:
                                loger.warning("The choice option for join_request id "+str(jn_req.id)+" is not understood: "+str(op))
                            #import pdb; pdb.set_trace()
                        if len(obj):
                            jn_req.elem_choi[nam] = obj
                        else:
                            loger.warning("No obj to assign options ("+str(opts)+") to select name "+str(nam)+" for jn_req: "+str(jn_req.id))
                    else:
                        jn_req.elem_typs[nam] = elem.plugin_uid # 'text' 'textarea'
                        jn_req.elem_choi[nam] = ''

                    if not nam in jn_req.form_headers:
                        jn_req.form_headers[nam] = data.get('label')
                    fobi_headers.append(jn_req.form_headers[nam])
                    fobi_keys.append(nam)
                #import pdb; pdb.set_trace()

            #jn_req.tworows = two_dicts_to_string(jn_req.form_headers, jn_req.data, 'th', 'td')
            jn_req.items = list(jn_req.data.items())
            jn_req.items_data = []
            for key in fobi_keys:
                if not key in jn_req.form_headers:
                    jn_req.form_headers[key] = 'error'
                elif not key in jn_req.elem_typs:
                    jn_req.elem_typs[key] = 'error'
                elif not key in jn_req.elem_choi:
                    jn_req.elem_choi[key] = 'error'
                jn_req.items_data.append({"key": jn_req.form_headers[key], "val": jn_req.data.get(key), "ky": key, "typ": jn_req.elem_typs[key], "opts": jn_req.elem_choi[key]})

    auto_resource = ''
    if jn_req.agent and not jn_req.check_user_pass():
        auto_resource = create_user_accounts(request, jn_req.agent, jn_req.project)

    wallet_form = None
    oauth_form = None
    pay_form = None
    if 'multicurrency' in settings.INSTALLED_APPS and jn_req.project.agent.need_multicurrency():
        from multicurrency.forms import MulticurrencyAuthCreateForm, MulticurrencyAuthForm, PaySharesForm
        walletuser = jn_req.multiwallet_user()
        if jn_req.agent:
            other = None
            auth = None
            for oauth in jn_req.agent.multicurrencyauth_set.all():
                if oauth.auth_user == walletuser:
                    auth = oauth
                    break
                else:
                    other = oauth
            if other and not walletuser:
                # switch for real auth_user
                walletuser = other.auth_user
                auth = other
            if not walletuser:
                walletuser = jn_req.agent.nick
            if auth and jn_req.pending_shares():

                out_text, reqdata = auth.pay_shares_html(jn_req, request.user)
                if reqdata:
                    if 'url_w2w' in settings.MULTICURRENCY:
                        pay_form = PaySharesForm(initial=reqdata)
                    else:
                        out_text += " &nbsp; &nbsp; <div style='display: inline-block;'><input type='button' class='btn btn-primary' value='"+str(_("Pay the shares (coming soon)"))+"' disabled='disabled'> "
                        out_text += "<br>("+str(_("meanwhile pay from"))+" <a href='https://wallet.bankofthecommons.coop' target='_blank'>https://wallet.bankofthecommons.coop</a>)</div>"
            else:
                wallet_form = MulticurrencyAuthCreateForm(initial={
                    'username': walletuser,
                    'email': jn_req.agent.email,
                })
                oauth_form = MulticurrencyAuthForm(initial={
                    'loginname': walletuser,
                    'wallet_password': '',
                })

    if hasattr(agent, 'project') and agent.project.is_moderated() and not agent.email and user_agent in agent.managers():
        messages.error(request, _("Please provide an email for the \"{0}\" project to use as a remitent for the moderated joining process notifications!").format(agent.name))

    return render(request, "work/join_request_with_comments.html", {
        "help": get_help("project_feedback"),
        "jn_req": jn_req,
        "user_agent": user_agent,
        "agent": agent,
        "fobi_headers": fobi_headers,
        "auto_resource": auto_resource,
        "wallet_form": wallet_form,
        "oauth_form": oauth_form,
        "out_text": out_text,
        "pay_form": pay_form,
    })




def validate_nick(request):
    answer = True
    error = ""
    data = request.GET
    nick = data.get('nick')
    agent_id = data.get('agent_id')
    agent = None
    values = list(data.values())
    if not nick:
        nick = values[0]
    if nick:
        try:
            agent = EconomicAgent.objects.get(nick=nick)
            if agent_id and int(agent_id) and agent.id == int(agent_id):
                pass
            else:
                error = "Nickname already taken"
        except EconomicAgent.DoesNotExist:
            pass

        if not error:
            username = nick
            try:
                user = User.objects.get(username=username)
                if user.agent.agent.id == int(agent_id):
                    pass
                else:
                    error = "Username already taken" #+str(user.agent.agent)
            except User.DoesNotExist:
                pass
            if not error:
                val = validators.RegexValidator(r'^[\w.@+-]+$',
                                            _('Enter a valid username. '
                                                'This value may contain only letters, numbers '
                                               'and @/./+/-/_ characters.'), 'invalid')
                try:
                    if agent_id and int(agent_id) and agent:
                        if agent.id == int(agent_id):
                            pass
                        else:
                            error = val(username)
                    else:
                        error = val(username)
                except ValidationError:
                    error = "Error: May only contain letters, numbers, and @/./+/-/_ characters."

    if error:
        answer = error
    response = simplejson.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")


def validate_username(request):
    answer = True
    error = ""
    data = request.GET
    values = list(data.values())
    if values:
        username = values[0]
        try:
            user = User.objects.get(username=username)
            error = "Username already taken"
        except User.DoesNotExist:
            pass
        if not error:
            val = validators.RegexValidator(r'^[\w.@+-]+$',
                                        _('Enter a valid username. '
                                            'This value may contain only letters, numbers '
                                            'and @/./+/-/_ characters.'), 'invalid')
            try:
                error = val(username)
            except ValidationError:
                error = "Error: May only contain letters, numbers, and @/./+/-/_ characters."
    if error:
        answer = error
    response = simplejson.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")


def validate_name(request):
    answer = True
    error = ""
    form = ValidateNameForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        agid = data["agent_id"] or None
        name = data["name"] #values[0]
        surname = data["surname"] or None
        typeofuser = data["typeofuser"]
        if typeofuser == 'individual':
            if surname:
                ags = EconomicAgent.objects.filter(name__iexact=name+' '+surname)
                if not ags:
                    ags = EconomicAgent.objects.filter(name_en__iexact=name+' '+surname)
            else:
                ags = EconomicAgent.objects.filter(name__iexact=name)
                if not ags:
                    ags = EconomicAgent.objects.filter(name_en__iexact=name)
            if agid:
                ags = ags.exclude(id=int(agid))
            if ags:
                if surname:
                    error = "Name and Surname already known. Do you want to differentiate anyhow?"
                else:
                    error = "Name of individual already known. Do you want to differentiate anyhow?"
        else:
            ags = EconomicAgent.objects.filter(name__iexact=name)
            if not ags:
                ags = EconomicAgent.objects.filter(name_en__iexact=name)
            if agid:
                ags = ags.exclude(id=int(agid))
            if ags:
                error = "Name of collective already known. Do you want to differentiate anyhow?"
    #import pdb; pdb.set_trace()
    if error:
        answer = error
    response = simplejson.dumps(answer, ensure_ascii=False)
    return HttpResponse(response, content_type="text/json-comment-filtered")



@login_required
def connect_agent_to_join_request(request, agent_id, join_request_id):
    mbr_req = get_object_or_404(JoinRequest, pk=join_request_id)
    agent = get_object_or_404(EconomicAgent, pk=agent_id)
    project = mbr_req.project
    if project.joining_style == 'moderated':
      if request.user.agent.agent in project.agent.managers() or request.user.agent.agent is project.agent:
        if not mbr_req.agent:
            mbr_req.agent=agent
            mbr_req.state = "new"
            mbr_req.save()
            association_type = AgentAssociationType.objects.get(identifier="participant")
            aa = AgentAssociation(
                is_associate=agent,
                has_associate=project.agent,
                association_type=association_type,
                state="potential",
                )
            aa.save()
            return HttpResponseRedirect('/%s/%s/%s/'
                % ('work/agent', project.agent.id, 'join-requests'))
        elif not mbr_req.agent == agent:
            raise ValidationError("The join-request ("+str(mbr_req)+") is already linked to another agent: "+str(mbr_req.agent))
        else:
            raise ValidationError("The join-request ("+str(mbr_req)+") is already linked to this agent. Why redo? "+str(mbr_req.agent))
      else:
          raise ValidationError("Not enough permissions to connect agent to join-request!")
    else:
        raise ValidationError('Project with a non moderated joining style! Project:'+str(project)+' joinstyle:'+project.joining_style+' req.agent:'+str(mbr_req.agent))

    """project_agent = get_object_or_404(EconomicAgent, pk=agent_id)
    if request.method == "POST":
        agent_form = JoinAgentSelectionForm(data=request.POST)
        if agent_form.is_valid():
            data = agent_form.cleaned_data
            agent = data["created_agent"]
            mbr_req.agent=agent
            mbr_req.state = "new"
            mbr_req.save()
        else:
            raise ValidationError(agent_form.errors)"""

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', project_agent.id, 'join-requests'))


from six import text_type, PY3
from django.utils.encoding import force_text

def safe_text(text):
    """
    Safe text (encode).

    :return str:
    """
    if PY3:
        return force_text(text, encoding='utf-8')
    else:
        return force_text(text, encoding='utf-8').encode('utf-8')

def two_dicts_to_string(headers, data, html_element1='th', html_element2='td'):
    """
    Takes two dictionaries, assuming one contains a mapping keys to titles
    and another keys to data. Joins as string and returns wrapped into
    HTML "p" tag.
    """
    formatted_data = [
        (value, data.get(key, '')) for key, value in list(headers.items())
        ]
    return "".join(
        ["<tr><{0}>{1}</{2}><{3}>{4}</{5}></tr>".format(html_element1, safe_text(key), html_element1, html_element2,
                                      safe_text(value), html_element2)
         for key, value in formatted_data]
        )



'''
@login_required
def create_project_user_and_agent(request, agent_id):
    project_agent = get_object_or_404(EconomicAgent, id=agent_id)
    if not project_agent.managers: # or not request.user.agent.agent in project_agent.managers:
        return render(request, 'valueaccounting/no_permission.html')
    user_form = UserCreationForm(data=request.POST or None)
    agent_form = AgentForm(data=request.POST or None)
    agent_selection_form = AgentSelectionForm()
    if request.method == "POST":
        sa_id = request.POST.get("selected_agent")
        agent = None
        if sa_id:
            agent = EconomicAgent.objects.get(id=sa_id)
        if agent_form.is_valid():
            nick = request.POST.get("nick")
            description = request.POST.get("description")
            url = request.POST.get("url")
            address = request.POST.get("address")
            email = request.POST.get("email")
            agent_type_id = request.POST.get("agent_type")
            errors = False
            password1 = request.POST.get("password1")
            password2 = request.POST.get("password2")
            username = request.POST.get("username")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")  or ""
            if password1:
                if password1 != password2:
                    errors = True
                if not username:
                    errors = True
                user_form.is_valid()
            if not errors:
                if agent:
                    agent.description = description
                    agent.url = url
                    agent.address = address
                    if agent_type_id:
                        if agent.agent_type.id != agent_type_id:
                            agent_type = AgentType.objects.get(id=agent_type_id)
                            agent.agent_type = agent_type
                    if not agent.email:
                        agent.email = email
                else:
                    if nick and first_name:
                        try:
                            agent = EconomicAgent.objects.get(nick=nick)
                            errors = True
                        except EconomicAgent.DoesNotExist:
                            pass
                    else:
                        errors = True
                    if not errors:
                        name = " ".join([first_name, last_name])
                        agent_type = AgentType.objects.get(id=agent_type_id)
                        agent = EconomicAgent(
                            nick = nick,
                            name = name,
                            description = description,
                            url = url,
                            address = address,
                            agent_type = agent_type,
                        )
                if not errors:
                    if user_form.is_valid():
                        agent.created_by=request.user
                        agent.save()
                        user = user_form.save(commit=False)
                        user.first_name = request.POST.get("first_name")
                        user.last_name = request.POST.get("last_name")
                        user.email = request.POST.get("email")
                        user.save()
                        au = AgentUser(
                            agent = agent,
                            user = user)
                        au.save()
                        return HttpResponseRedirect('/%s/%s/'
                            % ('accounting/agent', agent.id))

    return render(request, "work/create_project_user_and_agent.html", {
        "user_form": user_form,
        "agent_form": agent_form,
        "agent_selection_form": agent_selection_form,
    })

'''


#   S K I L L S

@login_required
def new_skill_type(request, agent_id):
    agent = EconomicAgent.objects.get(id=agent_id)
    new_skill = request.POST.get("new_skill_type")
    if not new_skill:
        edit_skill = request.POST.get("edit_skill_type")
        if edit_skill:
          #raise ValidationError("Edit skill type? redirect")
          return edit_skill_type(request, agent.id)
        else:
          raise ValidationError("New skill type, invalid")

    Stype_form = NewSkillTypeForm(agent=agent, data=request.POST)
    if Stype_form.is_valid():
        #raise ValidationError("New resource type, valid")
        data = Stype_form.cleaned_data
        if hasattr(data["parent_type"], 'id'):
            parent_rt = Ocp_Skill_Type.objects.get(id=data["parent_type"].id)
            if parent_rt.id:
              out = None
              if hasattr(data["unit_type"], 'id'):
                gut = Ocp_Unit_Type.objects.get(id=data["unit_type"].id)
                out = gut.ocp_unit()
              new_rt = EconomicResourceType(
                name=data["name"],
                description=data["description"],
                unit=out,
                price_per_unit=data["price_per_unit"],
                substitutable=False, #data["substitutable"],
                context_agent=data["context_agent"],
                url=data["url"],
                photo_url=data["photo_url"],
                #parent=data["parent"],
                created_by=request.user,
                behavior="work",
                inventory_rule="never",
              )
              new_rt.save()

              # mptt: get_ancestors(ascending=False, include_self=False)
              ancs = parent_rt.get_ancestors(True, True)
              for an in ancs:
                #if an.clas != 'Artwork':
                  an = Ocp_Skill_Type.objects.get(id=an.id)
                  if an.resource_type:
                    new_rtfv = None
                    for fv in an.resource_type.facets.all():  # inherit first facetvalue from the parents
                      new_rtfv = ResourceTypeFacetValue(
                        resource_type=new_rt,
                        facet_value=fv.facet_value
                      )
                      new_rtfv.save()
                    if new_rtfv:
                      break
                  if an.facet_value:                          # if no fvs (didn't break) and the parent has one, relate that fv to the new skill
                    new_rtfv = ResourceTypeFacetValue(
                        resource_type=new_rt,
                        facet_value=an.facet_value
                    )
                    new_rtfv.save()
                    break

              new_oat = Ocp_Skill_Type(
                  name=data["name"],
                  verb=data["verb"],
                  gerund=data["gerund"],
                  description=data["description"],
                  resource_type=new_rt,
                  ocp_artwork_type=data["related_type"],
              )
              # mptt: insert_node(node, target, position='last-child', save=False)
              new_ski = Ocp_Skill_Type.objects.insert_node(new_oat, parent_rt, 'last-child', True)

              et_work = EventType.objects.get(name="Time Contribution")
              art = AgentResourceType(
                    agent=agent,
                    resource_type=new_rt,
                    event_type=et_work,
                    created_by=request.user,
              )
              art.save()

              suggestion = SkillSuggestion(
                  skill=data["name"],
                  suggested_by=request.user,
                  resource_type=new_rt,
                  state="accepted"
              )
              suggestion.save()
              try:
                suggester = request.user.agent.agent
              except:
                suggester = request.user
              if notification:
                  users = User.objects.filter(is_staff=True)
                  suggestions_url = get_url_starter(request) + "/accounting/skill-suggestions/"
                  site_name = get_site_name(request)
                  if users and site_name:
                      notification.send(
                        users,
                        "work_skill_suggestion",
                        {"skill": suggestion.skill,
                         "suggested_by": suggester.name,
                         "suggestions_url": suggestions_url,
                         "site_name": site_name,
                         "current_site": request.get_host(),
                        }
                      )
              #nav_form = ExchangeNavForm(agent=agent, data=None)
              #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
              #Stype_form = NewSkillTypeForm(agent=agent, data=None)

            else: # have no parent_type id
              pass
        else: # have no parent resource field
            pass
    else: # is not valid
        pass #raise ValidationError(Rtype_form.errors)

    next = request.POST.get("next")
    if next == "exchanges_all":
        return HttpResponseRedirect('/%s/%s/%s/'
            % ('work/agent', agent.id, 'exchanges'))
    elif next == "members_agent":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/agent', agent.id))
    else:
        raise ValidationError("Has no next page specified! "+str(next))


@login_required
def edit_skill_type(request, agent_id):
    edit_skill = request.POST.get("edit_skill_type")
    if not edit_skill:
        new_skill = request.POST.get("new_skill_type")
        if new_skill:
          raise ValidationError("New skill type? redirect")
        else:
          raise ValidationError("Edit skill type, invalid")

    agent = EconomicAgent.objects.get(id=agent_id)
    Stype_form = NewSkillTypeForm(agent=agent, data=request.POST)
    if Stype_form.is_valid():
        data = Stype_form.cleaned_data
        if hasattr(data["parent_type"], 'id'):
          parent_st = Ocp_Skill_Type.objects.get(id=data["parent_type"].id)
          if parent_st.id:
            out = None
            if hasattr(data["unit_type"], 'id'):
              gut = Ocp_Unit_Type.objects.get(id=data["unit_type"].id)
              out = gut.ocp_unit()
            edid = request.POST.get("edid")
            if edid == '':
              raise ValidationError("Missing id of the edited skill! (edid)")
            else:
              idar = edid.split('_')
              if idar[0] == "Sid":
                grt = Ocp_Skill_Type.objects.get(id=idar[1])
                grt.name = data["name"]
                grt.description = data["description"]
                grt.verb = data["verb"]
                grt.gerund = data["gerund"]

                moved = False
                if not grt.parent == parent_st:
                  # mptt: move_to(target, position='first-child')
                  grt.move_to(parent_st, 'last-child')
                  moved = True

                grt.ocp_artwork_type = data["related_type"]
                try:
                  grt.save()
                except:
                  raise ValidationError("The skill name already exists and they are unique")

                if not grt.resource_type:
                  #pass #raise ValidationError("There's no resource type! create it?")
                  new_rt = EconomicResourceType(
                    name=data["name"],
                    description=data["description"],
                    unit=out,
                    price_per_unit=data["price_per_unit"],
                    substitutable=False, #data["substitutable"],
                    context_agent=data["context_agent"],
                    url=data["url"],
                    photo_url=data["photo_url"],
                    created_by=request.user,
                    behavior="work",
                    inventory_rule="never",
                  )
                  new_rt.save()
                  grt.resource_type = new_rt
                  grt.save()

                  # mptt: get_ancestors(ascending=False, include_self=False)
                  ancs = parent_st.get_ancestors(True, True)   # note: they're General.Job
                  for an in ancs:
                    #if an.clas != 'Artwork':
                      an = Ocp_Skill_Type.objects.get(id=an.id)
                      if an.resource_type:
                        new_rtfv = None
                        for fv in an.resource_type.facets.all():
                          new_rtfv = ResourceTypeFacetValue(
                            resource_type=new_rt,
                            facet_value=fv.facet_value
                          )
                          new_rtfv.save()
                        if new_rtfv:
                          break
                      if an.facet_value:
                        new_rtfv = ResourceTypeFacetValue(
                            resource_type=new_rt,
                            facet_value=an.facet_value
                        )
                        new_rtfv.save()
                        break

                else:
                  rt = grt.resource_type;
                  rt.name = data["name"]
                  rt.description = data["description"]
                  rt.unit = out
                  rt.price_per_unit = data["price_per_unit"]
                  rt.substitutable = False #data["substitutable"]
                  rt.context_agent = data["context_agent"]
                  rt.url = data["url"]
                  rt.photo_url = data["photo_url"]
                  #rt.parent = data["parent"]
                  rt.edited_by = request.user
                  if moved:
                    old_rtfvs = ResourceTypeFacetValue.objects.filter(resource_type=rt)
                    for rtfv in old_rtfvs:
                      rtfv.delete()
                    # mptt: get_ancestors(ascending=False, include_self=False)
                    ancs = parent_st.get_ancestors(True, True)   # note: they're General.Job
                    for an in ancs:
                      #if an.clas != 'Artwork':
                        an = Ocp_Skill_Type.objects.get(id=an.id)
                        if an.resource_type:
                          new_rtfv = None
                          for fv in an.resource_type.facets.all():
                            new_rtfv = ResourceTypeFacetValue(
                              resource_type=rt,
                              facet_value=fv.facet_value
                            )
                            new_rtfv.save()
                          if new_rtfv:
                            break
                        if an.facet_value:
                          new_rtfv = ResourceTypeFacetValue(
                              resource_type=rt,
                              facet_value=an.facet_value
                          )
                          new_rtfv.save()
                          break
                  rt.save()

                #nav_form = ExchangeNavForm(agent=agent, data=None)
                #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
                #Stype_form = NewSkillTypeForm(agent=agent, data=None)

              else: # is not Sid
                pass
          else: # have no parent_type id
            pass
        else: # have no parent resource field
          pass

    next = request.POST.get("next")
    if next == "exchanges_all":
        return HttpResponseRedirect('/%s/%s/%s/'
            % ('work/agent', agent.id, 'exchanges'))
    elif next == "members_agent":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/agent', agent.id))
    else:
        raise ValidationError("Has no next page specified! "+str(next))





#   R E S O U R C E   T Y P E S

@login_required
def new_resource_type(request, agent_id):
    agent = EconomicAgent.objects.get(id=agent_id)
    new_rt = request.POST.get("new_resource_type")
    if not new_rt:
        edit_rt = request.POST.get("edit_resource_type")
        if edit_rt:
          #raise ValidationError("Edit skill type? redirect")
          return edit_resource_type(request, agent.id)
        else:
          raise ValidationError("New resource type, invalid")

    Rtype_form = NewResourceTypeForm(agent=agent, data=request.POST)
    if Rtype_form.is_valid():
        data = Rtype_form.cleaned_data
        if hasattr(data["resource_type"], 'id'):
            parent_rt = Ocp_Artwork_Type.objects.get(id=data["resource_type"].id)
            if parent_rt.id:
                out = None
                if hasattr(data["unit_type"], 'id'):
                    gut = Ocp_Unit_Type.objects.get(id=data["unit_type"].id)
                    out = gut.ocp_unit()
                if hasattr(data, "substitutable"):
                    substi = data["substitutable"]
                else:
                    substi = False
                new_rt = EconomicResourceType(
                    name=data["name"],
                    description=data["description"],
                    unit=out,
                    price_per_unit=data["price_per_unit"],
                    substitutable=substi,
                    context_agent=data["context_agent"],
                    url=data["url"],
                    photo_url=data["photo_url"],
                    parent=data["parent"],
                    created_by=request.user,
                )
                #try:
                new_rt.save()
                #except:
                #  raise ValidationError('Cannot save new resource type:'+str(new_oat)+' Parent:'+str(parent_rt))

                # mptt: get_ancestors(ascending=False, include_self=False)
                ancs = parent_rt.get_ancestors(True, True)
                for an in ancs:
                    if an.clas != 'Artwork':
                        an = Ocp_Artwork_Type.objects.get(id=an.id)
                        if an.resource_type:
                          new_rtfv = None
                          for fv in an.resource_type.facets.all():
                            new_rtfv = ResourceTypeFacetValue(
                              resource_type=new_rt,
                              facet_value=fv.facet_value
                            )
                            new_rtfv.save()
                          if new_rtfv:
                            break
                        if an.facet_value:
                          new_rtfv = ResourceTypeFacetValue(
                              resource_type=new_rt,
                              facet_value=an.facet_value
                          )
                          new_rtfv.save()
                          break

                rel_material = None
                rel_nonmaterial = None
                if hasattr(data["related_type"], 'id'):
                    rrt = Ocp_Artwork_Type.objects.get(id=data["related_type"].id)
                    # mptt: get_ancestors(ascending=False, include_self=False)
                    rrt_ancs = rrt.get_ancestors(False, True)
                    for an in rrt_ancs: # see if is child of material or non-material
                        if an.clas == 'Material':
                          #try:
                          #  mat = Material_Type.objects.get(id=rrt.id)
                          #except:
                          #  mat = Ocp_Artwork_Type.objects.update_to_general('Material_Type', rrt.id)
                          rel_material = rrt #mat
                          break
                        if an.clas == 'Nonmaterial':
                          #try:
                          #  non = Nonmaterial_Type.objects.get(id=rrt.id)
                          #except:
                          #  non = Ocp_Artwork_Type.objects.update_to_general('Nonmaterial_Type', rrt.id)
                          rel_nonmaterial = rrt #non
                          break

                new_oat = Ocp_Artwork_Type(
                    name=data["name"],
                    description=data["description"],
                    resource_type=new_rt,
                    rel_material_type=rel_material,
                    rel_nonmaterial_type=rel_nonmaterial,
                )
                # mptt: insert_node(node, target, position='last-child', save=False)
                try:
                    new_res = Ocp_Artwork_Type.objects.insert_node(new_oat, parent_rt, 'last-child', True)
                except:
                    raise ValidationError('Cannot insert node:'+str(new_oat)+' Parent:'+str(parent_rt))

                #nav_form = ExchangeNavForm(agent=agent, data=None)
                #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
                #Stype_form = NewSkillTypeForm(agent=agent, data=None)

            else: # have no parent_type id
                pass
        else: # have no parent resource field
            pass
    else:
        pass #raise ValidationError(Rtype_form.errors)

    next = request.POST.get("next")
    if next == "exchanges_all":
        return HttpResponseRedirect('/%s/%s/%s/'
            % ('work/agent', agent.id, 'exchanges'))
    elif next == "members_agent":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/agent', agent.id))
    else:
        raise ValidationError("Has no next page specified! "+str(next))



@login_required
def edit_resource_type(request, agent_id):
    edit_rt = request.POST.get("edit_resource_type")
    if not edit_rt:
        new_rt = request.POST.get("new_resource_type")
        if new_rt:
          raise ValidationError("New resource type? redirect")
        else:
          raise ValidationError("Edit resource type, invalid")

    agent = EconomicAgent.objects.get(id=agent_id)
    Rtype_form = NewResourceTypeForm(agent=agent, data=request.POST)
    if Rtype_form.is_valid():
        data = Rtype_form.cleaned_data
        if hasattr(data["resource_type"], 'id'):
            parent_rt = Ocp_Artwork_Type.objects.get(id=data["resource_type"].id)
            if parent_rt.id:
                out = None
                if hasattr(data["unit_type"], 'id'):
                    gut = Ocp_Unit_Type.objects.get(id=data["unit_type"].id)
                    out = gut.ocp_unit()
                edid = request.POST.get("edid")
                if edid == '':
                    raise ValidationError("Missing edid!")
                else:
                    #raise ValidationError("Lets edit "+edid)
                    idar = edid.split('_')
                    if idar[0] == "Rid":
                        grt = Ocp_Artwork_Type.objects.get(id=idar[1])
                        grt.name = data["name"]
                        grt.description = data["description"]
                        moved = False
                        if not grt.parent == parent_rt:
                          # mptt: move_to(target, position='first-child')
                          grt.move_to(parent_rt, 'last-child')
                          moved = True

                        rel_material = None
                        rel_nonmaterial = None
                        if hasattr(data["related_type"], 'id'):
                          rrt = Ocp_Artwork_Type.objects.get(id=data["related_type"].id)
                          # mptt: get_ancestors(ascending=False, include_self=False)
                          rrt_ancs = rrt.get_ancestors(False, True)
                          for an in rrt_ancs: # see if is child of material or non-material
                            if an.clas == 'Material':
                              #try:
                              #  mat = Material_Type.objects.get(id=rrt.id)
                              #except:
                              #  mat = Ocp_Artwork_Type.objects.update_to_general('Material_Type', rrt.id)
                              rel_material = rrt #mat
                              break
                            if an.clas == 'Nonmaterial':
                              #try:
                              #  non = Nonmaterial_Type.objects.get(id=rrt.id)
                              #except:
                              #  non = Ocp_Artwork_Type.objects.update_to_general('Nonmaterial_Type', rrt.id)
                              rel_nonmaterial = rrt #non
                              break
                        grt.rel_material_type = rel_material
                        grt.rel_nonmaterial_type = rel_nonmaterial

                        grt.save()

                        if not grt.resource_type:
                          #pass #raise ValidationError("There's no resource type! create it?")
                          if hasattr(data, "substitutable"):
                            substi = data["substitutable"]
                          else:
                            substi = False
                          new_rt = EconomicResourceType(
                            name=data["name"],
                            description=data["description"],
                            unit=out,
                            price_per_unit=data["price_per_unit"],
                            substitutable=substi,
                            context_agent=data["context_agent"],
                            url=data["url"],
                            photo_url=data["photo_url"],
                            parent=data["parent"],
                            created_by=request.user,
                          )
                          new_rt.save()
                          grt.resource_type = new_rt
                          grt.save()

                          # mptt: get_ancestors(ascending=False, include_self=False)
                          ancs = parent_rt.get_ancestors(True, True)
                          for an in ancs:
                            if an.clas != 'Artwork':
                              an = Ocp_Artwork_Type.objects.get(id=an.id)
                              if an.resource_type:
                                new_rtfv = None
                                for fv in an.resource_type.facets.all():
                                  new_rtfv = ResourceTypeFacetValue(
                                    resource_type=new_rt,
                                    facet_value=fv.facet_value
                                  )
                                  new_rtfv.save()
                                if new_rtfv:
                                  break
                              if an.facet_value:
                                new_rtfv = ResourceTypeFacetValue(
                                    resource_type=new_rt,
                                    facet_value=an.facet_value
                                )
                                new_rtfv.save()
                                break

                        else:
                          rt = grt.resource_type;
                          rt.name = data["name"]
                          rt.description = data["description"]
                          rt.unit = out
                          rt.price_per_unit = data["price_per_unit"]
                          rt.substitutable = data["substitutable"]
                          rt.context_agent = data["context_agent"]
                          rt.url = data["url"]
                          rt.photo_url = data["photo_url"]
                          rt.parent = data["parent"]
                          rt.edited_by = request.user
                          if moved:
                            old_rtfvs = ResourceTypeFacetValue.objects.filter(resource_type=rt)
                            for rtfv in old_rtfvs:
                              rtfv.delete()
                            # mptt: get_ancestors(ascending=False, include_self=False)
                            ancs = parent_rt.get_ancestors(True, True)
                            for an in ancs:
                              if an.clas != 'Artwork':
                                an = Ocp_Artwork_Type.objects.get(id=an.id)
                                if an.resource_type:
                                  new_rtfv = None
                                  for fv in an.resource_type.facets.all():
                                    new_rtfv = ResourceTypeFacetValue(
                                      resource_type=rt,
                                      facet_value=fv.facet_value
                                    )
                                    new_rtfv.save()
                                  if new_rtfv:
                                    break
                                if an.facet_value:
                                  new_rtfv = ResourceTypeFacetValue(
                                      resource_type=rt,
                                      facet_value=an.facet_value
                                  )
                                  new_rtfv.save()
                                  break
                          rt.save()

                        mkfv = request.POST.get("facetvalue")
                        if mkfv == 'on' and not moved:
                            #raise ValidationError("Insert FacetValue: "+str(grt.resource_type.facets.first().facet_value.facet))
                            new_fv, created = FacetValue.objects.get_or_create(
                                facet=grt.resource_type.facets.first().facet_value.facet,
                                value=grt.name
                            )
                            grt.facet_value = new_fv
                            grt.save()
                            rtfvs = grt.resource_type.facets.all()
                            if rtfvs:
                                for rtfv in rtfvs:
                                    if rtfv.facet_value == grt.resource_type.facets.first().facet_value:
                                        rtfv.facet_value = new_fv
                                        rtfv.save()
                                        break
                            else:
                                new_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
                                    resource_type=grt.resource_type,
                                    facet_value=new_fv
                                )
                            desc = grt.get_descendants() # true: include self
                            for des in desc:
                                ort = Ocp_Artwork_Type.objects.get(id=des.id)
                                if ort.resource_type:
                                    rtfvs = ort.resource_type.facets.all()
                                    if rtfvs:
                                        for rtfv in rtfvs:
                                            if rtfv.facet_value != new_fv: #parent_rt.resource_type.facets.first().facet_value:
                                                rtfv.facet_value = new_fv
                                                rtfv.save()
                                                break
                                            else:
                                                pass #raise ValidationError("the first fv is already the new fv: "+str(new_fv))
                                    else:
                                        new_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
                                            resource_type=ort.resource_type,
                                            facet_value=new_fv
                                        )

                        #nav_form = ExchangeNavForm(agent=agent, data=None)
                        #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
                        #Stype_form = NewSkillTypeForm(agent=agent, data=None)

                    else: # is not Rid
                        pass


            else: # have no parent_type id
                pass
        else: # have no parent resource field
            pass
    else: # form invalid
        raise ValidationError("form errors: "+str(Rtype_form.errors))

    next = request.POST.get("next")
    if next == "exchanges_all":
        return exchanges_all(request, agent.id) # HttpResponseRedirect('/%s/%s/%s/'
            # % ('work/agent', agent.id, 'exchanges'))
    elif next == "members_agent":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/agent', agent.id))
    else:
        raise ValidationError("Has no next page specified! "+str(next))







#    E X C H A N G E S   A L L

@login_required
def exchanges_all(request, agent_id): #all types of exchanges for one context agent
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    today = datetime.date.today()
    end =  today
    start = today - datetime.timedelta(days=365)
    init = {"start_date": start, "end_date": end}
    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
    et_give = EventType.objects.get(name="Give")
    et_receive = EventType.objects.get(name="Receive")
    context_ids = [c.id for c in agent.related_all_agents()]
    if not agent.id in context_ids:
        context_ids.append(agent.id)
    ets = ExchangeType.objects.filter(context_agent__id__in=context_ids) #all()
    event_ids = ""
    select_all = True
    selected_values = "all"

    #nav_form = ExchangeNavForm(agent=agent, data=request.POST or None)

    gen_ext = Ocp_Record_Type.objects.get(clas='ocp_exchange')
    usecases = Ocp_Record_Type.objects.filter(parent__id=gen_ext.id).exclude( Q(exchange_type__isnull=False), Q(exchange_type__context_agent__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids) ) #UseCase.objects.filter(identifier__icontains='_xfer')
    #outypes = Ocp_Record_Type.objects.filter( Q(exchange_type__isnull=False, exchange_type__context_agent__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids) )
    #outchilds_ids = []
    #for tp in outypes:
    #  desc = tp.get_descendants(True)
    #  outchilds_ids.extend([ds.id for ds in desc])
    #exchange_types = Ocp_Record_Type.objects.filter(lft__gt=gen_ext.lft, rght__lt=gen_ext.rght, tree_id=gen_ext.tree_id).exclude(id__in=outchilds_ids) #.exclude(Q(exchange_type__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids))
    #usecase_ids = [uc.id for uc in usecases]

    ext_form = ContextExchangeTypeForm(agent=agent, data=request.POST or None)
    #unit_types = Ocp_Unit_Type.objects.all()

    Rtype_form = NewResourceTypeForm(agent=agent, data=request.POST or None)
    Stype_form = NewSkillTypeForm(agent=agent, data=request.POST or None)

    exchanges_by_type = Exchange.objects.exchanges_by_type(agent)

    #import pdb; pdb.set_trace()
    if not request.method == "POST":

        exchanges = Exchange.objects.exchanges_by_date_and_context(start, end, agent, exchanges_by_type)
        if exchanges_by_type:
            while not exchanges:
                start = start - datetime.timedelta(days=365)
                exchanges = Exchange.objects.exchanges_by_date_and_context(start, end, agent, exchanges_by_type)
                if exchanges:
                    init = {"start_date": start, "end_date": end}
                    dt_selection_form = DateSelectionForm(initial=init, data=request.POST or None)
                    break

        nav_form = ExchangeNavForm(agent=agent, exchanges=exchanges_by_type, data=request.POST or None)

    if request.method == "POST":

        dt_selection_form = DateSelectionForm(data=request.POST)
        if dt_selection_form.is_valid():
            start = dt_selection_form.cleaned_data["start_date"]
            end = dt_selection_form.cleaned_data["end_date"]

        exchanges = Exchange.objects.exchanges_by_date_and_context(start, end, agent, exchanges_by_type) #filter(context_agent=agent)

        nav_form = ExchangeNavForm(agent=agent, exchanges=exchanges_by_type, data=request.POST)

        if "categories" in request.POST:
            selected_values = request.POST["categories"]
            if selected_values:
                sv = selected_values.split(",")
                vals = []
                for v in sv:
                    vals.append(v.strip())
                if vals[0] == "all":
                    select_all = True
                else:
                    select_all = False
                    #transfers_included = []
                    exchanges_included = []
                    #events_included = []
                    for ex in exchanges:
                        if str(ex.exchange_type.id) in vals:
                            exchanges_included.append(ex)
                    exchanges = exchanges_included

                #nav_form = ExchangeNavForm(agent=agent, data=None)
                #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
                #Stype_form = NewSkillTypeForm(agent=agent, data=None)
        else:
          #exchanges = Exchange.objects.exchanges_by_date_and_context(start, end, agent) #Exchange.objects.filter(context_agent=agent) #.none()
          selected_values = "all"


        new_exchange = request.POST.get("new_exchange")
        if new_exchange:
            if nav_form.is_valid():
                data = nav_form.cleaned_data
                if hasattr(data["used_exchange_type"], 'id'):
                  old_ext = ExchangeType.objects.get(id=data["used_exchange_type"].id)
                  if old_ext.id:
                    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                      % ('work/agent', agent.id, 'exchange-logging-work', old_ext.id, 0))

                if hasattr(data["exchange_type"], 'id'):
                  gen_ext = Ocp_Record_Type.objects.get(id=data["exchange_type"].id)
                  ext = gen_ext.exchange_type
                  if ext:
                    gen_rt = None
                    gen_sk = None

                    if hasattr(data["resource_type"], 'id'): # we are creating a new exchange type and ext is the parent?
                      gen_rt = Ocp_Artwork_Type.objects.get(id=data["resource_type"].id)

                    if hasattr(data["skill_type"], 'id'):
                      gen_sk = Ocp_Skill_Type.objects.get(id=data["skill_type"].id)


                    if gen_rt and hasattr(gen_ext, 'ocp_artwork_type') and gen_ext.ocp_artwork_type and gen_ext.ocp_artwork_type == gen_rt: # we have the related RT in the ET! do nothing.
                      return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                              % ('work/agent', agent.id, 'exchange-logging-work', ext.id, 0))
                    if gen_sk and hasattr(gen_ext, 'ocp_skill_type') and gen_ext.ocp_skill_type and gen_ext.ocp_skill_type == gen_sk: # we have the related RT in the ET! do nothing.
                      return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                              % ('work/agent', agent.id, 'exchange-logging-work', ext.id, 0))

                    name = None
                    narr = gen_ext.name.split(' ')
                    if len(narr) > 0:
                      name = narr[0] # get only first word of general record type ?
                    if gen_sk:
                      if gen_sk.gerund:
                        name += ' '+gen_sk.gerund.title()
                      else:
                        name += ' '+gen_sk.name
                    if gen_rt:
                      name += ' '+gen_rt.name


                    agnt = None
                    if gen_rt and hasattr(gen_rt.resource_type, 'context_agent'):
                      agnt = gen_rt.resource_type.context_agent
                    elif gen_sk and hasattr(gen_sk.resource_type, 'context_agent'):
                      agnt = gen_sk.resource_type.context_agent
                    elif ext.context_agent:
                      agnt = ext.context_agent
                    else:
                      agnt = agent

                    uc = ext.use_case
                    if name and uc:
                        new_exts = ExchangeType.objects.filter(name__iexact=name)
                        if not new_exts:
                            new_exts = ExchangeType.objects.filter(name__iexact=ext.name)
                        if not new_exts:
                            new_exts = ExchangeType.objects.filter(name__icontains=ext.name)
                        if new_exts:
                            if len(new_exts) > 1:
                                raise ValidationError("More than one ExchangeType with same name: "+str(new_exts))
                            new_ext = new_exts[0]
                            if new_ext.context_agent and not new_ext.context_agent == agnt:# if the ext exists and the context_agent is not the
                                if agnt.parent():                                          # same, set the parent agent or the new agent as
                                    new_ext.context_agent = agnt.parent()                  # a new context. TODO: check if the old context has
                                else:                                                      # the same parent (so the ext keeps showing for them)
                                    new_ext.context_agent = agnt

                                new_ext.edited_by = request.user
                                new_ext.save() # TODO check if the new_ext is reached by the agent related contexts

                            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                                 % ('work/agent', agent.id, 'exchange-logging-work', new_ext.id, 0))
                        else:
                            #import pdb; pdb.set_trace()
                            if name in ext.name:
                                name = ext.name

                            new_ext, created = ExchangeType.objects.get_or_create(
                              name=name,
                              #use_case=uc,
                              #created_by=request.user,
                              #created_date=datetime.date.today(),
                              #context_agent=agnt
                            )
                            if created:
                                print("- created ExchangeType: "+str(new_ext))
                            new_ext.use_case = uc
                            new_ext.context_agent = agnt
                            new_ext.save() # here we get an id

                        new_recs = Ocp_Record_Type.objects.filter(name=name)
                        if not new_recs:
                            new_recs = Ocp_Record_Type.objects.filter(name_en=name)
                        if new_recs:
                            new_rec = new_recs[0]
                        else:
                            new_rec = Ocp_Record_Type(gen_ext)
                            new_rec.pk = None
                            new_rec.id = None
                            new_rec.name = name
                            print("- created Ocp_Record_Type: "+name)
                            # mptt: insert_node(node, target, position='last-child', save=False)
                            new_rec = Ocp_Record_Type.objects.insert_node(new_rec, gen_ext, 'last-child', True)
                        new_rec.name = name
                        new_rec.exchange_type = new_ext
                        new_rec.ocpRecordType_ocp_artwork_type = gen_rt
                        new_rec.ocp_skill_type = gen_sk
                        new_rec.save()

                        inherited = False
                        for tr in ext.transfer_types.all():
                            if tr.inherit_types == True:
                                inherited = True
                        if inherited: # any of the transfer_types has inherit_types?
                            for tr in ext.transfer_types.all():
                                new_tr = TransferType.objects.get(pk=tr.pk)
                                new_tr.pk = None
                                new_tr.id = None
                                new_tr.exchange_type = new_ext
                                new_tr.created_by = request.user
                                new_tr.created_date = datetime.date.today()
                                narr = tr.name.split(' ')
                                nam = ' '.join(narr[:-1]) # substitute the last word in transfer name for the resource type name
                                new_tr.name = nam
                                if gen_sk:
                                    new_tr.name += ' - '+gen_sk.name
                                if gen_rt:
                                    new_tr.name += ' - '+gen_rt.name

                                new_tr.save()

                                if tr.inherit_types == True: # provisional inheriting of the facet_value assigned in ocp_artwork_type tree
                                    inherited = True
                                    # its just-in-case as a fail saver (the resource types will be retrieved via exchange_type)
                                    # mptt: get_ancestors(ascending=False, include_self=False)
                                    if gen_rt:
                                        parids = [p.id for p in gen_rt.get_ancestors(True, True)]
                                        # careful! these are general.Type and the upper level
                                        pars = gen_rt.get_ancestors(True)             # 'Artwork' is not in Artwork_Type nor Ocp_Artwork_Type
                                        for par in pars:
                                            if par.clas != 'Artwork':
                                              pr = Ocp_Artwork_Type.objects.get(id=par.id)
                                              if pr.facet_value:
                                                  ttfv, created = TransferTypeFacetValue.objects.get_or_create(
                                                      transfer_type=new_tr,
                                                      facet_value=pr.facet_value,
                                                      # defaults={},
                                                  )
                                                  if ttfv:
                                                      new_tr.facet_values.add(ttfv)
                                                      break
                                    if gen_sk:
                                        parids = [p.id for p in gen_sk.get_ancestors(True, True)] # careful! these are general.Job
                                        pars = gen_sk.get_ancestors(True)
                                        for par in pars:
                                            pr = Ocp_Skill_Type.objects.get(id=par.id)
                                            if pr.facet_value:
                                                ttfv, created = TransferTypeFacetValue.objects.get_or_create(
                                                    transfer_type=new_tr,
                                                    facet_value=pr.facet_value,
                                                    # defaults={},
                                                )
                                                if ttfv:
                                                    new_tr.facet_values.add(ttfv)
                                                    break
                                else:
                                    old_fvs = tr.facet_values.all()
                                    new_tr.facet_values = old_fvs

                            # end for tr in ext.transfer_types.all()
                            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                                  % ('work/agent', agent.id, 'exchange-logging-work', new_ext.id, 0))

                        else: # not inherited, rise error
                            raise ValidationError("No transfer inheriting types in this exchange type! "+ext.name)

                    else: # end if name and uc:
                        raise ValidationError("Bad new name ("+name+") or no use-case in the parent exchange type! "+ext.name)

                    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                        % ('work/agent', agent.id, 'exchange-logging-work', ext.id, 0))

                  else: # endif ext
                    # the parent ocp record type still not have an ocp exchange type, create it? TODO
                    pass

                  #return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                  #  % ('work/agent', agent.id, 'exchange-logging-work', ext.id, gen_rt.id)) # ¿ use the exchange id for a resource id ?

                else: # endif hasattr(data["exchange_type"], 'id'):
                  #nav_form.add_error('exchange_type', _("No exchange type selected"))
                  pass #raise ValidationError("No exchange type selected")

            else: # nav_form is not valid
              pass #raise ValidationError(nav_form.errors)

        # there's no new_exchange, is it a new resource type?
        """new_resource_type = request.POST.get("new_resource_type")
        edit_resource_type = request.POST.get("edit_resource_type")
        """

        # there's no new_resource_type = request.POST.get("new_resource_type")
        """new_skill_type = request.POST.get("new_skill_type")
        edit_skill_type = request.POST.get("edit_skill_type")
        """


        edit_exchange_type = request.POST.get("edit_exchange_type") # TODO the detail about transfertypes
        if edit_exchange_type:
            if ext_form.is_valid():
                data = ext_form.cleaned_data
                etid = data["edid"].split('_')[1]
                gen_ext = Ocp_Record_Type.objects.get(id=etid)
                new_parent = Ocp_Record_Type.objects.get(id=data["parent_type"].id)

                ext = gen_ext.exchange_type
                if ext:
                  ext.name = data["name"]
                  ext.context_agent = data['context_agent']
                else:
                  raise ValidationError("Editing Exchange Type! Without internal exchange_type TODO: "+gen_ext.name)
                gen_ext.name = data["name"]
                gen_ext.ocp_artwork_type = data['resource_type']
                gen_ext.ocp_skill_type = data['skill_type']
                moved = False
                if not gen_ext.parent.id == new_parent.id:
                  moved = True
                  raise ValidationError("Editing Exchange Type! Changed Parent TODO: "+data['parent_type'].name+' ext:'+str(new_parent)+' moved:'+str(moved))
                else:
                  gen_ext.save()
                  if ext:
                    ext.save()

                #nav_form = ExchangeNavForm(agent=agent, data=None)
                #Rtype_form = NewResourceTypeForm(agent=agent, data=None)
                #Stype_form = NewSkillTypeForm(agent=agent, data=None)
                #raise ValidationError("Editing Exchange Type! "+data['parent_type'].name+' ext:'+str(new_parent)+' moved:'+str(moved))


    else: # No POST
        pass #exchanges = Exchange.objects.exchanges_by_date_and_context(start, end, agent)

    exchange_types = Ocp_Record_Type.objects.filter(exchange_type__isnull=False, exchange_type__id__in=set([ex.exchange_type.id for ex in exchanges_by_type])).order_by('pk', 'tree_id', 'lft').distinct()

    total_transfers = [{'unit':u,'name':'','clas':'','abbr':'','income':0,'incommit':0,'outgo':0,'outcommit':0, 'balance':0,'balnote':0,'debug':''} for u in agent.used_units_ids(exchanges_by_type)]
    total_rec_transfers = 0
    comma = ""

    fairunit = None
    eachunit = None

    '''for x in exchanges:
        x.list_name = x.show_name(agent)
        flip = False
        if not str(x) == x.list_name:
            flip = True

        x.transfer_list = list(x.transfers.all())
        for transfer in x.transfer_list:
            transfer.list_name = transfer.show_name(agent, flip) # "2nd arg is 'forced'
    '''

    shr_pros = []
    if hasattr(agent, 'project') and agent.project:
        shr_pros.append(agent.project)


    for x in exchanges_by_type:

        x.transfer_list = list(x.transfers.all())

        for transfer in x.transfer_list:

            if transfer.quantity():
              uq = transfer.unit_of_quantity()
              rt = transfer.resource_type()
              uv = transfer.unit_of_value()
              if uq and uq.name == "Each" and uv: # and not uq and
                if rt.is_account():
                    print(",, Switch uq each from uv:"+str(uv)+" in ex:"+str(x.id)+" tx:"+str(transfer.id)+" rt:"+str(rt)+" acc:"+str(rt.is_account()))
                    uq = uv
              if not uq and rt:
                print(",, Switch missing uq from rt.unit:"+str(rt.unit)+" in ex:"+str(x.id)+" tx:"+str(transfer.id)+" rt:"+str(rt)+" acc:"+str(rt.is_account()))
                uq = rt.unit

              toag = transfer.to_agent()
              fromag = transfer.from_agent()
              if hasattr(toag, 'project') and toag.project:
                if not toag.project in shr_pros:
                    shr_pros.append(toag.project)
              if hasattr(fromag, 'project') and fromag.project:
                if not fromag.project in shr_pros:
                    shr_pros.append(fromag.project)

              if uq:
                #print(". uq:"+str(uq)+" is_curr:"+str(uq.is_currency()))
                if not hasattr(uq, 'gen_unit'):
                  raise ValidationError("The unit has not gen_unit! "+str(uq))
                for to in total_transfers:
                  #print("ToTr: "+str(to))
                  if to['unit'] == uq.gen_unit.unit_type.id:
                    #print(". . found ut in unit_of_quantity: "+str(uq.gen_unit.unit_type)+" toag:"+str(toag)+" fromag:"+str(fromag))
                    nom = uq.gen_unit.unit_type.name

                    to['name'] = nom
                    to['clas'] = uq.gen_unit.unit_type.clas
                    to['abbr'] = uq.symbol if uq.symbol else uq.abbrev

                    if transfer.transfer_type.is_incoming(x, agent): #is_reciprocal:
                      sign = '<'
                      if transfer.events.all():
                        if uv:
                            to['income'] = (to['income']*1) + (transfer.value()*1)
                        else:
                            to['income'] = (to['income']*1) + (transfer.quantity()*1)
                      for com in transfer.commitments.all_give():
                        if com.unfilled_quantity() > 0:
                          if uv:
                            to['incommit'] = (to['incommit']*1) + (transfer.value()*1)
                          else:
                            to['incommit'] = (to['incommit']*1) + (com.unfilled_quantity()*1)
                      #to['debug'] += str(x.id)+':'+str([ev.event_type.name+':'+str(ev.quantity)+':'+ev.resource_type.name+':'+ev.resource_type.ocp_artwork_type.name for ev in x.transfer_give_events()])+sign+' - '
                    else:
                      sign = '>'
                      if transfer.events.all():
                        if uv:
                            to['outgo'] = (to['outgo']*1) + (transfer.actual_value()*1)
                        else:
                            to['outgo'] = (to['outgo']*1) + (transfer.actual_quantity()*1)
                      for com in transfer.commitments.all_give():
                        if com.unfilled_quantity() > 0:
                          if uv:
                            to['outcommit'] = (to['outcommit']*1) + (transfer.value()*1)
                          else:
                            to['outcommit'] = (to['outcommit']*1) + (com.unfilled_quantity()*1)
                      #to['debug'] += str(x.id)+':'+str([str(ev.event_type.name)+':'+str(ev.quantity)+':'+ev.resource_type.name+':'+ev.resource_type.ocp_artwork_type.name for ev in x.transfer_receive_events()])+sign+' - '

                    if uq.gen_unit.unit_type.clas == 'each':
                      eachunit = to['unit']
                      #print("... found each in unit_of_quantity! ex:"+str(x.id)+" tx:"+str(transfer.id)+" rt:"+str(rt))
                      #loger.info("... found each in unit_of_quantity! ex:"+str(x.id)+" tx:"+str(transfer.id)+" rt:"+str(rt))
                      rt.cur = False
                      if hasattr(rt, 'ocp_artwork_type') and rt.ocp_artwork_type:
                        rt.cur = rt.ocp_artwork_type.is_currency()

                        if rt.cur: # and rt.ocp_artwork_type.general_unit_type:
                          print("--- found rt.is_currency, add to totals. "+str(rt)+" ex:"+str(x.id)+" tx:"+str(transfer.id))
                          if rt.ocp_artwork_type.general_unit_type:
                            to['debug'] += str(transfer.quantity())+'-'+str(rt.ocp_artwork_type.general_unit_type.name)+sign+'(ex:'+str(x.id)+') - '
                          else:
                            to['debug'] += str(transfer.quantity())+'-'+str(rt.ocp_artwork_type)+sign+'-MISSING UNIT! '
                          for ttr in total_transfers:
                            if ttr['unit'] == rt.ocp_artwork_type.general_unit_type.id:
                              nom = rt.ocp_artwork_type.general_unit_type.name
                              print("---- found other unit to add currency rt. nom:"+str(nom)+" tx:"+str(transfer.id)+" tx.qty:"+str(transfer.quantity())+" evs:"+str(len(transfer.events.all())))
                              ttr['name'] = nom
                              ttr['clas'] = rt.ocp_artwork_type.general_unit_type.clas

                              if transfer.events.all():
                                if sign == '<':
                                  ttr['income'] = (ttr['income']*1) + (transfer.quantity()*1)
                                if sign == '>':
                                  ttr['outgo'] = (ttr['outgo']*1) + (transfer.quantity()*1)
                                #ttr['balance'] = (ttr['income']*1) - (ttr['outgo']*1)
                              for com in transfer.commitments.all_give():
                                if com.unfilled_quantity() > 0:
                                  if sign == '<':
                                    ttr['incommit'] = (ttr['incommit']*1) + (com.unfilled_quantity()*1)
                                  if sign == '>':
                                    ttr['outcommit'] = (ttr['outcommit']*1) + (com.unfilled_quantity()*1)
                              break
                            else:
                                pass #print("---- pass u:"+str(ttr['name'])+" <> "+str(rt.ocp_artwork_type.general_unit_type))
                        else:
                            #to['debug'] += '::'+str(rt)+'!!'+sign+'::'
                            #print("--- found rt with ocp_artwork_type but is not currency, skip "+str(rt))
                            pass #raise ValidationError("Not rt.cur or rt.ocp_artwork_type.general_unit_type! rt: "+str(rt))

                      elif rt:
                        print("--- found rt without ocp_artwork_type, skip "+str(rt))
                        to['debug'] += ':'+str(rt)+'!!'+sign+':'

                      #to['debug'] += str(x.transfer_give_events())+':'
                    elif uq.gen_unit.unit_type.clas == 'faircoin':
                        fairunit = uq.gen_unit.unit_type.id
                        #to['debug'] += str(x.transfer_give_events())+':'

                    elif uq.gen_unit.unit_type.clas == 'euro':
                      pass #to['balance'] = (to['income']*1) - (to['outgo']*1)

                      #to['debug'] += str([ev.event_type.name+':'+str(ev.quantity)+':'+ev.resource_type.name for ev in transfer.events.all()])+sign+'(ex:'+str(x.id)+') - '
                    else:

                      if not uq.is_currency():
                            to['debug'] += 'U:'+str(uq.gen_unit.unit_type.name)+sign

              else: # not uq
                pass #raise ValidationError("the transfer has not unit of quantity! "+str(uq))
            else: # not quantity
                pass

            for event in transfer.events.all():
                event_ids = event_ids + comma + str(event.id)
                comma = ","

        # end for transfer in x.transfer_list

        for event in x.events.all():
            event_ids = event_ids + comma + str(event.id)
            comma = ","
        #todo: get sort to work

    # end for x in exchanges_by_type

    facc = agent.faircoin_resource()
    wal = faircoin_utils.is_connected()

    for to in total_transfers:

        if fairunit: # and agent.faircoin_resource(): # or agent.need_faircoins():
            if to['unit'] == fairunit:
                if facc:
                  to['balnote'] = (to['income']*1) - (to['outgo']*1)
                  if wal:
                    if facc.is_wallet_address():
                        bal = facc.digital_currency_balance()
                        try:
                            to['balance'] = '{0:.4f}'.format(float(bal))
                        except ValueError:
                            to['balance'] = bal
                    else:
                        to['balance'] = "<span class='error'>unknown</span>"
                  else:
                    to['balance'] = "<span class='error'>no wallet</span>"
                else: # not fairaccount like botc, count fairs like everything else
                    to['balance'] = (to['income']*1) - (to['outgo']*1) #'!!'
            else:
                to['balance'] = (to['income']*1) - (to['outgo']*1)
        else:
            to['balance'] = (to['income']*1) - (to['outgo']*1)
        #if to['unit']:
        #    unit = Unit.objects.get(id=to['unit'])
        #    print(":: unit:"+str(unit))

        if not isinstance(to['balance'], str):
            to['balance'] = remove_exponent(to['balance'])
        if not isinstance(to['balnote'], str):
            to['balnote'] = remove_exponent(to['balnote'])
        to['income'] = remove_exponent(to['income'])
        to['incommit'] = remove_exponent(to['incommit'])
        if to['incommit']:
            if to['abbr'] in settings.CRYPTOS:
                to['incommit'] = ('\u2248\u00a0')+str(to['incommit'])
            else:
                to['incommit'] = '+'+str(to['incommit'])
        to['outgo'] = remove_exponent(to['outgo'])
        to['outcommit'] = remove_exponent(to['outcommit'])
        if to['outcommit']:
            if to['abbr'] in settings.CRYPTOS:
                to['outcommit'] = ('\u2248\u00a0')+str(to['outcommit'])
            else:
                to['outcommit'] = '-'+str(to['outcommit'])

        # change shares names for shorter version
        if to['name'] and shr_pros:
            nom = to['name']
            nar = nom.split(' ')
            #print("shr_pros: "+str(shr_pros))
            if len(nar) > 1:
                for pro in shr_pros:
                    comp = pro.compact_name()
                    abbr = pro.abbrev_name()
                    if comp and abbr:
                        nar[:] = [abbr if n == comp else n for n in nar]
                        nom2 = ' '.join(nar)
                        #print(".... comp:"+str(comp)+" abbr:"+str(abbr)+" nom2:"+str(nom2))
                        if not nom == nom2:
                            to['name'] = nom2
                            print("- Changed unit name for the abbrev form of project't name: "+str(nom2))
                            break
    if eachunit:
        total_transfers = [to for to in total_transfers if not to['unit'] == eachunit]


    print("......... start slots_with_detail ..........")
    loger.info("......... start slots_with_detail ..........")
    for x in exchanges:
        x.slots = x.slots_with_detail(agent)
    print("......... end slots_with_detail ..........")
    loger.info("......... end slots_with_detail ..........")

    return render(request, "work/exchanges_all.html", {
        "exchanges": exchanges,
        "exchanges_by_type": exchanges_by_type,
        "dt_selection_form": dt_selection_form,
        "total_transfers": total_transfers,
        "total_rec_transfers": total_rec_transfers,
        "select_all": select_all,
        "selected_values": selected_values,
        "ets": ets,
        "event_ids": event_ids,
        "context_agent": agent,
        "nav_form": nav_form,
        "usecases": usecases,
        "Etype_tree": Ocp_Record_Type.objects.filter(lft__gt=gen_ext.lft, rght__lt=gen_ext.rght, tree_id=gen_ext.tree_id).exclude( Q(exchange_type__isnull=False), Q(exchange_type__context_agent__isnull=False), ~Q(exchange_type__context_agent__id__in=context_ids) ),
        "Rtype_tree": Ocp_Artwork_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False),  ~Q(resource_type__context_agent__id__in=context_ids) ),
        "Stype_tree": Ocp_Skill_Type.objects.all().exclude( Q(resource_type__isnull=False), Q(resource_type__context_agent__isnull=False), ~Q(resource_type__context_agent__id__in=context_ids) ),
        "Rtype_form": Rtype_form,
        "Stype_form": Stype_form,
        "Utype_tree": Ocp_Unit_Type.objects.filter(id__in=agent.used_units_ids(exchanges_by_type)), #all(),
        #"unit_types": unit_types,
        "ext_form": ext_form,
    })


@login_required
def delete_exchange(request, exchange_id):
    #todo: Lynn needs lots of work
    if request.method == "POST":
        exchange = get_object_or_404(Exchange, pk=exchange_id)
        if exchange.is_deletable:
            exchange.delete()
        next = request.POST.get("next")
        """if next == "exchanges":
            return HttpResponseRedirect('/%s/'
                % ('accounting/exchanges'))
        if next == "demand_transfers":
            return HttpResponseRedirect('/%s/'
                % ('accounting/sales-and-distributions')) #obsolete
        if next == "material_contributions":
            return HttpResponseRedirect('/%s/'
                % ('accounting/material-contributions')) #obsolete
        if next == "distributions":
            return HttpResponseRedirect('/%s/'
                % ('accounting/distributions'))"""
        if next == "exchanges-all":
            return HttpResponseRedirect('/%s/%s/%s/'
                % ('work/agent', exchange.context_agent.id, 'exchanges'))
       #todo: needs a fall-through if next is none of the above




#    E X C H A N G E   L O G G I N G

@login_required
def exchange_logging_work(request, context_agent_id, exchange_type_id=None, exchange_id=None):
    context_agent = get_object_or_404(EconomicAgent, pk=context_agent_id)
    agent = get_agent(request)
    logger = False
    add_work_form = None
    if agent:
        if request.user.is_superuser:
            logger = True

    if exchange_type_id != "0": #new exchange
        if agent:
            exchange_type = get_object_or_404(ExchangeType, id=exchange_type_id)
            use_case = exchange_type.use_case

            exchange_form = ExchangeContextForm()
            #if request.method == "POST":
            #    exchange_form = ExchangeContextForm(data=request.POST)
            #    if exchange_form.is_valid():
            exchange = exchange_form.save(commit=False)
            exchange.context_agent = context_agent
            exchange.use_case = use_case
            exchange.exchange_type = exchange_type
            exchange.created_by = request.user
            exchange.start_date = datetime.date.today()
            exchange.save()

            return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                  % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

        else:
            raise ValidationError("System Error: No agent, not allowed to create exchange.")

    elif exchange_id != "0": #existing exchange
        exchange = get_object_or_404(Exchange, id=exchange_id)

        if not exchange.context_agent == context_agent and not context_agent in exchange.related_agents():
            raise ValidationError("NOT VALID URL! please "+str(request.user.agent.agent)+" don't touch the urls manually...")

        if request.method == "POST":
            exchange_form = ExchangeContextForm(instance=exchange, data=request.POST)
            if exchange_form.is_valid():
                exchange = exchange_form.save()
                #return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
                #    % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))

        exchange_type = exchange.exchange_type
        use_case = exchange_type.use_case
        exchange_form = ExchangeContextForm(instance=exchange)

        slots = []
        total_t = 0
        total_t_unit = None
        total_rect = 0
        total_rect_unit = None
        total_agents = []
        work_events = exchange.work_events()
        slots = exchange.slots_with_detail(context_agent)
        if slots:
            mem = slots[0]
        for slot in slots:
            if not slot == mem and slot.name == mem.name:
                print(("Duplicate TT (slot), delete? "+str(slot)+" fvs:"+str(slot.facet_values.all())))
                loger.info("Duplicate TT (slot), delete? "+str(slot)+" fvs:"+str(slot.facet_values.all()))
                if slot.is_deletable() and not slot.facet_values.all():
                    print(("DELETE? empty slot: "+str(slot)))
                    loger.info("DELETE? empty slot: "+str(slot))
                    #slot.delete()
            #tos = slot.agents_to()
            for to in slot.agents_to:
                if not to in total_agents:
                    total_agents.append(to)
            #fros = slot.agents_from()
            for fr in slot.agents_from:
                if not fr in total_agents:
                    total_agents.append(fr)

            if slot.is_income == True: #is_incoming(exchange, context_agent) == True:
                #pass
                total_rect = total_rect + slot.total
                #print(".. change is_income to True? "+str(slot.is_income))
                #slot.is_income = True
                total_rect_unit = slot.total_unit
            elif slot.is_income == False: #is_incoming(exchange, context_agent) == False:
                total_t = total_t + slot.total
                #print(".. change is_income to False? "+str(slot.is_income))
                #slot.is_income = False
                total_t_unit = slot.total_unit
                #pass
            elif slot.is_reciprocal:
                total_rect = total_rect + slot.total
                print(".. change reci is_income to True? "+str(slot.is_income))
                #slot.is_income = True
                total_rect_unit = slot.total_unit
            else:
                total_t = total_t + slot.total
                print(".. change reci is_income to False? "+str(slot.is_income))
                #slot.is_income = False
                total_t_unit = slot.total_unit

        if agent:
            if request.user == exchange.created_by or context_agent in agent.managed_projects() or context_agent == agent:
                pass #logger = True
            if hasattr(exchange, 'join_request') and exchange.join_request: #hasattr(exchange, 'join_request')
                #if exchange.join_request.agent == agent:
                logger = False
                if exchange.join_request.subscription_unit():
                    exchange.join_request.check_subscription_expiration()

            for event in work_events:
                event.changeform = WorkEventContextAgentForm(
                    context_agent=context_agent,
                    instance=event,
                    prefix=str(event.id))
            work_init = {
                "from_agent": agent,
                "event_date": datetime.date.today()
            }
            add_work_form = WorkEventContextAgentForm(initial=work_init, context_agent=context_agent)

            fliped = []
            for slot in slots:
                slot.flip = False
                slot.list_name = slot.show_name(context_agent)
                if not slot.list_name == slot.name:
                    slot.flip = True
                    fliped.append(slot)
            if len(fliped) < len(slots) and len(fliped) > 0:
                for slot in slots:
                    if not slot in fliped:
                        slot.list_name = slot.show_name(context_agent, True) # 2nd arg is 'forced' (no need commitments or events)
                        slot.flip = True
                        #if slot.is_income:
                        #    print("- Switch slot.is_income to False because is Fliped ?")
                        #    #slot.is_income = False
                        #else:
                        #    print("- Switch slot.is_income to True because is Fliped ?")
                        #    #slot.is_income = True
                        fliped.append(slot)

            for slot in slots:

                ta_init = slot.default_to_agent
                fa_init = slot.default_from_agent
                if not ta_init:
                    ta_init = agent
                if not fa_init:
                    fa_init = agent

                #if not slot.flip:
                    #fa_init = ta_init
                    #ta_init = slot.default_from_agent
                    #slot.default_from_agent = fa_init
                    #slot.default_to_agent = ta_init

                #    if slot.inherit_types:
                        #pass
                #        if slot.is_income:
                #            pass #slot.is_income = False
                #        else:
                #            print("-Switch slot.is_income to True because inherit_types ?")
                #            pass #slot.is_income = True

                xfer_init = {
                    "from_agent": fa_init,
                    "to_agent": ta_init,
                    "event_date": datetime.date.today()
                }
                slot.add_xfer_form = ContextTransferForm(initial=xfer_init, prefix="ATR" + str(slot.id), context_agent=context_agent, transfer_type=slot)
                slot.create_role_formset = resource_role_context_agent_formset(prefix=str(slot.id))
                ctx_qs = context_agent.related_all_agents_queryset()
                for form in slot.create_role_formset.forms:
                    form.fields["agent"].queryset = ctx_qs

                commit_init = {
                    "from_agent": fa_init,
                    "to_agent": ta_init,
                    "commitment_date": datetime.date.today(),
                    "due_date": exchange.start_date,
                }
                slot.add_commit_form = ContextTransferCommitmentForm(initial=commit_init, prefix="ACM" + str(slot.id), context_agent=context_agent, transfer_type=slot)

                slot.add_ext_agent = ContextExternalAgent() #initial=None, prefix="AGN"+str(slot.id))#, context_agent=context_agent)




    else:
        raise ValidationError("System Error: No exchange or use case.")

    return render(request, "work/exchange_logging_work.html", {
        "use_case": use_case,
        "exchange": exchange,
        "exchange_type": exchange_type,
        "exchange_form": exchange_form,
        "agent": agent,
        "context_agent": context_agent,
        "logger": logger,
        "slots": slots,
        "work_events": work_events,
        "add_work_form": add_work_form,
        "total_t": total_t,
        "total_t_unit": total_t_unit,
        "total_rect": total_rect,
        "total_rect_unit": total_rect_unit,
        "total_agents": total_agents,
        "help": get_help("exchange"),
        #"add_type": add_new_type_mkp(),
    })


def add_new_type_mkp(): # not used now
    out = "" #"<div class='add-new-type'><p>"
    out += str(_("If you don't find a type that suits, choose a subcategory and click:"))
    #out += "</p><a href='#' class='btn-mini'>New Resource Type</a>"
    #out += "</div>"
    return out


@login_required
def add_transfer_external_agent(request, commitment_id, context_agent_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    context_agent = get_object_or_404(EconomicAgent, pk=context_agent_id)
    exchange = commitment.exchange
    user_agent = get_agent(request)
    if not user_agent:
        return render(request, 'work/no_permission.html')
    if request.method == "POST":
        form = AgentCreateForm(request.POST)
        if form.is_valid():
            new_agent = form.save(commit=False)
            new_agent.created_by=request.user
            new_agent.save()
            if not commitment.to_agent and commitment.from_agent == context_agent:
                commitment.to_agent = new_agent
                commitment.save()
            elif not commitment.from_agent and commitment.to_agent == context_agent:
                commitment.from_agent = new_agent
                commitment.save()
            # TODO relate the context_agent


    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



# functions copied from valuenetwork.views because were only running by staff

@login_required
def add_transfer(request, exchange_id, transfer_type_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    transfer_type = get_object_or_404(TransferType, pk=transfer_type_id)
    if request.method == "POST":
        exchange_type = exchange.exchange_type
        context_agent = exchange.context_agent

        form = ContextTransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ATR" + str(transfer_type.id))

        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            res = None
            res_from = None
            et2 = None
            res_identifier = None
            if qty:
                et_give = EventType.objects.get(name="Give")
                et_receive = EventType.objects.get(name="Receive")
                event_date = data["event_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]
                if hasattr(exchange, 'join_request') and exchange.join_request:
                    if transfer_type.is_currency:
                        to_agent = exchange.join_request.project.agent
                        from_agent = exchange.join_request.agent
                    elif transfer_type.is_share():
                        to_agent = exchange.join_request.agent
                        from_agent = exchange.join_request.project.agent

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                #if not transfer_type.can_create_resource:
                res = data["resource"]
                if transfer_type.is_currency:
                    res_from = data["from_resource"]
                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None
                if transfer_type.is_contribution:
                    is_contribution = data["is_contribution"]
                else:
                    is_contribution = False
                if transfer_type.is_to_distribute:
                    is_to_distribute = data["is_to_distribute"]
                else:
                    is_to_distribute = False
                event_ref = data["event_reference"]
                if transfer_type.can_create_resource:
                    #res = data["resource"]
                    if not res:
                        res_identifier = data["identifier"]
                        if res_identifier:
                            res = EconomicResource(
                                identifier=res_identifier,
                                url=data["url"],
                                photo_url=data["photo_url"],
                                current_location=data["current_location"],
                                notes=data["notes"],
                                access_rules=data["access_rules"],
                                resource_type=rt,
                                exchange_stage=exchange_type,
                                quantity=0,
                                created_by=request.user,
                                )
                if exchange.exchange_type.use_case == UseCase.objects.get(identifier="supply_xfer"):
                    if transfer_type.is_reciprocal:
                        if res:
                            res.quantity -= qty
                        et = et_give
                    else:
                        if res:
                            res.quantity += qty
                        et = et_receive
                elif exchange.exchange_type.use_case == UseCase.objects.get(identifier="demand_xfer"):
                    if transfer_type.is_reciprocal:
                        if res:
                            res.quantity += qty
                        et = et_receive
                    else:
                        if res:
                            res.quantity -= qty
                        et = et_give
                else: #internal xfer use case
                    if transfer_type.is_reciprocal:
                        et = et_receive
                        et2 = et_give
                    else:
                        et = et_give
                        et2 = et_receive
                    if transfer_type.is_currency:
                        if res != res_from:
                            if res:
                                res.quantity += qty
                            if res_from:
                                res_from.quantity -= qty
                if res:
                    res.save()
                if res_from:
                    res_from.save()
                if res_identifier: #new resource
                    create_role_formset = resource_role_context_agent_formset(prefix=str(transfer_type.id), data=request.POST)
                    for form_rra in create_role_formset.forms:
                        if form_rra.is_valid():
                            data_rra = form_rra.cleaned_data
                            if data_rra:
                                data_rra = form_rra.cleaned_data
                                role = data_rra["role"]
                                agent = data_rra["agent"]
                                if role and agent:
                                    rra = AgentResourceRole()
                                    rra.agent = agent
                                    rra.role = role
                                    rra.resource = res
                                    rra.is_contact = data_rra["is_contact"]
                                    rra.save()

                xfer_name = transfer_type.name
                if transfer_type.is_reciprocal:
                    xfer_name = xfer_name + " from " + from_agent.nick
                else:
                    xfer_name = xfer_name + " of " + rt.name
                xfer = Transfer(
                    name=xfer_name,
                    transfer_type = transfer_type,
                    exchange = exchange,
                    context_agent = context_agent,
                    transfer_date = event_date,
                    notes = description,
                    created_by = request.user
                    )
                xfer.save()
                e_is_to_distribute = is_to_distribute
                if et == et_give:
                    e_is_to_distribute = False
                e_is_contribution = is_contribution
                if et == et_receive and et2:
                    e_is_contribution = False
                if et == et_give and res_from:
                    event_res = res_from
                else:
                    event_res = res
                event = EconomicEvent(
                    event_type = et,
                    event_date=event_date,
                    resource_type=rt,
                    resource=event_res,
                    transfer=xfer,
                    exchange_stage=exchange.exchange_type,
                    context_agent = context_agent,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value=unit_of_value,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    is_contribution = e_is_contribution,
                    is_to_distribute = e_is_to_distribute,
                    event_reference=event_ref,
                    created_by = request.user,
                    )
                event.save()
                if et2:
                    e2_is_to_distribute = is_to_distribute
                    if et2 == et_give:
                        e2_is_to_distribute = False
                    e2_is_contribution = is_contribution
                    if et2 == et_receive:
                        e2_is_contribution = False
                    if et2 == et_give and res_from:
                        event_res = res_from
                    else:
                        event_res = res
                    event2 = EconomicEvent(
                        event_type = et2,
                        event_date=event_date,
                        resource_type=rt,
                        resource=event_res,
                        transfer=xfer,
                        exchange_stage=exchange.exchange_type,
                        context_agent = context_agent,
                        quantity=qty,
                        unit_of_quantity = rt.unit,
                        value=value,
                        unit_of_value=unit_of_value,
                        from_agent = from_agent,
                        to_agent = to_agent,
                        is_contribution = e2_is_contribution,
                        is_to_distribute = e2_is_to_distribute,
                        event_reference=event_ref,
                        created_by = request.user,
                    )
                    event2.save()

    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def add_transfer_commitment_work(request, exchange_id, transfer_type_id):
    transfer_type = get_object_or_404(TransferType, pk=transfer_type_id)
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    if request.method == "POST":
        exchange_type = exchange.exchange_type
        context_agent = exchange.context_agent
        form = ContextTransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix="ACM" + str(transfer_type.id))
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            et2 = None
            if qty:
                commitment_date = data["commitment_date"]
                due_date = data["due_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                if hasattr(exchange, 'join_request') and exchange.join_request:
                    if transfer_type.is_currency:
                        to_agent = exchange.join_request.project.agent
                        from_agent = exchange.join_request.agent
                    elif transfer_type.is_share():
                        to_agent = exchange.join_request.agent
                        from_agent = exchange.join_request.project.agent

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None

                xfer_name = transfer_type.name
                if transfer_type.is_reciprocal:
                    if from_agent:
                      xfer_name = xfer_name + " from " + from_agent.nick
                    else:
                      xfer_name = xfer_name + " from ?"
                else:
                    xfer_name = xfer_name + " of " + rt.name
                xfer = Transfer(
                    name=xfer_name,
                    transfer_type = transfer_type,
                    exchange = exchange,
                    context_agent = context_agent,
                    transfer_date = commitment_date,
                    created_by = request.user
                    )
                xfer.save()

                if exchange.exchange_type.use_case == UseCase.objects.get(identifier="supply_xfer"):
                    if not transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Give")
                    else:
                        et = EventType.objects.get(name="Receive")
                elif exchange.exchange_type.use_case == UseCase.objects.get(identifier="demand_xfer"):
                    if transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Receive")
                    else:
                        et = EventType.objects.get(name="Give")
                else: #internal xfer use case
                    if transfer_type.is_reciprocal:
                        et = EventType.objects.get(name="Receive")
                        et2 = EventType.objects.get(name="Give")
                    else:
                        et = EventType.objects.get(name="Give")
                        et2 = EventType.objects.get(name="Receive")
                commit = Commitment(
                    event_type = et,
                    commitment_date=commitment_date,
                    due_date=due_date,
                    resource_type=rt,
                    exchange = exchange,
                    transfer=xfer,
                    exchange_stage=exchange.exchange_type,
                    context_agent = context_agent,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value=unit_of_value,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    description=description,
                    created_by = request.user,
                    )
                commit.save()
                if et2:
                    commit2 = Commitment(
                        event_type = et2,
                        commitment_date=commitment_date,
                        due_date=due_date,
                        resource_type=rt,
                        exchange = exchange,
                        transfer=xfer,
                        exchange_stage=exchange.exchange_type,
                        context_agent = context_agent,
                        quantity=qty,
                        unit_of_quantity = rt.unit,
                        value=value,
                        unit_of_value=unit_of_value,
                        from_agent = from_agent,
                        to_agent = to_agent,
                        created_by = request.user,
                    )
                    commit2.save()

        else:
          # form not valid
          pass
    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def change_transfer_commitments_work(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    if request.method == "POST":
        commits = transfer.commitments.all()
        transfer_type = transfer.transfer_type
        exchange = transfer.exchange
        context_agent = transfer.context_agent
        form = ContextTransferCommitmentForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "C") # "ACM" + str(transfer_type.id) )
        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            if qty:
                commitment_date = data["commitment_date"]
                due_date = data["due_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                    if data["from_agent"]:
                        from_agent = data["from_agent"]
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                    if data["to_agent"]:
                        to_agent = data["to_agent"]
                else:
                    to_agent = data["to_agent"]

                if hasattr(exchange, 'join_request') and exchange.join_request:
                    if transfer_type.is_currency:
                        to_agent = exchange.join_request.project.agent
                        from_agent = exchange.join_request.agent
                    elif transfer_type.is_share():
                        to_agent = exchange.join_request.agent
                        from_agent = exchange.join_request.project.agent

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)


                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None

                for commit in commits:
                    commit.resource_type = rt
                    commit.from_agent = from_agent
                    commit.to_agent = to_agent
                    commit.commitment_date = commitment_date
                    commit.due_date = due_date
                    commit.quantity=qty
                    commit.unit_of_quantity = rt.unit
                    commit.value=value
                    commit.unit_of_value = unit_of_value
                    commit.description=description
                    commit.changed_by = request.user
                    commit.save()

    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def delete_transfer_commitments(request, transfer_id, commitment_id=None):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    exchange = transfer.exchange
    agid = transfer.context_agent.id
    if request.method == "POST":
      if commitment_id:
        comm = get_object_or_404(Commitment, pk=commitment_id)
        if comm and comm.is_deletable():
            comm.delete()
      else:
        for commit in transfer.commitments.all():
            if commit.is_deletable():
                commit.delete()
        if transfer.is_deletable():
             transfer.delete()
    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', agid, 'exchange-logging-work', 0, exchange.id))



@login_required
def transfer_from_commitment(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    transfer_type = transfer.transfer_type
    exchange = transfer.exchange
    context_agent = transfer.context_agent
    if request.method == "POST":
        form = ContextTransferForm(data=request.POST, transfer_type=transfer.transfer_type, context_agent=transfer.context_agent, posting=True, prefix=transfer.form_prefix())
        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            event_date = data["event_date"]
            if transfer_type.give_agent_is_context:
                from_agent = context_agent
                if data["from_agent"]:
                    from_agent = data["from_agent"]
            else:
                from_agent = data["from_agent"]
            if transfer_type.receive_agent_is_context:
                to_agent = context_agent
                if data["to_agent"]:
                    to_agent = data["to_agent"]
            else:
                to_agent = data["to_agent"]

            if hasattr(exchange, 'join_request') and exchange.join_request:
                if transfer_type.is_currency:
                    to_agent = exchange.join_request.project.agent
                    from_agent = exchange.join_request.agent
                elif transfer_type.is_share():
                    to_agent = exchange.join_request.agent
                    from_agent = exchange.join_request.project.agent

            rt = data["resource_type"]
            if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                gen_rt = data["ocp_resource_type"]
                rt = get_rt_from_ocp_rt(gen_rt)

            #if not transfer_type.can_create_resource:
            res = data["resource"]
            description = data["description"]
            if transfer_type.is_currency:
                value = qty
                unit_of_value = rt.unit
                res_from = data["from_resource"]
            else:
                res_from = None
                value = data["value"]
                if value:
                    unit_of_value = data["unit_of_value"]
                else:
                    unit_of_value = None
            if transfer_type.is_contribution:
                is_contribution = data["is_contribution"]
            else:
                is_contribution = False
            event_ref = data["event_reference"]
            #res = None
            if transfer_type.can_create_resource:
                #res = data["resource"]
                if not res:
                    res_identifier = data["identifier"]
                    if res_identifier: #new resource
                        res = EconomicResource(
                            identifier=res_identifier,
                            url=data["url"],
                            photo_url=data["photo_url"],
                            current_location=data["current_location"],
                            notes=data["notes"],
                            access_rules=data["access_rules"],
                            resource_type=rt,
                            exchange_stage=exchange.exchange_type,
                            quantity=0,
                            created_by=request.user,
                            )
                        res.save()
                        create_role_formset = transfer.create_role_formset(data=request.POST)
                        for form_rra in create_role_formset.forms:
                            if form_rra.is_valid():
                                data_rra = form_rra.cleaned_data
                                if data_rra:
                                    role = data_rra["role"]
                                    agent = data_rra["agent"]
                                    if role and agent:
                                        rra = AgentResourceRole()
                                        rra.agent = agent
                                        rra.role = role
                                        rra.resource = res
                                        rra.is_contact = data_rra["is_contact"]
                                        rra.save()
            for commit in transfer.commitments.all():
                if commit.event_type == et_give and res_from:
                    event_res = res_from
                else:
                    event_res = res
                event = EconomicEvent(
                    event_type=commit.event_type,
                    resource_type = rt,
                    resource = event_res,
                    from_agent = from_agent,
                    to_agent = to_agent,
                    exchange_stage=transfer.exchange.exchange_type,
                    transfer=transfer,
                    commitment=commit,
                    context_agent = transfer.context_agent,
                    event_date = event_date,
                    quantity=qty,
                    unit_of_quantity = rt.unit,
                    value=value,
                    unit_of_value = unit_of_value,
                    description=description,
                    event_reference=event_ref,
                    created_by = request.user,
                )
                event.save()
                if event_res:
                    if event.event_type == et_give:
                        event_res.quantity -= event.quantity
                    else:
                        event_res.quantity += event.quantity
                    event_res.save()
                commit.finished = True
                commit.save()

    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', transfer.context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def change_transfer_events_work(request, transfer_id, context_agent_id=None):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    if context_agent_id:
        context_agent = get_object_or_404(EconomicAgent, pk=context_agent_id)
    if request.method == "POST":
        events = transfer.events.all()
        transfer_type = transfer.transfer_type
        exchange = transfer.exchange
        events = transfer.events.all()
        if not context_agent:
          if transfer.context_agent:
            context_agent = transfer.context_agent
          elif exchange.context_agent:
            context_agent = exchange.context_agent
          elif events:
            if events[0].to_agent == request.user.agent.agent:
              context_agent = request.user.agent.agent
            elif events[0].from_agent == request.user.agent.agent:
              context_agent = request.user.agent.agent
            #else:
              #from_resource, to_resource = transfer.give_and_receive_resources()
              #if transfer_type.is_reciprocal:
              #  context_agent = events[0].to_agent
              #else:
              #  context_agent = events[0].from_agent
        form = ContextTransferForm(data=request.POST, transfer_type=transfer_type, context_agent=context_agent, posting=True, prefix=transfer.form_prefix() + "E")

        if form.is_valid():
            data = form.cleaned_data
            et_give = EventType.objects.get(name="Give")
            et_receive = EventType.objects.get(name="Receive")
            qty = data["quantity"]
            if qty:
                event_date = data["event_date"]
                if transfer_type.give_agent_is_context:
                    from_agent = context_agent
                else:
                    from_agent = data["from_agent"]
                if transfer_type.receive_agent_is_context:
                    to_agent = context_agent
                else:
                    to_agent = data["to_agent"]

                if hasattr(exchange, 'join_request') and exchange.join_request:
                    if transfer_type.is_currency:
                        to_agent = exchange.join_request.project.agent
                        from_agent = exchange.join_request.agent
                    elif transfer_type.is_share():
                        to_agent = exchange.join_request.agent
                        from_agent = exchange.join_request.project.agent

                rt = data["resource_type"]
                if data["ocp_resource_type"]: #next and next == "exchange-work": # bumbum
                    gen_rt = data["ocp_resource_type"]
                    rt = get_rt_from_ocp_rt(gen_rt)

                res = data["resource"]
                res_from = None
                if transfer_type.is_currency:
                    res_from = data["from_resource"]
                description = data["description"]
                if transfer_type.is_currency:
                    value = qty
                    unit_of_value = rt.unit
                else:
                    value = data["value"]
                    if value:
                        unit_of_value = data["unit_of_value"]
                    else:
                        unit_of_value = None
                if transfer_type.is_contribution:
                    is_contribution = data["is_contribution"]
                else:
                    is_contribution = False
                event_ref = data["event_reference"]

                #old_res = None
                old_qty = events[0].quantity
                old_res_from, old_res = transfer.give_and_receive_resources()
                #if events[0].resource:
                #    old_res = events[0].resource
                for event in events:
                    event.resource_type = rt
                    event.resource = res
                    if res_from and event.event_type == et_give:
                        event.resource = res_from
                    event.from_agent = from_agent
                    event.to_agent = to_agent
                    event.event_date = event_date
                    event.quantity=qty
                    event.unit_of_quantity = rt.unit
                    event.value=value
                    event.unit_of_value = unit_of_value
                    event.description=description
                    event.event_reference=event_ref
                    event.changed_by = request.user
                    event.save()
                    res_to_change = event.resource
                    if event.event_type == et_give:
                        if old_res_from:
                            old_res_to_change = old_res_from
                        else:
                            old_res_to_change = old_res
                    else:
                        old_res_to_change = old_res
                    if res_to_change:
                        if old_res_to_change:
                            if res_to_change == old_res_to_change:
                                if event.event_type == et_give:
                                    res_to_change.quantity = res_to_change.quantity + old_qty - qty
                                else:
                                    res_to_change.quantity = res_to_change.quantity - old_qty + qty
                                res_to_change.save()
                            else:
                                if event.event_type == et_give:
                                    res_to_change.quantity = res_to_change.quantity - qty
                                    old_res_to_change.quantity = old_res_to_change.quantity + qty
                                else:
                                    res_to_change.quantity = res_to_change.quantity + qty
                                    old_res_to_change.quantity = old_res_to_change.quantity - qty
                                res_to_change.save()
                                old_res_to_change.save()
                        else:
                            if event.event_type == et_give:
                                res_to_change.quantity = res_to_change.quantity - qty
                            else:
                                res_to_change.quantity = res_to_change.quantity + qty
                            res_to_change.save()
                    else:
                        if old_res_to_change:
                            if event.event_type == et_give:
                                old_res_to_change.quantity = old_res_to_change.quantity + qty
                            else:
                                old_res_to_change.quantity = old_res_to_change.quantity - qty
                            old_res_to_change.save()

                transfer.transfer_date = event_date
                transfer.save()

    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def delete_transfer_events(request, transfer_id):
    transfer = get_object_or_404(Transfer, pk=transfer_id)
    exchange = transfer.exchange
    if request.method == "POST":
        res = None
        events = transfer.events.all()
        et_give = EventType.objects.get(name="Give")
        give_res = None
        receive_res = None
        if events:
            for event in events:
                if event.event_type == et_give:
                    give_res = event.resource
                else:
                    receive_res = event.resource
                event.delete()
            if give_res != receive_res:
                if give_res:
                    give_res.quantity += event.quantity
                if receive_res:
                    receive_res.quantity -= event.quantity
            if give_res:
                if give_res.is_deletable():
                    give_res.delete()
                else:
                    give_res.save()
            if receive_res:
                if receive_res.is_deletable():
                    receive_res.delete()
                else:
                    receive_res.save()
        if transfer.is_deletable():
             transfer.delete()
    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', transfer.context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def add_work_for_exchange(request, exchange_id):
    exchange = get_object_or_404(Exchange, pk=exchange_id)
    context_agent = exchange.context_agent
    form = WorkEventContextAgentForm(context_agent=context_agent, data=request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        rt = event.resource_type
        event.event_type = EventType.objects.get(name="Time Contribution")
        event.exchange = exchange
        event.context_agent = context_agent
        event.to_agent = context_agent
        event.unit_of_quantity = rt.unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def change_exchange_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    exchange = event.exchange
    context_agent=exchange.context_agent
    if request.method == "POST":
        form = WorkEventContextAgentForm(
            context_agent=context_agent,
            instance=event,
            data=request.POST,
            prefix=str(event.id))
        if form.is_valid():
            data = form.cleaned_data
            form.save()

    return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
        % ('work/agent', context_agent.id, 'exchange-logging-work', 0, exchange.id))



@login_required
def delete_event(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(EconomicEvent, pk=event_id)
        agent = event.from_agent
        process = event.process
        exchange = event.exchange
        distribution = event.distribution
        resource = event.resource
        if resource:
            if event.consumes_resources():
                resource.quantity += event.quantity
            if event.creates_resources():
                resource.quantity -= event.quantity
            if event.changes_stage():
                tbcs = process.to_be_changed_requirements()
                if tbcs:
                    tbc = tbcs[0]
                    tbc_evts = tbc.fulfilling_events()
                    if tbc_evts:
                        tbc_evt = tbc_evts[0]
                        resource.quantity = tbc_evt.quantity
                        tbc_evt.delete()
                    resource.stage = tbc.stage
                else:
                    resource.revert_to_previous_stage()
            event.delete()
            if resource.is_deletable():
                resource.delete()
            else:
                resource.save()
        else:
            event.delete()

    next = request.POST.get("next")
    """if next == "process":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/process', process.id))
    if next == "cleanup-processes":
        return HttpResponseRedirect('/%s/'
            % ('accounting/cleanup-processes'))
    if next == "exchange":
        return HttpResponseRedirect('/%s/%s/%s/'
            % ('accounting/exchange', 0, exchange.id))"""
    if next == "exchange-work":
        return HttpResponseRedirect('/%s/%s/%s/%s/%s/'
            % ('work/agent', event.context_agent.id, 'exchange-logging-work', 0, exchange.id))
    """if next == "distribution":
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/distribution', distribution.id))
    if next == "resource":
        resource_id = request.POST.get("resource_id")
        return HttpResponseRedirect('/%s/%s/'
            % ('accounting/resource', resource_id))
    elif next == "contributions":
        page = request.POST.get("page")

        if page:
            return HttpResponseRedirect('/%s/%s/?page=%s'
                % ('accounting/contributionhistory', agent.id, page))
        else:
            return HttpResponseRedirect('/%s/%s/'
                % ('accounting/contributionhistory', agent.id))
    elif next == "work-contributions":
        page = request.POST.get("page")

        if page:
            return HttpResponseRedirect('/%s/?page=%s'
                % ('work/my-history', page))
        else:
            return HttpResponseRedirect('/%s/'
                % ('work/my-history'))
    elif next == "work":
        return HttpResponseRedirect('/%s/%s/'
            % ('work/process-logging', process.id))"""




def resource_role_context_agent_formset(prefix, data=None):
    RraFormSet = modelformset_factory(
        AgentResourceRole,
        form=ResourceRoleContextAgentForm,
        can_delete=True,
        extra=4,
        )
    formset = RraFormSet(prefix=prefix, queryset=AgentResourceRole.objects.none(), data=data)
    return formset


def json_ocp_resource_type_resources_with_locations(request, ocp_artwork_type_id):
    rs = EconomicResource.objects.filter(resource_type__ocp_artwork_type__isnull=False, resource_type__ocp_artwork_type__id=ocp_artwork_type_id)
    resources = []
    for r in rs:
        loc = ""
        if r.current_location:
            loc = r.current_location.name
        fields = {
            "pk": r.pk,
            "identifier": r.identifier,
            "location": loc,
        }
        resources.append({"fields": fields})
    data = simplejson.dumps(resources, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")





#    C R E A T E   S H A R E S


def create_project_shares(request, agent_id):

    agent = EconomicAgent.objects.get(id=agent_id)
    project = agent.project

    user_agent = get_agent(request)
    if not user_agent or not request.user.is_superuser or not project.fobi_slug: # or not project.share_types()
        loger.warning("No project fobi slug? "+str(project)+" or not user_agent")
        return render(request, 'work/no_permission.html')

    nome = project.compact_name()
    abbr = project.abbrev_name()
    print("---------- start create_project_shares ("+str(nome)+":"+str(abbr)+") ----------")
    loger.info("---------- start create_project_shares ("+str(nome)+":"+str(abbr)+") ----------")
    if request.method == "POST":
        shareprice = request.POST.get('shareprice')
        priceunit = request.POST.get('priceunit')
        shareabbr = request.POST.get('shareabbr')
        #print("shareprice:"+str(shareprice)+" priceunit:"+str(priceunit)+" shareabbr:"+str(shareabbr)+" <> "+str(abbr))
        prunit = Unit.objects.get(id=priceunit)
        if not shareprice or not priceunit or not shareabbr or not prunit:
            print("some vars missing!! shareprice:"+str(shareprice)+" priceunit:"+str(priceunit)+" prunit:"+str(prunit)+" shareabbr:"+str(shareabbr)+" <> "+str(abbr))
            loger.info("some vars missing!! shareprice:"+str(shareprice)+" priceunit:"+str(priceunit)+" prunit:"+str(prunit)+" shareabbr:"+str(shareabbr)+" <> "+str(abbr))
            messages.error(request, "Some vars missing!! shareprice:"+str(shareprice)+" priceunit:"+str(priceunit)+" prunit:"+str(prunit)+" shareabbr:"+str(shareabbr)+" <> "+str(abbr))
            return render(request, 'work/no_permission.html')

        if not abbr == shareabbr:
            abbr = shareabbr
    else:
        raise ValidationError("can't create shares without the custom data")

    if len(abbr) < 3:
        raise ValidationError("The project abbrev name is too short to create shares ?! "+abbr)



    # Project Shares

    gen_curr_typ = Ocp_Unit_Type.objects.get(clas="currency")
    artw_sh = Ocp_Artwork_Type.objects.get(clas="shares")
    gen_share_typ = Ocp_Unit_Type.objects.get(clas="shares_currency")
    ocp_each = Unit.objects.get(name_en="Each")

    #  Unit
    ocpboc_shares = Unit.objects.filter(name_en=nome+' Share')
    if not ocpboc_shares:
        ocpboc_shares = Unit.objects.filter(name_en=agent.name_en+' Share')
    if not ocpboc_shares:
        ocpboc_share, created = Unit.objects.get_or_create(
            name_en=nome+' Share',
            unit_type='value',
            abbrev=abbr
        )
        if created:
            print("- created OCP Unit: '"+nome+" Share ("+abbr+")'")
            loger.info("- created OCP Unit: '"+nome+" Share ("+abbr+")'")
            messages.info(request, "- created OCP Unit: '"+nome+" Share ("+abbr+")'")
    else:
        if len(ocpboc_shares) > 1:
            raise ValidationError("There is more than one Unit !? "+str(ocpboc_shares))
        ocpboc_share = ocpboc_shares[0]
    ocpboc_share.name_en = nome+' Share'
    ocpboc_share.unit_type = 'value'
    if ocpboc_share.abbrev and not ocpboc_share.abbrev == abbr:
        print("- changed shares Unit abbrev, from "+str(ocpboc_share.abbrev)+" to "+str(abbr))
        loger.info("- changed shares Unit abbrev, from "+str(ocpboc_share.abbrev)+" to "+str(abbr))
        messages.info(request, "- changed shares Unit abbrev, from "+str(ocpboc_share.abbrev)+" to "+str(abbr))
    ocpboc_share.abbrev = abbr
    ocpboc_share.save()

    #  Ocp_Unit_Type
    gen_boc_typs = Ocp_Unit_Type.objects.filter(name_en__iexact=nome+' Shares')
    if not gen_boc_typs:
        gen_boc_typs = Ocp_Unit_Type.objects.filter(name_en__iexact=agent.name+' Shares')
    if not gen_boc_typs:
        gen_boc_typ, created = Ocp_Unit_Type.objects.get_or_create(
            name_en=nome+' Shares',
            parent=gen_share_typ)
        if created:
            print("- created Ocp_Unit_Type: '"+nome+" Shares'")
            loger.info("- created Ocp_Unit_Type: '"+nome+" Shares'")
            messages.info(request, "- created Ocp_Unit_Type: '"+nome+" Shares'")
    else:
        if len(gen_boc_typs) > 1:
            raise ValidationError("There are more than one Ocp_Unit_Type !? "+str(gen_boc_typs))
        gen_boc_typ = gen_boc_typs[0]
    gen_boc_typ.clas = project.fobi_slug+'_shares'
    gen_boc_typ.save()

    #  Gene_Unit
    boc_shares = Gene_Unit.objects.filter(name__iexact=nome+" Share")
    if not boc_shares:
        boc_shares = Gene_Unit.objects.filter(name__iexact=agent.name+" Share")
    if boc_shares:
        if len(boc_shares) > 1:
            raise ValidationError("There're more than one Gene_Unit !? "+str(boc_shares))
        boc_share = boc_shares[0]
    else:
        boc_share, created = Gene_Unit.objects.get_or_create(
            name=nome+' Share',
            code=abbr)
        if created:
            print("- created General.Unit: '"+nome+" Share'")
            loger.info("- created General.Unit: '"+nome+" Share'")
            messages.info(request, "- created General.Unit: '"+nome+" Share'")
    boc_share.name = nome+" Share"
    boc_share.code = abbr
    boc_share.unit_type = gen_boc_typ
    boc_share.ocp_unit = ocpboc_share
    boc_share.save()

    #  EconomicResourceType
    acc_typ = project.shares_account_type()
    if acc_typ:
        share_rts = EconomicResourceType.objects.filter(name_en__icontains=nome+" Share").exclude(id=acc_typ.id)
        if not share_rts:
            share_rts = EconomicResourceType.objects.filter(name_en__icontains=agent.name+" Share").exclude(id=acc_typ.id)
    else:
        share_rts = EconomicResourceType.objects.filter(name_en__icontains=nome+" Share")
        if not share_rts:
            share_rts = EconomicResourceType.objects.filter(name_en__icontains=agent.name+" Share")
    if share_rts:
        if len(share_rts) > 1:
            raise ValidationError("There are more than 1 EconomicResourceType with same name: "+str(share_rts))
        share_rt = share_rts[0]
    else:
        share_rt, created = EconomicResourceType.objects.get_or_create(
            name_en=nome+' Share',
            unit=ocpboc_share,
            inventory_rule='yes',
            behavior='other'
        )
        if created:
            print("- created EconomicResourceType: '"+nome+" Share'")
            loger.info("- created EconomicResourceType: '"+nome+" Share'")
            messages.info(request, "- created EconomicResourceType: '"+nome+" Share'")
    share_rt.name_en = nome+" Share"
    if hasattr(share_rt, 'unit'):
        if not share_rt.unit == ocpboc_share:
            print("- CHANGED share_rt.unit from "+str(share_rt.unit)+" to "+str(ocpboc_share))
            loger.info("- CHANGED share_rt.unit from "+str(share_rt.unit)+" to "+str(ocpboc_share))
            messages.info(request, "- CHANGED share_rt.unit from "+str(share_rt.unit)+" to "+str(ocpboc_share))
    share_rt.unit = ocpboc_share #ocp_each
    share_rt.inventory_rule = 'yes'
    share_rt.behavior = 'other'
    share_rt.price_per_unit = shareprice # allow coords to choose share price and unit in a form
    share_rt.unit_of_price = prunit
    share_rt.context_agent = project.agent
    share_rt.save()

    shrfv = FacetValue.objects.get(value="Project Shares")
    for fv in share_rt.facets.all():
        if not fv.facet_value == shrfv:
            print("- delete: "+str(fv))
            loger.info("- delete: "+str(fv))
            messages.info(request, "- delete: "+str(fv))
            fv.delete()
    share_rtfv, created = ResourceTypeFacetValue.objects.get_or_create(
        resource_type=share_rt,
        facet_value=shrfv)
    if created:
        print("- created ResourceTypeFacetValue: "+str(share_rtfv))
        loger.info("- created ResourceTypeFacetValue: "+str(share_rtfv))
        messages.info(request, "- created ResourceTypeFacetValue: "+str(share_rtfv))


    #  Ocp_Artwork_Type
    if acc_typ:
        artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains=nome+" Share").exclude(id=acc_typ.ocp_artwork_type.id)
        if not artw_bocs:
            artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains=agent.name_en+" Share").exclude(id=acc_typ.ocp_artwork_type.id)
    else:
        artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains=nome+" Share")
        if not artw_bocs:
            artw_bocs = Ocp_Artwork_Type.objects.filter(name_en__icontains=agent.name_en+" Share")
    if artw_bocs:
        if len(artw_bocs) > 1:
            raise ValidationError("There are more than 1 Ocp_Artwork_Type with same name: "+str(artw_bocs))
        artw_boc = artw_bocs[0]
    else:
        artw_boc, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en=nome+' Share',
            parent=Type.objects.get(id=artw_sh.id)
        )
        if created:
            print("- created Ocp_Artwork_Type: '"+nome+" Share'")
            loger.info("- created Ocp_Artwork_Type: '"+nome+" Share'")
            messages.info(request, "- created Ocp_Artwork_Type: '"+nome+" Share'")
    artw_boc.name_en = nome+" Share"
    artw_boc.parent = Type.objects.get(id=artw_sh.id)
    artw_boc.resource_type = share_rt
    artw_boc.general_unit_type = Unit_Type.objects.get(id=gen_boc_typ.id)
    artw_boc.save()


    #  P r o j e c t   S h a r e s   A c c o u n t

    #  EconomicResourceType
    ert_accs = EconomicResourceType.objects.filter(name_en__icontains=agent.name_en+" Shares Account")
    if not ert_accs:
        ert_accs = EconomicResourceType.objects.filter(name_en__icontains=nome+" Shares Account")
    if ert_accs:
        if len(ert_accs) > 1:
            raise ValidationError("There is more than 1 EconomicResourceType ?! "+str(ert_accs))
        ert_acc = ert_accs[0]
    else:
        ert_acc, created = EconomicResourceType.objects.get_or_create(
            name_en=agent.name_en+" Shares Account",
            unit=ocp_each,
            inventory_rule='yes',
            behavior='account')
        if created:
            print("- created EconomicResourceType: "+str(ert_acc))
            loger.info("- created EconomicResourceType: "+str(ert_acc))
            messages.info(request, "- created EconomicResourceType: "+str(ert_acc))
    ert_acc.name_en = agent.name_en+" Shares Account"
    ert_acc.unit = ocp_each
    ert_acc.inventory_rule = 'yes'
    ert_acc.behavior = 'account'
    ert_acc.unit_of_price = ocpboc_share
    ert_acc.context_agent = agent
    ert_acc.save()

    #  Ocp_Artwork_Type
    parent_accs = Ocp_Artwork_Type.objects.get(clas="accounts")
    proaccs = Ocp_Artwork_Type.objects.filter(name_en__icontains=agent.name_en+" Shares Account")
    if not proaccs:
        proaccs = Ocp_Artwork_Type.objects.filter(name_en__icontains=nome+" Shares Account")
    if proaccs:
        if len(proaccs) > 1:
            raise ValidationError("There is more than one Ocp_Artwork_Type ?! "+str(proaccs))
        proacc = proaccs[0]
    else:
        proacc, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en=agent.name_en+" Shares Account",
            parent=parent_accs)
        if created:
            print("- created Ocp_Artwork_Type: '"+nome+" Shares Account'")
            loger.info("- created Ocp_Artwork_Type: '"+nome+" Shares Account'")
            messages.info(request, "- created Ocp_Artwork_Type: '"+nome+" Shares Account'")
    proacc.name_en = agent.name_en+" Shares Account"
    proacc.parent = parent_accs
    proacc.clas = nome.lower()+'shares'
    proacc.resource_type = ert_acc
    proacc.rel_nonmaterial_type = artw_boc
    proacc.save()

    # has resource ?
    owner = AgentResourceRoleType.objects.get(is_owner=True, name_en="Owner")
    aresrol = None
    arrs = AgentResourceRole.objects.filter(agent=agent, role=owner, resource__resource_type=ert_acc)
    if arrs:
        if len(arrs) > 1:
            raise ValidationError("There are two accounts of the same type for the same agent! "+str(arrs))
        aresrol = arrs[0]
        res = aresrol.resource
    else:
        #  EconomicResource
        ress = EconomicResource.objects.filter(resource_type=ert_acc, identifier=abbr+" shares account for "+abbr)
        if not ress:
            ress = EconomicResource.objects.filter(resource_type=ert_acc, identifier=abbr+" shares account for "+agent.name)
        if not ress:
            ress = EconomicResource.objects.filter(resource_type=ert_acc, identifier=abbr+" shares account for "+agent.nick)
        if not ress:
            ress = EconomicResource.objects.filter(resource_type=ert_acc, identifier=agent.nick+" shares account for "+agent.nick)
        if ress:
            if len(ress) > 1:
                raise ValidationError("There's more than one EconomicResource ?! "+str(ress))
            res = ress[0]
        else:
            res, created = EconomicResource.objects.get_or_create(
                resource_type=ert_acc,
                identifier=agent.nick+" shares account for "+agent.nick,
                quantity=1
            )
            if created:
                print("- created EconomicResource: "+str(res))
                loger.info("- created EconomicResource: "+str(res))
                messages.info(request, "- created EconomicResource: "+str(res))
    old_ident = res.identifier
    res.resource_type = ert_acc
    res.identifier = agent.nick+" shares account for "+agent.nick
    res.quantity = 1
    res.save()
    if not res.identifier == old_ident:
        print("The resource name has changed! rename member accounts?")
        loger.info("The resource name has changed! rename member accounts?")
        messages.info(request, "The resource name has changed! rename member accounts?")
        for ag in agent.all_has_associates():
            for rs in ag.has_associate.owned_accounts():
                if abbr+" shares account" in rs.identifier:
                    rs.identifier = agent.nick_en+" shares account for "+ag.has_associate.nick_en
                    rs.save()
                    print("- Renamed account! "+rs.identifier)
                    loger.info("- Renamed account! "+rs.identifier)
                    messages.info(request, "- Renamed account! "+rs.identifier)

    #  AgentResourceRole
    if not aresrol:
        aresrol, created = AgentResourceRole.objects.get_or_create(
            agent=agent,
            resource=res,
            role=owner)
        if created:
            print("- created AgentResourceRole: "+str(aresrol))
            loger.info("- created AgentResourceRole: "+str(aresrol))
            messages.info(request, "- created AgentResourceRole: "+str(aresrol))

    print("---------- end create_project_shares ("+str(nome)+":"+str(abbr)+") ----------")
    loger.info("---------- end create_project_shares ("+str(nome)+":"+str(abbr)+") ----------")

    return HttpResponseRedirect('/%s/%s/'
            % ('work/agent', project.agent.id))



#    S H A R E S   E X C H A N G E   T Y P E S


def create_shares_exchange_types(request, agent_id):

    agent = EconomicAgent.objects.get(id=agent_id)
    project = agent.project
    user_agent = get_agent(request)
    if not user_agent or not project.share_types() or not request.user.is_superuser:
        return render(request, 'work/no_permission.html')

    print("---------- start create_shares_exchange_types ("+str(agent)+") ----------")
    loger.info("---------- start create_shares_exchange_types ("+str(agent)+") ----------")

    ocpag = EconomicAgent.objects.root_ocp_agent()
    dummy = EconomicAgent.objects.get(nick_en="Dummy")
    if not dummy:
        dummy, created = EconomicAgent.objects.get_or_create(
            nick_en="Dummy",
            name_en="Dummy ContextAgent",
            agent_type=AgentType.objects.get(name="Entity"),
            is_context=True)
        if created:
            print("- created EconomicAgent: 'Dummy'")
            loger.info("- created EconomicAgent: 'Dummy'")
    dummy.name_en = "Dummy ContextAgent"
    dummy.is_context = True
    dummy.save()

    botc = EconomicAgent.objects.filter(nick_en="BoC")
    if not botc:
        botc = EconomicAgent.objects.filter(nick_en="BotC")
    if not botc:
        print("- WARNING: the BotC agent don't exist, not created any exchange type for shares")
        loger.info("- WARNING: the BotC agent don't exist, not created any exchange type for shares")
        raise ValidationError("- WARNING: the BotC agent don't exist, not created any exchange type for shares")
    else:
        botc = botc[0]


    # common Exchange Types

    ocpext = Ocp_Record_Type.objects.get(clas='ocp_exchange')
    usecas = UseCase.objects.get(identifier='intrnl_xfer')

    et_sharecos = Ocp_Record_Type.objects.filter(name_en__icontains="Shares Economy")
    if et_sharecos:
        if len(et_sharecos) > 1:
            raise ValidationError("There are more than 1 Ocp_Record_Type named 'Shares Economy' : "+str(et_sharecos))
        et_shareco = et_sharecos[0]
    else:
        et_shareco, created = Ocp_Record_Type.objects.get_or_create(
            name_en="Shares Economy:",
            parent=ocpext)
        if created:
            print("- created Ocp_Record_Type branch: 'Shares Economy'")
            loger.info("- created Ocp_Record_Type branch: 'Shares Economy'")
    et_shareco.name_en = "Shares Economy:"
    et_shareco.clas = "shares_economy"

    shareco, created = ExchangeType.objects.get_or_create(
        name="Shares Economy")
    if created:
        print("- created ExchangeType: 'Shares Economy'")
        loger.info("- created ExchangeType: 'Shares Economy'")

    shareco.context_agent = botc
    shareco.use_case = usecas
    shareco.save()

    et_shareco.exchange_type = shareco
    et_shareco.save()

    et_sharebuys = Ocp_Record_Type.objects.filter(name_en__iexact="Buy Shares", parent=et_shareco)
    if not et_sharebuys:
        et_sharebuys = Ocp_Record_Type.objects.filter(name_en__iexact="shares Buy", parent=et_shareco)
    if not et_sharebuys:
        et_sharebuys = Ocp_Record_Type.objects.filter(name_en__iexact="buy Project Shares", parent=et_shareco)
    if et_sharebuys:
        et_sharebuy = et_sharebuys[0]
    else:
        et_sharebuy, created = Ocp_Record_Type.objects.get_or_create(
            name_en="shares Buy",
            parent=et_shareco)
        if created:
            print("- created Ocp_Record_Type branch: 'shares Buy'")
            loger.info("- created Ocp_Record_Type branch: 'shares Buy'")
    et_sharebuy.name_en = 'shares Buy'
    et_sharebuy.clas = 'buy'

    etshs = ExchangeType.objects.filter(name__iexact="buy Project Shares")
    if not etshs:
        etshs = ExchangeType.objects.filter(name__iexact="share-buy Project Shares")
    if etshs:
        if len(etshs) > 1:
            raise ValidationError("There're more than 1 ExchangeType with same name : "+str(etshs))
        etsh = etshs[0]
    else:
        etsh, created = ExchangeType.objects.get_or_create(
            name="share-buy Project Shares",
            use_case=usecas)
        if created:
            print("- created ExchangeType: 'share-buy Project Shares'")
            loger.info("- created ExchangeType: 'share-buy Project Shares'")
    etsh.name = "share-buy Project Shares"
    etsh.use_case = usecas
    etsh.save()

    et_sharebuy.exchange_type = etsh
    et_sharebuy.ocpRecordType_ocp_artwork_type = Ocp_Artwork_Type.objects.get(clas="shares", name_en="Shares")
    et_sharebuy.save()

    # TransferType  ->  pay
    ttpays = TransferType.objects.filter(exchange_type=etsh, is_currency=True)
    if ttpays:
        if len(ttpays) > 1:
            raise ValidationError("There're more than 1 TransferType with is_currency for ET : "+str(etsh))
        ttpay = ttpays[0]
    else:
        ttpay, created = TransferType.objects.get_or_create(
            name="Give the payment of the Project shares",
            exchange_type=etsh
        )
        if created:
            print("- created TransferType: 'Give the payment of the Project shares'")
            loger.info("- created TransferType: 'Give the payment of the Project shares'")
    ttpay.name = "Give the payment of the Project shares"
    ttpay.exchange_type = etsh
    ttpay.sequence = 1
    ttpay.give_agent_is_context = False
    ttpay.receive_agent_is_context = True
    ttpay.is_reciprocal = True
    ttpay.is_currency = True
    ttpay.inherit_types =  False
    ttpay.is_to_distribute = True
    ttpay.is_contribution = False
    ttpay.can_create_resource = False
    ttpay.save()

    fvmoney = FacetValue.objects.get(value="Money") # maybe better just Shares (not multi gateway)?

    for fv in ttpay.facet_values.all():
        if not fv.facet_value == fvmoney:
            print("- delete fv: "+str(fv))
            loger.info("- delete fv: "+str(fv))
            fv.delete()
    ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
        transfer_type=ttpay,
        facet_value=fvmoney)
    if created:
        print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(fvmoney))
        loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(fvmoney))

    #  TransferType  ->  receive
    ttshrs = TransferType.objects.filter(exchange_type=etsh, inherit_types=True)
    if ttshrs:
        if len(ttshrs) > 1:
            raise ValidationError("There are more than 1 TransferType with inherit_types for ET : "+str(etsh))
        ttshr = ttshrs[0]
    else:
        ttshr, created = TransferType.objects.get_or_create(
            name="Receive the Project shares",
            exchange_type=etsh
        )
        if created:
            print("- created TransferType: 'Receive the Project shares'")
            loger.info("- created TransferType: 'Receive the Project shares'")
    ttshr.name = "Receive the Project shares"
    ttshr.exchange_type = etsh
    ttshr.sequence = 2
    ttshr.give_agent_is_context = True
    ttshr.receive_agent_is_context = False
    ttshr.is_reciprocal = False
    ttshr.is_currency = False
    ttshr.inherit_types =  True
    ttshr.is_to_distribute = False
    ttshr.is_contribution = False
    ttshr.can_create_resource = False
    ttshr.save()

    shrfv = FacetValue.objects.get(value="Project Shares")

    for fv in ttshr.facet_values.all():
        if not fv.facet_value == shrfv:
            print("- delete: "+str(fv))
            loger.info("- delete: "+str(fv))
            fv.delete()
    ttshrfv, created = TransferTypeFacetValue.objects.get_or_create(
        transfer_type=ttshr,
        facet_value=shrfv)
    if created:
        print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))
        loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))



    #  generic   B u y   P r o j e c t   S h a r e s

    rt = project.shares_account_type()
    if not rt:
        raise ValidationError("The project has not a shares_account_type ! "+str(project))
    elif not rt.ocp_artwork_type:
        raise ValidationError("The project rt has not an ocp_artwork_type ! "+str(rt))
    elif not rt.ocp_artwork_type.rel_nonmaterial_type:
        raise ValidationError("The project rt.ocp_artwork_type has not a rel_nonmaterial_type ! "+str(rt.ocp_artwork_type))
    elif not rt.ocp_artwork_type.rel_nonmaterial_type.general_unit_type:
        raise ValidationError("The project rt.ocp_artwork_type.rel_nonmaterial_type has not a general_unit_type ! "+str(rt.ocp_artwork_type.rel_nonmaterial_type))
    else:

        #  ExchangeType  ->  project
        extyps = ExchangeType.objects.filter(name__iexact="buy "+str(project.compact_name())+" Shares")
        if not extyps:
            extyps = ExchangeType.objects.filter(name__iexact="buy "+str(project.agent.name)+" Shares")
        if not extyps:
            extyps = ExchangeType.objects.filter(name__iexact="share-buy "+str(project.agent.name)+" Shares")
        if extyps:
            if len(extyps) > 1:
                raise ValidationError("There are more than 1 ExchangeType with same name: "+str(extyps))
            extyp = extyps[0]
        else:
            extyp, created = ExchangeType.objects.get_or_create(
                name="share-buy "+str(project.compact_name())+" Shares",
                use_case=usecas)
            if created:
                print("- created ExchangeType: 'share-buy "+str(project.compact_name())+" Shares'")
                loger.info("- created ExchangeType: 'share-buy "+str(project.compact_name())+" Shares'")
        extyp.name = "share-buy "+str(project.compact_name())+" Shares"
        extyp.use_case = usecas
        extyp.context_agent = project.agent
        extyp.save()

        tts = extyp.transfer_types.all()
        if len(tts) > 2:
            #print("The ExchangeType already has TransferType's: "+str(tts))
            raise ValidationError("The ExchangeType has more than 2 TransferType's: "+str(tts))

        #  Ocp_Record_Type  ->  project
        rectyps = Ocp_Record_Type.objects.filter(name_en__iexact="buy "+str(project.compact_name())+" Shares")
        if not rectyps:
            rectyps = Ocp_Record_Type.objects.filter(name_en__iexact="buy "+str(project.agent.name_en)+" Shares")
        if not rectyps:
            rectyps = Ocp_Record_Type.objects.filter(name_en__iexact="share-buy "+str(project.agent.name_en)+" Shares")
        if rectyps:
            if len(rectyps) > 1:
                raise ValidationError("There are more than 1 Ocp_Record_Type with same name: "+str(rectyps))
            rectyp = rectyps[0]
        else:
            rectyp, created = Ocp_Record_Type.objects.get_or_create(
                name_en="share-buy "+str(project.compact_name())+" Shares",
                parent=et_sharebuy)
            if created:
                print("- created Ocp_Record_Type: 'share-buy "+str(project.compact_name())+" Shares'")
                loger.info("- created Ocp_Record_Type: 'share-buy "+str(project.compact_name())+" Shares'")
        rectyp.name_en = "share-buy "+str(project.compact_name())+" Shares"
        rectyp.parent = et_sharebuy
        rectyp.exchange_type = extyp
        rectyp.ocpRecordType_ocp_artwork_type = rt.ocp_artwork_type.rel_nonmaterial_type
        rectyp.save()

        ##  TransferType's  ->  project  ->  pay
        ttpays = TransferType.objects.filter(exchange_type=extyp, is_currency=True)
        if not ttpays:
            ttpays = TransferType.objects.filter(exchange_type=extyp, name__icontains="Payment")
        if ttpays:
            if len(ttpays) > 1:
                raise ValidationError("There are more than 1 TransferType with is_currency or 'Payment' : "+str(ttpays))
            ttpay = ttpays[0]
        else:
            ttpay, created = TransferType.objects.get_or_create(
                name="Give the payment of the "+str(project.agent.name)+" shares",
                exchange_type=extyp)
            if created:
                print("- created TransferType: 'Give the payment of the "+str(project.agent.name)+" shares'")
                loger.info("- created TransferType: 'Give the payment of the "+str(project.agent.name)+" shares'")
        ttpay.name = "Give the payment of the "+str(project.agent.name)+" shares"
        ttpay.exchange_type = extyp
        ttpay.sequence = 1
        ttpay.give_agent_is_context = True
        ttpay.receive_agent_is_context = False
        ttpay.is_reciprocal = False
        ttpay.is_currency = True
        ttpay.inherit_types =  False
        ttpay.is_to_distribute = True
        ttpay.is_contribution = False
        ttpay.can_create_resource = False
        ttpay.save()

        ###  TransferTypeFacetValue  ->  pay  ->  money
        ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttpay,
            facet_value=fvmoney)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(fvmoney))
            loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(fvmoney))

        ##  TransferType  ->  project  ->  receive
        ttshrs = TransferType.objects.filter(exchange_type=extyp, inherit_types=True)
        if not ttshrs:
            ttshrs = TransferType.objects.filter(exchange_type=extyp, name__icontains="Receive")
        if not ttshrs:
            ttshrs = TransferType.objects.filter(exchange_type=extyp, name__icontains="Transfer Membership")
        if ttshrs:
            if len(ttshrs) > 1:
                raise ValidationError("There are more than 1 TransferType with inherit_types or 'Receive' : "+str(ttshrs))
            ttshr = ttshrs[0]
        else:
            ttshr, created = TransferType.objects.get_or_create(
                name="Receive the "+str(project.agent.name)+" shares",
                exchange_type=extyp)
            if created:
                print("- created TransferType: 'Receive the "+str(project.agent.name)+" shares'")
                loger.info("- created TransferType: 'Receive the "+str(project.agent.name)+" shares'")
        ttshr.name = "Receive the "+str(project.agent.name)+" shares"
        ttshr.exchange_type = extyp
        ttshr.sequence = 2
        ttshr.give_agent_is_context = False
        ttshr.receive_agent_is_context = True
        ttshr.is_reciprocal = True
        ttshr.is_currency = False
        ttshr.inherit_types =  True
        ttshr.is_to_distribute = False
        ttshr.is_contribution = False
        ttshr.can_create_resource = False
        ttshr.save()

        ###  TransferTypeFacetValue  ->  receive  ->  share
        for fv in ttshr.facet_values.all():
            if not fv.facet_value == shrfv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttshrfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttshr,
            facet_value=shrfv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))
            loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))



        curfacet = Facet.objects.get(name="Currency")
        nonfacet = Facet.objects.get(name="Non-material")
        gate_keys = project.active_payment_options_obj()
        for obj in gate_keys:

            gatefv = None
            parent_rectyp = None
            slug = None
            nome = None
            ob = obj[0]
            if ob == 'transfer' or ob == 'ccard' or ob == 'debit' or ob == 'cash' or ob == 'botcw':
                slug = 'fiat'
                nome = 'Fiat'
                title = 'Fiat-currency'
            elif ob == 'faircoin':
                slug = 'fair'
                nome = 'Fair'
                title = 'Faircoin'
            elif ob in settings.CRYPTOS:
                slug = 'crypto'
                nome = 'Crypto'
                title = 'Cryptocoins'
            elif ob == 'share':
                slug = 'share'
                nome = 'Shares'
                title = 'Shares'
                gatefv = shrfv
                continue # the share-buy et tree is already there
            else:
                raise ValidationError("Payment gateway not known: "+str(ob))


            if not gatefv:
                gatefv, created = FacetValue.objects.get_or_create(value=nome+" currency", facet=curfacet)
                if created:
                    print("- created FacetValue: '"+nome+" currency'")
                    loger.info("- created FacetValue: '"+nome+" currency'")

            etfiats = ExchangeType.objects.filter(name=title+" Economy")
            if etfiats:
                etfiat = etfiats[0]
                for tt in etfiat.transfer_types.all():
                    print("- delete tt? "+str(tt))
                    loger.info("- delete tt? "+str(tt))
                    if tt.is_deletable():
                        tt.delete()
                print("- delete etfiat? "+str(etfiat))
                loger.info("- delete etfiat? "+str(etfiat))
                if etfiat.is_deletable():
                    etfiat.delete()

            #  Ocp_Record_Type  branch
            parent_rectyps = Ocp_Record_Type.objects.filter(clas=slug+"_economy")
            if not parent_rectyps:
                parent_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=title+" Economy")
            if parent_rectyps:
                if len(parent_rectyps) > 1:
                    raise ValidationError("There are more than 1 Ocp_Record_Type named: '"+title+" Economy'")
                parent_rectyp = parent_rectyps[0]
                #print("- edited Ocp_Record_Type: '"+title+" Economy:'")
            else:
                parent_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                    name_en=title+" Economy:",
                    clas=slug+"_economy",
                    parent=ocpext
                )
                if created:
                    print("- created Ocp_Record_Type: '"+title+" Economy:'")
                    loger.info("- created Ocp_Record_Type: '"+title+" Economy:'")
            parent_rectyp.name_en = title+" Economy:"
            parent_rectyp.parent = ocpext
            parent_rectyp.clas = slug+"_economy"
            parent_rectyp.exchange_type = None
            parent_rectyp.save()

            #   Buy  sub-branch
            parent_rectypbuy, created = Ocp_Record_Type.objects.get_or_create(
                name_en=slug+" Buy",
                parent=parent_rectyp
            )
            if created:
                print("- created Ocp_Record_Type: '"+slug+" Buy'")
                loger.info("- created Ocp_Record_Type: '"+slug+" Buy'")
            parent_rectypbuy.clas = "buy"
            parent_rectypbuy.save()


            #   G e n e r i c    B u y    N o n - m a t e r i a l

            #  Ocp_Record_Type
            parent_rectypbuy_nons = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-Buy Non-material resources")
            if not parent_rectypbuy_nons:
                parent_rectypbuy_nons = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy Non-materials")
            if parent_rectypbuy_nons:
                parent_rectypbuy_non = parent_rectypbuy_nons[0]
            else:
                parent_rectypbuy_non, created = Ocp_Record_Type.objects.get_or_create(
                    name_en=slug+"-buy Non-materials",
                    parent=parent_rectypbuy
                )
                if created:
                    print("- created Ocp_Record_Type: '"+slug+"-buy Non-materials'")
                    loger.info("- created Ocp_Record_Type: '"+slug+"-buy Non-materials'")
            parent_rectypbuy_non.name_en = slug+"-buy Non-materials"
            parent_rectypbuy_non.parent = parent_rectypbuy
            parent_rectypbuy_non.ocpRecordType_ocp_artwork_type = Ocp_Artwork_Type.objects.get(clas="Nonmaterial")
            #parent_rectypbuy_non.save()

            #  ExchangeType
            etfiat_nons = ExchangeType.objects.filter(name__icontains=slug+"-Buy Non-material resources")
            if not etfiat_nons:
                etfiat_nons = ExchangeType.objects.filter(name=slug+"-buy Non-materials")
            if etfiat_nons:
                if len(etfiat_nons) > 1:
                    raise ValidationError("There are more than 1 ExchangeType with the name: '"+slug+"-buy Non-materials'")
                etfiat_non = etfiat_nons[0]
            else:
                etfiat_non, created = ExchangeType.objects.get_or_create(
                    name=slug+"-buy Non-materials")
                if created:
                    print("- created ExchangeType: '"+slug+"-buy Non-materials'")
                    loger.info("- created ExchangeType: '"+slug+"-buy Non-materials'")
            etfiat_non.name = slug+"-buy Non-materials"
            etfiat_non.use_case = usecas
            etfiat_non.save()

            parent_rectypbuy_non.exchange_type = etfiat_non
            parent_rectypbuy_non.save()

            ##  TransferType  ->  pay
            ttpays = TransferType.objects.filter(exchange_type=etfiat_non, is_currency=True)
            if ttpays:
                if len(ttpays) > 1:
                    raise ValidationError("There are more than 1 TransferType with is_currency for the ET : "+str(etfiat_non))
                ttpay = ttpays[0]
            else:
                ttpay, created = TransferType.objects.get_or_create(
                    name="Give the payment of the Non-material ("+slug+")",
                    exchange_type=etfiat_non
                    #give_agent_is_context=True,
                )
                if created:
                    print("- created TransferType: 'Give the payment of the Non-material ("+slug+")'")
                    loger.info("- created TransferType: 'Give the payment of the Non-material ("+slug+")'")

            ttpay.name = "Give the payment of the Non-material ("+slug+")"
            ttpay.exchange_type = etfiat_non
            ttpay.sequence = 1
            ttpay.give_agent_is_context = False
            ttpay.receive_agent_is_context = True
            ttpay.is_reciprocal = True
            ttpay.is_currency = True
            ttpay.inherit_types =  False
            ttpay.is_to_distribute = True
            ttpay.is_contribution = False
            ttpay.can_create_resource = False
            ttpay.save()

            ###  TransferTypeFacetValue  ->  pay  ->  gatefv
            for fv in ttpay.facet_values.all():
                if not fv.facet_value == gatefv:
                    print("- delete fv: "+str(fv))
                    loger.info("- delete fv: "+str(fv))
                    fv.delete()
            ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttpay,
                facet_value=gatefv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))
                loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))

            ##  TransferType  ->  receive
            ttnons = TransferType.objects.filter(exchange_type=etfiat_non, inherit_types=True)
            if ttnons:
                if len(ttnons) > 1:
                    raise ValidationError("There are more than 1 TransferType with inherit_types for the ET : "+str(etfiat_non))
                ttnon = ttnons[0]
            else:
                ttnon, created = TransferType.objects.get_or_create(
                    name="Receive the Non-material",
                    exchange_type=etfiat_non
                    #receive_agent_is_context=True,
                )
                if created:
                    print("- created TransferType: 'Receive the Non-material' ("+slug+")")
                    loger.info("- created TransferType: 'Receive the Non-material' ("+slug+")")

            ttnon.name = "Receive the Non-material"
            ttnon.exchange_type = etfiat_non
            ttnon.sequence = 2
            ttnon.give_agent_is_context = True
            ttnon.receive_agent_is_context = False
            ttnon.is_reciprocal = False
            ttnon.is_currency = False
            ttnon.inherit_types = True
            ttnon.is_to_distribute = False
            ttnon.is_contribution = False
            ttnon.can_create_resource = False
            ttnon.save()

            ###  TransferTypeFacetValue  ->  receive  ->  Nonmaterial
            nonfvs = FacetValue.objects.filter(facet=nonfacet)
            for fv in nonfvs:
                ttnonfv, created = TransferTypeFacetValue.objects.get_or_create(
                    transfer_type=ttnon,
                    facet_value=fv)
                if created:
                    print("- created TransferTypeFacetValue: "+str(ttnon)+" <> "+str(fv))
                    loger.info("- created TransferTypeFacetValue: "+str(ttnon)+" <> "+str(fv))

            tts = etfiat_non.transfer_types.all()
            if not len(tts) == 2:
                print("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))
                loger.info("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))
                raise ValidationError("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))


            #   S H A R E S    B U Y

            fiat_rectyps = Ocp_Record_Type.objects.filter(name_en=slug+"-buy Shares")
            if not fiat_rectyps:
                fiat_rectyps = Ocp_Record_Type.objects.filter(name_en=slug+"-buy Project Shares")
            if fiat_rectyps:
                if len(fiat_rectyps) > 1:
                    raise ValidationError("There's more than 1 Ocp_Record_Type named: '"+slug+"-buy Project Shares'")
                fiat_rectyp = fiat_rectyps[0]
            else:
                fiat_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                    name_en=slug+"-buy Project Shares",
                    parent=parent_rectypbuy_non
                )
                if created:
                    print("- created Ocp_Record_Type: '"+slug+"-buy Project Shares'")
                    loger.info("- created Ocp_Record_Type: '"+slug+"-buy Project Shares'")
            fiat_rectyp.name_en = slug+"-buy Project Shares"
            fiat_rectyp.parent = parent_rectypbuy_non
            fiat_rectyp.ocpRecordType_ocp_artwork_type = Ocp_Artwork_Type.objects.get(clas="shares")

            #  ExchangeType shares
            etfiat_shrs = ExchangeType.objects.filter(name__icontains=slug+"-buy Project Shares")
            if not etfiat_shrs:
                etfiat_shrs = ExchangeType.objects.filter(name__icontains=slug+"-buy Shares")
            if etfiat_shrs:
                if len(etfiat_shrs) > 1:
                    raise ValidationError("There's more than 1 ExchangeType! : "+str(etfiat_shrs))
                etfiat_shr = etfiat_shrs[0]
            else:
                etfiat_shr, created = ExchangeType.objects.get_or_create(
                    name=slug+"-buy Project Shares")
                if created:
                    print("- created ExchangeType: '"+slug+"-buy Project Shares'")
                    loger.info("- created ExchangeType: '"+slug+"-buy Project Shares'")

            etfiat_shr.name = slug+"-buy Project Shares"
            etfiat_shr.use_case = usecas
            etfiat_shr.save()

            fiat_rectyp.exchange_type = etfiat_shr
            fiat_rectyp.save()

            ##  TransferType  ->  pay
            ttfiats = TransferType.objects.filter(exchange_type=etfiat_shr, is_currency=True)
            if ttfiats:
                if len(ttfiats) > 1:
                    raise ValidationError("There's more than 1 TransferType with is_currency for the ET: "+str(etfiat_shr))
                ttfiat = ttfiats[0]
            else:
                ttfiat, created = TransferType.objects.get_or_create(
                    name="Give the payment of the Shares ("+slug+")",
                    exchange_type=etfiat_shr,
                )
                if created:
                    print("- created TransferType: 'Give the payment of the Shares ("+slug+")'")
                    loger.info("- created TransferType: 'Give the payment of the Shares ("+slug+")'")
            ttfiat.name = "Give the payment of the Shares ("+slug+")"
            ttfiat.sequence = 1
            ttfiat.exchange_type = etfiat_shr
            ttfiat.give_agent_is_context = False
            ttfiat.receive_agent_is_context = True
            ttfiat.is_reciprocal = True
            ttfiat.is_currency = True
            ttfiat.inherit_types =  False
            ttfiat.is_to_distribute = True
            ttfiat.is_contribution = False
            ttfiat.can_create_resource = False
            ttfiat.save()

            ###  TransferTypeFacetValue  ->  pay  ->  gatefv
            for fv in ttfiat.facet_values.all():
                if not fv.facet_value == gatefv:
                    print("- delete fv: "+str(fv))
                    loger.info("- delete fv: "+str(fv))
                    fv.delete()
            ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttfiat,
                facet_value=gatefv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttfiat)+" <> "+str(gatefv))
                loger.info("- created TransferTypeFacetValue: "+str(ttfiat)+" <> "+str(gatefv))

            ##  TransferType  ->  receive
            ttshrs = TransferType.objects.filter(exchange_type=etfiat_shr, inherit_types=True)
            if ttshrs:
                if len(ttshrs) > 1:
                    raise ValidationError("There's more than 1 TransferType with inherit_types in the ET: "+str(etfiat_shr))
                ttshr = ttshrs[0]
            else:
                ttshr, created = TransferType.objects.get_or_create(
                    name="Receive the Shares",
                    exchange_type=etfiat_shr,
                    #receive_agent_is_context=True,
                )
                if created:
                    print("- created TransferType: 'Receive the Shares' ("+slug+")")
                    loger.info("- created TransferType: 'Receive the Shares' ("+slug+")")
            ttshr.name = "Receive the Shares"
            ttshr.exchange_type = etfiat_shr
            ttshr.sequence = 2
            ttshr.give_agent_is_context = True
            ttshr.receive_agent_is_context = False
            ttshr.is_reciprocal = False
            ttshr.is_currency = False
            ttshr.inherit_types =  True
            ttshr.is_to_distribute = False
            ttshr.is_contribution = False
            ttshr.can_create_resource = False
            ttshr.save()

            ###  TransferTypeFacetValue  ->  receive  ->  shares
            for fv in ttshr.facet_values.all():
                if not fv.facet_value == shrfv:
                    print("- delete fv: "+str(fv))
                    loger.info("- delete fv: "+str(fv))
                    fv.delete()
            ttnonfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttshr,
                facet_value=shrfv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))
                loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))

            tts = etfiat_shr.transfer_types.all()
            if len(tts) > 2:
                print("The ExchangeType '"+slug+"-buy Project Shares' has more than 2 transfer types: "+str(tts))
                loger.info("The ExchangeType '"+slug+"-buy Project Shares' has more than 2 transfer types: "+str(tts))
                raise ValidationError("The ExchangeType '"+slug+"-buy Project Shares' has more than 2 transfer types: "+str(tts))



            #   P R O J E C T    B U Y    S H A R E S

            slug_ets = ExchangeType.objects.filter(name__icontains=slug+"-buy "+str(project.compact_name())+" Share")
            if not slug_ets:
                slug_ets = ExchangeType.objects.filter(name__icontains=slug+"-buy "+str(project.agent.name)+" Share")

            ## TODO delete when fully migrated
            fdc_et = None
            if slug == 'fair' and project.fobi_slug == 'freedom-coop':
                fdc_et = ExchangeType.objects.membership_share_exchange_type()
            if fdc_et:
                if not slug_ets:
                    slug_ets = [fdc_et]
                else:
                    print("## Repair old fdc_et uses because there is the new et? fdc_et:"+str(fdc_et)+" old_exs:"+str(len(fdc_et.exchanges.all()))+" new_et:"+str(slug_ets[0])+" new_exs:"+str(len(slug_ets[0].exchanges.all())))
                    loger.info("## Repair old fdc_et uses because there is the new et? fdc_et:"+str(fdc_et)+" old_exs:"+str(len(fdc_et.exchanges.all()))+" new_et:"+str(slug_ets[0])+" new_exs:"+str(len(slug_ets[0].exchanges.all())))
                    for ex in fdc_et.exchanges.all():
                        pass
            ##

            if slug_ets:
                if len(slug_ets) > 1:
                    raise ValidationError("There's more than 1 ExchangeType named: '"+slug+"-buy "+str(project.compact_name())+" Share")
                slug_et = slug_ets[0]
            else:
                slug_et, created = ExchangeType.objects.get_or_create(
                    name=slug+"-buy "+str(project.compact_name())+" Shares"
                )
                if created:
                    print("- created ExchangeType: '"+slug+"-buy "+str(project.compact_name())+" Shares'")
                    loger.info("- created ExchangeType: '"+slug+"-buy "+str(project.compact_name())+" Shares'")
            slug_et.name = slug+"-buy "+str(project.compact_name())+" Shares"
            slug_et.use_case = usecas
            slug_et.context_agent = project.agent
            slug_et.save()

            # TransferType  ->  pay
            ttpays = TransferType.objects.filter(exchange_type=slug_et, is_currency=True)
            if ttpays:
                if len(ttpays) > 1:
                    raise ValidationError("There's more than 1 TransferType with is_currency for the ET : "+str(slug_et))
                ttpay = ttpays[0]
            else:
                ttpay.pk = None
                ttpay.id = None
                print("- created TransferType: 'Give the payment of the "+str(project.agent.name)+" shares ("+slug+")'")
                loger.info("- created TransferType: 'Give the payment of the "+str(project.agent.name)+" shares ("+slug+")'")
            ttpay.name = "Give the payment of the "+str(project.agent.name)+" shares ("+slug+")"
            ttpay.exchange_type = slug_et
            ttpay.sequence = 1
            ttpay.give_agent_is_context = False
            ttpay.receive_agent_is_context = True
            ttpay.is_reciprocal = True
            ttpay.is_currency = True
            ttpay.inherit_types =  False
            ttpay.is_to_distribute = True
            ttpay.is_contribution = False
            ttpay.can_create_resource = False
            ttpay.save()

            for fv in ttpay.facet_values.all():
                if not fv.facet_value == gatefv:
                    print("- delete fv: "+str(fv))
                    loger.info("- delete fv: "+str(fv))
                    fv.delete()
            ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttpay,
                facet_value=gatefv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))
                loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))

            # TransferType  ->  receive  ->  share
            ttshrs = TransferType.objects.filter(exchange_type=slug_et, inherit_types=True)
            if not ttshrs:
                ttshrs = TransferType.objects.filter(exchange_type=slug_et, is_currency=False)
            if ttshrs:
                if len(ttshrs) > 1:
                    raise ValidationError("There are more than 1 TransferType with inherit_types (or not is_currency) for the ET : "+str(slug_et))
                ttshr = ttshrs[0]
            else:
                ttshr.pk = None
                ttshr.id = None
                print("- created TransferType: 'Receive the "+str(project.agent.name)+" shares' ("+slug+")")
                loger.info("- created TransferType: 'Receive the "+str(project.agent.name)+" shares' ("+slug+")")
            ttshr.name = "Receive the "+str(project.agent.name)+" shares"
            ttshr.exchange_type = slug_et
            ttshr.sequence = 2
            ttshr.give_agent_is_context = True
            ttshr.receive_agent_is_context = False
            ttshr.is_reciprocal = False
            ttshr.is_currency = False
            ttshr.inherit_types =  True
            ttshr.is_to_distribute = False
            ttshr.is_contribution = False
            ttshr.can_create_resource = False
            ttshr.save()

            for fv in ttshr.facet_values.all():
                if not fv.facet_value == shrfv:
                    print("- delete fv: "+str(fv))
                    loger.info("- delete fv: "+str(fv))
                    fv.delete()
            ttshrfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttshr,
                facet_value=shrfv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))
                loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(shrfv))


            tts = slug_et.transfer_types.all()
            if not len(tts) == 2:
                raise ValidationError("WARNING: The ExchangeType '"+str(slug_et)+"' don't has 2 TransferType's: "+str(tts))


            pro_shr_rectyps = Ocp_Record_Type.objects.filter(exchange_type=slug_et)
            if not pro_shr_rectyps:
                pro_shr_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy "+str(project.compact_name())+" Share")
            if not pro_shr_rectyps:
                pro_shr_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy "+str(project.agent.name_en)+" Share")
            if pro_shr_rectyps:
                if len(pro_shr_rectyps) > 1:
                    raise ValidationError("There are more than 1 Ocp_Record_Type with same name: "+str(pro_shr_rectyp))
                pro_shr_rectyp = pro_shr_rectyps[0]
            else:
                pro_shr_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                    name_en=slug+"-buy "+str(project.compact_name())+" Shares",
                    parent=fiat_rectyp
                )
                if created:
                    print("- created Ocp_Record_Type: '"+slug+"-buy "+str(project.agent.name_en)+" Shares'")
                    loger.info("- created Ocp_Record_Type: '"+slug+"-buy "+str(project.agent.name_en)+" Shares'")
            pro_shr_rectyp.name_en = slug+"-buy "+str(project.compact_name())+" Shares"
            pro_shr_rectyp.ocpRecordType_ocp_artwork_type = rt.ocp_artwork_type.rel_nonmaterial_type
            pro_shr_rectyp.parent = fiat_rectyp
            pro_shr_rectyp.exchange_type = slug_et
            pro_shr_rectyp.save()

    print("---------- end create_shares_exchange_types ("+str(agent)+") ----------")
    loger.info("---------- end create_shares_exchange_types ("+str(agent)+") ----------")

    #return exchanges_all(request, project.agent.id)
    return HttpResponseRedirect('/%s/%s/'
                % ('work/agent', project.agent.id))



#    S U B S C R I P T I O N   E X C H A N G E   T Y P E S


def create_subscription_exchange_types(request, agent_id):

    agent = EconomicAgent.objects.get(id=agent_id)
    project = agent.project
    user_agent = get_agent(request)
    if not user_agent or not project.subscription_unit() or not request.user.is_superuser:
        return render(request, 'work/no_permission.html')

    print("---------- start create_subscription_exchange_types ("+str(agent)+") ----------")
    loger.info("---------- start create_subscription_exchange_types ("+str(agent)+") ----------")

    ocpag = EconomicAgent.objects.root_ocp_agent()

    # common Exchange Types

    ocpext = Ocp_Record_Type.objects.get(clas='ocp_exchange')
    usecas = UseCase.objects.get(identifier='intrnl_xfer')

    ocp_eachs = Unit.objects.filter(name_en='Each')
    if ocp_eachs:
        ocp_each = ocp_eachs[0]
    else:
        raise ValidationError("Not found the Each Unit?")

    nonmat_typs = Ocp_Artwork_Type.objects.filter(clas='Nonmaterial')
    if not nonmat_typs:
        raise ValidationError("Not found the Ocp_Artwork_Type with clas 'Nonmaterial' ?!")
    nonmat_typ = nonmat_typs[0]

    rt_subs = EconomicResourceType.objects.filter(name_en='Subscriptions')
    if not rt_subs:
        rt_subs = EconomicResourceType.objects.filter(name_en='Subscription')
    if rt_subs:
        rt_sub = rt_subs[0]
    else:
        rt_sub, c = EconomicResourceType.objects.get_or_create(
            name_en='Subscription')
        if c:
            print(("- created EconomicResourceType: "+str(rt_sub)))
            loger.info("- created EconomicResourceType: "+str(rt_sub))
    rt_sub.unit = ocp_each
    rt_sub.unit_of_use = ocp_each
    rt_sub.unit_of_value = None
    #rt_sub.value_per_unit_of_use = 1
    rt_sub.substitutable = False
    rt_sub.inventory_rule = 'no'
    #rt_sub.behavior =
    rt_sub.context_agent = None
    rt_sub.save()

    artw_subsc = Ocp_Artwork_Type.objects.filter(name_en='Subscription')
    if not artw_subsc:
        artw_subsc = Ocp_Artwork_Type.objects.filter(name_en='Subscriptions')
    if not artw_subsc:
        artw_sub, created = Ocp_Artwork_Type.objects.get_or_create(
            name_en='Subscriptions',
            parent=nonmat_typ)
        if created:
            print("- created Ocp_Artwork_Type branch: 'Subscriptions'")
            loger.info("- created Ocp_Artwork_Type branch: 'Subscriptions'")
    else:
        artw_sub = artw_subsc[0]
    artw_sub.name_en = 'Subscriptions'
    artw_sub.clas = 'subscriptions'
    artw_sub.parent = nonmat_typ
    artw_sub.resource_type = rt_sub
    artw_sub.general_unit_type = None #gen_share_typ
    artw_sub.save()

    curfacet = Facet.objects.get(name="Currency")
    nonfacet = Facet.objects.get(name="Non-material")

    subfv, c = FacetValue.objects.get_or_create(
        facet=nonfacet,
        value="Project Subscriptions")
    if c:
        print(("- created FacetValue: "+str(subfv)))


    #  generic   B u y   P r o j e c t   S u b s c r i p t i o n s

    subunit = project.subscription_unit()
    if not subunit:
        raise ValidationError("The project has not a subscription_unit ! "+str(project))

    sub_rt = project.subscription_rt()
    if not sub_rt:
        sub_rt, c = EconomicResourceType.objects.get_or_create(
            name_en=project.agent.nick+" Subscription")
        if c:
            print(("- created the EconomicResourceType: "+str(sub_rt)))
    sub_rt.name_en = project.agent.nick+" Subscription"
    sub_rt.unit = project.subscription_unit()
    sub_rt.unit_of_use = sub_rt.unit
    sub_rt.unit_of_value = sub_rt.unit
    sub_rt.unit_of_price = sub_rt.unit
    sub_rt.substitutable = False
    sub_rt.context_agent = project.agent
    sub_rt.inventory_rule = 'no'
    sub_rt.save()

    if not hasattr(sub_rt, 'ocp_artwork_type'):
        artw_prosubs = Ocp_Artwork_Type.objects.filter(name_en=project.compact_name()+' Subscription')
        if not artw_prosubs:
            artw_prosubs = Ocp_Artwork_Type.objects.filter(name_en=project.agent.nick+' Subscription')
        if not artw_prosubs:
            artw_prosubs = Ocp_Artwork_Type.objects.filter(name_en=project.agent.nick_en+' Subscription')
        if not artw_prosubs:
            artw_prosub, created = Ocp_Artwork_Type.objects.get_or_create(
                name_en=project.agent.nick+' Subscription',
                parent=artw_sub)
            if created:
                print(("- created Ocp_Artwork_Type: "+str(artw_prosub)))
                loger.info("- created Ocp_Artwork_Type: "+str(artw_prosub))
        else:
            artw_prosub = artw_prosubs[0]
    else:
        artw_prosub = sub_rt.ocp_artwork_type
    artw_prosub.name_en = project.agent.nick+' Subscription'
    artw_prosub.clas = project.agent.nick+' subscription'
    artw_prosub.parent = artw_sub
    artw_prosub.resource_type = sub_rt
    artw_prosub.general_unit_type = None #gen_share_typ
    artw_prosub.save()
    #raise ValidationError("The project sub_rt has not an ocp_artwork_type ! "+str(rt))

    #elif not sub_rt.ocp_artwork_type.rel_nonmaterial_type:
    #    raise ValidationError("The project sub_rt.ocp_artwork_type has not a rel_nonmaterial_type ! "+str(rt.ocp_artwork_type))
    #elif not sub_rt.ocp_artwork_type.rel_nonmaterial_type.general_unit_type:
    #    raise ValidationError("The project sub_rt.ocp_artwork_type.rel_nonmaterial_type has not a general_unit_type ! "+str(sub_rt.ocp_artwork_type.rel_nonmaterial_type))
    #else:
    #    pass

    gate_keys = project.active_payment_options_obj()
    for obj in gate_keys:
        gatefv = None
        parent_rectyp = None
        slug = None
        nome = None
        ob = obj[0]
        if ob == 'transfer' or ob == 'ccard' or ob == 'debit' or ob == 'cash' or ob == 'botcw':
            slug = 'fiat'
            nome = 'Fiat'
            title = 'Fiat-currency'
        elif ob == 'faircoin':
            slug = 'fair'
            nome = 'Fair'
            title = 'Faircoin'
        elif ob in settings.CRYPTOS:
            slug = 'crypto'
            nome = 'Crypto'
            title = 'Cryptocoins'
        #elif ob == 'share':
        #    slug = 'share'
        #    nome = 'Shares'
        #    title = 'Shares'
        #    gatefv = shrfv
        #    continue # the share-buy et tree is already there
        else:
            raise ValidationError("Payment gateway not known: "+str(ob))

        if not gatefv:
            gatefv, created = FacetValue.objects.get_or_create(value=nome+" currency", facet=curfacet)
            if created:
                print("- created FacetValue: '"+nome+" currency'")
                loger.info("- created FacetValue: '"+nome+" currency'")

        etfiats = ExchangeType.objects.filter(name=title+" Economy")
        if etfiats:
            etfiat = etfiats[0]
            for tt in etfiat.transfer_types.all():
                print("- delete tt? "+str(tt))
                loger.info("- delete tt? "+str(tt))
                if tt.is_deletable():
                    tt.delete()
            print("- delete etfiat? "+str(etfiat))
            loger.info("- delete etfiat? "+str(etfiat))
            if etfiat.is_deletable():
                etfiat.delete()

        #  Ocp_Record_Type  branch
        parent_rectyps = Ocp_Record_Type.objects.filter(clas=slug+"_economy")
        if not parent_rectyps:
            parent_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=title+" Economy")
        if parent_rectyps:
            if len(parent_rectyps) > 1:
                raise ValidationError("There are more than 1 Ocp_Record_Type named: '"+title+" Economy'")
            parent_rectyp = parent_rectyps[0]
            #print("- edited Ocp_Record_Type: '"+title+" Economy:'")
        else:
            parent_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                name_en=title+" Economy:",
                clas=slug+"_economy",
                parent=ocpext
            )
            if created:
                print("- created Ocp_Record_Type: '"+title+" Economy:'")
                loger.info("- created Ocp_Record_Type: '"+title+" Economy:'")
        parent_rectyp.name_en = title+" Economy:"
        parent_rectyp.parent = ocpext
        parent_rectyp.clas = slug+"_economy"
        parent_rectyp.exchange_type = None
        parent_rectyp.save()

        #   Buy  sub-branch
        parent_rectypbuy, created = Ocp_Record_Type.objects.get_or_create(
            name_en=slug+" Buy",
            parent=parent_rectyp
        )
        if created:
            print("- created Ocp_Record_Type: '"+slug+" Buy'")
            loger.info("- created Ocp_Record_Type: '"+slug+" Buy'")
        parent_rectypbuy.clas = "buy"
        parent_rectypbuy.save()


        #   G e n e r i c    B u y    N o n - m a t e r i a l

        #  Ocp_Record_Type
        parent_rectypbuy_nons = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-Buy Non-material resources")
        if not parent_rectypbuy_nons:
            parent_rectypbuy_nons = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy Non-materials")
        if parent_rectypbuy_nons:
            parent_rectypbuy_non = parent_rectypbuy_nons[0]
        else:
            parent_rectypbuy_non, created = Ocp_Record_Type.objects.get_or_create(
                name_en=slug+"-buy Non-materials",
                parent=parent_rectypbuy
            )
            if created:
                print("- created Ocp_Record_Type: '"+slug+"-buy Non-materials'")
                loger.info("- created Ocp_Record_Type: '"+slug+"-buy Non-materials'")
        parent_rectypbuy_non.name_en = slug+"-buy Non-materials"
        parent_rectypbuy_non.parent = parent_rectypbuy
        parent_rectypbuy_non.ocpRecordType_ocp_artwork_type = Ocp_Artwork_Type.objects.get(clas="Nonmaterial")
        #parent_rectypbuy_non.save()

        #  ExchangeType
        etfiat_nons = ExchangeType.objects.filter(name__icontains=slug+"-Buy Non-material resources")
        if not etfiat_nons:
            etfiat_nons = ExchangeType.objects.filter(name=slug+"-buy Non-materials")
        if etfiat_nons:
            if len(etfiat_nons) > 1:
                raise ValidationError("There are more than 1 ExchangeType with the name: '"+slug+"-buy Non-materials'")
            etfiat_non = etfiat_nons[0]
        else:
            etfiat_non, created = ExchangeType.objects.get_or_create(
                name=slug+"-buy Non-materials")
            if created:
                print("- created ExchangeType: '"+slug+"-buy Non-materials'")
                loger.info("- created ExchangeType: '"+slug+"-buy Non-materials'")
        etfiat_non.name = slug+"-buy Non-materials"
        etfiat_non.use_case = usecas
        etfiat_non.save()

        parent_rectypbuy_non.exchange_type = etfiat_non
        parent_rectypbuy_non.save()

        ##  TransferType  ->  pay
        ttpays = TransferType.objects.filter(exchange_type=etfiat_non, is_currency=True)
        if ttpays:
            if len(ttpays) > 1:
                raise ValidationError("There are more than 1 TransferType with is_currency for the ET : "+str(etfiat_non))
            ttpay = ttpays[0]
        else:
            ttpay, created = TransferType.objects.get_or_create(
                name="Give the payment of the Non-material ("+slug+")",
                exchange_type=etfiat_non
                #give_agent_is_context=True,
            )
            if created:
                print("- created TransferType: 'Give the payment of the Non-material ("+slug+")'")
                loger.info("- created TransferType: 'Give the payment of the Non-material ("+slug+")'")

        ttpay.name = "Give the payment of the Non-material ("+slug+")"
        ttpay.exchange_type = etfiat_non
        ttpay.sequence = 1
        ttpay.give_agent_is_context = False
        ttpay.receive_agent_is_context = True
        ttpay.is_reciprocal = True
        ttpay.is_currency = True
        ttpay.inherit_types =  False
        ttpay.is_to_distribute = True
        ttpay.is_contribution = False
        ttpay.can_create_resource = False
        ttpay.save()

        ###  TransferTypeFacetValue  ->  pay  ->  gatefv
        for fv in ttpay.facet_values.all():
            if not fv.facet_value == gatefv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttpay,
            facet_value=gatefv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))
            loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))

        ##  TransferType  ->  receive
        ttnons = TransferType.objects.filter(exchange_type=etfiat_non, inherit_types=True)
        if ttnons:
            if len(ttnons) > 1:
                raise ValidationError("There are more than 1 TransferType with inherit_types for the ET : "+str(etfiat_non))
            ttnon = ttnons[0]
        else:
            ttnon, created = TransferType.objects.get_or_create(
                name="Receive the Non-material",
                exchange_type=etfiat_non
                #receive_agent_is_context=True,
            )
            if created:
                print("- created TransferType: 'Receive the Non-material' ("+slug+")")
                loger.info("- created TransferType: 'Receive the Non-material' ("+slug+")")

        ttnon.name = "Receive the Non-material"
        ttnon.exchange_type = etfiat_non
        ttnon.sequence = 2
        ttnon.give_agent_is_context = True
        ttnon.receive_agent_is_context = False
        ttnon.is_reciprocal = False
        ttnon.is_currency = False
        ttnon.inherit_types = True
        ttnon.is_to_distribute = False
        ttnon.is_contribution = False
        ttnon.can_create_resource = False
        ttnon.save()

        ###  TransferTypeFacetValue  ->  receive  ->  Nonmaterial
        nonfvs = FacetValue.objects.filter(facet=nonfacet)
        for fv in nonfvs:
            ttnonfv, created = TransferTypeFacetValue.objects.get_or_create(
                transfer_type=ttnon,
                facet_value=fv)
            if created:
                print("- created TransferTypeFacetValue: "+str(ttnon)+" <> "+str(fv))
                loger.info("- created TransferTypeFacetValue: "+str(ttnon)+" <> "+str(fv))

        tts = etfiat_non.transfer_types.all()
        if not len(tts) == 2:
            print("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))
            loger.info("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))
            raise ValidationError("The ExchangeType '"+slug+"-buy Non-materials' has not 2 transfer types: "+str(tts))


        #   S U B S C R I P T I O N S    B U Y

        fiat_rectyps = Ocp_Record_Type.objects.filter(name_en=slug+"-buy Project Subscriptions")
        if fiat_rectyps:
            if len(fiat_rectyps) > 1:
                raise ValidationError("There's more than 1 Ocp_Record_Type named: '"+slug+"-buy Project Subscriptions'")
            fiat_rectyp = fiat_rectyps[0]
        else:
            fiat_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                name_en=slug+"-buy Project Subscriptions",
                parent=parent_rectypbuy_non
            )
            if created:
                print("- created Ocp_Record_Type: '"+slug+"-buy Project Subscriptions'")
                loger.info("- created Ocp_Record_Type: '"+slug+"-buy Project Subscriptions'")
        fiat_rectyp.name_en = slug+"-buy Project Subscriptions"
        fiat_rectyp.parent = parent_rectypbuy_non
        fiat_rectyp.ocpRecordType_ocp_artwork_type = Ocp_Artwork_Type.objects.get(clas="subscriptions")

        #  ExchangeType shares
        etfiat_shrs = ExchangeType.objects.filter(name__icontains=slug+"-buy Project Subscriptions")
        if not etfiat_shrs:
            etfiat_shrs = ExchangeType.objects.filter(name__icontains=slug+"-buy Subscriptions")
        if etfiat_shrs:
            if len(etfiat_shrs) > 1:
                raise ValidationError("There's more than 1 ExchangeType! : "+str(etfiat_shrs))
            etfiat_shr = etfiat_shrs[0]
        else:
            etfiat_shr, created = ExchangeType.objects.get_or_create(
                name=slug+"-buy Project Subscriptions")
            if created:
                print("- created ExchangeType: '"+slug+"-buy Project Subscriptions'")
                loger.info("- created ExchangeType: '"+slug+"-buy Project Subscriptions'")

        etfiat_shr.name = slug+"-buy Project Subscriptions"
        etfiat_shr.use_case = usecas
        etfiat_shr.save()

        fiat_rectyp.exchange_type = etfiat_shr
        fiat_rectyp.save()

        ##  TransferType  ->  pay
        ttfiats = TransferType.objects.filter(exchange_type=etfiat_shr, is_currency=True)
        if ttfiats:
            if len(ttfiats) > 1:
                raise ValidationError("There's more than 1 TransferType with is_currency for the ET: "+str(etfiat_shr))
            ttfiat = ttfiats[0]
        else:
            ttfiat, created = TransferType.objects.get_or_create(
                name="Payment of the Subscription ("+slug+")",
                exchange_type=etfiat_shr,
            )
            if created:
                print("- created TransferType: 'Payment of the Subscription ("+slug+")'")
                loger.info("- created TransferType: 'Payment of the Subscription ("+slug+")'")
        ttfiat.name = "Payment of the Subscription ("+slug+")"
        ttfiat.sequence = 1
        ttfiat.exchange_type = etfiat_shr
        ttfiat.give_agent_is_context = False
        ttfiat.receive_agent_is_context = True
        ttfiat.is_reciprocal = True
        ttfiat.is_currency = True
        ttfiat.inherit_types =  False
        ttfiat.is_to_distribute = True
        ttfiat.is_contribution = False
        ttfiat.can_create_resource = False
        ttfiat.save()

        ###  TransferTypeFacetValue  ->  pay  ->  gatefv
        for fv in ttfiat.facet_values.all():
            if not fv.facet_value == gatefv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttfiat,
            facet_value=gatefv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttfiat)+" <> "+str(gatefv))
            loger.info("- created TransferTypeFacetValue: "+str(ttfiat)+" <> "+str(gatefv))

        ##  TransferType  ->  receive
        ttshrs = TransferType.objects.filter(exchange_type=etfiat_shr, inherit_types=True)
        if ttshrs:
            if len(ttshrs) > 1:
                raise ValidationError("There's more than 1 TransferType with inherit_types in the ET: "+str(etfiat_shr))
            ttshr = ttshrs[0]
        else:
            ttshr, created = TransferType.objects.get_or_create(
                name="Activate the Subscription",
                exchange_type=etfiat_shr,
                #receive_agent_is_context=True,
            )
            if created:
                print("- created TransferType: 'Activate the Subscription' ("+slug+")")
                loger.info("- created TransferType: 'Activate the Subscription' ("+slug+")")
        ttshr.name = "Activate the Subscription"
        ttshr.exchange_type = etfiat_shr
        ttshr.sequence = 2
        ttshr.give_agent_is_context = True
        ttshr.receive_agent_is_context = False
        ttshr.is_reciprocal = False
        ttshr.is_currency = False
        ttshr.inherit_types =  True
        ttshr.is_to_distribute = False
        ttshr.is_contribution = False
        ttshr.can_create_resource = False
        ttshr.save()

        ###  TransferTypeFacetValue  ->  receive  ->  shares
        for fv in ttshr.facet_values.all():
            if not fv.facet_value == subfv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttnonfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttshr,
            facet_value=subfv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(subfv))
            loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(subfv))

        tts = etfiat_shr.transfer_types.all()
        if len(tts) > 2:
            print("The ExchangeType '"+slug+"-buy Project Subscriptions' has more than 2 transfer types: "+str(tts))
            loger.info("The ExchangeType '"+slug+"-buy Project Subscriptions' has more than 2 transfer types: "+str(tts))
            raise ValidationError("The ExchangeType '"+slug+"-buy Project Subscriptions' has more than 2 transfer types: "+str(tts))



        #   P R O J E C T    B U Y    S U B S C R I P T I O N S

        slug_ets = ExchangeType.objects.filter(name__icontains=slug+"-buy "+str(project.compact_name())+" Subscription")
        if not slug_ets:
            slug_ets = ExchangeType.objects.filter(name__icontains=slug+"-buy "+str(project.agent.name)+" Subscription")
        if not slug_ets:
            slug_ets = ExchangeType.objects.filter(name__icontains=slug+"-buy "+str(project.agent.name_en)+" Subscription")

        if slug_ets:
            if len(slug_ets) > 1:
                raise ValidationError("There's more than 1 ExchangeType named: '"+slug+"-buy "+str(project.compact_name())+" Subscription")
            slug_et = slug_ets[0]
        else:
            slug_et, created = ExchangeType.objects.get_or_create(
                name=slug+"-buy "+str(project.compact_name())+" Subscription"
            )
            if created:
                print("- created ExchangeType: '"+slug+"-buy "+str(project.compact_name())+" Subscription'")
                loger.info("- created ExchangeType: '"+slug+"-buy "+str(project.compact_name())+" Subscription'")
        slug_et.name = slug+"-buy "+str(project.compact_name())+" Subscription"
        slug_et.use_case = usecas
        slug_et.context_agent = project.agent
        slug_et.save()

        # TransferType  ->  pay
        ttpays = TransferType.objects.filter(exchange_type=slug_et, is_currency=True)
        if ttpays:
            if len(ttpays) > 1:
                raise ValidationError("There's more than 1 TransferType with is_currency for the ET : "+str(slug_et))
            ttpay = ttpays[0]
        else:
            ttpay.pk = None
            ttpay.id = None
            print("- created TransferType: 'Payment of the "+str(project.agent.name_en)+" subscription ("+slug+")'")
            loger.info("- created TransferType: 'Payment of the "+str(project.agent.name_en)+" subscription ("+slug+")'")
        ttpay.name = "Payment of the "+str(project.agent.name_en)+" subscription ("+slug+")"
        ttpay.exchange_type = slug_et
        ttpay.sequence = 1
        ttpay.give_agent_is_context = False
        ttpay.receive_agent_is_context = True
        ttpay.is_reciprocal = True
        ttpay.is_currency = True
        ttpay.inherit_types =  False
        ttpay.is_to_distribute = True
        ttpay.is_contribution = False
        ttpay.can_create_resource = False
        ttpay.save()

        for fv in ttpay.facet_values.all():
            if not fv.facet_value == gatefv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttpayfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttpay,
            facet_value=gatefv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))
            loger.info("- created TransferTypeFacetValue: "+str(ttpay)+" <> "+str(gatefv))

        # TransferType  ->  receive  ->  share
        ttshrs = TransferType.objects.filter(exchange_type=slug_et, inherit_types=True)
        if not ttshrs:
            ttshrs = TransferType.objects.filter(exchange_type=slug_et, is_currency=False)
        if ttshrs:
            if len(ttshrs) > 1:
                raise ValidationError("There are more than 1 TransferType with inherit_types (or not is_currency) for the ET : "+str(slug_et))
            ttshr = ttshrs[0]
        else:
            ttshr.pk = None
            ttshr.id = None
            print("- created TransferType: 'Activate the "+str(project.agent.name_en)+" subscription' ("+slug+")")
            loger.info("- created TransferType: 'Activate the "+str(project.agent.name_en)+" subscription' ("+slug+")")
        ttshr.name = "Activate the "+str(project.agent.name_en)+" subscription"
        ttshr.exchange_type = slug_et
        ttshr.sequence = 2
        ttshr.give_agent_is_context = True
        ttshr.receive_agent_is_context = False
        ttshr.is_reciprocal = False
        ttshr.is_currency = False
        ttshr.inherit_types =  True
        ttshr.is_to_distribute = False
        ttshr.is_contribution = False
        ttshr.can_create_resource = False
        ttshr.save()

        for fv in ttshr.facet_values.all():
            if not fv.facet_value == subfv:
                print("- delete fv: "+str(fv))
                loger.info("- delete fv: "+str(fv))
                fv.delete()
        ttshrfv, created = TransferTypeFacetValue.objects.get_or_create(
            transfer_type=ttshr,
            facet_value=subfv)
        if created:
            print("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(subfv))
            loger.info("- created TransferTypeFacetValue: "+str(ttshr)+" <> "+str(subfv))


        tts = slug_et.transfer_types.all()
        if not len(tts) == 2:
            raise ValidationError("WARNING: The ExchangeType '"+str(slug_et)+"' don't has 2 TransferType's: "+str(tts))


        pro_sub_rectyps = Ocp_Record_Type.objects.filter(exchange_type=slug_et)
        if not pro_sub_rectyps:
            pro_sub_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy "+str(project.compact_name())+" Subscriptions")
        if not pro_sub_rectyps:
            pro_sub_rectyps = Ocp_Record_Type.objects.filter(name_en__icontains=slug+"-buy "+str(project.agent.name_en)+" Subscriptions")
        if pro_sub_rectyps:
            if len(pro_sub_rectyps) > 1:
                raise ValidationError("There are more than 1 Ocp_Record_Type with same name: "+str(pro_sub_rectyps))
            pro_sub_rectyp = pro_sub_rectyps[0]
        else:
            pro_sub_rectyp, created = Ocp_Record_Type.objects.get_or_create(
                name_en=slug+"-buy "+str(project.compact_name())+" Subscriptions",
                parent=fiat_rectyp
            )
            if created:
                print("- created Ocp_Record_Type: '"+slug+"-buy "+str(project.agent.name_en)+" Subscriptions'")
                loger.info("- created Ocp_Record_Type: '"+slug+"-buy "+str(project.agent.name_en)+" Subscriptions'")
        pro_sub_rectyp.name_en = slug+"-buy "+str(project.compact_name())+" Subscriptions"
        pro_sub_rectyp.ocpRecordType_ocp_artwork_type = artw_prosub #sub_rt.ocp_artwork_type
        pro_sub_rectyp.parent = fiat_rectyp
        pro_sub_rectyp.exchange_type = slug_et
        pro_sub_rectyp.save()

    print("---------- end create_subscription_exchange_types ("+str(agent)+") ----------")
    loger.info("---------- end create_subscription_exchange_types ("+str(agent)+") ----------")

    #return exchanges_all(request, project.agent.id)
    return HttpResponseRedirect('/%s/%s/'
                % ('work/agent', project.agent.id))




#    P R O J E C T   R E S O U R C E S


def project_all_resources(request, agent_id):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    #contexts = agent.related_all_contexts()
    #contexts.append(agent)
    #context_ids = [c.id for c in contexts]
    #other_contexts = EconomicAgent.objects.all().exclude(id__in=context_ids)
    rts = list(set([arr.resource.resource_type for arr in agent.resource_relationships()]))
    rt_ids = [arr.resource.id for arr in agent.resource_relationships()]
    fcr = agent.faircoin_resource()
    if fcr:
      if not fcr.id in rt_ids:
        rt_ids.append(fcr.id)
      if not fcr.resource_type in rts:
        rts.append(fcr.resource_type)
    #rts = list(set([arr.resource.resource_type for arr in AgentResourceRole.objects.filter(agent=agent)])) #__in=contexts)]))
    #resources = EconomicResource.objects.select_related().filter(quantity__gt=0).order_by('resource_type')
    #rts = EconomicResourceType.objects.all().exclude(context_agent__in=other_contexts)
    for rt in rts:
      rt.items = []
      for r in rt.resources.filter(pk__in=rt_ids):
        #if r.agent_resource_roles.all()[0].agent == agent: #in contexts:
          rt.items.append(r)

    resource_types = []
    facets = Facet.objects.all()
    select_all = True
    selected_values = "all"
    fvs = []
    if request.method == "POST":
        selected_values = request.POST.get("categories", "all");
        if selected_values:
            vals = selected_values.split(",")
            if vals[0] == "all":
                select_all = True
                #resources = EconomicResource.objects.select_related().filter(quantity__gt=0).order_by('resource_type')
                for rt in rts:
                    if rt.onhand_qty()>0:
                        resource_types.append(rt)
                if fcr and not fcr.resource_type in resource_types:
                    resource_types.append(fcr.resource_type)
            else:
                select_all = False
                #resources = EconomicResource.objects.select_related().filter(quantity__gt=0, resource_type__category__name__in=vals).order_by('resource_type')

                for val in vals:
                    val_split = val.split("_")
                    tide = val_split[1]
                    otyp = None
                    try:
                        otyp = Ocp_Artwork_Type.objects.get(id=tide)
                    except:
                      try:
                          otyp = Ocp_Skill_Type.objects.get(id=tide)
                      except:
                          pass
                    if otyp:
                        if otyp.facet_value:
                           fvs.append(otyp.facet_value)
                        elif otyp.resource_type:
                            if otyp.resource_type.facets.all():
                                fv = otyp.resource_type.facets.all()[0].facet_value
                                fvs.append(fv)

                rts = select_resource_types(fvs)
                for rt in rts:
                    if rt.onhand_qty()>0:
                        rt.items = []
                        for r in rt.resources.filter(pk__in=rt_ids):
                            rt.items.append(r)
                        if rt.items:
                            resource_types.append(rt)
                #resource_types.sort(key=lambda rt: rt.label())
    else:
        for rt in rts:
            #if rt.onhand_qty()>0:
            if not rt in resource_types:
              resource_types.append(rt)
            if rt.facets.count():
              if rt.facets.all():
                fvs.append(rt.facets.all()[0].facet_value) # add first facetvalue
        if fcr and not fcr.resource_type in resource_types:
            resource_types.append(fcr.resource_type)

    Rtype_form = NewResourceTypeForm(agent=agent, data=request.POST or None)

    return render(request, "work/project_resources.html", {
        #"resources": resources,
        "resource_types": resource_types,
        "facets": facets,
        "facetvalues": fvs,
        "select_all": select_all,
        "selected_values": selected_values,
        "photo_size": (128, 128),
        "help": get_help("inventory"),
        'agent': agent,
        'Rtype_tree': Ocp_Artwork_Type.objects.all(),
        'Rtype_form': Rtype_form,
        'Stype_tree': Ocp_Skill_Type.objects.all(),
    })


"""def new_resource_type(request, agent_id, Rtype):
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    if not (agent == user_agent or user_agent in agent.managers()):
        return render(request, 'work/no_permission.html')

    # process savings TODO

    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/agent', agent.id, 'resources'))"""



def project_resource(request, agent_id, resource_id):
    resource = get_object_or_404(EconomicResource, id=resource_id)
    agent = get_object_or_404(EconomicAgent, id=agent_id)
    user_agent = get_agent(request)
    user_agent.managed_rts = []
    for ag in user_agent.managed_projects():
        try:
            rts = ag.project.rts_with_clas()
            for rt in rts:
                if not rt in user_agent.managed_rts:
                    user_agent.managed_rts.append(rt)
        except:
            pass

    if not (agent == user_agent or user_agent in agent.managers() or request.user.is_superuser or resource.resource_type in user_agent.managed_rts ):
        return render(request, 'work/no_permission.html')

    RraFormSet = modelformset_factory(
        AgentResourceRole,
        form=ResourceRoleContextAgentForm,
        can_delete=True,
        extra=2,
        )
    role_formset = RraFormSet(
        prefix="role",
        queryset=resource.agent_resource_roles.all()
        )

    if not resource.is_digital_currency_resource():
        process_add_form = None
        order_form = None
        process = None
        pattern = None
        if resource.producing_events():
            process = resource.producing_events()[0].process
            pattern = None
            if process:
                pattern = process.process_pattern
        else:
            if agent:
                form_data = {'name': 'Create ' + resource.identifier, 'start_date': resource.created_date, 'end_date': resource.created_date}
                process_add_form = AddProcessFromResourceForm(form_data)
                if resource.resource_type.recipe_is_staged():
                    init={"start_date": datetime.date.today(),}
                    order_form = StartDateAndNameForm(initial=init)

    if request.method == "POST":
        process_save = request.POST.get("process-save")
        if process_save:
            process_add_form = AddProcessFromResourceForm(data=request.POST)
            if process_add_form.is_valid():
                process = process_add_form.save(commit=False)
                process.started = process.start_date
                process.finished = True
                process.created_by = request.user
                process.save()
                event = EconomicEvent()
                event.context_agent = process.context_agent
                event.event_date = process.end_date
                event.event_type = process.process_pattern.event_type_for_resource_type("out", resource.resource_type)
                event.process = process
                event.resource_type = resource.resource_type
                event.quantity = resource.quantity
                event.unit_of_quantity = resource.unit_of_quantity()
                event.resource = resource
                event.to_agent = event.context_agent
                event.from_agent = event.context_agent
                event.created_by = request.user
                event.save()
                return HttpResponseRedirect('/%s/%s/%s/%s'
                    % ('work/agent', agent.id, 'resource', resource.id))
    if resource.is_digital_currency_resource():
        #return manage_faircoin_account(request, resource.id)
        #HttpResponseRedirect(reverse('manage_faircoin_account', kwargs={'resource_id': resource.id}))
        return HttpResponseRedirect('/%s/%s/'
            % ('faircoin/manage-faircoin-account', resource_id))
    else:
        return render(request, "work/project_resource.html", {
            "resource": resource,
            "photo_size": (128, 128),
            "process_add_form": process_add_form,
            "order_form": order_form,
            "role_formset": role_formset,
            "agent": agent,
            "user_agent": user_agent,
        })

@login_required
def change_resource(request, agent_id, resource_id):
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        agent = get_object_or_404(EconomicAgent, pk=agent_id)
        v_help = None
        if resource.resource_type.unit_of_use:
            v_help = "give me a usable widget"
        form = EconomicResourceForm(data=request.POST, instance=resource, vpu_help=v_help)
        if form.is_valid():
            data = form.cleaned_data
            resource = form.save(commit=False)
            resource.changed_by=request.user
            resource.save()
            if not resource.resource_type.is_virtual_account() or request.user.is_superuser:
                RraFormSet = modelformset_factory(
                    AgentResourceRole,
                    form=ResourceRoleContextAgentForm,
                    can_delete=True,
                    extra=2,
                    )
                role_formset = RraFormSet(
                    prefix="role",
                    queryset=resource.agent_resource_roles.all(),
                    data=request.POST
                    )
                #import pdb; pdb.set_trace()
                if role_formset.is_valid():
                    saved_formset = role_formset.save(commit=False)
                    for role in saved_formset:
                        role.resource = resource
                        role.save()
            return HttpResponseRedirect('/%s/%s/%s/%s'
                % ('work/agent', agent.id, 'resources', resource_id))
        else:
            raise ValidationError(form.errors)



from mptt.exceptions import InvalidMove
from mptt.forms import MoveNodeForm

def movenode(request, node_id): # still not used
    rtype = get_object_or_404(Artwork_Type, pk=node_id)
    if request.method == 'POST':
        form = MoveNodeForm(rtype, request.POST)
        if form.is_valid():
            try:
                rtype = form.save()
                return HttpResponseRedirect(rtype.get_absolute_url())
            except InvalidMove:
                pass
    else:
        form = MoveNodeForm(rtype)

    return render(request, 'work/project_resources.html', {
        'form': form,
        'rtype': rtype,
        'Rtype_tree': Ocp_Artwork_Type.objects.all(),
        #'agent': agent,
    })







#    S I M P L E   T A S K S

@login_required
def my_tasks(request):
    my_work = []
    #my_skillz = []
    other_wip = []
    agent = get_agent(request)
    #if agent:
    context_ids = [c.id for c in agent.related_contexts()]
    my_work = Commitment.objects.unfinished().filter(
        event_type__relationship="work",
        from_agent=agent)
    #skill_ids = agent.resource_types.values_list('resource_type__id', flat=True)
    #my_skillz = Commitment.objects.unfinished().filter(
    #    from_agent=None,
    #    context_agent__id__in=context_ids,
    #    event_type__relationship="todo",
    #    resource_type__id__in=skill_ids)
    #other_unassigned = Commitment.objects.unfinished().filter(
    #    from_agent=None,
    #    context_agent__id__in=context_ids,
    #    event_type__relationship="work").exclude(resource_type__id__in=skill_ids)
    todos = Commitment.objects.unfinished().filter(
        from_agent=None,
        context_agent__id__in=context_ids,
        event_type__relationship="todo")
    #else:
    #    other_unassigned = Commitment.objects.unfinished().filter(
    #        from_agent=None,
    #        event_type__relationship="work")
    my_todos = Commitment.objects.todos().filter(from_agent=agent)
    init = {"from_agent": agent,}
    patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
    pattern_id = 0
    if patterns:
        pattern = patterns[0].pattern
        pattern_id = pattern.id
        todo_form = WorkTodoForm(agent=agent, pattern=pattern, initial=init)
    else:
        todo_form = WorkTodoForm(agent=agent, initial=init)
    #work_now = settings.USE_WORK_NOW
    return render(request, "work/my_tasks.html", {
        "agent": agent,
        "my_work": my_work,
        #"my_skillz": my_skillz,
        #"other_unassigned": other_unassigned,
        "my_todos": my_todos,
        "todo_form": todo_form,
        "pattern_id": pattern_id,
        #"work_now": work_now,
        "help": get_help("proc_log"),
    })


@login_required
def take_new_tasks(request):
    #task_bugs change
    # this method needs some serious house cleaning...
    # to do later, see github issue cited below
    #my_work = []
    my_skillz = []
    other_wip = []
    agent = get_agent(request)
    #if agent:
    context_ids = [c.id for c in agent.related_contexts()]
    #my_work = Commitment.objects.unfinished().filter(
    #    event_type__relationship="todo",
    #    from_agent=agent)
    skill_ids = agent.resource_types.values_list('resource_type__id', flat=True)
    my_skillz = Commitment.objects.unfinished().filter(
        from_agent=None,
        context_agent__id__in=context_ids,
        #task_bugs change
        #event_type__relationship="work",
        event_type__relationship="todo",
        resource_type__id__in=skill_ids)
    #other_unassigned = Commitment.objects.unfinished().filter(
    #    from_agent=None,
    #    context_agent__id__in=context_ids,
    #    event_type__relationship="work").exclude(resource_type__id__in=skill_ids)
    todos = Commitment.objects.unfinished().filter(
        from_agent=None,
        context_agent__id__in=context_ids,
        event_type__relationship="todo")
    #else:
    #    other_unassigned = Commitment.objects.unfinished().filter(
    #        from_agent=None,
    #        event_type__relationship="work")
    my_todos = Commitment.objects.todos().filter(from_agent=agent)
    init = {"from_agent": agent,}
    patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
    if patterns:
        pattern = patterns[0].pattern
        todo_form = WorkTodoForm(agent=agent, pattern=pattern, initial=init)
    else:
        todo_form = WorkTodoForm(agent=agent, initial=init)
    #work_now = settings.USE_WORK_NOW
    #task_bugs change
    # see https://github.com/FreedomCoop/valuenetwork/issues/263
    # process_tasks shd be filled
    process_tasks = []
    return render(request, "work/take_new_tasks.html", {
        "agent": agent,
        #"my_work": my_work,
        "process_tasks": process_tasks,
        "my_skillz": my_skillz,
        #"other_unassigned": other_unassigned,
        #"my_todos": my_todos,
        #"todo_form": todo_form,
        #"work_now": work_now,
        "help": get_help("proc_log"),
    })


@login_required
def add_todo(request):
    if request.method == "POST":
        patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
        if patterns:
            pattern = patterns[0].pattern
            form = TodoForm(data=request.POST, pattern=pattern)
        else:
            form = TodoForm(request.POST)
        next = request.POST.get("next")
        agent = get_agent(request)
        et = None
        ets = EventType.objects.filter(
            relationship='todo')
        if ets:
            et = ets[0]
        if et:
            if form.is_valid():
                data = form.cleaned_data
                todo = form.save(commit=False)
                todo.to_agent=agent
                todo.event_type=et
                todo.quantity = Decimal("0")
                todo.unit_of_quantity=todo.resource_type.unit
                todo.save()
                if notification:
                    if todo.from_agent:
                        if todo.from_agent != agent:
                            site_name = get_site_name(request)
                            user = todo.from_agent.user()
                            if user:
                                notification.send(
                                    [user.user,],
                                    "valnet_new_todo",
                                    {"description": todo.description,
                                    "creator": agent,
                                    "site_name": site_name,
                                    "current_site": request.get_host(),
                                    }
                                )

    return HttpResponseRedirect(next)


def json_get_context_resource_types(request, context_id, pattern_id=None):
    context_agent = get_object_or_404(EconomicAgent, pk=context_id)
    if pattern_id:
        pattern = get_object_or_404(ProcessPattern, pk=pattern_id)
    else:
        pattern = None
    if pattern:
        rts = pattern.todo_resource_types()
        if not rts:
            rts = pattern.work_resource_types()
    else:
        rts = EconomicResourceType.objects.filter(behavior="work")
    try:
        if context_agent.project.resource_type_selection == "project":
            rts = rts.filter(context_agent=context_agent)
        else:
            rts = rts.filter(Q(context_agent=context_agent)|Q(context_agent=None))
    except:
        rts = rts.filter(context_agent=None)
    json = serializers.serialize("json", rts, fields=('name'))
    return HttpResponse(json, content_type='application/json')


#    P R O C E S S   T A S K S

@login_required
def project_work(request):
    agent = get_agent(request)
    #task_bugs change
    projects = agent.related_contexts() #managed_projects()
    if not agent or agent.is_participant_candidate():
        return render(request, 'work/no_permission.html')
    next = "/work/project-work/"
    context_id = 0
    start = datetime.date.today() - datetime.timedelta(days=30)
    end = datetime.date.today() + datetime.timedelta(days=90)
    init = {"start_date": start, "end_date": end}
    date_form = DateSelectionForm(initial=init, data=request.POST or None)
    ca_form = WorkProjectSelectionFormOptional(data=request.POST or None, context_agents=projects)
    chosen_context_agent = None
    patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
    pattern_id = 0
    if patterns:
        pattern = patterns[0].pattern
        pattern_id = pattern.id
        todo_form = WorkTodoForm(pattern=pattern, agent=agent)
    else:
        todo_form = WorkTodoForm(agent=agent)
    if request.method == "POST":
        if date_form.is_valid():
            dates = date_form.cleaned_data
            start = dates["start_date"]
            end = dates["end_date"]
            if ca_form.is_valid():
                proj_data = ca_form.cleaned_data
                proj_id = proj_data["context_agent"]
                if proj_id:
                    context_id = proj_id
                    chosen_context_agent = EconomicAgent.objects.get(id=proj_id)

    start_date = start.strftime('%Y_%m_%d')
    end_date = end.strftime('%Y_%m_%d')
    processes, context_agents = assemble_schedule(start, end, chosen_context_agent)

    todos = Commitment.objects.todos().filter(due_date__range=(start, end))
    if chosen_context_agent:
        todos = todos.filter(context_agent=chosen_context_agent)
    my_project_todos = []
    for todo in todos:
        if todo.context_agent in projects:
            my_project_todos.append(todo)
    return render(request, "work/project_work.html", {
        "agent": agent,
        "context_agents": context_agents,
        "all_processes": projects,
        "date_form": date_form,
        "start_date": start_date,
        "end_date": end_date,
        "context_id": context_id,
        "todo_form": todo_form,
        "ca_form": ca_form,
        "todos": my_project_todos,
        "pattern_id": pattern_id,
        "next": next,
        "help": get_help("project_work"),
    })


@login_required
def work_change_process_sked_ajax(request):
    proc_id = request.POST["proc_id"]
    process = Process.objects.get(id=proc_id)
    form = ScheduleProcessForm(prefix=proc_id,instance=process,data=request.POST)
    if form.is_valid():
        data = form.cleaned_data
        process.start_date = data["start_date"]
        process.end_date = data["end_date"]
        process.notes = data["notes"]
        process.save()
        return_data = "OK"
        return HttpResponse(return_data, content_type="text/plain")
    else:
        return HttpResponse(form.errors, content_type="text/json-comment-filtered")

@login_required
def work_change_process(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    if request.method == "POST":
        form = ProcessForm(
            instance=process,
            data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            form.save()
            #next = request.POST.get("next")
            #if next:
            #    return HttpResponseRedirect('/%s/%s/'
            #        % ('work/process-logging', process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def process_logging(request, process_id):
    process = get_object_or_404(Process, id=process_id)
    pattern = process.process_pattern
    context_agent = process.context_agent
    agent = get_agent(request)
    user = request.user
    agent_projects = agent.related_contexts()
    if process.context_agent not in agent_projects:
        return render(request, 'valueaccounting/no_permission.html')
    logger = True
    worker = False
    super_logger = False
    todays_date = datetime.date.today()
    change_process_form = ProcessForm(instance=process)
    add_output_form = None
    add_citation_form = None
    add_consumable_form = None
    add_usable_form = None
    add_work_form = None
    unplanned_work_form = None
    unplanned_cite_form = None
    unplanned_consumption_form = None
    unplanned_use_form = None
    unplanned_output_form = None
    process_expense_form = None
    role_formset = None
    slots = []
    event_types = []
    work_now = settings.USE_WORK_NOW
    to_be_changed_requirement = None
    changeable_requirement = None

    work_reqs = process.work_requirements()
    consume_reqs = process.consumed_input_requirements()
    use_reqs = process.used_input_requirements()
    unplanned_work = process.uncommitted_work_events()

    if agent and pattern:
        slots = pattern.slots()
        event_types = pattern.event_types()
        #if request.user.is_superuser or request.user == process.created_by:
        if request.user.is_staff or request.user == process.created_by:
            logger = True
            super_logger = True
        for req in work_reqs:
            req.changeform = req.change_work_form()
            if agent == req.from_agent:
                logger = True
                worker = True
            init = {"from_agent": agent,
                "event_date": todays_date,
                "is_contribution": True,}
            req.input_work_form_init = req.input_event_form_init(init=init)
        for req in consume_reqs:
            req.changeform = req.change_form()
        for req in use_reqs:
            req.changeform = req.change_form()
        for event in unplanned_work:
            event.changeform = UnplannedWorkEventForm(
                pattern=pattern,
                context_agent=context_agent,
                instance=event,
                prefix=str(event.id))
        role_formset = resource_role_context_agent_formset(prefix="resource")
        produce_et = EventType.objects.get(name="Resource Production")
        change_et = EventType.objects.get(name="Change")
        if "out" in slots:
            output_resource_types = pattern.output_resource_types()
            try:
                if context_agent.project.resource_type_selection == "project":
                    output_resource_types = output_resource_types.filter(context_agent=context_agent)
                else:
                    output_resource_types = output_resource_types.filter(context_agent=None)
            except:
                output_resource_types = output_resource_types.filter(context_agent=None)
            unplanned_output_form = UnplannedOutputForm(prefix='unplannedoutput')
            unplanned_output_form.fields["resource_type"].queryset = output_resource_types
            if logger:
                if change_et in event_types:
                    to_be_changed_requirement = process.to_be_changed_requirements()
                    if to_be_changed_requirement:
                        to_be_changed_requirement = to_be_changed_requirement[0]
                    changeable_requirement = process.changeable_requirements()
                    if changeable_requirement:
                        changeable_requirement = changeable_requirement[0]
                else:
                    add_output_form = ProcessOutputForm(prefix='output')
                    add_output_form.fields["resource_type"].queryset = output_resource_types
        if "work" in slots:
            if agent:
                work_init = {
                    "from_agent": agent,
                    "is_contribution": True,
                }
                work_resource_types = pattern.work_resource_types()
                try:
                    if context_agent.project.resource_type_selection == "project":
                        work_resource_types = work_resource_types.filter(context_agent=context_agent)
                    else:
                        work_resource_types = work_resource_types.filter(context_agent=None)
                except:
                    work_resource_types = work_resource_types.filter(context_agent=None)
                work_unit = None
                if work_resource_types:
                    work_unit = work_resource_types[0].unit
                    #work_init = {"unit_of_quantity": work_unit,}
                    work_init = {
                        "from_agent": agent,
                        "unit_of_quantity": work_unit,
                        "is_contribution": True,
                    }
                    unplanned_work_form = UnplannedWorkEventForm(prefix="unplanned", context_agent=context_agent, initial=work_init)
                    unplanned_work_form.fields["resource_type"].queryset = work_resource_types
                    if logger:
                        work_init = {
                            "from_agent": agent,
                            "unit_of_quantity": work_unit,
                            "is_contribution": True,
                            "due_date": process.end_date,
                        }
                        add_work_form = WorkCommitmentForm(prefix='work', pattern=pattern, initial=work_init)
                        add_work_form.fields["resource_type"].queryset = work_resource_types
                else:
                    unplanned_work_form = UnplannedWorkEventForm(prefix="unplanned", pattern=pattern, context_agent=context_agent, initial=work_init)


        if "cite" in slots:
            cite_unit = None
            if context_agent.unit_of_claim_value:
                cite_unit = context_agent.unit_of_claim_value
            citable_resource_types = pattern.citables_with_resources()
            try:
                if context_agent.project.resource_type_selection == "project":
                    citable_resource_types = citable_resource_types.filter(context_agent=context_agent)
                else:
                    citable_resource_types = citable_resource_types.filter(context_agent=None)
            except:
                citable_resource_types = citable_resource_types.filter(context_agent=None)
            unplanned_cite_form = UnplannedCiteEventForm(prefix='unplannedcite', pattern=None, cite_unit=cite_unit)
            unplanned_cite_form.fields["resource_type"].queryset = citable_resource_types
            if logger:
                add_citation_form = ProcessCitationForm(prefix='citation', pattern=None)
                cite_resource_types = pattern.citable_resource_types()
                try:
                    if context_agent.project.resource_type_selection == "project":
                        cite_resource_types = cite_resource_types.filter(context_agent=context_agent)
                    else:
                        cite_resource_types = cite_resource_types.filter(context_agent=None)
                except:
                    cite_resource_types = cite_resource_types.filter(context_agent=None)
                add_citation_form.fields["resource_type"].queryset = cite_resource_types

        if "consume" in slots:
            unplanned_consumption_form = UnplannedInputEventForm(prefix='unplannedconsumption', pattern=None)
            consumable_resource_types = pattern.consumables_with_resources()
            try:
                if context_agent.project.resource_type_selection == "project":
                    consumable_resource_types = consumable_resource_types.filter(context_agent=context_agent)
                else:
                    consumable_resource_types = consumable_resource_types.filter(context_agent=None)
            except:
                consumable_resource_types = consumable_resource_types.filter(context_agent=None)
            unplanned_consumption_form.fields["resource_type"].queryset = consumable_resource_types
            if logger:
                add_consumable_form = ProcessConsumableForm(prefix='consumable', pattern=None)
                add_consumable_form.fields["resource_type"].queryset = consumable_resource_types

        if "use" in slots:
            unplanned_use_form = UnplannedInputEventForm(prefix='unplannedusable', pattern=None)
            usable_resource_types = pattern.usables_with_resources()
            try:
                if context_agent.project.resource_type_selection == "project":
                    usable_resource_types = usable_resource_types.filter(context_agent=context_agent)
                else:
                    usable_resource_types = usable_resource_types.filter(context_agent=None)
            except:
                usable_resource_types = usable_resource_types.filter(context_agent=None)
            unplanned_use_form.fields["resource_type"].queryset = usable_resource_types
            if logger:
                add_usable_form = ProcessUsableForm(prefix='usable', pattern=None)
                add_usable_form.fields["resource_type"].queryset = usable_resource_types
        #if "payexpense" in slots:
        #    process_expense_form = ProcessExpenseEventForm(prefix='processexpense', pattern=pattern)

    cited_ids = [c.resource.id for c in process.citations()]
    citation_requirements = process.citation_requirements()
    for cr in citation_requirements:
        cr.resources = []
        for evt in cr.fulfilling_events():
            resource = evt.resource
            resource.event = evt
            cr.resources.append(resource)

    output_resource_ids = [e.resource.id for e in process.production_events() if e.resource]

    return render(request, "work/process_logging.html", {
        "process": process,
        "change_process_form": change_process_form,
        "cited_ids": cited_ids,
        "citation_requirements": citation_requirements,
        "output_resource_ids": output_resource_ids,
        "agent": agent,
        "user": user,
        "logger": logger,
        "worker": worker,
        "super_logger": super_logger,
        "add_output_form": add_output_form,
        "add_citation_form": add_citation_form,
        "add_consumable_form": add_consumable_form,
        "add_usable_form": add_usable_form,
        "add_work_form": add_work_form,
        "unplanned_work_form": unplanned_work_form,
        "unplanned_cite_form": unplanned_cite_form,
        "unplanned_consumption_form": unplanned_consumption_form,
        "unplanned_use_form": unplanned_use_form,
        "unplanned_output_form": unplanned_output_form,
        "role_formset": role_formset,
        "process_expense_form": process_expense_form,
        "slots": slots,
        "to_be_changed_requirement": to_be_changed_requirement,
        "changeable_requirement": changeable_requirement,
        "work_reqs": work_reqs,
        "consume_reqs": consume_reqs,
        "uncommitted_consumption": process.uncommitted_consumption_events(),
        "use_reqs": use_reqs,
        "uncommitted_use": process.uncommitted_use_events(),
        "uncommitted_process_expenses": process.uncommitted_process_expense_events(),
        "unplanned_work": unplanned_work,
        "work_now": work_now,
        "help": get_help("process_work"),
    })

@login_required
def work_log_resource_for_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    form = ct.resource_create_form(data=request.POST)
    if form.is_valid():
        resource_data = form.cleaned_data
        agent = get_agent(request)
        resource_type = ct.resource_type
        try:
            qty = resource_data["event_quantity"]
        except:
            qty = resource_data["quantity"]
        event_type = ct.event_type
        resource = None
        if resource_type.inventory_rule == "yes":
            resource = form.save(commit=False)
            resource.quantity = qty
            resource.resource_type = resource_type
            resource.created_by=request.user
            if not ct.resource_type.substitutable:
                resource.independent_demand = ct.independent_demand
                resource.order_item = ct.order_item
            if event_type.applies_stage():
                resource.stage = ct.stage
            resource.save()
            event_date = resource_data["created_date"]
        else:
            event_date = resource_data["event_date"]
        from_agent = resource_data["from_agent"]
        default_agent = ct.process.default_agent()
        if not from_agent:
            from_agent = default_agent
        event = EconomicEvent(
            resource = resource,
            commitment = ct,
            event_date = event_date,
            event_type = event_type,
            from_agent = from_agent,
            to_agent = default_agent,
            resource_type = ct.resource_type,
            process = ct.process,
            context_agent = ct.process.context_agent,
            quantity = qty,
            unit_of_quantity = ct.unit_of_quantity,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        ct.process.set_started(event.event_date, request.user)

    next = request.POST.get("next")
    if next:
        if next == "work":
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', ct.process.id))

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', ct.process.id))

@login_required
def work_invite_collaborator(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    if request.method == "POST":
        if notification:
            agent = get_agent(request)
            users = commitment.possible_work_users()
            site_name = get_site_name(request)
            if users:
                notification.send(
                    users,
                    "valnet_help_wanted",
                    {"resource_type": commitment.resource_type,
                    "due_date": commitment.due_date,
                    "hours": commitment.quantity,
                    "unit": commitment.resource_type.unit,
                    "description": commitment.description or "",
                    "process": commitment.process,
                    "creator": agent,
                    "site_name": site_name,
                    "current_site": request.get_host(),
                    }
                )

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_change_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    process = ct.process
    if request.method == "POST":

        agent = get_agent(request)
        prefix = ct.form_prefix()
        if ct.event_type.relationship=="work":
            form = WorkCommitmentForm(instance=ct, data=request.POST, prefix=prefix)
        else:
            form = ChangeCommitmentForm(instance=ct, data=request.POST, prefix=prefix)
        next = request.POST.get("next")

        if form.is_valid():
            data = form.cleaned_data
            rt = ct.resource_type
            demand = ct.independent_demand
            new_qty = data["quantity"]

            #todo:
            #old_ct = Commitment.objects.get(id=commitment_id)
            #explode = handle_commitment_changes(old_ct, rt, new_qty, demand, demand)
            #flow todo: explode?
            #explode wd apply to rt changes, which will not happen here
            #handle_commitment_changes will propagate qty changes
            commitment = form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_to_resource_for_commitment(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    form = ct.select_resource_form(data=request.POST)
    if form.is_valid():
        data = form.cleaned_data
        agent = get_agent(request)
        resource = data["resource"]
        quantity = data["quantity"]
        if resource and quantity:
            resource.quantity += quantity
            resource.changed_by=request.user
            resource.save()
            event_type = ct.event_type
            default_agent = ct.process.default_agent()
            event = EconomicEvent(
                resource = resource,
                commitment = ct,
                event_date = datetime.date.today(),
                event_type = event_type,
                from_agent = default_agent,
                to_agent = default_agent,
                resource_type = ct.resource_type,
                process = ct.process,
                context_agent = ct.context_agent,
                quantity = quantity,
                unit_of_quantity = ct.unit_of_quantity,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()
            ct.process.set_started(event.event_date, request.user)


    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', ct.process.id))

from functools import partial, wraps

@login_required
def non_process_logging(request):
    member = get_agent(request)
    if not member:
        return HttpResponseRedirect('/%s/'
            % ('work/work-home'))

    pattern = None
    pattern_id = 0
    patterns = PatternUseCase.objects.filter(use_case__identifier='non_prod')
    if patterns:
        pattern = patterns[0].pattern
        pattern_id = pattern.id
        rts = pattern.work_resource_types()
    else:
        rts = EconomicResourceType.objects.filter(behavior="work")
    ctx_qs = member.related_contexts_queryset()
    if ctx_qs:
        context_agent = ctx_qs[0]
        if context_agent.project and context_agent.project.resource_type_selection == "project":
            rts = rts.filter(context_agent=context_agent)
        else:
            rts = rts.filter(Q(context_agent=context_agent)|Q(context_agent=None))

    TimeFormSet = modelformset_factory(
        EconomicEvent,
        form=WorkCasualTimeContributionForm,
        can_delete=False,
        extra=4,
        max_num=8,
        )

    init = []
    for i in range(0, 4):
        init.append({"is_contribution": True,})
    time_formset = TimeFormSet(
        queryset=EconomicEvent.objects.none(),
        initial = init,
        data=request.POST or None)

    for form in time_formset.forms:
        form.fields["context_agent"].queryset = ctx_qs
        form.fields["resource_type"].queryset = rts

    if request.method == "POST":
        keep_going = request.POST.get("keep-going")
        just_save = request.POST.get("save")
        if time_formset.is_valid():
            events = time_formset.save(commit=False)

            if pattern:
                unit = Unit.objects.filter(
                    unit_type="time",
                    name__icontains="Hour")[0]
                for event in events:
                    if event.event_date and event.quantity:
                        event.from_agent=member
                        event.to_agent = event.context_agent.default_agent()
                        #event.is_contribution=True
                        rt = event.resource_type
                        event_type = pattern.event_type_for_resource_type("work", rt)
                        event.event_type=event_type
                        event.unit_of_quantity=unit
                        event.created_by=request.user
                        event.save()
            if keep_going:
                return HttpResponseRedirect('/%s/'
                    % ('work/non-process-logging'))
            else:
                return HttpResponseRedirect('/%s/'
                    % ('work/my-history'))

    return render(request, "work/non_process_logging.html", {
        "member": member,
        "time_formset": time_formset,
        "pattern_id": pattern_id,
        "help": get_help("non_proc_log"),
    })



@login_required
def work_todo_done(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            todo.finished = True
            todo.save()
            event = todo.todo_event()
            if not event:
                event = create_event_from_todo(todo)
                event.save()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def work_add_todo(request):
    if request.method == "POST":
        agent = get_agent(request)
        patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
        ca_id = request.POST["context_agent"]
        context_agent_in = EconomicAgent.objects.get(id=int(ca_id))
        if patterns:
            pattern = patterns[0].pattern
            form = WorkTodoForm(agent=agent, context_agent=context_agent_in, pattern=pattern, data=request.POST)
        else:
            form = WorkTodoForm(agent=agent, context_agent=context_agent_in, data=request.POST)
        next = request.POST.get("next")
        et = None
        ets = EventType.objects.filter(
            relationship='todo')
        if ets:
            et = ets[0]
        if et:
            if form.is_valid():
                data = form.cleaned_data
                todo = form.save(commit=False)
                todo.to_agent=agent
                todo.event_type=et
                todo.quantity = Decimal("0")
                todo.unit_of_quantity=todo.resource_type.unit
                todo.save()
                if notification:
                    if todo.from_agent:
                        if todo.from_agent != agent:
                            site_name = get_site_name(request)
                            user = todo.from_agent.user()
                            if user:
                                notification.send(
                                    [user.user,],
                                    "valnet_new_todo",
                                    {"description": todo.description,
                                    "creator": agent,
                                    "site_name": site_name,
                                    "current_site": request.get_host(),
                                    }
                                )

    return HttpResponseRedirect(next)

@login_required
def work_todo_delete(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            if notification:
                if todo.from_agent:
                    agent = get_agent(request)
                    if todo.from_agent != agent:
                        site_name = get_site_name(request)
                        user = todo.from_agent.user()
                        if user:
                            notification.send(
                                [user.user,],
                                "valnet_deleted_todo",
                                {"description": todo.description,
                                "creator": agent,
                                "site_name": site_name,
                                "current_site": request.get_host(),
                                }
                            )
            todo.delete()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def work_todo_change(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            agent = get_agent(request)
            prefix = todo.form_prefix()
            patterns = PatternUseCase.objects.filter(use_case__identifier='todo')
            ca_id = request.POST[prefix+"-context_agent"]
            context_agent_in = EconomicAgent.objects.get(id=int(ca_id))
            if patterns:
                pattern = patterns[0].pattern
                form = WorkTodoForm(data=request.POST, pattern=pattern, agent=agent, context_agent=context_agent_in, instance=todo, prefix=prefix)
            else:
                form = WorkTodoForm(data=request.POST, agent=agent, context_agent=context_agent_in, instance=todo, prefix=prefix)
            if form.is_valid():
                todo = form.save()

    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
def work_todo_decline(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            todo.from_agent=None
            todo.save()
    next = request.POST.get("next")
    return HttpResponseRedirect(next)

@login_required
#todo: change this to work_todo_qty -
#it's not always hours.
#The template correctly shows Qty of Unit
#but the internal names shd be changed
#to prevent future confusion.
def work_todo_time(request):
    if request.method == "POST":
        todo_id = request.POST.get("todoId")
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            hours = request.POST.get("hours")
            if hours:
                qty = Decimal(hours)
            else:
                qty = Decimal("0.0")
            #task_bugs change
            # was creating zero qty events
            event = todo.todo_event()
            if event:
                event.quantity = qty
                event.save()
            else:
                if qty:
                    event = create_event_from_todo(todo)
                    event.quantity = qty
                    event.save()
    return HttpResponse("Ok", content_type="text/plain")

@login_required
def work_todo_mine(request, todo_id):
    if request.method == "POST":
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            agent = get_agent(request)
            todo.from_agent = agent
            todo.save()
            #task_bugs change
            # was creating an event here
    next = request.POST.get("next")
    if next:
        return HttpResponseRedirect(next)
    return HttpResponseRedirect('/%s/'
        % ('work/my-dashboard'))

@login_required
def work_todo_description(request):
    if request.method == "POST":
        todo_id = request.POST.get("todoId")
        try:
            todo = Commitment.objects.get(id=todo_id)
        except Commitment.DoesNotExist:
            todo = None
        if todo:
            did = request.POST.get("did")
            event = todo.todo_event()
            if event:
                event.description = did
                event.save()

    return HttpResponse("Ok", content_type="text/plain")

@login_required
def work_commit_to_task(request, commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    process = ct.process
    if request.method == "POST":
        agent = get_agent(request)
        prefix = ct.form_prefix()
        form = CommitmentForm(data=request.POST, prefix=prefix)
        next = None
        next = request.POST.get("next")
        if form.is_valid():
            data = form.cleaned_data
            #todo: next line did not work, don't want to take time to figure out why right now
            #probly form shd have ct as instance.
            #ct = form.save(commit=False)
            start_date = data["start_date"]
            description = data["description"]
            quantity = data["quantity"]
            unit_of_quantity = data["unit_of_quantity"]
            ct.start_date=start_date
            ct.quantity=quantity
            ct.unit_of_quantity=unit_of_quantity
            ct.description=description
            ct.from_agent = agent
            ct.changed_by=request.user
            ct.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_uncommit(request, commitment_id):
    ct = get_object_or_404(Commitment, id=commitment_id)
    process = ct.process
    if request.method == "POST":
        ct.from_agent = None
        ct.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_process_worker(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = WorkCommitmentForm(data=request.POST, prefix='work')
        if form.is_valid():
            input_data = form.cleaned_data
            demand = process.independent_demand()
            rt = input_data["resource_type"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("work", rt)
            ct = form.save(commit=False)
            ct.process=process
            #flow todo: test order_item
            ct.order_item = process.order_item()
            ct.independent_demand=demand
            ct.event_type=event_type
            #ct.due_date=process.end_date
            ct.resource_type=rt
            ct.context_agent=process.context_agent
            ct.unit_of_quantity=rt.directional_unit("use")
            ct.created_by=request.user
            ct.save()
            if notification:
                agent = get_agent(request)
                users = ct.possible_work_users()
                site_name = get_site_name(request)
                if users:
                    notification.send(
                        users,
                        "valnet_help_wanted",
                        {"resource_type": ct.resource_type,
                        "due_date": ct.due_date,
                        "hours": ct.quantity,
                        "unit": ct.resource_type.unit,
                        "description": ct.description or "",
                        "process": ct.process,
                        "creator": agent,
                        "site_name": site_name,
                        "current_site": request.get_host(),
                        }
                    )
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_delete_event(request, event_id):
    event = get_object_or_404(EconomicEvent, pk=event_id)
    process = event.process
    if request.method == "POST":
        agent = event.from_agent
        exchange = event.exchange
        distribution = event.distribution
        resource = event.resource
        if resource:
            if event.consumes_resources():
                resource.quantity += event.quantity
            if event.creates_resources():
                resource.quantity -= event.quantity
            if event.changes_stage():
                tbcs = process.to_be_changed_requirements()
                if tbcs:
                    tbc = tbcs[0]
                    tbc_evts = tbc.fulfilling_events()
                    if tbc_evts:
                        tbc_evt = tbc_evts[0]
                        resource.quantity = tbc_evt.quantity
                        tbc_evt.delete()
                    resource.stage = tbc.stage
                else:
                    resource.revert_to_previous_stage()
            event.delete()
            if resource.is_deletable():
                resource.delete()
            else:
                resource.save()
        else:
            event.delete()

    next = request.POST.get("next")
    if next:
        if next != "process-logging":
            return HttpResponseRedirect(next)
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_work_event(request, commitment_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    form = ct.input_event_form_init(data=request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        #event.from_agent = ct.from_agent
        event.to_agent = ct.process.default_agent()
        event.resource_type = ct.resource_type
        event.process = ct.process
        event.context_agent = ct.context_agent
        event.unit_of_quantity = ct.unit_of_quantity
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
            % ('work/process-logging', ct.process.id))

@login_required
def work_change_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    commitment = event.commitment
    process = event.process
    if request.method == "POST":
        form = event.work_event_change_form(data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            form.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_process_input(request, process_id, slot):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        pattern = process.process_pattern
        if slot == "c":
            form = ProcessConsumableForm(data=request.POST, pattern=pattern, prefix='consumable')
            rel = "consume"
        elif slot == "u":
            form = ProcessUsableForm(data=request.POST, pattern=pattern, prefix='usable')
            rel = "use"
        if form.is_valid():
            input_data = form.cleaned_data
            qty = input_data["quantity"]
            if qty:
                demand = process.independent_demand()
                ct = form.save(commit=False)
                rt = input_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type(rel, rt)
                ct.event_type = event_type
                ct.process = process
                ct.context_agent=process.context_agent
                ct.order_item = process.order_item()
                ct.independent_demand = demand
                ct.due_date = process.start_date
                ct.created_by = request.user
                #todo: add stage and state as args?
                #todo pr: this shd probably use own_or_parent_recipes
                #ptrt, inheritance = ct.resource_type.main_producing_process_type_relationship()
                #if ptrt:
                #    ct.context_agent = ptrt.process_type.context_agent
                ct.save()
                #todo: this is used in process logging; shd it explode?
                #explode_dependent_demands(ct, request.user)
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

def work_json_directional_unit(request, resource_type_id, direction):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    defaults = {
        "unit": ert.directional_unit(direction).id,
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

@login_required
def work_delete_process_commitment(request, commitment_id):
    commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = commitment.process
    #commitment.delete_dependants()
    commitment.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_unplanned_work_event(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        form = UnplannedWorkEventForm(prefix="unplanned", data=request.POST, pattern=pattern)
        if form.is_valid():
            event = form.save(commit=False)
            rt = event.resource_type
            event.event_type = pattern.event_type_for_resource_type("work", rt)
            event.process = process
            event.context_agent = process.context_agent
            default_agent = process.default_agent()
            event.to_agent = default_agent
            event.unit_of_quantity = rt.unit
            event.created_by = request.user
            event.changed_by = request.user
            event.save()
            process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_change_unplanned_work_event(request, event_id):
    event = get_object_or_404(EconomicEvent, id=event_id)
    process = event.process
    pattern = process.process_pattern
    if pattern:
        if request.method == "POST":
            form = UnplannedWorkEventForm(
                pattern=pattern,
                instance=event,
                prefix=str(event.id),
                data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                form.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_unplanned_output(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = UnplannedOutputForm(data=request.POST, prefix='unplannedoutput')
        if form.is_valid():
            output_data = form.cleaned_data
            qty = output_data["quantity"]
            if qty:
                event = form.save(commit=False)
                rt = output_data["resource_type"]
                identifier = output_data["identifier"]
                notes = output_data["notes"]
                url = output_data["url"]
                photo_url = output_data["photo_url"]
                access_rules = output_data["access_rules"]
                demand = None
                if not rt.substitutable:
                    demand = process.independent_demand()
                    #flow todo: add order_item ? [no]
                    #N/A I think, but see also
                    #add_process_output

                resource = EconomicResource(
                    resource_type=rt,
                    identifier=identifier,
                    independent_demand=demand,
                    notes=notes,
                    url=url,
                    photo_url=photo_url,
                    quantity=event.quantity,
                    access_rules=access_rules,
                    #unit_of_quantity=event.unit_of_quantity,
                    created_by=request.user,
                )
                resource.save()

                event.resource = resource
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type("out", rt)
                event.event_type = event_type
                event.process = process
                event.context_agent = process.context_agent
                default_agent = process.default_agent()
                event.from_agent = default_agent
                event.to_agent = default_agent
                event.event_date = datetime.date.today()
                event.created_by = request.user
                event.save()
                process.set_started(event.event_date, request.user)

                next = request.POST.get("next")
                if next and next == "exchange-work":
                  role_formset =  resource_role_context_agent_formset(prefix="resource", data=request.POST)
                else:
                  role_formset =  resource_role_agent_formset(prefix="resource", data=request.POST)

                for form_rra in role_formset.forms:
                    if form_rra.is_valid():
                        data_rra = form_rra.cleaned_data
                        if data_rra:
                            role = data_rra["role"]
                            agent = data_rra["agent"]
                            if role and agent:
                                rra = AgentResourceRole()
                                rra.agent = agent
                                rra.role = role
                                rra.resource = resource
                                rra.is_contact = data_rra["is_contact"]
                                rra.save()
                #todo: add exchange-work redirect?

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_unplanned_input_event(request, process_id, slot):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        if slot == "c":
            prefix = "unplannedconsumption"
            et = "consume"
        else:
            prefix = "unplannedusable"
            et = "use"
        form = UnplannedInputEventForm(
            prefix=prefix,
            data=request.POST,
            pattern=pattern,
            load_resources=True)
        if form.is_valid():
            agent = get_agent(request)
            data = form.cleaned_data
            agent = get_agent(request)
            rt = data["resource_type"]
            r_id = data["resource"]
            qty = data["quantity"]
            event_date = data["event_date"]
            unit = rt.unit
            if et == "use":
                unit = rt.unit_for_use()
            resource = EconomicResource.objects.get(id=r_id)
            default_agent = process.default_agent()
            from_agent = resource.owner() or default_agent
            event_type = pattern.event_type_for_resource_type(et, rt)
            event = EconomicEvent(
                event_type=event_type,
                resource_type = rt,
                resource = resource,
                from_agent = from_agent,
                to_agent = default_agent,
                process = process,
                context_agent = process.context_agent,
                event_date = event_date,
                quantity=qty,
                unit_of_quantity = unit,
                created_by = request.user,
                changed_by = request.user,
            )
            event.save()
            if event_type.consumes_resources():
                resource.quantity -= event.quantity
                resource.changed_by=request.user
                resource.save()
            process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

def json_resource_type_resources(request, resource_type_id):
    json = serializers.serialize("json", EconomicResource.objects.filter(resource_type=resource_type_id), fields=('identifier'))
    return HttpResponse(json, content_type='application/json')

@login_required
def work_add_consumption_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    process = ct.process
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    form = InputEventForm(prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        event.context_agent = ct.context_agent
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.unit_of_quantity = ct.unit_of_quantity
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        if ct.consumes_resources():
            resource.quantity -= event.quantity
            resource.changed_by=request.user
            resource.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_use_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    unit = ct.resource_type.directional_unit("use")
    qty_help = " ".join(["unit:", unit.abbrev])
    form = InputEventForm(qty_help=qty_help, prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.from_agent = agent
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        #event.project = ct.project
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.context_agent = ct.context_agent
        event.unit_of_quantity = unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', ct.process.id))

@login_required
def work_add_process_output(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = ProcessOutputForm(data=request.POST, prefix='output')
        if form.is_valid():
            output_data = form.cleaned_data
            qty = output_data["quantity"]
            if qty:
                ct = form.save(commit=False)
                rt = output_data["resource_type"]
                pattern = process.process_pattern
                event_type = pattern.event_type_for_resource_type("out", rt)
                ct.event_type = event_type
                ct.process = process
                ct.context_agent = process.context_agent
                ct.independent_demand = process.independent_demand()
                ct.due_date = process.end_date
                ct.created_by = request.user
                ct.save()
                if process.name == "Make something":
                    process.name = " ".join([
                                "Make",
                                ct.resource_type.name,
                            ])
                else:
                    process.name = " and ".join([
                                process.name,
                                ct.resource_type.name,
                            ])
                if len(process.name) > 128:
                    process.name = process.name[0:128]
                process.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_log_stage_change_event(request, commitment_id, resource_id):
    to_be_changed_commitment = get_object_or_404(Commitment, pk=commitment_id)
    process = to_be_changed_commitment.process
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        quantity = resource.quantity
        default_agent = process.default_agent()
        from_agent = default_agent
        event_date = datetime.date.today()
        prefix = resource.form_prefix()
        #shameless hack
        qty_field = prefix + "-quantity"
        if request.POST.get(qty_field):
            form = resource.transform_form(data=request.POST)
            if form.is_valid():
                data = form.cleaned_data
                quantity = data["quantity"]
                event_date = data["event_date"]
                from_agent = data["from_agent"]
        change_commitment = process.changeable_requirements()[0]
        rt = to_be_changed_commitment.resource_type
        event = EconomicEvent(
            commitment=to_be_changed_commitment,
            event_type=to_be_changed_commitment.event_type,
            resource_type = rt,
            resource = resource,
            from_agent = from_agent,
            to_agent = default_agent,
            process = process,
            context_agent = process.context_agent,
            event_date = event_date,
            quantity=resource.quantity,
            unit_of_quantity = rt.unit,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        event = EconomicEvent(
            commitment=change_commitment,
            event_type=change_commitment.event_type,
            resource_type = rt,
            resource = resource,
            from_agent = from_agent,
            to_agent = default_agent,
            process = process,
            context_agent = process.context_agent,
            event_date = event_date,
            quantity=quantity,
            unit_of_quantity = rt.unit,
            created_by = request.user,
            changed_by = request.user,
        )
        event.save()
        resource.stage = change_commitment.stage
        resource.quantity = quantity
        resource.save()
        process.set_started(event.event_date, request.user)
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_process_citation(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if request.method == "POST":
        form = ProcessCitationForm(data=request.POST, prefix='citation')
        if form.is_valid():
            input_data = form.cleaned_data
            demand = process.independent_demand()
            quantity = Decimal("1")
            rt = input_data["resource_type"]
            descrip = input_data["description"]
            pattern = process.process_pattern
            event_type = pattern.event_type_for_resource_type("cite", rt)
            agent = get_agent(request)
            ct = Commitment(
                process=process,
                #from_agent=agent,
                independent_demand=demand,
                order_item = process.order_item(),
                event_type=event_type,
                due_date=process.start_date,
                resource_type=rt,
                context_agent=process.context_agent,
                quantity=quantity,
                description=descrip,
                unit_of_quantity=rt.directional_unit("cite"),
                created_by=request.user,
            )
            ct.save()

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_add_citation_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    resource = get_object_or_404(EconomicResource, pk=resource_id)
    prefix = resource.form_prefix()
    unit = ct.resource_type.directional_unit("use")
    qty_help = " ".join(["unit:", unit.abbrev])
    form = InputEventForm(qty_help=qty_help, prefix=prefix, data=request.POST)
    if form.is_valid():
        agent = get_agent(request)
        event = form.save(commit=False)
        event.commitment = ct
        event.event_type = ct.event_type
        event.from_agent = agent
        event.resource_type = ct.resource_type
        event.resource = resource
        event.process = ct.process
        default_agent = ct.process.default_agent()
        event.from_agent = default_agent
        event.to_agent = default_agent
        event.context_agent = ct.context_agent
        event.unit_of_quantity = unit
        event.created_by = request.user
        event.changed_by = request.user
        event.save()
        ct.process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', ct.process.id))

@login_required
def work_add_unplanned_cite_event(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    pattern = process.process_pattern
    if pattern:
        form = UnplannedCiteEventForm(
            prefix='unplannedcite',
            data=request.POST,
            pattern=pattern,
            load_resources=True)
        if form.is_valid():
            data = form.cleaned_data
            qty = data["quantity"]
            if qty:
                agent = get_agent(request)
                rt = data["resource_type"]
                r_id = data["resource"]
                resource = EconomicResource.objects.get(id=r_id)
                #todo: rethink for citations
                default_agent = process.default_agent()
                from_agent = resource.owner() or default_agent
                event_type = pattern.event_type_for_resource_type("cite", rt)
                event = EconomicEvent(
                    event_type=event_type,
                    resource_type = rt,
                    resource = resource,
                    from_agent = from_agent,
                    to_agent = default_agent,
                    process = process,
                    context_agent = process.context_agent,
                    event_date = datetime.date.today(),
                    quantity=qty,
                    unit_of_quantity = rt.directional_unit("cite"),
                    created_by = request.user,
                    changed_by = request.user,
                )
                event.save()
                process.set_started(event.event_date, request.user)

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

@login_required
def work_delete_citation_event(request, commitment_id, resource_id):
    ct = get_object_or_404(Commitment, pk=commitment_id)
    process = ct.process
    if request.method == "POST":
        resource = get_object_or_404(EconomicResource, pk=resource_id)
        events = ct.fulfillment_events.filter(resource=resource)
        for event in events:
            event.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))

def json_resource_type_citation_unit(request, resource_type_id):
    ert = get_object_or_404(EconomicResourceType, pk=resource_type_id)
    direction = "use"
    defaults = {
        "unit": ert.directional_unit(direction).name,
    }
    data = simplejson.dumps(defaults, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")

@login_required
def work_join_task(request, commitment_id):
    if request.method == "POST":
        ct = get_object_or_404(Commitment, id=commitment_id)
        process = ct.process
        agent = get_agent(request)

        if notification:
            workers = ct.workers()
            users = []
            for worker in workers:
                worker_users = [au.user for au in worker.users.all()]
                users.extend(worker_users)
            site_name = get_site_name(request)
            if users:
                notification.send(
                    users,
                    "valnet_join_task",
                    {"resource_type": ct.resource_type,
                    "due_date": ct.due_date,
                    "hours": ct.quantity,
                    "unit": ct.resource_type.unit,
                    "description": ct.description or "",
                    "process": process,
                    "creator": agent,
                    "site_name": site_name,
                    "current_site": request.get_host(),
                    }
                )

    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process.id))


 #    H I S T O R Y

@login_required
def my_history(request): # tasks history
    #agent = get_object_or_404(EconomicAgent, pk=agent_id)
    user_agent = get_agent(request)
    agent = user_agent
    user_is_agent = False
    if agent == user_agent:
        user_is_agent = True
    #event_list = agent.contributions()
    event_list = agent.given_events.all().filter(event_type__relationship = "work")
    no_bucket = 0
    with_bucket = 0
    event_value = Decimal("0.0")
    claim_value = Decimal("0.0")
    outstanding_claims = Decimal("0.0")
    claim_distributions = Decimal("0.0")
    claim_distro_events = []
    event_types = {e.event_type for e in event_list}
    filter_form = EventTypeFilterForm(event_types=event_types, data=request.POST or None)
    paid_filter = "U"
    if request.method == "POST":
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            et_ids = data["event_types"]
            start = data["start_date"]
            end = data["end_date"]
            paid_filter = data["paid_filter"]
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
            #belt and suspenders: if no et_ids, form is not valid
            if et_ids:
                event_list = event_list.filter(event_type__id__in=et_ids)

    for event in event_list:
        if event.bucket_rule_for_context_agent():
            with_bucket += 1
        else:
            no_bucket += 1
        for claim in event.claims():
            claim_value += claim.original_value
            outstanding_claims += claim.value
            for de in claim.distribution_events():
                claim_distributions += de.value
                claim_distro_events.append(de.event)
    et = EventType.objects.get(name="Distribution")
    all_distro_evts = EconomicEvent.objects.filter(to_agent=agent, event_type=et)
    other_distro_evts = [d for d in all_distro_evts if d not in claim_distro_events]
    other_distributions = sum(de.quantity for de in other_distro_evts)
    #took off csv export for now
    #event_ids = ",".join([str(event.id) for event in event_list])

    if paid_filter == "U":
        event_list = list(event_list)
        for evnt in event_list:
            if evnt.owed_amount() == 0:
                    event_list.remove(evnt)

    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "work/my_history.html", {
        "agent": agent,
        "user_is_agent": user_is_agent,
        "events": events,
        "filter_form": filter_form,
        #"event_ids": event_ids,
        "no_bucket": no_bucket,
        "with_bucket": with_bucket,
        "claim_value": format(claim_value, ",.2f"),
        "outstanding_claims": format(outstanding_claims, ",.2f"),
        "claim_distributions": format(claim_distributions, ",.2f"),
        "other_distributions": format(other_distributions, ",.2f"),
        "help": get_help("my_history"),
    })

@login_required
def change_history_event(request, event_id):
    event = get_object_or_404(EconomicEvent, pk=event_id)
    page = request.GET.get("page")
    event_form = event.change_form(data=request.POST or None)
    if request.method == "POST":
        page = request.POST.get("page")
        if event_form.is_valid():
            event = event_form.save(commit=False)
            event.changed_by = request.user
            event.save()
        agent = event.from_agent
        #next = request.POST.get("next")
        if page:
            #if next:
            #    if next == "work-contributions":
            #        return HttpResponseRedirect('/%s/'
            #            % ('work/my-history', page))
            return HttpResponseRedirect('/%s/'
                % ('work/my-history', page))
        else:
            #if next:
            #    if next == "work-contributions":
            #        return HttpResponseRedirect('/%s/'
            #            % ('work/my-history'))
            return HttpResponseRedirect('/%s/'
                % ('work/my-history'))
    return render(request, "work/change_history_event.html", {
        "event_form": event_form,
        "page": page,
    })



def create_worktimer_context(
        request,
        process,
        agent,
        commitment):
    prev = ""
    today = datetime.date.today()
    #todo: will not now handle lack of commitment
    event = EconomicEvent(
        event_date=today,
        from_agent=agent,
        to_agent=process.default_agent(),
        process=process,
        context_agent=process.context_agent,
        quantity=Decimal("0"),
        is_contribution=True,
        created_by = request.user,
    )

    if commitment:
        event.commitment = commitment
        event.event_type = commitment.event_type
        event.resource_type = commitment.resource_type
        event.unit_of_quantity = commitment.resource_type.unit
        init = {
            "work_done": commitment.finished,
            "process_done": commitment.process.finished,
        }
        wb_form = WorkbookForm(initial=init)
        prev_events = commitment.fulfillment_events.filter(event_date__lt=today)
        if prev_events:
            prev_dur = sum(prev.quantity for prev in prev_events)
            unit = ""
            if commitment.unit_of_quantity:
                unit = commitment.unit_of_quantity.abbrev
            prev = " ".join([str(prev_dur), unit])
    else:
        wb_form = WorkbookForm()
    #if event.quantity > 0:
    event.save()
    others_working = []
    other_work_reqs = []
    wrqs = process.work_requirements()
    if wrqs.count() > 1:
        for wrq in wrqs:
            if wrq.from_agent != commitment.from_agent:
                if wrq.from_agent:
                    wrq.has_labnotes = wrq.agent_has_labnotes(wrq.from_agent)
                    others_working.append(wrq)
                else:
                    other_work_reqs.append(wrq)
    return {
        "commitment": commitment,
        "process": process,
        "wb_form": wb_form,
        "others_working": others_working,
        "other_work_reqs": other_work_reqs,
        "today": today,
        "prev": prev,
        "event": event,
        "help": get_help("work_timer"),
    }

@login_required
def work_timer(
        request,
        process_id,
        commitment_id=None):
    process = get_object_or_404(Process, id=process_id)
    agent = get_agent(request)
    ct = None
    if commitment_id:
        ct = get_object_or_404(Commitment, id=commitment_id)
        #if not request.user.is_superuser:
        #    if agent != ct.from_agent:
        #        return render(request, 'valueaccounting/no_permission.html')
    template_params = create_worktimer_context(
        request,
        process,
        agent,
        ct,
    )
    return render(request, "work/work_timer.html",
        template_params)

@login_required
def save_timed_work_now(request, event_id):
    if request.method == "POST":
        event = get_object_or_404(EconomicEvent, id=event_id)
        form = WorkbookForm(instance=event, data=request.POST)
        if form.is_valid():
            data = form.cleaned_data
            event = form.save(commit=False)
            event.changed_by = request.user
            process = event.process
            event.save()
            if not process.started:
                process.started = event.event_date
                process.changed_by=request.user
                process.save()
            data = "ok"
        else:
            data = form.errors
        return HttpResponse(data, content_type="text/plain")

@login_required
def work_process_finished(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    if not process.finished:
        process.finished = True
        process.save()
    else:
        if process.finished:
            process.finished = False
            process.save()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/process-logging', process_id))



#    O R D E R   P L A N S

@login_required
def order_list(request):
    agent = get_agent(request)
    help = get_help("order_list")
    projects = agent.managed_projects()

    return render(request, "work/order_list.html", {
        "projects": projects,
        "agent": agent,
        "help": help,
    })


@login_required
def order_plan(request, order_id):
    agent = get_agent(request)
    order = get_object_or_404(Order, pk=order_id)
    coordinated_projects = agent.managed_projects()
    if order.provider not in coordinated_projects:
        return render(request, 'valueaccounting/no_permission.html')
    error_message = ""
    order_items = order.order_items()
    rts = None
    add_order_item_form = None
    if agent:
        if order.order_type == "customer":
            patterns = PatternUseCase.objects.filter(use_case__identifier='cust_orders')
            if patterns:
                pattern = patterns[0].pattern
            else:
                raise ValidationError("no Customer Order ProcessPattern")
            rts = pattern.all_resource_types()
        else:
            rts = ProcessPattern.objects.all_production_resource_types()
        if rts:
            add_order_item_form = AddOrderItemForm(resource_types=rts)
        visited = set()
        for order_item in order_items:
            order_item.processes = order_item.unique_processes_for_order_item(visited)
            if order_item.is_workflow_order_item():
                init = {'quantity': order_item.quantity,}
                order_item.resource_qty_form = ResourceQuantityForm(prefix=str(order_item.id), initial=init)
                init = {'context_agent': order_item.context_agent,}
                order_item.project_form = ProjectSelectionForm(prefix=str(order_item.id), initial=init)
                last_date = order_item.process.end_date
                next_date = last_date + datetime.timedelta(days=1)
                init = {"start_date": next_date, "end_date": next_date}
                order_item.add_process_form = WorkflowProcessForm(prefix=str(order_item.id), initial=init, order_item=order_item)
    return render(request, "work/order_plan.html", {
        "order": order,
        "agent": agent,
        "order_items": order_items,
        "add_order_item_form": add_order_item_form,
        "error_message": error_message,
    })


@login_required
def change_project_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    agent = get_agent(request)
    coordinated_projects = agent.managed_projects()
    if order.provider not in coordinated_projects:
        return render(request, 'valueaccounting/no_permission.html')
    order_form = OrderChangeForm(instance=order, data=request.POST or None)
    if request.method == "POST":
        if order_form.is_valid():
            order = order_form.save()
            return HttpResponseRedirect('/%s/'
                % ('work/order-list'))

    return render(request, "work/change_project_order.html", {
        "order_form": order_form,
        "order": order,
        "next": next,
    })


@login_required
def plan_work(request, rand=0):
    agent = get_agent(request)
    slots = []
    resource_types = []
    selected_pattern = None
    selected_context_agent = None
    pattern_form = PatternProdSelectionForm()
    ca_form = ProjectSelectionFilteredForm(agent=agent)
    init = {"start_date": datetime.date.today(), "end_date": datetime.date.today()}
    process_form = DateAndNameForm(data=request.POST or None)
    #demand_form = OrderSelectionFilteredForm(data=request.POST or None)
    if request.method == "POST":
        input_resource_types = []
        input_process_types = []

        done_process = request.POST.get("create-process")
        add_another = request.POST.get("add-another")
        edit_process = request.POST.get("edit-process")
        get_related = request.POST.get("get-related")
        if get_related:
            selected_pattern = ProcessPattern.objects.get(id=request.POST.get("pattern"))
            selected_context_agent = EconomicAgent.objects.get(id=request.POST.get("context_agent"))
            if selected_pattern:
                slots = selected_pattern.event_types()
                for slot in slots:
                    rts = selected_pattern.get_resource_types(slot)
                    try:
                        if selected_context_agent.project.resource_type_selection == "project":
                            rts = rts.filter(context_agent=selected_context_agent)
                        else:
                            rts = rts.filter(context_agent=None)
                    except:
                        rts = rts.filter(context_agent=None)
                    slot.resource_types = rts
            process_form = DateAndNameForm(initial=init)
            #demand_form = OrderSelectionFilteredForm(provider=selected_context_agent)
        else:
            rp = request.POST
            today = datetime.date.today()
            if process_form.is_valid():
                start_date = process_form.cleaned_data["start_date"]
                end_date = process_form.cleaned_data["end_date"]
                process_name = process_form.cleaned_data["process_name"]
            else:
                start_date = today
                end_date = today
            demand = None
            added_to_order = False
            #if demand_form.is_valid():
            #    demand = demand_form.cleaned_data["demand"]
            #    if demand:
            #        added_to_order = True
            produced_rts = []
            cited_rts = []
            consumed_rts = []
            used_rts = []
            work_rts = []
            for key, value in list(dict(rp).items()):
                if "selected-context-agent" in key:
                    context_agent_id = key.split("~")[1]
                    selected_context_agent = EconomicAgent.objects.get(id=context_agent_id)
                    continue
                if "selected-pattern" in key:
                    pattern_id = key.split("~")[1]
                    selected_pattern = ProcessPattern.objects.get(id=pattern_id)
                    continue
                et = None
                action = ""
                try:
                    et_name = key.split("~")[0]
                    et = EventType.objects.get(name=et_name)
                    action = et.relationship
                except EventType.DoesNotExist:
                    pass
                if action == "consume":
                    consumed_id = int(value[0])
                    consumed_rt = EconomicResourceType.objects.get(id=consumed_id)
                    consumed_rts.append(consumed_rt)
                    continue
                if action == "use":
                    used_id = int(value[0])
                    used_rt = EconomicResourceType.objects.get(id=used_id)
                    used_rts.append(used_rt)
                    continue
                if action == "cite":
                    cited_id = int(value[0])
                    cited_rt = EconomicResourceType.objects.get(id=cited_id)
                    cited_rts.append(cited_rt)
                    continue
                if action == "out":
                    produced_id = int(value[0])
                    produced_rt = EconomicResourceType.objects.get(id=produced_id)
                    produced_rts.append(produced_rt)
                    continue
                if action == "work":
                    work_id = int(value[0])
                    work_rt = EconomicResourceType.objects.get(id=work_id)
                    work_rts.append(work_rt)
                    continue

            if rand:
                if not demand:
                    demand = Order(
                        order_type="rand",
                        order_date=today,
                        due_date=end_date,
                        provider=selected_context_agent,
                        created_by=request.user)
                    demand.save()
            if not process_name:
                process_name = "Make something"
                if produced_rts:
                    process_name = " ".join([
                        "Make",
                        produced_rts[0].name,
                    ])

            process = Process(
                name=process_name,
                end_date=end_date,
                start_date=start_date,
                process_pattern=selected_pattern,
                created_by=request.user,
                context_agent=selected_context_agent,
                plan=demand,
            )
            process.save()

            for rt in produced_rts:
                resource_types.append(rt)
                et = selected_pattern.event_type_for_resource_type("out", rt)
                if et:
                    commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        description="",
                        user=request.user)
                    if rand:
                        if not added_to_order: #add to order feature removed, didn't work, no simple solution
                            commitment.order = demand
                            commitment.order_item = commitment
                            commitment.save()

            for rt in cited_rts:
                et = selected_pattern.event_type_for_resource_type("cite", rt)
                if et:
                    commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        order_item = process.order_item(),
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        description="",
                        user=request.user)
            for rt in used_rts:
                if rt not in resource_types:
                    resource_types.append(rt)
                    et = selected_pattern.event_type_for_resource_type("use", rt)
                    if et:
                        commitment = process.add_commitment(
                            resource_type= rt,
                            demand=demand,
                            order_item = process.order_item(),
                            quantity=Decimal("1"),
                            event_type=et,
                            unit=rt.unit,
                            description="",
                            user=request.user)

            for rt in consumed_rts:
                if rt not in resource_types:
                    resource_types.append(rt)
                    et = selected_pattern.event_type_for_resource_type("consume", rt)
                    if et:
                        commitment = process.add_commitment(
                            resource_type= rt,
                            demand=demand,
                            order_item = process.order_item(),
                            quantity=Decimal("1"),
                            event_type=et,
                            unit=rt.unit,
                            description="",
                            user=request.user)

            for rt in work_rts:
                agent = None
                et = selected_pattern.event_type_for_resource_type("work", rt)
                if et:
                    work_commitment = process.add_commitment(
                        resource_type= rt,
                        demand=demand,
                        order_item = process.order_item(),
                        quantity=Decimal("1"),
                        event_type=et,
                        unit=rt.unit,
                        from_agent=agent,
                        description="",
                        user=request.user)
                    if notification:
                        if not work_commitment.from_agent:
                            agent = get_agent(request)
                            users = work_commitment.possible_work_users()
                            site_name = get_site_name(request)
                            if users:
                                notification.send(
                                    users,
                                    "valnet_new_task",
                                    {"resource_type": work_commitment.resource_type,
                                    "due_date": work_commitment.due_date,
                                    "hours": work_commitment.quantity,
                                    "unit": work_commitment.resource_type.unit,
                                    "description": work_commitment.description or "",
                                    "process": work_commitment.process,
                                    "creator": agent,
                                    "site_name": site_name,
                                    "current_site": request.get_host(),
                                    }
                                )

            #if done_process:
            #    return HttpResponseRedirect('/%s/'
            #        % ('work/order-list'))
            #if add_another:
            #    return HttpResponseRedirect('/%s/%s/'
            #        % ('work/plan-work', rand))
            #if edit_process:
            return HttpResponseRedirect('/%s/%s/'
                % ('work/process-logging', process.id))

    return render(request, "work/plan_work.html", {
        "slots": slots,
        "selected_pattern": selected_pattern,
        "selected_context_agent": selected_context_agent,
        "ca_form": ca_form,
        "pattern_form": pattern_form,
        "process_form": process_form,
        #"demand_form": demand_form,
        "rand": rand,
        "help": get_help("process_select"),
    })

def project_history(request, agent_id):
    project = get_object_or_404(EconomicAgent, pk=agent_id)
    agent = get_agent(request)
    event_list = project.contribution_events()
    #event_list = project.all_events()
    agent_ids = {event.from_agent.id for event in event_list if event.from_agent}
    agents = EconomicAgent.objects.filter(id__in=agent_ids)
    filter_form = ProjectContributionsFilterForm(agents=agents, data=request.POST or None)
    if request.method == "POST":
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            #event_type = data["event_type"]
            from_agents = data["from_agents"]
            start = data["start_date"]
            end = data["end_date"]
            if from_agents:
                event_list = event_list.filter(from_agent__in=from_agents)
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
    event_ids = ",".join([str(event.id) for event in event_list])
    paginator = Paginator(event_list, 25)
    page = request.GET.get('page')
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        events = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        events = paginator.page(paginator.num_pages)

    return render(request, "work/project_history.html", {
        "project": project,
        "events": events,
        "filter_form": filter_form,
        "agent": agent,
        "event_ids": event_ids,
    })

@login_required
def project_history_csv(request):
    event_ids = request.GET.get("event-ids")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=project-history.csv'
    writer = csv.writer(response)
    event_ids_split = event_ids.split(",")
    queryset = EconomicEvent.objects.filter(id__in=event_ids_split)
    opts = EconomicEvent._meta
    field_names = [field.name for field in opts.fields]
    writer.writerow(field_names)
    for obj in queryset:
        row = []
        for field in field_names:
            x = getattr(obj, field)
            try:
                x = x.encode('latin-1', 'replace')
            except AttributeError:
                pass
            row.append(x)
        writer.writerow(row)

    return response

def fake_kanban(request, agent_id):
    project = get_object_or_404(EconomicAgent, pk=agent_id)
    agent = get_agent(request)

    """
    event_list = project.contribution_events()
    event_list = project.all_events()
    agent_ids = {event.from_agent.id for event in event_list if event.from_agent}
    agents = EconomicAgent.objects.filter(id__in=agent_ids)
    filter_form = ProjectContributionsFilterForm(agents=agents, data=request.POST or None)
    if request.method == "POST":
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            #event_type = data["event_type"]
            from_agents = data["from_agents"]
            start = data["start_date"]
            end = data["end_date"]
            if from_agents:
                event_list = event_list.filter(from_agent__in=from_agents)
            if start:
                event_list = event_list.filter(event_date__gte=start)
            if end:
                event_list = event_list.filter(event_date__lte=end)
    event_ids = ",".join([str(event.id) for event in event_list])
    """

    return render(request, "work/fake_kanban.html", {
        "project": project,
        "agent": agent,

    })

@login_required
def order_delete_confirmation_work(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    agent = get_agent(request)
    coordinated_projects = agent.managed_projects()
    if order.provider not in coordinated_projects:
        return render(request, 'work/no_permission.html')
    pcs = order.producing_commitments()
    sked = []
    reqs = []
    work = []
    tools = []
    next = "order-list"
    if pcs:
        visited_resources = set()
        for ct in pcs:
            #visited_resources.add(ct.resource_type)
            schedule_commitment(ct, sked, reqs, work, tools, visited_resources, 0)
        return render(request, 'work/order_delete_confirmation_work.html', {
            "order": order,
            "sked": sked,
            "reqs": reqs,
            "work": work,
            "tools": tools,
            "next": next,
        })
    else:
        commitments = Commitment.objects.filter(independent_demand=order)
        if commitments:
            for ct in commitments:
                sked.append(ct)
                if ct.process not in sked:
                    sked.append(ct.process)
            return render(request, 'work/order_delete_confirmation_work.html', {
                "order": order,
                "sked": sked,
                "reqs": reqs,
                "work": work,
                "tools": tools,
                "next": next,
            })
        else:
            order.delete()
            if next == "order-list":
                return HttpResponseRedirect('/%s/'
                    % ('work/order-list'))
            #if next == "closed_work_orders":
            #    return HttpResponseRedirect('/%s/'
            #        % ('work/closed-work-orders'))




#   I N V O I C E

@login_required
def invoice_number(request):
    agent = get_agent(request)
    invoice_numbers = InvoiceNumber.objects.filter(
        created_by=request.user)
    form = InvoiceNumberForm(agent=agent, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            member = data["member"]
            nbr = form.save(commit=False)
            idate = datetime.date.today()
            nbr.invoice_date = idate
            nbr.created_date = idate
            nbr.created_by = request.user
            nbr.save()

        return HttpResponseRedirect('/%s/'
            % ('work/invoice-number',))


    return render(request, "work/invoice_number.html", {
        "help": get_help("invoice_number"),
        "agent": agent,
        "form": form,
        "invoice_numbers": invoice_numbers,
    })


# Value equations

@login_required
def value_equations_work(request, agent_id):
    context_agent = get_object_or_404(EconomicAgent, pk=agent_id)
    agent = get_agent(request)
    value_equations = ValueEquation.objects.filter(context_agent=context_agent)

    return render(request, "work/value_equations_work.html", {
        "help": get_help("value_equations"),
        "value_equations": value_equations,
        "agent": agent,
        "context_agent": context_agent,
    })

@login_required
def create_value_equation_work(request, agent_id):
    context_agent = get_object_or_404(EconomicAgent, id=agent_id)
    if request.method == "POST":
        ve_form = VEForm(data=request.POST)
        if ve_form.is_valid():
            ve = ve_form.save(commit=False)
            ve.context_agent = context_agent
            ve.created_by = request.user
            ve.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', agent_id, ve.id))

@login_required
def create_value_equation_bucket_work(request, value_equation_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    if request.method == "POST":
        veb_form = ValueEquationBucketForm(data=request.POST)
        if veb_form.is_valid():
            veb = veb_form.save(commit=False)
            veb.value_equation = ve
            veb.created_by = request.user
            veb.save()
    #import pdb; pdb.set_trace()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def edit_value_equation_work(request, value_equation_id=None, agent_id=None):
    value_equation = None
    value_equation_bucket_form = None
    if value_equation_id:
        value_equation = get_object_or_404(ValueEquation, id=value_equation_id)
        value_equation_form = VEForm(instance=value_equation)
        value_equation_bucket_form = ValueEquationBucketForm()
        context_agent = value_equation.context_agent
    else:
        value_equation_form = VEForm()
        context_agent = EconomicAgent.objects.get(pk=agent_id)
    agent = get_agent(request)
    test_results = []
    rpt_heading = ""
    if request.method == "POST":
        rule_id = int(request.POST['test'])
        vebr = ValueEquationBucketRule.objects.get(id=rule_id)
        tr = vebr.test_results()
        nbr = len(tr)
        if nbr > 50:
            nbr = 50
        count = 0
        while count < nbr:
            tr[count].claim_amount = vebr.compute_claim_value(tr[count])
            test_results.append(tr[count])
            count+=1
        rpt_heading = "Bucket " + str(vebr.value_equation_bucket.sequence) + " " + vebr.event_type.name

    return render(request, "work/edit_value_equation_work.html", {
        "value_equation": value_equation,
        "agent": agent,
        "context_agent": context_agent,
        "value_equation_form": value_equation_form,
        "value_equation_bucket_form": value_equation_bucket_form,
        "test_results": test_results,
        "rpt_heading": rpt_heading,
    })

@login_required
def change_value_equation_work(request, value_equation_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    if request.method == "POST":
        ve_form = VEForm(instance=ve, data=request.POST)
        if ve_form.is_valid():
            ve = ve_form.save(commit=False)
            ve.changed_by = request.user
            ve.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def delete_value_equation_work(request, value_equation_id, agent_id):
    ve = get_object_or_404(ValueEquation, id=value_equation_id)
    ve.delete()
    return HttpResponseRedirect('/%s/%s/'
        % ('work/value-equations-work', agent_id))

@login_required
def change_value_equation_bucket_work(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    if request.method == "POST":
        veb_form = ValueEquationBucketForm(prefix=str(veb.id), instance=veb, data=request.POST)
        if veb_form.is_valid():
            veb = veb_form.save(commit=False)
            veb.changed_by = request.user
            veb.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def delete_value_equation_bucket_work(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    veb.delete()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def create_value_equation_bucket_rule_work(request, bucket_id):
    veb = get_object_or_404(ValueEquationBucket, id=bucket_id)
    ve = veb.value_equation
    if request.method == "POST":
        vebr_form = ValueEquationBucketRuleForm(prefix=str(bucket_id), data=request.POST)
        if vebr_form.is_valid():
            vebr = vebr_form.save(commit=False)
            vebr.value_equation_bucket = veb
            vebr.created_by = request.user
            filter_form = BucketRuleFilterSetForm(context_agent=None, event_type=None, pattern=None, prefix=str(bucket_id), data=request.POST)
            if filter_form.is_valid():
                vebr.filter_rule = filter_form.serialize()
                vebr.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def change_value_equation_bucket_rule_work(request, rule_id):
    vebr = get_object_or_404(ValueEquationBucketRule, id=rule_id)
    ve = vebr.value_equation_bucket.value_equation
    if request.method == "POST":
        vebr_form = ValueEquationBucketRuleForm(prefix="vebr" + str(vebr.id), instance=vebr, data=request.POST)
        if vebr_form.is_valid():
            vebr = vebr_form.save(commit=False)
            vebr.changed_by = request.user
            filter_form = BucketRuleFilterSetForm(context_agent=None, event_type=None, pattern=None, prefix="vebrf" + str(rule_id), data=request.POST)
            if filter_form.is_valid():
                vebr.filter_rule = filter_form.serialize()
                vebr.save()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def delete_value_equation_bucket_rule_work(request, rule_id):
    vebr = get_object_or_404(ValueEquationBucketRule, id=rule_id)
    ve = vebr.value_equation_bucket.value_equation
    vebr.delete()
    return HttpResponseRedirect('/%s/%s/%s/'
        % ('work/edit-value-equation-work', ve.context_agent.id, ve.id))

@login_required
def value_equation_sandbox_work(request, value_equation_id):
    #ve = None
    #ves = ValueEquation.objects.all()
    #init = {}
    #if value_equation_id:
    ve = ValueEquation.objects.get(id=value_equation_id)
    init = {"value_equation": ve}
    context_agent = ve.context_agent
    header_form = VESandboxForm(data=request.POST or None)
    #buckets = []
    agent_totals = []
    details = []
    total = None
    hours = None
    agent_subtotals = None
    event_count = 0
    #if ves:
    #    if not ve:
    #        ve = ves[0]
    buckets = ve.buckets.all()
    if request.method == "POST":
        if header_form.is_valid():
            data = header_form.cleaned_data
            value_equation = ve #data["value_equation"]
            amount = data["amount_to_distribute"]
            serialized_filters = {}
            for bucket in buckets:
                if bucket.filter_method:
                    bucket_form = bucket.filter_entry_form(data=request.POST or None)
                    if bucket_form.is_valid():
                        ser_string = bucket_data = bucket_form.serialize()
                        serialized_filters[bucket.id] = ser_string
                        bucket.form = bucket_form
            agent_totals, details = ve.run_value_equation(amount_to_distribute=Decimal(amount), serialized_filters=serialized_filters)
            total = sum(at.quantity for at in agent_totals)
            hours = sum(d.quantity for d in details)
            #daniel = EconomicAgent.objects.get(nick="Daniel")
            #dan_details = [d for d in details if d.from_agent==daniel]
            agent_subtotals = {}
            for d in details:
                key = "-".join([str(d.from_agent.id), str(d.vebr.id)])
                if key not in agent_subtotals:
                    agent_subtotals[key] = AgentSubtotal(d.from_agent, d.vebr)
                sub = agent_subtotals[key]
                sub.quantity += d.quantity
                try:
                    sub.value += d.share
                except AttributeError:
                    sub.value = Decimal("0.0")
                try:
                    sub.distr_amt += d.distr_amt
                except AttributeError:
                    sub.distr_amt = Decimal("0.0")
                sub.rate = 0
                if sub.distr_amt and sub.quantity:
                    sub.rate = (sub.distr_amt / sub.quantity).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            agent_subtotals = list(agent_subtotals.values())
            agent_subtotals = sorted(agent_subtotals, key=methodcaller('key'))

            details.sort(key=lambda x: x.from_agent)
            event_count = len(details)

    else:
        for bucket in buckets:
            if bucket.filter_method:
                bucket.form = bucket.filter_entry_form()

    return render(request, "work/value_equation_sandbox_work.html", {
        "header_form": header_form,
        "buckets": buckets,
        "agent_totals": agent_totals,
        "details": details,
        "agent_subtotals": agent_subtotals,
        "total": total,
        "event_count": event_count,
        "hours": hours,
        "ve": ve,
        "context_agent": context_agent,
    })


def json_default_equation_work(request, event_type_id):
    et = get_object_or_404(EventType, pk=event_type_id)
    equation = et.default_event_value_equation()
    data = simplejson.dumps(equation, ensure_ascii=False)
    return HttpResponse(data, content_type="text/json-comment-filtered")
