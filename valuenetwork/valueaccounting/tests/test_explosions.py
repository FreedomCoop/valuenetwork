import datetime
from decimal import *

from django.test import TestCase
from django.test import Client

from valuenetwork.valueaccounting.models import *
from valuenetwork.valueaccounting.views import *
from valuenetwork.valueaccounting.utils import *
from valuenetwork.valueaccounting.tests.objects_for_testing import *

class ExplosionTest(TestCase):

    """Testing dependent demand explosion

        Background reading:
        http://hillside.net/plop/plop97/Proceedings/haugen.pdf
    """

    def setUp(self):

        self.user = User.objects.create_user('alice', 'alice@whatever.com', 'password')

        recipe = Recipe()
        self.recipe = recipe
        self.parent = recipe.parent
        self.child = recipe.child
        self.grandchild = recipe.grandchild
        self.unit = recipe.unit
        self.consumption_event_type = recipe.consumption_event_type

        self.order = Order(
            due_date=datetime.date.today(),
        )
        self.order.save()

        self.order.add_commitment(
            resource_type=self.parent,
            context_agent=None,
            event_type=recipe.production_event_type,
            quantity=Decimal("4"),
            description="Test",
            unit=self.unit,
        )

        self.prior_commitment = Commitment(
            resource_type=self.child,
            due_date=self.order.due_date - datetime.timedelta(weeks=4),
            quantity=Decimal(2),
            event_type=self.consumption_event_type,
            unit_of_quantity=self.unit,
        )
        self.prior_commitment.save()

        self.resource = EconomicResource(
            resource_type=self.child,
            quantity=Decimal(5),
            #unit_of_quantity=self.unit,
        )
        self.resource.save()

    def test_order_commitment(self):
        cts = self.order.order_items()
        ct = cts[0]
        self.assertEqual(cts.count(), 1)
        self.assertEqual(ct.resource_type, self.parent)

    def test_explosion(self):
        """Explode dependent demands from order item

            Including netting out inventory:
            Child input will meet onhand inventory of 5
            - prior demand of 2 = 3 still available
            which reduces the child input demand from 8 to 5.
            Which also reduces the grandchild demand from 24 to 15.

        """

        cts = self.order.order_items()
        commitment = cts[0]
        visited = []
        process = commitment.generate_producing_process(self.user, visited, explode=True)
        child_input = process.incoming_commitments()[0]
        self.assertEqual(child_input.quantity, Decimal("8"))
        child_output=child_input.associated_producing_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(grandchild_input.quantity, Decimal("15"))
        self.assertEqual(child_process.next_processes()[0], process)
        self.assertEqual(process.previous_processes()[0], child_process)

    def test_cycle(self):
        """ cycles occur when an explosion repeats itself:

            when an output resource type re-appears as a input
            later in the explosion.
            In this case, the explosion must not go into
            an infinite loop.
            As of now, it just stops exploding.
            Other behaviors may be necessary in the future.

        """

        child_pt = self.child.main_producing_process_type()
        cyclic_input = ProcessTypeResourceType(
            process_type=child_pt,
            resource_type=self.parent,
            event_type=self.consumption_event_type,
            quantity=Decimal("1"),
            unit_of_quantity=self.unit,
        )
        cyclic_input.save()
        cts = self.order.order_items()
        commitment = cts[0]
        visited = []
        process = commitment.generate_producing_process(self.user, visited, explode=True)
        child_input = process.incoming_commitments()[0]
        self.assertEqual(child_input.quantity, Decimal("8"))
        child_output=child_input.associated_producing_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[1]
        #print("+++ child_process.incoming_commitments(): "+str(child_process.incoming_commitments()))
        self.assertEqual(grandchild_input.quantity, Decimal("15"))
        cyclic_input_commitment = child_process.incoming_commitments()[0]
        self.assertEqual(cyclic_input_commitment.quantity, Decimal("5"))
        crt = cyclic_input_commitment.resource_type
        self.assertEqual(crt.producing_commitments().count(), 1)


    def test_scheduling(self):
        """ dependent demand explosion scheduling:

            The explosion initially schedules everything
            backwards from the end due date,
            using ProcessType.estimated_duration.
            Sometimes this will backschedule into the past,
            especially if considering purchase lead times.
            So those elements will need to be forward-scheduled,
            which will move their successors forward in time
            by the same duration.

            Behavior-Driven procedure description:
            Given: an order for a ResourceType with a 2-level recipe,
            due today.

            When I generate a producing process and explode the dependent demands,
            then the child process will have been backscheduled into the past,
            and the purchase lead time will also go into the past.

            When I reschedule the child process forward,
            then the child_process will no longer start in the past,
            and the end item due date will now be in the future.

            When I reschedule forward from the purchase lead time,
            then the purchase date will no longer be in the past.

        """

        #Given: an order for a ResourceType with a recipe (self.parent).
        cts = self.order.order_items()
        commitment = cts[0]
        visited = []

        #When I generate a producing process and explode the dependent demands,
        process = commitment.generate_producing_process(self.user, visited, explode=True)
        child_input = process.incoming_commitments()[0]
        rt = child_input.resource_type
        child_output=rt.producing_commitments()[0]
        child_process=child_output.process
        #then the child_process will have been backscheduled into the past,
        self.assertTrue(child_process.too_late())
        grandchild_input = child_process.incoming_commitments()[0]
        source = grandchild_input.sources()[0]
        #and the purchase lead time will also go into the past.
        self.assertTrue(source.too_late)
        lag = datetime.date.today() - child_process.start_date
        delta_days = lag.days + 1

        #When I reschedule the child process forward,
        child_process.reschedule_forward(delta_days, self.user)
        #(get the parent_process again because it has changed)
        parent_process = Process.objects.get(id=process.id)
        #then the child_process will no longer start in the past,
        self.assertFalse(child_process.too_late())
        #and the end item due date will now be in the future.
        self.assertTrue(parent_process.end_date > datetime.date.today())

        #When I reschedule forward from the purchase lead time,
        grandchild_input.reschedule_forward_from_source(source.lead_time, self.user)
        #(get the grandchild_input and source again because they have changed)
        grandchild_input = child_process.incoming_commitments()[0]
        source = grandchild_input.sources()[0]
        #then the purchase date will no longer be in the past.
        self.assertFalse(source.too_late)

    def test_commitment_change_propagation(self):
        """Propagate changes to dependants

        """

        cts = self.order.order_items()
        commitment = cts[0]

        # set up the process flow to be changed
        visited = []
        process = commitment.generate_producing_process(self.user, visited, explode=True)
        child_input = process.incoming_commitments()[0]
        self.assertEqual(child_input.quantity, Decimal("8"))
        child_output=child_input.associated_producing_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(grandchild_input.quantity, Decimal("15"))

        #change input quantity
        new_rt = child_input.resource_type
        new_qty = Decimal("10")
        explode = handle_commitment_changes(
            child_input,
            new_rt,
            new_qty,
            self.order,
            self.order)
        child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("7"))
        self.assertEqual(grandchild_input.quantity, Decimal("21"))
        self.assertFalse(explode)
        new_qty = Decimal("8")
        explode = handle_commitment_changes(
            child_input,
            new_rt,
            new_qty,
            self.order,
            self.order)
        child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(grandchild_input.quantity, Decimal("15"))

        # change output quantity
        new_rt = commitment.resource_type
        new_qty = Decimal("8")
        explode = handle_commitment_changes(
            commitment,
            new_rt,
            new_qty,
            self.order,
            self.order)
        child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("18"))
        self.assertEqual(grandchild_input.quantity, Decimal("54"))
        self.assertFalse(explode)

        #change input resource type
        new_rt = EconomicResourceType(
            name="changed resource type",
        )
        new_rt.save()
        explode = handle_commitment_changes(
            child_input,
            new_rt,
            new_qty,
            self.order,
            self.order)
        child_input.resource_type = new_rt
        child_input.save()
        child_outputs=child_input.associated_producing_commitments()
        self.assertEqual(len(child_outputs), 0)
        self.assertTrue(explode)

    def test_api_commitment_change_propagation(self):
        """Propagate changes to dependants
            using the methods called by
            the graphql api

        """

        cts = self.order.order_items()
        commitment = cts[0]

        # set up the process flow to be changed
        visited = []
        process = commitment.generate_producing_process(self.user, visited, explode=True)
        child_input = process.incoming_commitments()[0]
        self.assertEqual(child_input.quantity, Decimal("8"))
        child_output=child_input.associated_producing_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(grandchild_input.quantity, Decimal("15"))

        #change input quantity
        new_rt = child_input.resource_type
        new_qty = Decimal("10")
        child_input.quantity = new_qty
        explode = child_input.handle_commitment_changes()
        #child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("7"))
        self.assertEqual(grandchild_input.quantity, Decimal("21"))
        self.assertFalse(explode)
        new_qty = Decimal("8")
        child_input.quantity = new_qty
        explode = child_input.handle_commitment_changes()
        #child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("5"))
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(grandchild_input.quantity, Decimal("15"))

        # change output quantity
        new_rt = commitment.resource_type
        new_qty = Decimal("8")
        commitment.quantity = new_qty
        explode = commitment.handle_commitment_changes()
        #child_input.quantity = new_qty
        child_input.save()
        child_output=child_input.associated_producing_commitments()[0]
        child_process=child_output.process
        grandchild_input = child_process.incoming_commitments()[0]
        self.assertEqual(child_output.quantity, Decimal("18"))
        self.assertEqual(grandchild_input.quantity, Decimal("54"))
        self.assertFalse(explode)

        #change input resource type
        new_rt = EconomicResourceType(
            name="changed resource type",
        )
        new_rt.save()
        child_input.resource_type = new_rt
        explode = child_input.handle_commitment_changes()
        #child_input.resource_type = new_rt
        child_input.save()
        child_outputs=child_input.associated_producing_commitments()
        self.assertEqual(len(child_outputs), 0)
        self.assertTrue(explode)
