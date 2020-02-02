#
# Graphene master schema for Valuenetwork datatypes
#

import graphene
import jwt
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from graphene_django.debug import DjangoDebug
from django.conf import settings

import valuenetwork.api.schemas.UseFairCoin
import valuenetwork.api.schemas.Auth
import valuenetwork.api.schemas.Agent
import valuenetwork.api.schemas.AgentRelationship
import valuenetwork.api.schemas.AgentRelationshipRole
import valuenetwork.api.schemas.AgentResourceClassification
import valuenetwork.api.schemas.Organization
import valuenetwork.api.schemas.OrganizationClassification
import valuenetwork.api.schemas.Person
import valuenetwork.api.schemas.EconomicResource
import valuenetwork.api.schemas.Process
import valuenetwork.api.schemas.Exchange
import valuenetwork.api.schemas.Transfer
import valuenetwork.api.schemas.EconomicEvent
import valuenetwork.api.schemas.QuantityValue
import valuenetwork.api.schemas.Unit
import valuenetwork.api.schemas.ResourceClassification
import valuenetwork.api.schemas.ProcessClassification
import valuenetwork.api.schemas.Commitment
import valuenetwork.api.schemas.Plan
import valuenetwork.api.schemas.Place
import valuenetwork.api.schemas.Validation
import valuenetwork.api.schemas.NotificationSetting
from valuenetwork.api.schemas.helpers import hash_password


class ViewerQuery(
    valuenetwork.api.schemas.UseFairCoin.Query,
    valuenetwork.api.schemas.Agent.Query,
    valuenetwork.api.schemas.AgentRelationship.Query,
    valuenetwork.api.schemas.AgentRelationshipRole.Query,
    valuenetwork.api.schemas.AgentResourceClassification.Query,
    valuenetwork.api.schemas.Organization.Query,
    valuenetwork.api.schemas.OrganizationClassification.Query,
    valuenetwork.api.schemas.Person.Query,
    valuenetwork.api.schemas.EconomicResource.Query,
    valuenetwork.api.schemas.Process.Query,
    valuenetwork.api.schemas.Exchange.Query,
    valuenetwork.api.schemas.Transfer.Query,
    valuenetwork.api.schemas.EconomicEvent.Query,
    valuenetwork.api.schemas.QuantityValue.Query,
    valuenetwork.api.schemas.Unit.Query,
    valuenetwork.api.schemas.ResourceClassification.Query,
    valuenetwork.api.schemas.ProcessClassification.Query,
    valuenetwork.api.schemas.Commitment.Query,
    valuenetwork.api.schemas.Plan.Query,
    valuenetwork.api.schemas.Place.Query,
    valuenetwork.api.schemas.Validation.Query,
    valuenetwork.api.schemas.NotificationSetting.Query,
    graphene.ObjectType
):
    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop('token', None)
        self.user = kwargs.pop('user', None)
        super(ViewerQuery, self).__init__(*args, **kwargs)


class Query(graphene.ObjectType):
    viewer = graphene.Field(ViewerQuery, token=graphene.String())
    debug = graphene.Field(DjangoDebug, name='__debug')

    def resolve_viewer(self, args, context, info):
        token_str = args.get('token')
        token = jwt.decode(token_str, settings.SECRET_KEY)
        user = User.objects.get_by_natural_key(token['username'])
        if token is not None and user is not None:
            if token['password'] != hash_password(user):
                raise PermissionDenied("Invalid password")
            return ViewerQuery(token=token, user=user)
        raise PermissionDenied('Cannot access this resource')


class Mutation(graphene.ObjectType):
    create_token = valuenetwork.api.schemas.Auth.CreateToken.Field()
    create_person = valuenetwork.api.schemas.Agent.CreatePerson.Field()
    create_organization = valuenetwork.api.schemas.Agent.CreateOrganization.Field()
    update_person = valuenetwork.api.schemas.Agent.UpdatePerson.Field()
    update_organization = valuenetwork.api.schemas.Agent.UpdateOrganization.Field()
    delete_person = valuenetwork.api.schemas.Agent.DeletePerson.Field()
    delete_organization = valuenetwork.api.schemas.Agent.DeleteOrganization.Field()
    create_process = valuenetwork.api.schemas.Process.CreateProcess.Field()
    update_process = valuenetwork.api.schemas.Process.UpdateProcess.Field()
    delete_process = valuenetwork.api.schemas.Process.DeleteProcess.Field()
    create_commitment = valuenetwork.api.schemas.Commitment.CreateCommitment.Field()
    update_commitment = valuenetwork.api.schemas.Commitment.UpdateCommitment.Field()
    delete_commitment = valuenetwork.api.schemas.Commitment.DeleteCommitment.Field()
    create_economic_event = valuenetwork.api.schemas.EconomicEvent.CreateEconomicEvent.Field()
    update_economic_event = valuenetwork.api.schemas.EconomicEvent.UpdateEconomicEvent.Field()
    delete_economic_event = valuenetwork.api.schemas.EconomicEvent.DeleteEconomicEvent.Field()
    create_plan = valuenetwork.api.schemas.Plan.CreatePlan.Field()
    create_plan_from_recipe = valuenetwork.api.schemas.Plan.CreatePlanFromRecipe.Field()
    update_plan = valuenetwork.api.schemas.Plan.UpdatePlan.Field()
    delete_plan = valuenetwork.api.schemas.Plan.DeletePlan.Field()
    update_economic_resource = valuenetwork.api.schemas.EconomicResource.UpdateEconomicResource.Field()
    delete_economic_resource = valuenetwork.api.schemas.EconomicResource.DeleteEconomicResource.Field()
    create_validation = valuenetwork.api.schemas.Validation.CreateValidation.Field()
    delete_validation = valuenetwork.api.schemas.Validation.DeleteValidation.Field()
    create_notification_setting = valuenetwork.api.schemas.NotificationSetting.CreateNotificationSetting.Field()
    update_notification_setting = valuenetwork.api.schemas.NotificationSetting.UpdateNotificationSetting.Field()
    create_agent_relationship = valuenetwork.api.schemas.AgentRelationship.CreateAgentRelationship.Field()
    update_agent_relationship = valuenetwork.api.schemas.AgentRelationship.UpdateAgentRelationship.Field()
    #delete_agent_relationship = valuenetwork.api.schemas.AgentRelationship.DeleteAgentRelationship.Field()
    create_agent_resource_classification = valuenetwork.api.schemas.AgentResourceClassification.CreateAgentResourceClassification.Field()
    delete_agent_resource_classification = valuenetwork.api.schemas.AgentResourceClassification.DeleteAgentResourceClassification.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
