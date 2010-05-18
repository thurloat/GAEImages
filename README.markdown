## GAEImages - An Image uploading compressor do-hickey for Django App Engine
### Squishes your image down to 1MB through size and quality (in that order)
****

### Destructions as follows

#### In settings.py
        INSTALLED_APPS = (
            ...
            'GAEImages',
            ...
        )

#### In models.py

        from GAEImages.properties import ReferenceListProperty
        
        class ThingThatNeedsImages(db.model):
        	mahimagez = ReferenceListProperty(FlashImage)



#### In your views.py

        from flashdrawing.views import FlashDrawingWidget, FlashDrawingField
        
        class Woot(Form):
        	mahimagez = FlashDrawingField(widget=FlashDrawingWidget)
        	class Meta:
        		model = models.ThingThatNeedsImages

****
Now you'll have some images all up in your app. They're stored in each model as the key, 
which after the compression and upload to /fupload gets sent back to the client and stored in a list.

everything is handled for you. for more custom implementations, take a walk through the code and it's
pretty self-explainitory.

##### any questions: email thurloat at gmail dot com

goot luck!