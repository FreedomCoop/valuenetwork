import datetime
from decimal import *

from django.test import TestCase
from django.test import Client

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.tests.objects_for_testing import *

class FacetTest(TestCase):

    """Testing Facets and ProcessPatterns 

        and ResourceType-Pattern FacetValue matching.

    """

    def setUp(self):

        facets = Facets()
        
        self.domain = facets.domain        
        self.source = facets.source
        self.optical_pattern = facets.optical_pattern
        self.electronic_pattern = facets.electronic_pattern
        self.electroptical_pattern = facets.electroptical_pattern
        self.twofacet_pattern = facets.twofacet_pattern
        self.event_type = facets.event_type
        self.optical_product = facets.optical_product
        self.electronic_product = facets.electronic_product
        self.twofacet_product = facets.twofacet_product
        self.other_product = facets.other_product
        self.full_pattern = facets.full_pattern
        self.event_type_cite = facets.event_type_cite
        self.event_type_use = facets.event_type_use
        self.event_type_consume = facets.event_type_consume
        self.event_type_work = facets.event_type_work
        
    def test_facet_values(self):
        value_list = self.source.value_list()
        self.assertEqual(value_list, 'Them, Us')

    def test_optical_pattern_resource_types(self):
        rts = self.optical_pattern.get_resource_types(self.event_type)
        self.assertEqual(rts.count(), 1)
        self.assertEqual(rts[0], self.optical_product)

    def test_electronic_pattern_resource_types(self):
        """Pattern-ResourceType FacetValue matching rules for this test:

            The electronic_pattern has one FacetValue:
                Facet: Domain, Value: Electronic
            So the electronic and twofacet_products all match.
            The fact that the twofacet_product has another facet does not matter.
            
        """
        rts = self.electronic_pattern.get_resource_types(self.event_type)
        self.assertEqual(rts.count(), 2)
        self.assertTrue(self.electronic_product in rts)
        self.assertTrue(self.twofacet_product in rts)

    def test_electroptical_pattern_resource_types(self):
        """Pattern-ResourceType FacetValue matching rules for this test:

            If a Pattern has more than one FacetValue in the same Facet,
            for a ResourceType to match, it must match one of the FacetValues 
            in that same Facet.
            So in this case:
            The electroptical_pattern has the following FacetValues:
                Domain: Electronic
                Domain: Optical
            So the electronic, optical and twofacet_products all match.
            The fact that the twofacet_product has another facet does not matter.
            
        """
        rts = self.electroptical_pattern.get_resource_types(self.event_type)
        self.assertEqual(rts.count(), 3)
        self.assertTrue(self.electronic_product in rts)
        self.assertTrue(self.optical_product in rts)
        self.assertTrue(self.twofacet_product in rts)

    def test_twofacet_pattern_resource_types(self):
        """Pattern-ResourceType FacetValue matching rules for this test:

            If a Pattern has FacetValues in more than one different Facet,
            for a ResourceType to match, it must have FacetValues
            in each of the Facets in the Pattern, 
            and its FacetValues must match one of the FacetValues 
            in the same Facet in the Pattern.
            So in this case:
            The twofacet_pattern has the following FacetValues:
                Domain: Electronic
                Source: Us
            So only the twofacet_product matches.
            
        """
        rts = self.twofacet_pattern.get_resource_types(self.event_type)
        self.assertEqual(rts.count(), 1)
        self.assertEqual(rts[0], self.twofacet_product)

    def test_full_pattern_resource_types(self):
        """The full pattern has a full set of event types:

            produced, consumed, used, cited and work.
            The produced facets are the same as the twofacet_pattern.
            
        """
        rts = self.full_pattern.get_resource_types(self.event_type)
        self.assertEqual(rts.count(), 1)
        self.assertEqual(rts[0], self.twofacet_product)
        rts = self.full_pattern.get_resource_types(self.event_type_cite)
        self.assertEqual(rts.count(), 1)
        rts = self.full_pattern.get_resource_types(self.event_type_use)
        self.assertEqual(rts.count(), 2)
        rts = self.full_pattern.get_resource_types(self.event_type_consume)
        self.assertEqual(rts.count(), 1)
        rts = self.full_pattern.get_resource_types(self.event_type_work)
        self.assertEqual(rts.count(), 1)

    def test_event_type_for_resource_type(self):
        et = self.electronic_pattern.base_event_type_for_resource_type(
            "out",
            self.electronic_product)
        self.assertEqual(et, self.event_type)

    def test_no_event_type_for_resource_type(self):
        et = self.electronic_pattern.base_event_type_for_resource_type(
            "out",
            self.other_product)
        self.assertEqual(et, None)

    def test_fallback_event_type_for_resource_type(self):
        """If a Pattern does not have a configured EventType for a ResourceType,

            it will do the best it can so the caller gets a working EventType.
            base_event_type_for_resource_type (in test_no_event_type_for_resource_type)
            does not try.

        """
        et = self.electronic_pattern.event_type_for_resource_type(
            "out",
            self.other_product)
        self.assertEqual(et, self.event_type)

        
        
        

