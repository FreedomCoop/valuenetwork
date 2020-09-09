
import copy
from django import forms
from django.contrib.admin.templatetags.admin_static import static
from django.urls import reverse
from django.utils.html import escape, format_html, format_html_join, smart_urlquote
from django.utils.text import Truncator
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils import six
from django.contrib import admin
from django.forms.widgets import SelectMultiple
from django.http import HttpResponse
from django.utils.html import escape, escapejs
from django.conf import settings
from django.template.loader import render_to_string

def url_params_from_lookup_dict(lookups):
		"""
		Converts the type of lookups specified in a ForeignKey limit_choices_to
		attribute to a dictionary of query parameters
		"""
		params = {}
		if lookups and hasattr(lookups, 'items'):
				items = []
				for k, v in list(lookups.items()):
						if callable(v):
								v = v()
						if isinstance(v, (tuple, list)):
								v = ','.join(str(x) for x in v)
						elif isinstance(v, bool):
								# See django.db.fields.BooleanField.get_prep_lookup
								v = ('0', '1')[v]
						else:
								v = six.text_type(v)
						items.append((k, v))
				params.update(dict(items))
		return params

class ForeignKeyRawIdWidget(forms.TextInput):
	"""
	A Widget for displaying ForeignKeys in the "raw_id" interface rather than
	in a <select> box.
	"""
	def __init__(self, rel, admin_site, attrs=None, using=None, can_add_related=None, can_change_related=None, can_delete_related=None, instance_obj=None):
		self.rel = rel
		self.admin_site = admin_site
		self.db = using
		super(ForeignKeyRawIdWidget, self).__init__(attrs)

	def base_url_parameters(self):
		return url_params_from_lookup_dict(self.rel.limit_choices_to)

	def url_parameters(self):
		from django.contrib.admin.views.main import TO_FIELD_VAR
		params = self.base_url_parameters()
		params.update({TO_FIELD_VAR: self.rel.get_related_field().name})
		return params

	def label_for_value(self, value):
		key = self.rel.get_related_field().name
		try:
			obj = self.rel.to._default_manager.using(self.db).get(**{key: value})
			return '&nbsp;<strong>%s</strong>' % escape(Truncator(obj).words(14, truncate='...'))
		except (ValueError, self.rel.to.DoesNotExist):
			return ''

class contrib_ForeignKeyRawIdWidgetWrapper(ForeignKeyRawIdWidget):
		"""
		A Widget for displaying ManyToMany ids in the "raw_id" interface rather than
		in a <select multiple> box.
		"""
		def render(self, name, value, attrs=None):
			if attrs is None:
					attrs = {}
			if self.rel.to in self.admin_site._registry:
					# The related object is registered with the same AdminSite
					attrs['class'] = 'vForeignKeyRawIdWidget'
			if value:
					value = ','.join(force_text(v) for v in value)
			else:
					value = ''
			return super(ForeignKeyRawIdWidget, self).render(name, value, attrs)

		def url_parameters(self):
			return self.base_url_parameters()

		def label_for_value(self, value):
			return ''

		def value_from_datadict(self, data, files, name):
			value = data.get(name)
			return value

class ManyToManyRawIdWidget(ForeignKeyRawIdWidget):

    def url_parameters(self):
        return self.base_url_parameters()

    def label_for_value(self, value):
        return ''

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(',')

class contrib_ManyToManyRawIdWidgetWrapper(ManyToManyRawIdWidget):

    def url_parameters(self):
        return self.base_url_parameters()

    def label_for_value(self, value):
        return ''
    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(',')


from django.utils.translation import ugettext_lazy as _

