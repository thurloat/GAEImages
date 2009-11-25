from google.appengine.ext import db
from django.utils.translation import ugettext_lazy as _
import django.forms
import pickle
import properties
import models

################################################################
# Model Mix-ins
################################################################
# TODO (Wolfe):  _Auditable and _SaveHistory are NOT independent.
#    Restructure so you can include or the other or both.

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.db import djangoforms
from utils import *
import copy
from django import forms
from django.forms import CharField
END_OF_TIME = dt.date(9999, 12, 31)

from norex.pager import match_filter, INEQUALITY_OPERATORS

class GaebarModelHook(object):
  running_gaebar = False
  def __init__(self, *args, **kwds):
    return db.Model.__init__(self, *args, **kwds) if GaebarModelHook.running_gaebar else super(GaebarModelHook, self).__init__(*args, **kwds)
  @classmethod
  def get(cls, *args, **kwds):
    return db.Model.get(*args, **kwds) if GaebarModelHook.running_gaebar else super(GaebarModelHook, cls).get(*args, **kwds)
  def put(self, *args, **kwds):
    return db.Model.put(self, *args, **kwds) if GaebarModelHook.running_gaebar else super(GaebarModelHook, self).put(*args, **kwds)
  def delete(self, *args, **kwds):
    return db.Model.delete(self, *args, **kwds) if GaebarModelHook.running_gaebar else super(GaebarModelHook, self).delete(*args, **kwds)
  @classmethod
  def all(cls, *args, **kwds):
    return db.Model.all(*args, **kwds) if GaebarModelHook.running_gaebar else super(GaebarModelHook, cls).all(*args, **kwds)


class BitemporalQuery(object): # TODO:  Handle keys_only ?
  def __init__(self, query):
    self._inequality_prop = None
    self._manual_filter = False
    self.date = _Bitemporal._date
    if self.date is None:
      self._query = query.filter("_bitemporal_last", True)
    else:
      self._query = query
  @property
  def model(self): return self._query.model
  def __iter__(self): return self._query.run()
  def __getitem__(self, arg): return self._query.__getitem__(arg)
  def __len__(self):
    return self._query.__len__()
  def filter(self, property_operator, value):
    self._query = self._query.filter(property_operator, value)
    return self
  def order(self, prop):
    self._query = self._query.order(prop)
    return self
  def ancestor(self, ancestor):
    self._query = self._query.ancestor(ancestor)
    return self

  def get(self):
    if self.date is None:
      return self._query.get()
    else:
      results = self.fetch(100)
      return results[0] if results else None
  def fetch(self, limit, offset=0):
    if self.date is None:
      return self._query.fetch(limit, offset)
    else:
      return [x for x in self._query.fetch(limit, offset) if x.effective_date <= self.date and x.expiry_date > self.date]

class Bitemporal(db.Model):
  @classmethod
  def setup_delete_fields(cls):
    map (cls.protect_field, ['effective_date', 'expiry_date', '_bitemporal_action'])
    return super(_Bitemporal, cls).setup_delete_fields()
  bitemporal = True

