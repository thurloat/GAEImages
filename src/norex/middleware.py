import norex.db as db
import datetime as dt

class UseRawModels(object):
  def process_request(self, request):
    db.GaebarModelHook.running_gaebar = request.META['PATH_INFO'][0:8] == '/gaebar/'

  def process_response(self, request, response):
    db.GaebarModelHook.running_gaebar = False
    return response

class BitemporalDate(object):
  def process_request(self, request):
    date = request.REQUEST.get('date', None)
    db._Bitemporal._date = None if date is None else dt.date(*[int(x) for x in date.split('-')])

class ChangePostToGetForForms(object):
  def process_request (self, request):
    if (request.REQUEST.get('action', None) == 'miniform_create'
        and not request.REQUEST.get('submit', None)):
      request.method = 'GET'