class ForeignKeyRawIdWidgetWrapper(contrib_ForeignKeyRawIdWidgetWrapper):

	class Media:
		js = ("%srelated-widget-wrapper.js" % settings.STATIC_URL,)

	def __init__(self, *args, **kwargs):
		self.can_add_related = kwargs.pop('can_add_related', None)
		self.can_change_related = kwargs.pop('can_change_related', None)
		self.can_delete_related = kwargs.pop('can_delete_related', None)
		self.instance_obj = kwargs.pop('instance_obj', None)
		super(ForeignKeyRawIdWidgetWrapper, self).__init__(*args, **kwargs)

	@classmethod
	def from_contrib_wrapper(cls, wrapper, admin_site, can_add_related, can_change_related, can_delete_related, instance_obj):
		return cls(wrapper.rel, admin_site, None, None,
			can_add_related=can_add_related,
			can_change_related=can_change_related,
			can_delete_related=can_delete_related,
			instance_obj=instance_obj)

	def get_related_url(self, rel_to, info, action, args=[]):
		return reverse("admin:%s_%s_%s" % (info + (action,)), current_app=self.admin_site.name, args=args)

	def render(self, name, value, attrs={}, *args, **kwargs):
		rel_to = self.rel.to
		if attrs is None:
			attrs = {}
		extra = []
		info = (rel_to._meta.app_label, rel_to._meta.object_name.lower())
		if rel_to in self.admin_site._registry:
			# The related object is registered with the same AdminSite
			related_url = reverse(
					'admin:%s_%s_changelist' % (
							rel_to._meta.app_label,
							rel_to._meta.model_name,
					),
					current_app=self.admin_site.name,
			)

			params = self.url_parameters()
			if params:
				url = '?' + '&amp;'.join('%s=%s' % (k, v) for k, v in list(params.items()))
			else:
				url = ''

			if "class" not in attrs:
				attrs['class'] = 'vForeignKeyRawIdAdminField'	# The JavaScript code looks for this hook.

		output = [super(ForeignKeyRawIdWidget, self).render(name, value, attrs)] + extra
		if value:
			output.append(self.label_for_value(value))

		attrs['class'] = ' '.join((attrs.get('class', ''), 'related-widget-wrapper'))
		name_desc = name
		name = "%s_%s" % ( name, value )

		add_url = self.get_related_url(self.rel.to, info, 'add')
		add_help_text = _('Add Another')

		try:
			obj_desc = self.instance_obj.human.__str__()
		except:
			try:
				obj_desc = self.instance_obj.ic_membership.human.__str__()
			except:
				obj_desc = self.instance_obj.__str__()

		context = {
		 'widget' : mark_safe(''.join(output)),
		 'name': name,
		 'media_prefix': settings.STATIC_URL,
		 'can_add_related': self.can_add_related,
		 'add_link' :  add_url,
		 'add_help_text' : add_help_text,
		 'obj_desc' : obj_desc,
		 'name_desc': name_desc,
		 'look_link': ""
		}

		output = ""
		if value:
			java_remove = format_html(' onclick="remove_item_foreign(&#39;id_{0}&#39;); return false;"', name_desc)
			out_link = "<a %s href='javascript:void;'>%s</a>" % ( java_remove, _("Remove").encode("utf-8") )
			obj_desc = obj_desc + " | " + out_link
			#CRUD buttons
			if self.can_change_related:
				change_url = self.get_related_url(self.rel.to, info, 'change', [value])
				template = self.get_related_url(self.rel.to, info, 'change', ['%s'])
				change_url_template = template
				change_help_text =  _('Change related model')
				change_link = "<a class='related-widget-wrapper-link related-widget-wrapper-change-link changelink' "
				change_link += "id='edit_id_" + name + "' data-href-template='" + change_url_template + "'"
				if change_url:
					change_link += " href='" + change_url + "'"
				change_link += " title='" + change_help_text.encode("utf-8") + "'>"  + "</a>"
				obj_desc = obj_desc + " | " + change_link
				context.update({
					'obj_desc' : mark_safe(obj_desc),
					})
			if self.can_delete_related:
				delete_url = self.get_related_url(self.rel.to, info, 'delete', [value])
				template = self.get_related_url(self.rel.to, info, 'delete', ['%s'])
				delete_url_template = template
				delete_help_text =  _('Delete related model')
				del_link = "<a class='related-widget-wrapper-link related-widget-wrapper-delete-link deletelink' id='delete_id_"
				del_link += name + "' data-href-template='" + delete_url_template + "'"
				if delete_url:
					del_link += " href='" + delete_url  + "'"
				del_link += " title='" + delete_help_text.encode("utf-8") + "'>" + "</a>"
				obj_desc = obj_desc + " | " + del_link
				context.update({
					'obj_desc' : mark_safe(obj_desc),
					})
		if self.can_add_related:
			add_url = self.get_related_url(self.rel.to, info, 'add')
			add_help_text = _('Add Another')
			add_link = "<a class='related-widget-wrapper-link related-widget-wrapper-add-link add-related addlink' href='%s'>%s</a>" % (add_url, _("Add").encode("utf-8"))
			context.update({'add_link' : mark_safe(add_link)})
		look_url = related_url + url;
		look_link = "<a class='related-lookup related-widget-wrapper-link' href='"
		look_img = '<img src="%s" width="16" height="16" alt="%s" /></a>' % (static('admin/img/selector-search.gif'), _('Lookup'))
		look_link += look_url + "' id='look_id_" + name + "' > " + look_img + "</a>"
		context.update({'look_link' : mark_safe(look_link)})
		return  mark_safe(render_to_string('related-widget-wrapper.html', context))


