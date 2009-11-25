from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views.generic.list_detail import object_list, object_detail
from django.views.generic.create_update import create_object, delete_object, update_object, get_model_and_form_class
from django.template import loader
from django import forms
from google.appengine.api import users
from ragendja.json import JSONResponse
from google.appengine.runtime import DeadlineExceededError
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError
from django.shortcuts import render_to_response
from utils import *
from authorization.models import has_permission, users_to_emulate, current_user
import os
from django.template import RequestContext
import draft

################################################################
# Render
################################################################
IS_DEV = os.environ['SERVER_SOFTWARE'].startswith('Dev')  # Development server
base_template_params = {}
def template_params(request, params):
  p = {}
  import logging
  logging.debug("IN common/norex/views.py template_params: current_user = %s", current_user())
  p.update(base_template_params)
  p.update(params)
  return p

def respond(request, template, params=None, model=None):
  """Helper to render a response, passing standard stuff to the response.

  Args:
    request: The request object.
    template: The template name.
    params: A dict giving the template parameters; modified in-place.

  Returns:
    Whatever render_to_response(template, params) returns.

  Raises:
    Whatever render_to_response(template, params) raises.
  """
  if params is None: params = {}
  try:
    return render_to_response(template, template_params(request, params), context_instance=RequestContext(request))
  except DeadlineExceededError:
    logging.exception('DeadlineExceededError')
    return HttpResponse('DeadlineExceededError', status=503)
  except CapabilityDisabledError, err:
    logging.exception('CapabilityDisabledError: %s', err)
    return HttpResponse('App Engine is undergoing maintenance. '
                        'Please try again in a while. ' + str(err),
                        status=503)
  except MemoryError:
    logging.exception('MemoryError')
    return HttpResponse('MemoryError', status=503)
  except AssertionError:
    logging.exception('AssertionError')
    return HttpResponse('AssertionError', status=503)

################################################################
# Forms and Widgets
################################################################
class PictouError(AttributeError):
  pass

class AutocompleteWidget(forms.TextInput):
  def __init__(self, *args, **kwds):
    self.actions = kwds.pop('actions', ['search', 'create', 'edit'])
    self.url = kwds['attrs']['url']
    super(AutocompleteWidget,self).__init__(*args, **kwds)
  def render(self, name, value, attrs={}):
    attrs['class'] = 'autocomplete'
    return loader.render_to_string('pictou/autocomplete.tpl', {'key': value, 'url': self.url,
                                                               'actions': self.actions,
                                                               'textfield': super(AutocompleteWidget,self).render(name, value, attrs)})

class AutocompleteField(forms.CharField):
  def __init__(self, url, **kwds):
    super(AutocompleteField,self).__init__(widget=AutocompleteWidget(attrs={'class':'autocomplete', 'size': 80, 'url':url}), **kwds)
  def clean(self, value):
    if not value:
      value = None
    result = super(AutocompleteField,self).clean(value)
    return result or None

class MiniformWidget(forms.Textarea):
  def render(self, name, value, attrs=None):
    if not value: keys = []
    elif not isinstance(value, list): keys = [value]
    elif value[0] is None: keys = []
    else:
      try:
        keys = [str(v.key()) for v in value]
      except AttributeError:
        raise PictouError("Miniform key mismatch; check that the model type matches that of the view; check that keys are being cleaned by a field to convert to objects; see widgets form field.")
    return super(MiniformWidget,self).render(name, "\n".join(keys), attrs)

class MiniformField(forms.CharField):
  def __init__(self, Model, url, **kwds):
    self.Model = Model
    super(MiniformField,self).__init__(widget=MiniformWidget(attrs={'class':'miniform', 'url':url}), **kwds)
  def clean(self, value):
    """ extending the clean method to work with GAE keys """
    value = value.strip()
    if (value): keys = value.strip().split("\n")
    else: keys = []
    return [self.Model.get(key.strip()) for key in keys]

class RateWidget(forms.TextInput):
  def __init__(self, *args, **kwds):
    kwds.setdefault('attrs', {})
    kwds['attrs'].setdefault('size', 5)
    super(RateWidget,self).__init__(*args, **kwds)
  def render(self, name, value, attrs=None):
    value = "%.2f" % (float(value),) if value else None
    return super(RateWidget, self).render(name, value, attrs)

