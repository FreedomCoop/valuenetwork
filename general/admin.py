#encoding=utf-8
from django import forms
from django.contrib import admin
from django.forms import widgets

from django.utils.translation import ugettext as _

from django.forms.models import BaseInlineFormSet
from django.forms.formsets import formset_factory
#from django.forms.models import BaseModelFormSet

from mptt.admin import MPTTModelAdmin
from mptt.fields import TreeForeignKey, TreeManyToManyField
#from mptt.forms import MPTTAdminForm, TreeNodeChoiceField

#from django_mptt_admin.admin import DjangoMpttAdmin

from general.models import *  # Tree, Human, Adress, Region, Concept, Type, Being_Type

#class CustomMPTTModelAdmin(MPTTModelAdmin):
    # speficfy pixel amount for this ModelAdmin only:
    #fields = ['name']
#    mptt_level_indent = 20
#    mptt_indent_field = "name"

from django.urls import reverse

#from django.contrib.admin import InlineModelAdmin

class InlineEditLinkMixin(object):
    readonly_fields = ['edit_details']
    edit_label = "Edit"
    def edit_details(self, obj):
        if obj.id:
            opts = self.model._meta
            return "<a href='%s' target='_blank'>%s</a>" % (reverse(
                'admin:%s_%s_change' % (opts.app_label, opts.object_name.lower()),
                args=[obj.id]
            ), self.edit_label)
        else:
            return "(save to edit details)"
    edit_details.allow_tags = True


from itertools import chain
from django import forms
from django.conf import settings
from django.contrib.admin import widgets
#from django.utils.encoding import smart_text, force_unicode
#from django.utils.safestring import mark_safe
#from django.utils.html import escape, conditional_escape

class AutoNameMixin(admin.ModelAdmin):
  #class Media:
    #css = {
    #    "all": ("my_styles.css",)
    #}
  #  js = ("general.js",)

  #si añadimos datos a rendear en la template, debemos setear aqui:
  #change_form_template = 'admin/myapp/extras/openstreetmap_change_form.html'
  def change_view(self, request, object_id, form_url='', extra_context=None):
    extra_context = extra_context or {}
    #extra_context['osm_data'] = self.get_osm_info()
    return super(AutoNameMixin, self).change_view(request, object_id,
        form_url, extra_context=extra_context)


  def save_model(self, request, obj, form, change):
    instance = form.save(commit=False)
    if not hasattr(instance, 'name'):
      print(('AUTO NAME SAVE hasnot name!! '+str(obj)))
    #if instance.name is None or instance.name == '':
    instance.name = instance.__str__()
    instance.save()
    form.save_m2m()
    return instance

from general.widgets import ForeignKeyRawIdWidgetWrapperAdmin
#class Css_Mixin(ForeignKeyRawIdWidgetWrapperAdmin):
class Css_Mixin(admin.ModelAdmin):
  class Media:
    css = {
      'all': ('admin_record.css',)# 'selfemployed.css',)
    }
    js = ("general.js",)

class AutoSaveFK_mixinline(admin.StackedInline):
  class Media:
    js = ('saveOnFKchange.js',)




# ----------  H U M A N

