#
# Graphene schema for exposing Place model
#

import graphene
from valuenetwork.valueaccounting.models import Location
from valuenetwork.api.types.Place import Place
#from six import with_metaclass
#from django.contrib.auth.models import User
#from .Auth import AuthedInputMeta, AuthedMutation
#from django.core.exceptions import PermissionDenied


class Query(object): #graphene.AbstractType):

    place = graphene.Field(Place,
                           id=graphene.Int())

    all_places = graphene.List(Place)

    def resolve_place(self, context, **args): #args, *rargs):
        id = args.get('id')
        if id is not None:
            place = Location.objects.get(pk=id)
            if place:
                return place
        return None

    def resolve_all_places(self, context, **args): #args, context, info):
        return Location.objects.all()


'''
class CreateProcess(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        name = graphene.String(required=True)
        planned_start = graphene.String(required=True)
        planned_duration = graphene.Int(required=True)
        scope_id = graphene.Int(required=True)
        note = graphene.String(required=False)

    process = graphene.Field(lambda: Process)

    @classmethod
    def mutate(cls, root, args, context, info):
        #import pdb; pdb.set_trace()
        name = args.get('name')
        planned_start = args.get('planned_start')
        planned_duration = args.get('planned_duration')
        note = args.get('note')
        scope_id = args.get('scope_id')

        if not note:
            note = ""
        start_date = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
        end_date = start_date + datetime.timedelta(days=planned_duration)
        scope = EconomicAgent.objects.get(pk=scope_id)
        process = ProcessProxy(
            name=name,
            start_date=start_date,
            end_date=end_date,
            notes=note,
            context_agent=scope,
            created_by=context.user,
        )

        user_agent = AgentUser.objects.get(user=context.user).agent
        is_authorized = user_agent.is_authorized(object_to_mutate=process)
        if is_authorized:
            process.save()
        else:
            raise PermissionDenied('User not authorized to perform this action.')

        #TODO: add logic for inserting process into workflow plan

        return CreateProcess(process=process)


class UpdateProcess(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)
        name = graphene.String(required=False)
        planned_start = graphene.String(required=False)
        planned_duration = graphene.Int(required=False)
        scope_id = graphene.Int(required=False)
        note = graphene.String(required=False)
        is_finished = graphene.Boolean(required=False)

    process = graphene.Field(lambda: Process)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        name = args.get('name')
        planned_start = args.get('planned_start')
        planned_duration = args.get('planned_duration')
        note = args.get('note')
        scope_id = args.get('scope_id')
        is_finished = args.get('is_finished')

        process = ProcessProxy.objects.get(pk=id)
        if process:
            if name:
                process.name = name
            if note:
                process.notes=note
            if planned_start:
                start_date = datetime.datetime.strptime(planned_start, '%Y-%m-%d').date()
                process.start_date=start_date
            if planned_duration:
                end_date = process.start_date + datetime.timedelta(days=planned_duration)
                process.end_date=end_date
            if scope_id:
                scope = EconomicAgent.objects.get(pk=scope_id)
                process.context_agent=scope
            if is_finished:
                process.finished=is_finished
            process.changed_by=context.user

            user_agent = AgentUser.objects.get(user=context.user).agent
            is_authorized = user_agent.is_authorized(object_to_mutate=process)
            if is_authorized:
                process.save_api()
            else:
                raise PermissionDenied('User not authorized to perform this action.')


        return UpdateProcess(process=process)


class DeleteProcess(AuthedMutation):
    class Input(with_metaclass(AuthedInputMeta)):
        id = graphene.Int(required=True)

    process = graphene.Field(lambda: Process)

    @classmethod
    def mutate(cls, root, args, context, info):
        id = args.get('id')
        process = ProcessProxy.objects.get(pk=id)
        if process:
            if process.is_deletable():
                user_agent = AgentUser.objects.get(user=context.user).agent
                is_authorized = user_agent.is_authorized(object_to_mutate=process)
                if is_authorized:
                    process.delete()
                else:
                    raise PermissionDenied('User not authorized to perform this action.')
                #TODO: add logic for adjusting other processes if workflow plan
            else:
                raise PermissionDenied("Process has economic events so cannot be deleted.")

        return DeleteProcess(process=process)
'''
