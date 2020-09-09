#
# Graphene schema for exposing Plan (Order) model
#

import graphene
import datetime
from valuenetwork.valueaccounting.models import Order, EconomicAgent, AgentUser, EconomicResourceType
from valuenetwork.api.types.Plan import Plan
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied


class Query(object): #graphene.AbstractType):

    plan = graphene.Field(Plan,
                          id=graphene.Int())

    all_plans = graphene.List(Plan)

    # load single item

    def resolve_plan(self, args, *rargs):
        id = args.get('id')
        if id is not None:
            plan = Order.objects.get(pk=id)
            if plan:
                return plan
        return None

    # load all items

    def resolve_all_plans(self, args, context, info):
        return Order.objects.rand_orders()


class CreatePlan(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        name = graphene.String(required=True)
        due = graphene.String(required=True)
        note = graphene.String(required=False)

    plan = graphene.Field(lambda: Plan)

    @classmethod
    def mutate(cls, root, args, context, info):
        name = args.get('name')
        due = args.get('due')
        note = args.get('note')

        if not note:
            note = ""
        due = datetime.datetime.strptime(due, '%Y-%m-%d').date()
        plan = Order(
            order_type="rand",
            name=name,
            due_date=due,
            description=note,
            created_by=context.user,
        )

        user_agent = AgentUser.objects.get(user=context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=plan)
        if is_authorized:
            plan.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreatePlan(plan=plan)


class CreatePlanFromRecipe(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        produces_resource_classification_id = graphene.Int(required=True)
        due = graphene.String(required=True)
        name = graphene.String(required=True)
        note = graphene.String(required=False)

    plan = graphene.Field(lambda: Plan)

    @classmethod
    def mutate(cls, root, args, context, info):
        produces_resource_classification_id = args.get('produces_resource_classification_id')
        due = args.get('due')
        name = args.get('name')
        note = args.get('note')

        rc = EconomicResourceType.objects.get(pk=produces_resource_classification_id)
        scope = rc.main_producing_process_type().context_agent

        user_agent = AgentUser.objects.get(user=context.user).agent
        is_authorized = user_agent.is_authorized(context_agent_id=scope.id)
        if is_authorized:
            plan = rc.generate_mfg_work_order(order_name=name, due_date=due, created_by=context.user)
            if note:
                plan.description = note
                plan.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreatePlan(plan=plan)


class UpdatePlan(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        name = graphene.String(required=False)
        due = graphene.String(required=False)
        note = graphene.String(required=False)

    plan = graphene.Field(lambda: Plan)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        name = args.get('name')
        due = args.get('due')
        note = args.get('note')

        plan = Order.objects.get(pk=id)
        if plan:
            if name:
                plan.name = name
            if note:
                plan.description = note
            if due:
                due_date = datetime.datetime.strptime(due, '%Y-%m-%d').date()
                plan.due_date=due_date

            user_agent = AgentUser.objects.get(user=context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=plan)
            if is_authorized:
                plan.save()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdatePlan(plan=plan)


class DeletePlan(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    plan = graphene.Field(lambda: Plan)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        plan = Order.objects.get(pk=id)
        if plan:
            if plan.is_deletable():
                user_agent = AgentUser.objects.get(user=context.user).agent
                is_authorized = user_agent.is_authorized(object_to_mutate=plan)
                if is_authorized:
                    plan.delete_api()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied('Plan has related events, cannot be deleted.')

        return DeletePlan(plan=plan)
