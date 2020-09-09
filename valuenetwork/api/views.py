import datetime
import time
import csv
import copy
from operator import itemgetter, attrgetter, methodcaller

from django.db.models import Q
from django.http import HttpResponse, HttpResponseServerError, Http404, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.template import RequestContext
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.core.exceptions import MultipleObjectsReturned
from django.forms import ValidationError
import json as simplejson
from collections import OrderedDict
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.auth.models import User, Group

from rest_framework import viewsets, permissions

from valuenetwork.api.serializers import *

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.utils import get_url_starter, camelcase, camelcase_lower

from rdflib import Graph, Literal, BNode
from rdflib.serializer import Serializer
from rdflib import Namespace, URIRef
from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS

import sys
if sys.version_info >= (3, 0):
    from urllib.request import urlopen
else:
    from urllib.request import urlopen

from io import StringIO

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class UserCreationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be created.
    """
    queryset = User.objects.all()
    serializer_class = UserCreationSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def post_save(self, obj, created=False):
        """
        On creation, replace the raw password with a hashed version.
        """
        if created:
            obj.set_password(obj.password)
            obj.save()


class PeopleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows people to be viewed or edited.
    """
    queryset = EconomicAgent.objects.individuals()
    serializer_class = PeopleSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class ContextViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows context agents to be viewed or edited.
    """
    queryset = EconomicAgent.objects.context_agents()
    serializer_class = ContextSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class AgentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows all Economic Agents to be viewed or edited.
    """
    queryset = EconomicAgent.objects.all()
    serializer_class = EconomicAgentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class AgentCreationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Economic Agents created.
    """
    queryset = EconomicAgent.objects.all()
    serializer_class = EconomicAgentCreationSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class AgentUserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows AgentUsers to be viewed, edited or created.
    """
    queryset = AgentUser.objects.all()
    serializer_class = AgentUserSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)


class AgentTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Agent Types to be viewed or edited.
    """
    queryset = AgentType.objects.all()
    serializer_class = AgentTypeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class EconomicEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Economic Events to be viewed or edited.
    You may use a query parameter, ?context={ context agent.slug },
    for example, ?context=breathing-games
    Slugs can be found on the API context list.

    More query parameters and filters to come, on request.
    """
    serializer_class = EconomicEventSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        """
        Optionally restricts the returned purchases to a given user,
        by filtering against a `username` query parameter in the URL.
        """
        queryset = EconomicEvent.objects.all()
        context_slug = self.request.QUERY_PARAMS.get('context', None)
        if context_slug is not None:
            queryset = queryset.filter(context_agent__slug=context_slug)
        return queryset

class ContributionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Economic Events that are contributions
    to be viewed or edited.
    You may use query parameters:

    ?context={ context_agent.slug },
        for example, ?context=pv-characterization
        Slugs can be found on the API context list.

    ?event-type={ event type.relationship },
        for example, ?event-type=work
        Relationships can be found on the API event-type list.

    To combine parameters, use &,
        for example, ?context=pv-characterization&event-type=work

    More query parameters and filters to come, on request.
    """
    serializer_class = ContributionSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        queryset = EconomicEvent.objects.filter(is_contribution=True)
        context_slug = self.request.QUERY_PARAMS.get('context', None)
        if context_slug is not None:
            queryset = queryset.filter(context_agent__slug=context_slug)
        event_type_relationship = self.request.QUERY_PARAMS.get('event-type', None)
        if event_type_relationship is not None:
            queryset = queryset.filter(event_type__relationship=event_type_relationship)
        return queryset

class EventTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Agent Types to be viewed or edited.
    """
    queryset = EventType.objects.all()
    serializer_class = EventTypeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class ResourceTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Agent Types to be viewed or edited.
    """
    queryset = EconomicResourceType.objects.all()
    serializer_class = ResourceTypeSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class EconomicResourceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Agent Types to be viewed or edited.
    """
    queryset = EconomicResource.objects.all()
    serializer_class = EconomicResourceSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

class UnitViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Agent Types to be viewed or edited.
    """
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

#the following methods relate to providing linked open data from NRP instances, for the valueflows vocab project.
#they use rdflib, Copyright (c) 2012-2015, RDFLib Team All rights reserved.

def get_lod_setup_items():

    path = get_url_starter() + "/api/"
    instance_abbrv = Site.objects.get_current().domain.split(".")[0]

    context = {
        "vf": "https://w3id.org/valueflows/",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        #"rdfs:label": { "@container": "@language" },
        "Agent": "vf:Agent",
        "Person": "vf:Person",
        "Group": "vf:Group",
        #"Organization": "vf:Organization",
        "url":  { "@id": "vf:url", "@type": "@id" },
        "image": { "@id": "vf:image", "@type": "@id" },
        #"displayName": "vf:displayName",
        #"displayNameMap": { "@id": "displayName", "@container": "@language" },
        "Relationship": "vf:Relationship",
        "subject": { "@id": "vf:subject", "@type": "@id" },
        "object": { "@id": "vf:object", "@type": "@id" },
        "relationship": { "@id": "vf:relationship", "@type": "@id" },
        #"member": { "@id": "vf:member", "@type": "@id" }
        "label": "skos:prefLabel",
        "labelMap": { "@id": "skos:prefLabel", "@container": "@language" },
        "note": "skos:note",
        "noteMap": { "@id": "skos:note", "@container": "@language" },
        "inverseOf": "owl:inverseOf",
        instance_abbrv: path,
    }

    store = Graph()
    #store.bind("foaf", FOAF)
    store.bind("rdf", RDF)
    store.bind("rdfs", RDFS)
    store.bind("owl", OWL)
    store.bind("skos", SKOS)
    #as_ns = Namespace("http://www.w3.org/ns/activitystreams#")
    #store.bind("as", as_ns)
    #schema_ns = Namespace("http://schema.org/")
    #store.bind("schema", schema_ns)
    #at_ns = Namespace(path + "agent-type/")
    #store.bind("at", at_ns)
    #aat_ns = Namespace(path + "agent-relationship-type/")
    #store.bind("aat", aat_ns)
    vf_ns = Namespace("https://w3id.org/valueflows/")
    store.bind("vf", vf_ns)
    instance_ns = Namespace(path)
    store.bind("instance", instance_ns)

    return path, instance_abbrv, context, store, vf_ns


def agent_type_lod(request, agent_type_name):
    ats = AgentType.objects.all()
    agent_type = None

    for at in ats:
        if camelcase(at.name) == agent_type_name:
            agent_type = at

    if not agent_type:
        return HttpResponse({}, content_type='application/json')


    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    if agent_type.name != "Person" and agent_type.name != "Group" and agent_type.name != "Individual":
        class_name = camelcase(agent_type.name)
        ref = URIRef(instance_abbrv + ":agent-type-lod/" +class_name)
        store.add((ref, RDF.type, OWL.Class))
        store.add((ref, SKOS.prefLabel, Literal(class_name, lang="en")))
        if agent_type.party_type == "individual":
            store.add((ref, RDFS.subClassOf, vf_ns.Person))
        else:
            store.add((ref, RDFS.subClassOf, vf_ns.Group))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render_to_response("valueaccounting/agent_type.html", {
    #    "agent_type": agent_type,
    #}, context_instance=RequestContext(request))

def agent_relationship_type_lod(request, agent_assoc_type_name):
    aats = AgentAssociationType.objects.all()
    agent_assoc_type = None
    for aat in aats:
        if camelcase_lower(aat.label) == agent_assoc_type_name:
            agent_assoc_type = aat
            inverse = False
        elif camelcase_lower(aat.inverse_label) == agent_assoc_type_name:
            agent_assoc_type = aat
            inverse = True

    if not agent_assoc_type:
        return HttpResponse({}, content_type='application/json')

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    if inverse:
        property_name = camelcase_lower(agent_assoc_type.inverse_label)
        inverse_property_name = camelcase_lower(agent_assoc_type.label)
        label = agent_assoc_type.inverse_label
    else:
        property_name = camelcase_lower(agent_assoc_type.label)
        inverse_property_name = camelcase_lower(agent_assoc_type.inverse_label)
        label = agent_assoc_type.label
    ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inverse_property_name)
    store.add((ref, RDF.type, RDF.Property))
    store.add((ref, SKOS.prefLabel, Literal(label, lang="en")))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render_to_response("valueaccounting/agent_assoc_type.html", {
    #    "agent_assoc_type": agent_assoc_type,
    #}, context_instance=RequestContext(request))

def agent_relationship_lod(request, agent_assoc_id):
    aa = AgentAssociation.objects.filter(id=agent_assoc_id)
    if not aa:
        return HttpResponse({}, content_type='application/json')
    else:
        agent_association = aa[0]

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(agent_association.id) + "/")
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(agent_association.id) + "/")
    ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.is_associate.id) + "/")
    ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.has_associate.id) + "/")
    property_name = camelcase_lower(agent_association.association_type.label)
    ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type/" + property_name)
    store.add((ref, RDF.type, vf_ns["Relationship"]))
    store.add((ref, vf_ns["subject"], ref_subject))
    store.add((ref, vf_ns["object"], ref_object))
    store.add((ref, vf_ns["relationship"], ref_relationship))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render_to_response("valueaccounting/agent_association.html", {
    #    "agent_association": agent_association,
    #}, context_instance=RequestContext(request))


def agent_relationship_inv_lod(request, agent_assoc_id):
    aa = AgentAssociation.objects.filter(id=agent_assoc_id)
    if not aa:
        return HttpResponse({}, content_type='application/json')
    else:
        agent_association = aa[0]

    from rdflib import Graph, Literal, BNode
    from rdflib.namespace import FOAF, RDF, RDFS, OWL, SKOS
    from rdflib.serializer import Serializer
    from rdflib import Namespace, URIRef

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(agent_association.id) + "/")
    inv_ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(agent_association.id) + "/")
    ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.is_associate.id) + "/")
    ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(agent_association.has_associate.id) + "/")
    property_name = camelcase_lower(agent_association.association_type.inverse_label)
    ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
    store.add((ref, RDF.type, vf_ns["Relationship"]))
    store.add((ref, vf_ns["subject"], ref_subject))
    store.add((ref, vf_ns["object"], ref_object))
    store.add((ref, vf_ns["relationship"], ref_relationship))
    store.add((ref, OWL.inverseOf, inv_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')
    #return render_to_response("valueaccounting/agent_association.html", {
    #    "agent_association": agent_association,
    #}, context_instance=RequestContext(request))

def agent_lod(request, agent_id):
    agents = EconomicAgent.objects.filter(id=agent_id)
    if not agents:
        return HttpResponse({}, content_type='application/json')

    agent = agents[0]
    subject_assocs = agent.all_is_associates()
    object_assocs = agent.all_has_associates()

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    #Lynn: I made a change here for consistency. Please check and fix if needed.
    ref = URIRef(instance_abbrv + ":agent-lod/" + str(agent.id) + "/")
    if agent.agent_type.name == "Individual" or agent.agent_type.name == "Person":
        store.add((ref, RDF.type, vf_ns.Person))
    #elif agent.agent_type.name == "Organization":
    #    store.add((ref, RDF.type, vf_ns.Organization))
    else:
        at_class_name = camelcase(agent.agent_type.name)
        ref_class = URIRef(instance_abbrv + ":agent-type-lod/" + at_class_name)
        store.add((ref, RDF.type, ref_class))
    store.add((ref, vf_ns["label"], Literal(agent.name, lang="en")))
    #if agent.photo_url:
    #    store.add((ref, vf_ns["image"], agent.photo_url))

    #if subject_assocs or object_assocs:
    #    store.add((  ))
    if subject_assocs:
        for a in subject_assocs:
            obj_ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(a.id) + "/")
            property_name = camelcase_lower(a.association_type.label)
            ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
            store.add((ref, ref_relationship, obj_ref))
    if object_assocs:
        for a in object_assocs:
            subj_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(a.id) + "/")
            inv_property_name = camelcase_lower(a.association_type.inverse_label)
            inv_ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inv_property_name)
            store.add((ref, inv_ref_relationship, subj_ref))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    return HttpResponse(ser, content_type='application/json')

#following method supplied by Niklas at rdflib-jsonld support to get the desired output for nested rdf inputs for rdflib
def simplyframe(data):
    items, refs = {}, {}
    for item in data['@graph']:
        itemid = item.get('@id')
        if itemid:
            items[itemid] = item
        for vs in list(item.values()):
            for v in [vs] if not isinstance(vs, list) else vs:
                if isinstance(v, dict):
                    refid = v.get('@id')
                    if refid and refid.startswith('_:'):
                        refs.setdefault(refid, (v, []))[1].append(item)
    for ref, subjects in list(refs.values()):
        if len(subjects) == 1:
            ref.update(items.pop(ref['@id']))
            del ref['@id']
    data['@graph'] = list(items.values())

def agent_jsonld(request):
    #test = "{'@context': 'http://json-ld.org/contexts/person.jsonld', '@id': 'http://dbpedia.org/resource/John_Lennon', 'name': 'John Lennon', 'born': '1940-10-09', 'spouse': 'http://dbpedia.org/resource/Cynthia_Lennon' }"
    #test = '{ "@id": "http://nrp.webfactional.com/accounting/agent-lod/1", "@type": "Person", "vf:label": { "@language": "en", "@value": "Bob Haugen" } }'
    #return HttpResponse(test, content_type='application/json')

    path, instance_abbrv, context, store, vf_ns = get_lod_setup_items()

    agent_types = AgentType.objects.all()
    for at in agent_types:
        #if at.name != "Person" and at.name != "Organization" and at.name != "Group" and at.name != "Individual":
        if at.name != "Person" and at.name != "Group" and at.name != "Individual":
            class_name = camelcase(at.name)
            #ref = URIRef(at_ns[class_name])
            ref = URIRef(instance_abbrv + ":agent-type-lod/" +class_name)
            store.add((ref, RDF.type, OWL.Class))
            store.add((ref, SKOS.prefLabel, Literal(class_name, lang="en")))
            if at.party_type == "individual":
                store.add((ref, RDFS.subClassOf, vf_ns.Person))
            else:
                store.add((ref, RDFS.subClassOf, vf_ns.Group))

    aa_types = AgentAssociationType.objects.all()
    for aat in aa_types:
        property_name = camelcase_lower(aat.label)
        inverse_property_name = camelcase_lower(aat.inverse_label)
        ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
        store.add((ref, RDF.type, RDF.Property))
        store.add((ref, SKOS.prefLabel, Literal(aat.label, lang="en")))
        #inverse = BNode()
        #store.add((ref, OWL.inverseOf, inverse))
        #store.add((inverse, RDFS.label, Literal(aat.inverse_label, lang="en")))
        if property_name != inverse_property_name:
            inv_ref = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inverse_property_name)
            store.add((inv_ref, RDF.type, RDF.Property))
            store.add((inv_ref, SKOS.prefLabel, Literal(aat.inverse_label, lang="en")))
        store.add((ref, OWL.inverseOf, inv_ref))
        store.add((inv_ref, OWL.inverseOf, ref))

    associations = AgentAssociation.objects.filter(state="active")
    agents = [assn.is_associate for assn in associations]
    agents.extend([assn.has_associate for assn in associations])
    agents = list(set(agents))

    for agent in agents:
        ref = URIRef(instance_abbrv + ":agent-lod/" + str(agent.id) + "/")
        if agent.agent_type.name == "Individual" or agent.agent_type.name == "Person":
            store.add((ref, RDF.type, vf_ns.Person))
        #elif agent.agent_type.name == "Organization":
        #    store.add((ref, RDF.type, vf_ns.Organization))
        else:
            at_class_name = camelcase(agent.agent_type.name)
            ref_class = URIRef(instance_abbrv + ":agent-type-lod/" + at_class_name)
            store.add((ref, RDF.type, ref_class))
        store.add((ref, vf_ns["label"], Literal(agent.name, lang="en")))
        #if agent.name != agent.nick:
        #    store.add((ref, FOAF.nick, Literal(agent.nick, lang="en")))
        #if agent.photo_url:
        #    store.add((ref, vf_ns["image"], agent.photo_url))

    for a in associations:
        ref = URIRef(instance_abbrv + ":agent-relationship-lod/" + str(a.id) + "/")
        inv_ref = URIRef(instance_abbrv + ":agent-relationship-inv-lod/" + str(a.id) + "/")
        ref_subject = URIRef(instance_abbrv + ":agent-lod/" + str(a.is_associate.id) + "/")
        ref_object = URIRef(instance_abbrv + ":agent-lod/" + str(a.has_associate.id) + "/")
        property_name = camelcase_lower(a.association_type.label)
        inv_property_name = camelcase_lower(a.association_type.inverse_label)
        ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + property_name)
        inv_ref_relationship = URIRef(instance_abbrv + ":agent-relationship-type-lod/" + inv_property_name)
        store.add((ref, RDF.type, vf_ns["Relationship"]))
        store.add((ref, vf_ns["subject"], ref_subject))
        store.add((ref, vf_ns["object"], ref_object))
        store.add((ref, vf_ns["relationship"], ref_relationship))
        store.add((inv_ref, RDF.type, vf_ns["Relationship"]))
        store.add((inv_ref, vf_ns["object"], ref_subject))
        store.add((inv_ref, vf_ns["subject"], ref_object))
        store.add((inv_ref, vf_ns["relationship"], inv_ref_relationship))

    ser = store.serialize(format='json-ld', context=context, indent=4)
    #import json
    #data = json.loads(ser)
    #simplyframe(data)
    #return HttpResponse(json.dumps(data, indent=4), content_type='application/json')
    return HttpResponse(ser, content_type='application/json')

def agent_jsonld_query(request):


    g = Graph()
    url = "http://nrp.webfactional.com/api/agent-jsonld/"
    remote_jsonld = urlopen(url).read()
    dict_data = simplejson.loads(remote_jsonld)
    context = dict_data["@context"]
    graph = dict_data["@graph"]
    local_graph = simplejson.dumps(graph)
    g.parse(StringIO(str(local_graph)), context=context, format="json-ld")
    local_expanded_json = g.serialize(format="json-ld", indent=4)
    local_expanded_dict = simplejson.loads(local_expanded_json)


    result = ""
    agents = [x for x in graph if x['@id'].find('agent-lod') > -1]
    agent_dict = {}
    for a in agents:
        agent_dict[str(a['@id'])] = a

    rels = [x for x in graph if x['@type']=='Relationship']

    agent_rels = []
    for r in rels:
        d = {}
        d["subject"] = agent_dict[r["subject"]]
        d["object"] = agent_dict[r["object"]]
        d["relationship"] = r["relationship"]
        agent_rels.append(d)

    for ar in agent_rels:
        object = ar['object']
        object_type = object['@type']
        if object_type.find('/') > -1:
            object_type = object_type.split('/')[1]
        object_label = object['vf:label']['@value']
        subject = ar['subject']
        subject_type = subject['@type']
        if subject_type.find('/') > -1:
            subject_type = subject_type.split('/')[1]
        subject_label = subject['vf:label']['@value']
        relationship = ar['relationship']
        if relationship.find('/') > -1:
            relationship = relationship.split('/')[1]
        ostr = ", a ".join([object_label, object_type])
        sstr = ", a ".join([subject_label, subject_type])
        line = " ".join([ sstr, relationship, ostr])
        result += line + "\n"
    result += "\n"
    result += "========== Gory details from http://nrp.webfactional.com/accounting/agent-jsonld/ ==========\n"

    for item in local_expanded_dict:
        for key, value in list(item.items()):
            if type(value) is list:
                value = value[0]
                if type(value) is dict:
                    valist = []
                    for key2, value2 in list(value.items()):
                        valist.append(": ".join([key2, value2]))
                    value = ", ".join(valist)
            line = ": ".join([key, value])
            result += line + "\n"
        result += "========== \n"

    return HttpResponse(result, content_type='text/plain')

