from django.contrib import admin
from django.urls import path
from topology.views import (
    host_metrics_view,
    router_ports_view,
    ssh_session_create_view,
    topology_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/host-metrics/", host_metrics_view),
    path("api/router-ports/", router_ports_view),
    path("api/ssh/session/", ssh_session_create_view),
    path("api/topology/", topology_view),
]
