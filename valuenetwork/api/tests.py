from django.test import TestCase
from django.contrib.auth.models import User
from valuenetwork.valueaccounting.models import *
from pinax.notifications.models import NoticeSetting, NoticeType
from valuenetwork.api.models import *
from .schema import schema
import datetime

import logging
logger = logging.getLogger("graphql.execution.executor").addHandler(logging.NullHandler())
# Note: if you want to see the executor error messages,
# comment out the line above and uncomment the one below:
#logging.basicConfig()

class MockContext:
    user = None

class APITest(TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ['DJANGO_SETTINGS_MODULE'] = 'valuenetwork.settings'
        super(APITest, cls).setUpClass()
        import django
        django.setup()

    def setUp(self):
        # agent data
        at_person = AgentType.objects.get(name="Individual")
        at_org = AgentType.objects.get(name="Organization")
        aat_member = AgentAssociationType.objects.get(identifier="member")
        aat_supplier = AgentAssociationType.objects.get(identifier="supplier")
        test_user, _ = User.objects.get_or_create(username='testUser11222')
        test_user.set_password('123456')
        test_user.save()
        test_agent, _ = EconomicAgent.objects.get_or_create(nick='testUser11222', agent_type=at_person)
        test_agent.name = 'testUser11222'
        if test_user not in test_agent.users.all():
            from valuenetwork.valueaccounting.models import AgentUser
            agent_user, _ = AgentUser.objects.get_or_create(agent=test_agent, user=test_user)
            test_agent.users.add(agent_user)
        test_agent.save()
        notice_type = NoticeType(
            label="api_test",
            display="api test",
            default=0,
            )
        notice_type.save()
        notice_set = NoticeSetting(
            notice_type=notice_type,
            send=True,
            user=test_user,
            )
        notice_set.save()
        org1 = EconomicAgent(
            name="org1",
            nick="org1",
            agent_type=at_org,
            )
        org1.save()
        org2 = EconomicAgent(
            name="org2",
            nick="org2",
            agent_type=at_org,
            )
        org2.save()
        another_person = EconomicAgent(
            name="not user",
            nick="not user",
            agent_type=at_person,
            )
        another_person.save()
        supplier = EconomicAgent(
            name="supp1",
            nick="supp1",
            agent_type=at_org,
            )
        supplier.save()
        test_agent_org1 = AgentAssociation(
            is_associate=test_agent,
            has_associate=org1,
            association_type=aat_member,
            )
        test_agent_org1.save()
        another_person_org1 = AgentAssociation(
            is_associate=another_person,
            has_associate=org1,
            association_type=aat_member,
            )
        another_person_org1.save()
        test_agent_org2 = AgentAssociation(
            is_associate=test_agent,
            has_associate=org2,
            association_type=aat_member,
            )
        test_agent_org2.save()
        supplier_org1 = AgentAssociation(
            is_associate=supplier,
            has_associate=org1,
            association_type=aat_supplier,
            )
        supplier_org1.save()

        # resource data
        unit_each = Unit(
            unit_type = "quantity",
            abbrev = "EA",
            name = "Each",
            )
        unit_each.save()
        unit_hours = Unit(
            unit_type = "time",
            abbrev = "HR",
            name = "Hours",
            )
        unit_hours.save()
        rti1 = EconomicResourceType(
            name='component1',
            unit=unit_each,
            behavior="consumed",
            inventory_rule="yes",
            )
        rti1.save()
        rti3 = EconomicResourceType(
            name='product1',
            unit=unit_each,
            behavior="produced",
            inventory_rule="yes",
            )
        rti3.save()
        rti2 = EconomicResourceType(
            name='work1',
            unit=unit_hours,
            behavior="work",
            inventory_rule="never",
            )
        rti2.save()
        res1 = EconomicResource(
            resource_type=rti1,
            identifier="a-component",
            quantity=5,
            )
        res1.save()
        res2 = EconomicResource(
            resource_type=rti1,
            identifier="another-component",
            quantity=100,
            )
        res2.save()
        res3 = EconomicResource(
            resource_type=rti3,
            identifier="a-product",
            quantity=20,
            )
        res3.save()
        arr1 = AgentResourceRoleType(
            name="owner",
            is_owner=True,
            )
        arr1.save()
        arr2 = AgentResourceRoleType(
            name="custodian",
            is_owner=False,
            )
        arr2.save()
        a1r3 = AgentResourceRole(
            agent=org1,
            resource=res3,
            role=arr1,
            )
        a1r3.save()
        a1r2 = AgentResourceRole(
            agent=org1,
            resource=res2,
            role=arr1,
            )
        a1r2.save()
        a1r1 = AgentResourceRole(
            agent=org1,
            resource=res1,
            role=arr2,
            )
        a1r1.save()

        # order-process-commitment-event data

        pt1 = ProcessType(
            name="pt1",
            context_agent=org1,
            estimated_duration=300,
            )
        pt1.save()
        proc1 = Process(
            name="proc1",
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=5),
            finished=False,
            context_agent=org1,
            process_type=pt1,
            )
        proc1.save()
        proc2 = Process(
            name="proc2",
            start_date=datetime.date.today() - datetime.timedelta(days=5),
            end_date=datetime.date.today() - datetime.timedelta(days=2),
            finished=True,
            context_agent=org1,
            )
        proc2.save()
        proc3 = Process(
            name="proc3",
            start_date=datetime.date.today() + datetime.timedelta(days=10),
            end_date=datetime.date.today() + datetime.timedelta(days=15),
            finished=False,
            context_agent=org2,
            )
        proc3.save()
        order1 = Order(
            name="order1",
            due_date=proc3.end_date,
            order_date=proc1.start_date,
            provider=org1,
            order_type="rand",
            )
        order1.save()
        proc1.plan = order1
        proc1.save()
        proc2.plan = order1
        proc2.save()
        proc3.plan = order1
        proc3.save()
        et_cite = EventType.objects.get(name="Citation")
        et_produce = EventType.objects.get(name="Resource Production")
        et_todo = EventType.objects.get(name="Todo")
        et_use = EventType.objects.get(name="Resource use")
        et_work = EventType.objects.get(name="Time Contribution")
        et_tobechanged = EventType.objects.get(name="To Be Changed")
        et_change = EventType.objects.get(name="Change")
        et_consume = EventType.objects.get(name="Resource Consumption")
        proc1_c1 = Commitment(
            event_type=et_work,
            due_date=datetime.date.today() + datetime.timedelta(days=10),
            from_agent=test_agent,
            resource_type=rti2,
            process=proc1,
            context_agent=org1,
            quantity=3,
            unit_of_quantity=unit_hours,
            independent_demand=order1,
            )
        proc1_c1.save()
        proc1_c2 = Commitment(
            event_type=et_work,
            due_date=datetime.date.today() + datetime.timedelta(days=10),
            from_agent=another_person,
            resource_type=rti2,
            process=proc1,
            context_agent=org1,
            quantity=2.5,
            unit_of_quantity=unit_hours,
            independent_demand=order1,
            )
        proc1_c2.save()
        proc1_c3 = Commitment(
            event_type=et_consume,
            due_date=datetime.date.today() + datetime.timedelta(days=10),
            #from_agent=another_person,
            resource_type=rti1,
            process=proc1,
            context_agent=org1,
            quantity=3,
            unit_of_quantity=unit_each,
            independent_demand=order1,
            )
        proc1_c3.save()
        proc1_c4 = Commitment(
            event_type=et_produce,
            due_date=datetime.date.today() + datetime.timedelta(days=10),
            #from_agent=another_person,
            resource_type=rti3,
            process=proc1,
            context_agent=org1,
            quantity=1,
            unit_of_quantity=unit_each,
            independent_demand=order1,
            )
        proc1_c4.save()
        proc1_e1 = EconomicEvent(
            event_type=et_work,
            event_date=datetime.date.today(),
            from_agent=test_agent,
            resource_type=rti2,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(1),
            unit_of_quantity=unit_hours,
            commitment=proc1_c1,
            )
        proc1_e1.save()
        proc1_e2 = EconomicEvent(
            event_type=et_work,
            event_date=datetime.date.today() + datetime.timedelta(days=1),
            from_agent=test_agent,
            resource_type=rti2,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(1.5),
            unit_of_quantity=unit_hours,
            commitment=proc1_c1,
            )
        proc1_e2.save()
        proc1_e3 = EconomicEvent(
            event_type=et_work,
            event_date=datetime.date.today() + datetime.timedelta(days=1),
            from_agent=another_person,
            resource_type=rti2,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(3),
            unit_of_quantity=unit_hours,
            commitment=proc1_c2,
            )
        proc1_e3.save()
        proc1_e4 = EconomicEvent(
            event_type=et_consume,
            event_date=datetime.date.today(),
            #from_agent=another_person,
            resource_type=rti1,
            resource=res1,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(3),
            unit_of_quantity=unit_each,
            commitment=proc1_c3,
            )
        proc1_e4.save()
        proc1_e5 = EconomicEvent(
            event_type=et_produce,
            event_date=datetime.date.today() + datetime.timedelta(days=3),
            from_agent=org1,
            resource_type=rti3,
            resource=res3,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(1),
            unit_of_quantity=unit_each,
            commitment=proc1_c4,
            )
        proc1_e5.save()
        proc1_e6 = EconomicEvent(
            event_type=et_produce,
            event_date=datetime.date.today() + datetime.timedelta(days=3),
            from_agent=org1,
            resource_type=rti1,
            resource=res2,
            process=proc1,
            context_agent=org1,
            quantity=Decimal(2),
            unit_of_quantity=unit_each,
            commitment=None,
            )
        proc1_e6.save()
        proc2_e1 = EconomicEvent(
            event_type=et_produce,
            event_date=datetime.date.today() - datetime.timedelta(days=5),
            from_agent=org1,
            resource_type=rti1,
            resource=res1,
            process=proc2,
            context_agent=org1,
            quantity=Decimal(20),
            unit_of_quantity=unit_each,
            commitment=None,
            )
        proc2_e1.save()
        proc3_e1 = EconomicEvent(
            event_type=et_consume,
            event_date=datetime.date.today() + datetime.timedelta(days=10),
            from_agent=org1,
            resource_type=rti3,
            resource=res3,
            process=proc3,
            context_agent=org2,
            quantity=Decimal(1),
            unit_of_quantity=unit_each,
            commitment=None,
            )
        proc3_e1.save()

    def test_basic_me_query(self):

        result = schema.execute('''
        mutation {
          createToken(username: "testUser11222", password: "123456") {
            token
          }
        }
        ''')
        call_result = result.data['createToken']
        token = call_result['token']
        query = '''
        query {
          viewer(token: "''' + token + '''") {
            myAgent {
              name
            }
          }
        }
        '''
        result = schema.execute(query)
        self.assertEqual('testUser11222', result.data['viewer']['myAgent']['name'])

    def test_change_password(self):

        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        user = User.objects.get_by_natural_key('testUser11222')
        user.set_password('654321')
        user.save()
        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    myAgent {
                      name
                    }
                  }
                }
                '''
        result = schema.execute(query)
        self.assertEqual(None, result.data['viewer'])
        self.assertTrue(len(result.errors) == 1)
        self.assertEqual('Invalid password', str(result.errors[0]))

    def test_agents_and_relationships(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    allAgents {
                      name
                      type
                      __typename
                      members: agentRelationships(category: MEMBER) {
                        id
                        subject {
                          name
                          type
                        }
                        relationship {
                          label
                          category
                        }
                        object {
                          name
                          type
                        }
                      }
                      tps: agentRelationships(category: TRADINGPARTNER) {
                        id
                        subject {
                          name
                          type
                        }
                        relationship {
                          label
                          category
                        }
                        object {
                          name
                          type
                        }
                      }
                      agentRoles {
                          label
                          category
                      }
                    }
                  }
                }
                '''
        result = schema.execute(query)
        allAgents = result.data['viewer']['allAgents']
        self.assertEqual(len(allAgents), 5)
        org1 = allAgents[1]
        self.assertEqual(org1['name'], 'org1')
        agentRelationships = org1['tps']
        supplier = agentRelationships[0]
        self.assertEqual(supplier['subject']['name'], 'supp1')
        self.assertEqual(org1['__typename'], 'Organization')
        self.assertEqual(org1['type'], 'Organization')
        person = allAgents[0]
        self.assertEqual(person['__typename'], 'Person')
        roles = person['agentRoles']
        role = roles[0]
        self.assertEqual(role['label'], 'is member of')

    def test_resources_and_resource_types(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    resourceClassificationsByProcessCategory(category: CONSUMED) {
                      name
                      category
                      processCategory
                      classificationResources {
                        trackingIdentifier
                        currentQuantity {
                          numericValue
                          unit {
                            name
                          }
                        }
                        resourceClassifiedAs {
                          name
                        }
                        image
                        category
                        note
                      }
                    }
                    resourceClassificationsByAction(action: PRODUCE) {
                      name
                      category
                      processCategory
                      classificationResources {
                        trackingIdentifier
                      }
                    }
                  }
                }
                '''
        result = schema.execute(query)
        #import pdb; pdb.set_trace()
        resourceClassificationsByProcessCategory = result.data['viewer']['resourceClassificationsByProcessCategory']
        resourceClassificationsByAction = result.data['viewer']['resourceClassificationsByAction']
        self.assertEqual(len(resourceClassificationsByProcessCategory), 1)
        rti1 = resourceClassificationsByProcessCategory[0]
        self.assertEqual(rti1['name'], 'component1')
        consumed_resources = rti1['classificationResources']
        self.assertEqual(len(consumed_resources), 2)
        conres1 = consumed_resources[0]
        self.assertEqual(conres1['trackingIdentifier'], 'a-component')
        prod_resources = resourceClassificationsByAction[1]['classificationResources']
        prodres1 = prod_resources[0]
        self.assertEqual(prodres1['trackingIdentifier'], 'a-product')

    def test_agent_other_queries(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    agent(id: 2) {
                      name
                      ownedEconomicResources(category: INVENTORY) {
                        id
                        resourceClassifiedAs {
                          name
                          category
                          processCategory
                        }
                        trackingIdentifier
                        currentQuantity {
                          numericValue
                          unit {
                            name
                          }
                        }
                        image
                        note
                      }
                      agentProcesses (isFinished: false) {
                        name
                        isFinished
                      }
                      agentPlans {
                        name
                        due
                        note
                      }
                    }
                  }
                }
                '''
        result = schema.execute(query)
        agent = result.data['viewer']['agent']
        ownedEconomicResources = result.data['viewer']['agent']['ownedEconomicResources']
        processes = result.data['viewer']['agent']['agentProcesses']
        plans = result.data['viewer']['agent']['agentPlans']
        self.assertEqual(agent['name'], 'org1')
        self.assertEqual(ownedEconomicResources[0]['resourceClassifiedAs']['name'], 'product1')
        self.assertEqual(ownedEconomicResources[0]['resourceClassifiedAs']['processCategory'], 'produced')
        self.assertEqual(len(ownedEconomicResources), 2)
        self.assertEqual(ownedEconomicResources[0]['currentQuantity']['unit']['name'], 'Each')
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]['name'], 'proc1')
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['name'], 'order1')

    def test_orders_processes_commitments_events(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        query = '''
                fragment coreEventFields on EconomicEvent {
                    action
                    start
                    affectedQuantity {
                        numericValue
                        unit {
                          name
                        }
                    }
                    affects {
                        resourceClassifiedAs {
                          name
                          category
                        }
                        trackingIdentifier
                    }
                    provider {
                        id
                        name
                    }
                    receiver {
                        id
                        name
                    }
                }
                fragment coreCommitmentFields on Commitment {
                    action
                    plannedStart
                    committedOn
                    due
                    committedQuantity {
                        numericValue
                        unit {
                          name
                        }
                    }
                    resourceClassifiedAs {
                        name
                        category
                    }
                    provider {
                        id
                        name
                    }
                    receiver {
                        id
                        name
                    }
                    involvedAgents {
                        name
                    }
                    plan {
                        name
                        plannedOn
                        due
                        note
                        scope {
                            name
                        }
                        workingAgents {
                            name
                        }
                        planProcesses {
                            name
                        }
                    }
                }
                query {
                  viewer(token: "''' + token + '''") {
                    process(id: 1) {
                        name
                        processPlan {
                          name
                        }
                        processClassifiedAs {
                            name
                            scope {
                                name
                            }
                            estimatedDuration
                        }
                        unplannedEconomicEvents(action: PRODUCE) {
                            ...coreEventFields
                        }
                        inputs {
                            ...coreEventFields
                        }
                        outputs {
                            ...coreEventFields
                        }
                        committedInputs {
                            ...coreCommitmentFields
                        }
                        committedOutputs (action: PRODUCE) {
                            ...coreCommitmentFields
                        }
                        nextProcesses {
                            name
                        }
                        previousProcesses {
                            name
                        }
                        workingAgents {
                            name
                            image
                            __typename
                        }
                    }
                  }
                }
                '''
        result = schema.execute(query)
        process = result.data['viewer']['process']
        self.assertEqual(process['name'], 'proc1')
        unplannedEconomicEvents = process['unplannedEconomicEvents']
        inputs = process['inputs']
        outputs = process['outputs']
        committedInputs = process['committedInputs']
        committedOutputs = process['committedOutputs']
        nextProcesses = process['nextProcesses']
        previousProcesses = process['previousProcesses']
        workingAgents = process['workingAgents']
        self.assertEqual(len(unplannedEconomicEvents), 1)
        self.assertEqual(len(inputs), 4)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(len(committedInputs), 3)
        self.assertEqual(len(committedOutputs), 1)
        self.assertEqual(len(nextProcesses), 1)
        self.assertEqual(len(previousProcesses), 1)
        self.assertEqual(len(workingAgents), 2)
        self.assertEqual(workingAgents[0]['__typename'], "Person")
        self.assertEqual(inputs[0]['action'], "work")
        self.assertEqual(inputs[1]['affectedQuantity']['numericValue'], 1.5)
        self.assertEqual(inputs[2]['affects']['resourceClassifiedAs']['name'], "component1")
        self.assertEqual(inputs[3]['provider']['name'], "testUser11222")
        self.assertEqual(outputs[0]['action'], "produce")
        self.assertEqual(committedInputs[0]['action'], "work")
        self.assertEqual(committedInputs[1]['committedQuantity']['numericValue'], 2.5)
        self.assertEqual(committedInputs[1]['plan']['name'], 'order1')
        self.assertEqual(committedInputs[1]['plan']['scope'][0]['name'], 'org1')
        self.assertEqual(committedInputs[2]['resourceClassifiedAs']['name'], "component1")
        self.assertEqual(committedInputs[1]['provider']['name'], "not user")
        self.assertEqual(committedOutputs[0]['action'], "produce")
        self.assertEqual(previousProcesses[0]['name'], 'proc2')
        self.assertEqual(nextProcesses[0]['name'], 'proc3')
        self.assertEqual(process['processClassifiedAs']['name'], 'pt1')

    def test_plan(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    agent(id: 2) {
                      name
                      ownedEconomicResources(category: INVENTORY) {
                        id
                        resourceClassifiedAs {
                          name
                          category
                          processCategory
                        }
                        trackingIdentifier
                        currentQuantity {
                          numericValue
                          unit {
                            name
                          }
                        }
                        image
                        note
                      }
                      agentProcesses (isFinished: false) {
                        name
                        isFinished
                      }
                      agentPlans {
                        name
                        due
                        note
                      }
                    }
                  }
                }
                '''
        result = schema.execute(query)
        agent = result.data['viewer']['agent']
        ownedEconomicResources = result.data['viewer']['agent']['ownedEconomicResources']
        processes = result.data['viewer']['agent']['agentProcesses']
        plans = result.data['viewer']['agent']['agentPlans']
        self.assertEqual(agent['name'], 'org1')
        self.assertEqual(ownedEconomicResources[0]['resourceClassifiedAs']['name'], 'product1')
        self.assertEqual(ownedEconomicResources[0]['resourceClassifiedAs']['processCategory'], 'produced')
        self.assertEqual(len(ownedEconomicResources), 2)
        self.assertEqual(ownedEconomicResources[0]['currentQuantity']['unit']['name'], 'Each')
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0]['name'], 'proc1')
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['name'], 'order1')

    def test_notification_settings(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''')
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        #result1 = schema.execute('''
        #        mutation {
        #          createNotificationSetting(token: "''' + token + '''", notificationTypeId: 1, agentId: 1, send: true) {
        #            notificationSetting {
        #              id
        #              notificationType {
        #                id
        #                display
        #                label
        #                description
        #              }
        #              send
        #              agent {
        #                name
        #              }
        #            }
        #          }
        #        }
        #        ''')
        #import pdb; pdb.set_trace()
        #self.assertEqual(result1.data['createNotificationSetting']['notificationSetting']['send'], True)

        query = '''
                query {
                  viewer(token: "''' + token + '''") {
                    agent(id: 1) {
                        name
                        agentNotificationSettings {
                            id
                            agent {
                              name
                            }
                            send
                            notificationType {
                              id
                              label
                              display
                              description
                            }
                        }
                    }
                  }
                }
                '''
        result5 = schema.execute(query)
        notifSettings = result5.data['viewer']['agent']['agentNotificationSettings']
        self.assertEqual(notifSettings[0]['id'], "1")
        self.assertEqual(notifSettings[0]['notificationType']['label'], "api_test")

    def test_create_update_delete_process(self):
        result = schema.execute('''
                mutation {
                  createToken(username: "testUser11222", password: "123456") {
                    token
                  }
                }
                ''', context_value=MockContext())
        call_result = result.data['createToken']
        token = call_result['token']
        test_agent = EconomicAgent.objects.get(name="testUser11222")

        result1 = schema.execute('''
                mutation {
                  createProcess(token: "''' + token + '''", name: "Make something cool", plannedStart: "2017-07-07", plannedFinish: "2017-07-14", scopeId: 2, planId: 1) {
                    process {
                        name
                        scope {
                            name
                        }
                        isFinished
                        plannedStart
                        plannedFinish
                        plannedDuration
                    }
                  }
                }
                ''', context_value=MockContext())
        self.assertEqual(result1.data['createProcess']['process']['name'], "Make something cool")
        self.assertEqual(result1.data['createProcess']['process']['scope']['name'], "org1")
        self.assertEqual(result1.data['createProcess']['process']['isFinished'], False)
        self.assertEqual(result1.data['createProcess']['process']['plannedStart'], "2017-07-07")
        self.assertEqual(result1.data['createProcess']['process']['plannedFinish'], "2017-07-14")
        self.assertEqual(result1.data['createProcess']['process']['plannedDuration'], "7 days, 0:00:00")

        result2 = schema.execute('''
                    mutation {
                        updateProcess(token: "''' + token + '''", id: 4, plannedFinish: "2017-07-15", isFinished: true) {
                            process {
                                name
                                scope {
                                    name
                                }
                                isFinished
                                plannedStart
                                plannedFinish
                                plannedDuration
                            }
                        }
                    }
                    ''', context_value=MockContext())

        self.assertEqual(result2.data['updateProcess']['process']['name'], "Make something cool")
        self.assertEqual(result2.data['updateProcess']['process']['scope']['name'], "org1")
        self.assertEqual(result2.data['updateProcess']['process']['isFinished'], True)
        self.assertEqual(result2.data['updateProcess']['process']['plannedStart'], "2017-07-07")
        self.assertEqual(result2.data['updateProcess']['process']['plannedDuration'], "8 days, 0:00:00")

        result3 = schema.execute('''
                    mutation {
                        deleteProcess(token: "''' + token + '''", id: 4) {
                            process {
                                name
                            }
                        }
                    }
                    ''', context_value=MockContext())

        proc = None
        try:
            proc = Process.objects.get(pk=4)
        except:
            pass
        self.assertEqual(proc, None)