def reference_list_choice(model):
  class ReferenceListChoice(forms.MultipleChoiceField):
    def clean(self, value):
      """ extending the clean method to work with GAE keys """
      return [model.get(k) for k in super(ReferenceListChoice, self).clean(value)]
  return ReferenceListChoice
################################################################
# Handlers
################################################################

class BaseHandlerFactory(object):
  def __init__(self, *args, **kwds):
    self.params = {'title': None,
                   'form': None,
                   'model': None,
                   'url': None,
                   'search_fields': (),
                   'autofill_in_miniform': False,
                   'miniform_template': 'pictou/miniform.tpl',
                   }
    if kwds:
      self.params.update(kwds)
    self.Model = self.params['model']
    self.Form = self.params['form']
    self.templates = {'show': 'show.tpl'}
    self.templates.update(self.params.get('templates', {}))
  @property
  def url(self): return self.params['url'] # reverse(self.handle)
  def redirect(self, url=None): return HttpResponseRedirect(url or self.url)
  def ajax(self): return self.REQUEST.get('ajax') # TODO: Figure out right way to detect AJAX call
  def json(self): return self.REQUEST.get('json') # TODO: Figure out right way to detect AJAX call

def _verbose_name(prop):
  return getattr(prop, 'verbose_name', None) or ' '.join(str(getattr(prop, 'name', prop)).split('_')).capitalize()

