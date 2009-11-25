from authorization.models import users_to_emulate, current_user
from google.appengine.api import users
import os


def auth(request):
  return {
    'request': request,
    'user': current_user(),
    'draft_id': getattr(request, 'draft_id', None),
    'is_dev': os.environ['SERVER_SOFTWARE'].startswith('Dev'),  # Development server
    'logout_url': users.create_logout_url('/'),
    'users_to_emulate': users_to_emulate(),
    }