class _Bitemporal(db.Model):
  _date = None # Make all db transaction assuming today is this _date.
  effective_date = db.DateProperty(default=dt.date.today())
  expiry_date = db.DateProperty(default=END_OF_TIME)
  # If action is delete, all other form fields are ignored except effective_date (of the deletion).
  _bitemporal_action = db.StringProperty(choices=['delete', 'split', 'change'])
  # from django.db import models as djangomodels
  # _bitemporal_action = djangomodels.CharField()
  _bitemporal_key = db.StringProperty()
  _bitemporal_last = db.BooleanProperty(required=False,default=False)

  def bitemporal_summary(self): return str(self)

  def date_chain(self, start=dt.date(1000,1,1), end=END_OF_TIME):
    saved_date = _Bitemporal._date
    _Bitemporal._date = None
    obj = self.__class__.get(self._bitemporal_key)
    _Bitemporal._date = saved_date
    return obj._date_chain(start, end)

  def _date_chain(self, start=dt.date(1000,1,1), end=END_OF_TIME):
    query = (self.real_all()
             .filter('_bitemporal_key', self._bitemporal_key)
             .filter('effective_date >=', start)
             .filter('_active', True)
             )
    if end < END_OF_TIME: query = query.filter('effective_date <', end)
    query = query.order('-effective_date')
    results = query.fetch(1000)
    for name,value in self.properties().items():
      if name[0] == '_': pass
      elif isinstance(value, db.ReferenceProperty):
        value = getattr (self, name)
        if isinstance(value, Bitemporal):
          results.extend (value._date_chain(self.effective_date, self.expiry_date))
      elif isinstance(value, properties.ReferenceListProperty):
        for value in getattr (self, name):
          if isinstance(value, Bitemporal):
            results.extend (value._date_chain(self.effective_date, self.expiry_date))
      else: pass
    results.sort(None,lambda x: x.effective_date,True)
    return results
  
  def __init__(self, *args, **kwds):
    if not getattr(self, 'bitemporal', False): return super(_Bitemporal, self).__init__(*args, **kwds)
    self.bitemporal = True
    super(_Bitemporal, self).__init__(*args, **kwds)
    if not self.effective_date:
      self.effective_date = dt.date.today()

  @classmethod
  def all(cls):
    if not getattr(cls, 'bitemporal', False): return super(_Bitemporal, cls).all()
    return BitemporalQuery(super(_Bitemporal, cls).all())

  @classmethod
  def real_all(cls):
    return super(_Bitemporal, cls).all()

  def put(self):
    if not getattr(self, 'bitemporal', False): return super(_Bitemporal, self).put()
    previous = db.get(self.key())
    action = self._bitemporal_action
    self._bitemporal_action = None
    if action == 'split' and self.effective_date != previous.effective_date:
      # TODO:  Add sanity checks that the split date is between current and future date
      #  idea: Subclass DateProperty w/ an additional check on the effective_date
      if not (self.effective_date > previous.effective_date):
        raise Exception('New effective date must be later than previous effective date.')
      if self._bitemporal_key is None:
        raise Exception('The _bitemporal_key did not get set.')
      self._entity = None
      self._key_name = None
      self._key = None
      previous.expiry_date = self.effective_date
      previous._bitemporal_last = False
      self._bitemporal_last = True
      # TODO: In a transaction!
      super(_Bitemporal, previous).put()
      return super(_Bitemporal, self).put()
    elif action == 'delete':
      previous = db.get(self.key())
      self.expiry_date = self.effective_date
      self.effective_date = previous.effective_date
      return super(_Bitemporal, self).put()
    else:
      if self._bitemporal_key is None:
        self._bitemporal_key = str(self.key())
        self._bitemporal_last = True
      return super(_Bitemporal, self).put()

  @classmethod
  def _process_get(cls, result):
    # If a date is specified, return current active record.  Else return the last record.
    # Additionally, pre-fetch ReferenceProperty and ReferenceListProperty fields.
    if isinstance(result, list):
      return [cls._process_get(x) for x in result]
    query = cls.all().filter("_bitemporal_key", result._bitemporal_key)
    if _Bitemporal._date is None:
      query = query.filter("_bitemporal_last", True)
    else:
      query = query.filter("effective_date <=", _Bitemporal._date).order("-effective_date")
    result = query.get()
    if not result: return result
    for name in getattr(cls, '_bitemporal_prefetch', ()):
      setattr(result, name, filter(identity, [item.__class__._process_get(item) for item in getattr(result, name)]))
    return result

  @classmethod
  def get(cls, keys):
    # If gaebar is running (or we're not bitemporal) use the real get.
    if not getattr(cls, 'bitemporal', False): return super(_Bitemporal, cls).get(keys)
    return db.Model.get(keys) if GaebarModelHook.running_gaebar else cls._process_get(super(_Bitemporal, cls).get(keys))

  @classmethod
  def set_date(cls, date=None):
    """Set the current effective date for all database transactions."""
    _Bitemporal._date = date
  @classmethod
  def reset_date(cls, date=None):
    """Reset the current effective date for all database transactions.
    That is, database queries should grab the chronologically latest entity
    which exceeds today's date."""
    cls.set_date()

last_model_saved = None # TODO: This is an unwise hack to avoid rewriting a view for a miniform row.
class _AssignKeyName(object):
  def __init__(self, *args, **kwds):
    if ('key_name' not in kwds) or (kwds['key_name'] is None):
      kwds['key_name'] = unique_key_name()
    super(_AssignKeyName, self).__init__(*args, **kwds)
  def put(self):
    global last_model_saved
    result = super(_AssignKeyName, self).put()
    if result: last_model_saved = self
  def __unicode__(self):
    return "PLEASE OVERRIDE __unicode__ METHOD"

