from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .snmp import (
    discover_switch_port_for_laptop,
    fallback_discover_access_port,
    is_link_up,
    poll_device,
    poll_host_metrics,
    poll_link_side,
)

def build_laptop_host_metrics(community: str) -> dict:
    laptop = poll_device(settings.LAPTOP_IP, community)
    laptop["host_metrics"] = poll_host_metrics(
        settings.LAPTOP_IP,
        community,
        wifi_token=getattr(settings, "LAPTOP_WIFI_EXTEND_TOKEN", "wifi_info"),
        gpu_token=getattr(settings, "LAPTOP_GPU_EXTEND_TOKEN", "gpu_info"),
    )
    return laptop

@api_view(["GET"])
def topology_view(request):
    community = settings.SNMP_COMMUNITY

    router = poll_device(settings.ROUTER_IP, community)
    switch = poll_device(settings.SWITCH_IP, community)
    laptop = build_laptop_host_metrics(community)

    router_to_switch_router_side = poll_link_side(
        settings.ROUTER_IP, community, settings.ROUTER_TO_SWITCH_ROUTER_PORT_INDEX
    )
    router_to_switch_switch_side = poll_link_side(
        settings.SWITCH_IP, community, settings.ROUTER_TO_SWITCH_SWITCH_PORT_INDEX
    )

    discovered_port_index = None
    discovery_method = "none"

    if settings.AUTO_DISCOVER_LAPTOP_SWITCH_PORT:
        candidate_port = discover_switch_port_for_laptop(
            settings.SWITCH_IP,
            settings.LAPTOP_IP,
            community,
            settings.SWITCH_UPLINK_PORT_INDEX,
        )
        if candidate_port is not None:
            candidate_side = poll_link_side(settings.SWITCH_IP, community, candidate_port)
            if candidate_side.get("oper_status") == 1:
                discovered_port_index = candidate_port
                discovery_method = "bridge_fdb_mac_lookup"

        if discovered_port_index is None:
            fallback_port = fallback_discover_access_port(
                settings.SWITCH_IP, community, settings.SWITCH_UPLINK_PORT_INDEX
            )
            if fallback_port is not None:
                discovered_port_index = fallback_port
                discovery_method = "traffic_heuristic"

    switch_to_laptop_switch_side = (
        poll_link_side(settings.SWITCH_IP, community, discovered_port_index)
        if discovered_port_index is not None
        else {
            "port_index": None,
            "port_name": None,
            "admin_status": None,
            "admin_status_label": "unknown",
            "oper_status": None,
            "oper_status_label": "unknown",
            "speed_mbps": None,
            "last_change": None,
            "in_octets": None,
            "out_octets": None,
            "in_errors": None,
            "out_errors": None,
        }
    )

    router_switch_up = (
        router["status"] == "up"
        and switch["status"] == "up"
        and is_link_up(router_to_switch_router_side)
        and is_link_up(router_to_switch_switch_side)
    )

    switch_laptop_up = (
        switch["status"] == "up"
        and laptop["status"] == "up"
        and discovered_port_index is not None
        and is_link_up(switch_to_laptop_switch_side)
    )

    return Response({
        "nodes": {
            "router": router,
            "switch": switch,
            "laptop": laptop,
        },
        "links": {
            "router_to_switch": {
                "status": "up" if router_switch_up else "down",
                "router_side": router_to_switch_router_side,
                "switch_side": router_to_switch_switch_side,
            },
            "switch_to_laptop": {
                "status": "up" if switch_laptop_up else "down",
                "switch_side": switch_to_laptop_switch_side,
                "laptop_ip": settings.LAPTOP_IP,
                "discovered_port_index": discovered_port_index,
                "discovery_method": discovery_method,
            },
        },
        "summary": {
            "online_nodes": sum(1 for n in [router, switch, laptop] if n["status"] == "up"),
            "offline_nodes": sum(1 for n in [router, switch, laptop] if n["status"] != "up"),
            "active_links": sum(1 for s in [router_switch_up, switch_laptop_up] if s),
        },
    })

@api_view(["GET"])
def host_metrics_view(request):
    community = settings.SNMP_COMMUNITY
    laptop = build_laptop_host_metrics(community)

    return Response({
        "node": laptop,
        "host_metrics": laptop["host_metrics"],
    })