"""
class H_addressInline(admin.StackedInline):
    model = rel_Human_Addresses
    extra = 0
    raw_id_fields = ('address',)
    readonly_fields = ('_selflink',)#'edit_details',)
    #fields = (('address', '_selflink', 'main_address', 'relation'),)
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('address', '_selflink', 'main_address', 'relation'),)
      }),
    )
    #formset = H_addressInlineSet
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        if '/general/project/' in request.path:
          rel = Relation.objects.get(clas='rel_proj_addr')
        elif '/general/person/' in request.path:
          rel = Relation.objects.get(clas='rel_pers_addr')
        else:
          rel = Relation.objects.get(clas='rel_hum_spac')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id).exclude(clas='rel_hum_regi').exclude(parent__clas='rel_hum_regi')
      return super(H_addressInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_jobInline(admin.StackedInline):
    model = rel_Human_Jobs
    extra = 0
    #fields = (('job','relation'),)
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('job','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_hum_art')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_jobInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_recordInline(admin.StackedInline):
    model = rel_Human_Records
    extra = 0
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('record','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_hum_reco')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_recordInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_regionInline(admin.StackedInline):
    model = rel_Human_Regions
    extra = 0
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('region','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_hum_regi')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_regionInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class H_materialInline(admin.StackedInline):
    model = rel_Human_Materials
    extra = 0
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('material','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_hum_mate')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_materialInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class H_nonmaterialInline(admin.StackedInline):
    model = rel_Human_Nonmaterials
    extra = 0
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('nonmaterial','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_hum_nonm')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_nonmaterialInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class H_projectInline(admin.StackedInline):
    model = rel_Human_Projects
    fk_name = 'human'
    extra = 0
    raw_id_fields = ('project',)
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('project','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_pers_proj')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_projectInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_companyInline(admin.StackedInline):
    model = rel_Human_Companies
    fk_name = 'human'
    extra = 0
    raw_id_fields = ('company',)
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('company','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_pers_comp')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_companyInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_personInline(admin.StackedInline):
    model = rel_Human_Persons
    fk_name = 'human'
    extra = 0
    raw_id_fields = ('person',)
    fieldsets = (
      (' ', {
        'classes': ('collapse',),
        'fields': (('person','relation'),)
      }),
    )
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
      if db_field.name == 'relation':
        rel = Relation.objects.get(clas='rel_proj_pers')
        kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
      return super(H_personInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class Proj_refPersonInlineSet(BaseInlineFormSet):
  def __init__(self, *args, **kwargs):
    super(Proj_refPersonInlineSet, self).__init__(*args, **kwargs)
    #print(str(self))
    #self.classes = ('collapse',)
    self.klass = 'Proj_refPersonInline'
    rel = Relation.objects.get(clas='reference')
    if hasattr(kwargs['instance'], 'human'):
      self.queryset = rel_Human_Persons.objects.filter(relation=rel, human=kwargs['instance'].human)

class Proj_refPersonInline(admin.StackedInline):
  model = rel_Human_Persons
  fk_name = 'human'
  extra = 0
  raw_id_fields = ('person',)
  readonly_fields = ('_selflink',)
  formset = Proj_refPersonInlineSet
  fields = (('person', '_selflink',),)
  #fieldsets = (
  #  (' ', {
  #    #'classes': ('collapse',),
  #    'fields': (('person', '_selflink',),)
  #  }),
  #)
  verbose_name = _(u"Reference Person")
  verbose_name_plural = _(u"Reference Members")
  classes = ['collapse', 'collapsed']


class Proj_personInlineSet(BaseInlineFormSet):
  def __init__(self, *args, **kwargs):
    super(Proj_personInlineSet, self).__init__(*args, **kwargs)
    #self.klass = 'Proj_personInline'
    rel = Relation.objects.get(clas='reference')
    if hasattr(kwargs['instance'], 'human'):
      self.queryset = rel_Human_Persons.objects.filter(human=kwargs['instance'].human).exclude(relation=rel)

class Proj_personInline(admin.StackedInline):
  model = rel_Human_Persons
  fk_name = 'human'
  extra = 0
  raw_id_fields = ('person',)
  readonly_fields = ('_selflink',)
  formset = Proj_personInlineSet
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('person', '_selflink', 'relation'),)
    }),
  )
  verbose_name = _(u"related Person")
  verbose_name_plural = _(u"other related persons")
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_proj_pers')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id).exclude(clas='reference')
    return super(Proj_personInline, self).formfield_for_foreignkey(db_field, request, **kwargs)
"""

"""
class H_accountCesInline(admin.StackedInline):
  model = AccountCes
  extra = 0
  fk_name = 'accCes_human'
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (#('accountCes', 'relation')
        ('entity', 'unit'), ('code', 'number'),# 'name'),# 'human'),
      )
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='social_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    if db_field.name == 'entity':
      typs = Project_Type.objects.filter(clas='ces')
      kwargs['queryset'] = Project.objects.filter(project_type__in=typs)
    return super(H_accountCesInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_accountBankInline(admin.StackedInline):
  model = AccountBank
  extra = 0
  fk_name = 'accBnk_human'
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (
        ('company', 'unit'), ('code', 'number'),
      )
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='fiat_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    return super(H_accountBankInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_accountCryptoInline(admin.StackedInline):
  model = AccountCrypto
  extra = 0
  fk_name = 'accCrypt_human'
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (
        ('unit', 'number'),
      )
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='crypto_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    return super(H_accountCryptoInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class H_assetInline(admin.StackedInline):
  #model = rel_Human_Material
  model = Asset
  extra = 0
  fk_name = 'asset_human'
  readonly_fields = ('_addresses_list', '_jobs_list', '_selflink',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (
        ('name', 'material_type'),
        ('description',),
        ('reciprocity',),
        ('_selflink', '_addresses_list', '_jobs_list',),
      )
    }),
  )
  #inlines = [  # TODO inlines into inlines didn't appear
  #  M_addressInline,
  #]
"""



