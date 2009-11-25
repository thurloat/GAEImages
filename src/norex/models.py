from google.appengine.ext import db

class Audit(db.Expando):
  user = db.UserProperty()
  action = db.StringProperty()
  timestamp = db.DateTimeProperty(None,True)
  xml = db.TextProperty()
  @classmethod
  def display(cls):
    return cls.all().order('-timestamp').fetch(10)
  def __unicode__(self):
    return "%s: %s %s %s..." % (self.user, self.action, self.timestamp.strftime("%x %X"), self.xml[0:60])
  @classmethod
  def creatable(cls): return False
