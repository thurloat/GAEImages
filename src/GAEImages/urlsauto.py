from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^fupload/', include('flashdrawing.urls')),
)
