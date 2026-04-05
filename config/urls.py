from django.contrib import admin
from django.urls import path
from topology.views import topology_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/topology/", topology_view),
]