######################### SAMPLE QUERIES #####################

'''
# usefaircoin

query($token: String) {
  viewer(token: $token) {
    ufc(id:1) {
      id
      title
      tagline
      description
      address
      hours
      phone
      website
      twitter
      faircoinAddress
      lat
      lng
      image
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allUfcs {
      id
      title
      tagline
      description
      address
      hours
      phone
      website
      twitter
      faircoinAddress
      lat
      lng
      image
    }
  }
}

# agent data

# user agent is authorized to create objects within that scope
query($token: String) {
  viewer(token: $token) {
    userIsAuthorizedToCreate(scopeId:23) 
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:39) {
      id
      name
      image
      note
      type
      validatedEventsCount(month:12, year:2017)
      eventsCount(month:12, year:2017)
      eventHoursCount(month:12, year:2017)
      eventPeopleCount(month:12, year:2017)
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgents {
      id
      name
      image
      primaryLocation {
        name
        address
      }
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    person(id:6) {
      id
      name
      image
      note
      type
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    myAgent {
      id
      agentSkillRelationships {
        id
        resourceClassification {
          name
        }
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allPeople {
      id
      name
      image
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    organization(id:26) {
      id
      name
      image
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allOrganizations {
      id
      name
      image
      note
      type
      __typename
      agentRecipes {
        name
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    fcOrganizations (visibility:"public", joiningStyle:"moderated") {
      id
      name
      image
      type
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    organizationClassification(id:8) {
      id
      name
      note
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allOrganizationClassifications {
      id
      name
      note
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    person(id:6) {
      name
      commitmentsMatchingSkills {
        id
        action
        resourceClassifiedAs {
          name
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentPlans(month:12, year: 2017) {
        name
        planProcesses(month:12, year: 2017) {
          name
          committedInputs(action: WORK) {
            note
            fulfilledBy(requestDistribution: true) {
              fulfilledBy {
                provider {
                  name
                }
                requestDistribution
                note
                isValidated
              }
            }
          }
        }
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:106) {
      name
      searchAgentCommitments(searchString:"Fruit") {
        id
        note
      }
      searchAgentPlans(searchString:"Fruit", isFinished: false) {
        id
        name
        note
      }
      searchAgentProcesses(searchString:"fruit") {
        id
        name
        note
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    organizationTypes {
      name
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgentRelationshipRoles {
      id
      label
      inverseLabel
      category
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agentRelationship(id:20) {
      subject {
        name
        type
      }
      relationship {
        label
        category
      }
      object {
        name
        type
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgentRelationships {
      id
      subject {
        name
        type
      }
      relationship {
        label
        category
      }
      object {
        name
        type
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships(category: MEMBER) {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

#also ...asSubject works
query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationshipsAsObject {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 6) {
      name
      memberRelationships {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 7) {
      name
      agentRelationships(category: MEMBER) {
        id
        subject {
          name
          type
          ownedEconomicResources (resourceClassificationId: 28) {
            createdDate
            resourceClassifiedAs {
              name
            }
            currentQuantity {
              numericValue
              unit {
                name
              }
            }
          }
        }
        relationship {
          label
          category
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships(roleId: 2) {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRoles {
        label
        category
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    myAgent {
      id
      name
      image
      note
      type
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:39) {
      id
      name
      image
      note
      type
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgents {
      id
      name
      image
      note
      email
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    person(id:6) {
      id
      name
      image
      note
      type
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allPeople {
      id
      name
      image
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    organization(id:26) {
      id
      name
      image
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allOrganizations {
      id
      name
      image
      note
      type
      __typename
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgentRelationshipRoles {
      id
      label
      inverseLabel
      category
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agentRelationship(id:20) {
      subject {
        name
        type
      }
      relationship {
        label
        category
      }
      object {
        name
        type
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allAgentRelationships {
      id
      subject {
        name
        type
      }
      relationship {
        label
        category
      }
      object {
        name
        type
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships(category: MEMBER) {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRelationships(roleId: 2) {
        id
        subject {
          name
          type
        }
        relationship {
          label
          category
        }
        object {
          name
          type
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      name
      agentRoles {
        label
        category
      }
    }
  }
}

# notification data

query ($token: String) {
  viewer(token: $token) {
    allNotificationTypes {
      id
      label
      display
      description
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    notificationSetting(id: 2) {
      id
      agent {
        name
      }
      send
      notificationType {
        id
        label
        display
        description
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allNotificationSettings {
      id
      agent {
        name
      }
      send
      notificationType {
        label
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 6) {
      name
      agentNotificationSettings {
        id
        agent {
          name
        }
        send
        notificationType {
          id
          label
        }
      }
    }
  }
}

# unit data

query($token: String) {
  viewer(token: $token) {
    unit(id:8) {
      id
      name
      symbol
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allUnits {
      id
      name
      symbol
    }
  }
}

# resource data

query($token: String) {
  viewer(token: $token) {
    resourceClassification(id:38) {
      id
      name
      image
      category
      note
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allResourceClassifications {
      id
      name
      unit {
        id
        name
        symbol
      }
      image
      category
      processCategory
      note
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allRecipes {
      id
      name
      image
      category
      processCategory
      note
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    resourceClassification(id: 31) {
      name
      classificationResources {
        trackingIdentifier
        currentQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    resourceClassificationsByProcessCategory(category: CONSUMED) {
      name
      category
      processCategory
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    resourceClassificationsByFacetValues(facetValues: "Material: Product,Material: Raw material,Non-material: Digital,Non-material: Formation") {
      id
      name
      classificationResources {
        id
        trackingIdentifier
        currentQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    resourceClassificationsByAction(action: PRODUCE) {
      name
      category
      processCategory
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allFacets {
      id
      name
      description
      facetValues {
        value
        description
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    economicResource(id: 157) {
      id
      resourceClassifiedAs {
        name
        category
      }
      trackingIdentifier
      currentQuantity {
        numericValue
        unit {
          name
        }
      }
      image
      category
      url
      note
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allEconomicResources {
      id
      resourceClassifiedAs {
        name
        category
      }
      trackingIdentifier
      currentQuantity {
        numericValue
        unit {
          name
        }
      }
      currentLocation {
        name
        address
      }
      image
      note
      resourceContacts {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 26) {
      name
      ownedEconomicResources {
        id
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
        currentQuantity {
          numericValue
          unit {
            name
          }
        }
        image
        note
        category
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent (id:39) {
      name
      ownedEconomicResources(page:1) {
        createdDate
        resourceClassifiedAs {
          name
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent (id:39) {
      name
      ownedEconomicResources(category: INVENTORY) {
        owners {
          name
        }
        resourceClassifiedAs {
          name
        }
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:106) {
      searchOwnedInventoryResources(searchString: "jam Jars lids") {
        id
        note
        resourceClassifiedAs {
          name
          note
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 6) {
      name
      ownedEconomicResources(category: CURRENCY) {
        id
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
        currentQuantity {
          numericValue
          unit {
            name
          }
        }
        image
        note
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 26) {
      name
      ownedEconomicResources(category: INVENTORY) {
        id
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
        currentQuantity {
          numericValue
          unit {
            name
          }
        }
        image
        note
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    economicResource(id: 20) {
      id
      resourceClassifiedAs {
        name
        category
      }
      trackingIdentifier
      currentQuantity {
        numericValue
        unit {
          name
        }
      }
      transfers {
        id
        transferDate
        provider {
          name
        }
        receiver {
          name
        }
        resourceClassifiedAs {
          name
        }
        giveResource {
          trackingIdentifier
        }
        takeResource {
          trackingIdentifier
        }
        transferQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

# kispagi
# old
query($token: String) {
  viewer(token: $token) { agent(id:""" + str(project_id) + """) { name
      agentProcesses {
        name id  plannedStart plannedDuration
        unplannedEconomicEvents { id note }
        committedInputs { note id fulfilledBy { fulfilledBy { id }}}
        inputs {
          id start
          provider {id name faircoinAddress} action note requestDistribution
          affectedQuantity{ numericValue unit {name}} note
          validations { id validationDate validatedBy { id name } }
        }
        processClassifiedAs {name} plannedDuration isFinished note
      }
    }
  }
}

#new suggested
query ($token: String) {
  viewer(token: $token) {
    agent(id: 39) {
      id
      name
      agentEconomicEvents(action: "work", year: 2017, month: 9) {
        id
        start
        requestDistribution
        affectedQuantity {
          numericValue
          unit {
            name
          }
        }
        affects {
          resourceClassifiedAs {
            name
            category
          }
          trackingIdentifier
        }
        provider {
          id
          name
          faircoinAddress
        }
        note
        inputOf {
          id
          name
          processPlan {
            id
          }
        }
        validations {
          id
          validationDate
          validatedBy {
            id
            name
          }
        }
      }
    }
  }
}

# process data

query($token: String) {
  viewer(token: $token) {
    process(id:51) {
      id
      name
      scope {
        name
      }
      processPlan {
        name
        due
      }
      plannedStart
      plannedDuration
      isFinished
      note
      userIsAuthorizedToUpdate
      userIsAuthorizedToDelete
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allProcesses {
      id
      name
      scope {
        name
      }
      processClassifiedAs {
        name
      }
      plannedStart
      plannedDuration
      isFinished
      note
      isDeletable
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    processClassification (id: 3) {
      id
      name
      scope {
        name
      }
      estimatedDuration
      note
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allProcessClassifications {
      id
      name
      scope {
        name
      }
      estimatedDuration
      note
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:26) {
      name
      agentProcesses {
        id
        name
        plannedStart
        plannedDuration
        isFinished
        note
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:39) {
      name
      agentPlans (isFinished: false) {
        id
        name
        due
        note
      }
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    agent(id:26) {
      name
      agentProcesses (isFinished: false) {
        id
        name
        plannedStart
        plannedFinish
        plannedDuration
        isFinished
        note
      }
    }
  }
}

fragment coreEventFields on EconomicEvent {
  action
  start
  affectedQuantity {
    numericValue
    unit {
      name
    }
  }
  affects {
    resourceClassifiedAs {
      name
      category
    }
    trackingIdentifier
  }
  provider {
    id
    name
  }
  receiver {
    id
    name
  }
}
fragment coreCommitmentFields on Commitment {
  action
  plannedStart
  committedOn
  due
  committedQuantity {
    numericValue
    unit {
      name
    }
  }
  resourceClassifiedAs {
    name
    category
  }
  provider {
    id
    name
  }
  receiver {
    id
    name
  }
}
query ($token: String) {
  viewer(token: $token) {
    process(id: 6) {
      name
      unplannedEconomicEvents(action: WORK) {
        ...coreEventFields
      }
      inputs (action: WORK) {
        ...coreEventFields
      }
      outputs {
        ...coreEventFields
      }
      committedInputs {
        ...coreCommitmentFields
      }
      committedOutputs (action: PRODUCE) {
        ...coreCommitmentFields
      }
      nextProcesses {
        name
      }
      previousProcesses {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    process(id: 52) {
      name
      isStarted
      isFinished
      workingAgents {
        name
        image
        __typename
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    plan(id: 50) {
      name
      scope {
        name
      }
      plannedOn
      due
      note
      planProcesses {
        name
      }
      workingAgents {
        name
        __typename
      }
      kanbanState
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allPlans {
      name
      planProcesses {
        name
      }
      isDeletable
      createdBy {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allPlans {
      id
      name
      plannedNonWorkInputs {
        action
        resourceClassifiedAs {
          name
        }
        committedQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      plannedOutputs {
        action
        resourceClassifiedAs {
          name
        }
        committedQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      nonWorkInputs {
        action
        affects {
          trackingIdentifier
          resourceClassifiedAs {
            name
          }
        }
        affectedQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      outputs {
        action
        affects {
          trackingIdentifier
          resourceClassifiedAs {
            name
          }
        }
        affectedQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

# event data

query ($token: String) {
  viewer(token: $token) {
    allEconomicEvents {
      id
      action
      start
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      url
      affects {
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      inputOf {
        id
        name
      }
      outputOf {
        id
        name
      }
      scope {
        id
        name
      }
      fulfills {
        fulfilledQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    filteredEconomicEvents (action: "give", resourceClassifiedAsId: 28, startDate: "2017-01-01", endDate: "2017-04-27", receiverId: 56, providerId: 26) {
      id
      action
      start
      affects {
        resourceClassifiedAs {
          id
          name
          category
        }
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      scope {
        id
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    agent(id: 6) {
      name
      agentEconomicEvents(latestNumberOfDays: 30, requestDistribution: true) {
        id
        action
        start
        requestDistribution
        affectedQuantity {
          numericValue
          unit {
            name
          }
        }
        affects {
          resourceClassifiedAs {
            name
            category
          }
          trackingIdentifier
        }
        provider {
          id
          name
        }
        receiver {
          id
          name
        }
        note
      }
      agentCommitments(latestNumberOfDays: 30) {
        id
        action
        plannedStart
        committedOn
        due
        committedQuantity {
          numericValue
          unit {
            name
          }
        }
        resourceClassifiedAs {
          name
          category
        }
        provider {
          id
          name
        }
        receiver {
          id
          name
        }
        note
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    economicEvent(id: 296) {
      id
      action
      start
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      affects {
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      scope {
        id
        name
      }
      userIsAuthorizedToUpdate
      userIsAuthorizedToDelete
      validations {
        id
        validationDate
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    economicEvent(id: 316) {
      id
      action
      start
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      affects {
        resourceClassifedAs {
          name
          category
        }
        trackingIdentifier
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      inputOf {
        name
      }
      outputOf {
        name
      }
      scope {
        id
        name
      }
      fulfills {
        fulfills {
          id
          committedQuantity {
            numericValue
            unit {
              name
            }
          }
        }
        fulfilledQuantity {
          numericValue
          unit {
            name
          }
        }
      }
    }
  }
}

# validation data

query($token: String) {
  viewer(token: $token) {
    validation(id:5) {
      id
      validatedBy {
        name
      }
      economicEvent {
        action
      }
      validationDate
    }
  }
}

query($token: String) {
  viewer(token: $token) {
    allValidations {
      id
      validatedBy {
        name
      }
      economicEvent {
        action
      }
      validationDate
    }
  }
}

# commitment data

query ($token: String) {
  viewer(token: $token) {
    allCommitments {
      id
      action
      plannedStart
      committedOn
      due
      committedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      resourceClassifiedAs {
        name
        category
      }
      involves {
        id
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      inputOf {
        id
        name
      }
      outputOf {
        id
        name
      }
      scope {
        id
        name
      }
      plan {
        id
        name
      }
      isPlanDeliverable
      forPlanDeliverable {
        id
        action
        outputOf {
          name
        }
      }
      isDeletable
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    commitment(id: 325) {
      id
      action
      plannedStart
      committedOn
      due
      committedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      resourceClassifiedAs {
        name
        category
      }
      involves {
        id
        resourceClassifiedAs {
          name
          category
        }
        trackingIdentifier
      }
      provider {
        id
        name
      }
      receiver {
        id
        name
      }
      inputOf {
        id
        name
      }
      outputOf {
        id
        name
      }
      scope {
        id
        name
      }
      plan {
        name
      }
      fulfilledBy (requestDistribution: false) {
        fulfilledBy {
          action
          start
          requestDistribution
          provider {
            name
          }
        }
        fulfilledQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      involvedAgents {
        name
      }
      userIsAuthorizedToUpdate
      userIsAuthorizedToDelete
      isDeletable
    }
  }
}

# exchange data

query ($token: String) {
  viewer(token: $token) {
    exchangeAgreement(id: 94) {
      plannedStart
      scope {
        name
      }
      exchangeAgreement {
        name
      }
      note
      transfers {
        name
        provider {
          name
        }
        receiver {
          name
        }
        transferQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      involvedAgents {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    transfer(id: 160) {
      name
      plannedStart
      scope {
        name
      }
      exchangeAgreement {
        name
      }
      note
      provider {
        name
      }
      receiver {
        name
      }
      transferQuantity {
        numericValue
        unit {
          name
        }
      }
      transferEconomicEvents {
        action
      }
      transferCommitments {
        action
      }
      giveCommitment {
        action
      }
      takeCommitment {
        action
      }
      involvedAgents {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    transfer(id: 76) {
      name
      plannedStart
      scope {
        name
      }
      note
      provider {
        name
      }
      receiver {
        name
      }
      resourceClassifiedAs {
        name
      }
      giveResource {
        trackingIdentifier
      }
      takeResource {
        trackingIdentifier
      }
      transferQuantity {
        numericValue
        unit {
          name
        }
      }
      transferEconomicEvents {
        action
      }
      giveEconomicEvent {
        action
      }
      takeEconomicEvent {
        action
      }
      transferCommitments {
        action
      }
      involvedAgents {
        name
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    transfer(id: 82) {
      name
      exchangeAgreement {
        plannedStart
      }
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    place(id: 4) {
      id
      name
      address
      latitude
      longitude
      note
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    allPlaces {
      id
      name
      address
      latitude
      longitude
      note
    }
  }
}

query ($token: String) {
  viewer(token: $token) {
    place(id: 5) {
      placeAgents {
        name
      }
      placeResources {
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
      }
    }
  }
}


######################### SAMPLE MUTATIONS ###########################

mutation ($token: String!) {
  createProcess(token: $token, name: "Test planned finish", plannedStart: "2017-10-01", 
    plannedFinish: "2017-10-10", scopeId: 39, note: "testing", planId: 62) {
    process {
      id
      name
      plannedStart
      plannedFinish
      processPlan {
        name
      }
    }
  }
}

mutation ($token: String!) {
  updateProcess(token: $token, id: 85, 
    plannedFinish: "2017-10-12", isFinished: true, planId: 62) {
    process {
      name
      isFinished
      plannedFinish
      plannedDuration
      processPlan {
        id
        name
      }
    }
  }
}

mutation ($token: String!) {
  deleteProcess(token: $token, id: 38) {
    process {
      name
    }
  }
}

mutation ($token: String!) {  
  createCommitment(token: $token, action: "use", plannedStart: "2018-10-01", due: "2018-10-10",
    scopeId: 39, note: "testing", committedResourceClassifiedAsId: 17, involvesId: 11, 
    committedNumericValue: "3.5", committedUnitId: 2, inputOfId: 6, planId: 52,
    providerId: 79, receiverId: 39, url: "http://www.test.coop") {
    commitment {
      id
      action
      plannedStart
      due
      url
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      resourceClassifiedAs {
        name
      }
      involves {
        trackingIdentifier
      }
      committedQuantity {
        numericValue
        unit {
          name
        }
      }
      committedOn
      isFinished
      note
    }
  }
}

mutation ($token: String!) {
  updateCommitment(token: $token, plannedStart: "2017-10-03", due: "2017-10-12",
    note: "testing more", committedNumericValue: "5.5", isFinished: true, id: 440, url: "http://www.testagain.coop") {
    commitment {
      id
      action
      plannedStart
      due
      url
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      resourceClassifiedAs {
        name
      }
      involves {
        trackingIdentifier
      }
      committedQuantity {
        numericValue
        unit {
          name
        }
      }
      committedOn
      isFinished
      note
    }
  }
}

mutation ($token: String!) {
  deleteCommitment(token: $token, id: 11) {
    commitment {
      action
    }
  }
}

mutation ($token: String!) {
  createPlan(token: $token, name: "Fudge!", due: "2017-10-15", note: "testing") {
    plan {
      id
      name
      due
      note
    }
  }
}

mutation ($token: String!) {
  createPlanFromRecipe(token: $token, name: "More Jam!", due: "2018-06-20", 
    producesResourceClassificationId: 37, note: "test") {
    plan {
      id
      name
      due
      note
      planProcesses {
        name
      }
    }
  }
}

mutation ($token: String!) {
  updatePlan(token: $token, id:53, name: "Fudge!", due: "2017-10-16", note: "testing more") {
    plan {
      id
      name
      due
      note
    }
  }
}

mutation ($token: String!) {
  deletePlan(token: $token, id: 53) {
    plan {
      name
    }
  }
}

mutation ($token: String!) {
  createEconomicEvent(token: $token, action: "use", start: "2017-10-01", scopeId: 39, 
    note: "testing", affectedResourceClassifiedAsId: 17, affectsId: 11, affectedNumericValue: "3.5", 
    affectedUnitId: 2, inputOfId: 62, providerId: 79, receiverId: 39, url: "hi.com") {
    economicEvent {
      id
      action
      start
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      affects {
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
      }
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      url
    }
  }
}

#creates a resource also
mutation ($token: String!) {
  createEconomicEvent(token: $token, action: "produce", start: "2017-10-07", scopeId: 39, 
    note: "testing new resource", affectedResourceClassifiedAsId: 37, affectedNumericValue: "30", 
    affectedUnitId: 4, outputOfId: 67, providerId: 39, receiverId: 39, createResource: true,
    resourceNote: "new one", resourceImage: "rrr.com/image", resourceTrackingIdentifier: "test-url",
    resourceUrl: "resource.com") {
    economicEvent {
      id
      action
      start
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      affects {
        id
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
        currentQuantity {
          numericValue
        }
        note
      }
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      url
    }
  }
}

mutation ($token: String!) {
  createEconomicEvent(token: $token, action: "work", start: "2017-10-01", scopeId: 39, 
    note: "testing no provider", affectedNumericValue: "5", affectedResourceClassifiedAsId: 61,
    inputOfId: 65, affectedUnitId: 2, requestDistribution: true) {
    economicEvent {
      id
      action
      start
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      affects {
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
        note
      }
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      url
      requestDistribution
    }
  }
}

#create a resource with an event
mutation ($token: String!) {
  createEconomicEvent(token: $token, action: "take", start: "2017-12-01", 
    scopeId: 39, note: "creating a resource", affectedNumericValue: "5", 
    affectedResourceClassifiedAsId: 38, affectedUnitId: 4, resourceCurrentLocationId: 7, 
    resourceTrackingIdentifier: "lynn-test-1234", createResource: true) {
    economicEvent {
      id
      action
      start
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      affects {
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
        currentLocation {
          name
        }
      }
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      url
    }
  }
}

mutation ($token: String!) {
  updateEconomicEvent(token: $token, id: 350, start: "2017-10-02", scopeId: 39, 
    note: "testing more", affectedResourceClassifiedAsId: 17, affectsId: 11, 
    affectedNumericValue: "4.5", affectedUnitId: 2, inputOfId: 62, providerId: 79, receiverId: 39) {
    economicEvent {
      id
      action
      start
      inputOf {
        name
      }
      outputOf {
        name
      }
      provider {
        name
      }
      receiver {
        name
      }
      scope {
        name
      }
      affects {
        trackingIdentifier
        resourceClassifiedAs {
          name
        }
      }
      affectedQuantity {
        numericValue
        unit {
          name
        }
      }
      note
    }
  }
}

mutation ($token: String!) {
  deleteEconomicEvent(token: $token, id: 350) {
    economicEvent {
      action
      start
    }
  }
}

mutation ($token: String!) {
  updateEconomicResource(token: $token, id: 128, trackingIdentifier: "xxxccc333", 
    note: "testing url", resourceClassifiedAsId: 37, image: "xxx.com", url: "rrr.com") {
    economicResource {
      id
      trackingIdentifier
      resourceClassifiedAs {
        name
      }
      currentQuantity {
        numericValue
        unit {
          name
        }
      }
      note
      image
      url
      currentLocation {
        id
      }
    }
  }
}

mutation ($token: String!) {
  deleteEconomicResource(token: $token, id: 34) {
    economicResource {
      trackingIdentifier
    }
  }
}

mutation ($token: String!) {
  updatePerson(token: $token, id: 74, note: "test", name: "test agent", primaryLocationId: 24,
  image: "https://testocp.freedomcoop.eu/site_media/media/photos/what_is_it.JPG") {
    person {
      id
      name
      note
      image
      primaryLocation {
        name
      }
    }
  }
}

mutation ($token: String!) {
  createOrganization(token: $token, type: "Organization", name: "test org 2") {
    organization {
      id
      name
      note
      image
      type
      primaryLocation {
        name
      }
      primaryPhone
    }
  }
}

mutation ($token: String!) {
  createPerson(token: $token, name: "anne person", note:"test", type: "Individual", primaryLocationId: 24, 
    image: "https://testocp.freedomcoop.eu/site_media/media/photos/what_is_it.JPG", primaryPhone: "333-444-5555" ) {
    person {
      id
      name
      note
      image
      type
      primaryLocation {
        name
      }
      primaryPhone
    }
  }
}

mutation ($token: String!) {
  deletePerson(token: $token, id: 39) {
    person {
      id
      name
    }
  }
}

mutation ($token: String!) {
  deleteOrganization(token: $token, id: 142) {
    organization {
      id
      name
    }
  }
}

mutation ($token: String!) {
  createNotificationSetting(token: $token, notificationTypeId: 1, agentId: 107, send: true) {
    notificationSetting {
      id
      notificationType {
        display
      }
      send
      agent {
        name
      }
    }
  }
}

mutation ($token: String!) {
  updateNotificationSetting (token: $token, id: 137, send: true) {
    notificationSetting {
      id
      notificationType {
        display
      }
      send
      agent {
        name
      }
    }
  }
}

mutation ($token: String!) {
  createValidation(token: $token, validatedById: 6, economicEventId: 393, note: "test") {
    validation {
      id
      validatedBy {
        name
      }
      economicEvent {
        action
        affectedQuantity {
          numericValue
          unit {
            name
          }
        }
      }
      validationDate
      note
    }
  }
}

mutation ($token: String!) {
  deleteValidation(token: $token, id: 4) {
    validation {
      validationDate
    }
  }
}

mutation ($token: String!) {
  createAgentRelationship(token: $token, subjectId: 122, objectId: 119, 
    relationshipId: 9, note: "test") {
    agentRelationship {
      id
      subject {
        name
      }
      relationship {
        label
      }
      object {
        name
      }
      note
    }
  }
}

mutation ($token: String!) {
  updateAgentRelationship(token: $token, id: 275, subjectId: 122, objectId: 131, 
    note: "test update") {
    agentRelationship {
      id
      subject {
        name
      }
      relationship {
        label
      }
      object {
        name
      }
      note
    }
  }
}

mutation ($token: String!) {
  createAgentResourceClassification(token: $token, agentId: 6, resourceClassificationId: 60) {
    agentResourceClassification {
      id
      agent {
        name
      }
      resourceClassification {
        name
      }
      action
    }
  }
}

mutation ($token: String!) {
  deleteAgentResourceClassification(token: $token, id: 42) {
    agentResourceClassification {
      agent {
        name
      }
      resourceClassification {
        name
      }
      action
    }
  }
}

'''
