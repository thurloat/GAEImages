# Modules will import *, so be careful of naming

import os
import re

SITE_ROOT = os.path.dirname(__file__)

import datetime as dt
_counter=0
def unique_key_name():
  global _counter
  _counter+=1
  return "k" + str(dt.datetime.now()) + "n" + str(_counter)

def pathto(filename):
  return os.path.join(SITE_ROOT, filename)

def info(object, spacing=10, collapse=1): 
  """Print methods and doc strings. 
  Takes module, class, list, dictionary, or string.""" 
  # method_list = [method for method in dir(object) if callable(getattr(object, method))] 
  # method_list = [method for method in dir(object) if not re.match("^__.*__$",method) and callable(getattr(object, method))]
  method_list = [method for method in dir(object) if not re.match("^__.*__$",method)]
  process_func = collapse and (lambda s: " ".join(s.split())) or (lambda s: s)
  print "\n".join(["%s %s" % 
                   (method.ljust(spacing), process_func(str(getattr(object, method).__doc__))) 
                   for method in method_list])

def add_one_year(date):
  m = date.month
  d = date.day
  y = date.year
  if m == 2 and d == 28:
    m = 3
    d = 1
  return dt.date(y+1,m,d)

def identity(x, *args, **kwds): return x

################################################################
# Memoize
################################################################
from google.appengine.api import memcache as the_memcache
import md5
cache = {}
def do_md5(str):
  return md5.new(str).digest()
function = type(do_md5)
def memoize(keyformat, memcache=False, single_request_cache=False, time=5):
  def decorator(fxn):
    def wrapper(*args, **kwargs):
      global cache
      if isinstance(keyformat, str):
        key = do_md5(keyformat % args[0:keyformat.count('%')])
      elif isinstance(keyformat, function):
        key = do_md5(function(*args, **kwargs))
      else:
        raise TypeError("Memoize keyformat must be a function or string")
      if single_request_cache and (key in cache): return cache[key]
      data = the_memcache.get(key) if memcache else None
      if data is not None:
        if single_request_cache: cache[key] = data
        return data
      data = fxn(*args, **kwargs)
      if memcache: the_memcache.set(key, data, time)
      if single_request_cache: cache[key] = data
      return data
    return wrapper
  return decorator
################################################################
class ClearSingleRequestCacheMiddleware(object):
  def process_request(self, request):
    global cache
    cache = {}
    return None
################
# End of Memoize
################

def unique(s):
  """Return a list of the elements in s, but without duplicates.

  Order of results is not guaranteed.

  For best speed, all sequence elements should be hashable.
  Next tries sort.  Then brute-force pairwise equality testing.
  """

  n = len(s)
  if n == 0:
    return []

  u = {}
  try:
    for x in s:
      u[x] = 1
  except TypeError:
    del u  # move on to the next method
  else:
    return u.keys()

  try:
    t = list(s)
    t.sort()
  except TypeError:
    del t  # move on to the next method
  else:
    assert n > 0
    last = t[0]
    lasti = i = 1
    while i < n:
      if t[i] != last:
        t[lasti] = last = t[i]
        lasti += 1
      i += 1
    return t[:lasti]

  # Brute force is all that's left.
  u = []
  for x in s:
    if x not in u:
      u.append(x)
  return u
