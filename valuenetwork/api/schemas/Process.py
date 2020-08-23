#
# Graphene schema for exposing Process model
#
# @package: OCP
# @since:   2017-06-22
#

import graphene
import datetime
from valuenetwork.valueaccounting.models import Process as ProcessProxy, EconomicAgent, AgentUser, Order
from valuenetwork.api.types.Process import Process
from six import with_metaclass
from django.contrib.auth.models import User
from .Auth import AuthedInputMeta, AuthedMutation
from django.core.exceptions import PermissionDenied


class Query(object): #graphene.AbstractType):

    # define input query params

    process = graphene.Field(Process,
                            id=graphene.Int())

    all_processes = graphene.List(Process)

    # load single item

    def resolve_process(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            process = ProcessProxy.objects.get(pk=id)
            if process:
                return process
        return None

    # load all items

    def resolve_all_processes(self, context, **args): #args, context, info):
        return ProcessProxy.objects.all()


class CreateProcess(AuthedMutation):
    class Arguments: #Input(with_metaclass(AuthedInputMeta)):
        token = graphene.String()
        name = graphene.String(required=True)
        planned_start = graphene.String(required=True)
        planned_finish = graphene.String(required=True)
        scope_id = graphene.Int(required=True)
        note = graphene.String(required=False)
        plan_id = graphene.Int(required=False)

    process = graphene.Field(lambda: Process)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        name = args.get('name')
        planned_start = args.get('planned_start')
        planned_finish = args.get('planned_finish')
        note = args.get('note')
        scope_id = args.get('scope_id')
        plan_id = args.get('plan_id')

        if not note:
            note = ""
        start_date = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(planned_finish, '%Y-%m-%d').date()
        scope = EconomicAgent.objects.get(pk=scope_id)
        plan = None
        if plan_id:
            plan = Order.objects.get(pk=plan_id)
        process = ProcessProxy(
            name=name,
            start_date=start_date,
            end_date=end_date,
            notes=note,
            context_agent=scope,
            plan=plan,
            created_by=info.context.user,
        )

        user_agent = AgentUser.objects.get(user=info.context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=process)
        if is_authorized:
            process.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        return CreateProcess(process=process)


class UpdateProcess(AuthedMutation):
    class Arguments: #(with_metaclass(AuthedInputMeta)):
        token = graphene.String()
        id = graphene.Int(required=True)
        name = graphene.String(required=False)
        planned_start = graphene.String(required=False)
        planned_finish = graphene.String(required=False)
        scope_id = graphene.Int(required=False)
        note = graphene.String(required=False)
        is_finished = graphene.Boolean(required=False)
        plan_id = graphene.Int(required=False)

    process = graphene.Field(lambda: Process)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        name = args.get('name')
        planned_start = args.get('planned_start')
        planned_finish = args.get('planned_finish')
        note = args.get('note')
        scope_id = args.get('scope_id')
        is_finished = args.get('is_finished')
        plan_id = args.get('plan_id')

        process = ProcessProxy.objects.get(pk=id)
        if process:
            if name:
                process.name = name
            if note:
                process.notes=note
            if planned_start:
                start_date = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
                process.start_date=start_date
            if planned_finish:
                end_date = datetime.datetime.strptime(planned_finish, '%Y-%m-%d').date()
                process.end_date=end_date
            if scope_id:
                scope = EconomicAgent.objects.get(pk=scope_id)
                process.context_agent=scope
            if plan_id:
                plan = Order.objects.get(pk=plan_id)
                process.plan=plan
            if is_finished != None:
                process.finished=is_finished
            process.changed_by=info.context.user

            user_agent = AgentUser.objects.get(user=info.context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=process)
            if is_authorized:
                process.save_api()
            else:
                raise PermissionDenied('User not authorized to perform this action.')


        return UpdateProcess(process=process)


class DeleteProcess(AuthedMutation):
    class Arguments: #Input(with_metaclass(AuthedInputMeta)):
        token = graphene.String()
        id = graphene.Int(required=True)

    process = graphene.Field(lambda: Process)

    #@classmethod
    def mutate(root, info, **args): #cls, root, args, context, info):
        id = args.get('id')
        process = ProcessProxy.objects.get(pk=id)
        if process:
            if process.is_deletable():
                user_agent = AgentUser.objects.get(user=info.context.user).agent
                is_authorized = user_agent.is_authorized(object_to_mutate=process)
                if is_authorized:
                    process.delete()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
                #TODO: add logic for adjusting other processes if workflow plan
            else:
                raise PermissionDenied("Process has economic events so cannot be deleted.")

        return DeleteProcess(process=process)