"""
class HumanAdmin(Css_Mixin):
  list_display = ['name', 'nickname', 'email']
  search_fields = ('name','nickname','email',)
  change_list_template = "admin/general/human/change_list.html"
  def save_formset(self, request, form, formset, change):
    def set_human_name(instance):
      if not instance.human:
        instance.human = request.human
      if not instance.name:
        instance.name = instance.__unicode__()
      instance.save()

    def set_accountCes_recordtype(instance):
      if not instance.record_type:
        instance.record_type = Record_Type.objects.get(clas='AccountCes')
      #recs = instance.human.records.all()
      #ac_ces = instance.human.accountsCes.all()

      #if not 'rel_tit' in globals():
      #  rel_tit = Relation.objects.get(clas='holder')
      #new_rel, created = rel_Human_Records.objects.get_or_create(human=instance.human, record=instance, relation=rel_tit)
      #print('NEW_REL: '+str(new_rel)+' CREATED: '+str(created))


      #if not instance.
      instance.save()
    def set_accountBank_recordtype(instance):
      if not instance.record_type:
        instance.record_type = Record_Type.objects.get(clas='AccountBank')
      instance.save()
    def set_accountCrypto_recordtype(instance):
      if not instance.record_type:
        instance.record_type = Record_Type.objects.get(clas='AccountCrypto')
      instance.save()

    def set_proj_refPerson_relation(instance):
      if not instance.relation:
        instance.relation = Relation.objects.get(clas='reference')
      instance.save()
    def set_nothing(instance):
      instance.save()

    '''if formset.model == AccountCes or formset.model == AccountBank or formset.model == AccountCrypto:
      instances = formset.save(commit=False)

      if formset.model == AccountCes:
        map(set_accountCes_recordtype, instances)
      if formset.model == AccountBank:
        map(set_accountBank_recordtype, instances)
      if formset.model == AccountCrypto:
        map(set_accountCrypto_recordtype, instances)

      formset.save_m2m()
      return instances
    '''
    if formset.model == rel_Human_Persons:
      instances = formset.save(commit=False)
      if not formset.model == rel_Human_Persons:
        map(set_human_name, instances)

      if hasattr(formset, 'klass') and formset.klass == 'Proj_refPersonInline':
          map(set_proj_refPerson_relation, instances)
      else:
          map(set_nothing, instances)

      formset.save_m2m()
      return instances

    else:
      return formset.save()



class Public_ProjectAdmin(MPTTModelAdmin, HumanAdmin):
  model = Project
  readonly_fields = ('_ref_persons', '_ic_membership', '_fees_to_pay',)
  change_list_template = None
  list_display = ['name', 'nickname', 'project_type', 'email'] #, '_is_collective']
  list_filter = ('project_type', )
  search_fields = ('name', 'nickname', 'project_type', 'email')

  fieldsets = (
    (None, {
      'fields':(('name', 'nickname', 'project_type'),
                ('website', 'ecommerce', 'socialweb'),
                ('email', 'email2', 'telephone_cell'),
                ('birth_date', 'parent', 'telephone_land'))
    }),
    (_(u"Description"), {
      #'classes': ('collapse',),
      'fields': (('description',),
                ('_ic_membership', '_fees_to_pay',),)
    }),
  )
  inlines = [
    Proj_refPersonInline,
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    Proj_personInline,
    #H_personInline,
    H_projectInline,
    #H_companyInline,

    #H_regionInline,
    #H_materialInline,
    #H_nonmaterialInline,
    #H_recordInline,
    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]

class ProjectAdmin(Public_ProjectAdmin): # admin.ModelAdmin):

  list_display = ['name', 'nickname', 'project_type', 'email', '_is_collective']#, 'ref_persons']
  list_filter = ('project_type', )
  search_fields = ('name', 'nickname', 'project_type', 'email')

  inlines = [
    Proj_refPersonInline,
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    Proj_personInline,
    H_personInline,
    H_projectInline,
    H_companyInline,

    H_regionInline,
    H_materialInline,
    H_nonmaterialInline,
    H_recordInline,
    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]




class Public_PersonAdmin(HumanAdmin):
  list_display = ['name', 'surnames', 'nickname', 'email']
  readonly_fields = ('_ic_membership', '_fees_to_pay',)
  change_list_template = None
  fieldsets = (
    (None, {
      'fields':(('name', 'surnames', 'id_card'),
                ('nickname', 'nickname2', 'birth_date'),
                ('email', 'email2'),
                ('website', 'telephone_cell', 'telephone_land'))
    }),
    (_(u"Description"), {
      #'classes': ('collapse',),
      'fields': (('description',),
                 ('_ic_membership', '_fees_to_pay',),)
    }),
  )
  #filter_horizontal = ('arts',)# 'projects',) # 'addresses',)
  inlines = [
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    #H_personInline,
    H_projectInline,
    #H_companyInline,

    #H_regionInline,
    #H_materialInline,
    #H_nonmaterialInline,
    #H_recordInline,

    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]

class PersonAdmin(Public_PersonAdmin):

  #list_display = ['name', 'surnames', 'nickname', 'email']
  search_fields = ('name', 'surnames', 'nickname', 'email')

  inlines = [
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    H_personInline,
    H_projectInline,
    H_companyInline,

    H_regionInline,
    H_materialInline,
    H_nonmaterialInline,
    H_recordInline,

    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]




class Public_CompanyAdmin(HumanAdmin):
  change_list_template = None
  fieldsets = (
    (None, {
      'fields':(('name', 'nickname', 'company_type'),
                ('legal_name', 'vat_number'),
                ('email', 'telephone_cell', 'telephone_land', 'website'))
    }),
    (_(u"start/end Dates"), {
      'classes': ('collapse',),
      'fields': (('birth_date', 'death_date'),)
    })
  )
  #filter_horizontal = ('ref_members',) # 'jobs',) # 'addresses')
  inlines = [
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    H_personInline,
    #H_projectInline,
    #H_companyInline,

    #H_materialInline,
    #H_nonmaterialInline,
    #H_regionInline,
    #H_recordInline,

    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]

class CompanyAdmin(Public_CompanyAdmin): # admin.ModelAdmin):
  #class Media:
  #  js = ('mselect-to-mcheckbox.js', 'jquery-ui-1.10.2.custom.js',)
  #  css = {
  #    'all': ('css/mselect-to-mcheckbox.css',)
  #  }

  list_display = ['name', 'nickname', 'email', 'company_type']
  list_filter = ('company_type',)
  search_fields = ('name', 'nickname', 'email', 'company_type')


  inlines = [
    H_addressInline,
    H_jobInline,
    #H_assetInline,

    H_personInline,
    H_projectInline,
    H_companyInline,

    H_materialInline,
    H_nonmaterialInline,
    H_regionInline,
    H_recordInline,

    #H_accountCesInline,
    #H_accountBankInline,
    #H_accountCryptoInline,
  ]
"""


