from modeltranslation.translator import translator, TranslationOptions


from fobi.models import FormEntry, FormElementEntry

class FormEntryTranslationOptions(TranslationOptions):
    fields = ('name',) # 'title' not used, 'slug' gives problems of all sorts
translator.register(FormEntry, FormEntryTranslationOptions)


class FormElementEntryTranslationOptions(TranslationOptions):
    fields = ('plugin_data',)
translator.register(FormElementEntry, FormElementEntryTranslationOptions)