class HandlerFactory(BaseHandlerFactory):
  def handle_hook(self): pass
  # (1)  Ask the model its properties
  # (2)  Get an appropriate widget for that property
  def extra(self):
    search_fields = [{'name': x,
                      'label': _verbose_name(getattr(self.Model, x, x)),
                      'value': self.REQUEST.get(x, ""),
                      'widget': widget and widget.render(x, self.REQUEST.get(x, "") , {})
                      } for x, widget in (self.params['search_fields'])]
    search_param_string = "".join(["&%s=%s" % (x['name'], x['value']) for x in search_fields if x['value']])
    drafts = draft.models.Draft.all().filter('creator', current_user())
    if drafts:
      drafts = loader.render_to_string('pictou/drafts.tpl',
                                       {'url': '/draft/',
                                        'object_list': draft.models.Draft.all().order('-timestamp'),
                                        'title': 'Drafts',})
    else:
      drafts = ''
    return template_params(self.request,
                           {'url': self.url,
                            'title': self.params['title'],
                            'ajax': self.REQUEST.get('ajax', False),
                            'creatable': self.Model.creatable() and has_permission(self.Model.__name__, 'create'),
                            'search_fields': search_fields,
                            'search_param_string': search_param_string,
                            'list_drafts': drafts,
                            })
  def handlers(self):
    return {'index': {'handler': self.index, 'permission': 'view'},
            'show': {'handler': self.show, 'permission': 'view'},
            'create': {'handler': self.create, 'permission': 'create'},
            'edit': {'handler': self.edit, 'permission': 'edit'},
            'delete': {'handler': self.delete, 'permission': 'delete'},
            'search': {'handler': self.search, 'permission': 'view'},
            'cancel': {'handler': self.cancel, 'permission': 'view'},
            
            # To support autocompletion
            'get': {'handler': self.get_by_key, 'permission': 'view'},
            'autocomplete': {'handler': self.autocomplete, 'permission': 'view'},
            
            # Miniforms
            'miniform': {'handler': self.miniform, 'permission': 'view'},
            'miniform_row': {'handler': self.miniform_row, 'permission': 'view'},
            'miniform_create': {'handler': self.addedit, 'permission': 'create'},
            'miniform_edit': {'handler': self.addedit, 'permission': 'edit'},
            'miniform_search': {'handler': self.search_select, 'permission': 'view'},
            }
  def handle(self, request, return_false_on_error = False):
    self.request = request
    self.REQUEST = request.REQUEST
    self.handle_hook()
    handlers = self.handlers()
    action = self.REQUEST.get('cancel_button', None) and 'cancel' or self.REQUEST.get('action', 'index')
    pair = handlers.get(action, handlers.get('index'))
    model = self.Model.__name__
    if not has_permission(model, pair['permission']):
      return HttpResponse('Unauthorized access; attempt to %s a %s' % (action, model), status=401)
    return pair['handler']()

  def cancel(self): return self.redirect()

  def addedit(self, form_class=None):
    if form_class is None: form_class = self.Form
    extra = self.extra()
    extra['ajax'] = True
    key = (self.REQUEST.get('action') != 'miniform_create') and self.REQUEST.get('key') or None # Key could be the value 'None'
    if key: response = update_object(self.request, object_id=key,
                                     form_class=form_class, post_save_redirect=self.url,
                                     extra_context=extra, template_name='form.tpl')
    else: response = create_object(self.request, form_class=form_class, post_save_redirect=self.url,
                                   extra_context=extra, template_name='form.tpl')
    if isinstance(response, HttpResponseRedirect):
      from norex.db import last_model_saved
      return self.miniform_row(last_model_saved)
    else: return response

  def index(self, template_name='list.tpl', order="search_string", query=None):
    if query is None: query = self.Model.all()
    return object_list(self.request, query.order(order), paginate_by=8,
                       extra_context= self.extra(), template_name=template_name)

  def show(self):
    return object_detail(self.request, self.Model.all(), self.REQUEST.get('key'),
                         extra_context= self.extra(), template_name=self.templates['show'])

  def create(self):
    return create_object(self.request, form_class=self.Form, post_save_redirect=self.url,
                         extra_context= self.extra(), template_name='form.tpl')
  

  def edit(self, template_name='form.tpl'):
    return update_object(self.request, object_id=self.REQUEST.get('key'),
                         form_class=self.Form, post_save_redirect=self.url,
                         extra_context= self.extra(), template_name=template_name)


  def delete(self):
    return delete_object(self.request, self.Model, object_id=self.REQUEST.get('key'),
                         post_delete_redirect=self.url, extra_context= self.extra(),
                         template_name='confirm_delete.tpl')

  def get_by_key(self):
    key = self.REQUEST.get('key')
    return HttpResponse(self.Model.get(key), status=200) # TODO (Wolfe) Use JSONResponse in appenginepatch/ragendja/json.py

  def autocomplete(self):
    prefix = self.REQUEST.get("autocomplete_parameter")
    if (prefix):
      results = (self.Model.filter_prefix("search_string", prefix.upper())
                 .order('search_string').fetch(10))
    else:
      results = []
    data = [{'id': str(x.key()), 'value': x.str_search_string(), 'str': str(x), 'info': x.str_autocomplete_info()}
            for x in results]
    return JSONResponse({'results': data})
    
  def miniform(self):
    keys = self.REQUEST.get('keys')
    if (keys): results = self.Model.get(keys.split('\n'))
    else: results = []
    form = loader.render_to_string(self.params['miniform_template'],
                           {'object_list': results,
                            'url': self.url,
                            'title': self.params['title'],
                            'autofill_in_miniform': self.params['autofill_in_miniform'],
                            'miniform_searchable': self.Model.miniform_searchable(),
                            })
    data = [{'id': str(x.key()), 'value': x.str_search_string(), 'str': str(x), 'info': x.str_autocomplete_info()}
            for x in results]
    return JSONResponse({'object_list': data, 'form': form})

  def miniform_row(self, obj=None):
    # This method, called from addedit, yields an AJAX response to replace either miniform or autofill data.
    # This duel role is, perhaps, ill-advised.
    key = self.REQUEST.get('key')
    if (obj == None):
      if (key): x = self.Model.get(self.REQUEST.get('key'))
      else: x = self.Model()
    else: x = obj
    data = {'id': str(x.key()), 'value': x.str_search_string(), 'str': str(x),
            'info': x.str_autocomplete_info(), 'old_key': key}
    form = loader.render_to_string('pictou/miniform-row.tpl', {'object': x, 'url': self.url})
    return JSONResponse({'action': 'replace_data', 'object': data, 'form': form})

  def search_select(self, template_name='autocomplete_list.tpl', order="search_string"):
    return self.search(template_name=template_name, order=order)

  def search(self, template_name='list.tpl', order="search_string"):
    "Field requests to filter results before presenting them."
    query = self.Model.all()
    ranges = 0
    # If one field is specified, do prefix search, otherwise do exact match
    for fieldname, widget in self.params['search_fields']:
      field = self.REQUEST.get(fieldname)
      if field:
        query = query.filter(fieldname, field)
        range = self.Model.filter_prefix (fieldname, field)
        ranges += 1
    if 1==ranges: query = range
    else: query = query.order(order)
    response = object_list(self.request,
                           query, paginate_by=8,
                           extra_context=self.extra(),
                           template_name=template_name)
    if (self.json()):
      return JSONResponse({'action': 'replace_facebox', 'content': response.content})
    return response