class ManyToManyRawIdWidgetWrapper(contrib_ManyToManyRawIdWidgetWrapper):

	class Media:
			js = ("%srelated-widget-wrapper.js" % settings.STATIC_URL,)

	def __init__(self, *args, **kwargs):
		self.can_add_related = kwargs.pop('can_add_related', None)
		self.can_change_related = kwargs.pop('can_change_related', None)
		self.can_delete_related = kwargs.pop('can_delete_related', None)
		self.instance_obj = kwargs.pop('instance_obj', None)
		super(ManyToManyRawIdWidgetWrapper, self).__init__(*args, **kwargs)

	@classmethod
	def from_contrib_wrapper(cls, wrapper, admin_site, can_add_related, can_change_related, can_delete_related, instance_obj):
		return cls(wrapper.rel, admin_site, None, None,
			can_add_related=can_add_related,
			can_change_related=can_change_related,
			can_delete_related=can_delete_related,
			instance_obj=instance_obj)

	def get_related_url(self, rel_to, info, action, args=[]):
		return reverse("admin:%s_%s_%s" % (info + (action,)), current_app=self.admin_site.name, args=args)

	def manytomany_to_ul(self, field_name, manytomany_manager):
		hidden_ids_text_name = "id_%s" % ( field_name )
		output = '<ul id="ul_%s" name="ul_%s">' % ( hidden_ids_text_name, hidden_ids_text_name)

		if not manytomany_manager:
			pass
		else:
			info = (self.rel.to._meta.app_label, self.rel.to._meta.object_name.lower())
			for obj in manytomany_manager.all():
				#CRUD buttons
				change_link = None
				if self.can_change_related:
					change_url = self.get_related_url(self.rel.to, info, 'change', [obj.id])
					template = self.get_related_url(self.rel.to, info, 'change', ['%s'])
					change_url_template = template
					change_help_text =  _('Change related model')
					change_link = "<a class='related-widget-wrapper-link related-widget-wrapper-change-link changelink' "
					change_link += "id='edit_id_" + field_name + "' data-href-template='" + change_url_template + "'"
					if change_url:
						change_link += " href='" + change_url + "'"
					change_link += " title='" + change_help_text.encode("utf-8") + "'>"  + "</a>"
				del_link = None
				if self.can_delete_related:
					delete_url = self.get_related_url(self.rel.to, info, 'delete', [obj.id])
					template = self.get_related_url(self.rel.to, info, 'delete', ['%s'])
					delete_url_template = template
					delete_help_text =  _('Delete related model')
					del_link = "<a class='related-widget-wrapper-link related-widget-wrapper-delete-link deletelink' id='delete_id_"
					del_link += field_name + "' data-href-template='" + delete_url_template + "'"
					if delete_url:
						del_link += " href='" + delete_url  + "'"
					del_link += " title='" + delete_help_text.encode("utf-8") + "'>" + "</a>"
				name = "manytomany_%s_%s" % ( field_name, obj.id )
				java_remove = format_html(' onclick="remove_item(window,&#39;{0}&#39;,&#39;{1}&#39;, &#39;{2}&#39;); return false;"', name, hidden_ids_text_name, obj.id)
				out_link = "<a %s href='javascript:void;'>%s</a>" % ( java_remove, _("Remove").encode("utf-8") )
				span = "<span name='%s' id='%s' value='%s'>%s - %s|%s|%s</span>" % (name, name, obj.id, obj, out_link, change_link, del_link);
				output += "<li> %s </li>" % (span)
		return mark_safe(output + "</ul>")

	def render(self, name, value, attrs={}, *args, **kwargs):
		rel_to = self.rel.to
		if attrs is None:
			attrs = {}
		extra = []
		if rel_to in self.admin_site._registry:
			# The related object is registered with the same AdminSite
			related_url = reverse(
					'admin:%s_%s_changelist' % (
							rel_to._meta.app_label,
							rel_to._meta.model_name,
					),
					current_app=self.admin_site.name,
			)

			params = self.url_parameters()
			if params:
				url = '?' + '&amp;'.join('%s=%s' % (k, v) for k, v in list(params.items()))
			else:
				url = ''
			if "class" not in attrs:
				attrs['class'] = 'vManyToManyRawIdAdminField'	# The JavaScript code looks for this hook.
				#but if you want to get original hook class it as: hForeignKeyRawIdAdminField -->ALEPH
			# TODO: "lookup_id_" is hard-coded here. This should instead use
			# the correct API to determine the ID dynamically.
			extra.append('<a href="%s%s" class="related-lookup" id="lookup_id_%s" onclick="return showRelatedObjectLookupPopup(this);"> ' % (related_url, url, name))
			extra.append('<img src="%s" width="16" height="16" alt="%s" /></a>' %
					(static('admin/img/selector-search.gif'), _('Lookup')))
			if isinstance(value, (tuple, list)):
				value = ','.join(str(x) for x in value)
		output = [super(ForeignKeyRawIdWidget, self).render(name, value, attrs)] + extra

		records = None
		if value:
			output.append(self.label_for_value(value))
			records = getattr(self.instance_obj, name)

		info = (rel_to._meta.app_label, rel_to._meta.object_name.lower())
		attrs['class'] = ' '.join((attrs.get('class', ''), 'related-widget-wrapper'))
		context = {
		 'widget' : mark_safe(''.join(output)),
		 'name': name,
		 'media_prefix': settings.STATIC_URL,
		 'can_change_related': self.can_change_related,
		 'can_add_related': self.can_add_related,
		 'can_delete_related': self.can_delete_related,
		 'obj_desc' : self.manytomany_to_ul(name, records)
		}
		if self.can_add_related:
			context.update({
			'add_url': self.get_related_url(rel_to, info, 'add'),
			'add_help_text': _('Add Another')
		})

		return  mark_safe(render_to_string('related-widget-wrapper-manytomany.html', context))

