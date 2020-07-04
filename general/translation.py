from modeltranslation.translator import translator, TranslationOptions
from .models import Job, Type, Artwork_Type, Space_Type, Record_Type, Unit_Type

class JobTranslationOptions(TranslationOptions):
    fields = ('name', 'verb', 'gerund', 'description')
translator.register(Job, JobTranslationOptions)


class TypeTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
translator.register(Type, TypeTranslationOptions)


class ArtworkTypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Artwork_Type, ArtworkTypeTranslationOptions)


class SpaceTypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Space_Type, SpaceTypeTranslationOptions)


class RecordTypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Record_Type, RecordTypeTranslationOptions)


class UnitTypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Unit_Type, UnitTypeTranslationOptions)



from work.models import Ocp_Unit_Type, Ocp_Artwork_Type, Ocp_Record_Type, Ocp_Skill_Type

class Ocp_Unit_TypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Ocp_Unit_Type, Ocp_Unit_TypeTranslationOptions)


class Ocp_Artwork_TypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Ocp_Artwork_Type, Ocp_Artwork_TypeTranslationOptions)


class Ocp_Record_TypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Ocp_Record_Type, Ocp_Record_TypeTranslationOptions)


class Ocp_Skill_TypeTranslationOptions(TranslationOptions):
    fields = ()
translator.register(Ocp_Skill_Type, Ocp_Skill_TypeTranslationOptions)