#---------  S P A C E

class Public_AddressAdmin(admin.ModelAdmin):
  class Media:
    js = ("general.js",)

  readonly_fields = ('_main_addr_of', '_jobs_list',)
  list_display = ['name', 'address_type', 'p_address', 'town', 'postalcode', 'region', '_main_addr_of',]
  list_filter = ('address_type', 'region',)
  search_fields = ('name', 'p_address', 'town', 'postalcode', 'region')
  raw_id_fields = ('jobs',)
  fieldsets = (
    (None, {
      'fields': (
        ('name', 'p_address',),
        ('town', 'postalcode'),
        ('region', '_main_addr_of'),
        ('address_type', 'ic_larder'),
        ('description',),# 'longitude', 'latitude'),
        ('size', 'size_unit',),
        ('jobs', '_jobs_list',)
      )
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'size_unit':
      typ = Unit_Type.objects.get(clas='area')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    if db_field.name == 'region':
      typ = Region_Type.objects.get(clas='region') # filtrando solo Comarcas
      kwargs['queryset'] = Region.objects.filter(region_type=typ)
    return super(Public_AddressAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class AddressAdmin(Public_AddressAdmin):

  fieldsets = (
    (None, {
      'fields': (
        ('name', 'p_address',),
        ('town', 'postalcode'),
        ('region', '_main_addr_of'),
        ('address_type', 'ic_larder'),
        ('description', 'longitude', 'latitude'),
        ('size', 'size_unit',),
        ('jobs', '_jobs_list',)
      )
    }),
  )



#---------  A R T S

class RelationAdmin(MPTTModelAdmin):
  model = Relation
  list_display = ['name', 'verb', 'clas']


class J_jobInline(admin.StackedInline):
  model = rel_Job_Jobs
  extra = 0
  fk_name = 'job1'
  raw_id_fields = ('job2',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('job2', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_job_jobs')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(J_jobInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class JobAdmin(MPTTModelAdmin):
  model = Job
  list_display = ['name', 'verb', 'clas']
  inlines = [
    J_jobInline,
  ]



# ---------- A R T W O R K S

class UnitAdmin(admin.ModelAdmin):
  model = Unit
  list_display = ['name', 'code', 'unit_type', 'ocp_unit']
  list_filter = ('unit_type',)




# - - - - - - - - - R E C O R D S

class RecordAdmin(admin.ModelAdmin):
  model = Record
  list_display = ['name', 'record_type',]
  list_filter = ('record_type',)

"""
class AccountCesAdmin(AutoNameMixin):
  model = AccountCes
  list_display = ['name', 'human', 'entity', 'code', 'number', 'unit']
  fieldsets = (
    (' ', {
      'fields':
        ('human', 'record_type', 'entity', 'unit', 'code', 'number', 'name'),

    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='social_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    if db_field.name == 'entity':
      typs = Project_Type.objects.filter(clas='ces')
      kwargs['queryset'] = Project.objects.filter(project_type__in=typs)
    return super(AccountCesAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class AccountBankAdmin(AutoNameMixin):
  model = AccountBank
  list_display = ['name', 'human', 'company', 'code', 'number', 'unit']
  fieldsets = (
    (' ', {
      'fields':
        ('human', 'record_type', 'company', 'unit', 'code', 'number', 'name'),

    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='fiat_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    return super(AccountBankAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class AccountCryptoAdmin(AutoNameMixin):
  model = AccountCrypto
  list_display = ['name', 'human', 'number', 'unit']
  fieldsets = (
    (' ', {
      'fields': #('accountCes', 'relation')
        ('human', 'record_type', 'unit', 'number', 'name'),

    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'unit':
      typ = Unit_Type.objects.get(clas='crypto_currency')
      kwargs['queryset'] = Unit.objects.filter(unit_type=typ)
    return super(AccountCryptoAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
"""

class UnitRatioAdmin(AutoNameMixin):
  model = UnitRatio
  #readonly_fields = ('name',)

  search_fields = ('name', 'record_type',)
  list_display = ['name', 'in_unit', 'rate', 'out_unit', 'record_type',]
  list_filter = ('record_type',)

  fieldsets = (
    (None, {
      'fields': (
        ('in_unit', 'rate', 'out_unit'),
        ('name', 'record_type',),
        ('description',),
      )
    }),
  )



# - - - - - - - - - N O N - M A T E R I A L

"""
class N_nonmaterialInline(admin.StackedInline):
  model = rel_Nonmaterial_Nonmaterials
  extra = 0
  fk_name = 'nonmaterial'
  raw_id_fields = ('nonmaterial2',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('nonmaterial2', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_non_nonm')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(N_nonmaterialInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class N_recordInline(admin.StackedInline):
  model = rel_Nonmaterial_Records
  extra = 0
  fk_name = 'nonmaterial'
  raw_id_fields = ('record',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('record', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_non_reco')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(N_recordInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class N_addressInline(admin.StackedInline):
  model = rel_Nonmaterial_Addresses
  extra = 0
  fk_name = 'nonmaterial'
  raw_id_fields = ('address',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('address', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_non_addr')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(N_addressInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class N_jobInline(admin.StackedInline):
  model = rel_Nonmaterial_Jobs
  extra = 0
  fk_name = 'nonmaterial'
  raw_id_fields = ('job',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('job', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_non_jobs')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(N_jobInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class Public_NonmaterialAdmin(admin.ModelAdmin):
  model = Nonmaterial
  list_display = ['name', 'nonmaterial_type',]
  list_filter = ('nonmaterial_type',)
  fieldsets = (
    (None, {
      'fields': (
        ('name', 'nonmaterial_type'),
        ('description',))
    }),
  )

class NonmaterialAdmin(Public_NonmaterialAdmin):
  inlines = [
    N_addressInline,
    N_recordInline,
    N_nonmaterialInline,
    N_jobInline,
  ]
"""


# - - - - - - - - - M A T E R I A L
"""
class M_nonmaterialInline(admin.StackedInline):
  model = rel_Material_Nonmaterials
  extra = 0
  fk_name = 'material'
  raw_id_fields = ('nonmaterial',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('nonmaterial', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_mat_nonm')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(M_nonmaterialInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class M_recordInline(admin.StackedInline):
  model = rel_Material_Records
  extra = 0
  fk_name = 'material'
  raw_id_fields = ('record',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('record', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_mat_reco')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(M_recordInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class M_addressInline(admin.StackedInline):
  model = rel_Material_Addresses
  extra = 0
  fk_name = 'material'
  raw_id_fields = ('address',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('address', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_mat_addr')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(M_addressInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class M_jobInline(admin.StackedInline):
  model = rel_Material_Jobs
  extra = 0
  fk_name = 'material'
  raw_id_fields = ('job',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('job', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_mat_jobs')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(M_jobInline, self).formfield_for_foreignkey(db_field, request, **kwargs)

class M_materialInline(admin.StackedInline):
  model = rel_Material_Materials
  extra = 0
  fk_name = 'material'
  raw_id_fields = ('material2',)
  fieldsets = (
    (' ', {
      'classes': ('collapse',),
      'fields': (('material2', 'relation'),)
    }),
  )
  def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
    if db_field.name == 'relation':
      rel = Relation.objects.get(clas='rel_mat_mate')
      kwargs['queryset'] = Relation.objects.filter(lft__gt=rel.lft, rght__lt=rel.rght, tree_id=rel.tree_id)
    return super(M_materialInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class Public_MaterialAdmin(admin.ModelAdmin):
  model = Material
  list_display = ['name', 'material_type',]
  list_filter = ('material_type',)
  fieldsets = (
    (None, {
      'fields': (
        ('name', 'material_type'),
        ('description',))
    }),
  )
  inlines = [
    M_addressInline,
  ]

class MaterialAdmin(Public_MaterialAdmin):
  inlines = [
    M_addressInline,
    M_recordInline,
    M_nonmaterialInline,
    M_jobInline,
    M_materialInline,
  ]
"""

"""
class Public_AssetAdmin(Public_MaterialAdmin):
  model = Asset
  list_display = ['name', 'asset_human', 'material_type', 'reciprocity',]
  #readonly_fields = ('_addresses_list',)
  raw_id_fields = ('asset_human',)
  fieldsets = MaterialAdmin.fieldsets + (
    (None, {
      'fields': (
        ('asset_human',),# '_addresses_list',),
        ('reciprocity',))
    }),
  )
  inlines = [
    M_addressInline,
    M_jobInline,
  ]

class AssetAdmin(Public_MaterialAdmin):
  inlines = MaterialAdmin.inlines
"""



# -------- T Y P E S


class Type_ProjectAdmin(MPTTModelAdmin):
  model = Project_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Being_Type.objects.get(clas='Project')
      kwargs['queryset'] = Being_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_ProjectAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class Type_CompanyAdmin(MPTTModelAdmin):
  model = Company_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Being_Type.objects.get(clas='Company')
      kwargs['queryset'] = Being_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_CompanyAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class Type_NonmaterialAdmin(MPTTModelAdmin):
  model = Nonmaterial_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Artwork_Type.objects.get(clas='Nonmaterial')
      kwargs['queryset'] = Artwork_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_NonmaterialAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class Type_MaterialAdmin(MPTTModelAdmin):
  model = Material_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Artwork_Type.objects.get(clas='Material')
      kwargs['queryset'] = Artwork_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_MaterialAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class Type_UnitAdmin(MPTTModelAdmin):
  model = Unit_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Artwork_Type.objects.get(clas='Unit')
      kwargs['queryset'] = Artwork_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_UnitAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class Type_RecordAdmin(MPTTModelAdmin):
  model = Record_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Artwork_Type.objects.get(clas='Record')
      kwargs['queryset'] = Artwork_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_RecordAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class Type_AddressAdmin(MPTTModelAdmin):
  model = Address_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      typ = Space_Type.objects.get(clas='Address')
      kwargs['queryset'] = Space_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_AddressAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

class Type_RegionAdmin(MPTTModelAdmin):
  model = Region_Type
  list_display = ['name', 'clas', 'parent']
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'parent':
      print((Space_Type.objects.filter(clas='Region').first()))
      typ = Space_Type.objects.filter(clas='Region').first()
      kwargs['queryset'] = Space_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght)#, tree_id=typ.tree_id)
    return super(Type_RegionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


# Register your models here.


# ----- BEINGS

##admin.site.register(Being)
##admin.site.register(Being_Type, MPTTModelAdmin) # Comment this line after creating 'Human', then 'Person', 'Project' and 'Company' under Human, inside Being_Types.
##admin.site.register(Human, HumanAdmin) # Comment once created the subtypes

##admin.site.register(Person, PersonAdmin)
#admin.site.register(Person, Public_PersonAdmin)  # public comentable

##admin.site.register(Project, ProjectAdmin)
#admin.site.register(Project, Public_ProjectAdmin)  # public comentable
admin.site.register(Project_Type, Type_ProjectAdmin)

##admin.site.register(Company, CompanyAdmin)
#admin.site.register(Company, Public_CompanyAdmin)   # public comentable
admin.site.register(Company_Type, Type_CompanyAdmin)


# ----- ARTS

##admin.site.register(Art, MPTTModelAdmin) # Comment this line after creating 'Relation' and 'Job' inside Arts.
admin.site.register(Relation, RelationAdmin)
admin.site.register(Job, JobAdmin)


# ----- ARTWORKS

##admin.site.register(Artwork)
admin.site.register(Artwork_Type, MPTTModelAdmin) # Comment this line after creating 'Unit', 'Record', 'Material' and 'Nonmaterial' inside Artwork_Types
admin.site.register(Unit, UnitAdmin)
admin.site.register(Unit_Type, Type_UnitAdmin)

#--------- Nonmaterial
admin.site.register(Nonmaterial_Type, Type_NonmaterialAdmin)
#admin.site.register(Nonmaterial, Public_NonmaterialAdmin)    # public comentable
##admin.site.register(Nonmaterial, NonmaterialAdmin)

#--------- Material
admin.site.register(Material_Type, Type_MaterialAdmin)
#admin.site.register(Material, Public_MaterialAdmin)    # public comentable
##admin.site.register(Material, MaterialAdmin)

##admin.site.register(Asset, Public_AssetAdmin)    # public comentable
##admin.site.register(Asset, AssetAdmin)

#---------- Records
admin.site.register(Record_Type, Type_RecordAdmin)
##admin.site.register(Record, RecordAdmin) # Comment this line to avoid a common record list and use only the ones below

admin.site.register(UnitRatio, UnitRatioAdmin)
##admin.site.register(AccountCes, AccountCesAdmin)
##admin.site.register(AccountBank, AccountBankAdmin)
##admin.site.register(AccountCrypto, AccountCryptoAdmin)


# ---- SPACES

##admin.site.register(Space)
##admin.site.register(Space_Type, MPTTModelAdmin) # Comment this line after creating 'Address' and 'Region' inside Space_Types
admin.site.register(Address, Public_AddressAdmin)
##admin.site.register(Address, AddressAdmin)
admin.site.register(Address_Type, Type_AddressAdmin)

admin.site.register(Region, MPTTModelAdmin)
admin.site.register(Region_Type, Type_RegionAdmin)


# ----- CONCEPTS

##admin.site.register(Concept, MPTTModelAdmin)
admin.site.register(Type, MPTTModelAdmin) # Comment this line whenever you don't need to edit the main whole Types tree
