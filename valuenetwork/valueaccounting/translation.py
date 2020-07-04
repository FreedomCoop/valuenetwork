from modeltranslation.translator import translator, TranslationOptions
from .models import EconomicAgent, AgentResourceRoleType, AgentAssociationType, EconomicResourceType, Unit

class EconomicAgentTranslationOptions(TranslationOptions):
    fields = ('name', 'nick', 'url', 'description', 'address', 'email', 'phone_primary', 'photo_url')
translator.register(EconomicAgent, EconomicAgentTranslationOptions)


class AgentResourceRoleTypeTranslationOptions(TranslationOptions):
    fields = ('name',)
translator.register(AgentResourceRoleType, AgentResourceRoleTypeTranslationOptions)


class AgentAssociationTypeTranslationOptions(TranslationOptions):
    fields = ('name', 'plural_name', 'label', 'inverse_label')
translator.register(AgentAssociationType, AgentAssociationTypeTranslationOptions)


class EconomicResourceTypeTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(EconomicResourceType, EconomicResourceTypeTranslationOptions)



class UnitTranslationOptions(TranslationOptions):
    fields = ('name',)
translator.register(Unit, UnitTranslationOptions)
