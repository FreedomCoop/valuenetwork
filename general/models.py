#encoding=utf-8
from __future__ import print_function

from django.utils.safestring import mark_safe
from django.db import models
from django.utils.six import python_2_unicode_compatible

from mptt.models import MPTTModel
from mptt.fields import TreeForeignKey, TreeManyToManyField
from datetime import date, timedelta
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import gettext_lazy as __
from decimal import Decimal

from itertools import chain

# Create your models here.

a_strG = "<a onclick='return showRelatedObjectLookupPopup(this);' href='/admin/general/"
a_strW = "<a onclick='return showRelatedObjectLookupPopup(this);' href='/admin/Welcome/"
#a_str2 = "?_popup=1&_changelist_filters=_popup=1&t=human' target='_blank' style='margin-left:-100px'>"
a_str2 = "?_popup=1&t=human' target='_blank' >"
a_str3 = "?_popup=1&t=human' target='_blank'>"

a_edit = '<b>Edit</b>'

ul_tag1 = '<ul style="margin-left:-10em;">'
ul_tag = '<ul>'

str_none = __('(none)')
str_remove = 'erase'

def erase_id_link(field, id):
	out = '<a class="erase_id_on_box" name="'+str(field)+','+str(id)+'" href="javascript:;">'+str_remove+'</a>'
	print(out)
	return out


#	 C O N C E P T S - (Concepts, Ideas...)
@python_2_unicode_compatible
class Concept(MPTTModel):	# Abstract
	name = models.CharField(unique=True, verbose_name=_(u"Name"), max_length=200, help_text=_(u"The name of the Concept"), default="")
	description = models.TextField(blank=True, verbose_name=_(u"Description"))
	parent = TreeForeignKey('self', null=True, blank=True, related_name='children')

	def __str__(self):
		return self.name

	class Meta:
		abstract = True
		verbose_name = _(u"Concept")
		verbose_name_plural = _(u"c- Concepts")


@python_2_unicode_compatible
class Type(Concept):	# Create own ID's (TREE)
	#concept = models.OneToOneField('Concept', primary_key=True, parent_link=True)
	clas = models.CharField(blank=True, verbose_name=_(u"Class"), max_length=200,
													help_text=_(u"Django model or python class associated to the Type"))
  #types = TreeManyToManyField('self', through='rel_Type_Types', verbose_name=_(u"Related Types"), blank=True)

	class Meta:
		verbose_name = _(u"c- Type")
		#verbose_name_plural = _(u"c- Types")

	def __str__(self):
		if self.clas is None or self.clas == '':
			return self.name
		else:
			return self.name+' ('+self.clas+')'

"""
class rel_Type_Types(models.Model):
	typ = TreeForeignKey('Type')
	typ2 = TreeForeignKey('Type', verbose_name=_(u"related Type"))
	relation = TreeForeignKey('Relation', related_name='ty_typ+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"T_type")
		verbose_name_plural = _(u"Types related the Type")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.typ2.__str__()
		else:
			return self.relation.gerund+' > '+self.typ2.__str__()
"""



