from django.apps import AppConfig
import valuenetwork.api.types as types

class ApiTypesAppConfig(AppConfig):
    name = 'valuenetwork.api.types'
    verbose_name = "ApiTypes"

    def ready(self):
        """ Source of this hack:
        https://stackoverflow.com/questions/37862725/django-1-9-how-to-import-in-init-py
        'Adding from .models import CommentMixin imports CommentMixin so that you can use it
        inside the ready() method. It does not magically add it to the comment module so that
        you can access it as comments.CommentMixin

        You could assign it to the comments module in the ready() method.'
        from .models import CommentMixin
        comments.CommentMixin = CommentsMixin
        """

        from valuenetwork.api.types.EconomicResource import EconomicResource, EconomicResourceCategory, ResourceClassification, Facet, FacetValue
        types.EconomicResource = EconomicResource
        types.EconomicResourceCategory = EconomicResourceCategory
        types.ResourceClassification = ResourceClassification
        types.Facet = Facet
        types.FacetFalue = FacetValue
        from valuenetwork.api.types.Agent import Agent
        types.Agent = Agent
        from valuenetwork.api.types.Process import Process
        types.Process = Process
        from valuenetwork.api.types.Plan import Plan
        types.Plan = Plan
        from valuenetwork.api.types.EconomicEvent import EconomicEvent
        types.EconomicEvent = EconomicEvent
        from valuenetwork.api.types.Commitment import Commitment
        types.Commitment = Commitment
        from valuenetwork.api.types.EconomicEvent import Fulfillment
        types.Fulfillment = Fulfillment
        from valuenetwork.api.types.Exchange import ExchangeAgreement
        types.ExchangeAgreement = ExchangeAgreement
        from valuenetwork.api.types.Exchange import Transfer
        types.Transfer = Transfer
        from valuenetwork.api.types.Place import Place
        types.Place = Place
        from valuenetwork.api.types.Validation import Validation
        types.Validation = Validation
        from valuenetwork.api.types.NotificationSetting import NotificationSetting
        types.NotificationSetting = NotificationSetting
        from valuenetwork.api.types.Agent import OrganizationClassification
        types.OrganizationClassification = OrganizationClassification
        from valuenetwork.api.types.AgentResourceClassification import AgentResourceClassification
        types.AgentResourceClassification = AgentResourceClassification
        from valuenetwork.api.types.UseFairCoin import UseFairCoin
        types.UseFairCoin = UseFairCoin
        super(ApiTypesAppConfig, self).ready()
