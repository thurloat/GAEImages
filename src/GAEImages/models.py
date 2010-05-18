from google.appengine.ext import db

class FlashImage(db.Model):
    url = '/fupload/'
    uploaded_data = db.BlobProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    comment = db.TextProperty()
    title = db.StringProperty()
    filename = db.StringProperty(default = "uploaded_image.png")
    
    def __unicode__(self): return str(self.filename)
    
    def get_embed(self): return u"<img src='/fupload/%s' />" % (self.key()) 
    
    def get_link(self): return u"<a href='/fupload/%s'>%s</a>" % (self.key(),self.filename)
    
    def deletable(self): return False;