#	 B E I N G S - (Éssers, Entitats, Projectes...)
"""
@python_2_unicode_compatible
class Being(models.Model):	# Abstract
	name = models.CharField(verbose_name=_(u"Name"), max_length=200, help_text=_(u"The name of the Entity"))
	#being_type = TreeForeignKey('Being_Type', blank=True, null=True, verbose_name=_(u"Tipus d'entitat"))
	birth_date = models.DateField(blank=True, null=True, verbose_name=_(u"Born date"), help_text=_(u"The day of starting existence"))
	death_date = models.DateField(blank=True, null=True, verbose_name=_(u"Die date"), help_text=_(u"The day of ceasing existence"))

	class Meta:
		abstract = True

	def __str__(self):
		return self.name.encode("utf-8")
"""
class Being_Type(Type):
	typ = models.OneToOneField('Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name= _(u"Type of entity")
		verbose_name_plural = _(u"e--> Types of entities")

"""
@python_2_unicode_compatible
class Human(Being):	# Create own ID's
	nickname = models.CharField(max_length=50, blank=True, verbose_name=_(u"Nickname"), help_text=_(u"The nickname most used of the human entity"))
	email = models.EmailField(max_length=100, blank=True, verbose_name=_(u"Email"), help_text=_(u"The main email address of the human entity"))
	telephone_cell = models.CharField(max_length=20, blank=True, verbose_name=_(u"Mobile phone"), help_text=_(u"The main telephone of the human entity"))
	telephone_land = models.CharField(max_length=20, blank=True, verbose_name=_(u"Land phone"))
	website = models.CharField(max_length=100, blank=True, verbose_name=_(u"Web"), help_text=_(u"The main web url of the human entity"))
	description = models.TextField(blank=True, null=True, verbose_name=_(u"Entity description"))

	jobs = TreeManyToManyField('Job', through='rel_Human_Jobs', verbose_name=_(u"Activities, Jobs, Skills"), blank=True)
	addresses = models.ManyToManyField('Address', through='rel_Human_Addresses', verbose_name=_(u"Addresses"), blank=True)
	regions = models.ManyToManyField('Region', through='rel_Human_Regions', verbose_name=_(u"Regions"), blank=True)
	records = models.ManyToManyField('Record', through='rel_Human_Records', verbose_name=_(u"Records"), blank=True)
	materials = models.ManyToManyField('Material', through='rel_Human_Materials', verbose_name=_(u"Material artworks"), blank=True)
	nonmaterials = models.ManyToManyField('Nonmaterial', through='rel_Human_Nonmaterials', verbose_name=_(u"Non-material artworks"), blank=True)
	persons = models.ManyToManyField('Person', through='rel_Human_Persons', related_name='hum_persons', verbose_name=_(u"Persons"), blank=True)
	projects = models.ManyToManyField('Project', through='rel_Human_Projects', related_name='hum_projects', verbose_name=_(u"Projects"), blank=True)
	companies = models.ManyToManyField('Company', through='rel_Human_Companies', related_name='hum_companies', verbose_name=_(u"Companies"), blank=True)

	class Meta:
		verbose_name = _(u"Human")
		verbose_name_plural = _(u"e- Humans")

	def __str__(self):
		if self.nickname is None or self.nickname == '':
			return self.name
		else:
			return self.nickname+' ('+self.name+')'

	def _my_accounts(self):
		return list(chain(self.accountsCes.all(), self.accountsCrypto.all(), self.accountsBank.all()))
	#_my_accounts.list = []
	accounts = property(_my_accounts)

	def _selflink(self):
		if self.id:
			if hasattr(self, 'person'):
				return mark_safe( a_strG + "person/" + str(self.person.id) + a_str2 + a_edit + "</a>") # % str(self.id))
			elif hasattr(self, 'project'):
				return mark_safe( a_strG + "project/" + str(self.project.id) + a_str2 + a_edit + "</a>")# % str(self.id) )
		else:
			return "Not present"
	_selflink.allow_tags = True
	_selflink.short_description = ''
	self_link = property (_selflink)
	def _ic_membership(self):
		try:
			#print self.ic_membership_set.all()
			if hasattr(self, 'ic_person_membership_set'):
				ic_ms = self.ic_person_membership_set.all()
				out = ul_tag
				for ms in ic_ms:
					out += '<li>'+a_strW + "ic_person_membership/" + str(ms.id) + a_str3 + '<b>'+ms.name +"</b></a></li>"
				return out+'</ul>'
			elif hasattr(self, 'ic_project_membership_set'):
				ic_ms = self.ic_project_membership_set.all()
				out = ul_tag
				for ms in ic_ms:
					out += '<li>'+a_strW + "ic_project_membership/" + str(ms.id) + a_str3 + '<b>'+ms.name +"</b></a></li>"
				if out == ul_tag:
					return str_none
				return out+'</ul>'
			return str_none
		except:
			return str_none
	_ic_membership.allow_tags = True
	_ic_membership.short_description = _(u"IC Membership")

	def _fees_to_pay(self):
		try:
			if self.out_fees.all().count() > 0:
				out = ul_tag
				for fe in self.out_fees.all():
					if not fe.payed:
						out += '<li>'+a_strW + "fee/" + str(fe.id) + a_str3 +'<b>'+ fe.name + "</b></a></li>"
				if out == ul_tag:
					return str_none
				return out+'</ul>'
			return str_none
		except:
			return str_none
	_fees_to_pay.allow_tags = True
	_fees_to_pay.short_description = _(u"Fees to pay")

	def __init__(self, *args, **kwargs):
		super(Human, self).__init__(*args, **kwargs)

		if not 'rel_tit' in globals():
			rel_tit = Relation.objects.get(clas='holder')

		#print 'I N I T	 H U M A N :	'+self.name


		'''if hasattr(self, 'accountsCes') and self.accountsCes.count() > 0:
			recrels = rel_Human_Records.objects.filter(human=self, record__in=self.accountsCes.all())
			if recrels.count() == 0:
				for acc in self.accountsCes.all():
					newrec, created = rel_Human_Records.objects.get_or_create(human=self, record=acc, relation=rel_tit)
					print('- new_REC acc_Ces: CREATED:' + str(created) + ' :: ' + str(newrec))

		if hasattr(self, 'accountsBank') and self.accountsBank.count() > 0:
			recrels = rel_Human_Records.objects.filter(human=self, record__in=self.accountsBank.all())
			if recrels.count() == 0:
				for acc in self.accountsBank.all():
					newrec, created = rel_Human_Records.objects.get_or_create(human=self, record=acc, relation=rel_tit)
					print('- new_REC acc_Bank: CREATED:' + str(created) + ' :: ' + str(newrec))

		if hasattr(self, 'accountsCrypto') and self.accountsCrypto.count() > 0:
			recrels = rel_Human_Records.objects.filter(human=self, record__in=self.accountsCrypto.all())
			if recrels.count() == 0:
				for acc in self.accountsCrypto.all():
					newrec, created = rel_Human_Records.objects.get_or_create(human=self, record=acc, relation=rel_tit)
					print '- new_REC acc_Crypto: CREATED:'+str(created)+' :: '+str(newrec)
    '''

@python_2_unicode_compatible
class Person(Human):
	human = models.OneToOneField('Human', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	surnames = models.CharField(max_length=200, blank=True, verbose_name=_(u"Surnames"), help_text=_(u"The surnames of the Person"))
	id_card = models.CharField(max_length=9, blank=True, verbose_name=_(u"ID/DNI/NIE"))
	email2 = models.EmailField(blank=True, verbose_name=_(u"Alternate email"))
	nickname2 = models.CharField(max_length=50, blank=True, verbose_name=_(u"Nickname in FairNetwork"))

	class Meta:
		verbose_name= _(u'Person')
		verbose_name_plural= _(u'e- Persons')

	def __str__(self):
		if self.nickname is None or self.nickname == '':
			if self.surnames is None or self.surnames == '':
				return self.name+' '+self.nickname2
			else:
				return self.name+' '+self.surnames
		else:
			#return self.nickname
			if self.surnames is None or self.surnames == '':
				return self.name+' ('+self.nickname+')'
			else:
				return self.name+' '+self.surnames+' ('+self.nickname+')'


@python_2_unicode_compatible
class Project(MPTTModel, Human):
	human = models.OneToOneField('Human', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	project_type = TreeForeignKey('Project_Type', blank=True, null=True, verbose_name=_(u"Type of project"))
	parent = TreeForeignKey('self', null=True, blank=True, related_name='subprojects', verbose_name=_(u"Parent project"))
	socialweb = models.CharField(max_length=100, blank=True, verbose_name=_(u"Social website"))
	email2 = models.EmailField(blank=True, verbose_name=_(u"Alternate email"))

	ecommerce = models.BooleanField(default=False, verbose_name=_(u"E-commerce?"))
	#images = models.ManyToManyField('Image', blank=True, null=True, verbose_name=_(u"Imatges"))

	def _is_collective(self):
		if self.persons.count() < 2 and self.projects.count() < 2:
			return False
		else:
			return True
	_is_collective.boolean = True
	_is_collective.short_description = _(u"is collective?")
	collective = property(_is_collective)

	#ref_persons = models.ManyToManyField('Person', blank=True, null=True, verbose_name=_(u"Persones de referència"))

	class Meta:
		verbose_name= _(u'Project')
		verbose_name_plural= _(u'e- Projects')

	def _get_ref_persons(self):
		return self.human_persons.filter(relation__clas='reference')

	def _ref_persons(self):
		prs = self._get_ref_persons()
		if prs.count() > 0:
			out = ul_tag
			for pr in prs:
				out += '<li>'+str(pr)+'</li>'
			return out+'</ul>'
		return str_none
	_ref_persons.allow_tags = True
	_ref_persons.short_description = _(u"Reference person?")

	def __str__(self):
		if self.nickname is None or self.nickname == '':
			if self.project_type:
				return self.name+' ('+self.project_type.name+')'
			else:
				return self.name
		else:
			return self.nickname+' ('+self.name+')'
"""

class Project_Type(Being_Type):
	projectType_being_type = models.OneToOneField('Being_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name = _(u"Type of Project")
		verbose_name_plural = _(u"e-> Types of Projects")


"""
class Company(Human):
	human = models.OneToOneField('Human', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	company_type = TreeForeignKey('Company_Type', null=True, blank=True, verbose_name=_(u"Type of company"))
	legal_name = models.CharField(max_length=200, blank=True, null=True, verbose_name=_(u"Legal name"))
	vat_number = models.CharField(max_length=20, blank=True, null=True, verbose_name=_(u"VAT/CIF"))
	class Meta:
		verbose_name = _(u"Company")
		verbose_name_plural = _(u"e- Companies")
"""
class Company_Type(Being_Type):
	companyType_being_type = models.OneToOneField('Being_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name = _(u"Type of Company")
		verbose_name_plural = _(u"e-> Types of Companies")


"""
@python_2_unicode_compatible
class rel_Human_Jobs(models.Model):
	human = models.ForeignKey('Human')
	job = TreeForeignKey('Job', verbose_name=_(u"Job"))
	relation = TreeForeignKey('Relation', related_name='hu_job+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_job")
		verbose_name_plural = _(u"Skills of the entity")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.job.__str__()
		else:
			return self.relation.gerund+' > '+self.job.__str__()


@python_2_unicode_compatible
class rel_Human_Addresses(models.Model):
	human = models.ForeignKey('Human')
	address = models.ForeignKey('Address', related_name='rel_human', verbose_name=_(u"Address"),
		 help_text=_(u"Once choosed the address, save the profile to see the changes."))
	relation = TreeForeignKey('Relation', related_name='hu_adr+', blank=True, null=True, verbose_name=_(u"relation"))
	main_address = models.BooleanField(default=False, verbose_name=_(u"Main address?"))
	class Meta:
		verbose_name = _(u"H_addr")
		verbose_name_plural = _(u"Addresses of the entity")
	def __str__(self):
		if self.relation is None or self.relation.gerund is None or self.relation.gerund == '':
			return self.address.__str__()
		else:
			return self.relation.gerund+' > '+self.address.__str__()
	def _is_main(self):
		return self.main_address
	_is_main.boolean = True
	is_main = property(_is_main)
	def _selflink(self):
		if self.address:
			return self.address._selflink()
	_selflink.allow_tags = True
	_selflink.short_description = ''


@python_2_unicode_compatible
class rel_Human_Regions(models.Model):
	human = models.ForeignKey('Human')
	region = TreeForeignKey('Region', verbose_name=_(u"Region"))
	relation = TreeForeignKey('Relation', related_name='hu_reg+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_reg")
		verbose_name_plural = _(u"Related regions")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.region.__str__()
		else:
			return self.relation.gerund+' > '+self.region.__str__()


@python_2_unicode_compatible
class rel_Human_Records(models.Model):
	human = models.ForeignKey('Human')
	record = models.ForeignKey('Record', verbose_name=_(u"Record"))
	relation = TreeForeignKey('Relation', related_name='hu_rec+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_rec")
		verbose_name_plural = _(u"Related records")
	def __str__(self):
		if not hasattr(self.relation, 'gerund') or self.relation.gerund is None or self.relation.gerund == '':
			return self.record.__str__()
		else:
			if not hasattr(self.record, 'record_type') or self.record.record_type is None or self.record.record_type == '':
				return self.relation.gerund+' > '+self.record.__str__()
			return self.record.record_type.name+': '+self.relation.gerund+' > '+self.record.__str__()
	def _selflink(self):
		return self.record._selflink()
	_selflink.allow_tags = True
	_selflink.short_description = ''


@python_2_unicode_compatible
class rel_Human_Materials(models.Model):
	human = models.ForeignKey('Human')
	material = models.ForeignKey('Material', verbose_name=_(u"Material artwork"))
	relation = TreeForeignKey('Relation', related_name='hu_mat+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_mat")
		verbose_name_plural = _(u"Material Artworks")
	def __str__(self):
		if not hasattr(self.relation, 'gerund') or self.relation.gerund is None or self.relation.gerund == '':
			return self.material.__str__()
		else:
			return self.relation.gerund+' > '+self.material.__str__()


@python_2_unicode_compatible
class rel_Human_Nonmaterials(models.Model):
	human = models.ForeignKey('Human')
	nonmaterial = models.ForeignKey('Nonmaterial', verbose_name=_(u"Non-material artwork"))
	relation = TreeForeignKey('Relation', related_name='hu_non+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_inm")
		verbose_name_plural = _(u"Non-material Artworks")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.nonmaterial.__str__()
		else:
			return self.relation.gerund+' > '+self.nonmaterial.__str__()


@python_2_unicode_compatible
class rel_Human_Persons(models.Model):
	human = models.ForeignKey('Human', related_name='human_persons')
	person = models.ForeignKey('Person', related_name='rel_humans', verbose_name=_(u"Related person"))
	relation = TreeForeignKey('Relation', related_name='hu_hum+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_per")
		verbose_name_plural = _(u"Related persons")
	def __str__(self):
		if self.relation is None or self.relation.gerund is None or self.relation.gerund == '':
			return self.person.__str__()
		else:
			return self.relation.gerund+' > '+self.person.__str__()

	def _selflink(self):
		return self.person._selflink()
	_selflink.allow_tags = True
	_selflink.short_description = ''


@python_2_unicode_compatible
class rel_Human_Projects(models.Model):
	human = models.ForeignKey('Human', related_name='human_projects')
	project = TreeForeignKey('Project', related_name='rel_humans', verbose_name=_(u"Related project"),
		 help_text=_(u"Once choosed the project, save the profile to see the changes."))
	relation = TreeForeignKey('Relation', related_name='hu_hum+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_pro")
		verbose_name_plural = _(u"Related projects")
	def __str__(self):
		if self.project.project_type is None or self.project.project_type == '':
			if self.relation.gerund is None or self.relation.gerund == '':
				return self.project.__str__()
			else:
				return self.relation.gerund+' > '+self.project.__str__()
		else:
			if not self.relation or self.relation.gerund is None or self.relation.gerund == '':
				return '('+self.project.project_type.being_type.name+') rel? > '+self.project.name
			else:
				return '('+self.project.project_type.being_type.name+') '+self.relation.gerund+' > '+self.project.name


@python_2_unicode_compatible
class rel_Human_Companies(models.Model):
	human= models.ForeignKey('Human', related_name='human_companies')
	company = models.ForeignKey('Company', verbose_name=_(u"related Company"))
	relation = TreeForeignKey('Relation', related_name='hu_hum+', blank=True, null=True, verbose_name=_(u"relation"))
	class Meta:
		verbose_name = _(u"H_emp")
		verbose_name_plural = _(u"Related companies")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.company.__str__()
		else:
			return '('+self.company.company_type.being_type.name+') '+self.relation.gerund+' > '+self.company.__str__()

"""

'''
class rel_Address_Jobs(models.Model):
	address = models.ForeignKey('Address')
	job = models.ForeignKey('Job', verbose_name=_(u"Art/Ofici vinculat"))
	relation = TreeForeignKey('Relation', related_name='ad_job+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"job")
		verbose_name_plural = _(u"Arts/Oficis vinculats")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.job.__str__()
		else:
			return self.relation.gerund+' > '+self.job.__str__()
'''



#	 A R T S - (Verbs, Relacions, Arts, Oficis, Sectors...)
@python_2_unicode_compatible
class Art(MPTTModel):	# Abstract
	name = models.CharField(unique=True, max_length=200, verbose_name=_(u"Name"), help_text=_(u"The name of the Art"))
	verb = models.CharField(max_length=200, blank=True, verbose_name=_(u"Verb"), help_text=_(u"The verb of the action, infinitive"))
	gerund = models.CharField(max_length=200, blank=True, verbose_name=_(u"Gerund"), help_text=_(u"The verb in gerund, present"))
	description = models.TextField(blank=True, verbose_name=_(u"Description"))

	parent = TreeForeignKey('self', null=True, blank=True, related_name='subarts')

	def __str__(self):
		if self.verb:
			return self.name+', '+self.verb
		else:
			return self.name

	class Meta:

		abstract = True

		verbose_name = _(u"Art")
		verbose_name_plural = _(u"a- Arts")


@python_2_unicode_compatible
class Relation(Art):	# Create own ID's (TREE)
	#art = models.OneToOneField('Art', primary_key=True, parent_link=True)
	clas = models.CharField(blank=True, verbose_name=_(u"Class"), max_length=50,
													help_text=_(u"Django model or python class associated to the Relation"))
	class Meta:
		verbose_name= _(u'Relation')
		verbose_name_plural= _(u'a- Relations')
	def __str__(self):
		if self.verb:
			if self.clas is None or self.clas == '':
				return self.verb
			else:
				return self.verb+' ('+self.clas+')'
		else:
			if self.clas is None or self.clas == '':
				return self.name
			else:
				return self.name+' ('+self.clas+')'


@python_2_unicode_compatible
class Job(Art):		# Create own ID's (TREE)
    #art = models.OneToOneField('Art', primary_key=True, parent_link=True)
    clas = models.CharField(blank=True, verbose_name=_(u"Clas"), max_length=50, help_text=_(u"Django model or python class associated to the Job"))
    jobs = models.ManyToManyField(
        'self',
        through='rel_Job_Jobs',
        through_fields=('job1', 'job2'),
        symmetrical=False,
        blank=True,
        verbose_name=_("related Skills"))

    class Meta:
        verbose_name= _(u'Skill')
        verbose_name_plural= _(u'a- Skills')
    def __str__(self):
        if self.clas is None or self.clas == '':
            return self.name#+', '+self.verb
        else:
            return self.name+' ('+self.clas+')'


@python_2_unicode_compatible
class rel_Job_Jobs(models.Model):
	job1 = models.ForeignKey('Job', on_delete=models.CASCADE, related_name="rel_jobs1")
	job2 = TreeForeignKey('Job', on_delete=models.CASCADE, related_name="rel_jobs2") #, verbose_name=_(u"related Jobs")
	relation = TreeForeignKey('Relation', related_name='jo_job+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"J_job")
		verbose_name_plural = _(u"Related jobs")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.job1.__str__()
		else:
			return '('+self.job1.name+') '+self.relation.gerund+' > '+self.job2.__str__()

#rel_tit = Relation.objects.get(clas='holder')



#	 S P A C E S - (Regions, Places, Addresses...)

@python_2_unicode_compatible
class Space(models.Model):	# Abstact
	name = models.CharField(verbose_name=_(u"Name"), max_length=100, help_text=_(u"The name of the Space"))
	#space_type = TreeForeignKey('Space_Type', blank=True, null=True, verbose_name=_(u"Tipus d'espai"))
	#m2 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

	def __str__(self):
		return self.name

	class Meta:
		abstract = True

class Space_Type(Type):
	typ = models.OneToOneField('Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)

	class Meta:
		verbose_name= _(u"Type of Space")
		verbose_name_plural= _(u"s--> Types of Spaces")


@python_2_unicode_compatible
class Address(Space):	# Create own ID's
	#space = models.OneToOneField('Space', primary_key=True, parent_link=True)
	address_type = TreeForeignKey('Address_Type', blank=True, null=True, verbose_name=_(u"Type of address"))
	p_address = models.CharField(max_length=200, verbose_name=_(u"Address"), help_text=_(u"Postal address able to receive by post"))
	town = models.CharField(max_length=150, verbose_name=_(u"Town"), help_text=_(u"Town or City"))
	postalcode = models.CharField(max_length=5, blank=True, null=True, verbose_name=_(u"Postal/Zip code"))
	region = TreeForeignKey('Region', blank=True, null=True, related_name='rel_addresses', verbose_name=_(u"Region"))

	#telephone = models.CharField(max_length=20, blank=True, verbose_name=_(u"Telefon fix"))
	ic_larder = models.BooleanField(default=False, verbose_name=_(u"Is a Larder?"))
	#main_address = models.BooleanField(default=False, verbose_name=_(u"Adreça principal?"))
	size = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, verbose_name=_(u'Size'), help_text=_(u"Number of units (accept 2 decimals)"))
	size_unit = models.ForeignKey('Unit', blank=True, null=True, verbose_name=_(u"Unit of measure"))
	longitude = models.IntegerField(blank=True, null=True, verbose_name=_(u"Longitude (geo)"))
	latitude = models.IntegerField(blank=True, null=True, verbose_name=_(u"Latitude (geo)"))

	jobs = models.ManyToManyField('Job', related_name='addresses', blank=True, verbose_name=_(u"Related Jobs"))

	description = models.TextField(blank=True, null=True, verbose_name=_(u"Description of the Address"), help_text=_(u"Exact localization, indications to arrive or comments"))

	def _main_addr_of(self):
		'''rel = rel_Human_Addresses.objects.filter(address=self, main_address=True).first() #TODO accept various and make a list
		if rel:
			return rel.human
		else:'''
		return _(u'nobody')
	_main_addr_of.allow_tags = True
	_main_addr_of.short_description = _(u"Main address of")
	main_addr_of = property(_main_addr_of)


	class Meta:
		verbose_name= _(u'Address')
		verbose_name_plural= _(u's- Addresses')
	def __str__(self):
		return self.name+' ('+self.p_address+' - '+self.town+')'

	def _jobs_list(self):
		out = ul_tag
		for jo in self.jobs.all():
			out += '<li><b>'+jo.verb+'</b> - '+erase_id_link('jobs', str(jo.id))+'</li>'
		if out == ul_tag:
			return str_none
		return out+'</ul>'
	_jobs_list.allow_tags = True
	_jobs_list.short_description = ''

	def _selflink(self):
		if self.id:
				return a_strG + "address/" + str(self.id) + a_str2 + a_edit +"</a>"# % str(self.id)
		else:
				return "Not present"
	_selflink.allow_tags = True

class Address_Type(Space_Type):
	addrTypeSpace_type = models.OneToOneField('Space_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name = _(u"Type of Address")
		verbose_name_plural = _(u"s-> Types of Addresses")



class Region(MPTTModel, Space):	# Create own ID's (TREE)
	#space = models.OneToOneField('Space', primary_key=True, parent_link=True)
	region_type = TreeForeignKey('Region_Type', blank=True, null=True, verbose_name=_(u"Type of region"))
	parent = TreeForeignKey('self', null=True, blank=True, related_name='subregions')

	description = models.TextField(blank=True, null=True, verbose_name=_(u"Description of the Region"))

	class Meta:
		verbose_name= _(u'Region')
		verbose_name_plural= _(u's- Regions')

class Region_Type(Space_Type):
	regionType_space_type = models.OneToOneField('Space_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name = _(u"Type of Region")
		verbose_name_plural = _(u"s-> Types of Regions")




#	 A R T W O R K S - (Obres, Coses, Registres, Documents...)
@python_2_unicode_compatible
class Artwork(models.Model):	# Abstract
	name = models.CharField(verbose_name=_(u"Name"), max_length=200, blank=True, null=True) #, help_text=_(u"El nom de la obra (Registre, Unitat, Cosa)"))
	#artwork_type = TreeForeignKey('Artwork_Type', blank=True, verbose_name=_(u"Tipus d'Obra"))
	description = models.TextField(blank=True, null=True, verbose_name=_(u"Description"))

	def __str__(self):
		return self.name

	class Meta:
		abstract = True

class Artwork_Type(Type):
	typ = models.OneToOneField('Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name = _(u"Type of Artwork")
		verbose_name_plural = _(u"o--> Types of Artworks")



# - - - - - N O N - M A T E R I A L
"""
@python_2_unicode_compatible
class rel_Nonmaterial_Records(models.Model):
	nonmaterial = models.ForeignKey('Nonmaterial')
	record = models.ForeignKey('Record', verbose_name=_(u"related Record"))
	relation = TreeForeignKey('Relation', related_name='no_reg+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"N_rec")
		verbose_name_plural = _(u"Related records")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.record.__str__()
		else:
			return '('+self.record.record_type.name+') '+self.relation.gerund+' > '+self.record.__str__()

@python_2_unicode_compatible
class rel_Nonmaterial_Addresses(models.Model):
	nonmaterial = models.ForeignKey('Nonmaterial')
	address = models.ForeignKey('Address', verbose_name=_(u"related Address"))
	relation = TreeForeignKey('Relation', related_name='no_adr+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"N_adr")
		verbose_name_plural = _(u"Related addresses")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.address.__str__()
		else:
			return '('+self.address.address_type.name+') '+self.relation.gerund+' > '+self.address.__str__()

@python_2_unicode_compatible
class rel_Nonmaterial_Jobs(models.Model):
	nonmaterial = models.ForeignKey('Nonmaterial')
	job = models.ForeignKey('Job', related_name='nonmaterials', verbose_name=_(u"related Arts/Jobs"))
	relation = TreeForeignKey('Relation', related_name='no_job+', blank=True, null=True, verbose_name=_(u"Relation"))
	class Meta:
		verbose_name = _(u"N_ofi")
		verbose_name_plural = _(u"Related Arts/Jobs")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.job.__str__()
		else:
			return self.relation.gerund+' > '+self.job.__str__()

@python_2_unicode_compatible
class rel_Nonmaterial_Nonmaterials(models.Model):
	nonmaterial = models.ForeignKey('Nonmaterial')
	nonmaterial2 = models.ForeignKey('Nonmaterial', related_name='subnonmaterials', verbose_name=_(u"related Non-material Artworks"))
	relation = TreeForeignKey('Relation', related_name='ma_mat+', blank=True, null=True, verbose_name=_(u"Relation"))
	class Meta:
		verbose_name = _(u"N_mat")
		verbose_name_plural = _(u"related Non-material artworks")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.nonmaterial2.__str__()
		else:
			return '('+self.nonmaterial2.material_type.name+') '+self.relation.gerund+' > '+self.nonmaterial2.__str__()


class Nonmaterial(Artwork):	# Create own ID's
	nonmaterial_type = TreeForeignKey('Nonmaterial_Type', blank=True, null=True, verbose_name=_(u"Type of non-material artwork"))

	records = models.ManyToManyField('Record', through='rel_Nonmaterial_Records', blank=True, verbose_name=_(u"related Records"))
	addresses = models.ManyToManyField('Address', through='rel_Nonmaterial_Addresses', blank=True, verbose_name=_(u"related Addresses"))
	jobs = models.ManyToManyField('Job', through='rel_Nonmaterial_Jobs', blank=True, verbose_name=_(u"related Arts/Jobs"))
	nonmaterials = models.ManyToManyField('self', through='rel_Nonmaterial_Nonmaterials', symmetrical=False, blank=True, verbose_name=_(u"related Non-material artworks"))

	class Meta:
		verbose_name = _(u"Non-material Artwork")
		verbose_name_plural = _(u"o- Non-material Artworks")
"""

class Nonmaterial_Type(Artwork_Type):
	nonmaterialType_artwork_type = models.OneToOneField('Artwork_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name= _(u"Type of Non-material artwork")
		verbose_name_plural= _(u"o-> Types of Non-material artworks")


"""
class Image(Nonmaterial):
	image_nonmaterial = models.OneToOneField('Nonmaterial', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	image_image = models.ImageField(upload_to='files/images', height_field='height', width_field='width',
													blank=True, null=True,
													verbose_name=_(u"Image (jpg/png)"))
	#footer = models.TextField(blank=True, null=True, verbose_name=_(u"Peu de foto"))
	url = models.URLField(blank=True, null=True, verbose_name=_(u"Url of the image"))
	height = models.IntegerField(blank=True, null=True, verbose_name=_(u"Height"))
	width = models.IntegerField(blank=True, null=True, verbose_name=_(u"Width"))

	class Meta:
		verbose_name = _(u"Image")
		verbose_name_plural = _(u"o- Images")
"""


# - - - - - M A T E R I A L
"""
@python_2_unicode_compatible
class rel_Material_Nonmaterials(models.Model):
	material = models.ForeignKey('Material')
	nonmaterial = models.ForeignKey('Nonmaterial', verbose_name=_(u"related Non-material"))
	relation = TreeForeignKey('Relation', related_name='ma_non+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"M_inm")
		verbose_name_plural = _(u"related Non-materials")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.nonmaterial.__str__()
		else:
			return '('+self.nonmaterial.nonmaterial_type.name+') '+self.relation.gerund+' > '+self.nonmaterial.__str__()

@python_2_unicode_compatible
class rel_Material_Records(models.Model):
	material = models.ForeignKey('Material')
	record = models.ForeignKey('Record', verbose_name=_(u"related Record"))
	relation = TreeForeignKey('Relation', related_name='ma_reg+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"M_rec")
		verbose_name_plural = _(u"related Records")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.record.__str__()
		else:
			return '('+self.record.record_type.name+') '+self.relation.gerund+' > '+self.record.__str__()

@python_2_unicode_compatible
class rel_Material_Addresses(models.Model):
	material = models.ForeignKey('Material')
	address = models.ForeignKey('Address', related_name='materials', verbose_name=_(u"related Address"))
	relation = TreeForeignKey('Relation', related_name='ma_adr+', blank=True, null=True)
	class Meta:
		verbose_name = _(u"M_adr")
		verbose_name_plural = _(u"related Addresses")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.address.__str__()
		else:
			return '('+self.address.address_type.name+') '+self.relation.gerund+' > '+self.address.__str__()

@python_2_unicode_compatible
class rel_Material_Materials(models.Model):
	material = models.ForeignKey('Material')
	material2 = models.ForeignKey('Material', related_name='submaterials', verbose_name=_(u"related Material artworks"))
	relation = TreeForeignKey('Relation', related_name='ma_mat+', blank=True, null=True, verbose_name=_(u"Relation"))
	class Meta:
		verbose_name = _(u"M_mat")
		verbose_name_plural = _(u"related Material artworks")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.material2.__str__()
		else:
			return '('+self.material2.material_type.name+') '+self.relation.gerund+' > '+self.material2.__str__()

@python_2_unicode_compatible
class rel_Material_Jobs(models.Model):
	material = models.ForeignKey('Material')
	job = models.ForeignKey('Job', related_name='materials', verbose_name=_(u"related Arts/Jobs"))
	relation = TreeForeignKey('Relation', related_name='ma_job+', blank=True, null=True, verbose_name=_(u"Relation"))
	class Meta:
		verbose_name = _(u"M_ofi")
		verbose_name_plural = _(u"related Arts/Jobs")
	def __str__(self):
		if self.relation.gerund is None or self.relation.gerund == '':
			return self.job.__str__()
		else:
			return self.relation.gerund+' > '+self.job.__str__()


class Material(Artwork): # Create own ID's
	material_type = TreeForeignKey('Material_Type', blank=True, null=True, verbose_name=_(u"Type of physical artwork"))

	nonmaterials = models.ManyToManyField('Nonmaterial', through='rel_Material_Nonmaterials', blank=True, verbose_name=_(u"related Non-materials"))
	records = models.ManyToManyField('Record', through='rel_Material_Records', blank=True, verbose_name=_(u"related Records"))
	addresses = models.ManyToManyField('Address', through='rel_Material_Addresses', blank=True, verbose_name=_(u"related Addresses"))
	materials = models.ManyToManyField('self', through='rel_Material_Materials', symmetrical=False, blank=True, verbose_name=_(u"related Material artworks"))
	jobs = models.ManyToManyField('Job', through='rel_Material_Jobs', blank=True, verbose_name=_(u"related Arts/Jobs"))

	class Meta:
		verbose_name = _(u"Material Artwork")
		verbose_name_plural = _(u"o- Material Artworks")

	def _addresses_list(self):
		out = ul_tag
		print(self.addresses.all())
		if self.addresses.all().count() > 0:
			for add in self.addresses.all():
				rel = add.materials.filter(material=self).first().relation
				out += '<li>'+rel.gerund+': <b>'+add.__str__()+'</b></li>'
			return out+'</ul>'
		return str_none
	_addresses_list.allow_tags = True
	_addresses_list.short_description = _(u"related Addresses?")

	def _jobs_list(self):
		out = ul_tag
		print(self.jobs.all())
		if self.jobs.all().count() > 0:
			for job in self.jobs.all():
				rel = job.materials.filter(material=self).first().relation
				out += '<li>'+rel.gerund+': <b>'+job.__str__()+'</b></li>'
			return out+'</ul>'
		return str_none
	_jobs_list.allow_tags = True
	_jobs_list.short_description = _(u"related Arts/Jobs?")
"""

class Material_Type(Artwork_Type):
	materialType_artwork_type = models.OneToOneField('Artwork_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name= _(u"Type of Material artwork")
		verbose_name_plural= _(u"o-> Types of Material artworks")


"""
@python_2_unicode_compatible
class Asset(Material):
	asset_material = models.OneToOneField('Material', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	asset_human = models.ForeignKey('Human', verbose_name=_(u"Entity"))
	reciprocity = models.TextField(blank=True, verbose_name=_(u"Reciprocity"))
	class Meta:
		verbose_name = _(u"Asset")
		verbose_name_plural = _(u"o- Assets")
	def __str__(self):
		return '('+self.material_type.name+') '+self.material.name

	def _selflink(self):
		if self.id:
				return a_strG + "asset/" + str(self.id) + a_str2 + a_edit +"</a>"# % str(self.id)
		else:
				return "Not present"
	_selflink.allow_tags = True
	_selflink.short_description = ''
"""


# - - - - - U N I T S

from valuenetwork.valueaccounting.models import Unit as Ocp_Unit

@python_2_unicode_compatible
class Unit(Artwork):	# Create own ID's
    unit_type = TreeForeignKey('Unit_Type', blank=True, null=True, verbose_name=_(u"Type of Unit"))
    code = models.CharField(max_length=4, verbose_name=_(u"Code or Symbol"))

    region = TreeForeignKey('Region', blank=True, null=True, verbose_name=_(u"related use Region"))
    #human = models.ForeignKey('Human', blank=True, null=True, verbose_name=_(u"related Entity"))

    ocp_unit = models.OneToOneField(Ocp_Unit, blank=True, null=True, verbose_name=_(u"OCP Unit"), related_name="gen_unit")

    class Meta:
    	verbose_name= _(u'Unit')
    	verbose_name_plural= _(u'o- Units')

    def __str__(self):
        if hasattr(self, 'ocp_unit') and self.ocp_unit:
            return self.name+' <'
        else:
            return self.unit_type.name+': '+self.name

class Unit_Type(Artwork_Type):
	unitType_artwork_type = models.OneToOneField('Artwork_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)

	class Meta:
		verbose_name = _(u"Type of Unit")
		verbose_name_plural = _(u"o-> Types of Units")



# - - - - - R E C O R D

@python_2_unicode_compatible
class Record(Artwork):	# Create own ID's
	record_type = TreeForeignKey('Record_Type', blank=True, null=True, verbose_name=_(u"Type of Record"))
	class Meta:
		verbose_name= _(u'Record')
		verbose_name_plural= _(u'o- Records')
	def __str__(self):
		if self.record_type is None or self.record_type == '':
			return self.name
		else:
			return self.record_type.name+': '+self.name

	def _selflink(self):
		if self.id:
				return a_strG + "record/" + str(self.id) + a_str2 + a_edit +"</a>"# % str(self.id)
		else:
				return "Not present"
	_selflink.allow_tags = True

class Record_Type(Artwork_Type):
	recordType_artwork_type = models.OneToOneField('Artwork_Type', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	class Meta:
		verbose_name= _(u'Type of Record')
		verbose_name_plural= _(u'o-> Types of Records')


@python_2_unicode_compatible
class UnitRatio(Record):
	record = models.OneToOneField('Record', primary_key=True, parent_link=True, on_delete=models.CASCADE)

	in_unit = models.ForeignKey('Unit', related_name='ratio_in', verbose_name=_(u"in Unit"))
	rate = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_(u"Ratio multiplier"))
	out_unit = models.ForeignKey('Unit', related_name='ratio_out', verbose_name=_(u"out Unit"))
	class Meta:
		verbose_name = _(u"Equivalence between Units")
		verbose_name_plural = _(u"o- Equivalences between Units")
	def __str__(self):
		return self.in_unit.name+' * '+str(self.rate)+' = '+self.out_unit.name


"""
@python_2_unicode_compatible
class AccountCes(Record):
	record = models.OneToOneField('Record', primary_key=True, parent_link=True, on_delete=models.CASCADE)

	accCes_human = models.ForeignKey('Human', related_name='accountsCes', verbose_name=_(u"Owner human entity"))
	entity = models.ForeignKey('Project', verbose_name=_(u"Network of the account"))
	unit = models.ForeignKey('Unit', verbose_name=_(u"Unit (currency)"))
	code = models.CharField(max_length=10, blank=True, null=True, verbose_name=_(u"Network code"))
	number = models.CharField(max_length=4, blank=True, null=True, verbose_name=_(u"Account number"))

	class Meta:
		verbose_name= _(u'CES Account')
		verbose_name_plural= _(u'o- CES Accounts')

	def __str__(self):
		return '('+self.unit.code+') '+self.accCes_human.nickname + ' ' + self.code + self.number#+' '+self.name


@python_2_unicode_compatible
class AccountBank(Record):
	record = models.OneToOneField('Record', primary_key=True, parent_link=True, on_delete=models.CASCADE)

	accBnk_human = models.ForeignKey('Human', related_name='accountsBank', verbose_name=_(u"Owner human entity"))
	company = models.ForeignKey('Company', blank=True, null=True, verbose_name=_(u"Bank entity"))
	unit = models.ForeignKey('Unit', blank=True, null=True, verbose_name=_(u"Unit (currency)"))
	code = models.CharField(max_length=11, blank=True, null=True, verbose_name=_(u"SWIFT/BIC Code"))
	number = models.CharField(max_length=34, blank=True, null=True, verbose_name=_(u"IBAN Account number"))
	bankcard = models.BooleanField(default=False, verbose_name=_(u"with bank Card?"))

	class Meta:
		verbose_name= _(u'Bank Account')
		verbose_name_plural= _(u'o- Bank Accounts')

	def __str__(self):
		try:
			return '('+self.unit.code+') '+self.company.nickname+': '+self.accBnk_human.nickname + ' ' + self.number
		except:
			return "<projecte buit>"


@python_2_unicode_compatible
class AccountCrypto(Record):
	record = models.OneToOneField('Record', primary_key=True, parent_link=True, on_delete=models.CASCADE)
	accCrypt_human = models.ForeignKey('Human', related_name='accountsCrypto', verbose_name=_(u"Owner human entity"))
	unit = models.ForeignKey('Unit', verbose_name=_(u"Unit (currency)"))
	number = models.CharField(max_length=34, blank=True, verbose_name=_(u"Address of the wallet"))
	class Meta:
		verbose_name = _(u"Cryptocurrency Account")
		verbose_name_plural = _(u"o- Cryptocurrency Accounts")

	def __str__(self):
		return '('+self.unit.code+') '+self.accCrypt_human.nickname + ' ' + self.number # +' '+self.name

"""



#   B A S I C   D B   R E C O R D S  ##

from django.db.models.signals import post_migrate
#from general.apps import GeneralAppConfig

def create_general_types(**kwargs):
    sep = ", "
    out = "Initial basic types created: <br>"
    being, created = Type.objects.get_or_create(name='Being', clas='Being')
    if created: out += str(being)+sep
    artwork, created = Type.objects.get_or_create(name='Artwork', clas='Artwork')
    if created: out += str(artwork)+sep
    space, created = Type.objects.get_or_create(name='Space', clas='Space')
    if created: out += str(space)+'<br>'

    """human, created = Being_Type.objects.get_or_create(name='Human', clas='Human', parent=being)
    if created: out += str(human)+": "

    persons = Being_Type.objects.filter(name="Person")
    if persons:
        if len(persons) > 1:
            out += "ERROR there's more than one 'Person' as a Being_Type ?"+'<br>'
            return out
        else:
            person = persons[0]
    else:
        person, created = Being_Type.objects.get_or_create(name='Person', parent=human)
        if created: out += str(person)+sep
    person.clas = 'Person'
    person.parent = human
    person.save()

    projects = Being_Type.objects.filter(name="Project")
    if projects:
        if len(projects) > 1:
            out += "ERROR there's more than one 'Project' as a Being_Type ?"+'<br>'
            return out
        else:
            project = projects[0]
    else:
        project, created = Being_Type.objects.get_or_create(name='Project', parent=human)
        if created: out += str(project)+sep
    project.clas = 'Project'
    project.parent = human
    project.save()

    companys = Being_Type.objects.filter(name="Company")
    if companys:
        if len(companys) > 1:
            out += "ERROR there's more than one 'Company' as a Being_Type ?"+'<br>'
            return out
        else:
            company = companys[0]
    else:
        company, created = Being_Type.objects.get_or_create(name='Company', parent=human)
        if created: out += str(company)+'<br>'
    company.clas = 'Company'
    company.parent = human
    company.save()

    material, created = Artwork_Type.objects.get_or_create(name='Material', clas='Material', parent=artwork)
    if created: out += str(material)+sep

    nonmaterial, created = Artwork_Type.objects.get_or_create(name='Non-material', clas='Nonmaterial', parent=artwork)
    if created: out += str(nonmaterial)+sep"""

    record, created = Artwork_Type.objects.get_or_create(name='Record', clas='Record', parent=artwork)
    if created: out += str(record)+sep

    unit, created = Artwork_Type.objects.get_or_create(name='Unit', clas='Unit', parent=artwork)
    if created: out += str(unit)+sep

    """currency, created = Unit_Type.objects.get_or_create(name='Currency', parent=unit)
    if created: out += str(currency)+sep
    social, created = Unit_Type.objects.get_or_create(name='MutualCredit currency', parent=currency)
    if created: out += str(social)+sep
    crypto, created = Unit_Type.objects.get_or_create(name='Cryptocurrency', parent=currency)
    if created: out += str(crypto)+sep
    fiat, created = Unit_Type.objects.get_or_create(name='Fiat currency', parent=currency)
    if created: out += str(crypto)+'<br>'
    """

    region, created = Space_Type.objects.get_or_create(name='Region', clas='Region', parent=space)
    if created: out += str(region)+sep
    address, created = Space_Type.objects.get_or_create(name='Address', clas='Address', parent=space)
    if created: out += str(address)+'<br>'

    unitratio, created = Record_Type.objects.get_or_create(name='Unit Ratio', clas='UnitRatio', parent=record)
    if created: out += str(unitratio)+sep
    """ces, created = Record_Type.objects.get_or_create(name='Account Ces', clas='AccountCes', parent=record)
    if created: out += str(ces)+sep
    bank, created = Record_Type.objects.get_or_create(name='Account Bank', clas='AccountBank', parent=record)
    if created: out += str(bank)+sep"""

    print(out)
    return out

#post_migrate.connect(create_general_types, sender=GeneralAppConfig)
