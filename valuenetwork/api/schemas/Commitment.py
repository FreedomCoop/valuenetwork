#
# Graphene schema for exposing Commitment
#

import graphene
import datetime
from decimal import Decimal
from valuenetwork.valueaccounting.models import Commitment as CommitmentProxy, EconomicAgent, EconomicResourceType, EconomicResource, Unit, EventType, Process, Order, AgentUser
from valuenetwork.api.types.Commitment import Commitment
from valuenetwork.api.types.EconomicEvent import Action
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied, ValidationError


class Query(object): #graphene.AbstractType):

    commitment = graphene.Field(Commitment,
                                id=graphene.Int())

    all_commitments = graphene.List(Commitment)

    def resolve_commitment(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            event = CommitmentProxy.objects.get(pk=id)
            if event:
                return event
        return None

    def resolve_all_commitments(self, context, **args): #args, context, info):
        return CommitmentProxy.objects.all()


#assumption: for commitments related to a process, the plan has already been created when these mutations are called

class CreateCommitment(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        action = graphene.String(required=True)
        input_of_id = graphene.Int(required=False)
        output_of_id = graphene.Int(required=False)
        provider_id = graphene.Int(required=False)
        receiver_id = graphene.Int(required=False)
        scope_id = graphene.Int(required=False)
        committed_resource_classified_as_id = graphene.Int(required=True)
        involves_id = graphene.Int(required=False)
        committed_numeric_value = graphene.String(required=True)
        committed_unit_id = graphene.Int(required=True)
        planned_start = graphene.String(required=False)
        due = graphene.String(required=True)
        note = graphene.String(required=False)
        url = graphene.String(required=False)
        plan_id = graphene.Int(required=False)
        is_plan_deliverable = graphene.Boolean(required=False)
        #for_plan_deliverable_id = graphene.Int(required=False)

    commitment = graphene.Field(lambda: Commitment)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        action = args.get('action')
        input_of_id = args.get('input_of_id')
        output_of_id = args.get('output_of_id')
        provider_id = args.get('provider_id')
        receiver_id = args.get('receiver_id')
        scope_id = args.get('scope_id')
        committed_resource_classified_as_id = args.get('committed_resource_classified_as_id')
        involves_id = args.get('involves_id')
        committed_numeric_value = args.get('committed_numeric_value')
        committed_unit_id = args.get('committed_unit_id')
        planned_start = args.get('planned_start')
        due = args.get('due')
        note = args.get('note')
        plan_id = args.get('plan_id')
        is_plan_deliverable = args.get('is_plan_deliverable')
        #for_plan_deliverable_id = args.get('for_plan_deliverable_id')
        url = args.get('url')

        #if output_of_id or input_of_id:
        #    if not plan_id:
        #        raise ValidationError("Process related commitments must be part of a plan.")
        event_type = EventType.objects.convert_action_to_event_type(action)
        if not note:
            note = ""
        due = datetime.datetime.strptime(due, '%Y-%m-%d').date()
        if planned_start:
            planned_start = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
        if scope_id:
            scope = EconomicAgent.objects.get(pk=scope_id)
        else:
            scope = None
        if provider_id:
            provider = EconomicAgent.objects.get(pk=provider_id)
        else:
            provider = None
        if receiver_id:
            receiver = EconomicAgent.objects.get(pk=receiver_id)
        else:
            receiver = None
        if input_of_id:
            process = Process.objects.get(pk=input_of_id)
        elif output_of_id:
            process = Process.objects.get(pk=output_of_id)
        else:
            process = None
        if committed_resource_classified_as_id:
            resource_classified_as = EconomicResourceType.objects.get(pk=committed_resource_classified_as_id)
        else:
            resource_classified_as = None
        if involves_id:
            committed_resource = EconomicResource.objects.get(pk=involves_id)
        else:
            committed_resource = None
        committed_unit = Unit.objects.get(pk=committed_unit_id)
        if not url:
            url = ""
        if plan_id:
            plan = Order.objects.get(pk=plan_id)
        else:
            plan = None
        if is_plan_deliverable:
            deliverable_for = plan
        else:
            deliverable_for = None
        #if for_plan_deliverable_id:
        #    order_item = CommitmentProxy.objects.get(pk=for_plan_deliverable_id)
        #else:
        #    order_item = None

        commitment = CommitmentProxy(
            event_type = event_type,
            process = process,
            from_agent = provider,
            to_agent = receiver,
            resource_type = resource_classified_as,
            resource = committed_resource,
            quantity = Decimal(committed_numeric_value),
            unit_of_quantity = committed_unit,
            url=url,
            start_date = planned_start,
            due_date = due,
            description=note,
            context_agent=scope,
            order=deliverable_for,
            independent_demand=plan,
            order_item=None, #order_item,
            created_by=info.context.user,
        )

        user_agent = AgentUser.objects.get(user=info.context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=commitment)
        if is_authorized:
            commitment.save_api()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateCommitment(commitment=commitment)


class UpdateCommitment(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        action = graphene.String(required=False)
        input_of_id = graphene.Int(required=False)
        output_of_id = graphene.Int(required=False)
        provider_id = graphene.Int(required=False)
        receiver_id = graphene.Int(required=False)
        scope_id = graphene.Int(required=False)
        committed_resource_classified_as_id = graphene.Int(required=False)
        involves_id = graphene.Int(required=False)
        committed_numeric_value = graphene.String(required=False)
        committed_unit_id = graphene.Int(required=False)
        committed_on = graphene.String(required=False)
        planned_start = graphene.String(required=False)
        due = graphene.String(required=False)
        is_finished = graphene.Boolean(required=False)
        note = graphene.String(required=False)
        url = graphene.String(required=False)

    commitment = graphene.Field(lambda: Commitment)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        action = args.get('action')
        input_of_id = args.get('input_of_id')
        output_of_id = args.get('output_of_id')
        provider_id = args.get('provider_id')
        receiver_id = args.get('receiver_id')
        scope_id = args.get('scope_id')
        committed_resource_classified_as_id = args.get('committed_resource_classified_as_id')
        involves_id = args.get('involves_id')
        committed_numeric_value = args.get('committed_numeric_value')
        committed_unit_id = args.get('committed_unit_id')
        committed_on = args.get('committed_on')
        planned_start = args.get('planned_start')
        due = args.get('due')
        note = args.get('note')
        is_finished = args.get('is_finished')
        url = args.get('url')

        commitment = CommitmentProxy.objects.get(pk=id)
        if commitment:
            if action:
                commitment.event_type = EventType.objects.convert_action_to_event_type(action)
            if note:
                commitment.description = note
            if due:
                commitment.due_date = datetime.datetime.strptime(due, '%Y-%m-%d').date()
            if planned_start:
                commitment.start_date = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
            if scope_id:
                commitment.context_agent = EconomicAgent.objects.get(pk=scope_id)
            if provider_id == 0:
                commitment.from_agent = None
            elif provider_id:
                commitment.from_agent = EconomicAgent.objects.get(pk=provider_id)
            if receiver_id:
                commitment.to_agent = EconomicAgent.objects.get(pk=receiver_id)
            if input_of_id:
                commitment.process = Process.objects.get(pk=input_of_id)
            elif output_of_id:
                commitment.process = Process.objects.get(pk=output_of_id)
            if committed_resource_classified_as_id:
                commitment.resource_type = EconomicResourceType.objects.get(pk=committed_resource_classified_as_id)
            if involves_id:
                commitment.resource = EconomicResource.objects.get(pk=involves_id)
            if committed_numeric_value:
                commitment.quantity = Decimal(committed_numeric_value)
            if committed_unit_id:
                commitment.unit_of_quantity = Unit.objects.get(pk=committed_unit_id)
            if is_finished != None:
                commitment.finished = is_finished
            if url:
                commitment.url = url

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=commitment)
            if is_authorized:
                commitment.save_api()
            else:
                raise PermissionDenied('User not authorized to perform this action.')

        return UpdateCommitment(commitment=commitment)


class DeleteCommitment(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    commitment = graphene.Field(lambda: Commitment)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        commitment = CommitmentProxy.objects.get(pk=id)
        if commitment:
            if commitment.is_deletable():
                user_agent = AgentUser.objects.get(user=info.context.user).agent
                is_authorized = user_agent.is_authorized(object_to_mutate=commitment)
                if is_authorized:
                    commitment.delete()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
            else:
                raise PermissionDenied("Commitment has fulfilling events so cannot be deleted.")

        return DeleteCommitment(commitment=commitment)