class ForeignKeyRawIdWidgetWrapperAdmin(admin.ModelAdmin):

	def get_form(self, request, obj=None, **kwargs):
		from functools import partial
		kwargs['formfield_callback'] = partial(self.formfield_for_dbfield, request=request, obj=obj)
		return super(ForeignKeyRawIdWidgetWrapperAdmin, self).get_form(request, obj, **kwargs)

	def formfield_for_dbfield(self, db_field, **kwargs):
		this_object = kwargs.pop('obj', None)
		formfield = super(ForeignKeyRawIdWidgetWrapperAdmin, self).formfield_for_dbfield(db_field, **kwargs)

		if (formfield and isinstance(formfield.widget, admin.widgets.ForeignKeyRawIdWidget)):
			request = kwargs.pop('request', None)

			related_modeladmin = self.admin_site._registry.get(db_field.rel.to)

			can_add_related = bool(related_modeladmin and
			related_modeladmin.has_add_permission(request))

			can_change_related = bool(related_modeladmin and
			related_modeladmin.has_change_permission(request))

			can_delete_related = bool(related_modeladmin and
			related_modeladmin.has_delete_permission(request))
			if isinstance(formfield.widget, admin.widgets.ManyToManyRawIdWidget):
				widget = ManyToManyRawIdWidgetWrapper.from_contrib_wrapper(
					formfield.widget,
					self.admin_site,
					can_add_related,
					can_change_related,
					can_delete_related,
					this_object)
				formfield.widget = widget
			else:
				widget = ForeignKeyRawIdWidgetWrapper.from_contrib_wrapper(
					formfield.widget,
					self.admin_site,
					can_add_related,
					can_change_related,
					can_delete_related,
					this_object)
				formfield.widget = widget
		return formfield

	def response_change(self, request, obj):
		print("general.widgets:response_change")
		if '_popup' in request.REQUEST:
			pk_value = obj._get_pk_val()
			print(("This is pop redirect to" + '<script type="text/javascript">opener.dismissEditRelatedPopup(window, "%s", "%s");</script>' % \
			(escape(pk_value), escapejs(obj))))
			return HttpResponse('<script type="text/javascript">opener.dismissEditRelatedPopup(window, "%s", "%s");</script>' % \
			# escape() calls force_unicode.
			(escape(pk_value), escapejs(obj)))
		else:
			return super(ForeignKeyRawIdWidgetWrapperAdmin, self).response_change(request, obj)

	def response_add(self, request, obj):
		print("hace add")
		if '_popup' in request.REQUEST:
			pk_value = obj._get_pk_val()
			print("return")
			return HttpResponse('<script type="text/javascript">opener.dismissEditRelatedPopup(window, "%s", "%s");</script>' % \
			# escape() calls force_unicode.
			(escape(pk_value), escapejs(obj)))
		else:
			return super(ForeignKeyRawIdWidgetWrapperAdmin, self).response_change(request, obj)

	def response_delete(self, request, obj_display):
		print(("hace del " + obj_display))
		if '_popup' in request.REQUEST:
			return HttpResponse('<script type="text/javascript">opener.dismissDeleteRelatedPopup(window, "%s");</script>' % obj_display)
		else:
			return super(ForeignKeyRawIdWidgetWrapperAdmin, self).response_change(request, obj)