class _Auditable(object):
  """ Every save, edit, or delete to an _Auditable model records an entry in model Audit """
  def str_search_string(self): return str(self)
  def str_autocomplete_info(self): return str(self)
  def before_save_hook(self): pass
  def put(self):
    self.log('put')
    self.search_string = self.str_search_string().upper()
    self.before_save_hook()
    return super(_Auditable, self).put()
  def delete(self):
    self.log('delete')
    return super(_Auditable,self).delete()
  def log(self, op):
    audit = models.Audit(
      user = users.get_current_user(),
      action = op,
      xml = self.to_xml())
    audit.put()
  def editable(self): return True
  def showable(self): return True
  @classmethod
  def creatable(cls): return True
  @classmethod
  def miniform_searchable(cls): return False
  def deletable(self):
    """Return true if this item has no ReferenceProperty or ReferenceListProperty links to it.
    (Currently tested by doing a fetch on all its Query properties.)
    """
    return not any ( [getattr(self,x).fetch(1) for x in dir(self) if isinstance(getattr(self,x), db.Query)] )
  

  @classmethod   # TODO: Not logically part of _Auditable. Rename _Auditable?
  def filter_prefix(cls, property_name, prefix):
    query = cls.all()
    query.filter("%s >= " % property_name, u"%s" % prefix)
    query.filter("%s < " % property_name, u"%s\xEF\xBF\xBD" % prefix)
    return query

class _SaveHistory(object):
  # These are defined in PictouModel to centralize the stuff that depends on inheritance from db.Model.  See TODO.
  # _active = db.BooleanProperty()
  # _timestamp = db.DateTimeProperty()
  # _current = db.SelfReferenceProperty()
  # search_string = db.StringProperty()
  
  """ On every edit and delete, this add-on saves previous states of
  the Model along with a timestamp.  The previous versions are saved
  as inactive records in the same table as the Model inself. """ 
  @classmethod
  def all(cls):
    """Query for only the active records

    NOTE:  To really return ALL, including "deleted" records, use real_all()
    """
    return super(_SaveHistory,cls).all().filter('_active =',True)
  @classmethod
  def real_all(cls):
    """ Query all records
    """
    return super(_SaveHistory,cls).all()

  # _current = db.ReferenceProperty()
  def real_delete(self):
    return super(_SaveHistory, self).delete()

  def delete(self):
    """Disable rather than delete items
    """
    self._active = False
    self._timestamp = dt.datetime.now()
    super(_SaveHistory,self).put()
  def put(self):
    """Save a copy of the previous record on every put().
    """
    # Alternative which uses the API is to property-copy as in appengine.ext.db.__init__.py, Model class init.
    if self._entity is not None:
      oldme = db.get(self.key())
      oldme._entity = None     # These two lines are used to force the
      oldme._key_name = None   # save of a new object.
      oldme._key = None   # save of a new object.
      oldme._active = False
      oldme._current = self.key()
      oldme._timestamp = dt.datetime.now()
      db.Model.put(oldme)
    self._timestamp = dt.datetime.now()
    self._active = True
    return super(_SaveHistory,self).put() 

from authorization.models import ModelWithPermissions
class PictouModel(db.Model):
  _active = db.BooleanProperty()
  _timestamp = db.DateTimeProperty()
  _current = db.SelfReferenceProperty()
  search_string = db.StringProperty()

  _protected_fields = []
  _deleted_fields = []
  @classmethod
  def protect_field(cls, field): cls._protected_fields.append(field)
  @classmethod
  def setup_delete_field(cls, field): cls._deleted_fields.append(field)
  @classmethod
  def setup_delete_fields(cls):
    map (cls.setup_delete_field, ['effective_date', 'expiry_date', '_bitemporal_action'])
    return set(cls._deleted_fields).difference(cls._protected_fields)
  @property
  def model_name(self):
    return self.__class__.__name__
  def str_autocomplete_info(self): return str(self)

class Expando  (PictouModel, ModelWithPermissions, _SaveHistory, _Auditable, _AssignKeyName, db.Expando): pass
class Model    (GaebarModelHook, _Bitemporal, PictouModel, ModelWithPermissions, _SaveHistory, _Auditable, _AssignKeyName, db.Model): pass

# METHODS_TO_SAVE = ['put', 'get', 'all', 'delete', '__init__']
# def save_methods(cls):
#   cls._methods_backed_up = {}
#   for method in METHODS_TO_SAVE:
#     if hasattr(cls, method):
#       cls._methods_backed_up[method] = getattr(cls, method)
#       try: delattr(cls, method)
#       except AttributeError:
#         del cls._methods_backed_up[method]

# def restore_methods(cls):
#   for (method, value) in cls._methods_backed_up.items():
#     setattr(cls, method, value)
#   del cls._methods_backed_up

