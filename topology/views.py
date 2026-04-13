from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response

from .snmp import (
    discover_router_port_for_host,
    discover_switch_port_for_laptop,
    fallback_discover_access_port,
    is_link_up,
    poll_device,
    poll_host_metrics,
    poll_link_side,
    walk_router_physical_interfaces,
)
from .ssh_gateway import session_manager

def empty_link_side() -> dict:
    return {
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

def empty_host_metrics() -> dict:
    return {
        "cpu": {
            "usage_percent": None,
            "load_average": {
                "1m": None,
                "5m": None,
                "15m": None,
            },
        },
        "memory": {
            "total_mb": None,
            "available_mb": None,
            "used_mb": None,
            "usage_percent": None,
            "swap_total_mb": None,
            "swap_available_mb": None,
            "swap_used_mb": None,
            "swap_usage_percent": None,
        },
        "disk": [],
        "disk_error": "Host is down",
        "processes": {
            "count": None,
        },
        "wifi": None,
        "wifi_error": "Host is down",
        "gpu": None,
        "gpu_error": "Host is down",
    }

def build_host_node(
    ip: str,
    community: str,
    wifi_token: str | None = None,
    gpu_token: str | None = None,
    include_optional_metric_errors: bool = True,
) -> dict:
    host = poll_device(ip, community)
    if host["status"] != "up":
        host["host_metrics"] = empty_host_metrics()
        return host

    host["host_metrics"] = poll_host_metrics(
        ip,
        community,
        wifi_token=wifi_token,
        gpu_token=gpu_token,
        include_optional_metric_errors=include_optional_metric_errors,
    )
    return host

def build_laptop_host_metrics(community: str) -> dict:
    return build_host_node(
        settings.LAPTOP_IP,
        community,
        wifi_token=getattr(settings, "LAPTOP_WIFI_EXTEND_TOKEN", "wifi_info"),
        gpu_token=getattr(settings, "LAPTOP_GPU_EXTEND_TOKEN", "gpu_info"),
    )

def build_server_host_metrics(community: str) -> dict:
    return build_host_node(
        settings.SERVER_IP,
        community,
        include_optional_metric_errors=False,
    )

def ssh_device_registry() -> dict:
    return {
        "router": {"name": "Router", "host": settings.ROUTER_IP, "port": 22},
        "switch": {"name": "Switch", "host": settings.SWITCH_IP, "port": 22},
        "laptop": {"name": "Laptop", "host": settings.LAPTOP_IP, "port": 22},
        "server": {"name": "Server", "host": settings.SERVER_IP, "port": 22},
    }

@api_view(["GET"])
def topology_view(request):
    community = settings.SNMP_COMMUNITY

    router = poll_device(settings.ROUTER_IP, community)
    router["physical_ports"] = (
        walk_router_physical_interfaces(settings.ROUTER_IP, community)
        if router["status"] == "up"
        else {
            "total_physical_ports": 0,
            "up_physical_ports": 0,
            "down_physical_ports": 0,
            "ports": [],
        }
    )
    switch = poll_device(settings.SWITCH_IP, community)
    laptop = build_laptop_host_metrics(community)
    server = build_server_host_metrics(community)

    router_to_switch_router_side = (
        poll_link_side(
            settings.ROUTER_IP, community, settings.ROUTER_TO_SWITCH_ROUTER_PORT_INDEX
        )
        if router["status"] == "up"
        else empty_link_side()
    )
    router_to_switch_switch_side = (
        poll_link_side(
            settings.SWITCH_IP, community, settings.ROUTER_TO_SWITCH_SWITCH_PORT_INDEX
        )
        if switch["status"] == "up"
        else empty_link_side()
    )

    discovered_port_index = None
    discovery_method = "none"

    if (
        settings.AUTO_DISCOVER_LAPTOP_SWITCH_PORT
        and switch["status"] == "up"
        and laptop["status"] == "up"
    ):
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
        if switch["status"] == "up" and discovered_port_index is not None
        else empty_link_side()
    )

    router_to_server_port_index = None
    if (
        getattr(settings, "AUTO_DISCOVER_SERVER_ROUTER_PORT", False)
        and router["status"] == "up"
        and server["status"] == "up"
    ):
        router_to_server_port_index = discover_router_port_for_host(
            settings.ROUTER_IP,
            settings.SERVER_IP,
            community,
        )

    router_to_server_router_side = (
        poll_link_side(settings.ROUTER_IP, community, router_to_server_port_index)
        if router["status"] == "up" and router_to_server_port_index is not None
        else empty_link_side()
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

    router_server_up = (
        router["status"] == "up"
        and server["status"] == "up"
        and router_to_server_port_index is not None
        and is_link_up(router_to_server_router_side)
    )

    return Response({
        "nodes": {
            "router": router,
            "switch": switch,
            "laptop": laptop,
            "server": server,
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
            "router_to_server": {
                "status": "up" if router_server_up else "down",
                "router_side": router_to_server_router_side,
                "server_ip": settings.SERVER_IP,
                "discovered_port_index": router_to_server_port_index,
                "discovery_method": (
                    "router_arp_table" if router_to_server_port_index is not None else "none"
                ),
            },
        },
        "summary": {
            "online_nodes": sum(1 for n in [router, switch, laptop, server] if n["status"] == "up"),
            "offline_nodes": sum(1 for n in [router, switch, laptop, server] if n["status"] != "up"),
            "active_links": sum(1 for s in [router_switch_up, switch_laptop_up, router_server_up] if s),
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

@api_view(["GET"])
def router_ports_view(request):
    community = settings.SNMP_COMMUNITY
    router = poll_device(settings.ROUTER_IP, community)
    physical_ports = (
        walk_router_physical_interfaces(settings.ROUTER_IP, community)
        if router["status"] == "up"
        else {
            "total_physical_ports": 0,
            "up_physical_ports": 0,
            "down_physical_ports": 0,
            "ports": [],
        }
    )

    return Response({
        "router": router,
        "physical_ports": physical_ports,
    })

@api_view(["POST"])
def ssh_session_create_view(request):
    device_id = (request.data.get("device") or "").strip().lower()
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""

    if not device_id or not username or not password:
        return Response(
            {"detail": "device, username, and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    device = ssh_device_registry().get(device_id)
    if not device:
        return Response(
            {"detail": "Unknown device."},
            status=status.HTTP_404_NOT_FOUND,
        )

    token = session_manager.create_pending_session(
        device=device_id,
        host=device["host"],
        port=device["port"],
        username=username,
        password=password,
    )

    return Response({
        "device": {
            "id": device_id,
            "name": device["name"],
            "host": device["host"],
            "port": device["port"],
        },
        "token": token,
        "ws_path": "/ws/ssh/",
    })
