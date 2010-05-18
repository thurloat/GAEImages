# -*- coding: utf-8 -*-

# class ReferenceListProperty(db.Property):

from google.appengine.ext import db
from google.appengine.api import datastore_errors
from django import forms
from google.appengine.ext.db import _ReverseReferenceProperty, DuplicatePropertyError

################################################################
# ReferenceListProperty
################################################################

class ReferenceListProperty(db.Property):
  """A property that stores a list of models.
  
  This is a parameterized property; the parameter must be a valid
  Model type, and all items must conform to this type.

  Obtained from: http://groups.google.com/group/google-appengine/msg/d203cc1b93ee22d7
  """
  def __init__(self,
               reference_class = None,
               verbose_name=None,
               collection_name=None,
               default=None,
               **kwds):
    """Construct ReferenceListProperty.

    Args:
      reference_class: Type for the list items; must be a subclass of Model.
      verbose_name: Optional verbose name.
      default: Optional default value; if omitted, an empty list is used.
      **kwds: Optional additional keyword arguments, passed to base class.
    """
    if not issubclass(reference_class, db.Model):
      raise TypeError('Item type should be a subclass of Model')
    if default is None:
      default = []
    self.reference_class = reference_class
    self.collection_name = collection_name
    super(ReferenceListProperty, self).__init__(verbose_name,
                                                default=default,
                                                **kwds)
  
  def validate(self, value):
    """Validate list.

    Note that validation here is just as broken as for ListProperty.
    The values in the list are only validated if the entire list is
    swapped out. If the list is directly modified, there is no attempt
    to validate the new items.

    Returns:
      A valid value.

    Raises:
      BadValueError if property is not a list whose items are
      instances of the reference_class given to the constructor.
    """
    value = super(ReferenceListProperty, self).validate(value)
    if value == [None]: return []
    if value is not None:
      if not isinstance(value, list):
        raise db.BadValueError('Property %s must be a list' %
                               self.name)
      for item in value:
        if not isinstance(item, self.reference_class):
          raise db.BadValueError(
            'Items in the %s list must all be %s instances' %
            (self.name, self.reference_class.__name__))
    return value

  def empty(self, value):
    """Is list property empty.

    [] is not an empty value.
 
    Returns:
      True if value is None, else False.
    """ 
    return value is None

  data_type = list
 
  def default_value(self):
    """Default value for list.
 
    Because the property supplied to 'default' is a static value,
    that value must be shallow copied to prevent all fields with
    default values from sharing the same instance.
 
    Returns:
      Copy of the default value.
    """ 
    return list(super(ReferenceListProperty, self).default_value())
 
  def get_value_for_datastore(self, model_instance):
    """A list of key values is stored.

    Prior to storage, we validate the items in the list.
    This check seems to be missing from ListProperty.

    Args:
      model_instance: Instance to fetch datastore value from.
 
    Returns:
      A list of the keys for all Models in the value list.
    """
    value = self.__get__(model_instance, model_instance.__class__)
    self.validate(value)
    if value is None:
      return None
    else:
      return [v.key() for v in value]
 
  def make_value_from_datastore(self, value):
    """Recreates the list of Models from the list of keys.
 
    Args:
      value: value retrieved from the datastore entity.

    Returns:
      None or a list of Models.
    """ 
    if value is None:
      return None
    else:
      return [db.get(v) for v in value]

# Adam Thurlow recommend...
#   def get_form_field(self, **kwargs):
#     defaults = {'form_class': forms.ModelMultipleChoiceField,
#                 'queryset': self.reference_class.all(),
#                 'required': False}
#     defaults.update(kwargs)
#     return super(ReferenceListProperty, self).get_form_field(**defaults)

# DW added this code copied from /usr/local/google_appengine/google/appengine/ext/db/__init__.py
  def __property_config__(self, model_class, property_name):
    super(ReferenceListProperty, self).__property_config__(model_class,
                                                       property_name)

    if self.collection_name is None:
      self.collection_name = '%s_listref_set' % (model_class.__name__.lower())
    if hasattr(self.reference_class, self.collection_name):
      raise DuplicatePropertyError('Class %s already has property %s'
                                   % (self.reference_class.__name__,
                                      self.collection_name))
    setattr(self.reference_class,
            self.collection_name,
            _ReverseReferenceProperty(model_class, property_name))