class MergeMetaMetaclass(djangoforms.ModelFormMetaclass):
  def __new__(cls, class_name, bases, attrs):
    Meta = attrs.get('Meta', type('Meta', (), {}))
    if (not hasattr(Meta, 'exclude')): Meta.exclude = []
    Meta.exclude.extend(['search_string','_active','_timestamp','_current',
                         '_bitemporal_last', '_bitemporal_key'])
    return super(MergeMetaMetaclass, cls).__new__(cls, class_name, bases, attrs)

from authorization.models import has_property_permission
class Form(djangoforms.ModelForm):
  def __init__(self, *args, **kwds):
    super(Form, self).__init__(*args, **kwds)
    instance = getattr(self, 'instance', None)
    model = self._meta.model.__name__
    for field in self._meta.model.setup_delete_fields():
      self.fields.pop(field, None)
    if instance:
      if getattr(instance, 'expiry_date', END_OF_TIME) != END_OF_TIME:
        self.fields['expiry_date'] = ReadOnlyTextField(label = instance._bitemporal_last and 'Expiry' or 'Until')
      else:
        self.fields.pop('expiry_date', None)
    for name in self.fields:
      if name == '_bitemporal_action':
        self.fields[name] = forms.ChoiceField(widget=forms.RadioSelect,
                                              required=False,
                                              label='Action',
                                              choices=[('change', 'Change the effective date'),
                                                       ('split', 'Make change on the effective date'),
                                                       ('delete', 'Expire on effective date (form below ignored)')])
      if not has_property_permission (model, name, 'view'):
        del self.fields['name']
        continue
      if instance and not has_property_permission ('Policy', name, 'edit'):
        self.fields[name] = read_only_version_of(self.fields[name])
      if not instance and not has_property_permission ('Policy', name, 'create'):
        del self.fields[name]

  __metaclass__ = MergeMetaMetaclass

################################################################
# Widgets and Fields
################################################################

from django.forms.util import flatatt, smart_unicode
from django.forms.widgets import CheckboxInput
from django.utils.html import escape


class SelectMultiple(forms.SelectMultiple):
  def value_from_datadict (self, data, file, name): return data.getlist(name)

class CheckboxSelectMultiple(forms.CheckboxSelectMultiple):
  """This version pre-processes the value list to convert model instances to keys"""
  @classmethod
  def value_from_datadict (self, data, file, name):
    return data.getlist(name)
  def render (self, name, value, attrs=None, choices=()):
    if value is None: value = []
    value = [isinstance (v, Model) and v.key() or v for v in value]
    return super(CheckboxSelectMultiple, self).render(name, value, attrs, choices)

class ReadOnlyTextField(forms.Field):
  def __init__(self, *args, **kwds):
    kwds['widget'] = ReadOnlyTextWidget()
    super(ReadOnlyTextField,self).__init__(*args, **kwds)
  def clean(self, value):
    return self.initial
class ReadOnlyTextWidget(forms.Widget):
  def render(self, name, value, attrs=None):
    self.value = value
    if value is None: value = ''
    value = smart_unicode(value)
    final_attrs = self.build_attrs(attrs, name=name)
    return u'<b%s>%s</b>' % (flatatt(final_attrs), escape(value))

def read_only_version_of (field):
  return field if isinstance(field, ReadOnlyVersionOf) else ReadOnlyVersionOf(field)

class ReadOnlyVersionOf(forms.Field):
  def __init__(self, old_field):
    class Widget(forms.Widget):
      def render(self, name, value, attrs=None):
        self.value = value
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        return u'<span%s><strong>%s</strong></span>' % (flatatt(final_attrs), smart_unicode(old_field.clean(value)))
    return super(ReadOnlyVersionOf,self).__init__(widget=Widget())
  def clean(self, value):
    return self.initial


integer_list_re = re.compile(r"^[0-9]+$")
class IntegerListField(forms.CharField):
  def __init__(self, max_length=None, min_length=None, *args, **kwargs):
    kwargs['widget'] = kwargs.get('widget', IntegerListTextarea(attrs={'cols': 10}))
    super(IntegerListField, self).__init__(integer_list_re, max_length, min_length, *args, **kwargs)
  default_error_messages = {
    'invalid': _(u'Enter a list of integers separated by commas, newlines, or whitespace.'),
    }
  def clean(self, value):
    return [int(i) for i in re.sub('\D+', " ", value).strip().split()]

class IntegerListTextarea(forms.Textarea):
  def render(self, name, value, attrs=None):
    if value is not None:
      value = "\n".join([str(i) for i in value])
    return super(IntegerListTextarea, self).render(name, value, attrs)

class IntegerListInput(forms.TextInput):
  def render(self, name, value, attrs=None):
    if value is not None:
      value = ", ".join([str(i) for i in value])
    return super(IntegerListInput, self).render(name, value, attrs)
