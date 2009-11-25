from django.conf.urls.defaults import *

urlpatterns = patterns("flashdrawing.views",
                       (r'^(?P<key>.+)$', 'render'),
                       (r'$', 'upload'),
                       )
