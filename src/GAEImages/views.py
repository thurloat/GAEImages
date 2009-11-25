import models
from flashdrawing.models import FlashImage
from django.http import HttpResponse, Http404
from google.appengine.ext import db
from django import forms
from django.template import loader

def upload(request):
    img = FlashImage()
    img.uploaded_data = db.Blob(request.FILES['filedata'].read())
    img.filename = str(request.FILES['filedata'])
    img.put()
    writer = HttpResponse()
    writer.write(img.key())
    return writer
    
def render(request,key):
    image = db.get(key)
    if image and image.uploaded_data:
        response = HttpResponse()
        response['Content-Type'] = 'image/png'
        response.write(image.uploaded_data)
        return response
    else:
        raise Http404('Sorry, I couldnt find that image!')

    
class FlashDrawingWidget(forms.Textarea):
  def render(self, name, value ,*args,**kwds):
    if (value is None): value = []
    keys = [str(v.key()) for v in value]
    return loader.render_to_string('flashdrawing/flashembed.tpl', 
                                   {'name':name,'textfield': super(FlashDrawingWidget,self).render(name, "\n".join(keys), *args,**kwds)})

class FlashDrawingField(forms.CharField):
  def clean(self, value):
    """ extending the clean method to work with GAE keys """
    value = value.strip()
    if (value): keys = value.strip().split("\n")
    else: keys = []
    return [db.get(key.strip()) for key in keys]



class FlashUploadWidget(forms.Textarea):
    def render(self,name,value,*args,**kwargs):
        return loader.render_to_string('flashdrawing/flashembedupload.tpl', 
                                   {'name':name,'textfield': super(FlashDrawingWidget,self).render(name, value, *args,**kwds)})
