from datetime import datetime, timezone

from django.conf import settings

from .current_state import SNAPSHOT_SCHEMA_VERSION, read_snapshot_payload
from .snmp import (
    discover_router_port_for_host,
    discover_router_switch_ports,
    discover_switch_port_for_laptop,
    fallback_discover_access_port,
    is_link_up,
    poll_device,
    poll_host_metrics,
    poll_link_side,
    poll_management_endpoint,
    poll_ping,
    walk_router_physical_interfaces,
    walk_switch_physical_interfaces,
)


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
        "in_rate_mbps": None,
        "out_rate_mbps": None,
        "total_rate_mbps": None,
        "in_errors": None,
        "out_errors": None,
    }


def empty_host_metrics() -> dict:
    return {
        "cpu": {
            "usage_percent": None,
            "load_average": {"1m": None, "5m": None, "15m": None},
        },
        "cpu_error": "Host is down",
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
        "memory_error": "Host is down",
        "disk": [],
        "disk_error": "Host is down",
        "processes": {"count": None},
        "network": None,
        "network_error": "Host is down",
        "wifi": None,
        "wifi_error": "Host is down",
        "gpu": None,
        "gpu_error": "Host is down",
    }


def empty_ping_metrics() -> dict:
    return {
        "sent": None,
        "received": None,
        "packet_loss_percent": None,
        "avg_latency_ms": None,
        "error": "Host is down",
    }


def empty_physical_ports() -> dict:
    return {
        "total_physical_ports": 0,
        "up_physical_ports": 0,
        "down_physical_ports": 0,
        "ports": [],
        "totals": {
            "in_octets": 0,
            "out_octets": 0,
            "in_rate_mbps": None,
            "out_rate_mbps": None,
            "total_rate_mbps": None,
            "in_errors": 0,
            "out_errors": 0,
            "in_discards": 0,
            "out_discards": 0,
        },
    }


def _parse_snapshot_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_rate_mbps(
    current_octets: int | float | None,
    previous_octets: int | float | None,
    elapsed_seconds: float | None,
) -> float | None:
    if elapsed_seconds is None or elapsed_seconds <= 0:
        return None
    if current_octets is None or previous_octets is None:
        return None
    try:
        delta = float(current_octets) - float(previous_octets)
    except (TypeError, ValueError):
        return None
    if delta < 0:
        return None
    return round((delta * 8) / elapsed_seconds / 1_000_000, 3)


def _annotate_side_rates(
    current_side: dict | None,
    previous_side: dict | None,
    elapsed_seconds: float | None,
) -> dict:
    side = dict(current_side or empty_link_side())
    side["in_rate_mbps"] = _compute_rate_mbps(
        side.get("in_octets"),
        (previous_side or {}).get("in_octets"),
        elapsed_seconds,
    )
    side["out_rate_mbps"] = _compute_rate_mbps(
        side.get("out_octets"),
        (previous_side or {}).get("out_octets"),
        elapsed_seconds,
    )
    if side["in_rate_mbps"] is None and side["out_rate_mbps"] is None:
        side["total_rate_mbps"] = None
    else:
        side["total_rate_mbps"] = round(
            (side["in_rate_mbps"] or 0) + (side["out_rate_mbps"] or 0),
            3,
        )
    return side


def _annotate_physical_port_rates(
    current_ports: dict,
    previous_ports: dict | None,
    elapsed_seconds: float | None,
) -> dict:
    previous_by_index = {
        port.get("port_index"): port
        for port in (previous_ports or {}).get("ports", [])
        if port.get("port_index") is not None
    }
    annotated_ports = []

    for port in current_ports.get("ports", []):
        previous_port = previous_by_index.get(port.get("port_index"))
        annotated_port = dict(port)
        annotated_port["in_rate_mbps"] = _compute_rate_mbps(
            annotated_port.get("in_octets"),
            (previous_port or {}).get("in_octets"),
            elapsed_seconds,
        )
        annotated_port["out_rate_mbps"] = _compute_rate_mbps(
            annotated_port.get("out_octets"),
            (previous_port or {}).get("out_octets"),
            elapsed_seconds,
        )
        if (
            annotated_port["in_rate_mbps"] is None
            and annotated_port["out_rate_mbps"] is None
        ):
            annotated_port["total_rate_mbps"] = None
        else:
            annotated_port["total_rate_mbps"] = round(
                (annotated_port["in_rate_mbps"] or 0)
                + (annotated_port["out_rate_mbps"] or 0),
                3,
            )
        annotated_ports.append(annotated_port)

    totals = dict(current_ports.get("totals", {}))
    in_total = [
        port["in_rate_mbps"]
        for port in annotated_ports
        if port.get("in_rate_mbps") is not None
    ]
    out_total = [
        port["out_rate_mbps"]
        for port in annotated_ports
        if port.get("out_rate_mbps") is not None
    ]
    totals["in_rate_mbps"] = round(sum(in_total), 3) if in_total else None
    totals["out_rate_mbps"] = round(sum(out_total), 3) if out_total else None
    if totals["in_rate_mbps"] is None and totals["out_rate_mbps"] is None:
        totals["total_rate_mbps"] = None
    else:
        totals["total_rate_mbps"] = round(
            (totals["in_rate_mbps"] or 0) + (totals["out_rate_mbps"] or 0),
            3,
        )

    annotated = dict(current_ports)
    annotated["ports"] = annotated_ports
    annotated["totals"] = totals
    return annotated


def build_host_node(
    ip: str,
    community: str,
    wifi_token: str | None = None,
    gpu_token: str | None = None,
    server_metrics_token: str | None = None,
    include_optional_metric_errors: bool = True,
) -> dict:
    host = poll_device(ip, community)
    if host["status"] != "up":
        host["host_metrics"] = empty_host_metrics()
        host["ping"] = empty_ping_metrics()
        return host

    host["host_metrics"] = poll_host_metrics(
        ip,
        community,
        wifi_token=wifi_token,
        gpu_token=gpu_token,
        server_metrics_token=server_metrics_token,
        include_optional_metric_errors=include_optional_metric_errors,
    )
    host["ping"] = poll_ping(ip)
    return host


def build_network_device_node(
    ip: str,
    community: str,
    *,
    physical_port_walker,
    include_optional_metric_errors: bool = False,
) -> dict:
    device = poll_device(ip, community)
    if device["status"] != "up":
        device["host_metrics"] = empty_host_metrics()
        device["ping"] = empty_ping_metrics()
        device["physical_ports"] = empty_physical_ports()
        return device

    device["host_metrics"] = poll_host_metrics(
        ip,
        community,
        include_optional_metric_errors=include_optional_metric_errors,
    )
    device["ping"] = poll_ping(ip)
    device["physical_ports"] = physical_port_walker(ip, community)
    return device


def _ping_reachable(ping: dict) -> bool:
    received = ping.get("received")
    if received is None:
        return False
    try:
        return int(received) > 0
    except (TypeError, ValueError):
        return False


def build_router_uplink(
    role: str,
    ip: str,
    gateway_ip: str | None,
    community: str,
) -> dict:
    probe = poll_management_endpoint(ip, community)
    ping = poll_ping(ip)
    gateway_ping = poll_ping(gateway_ip) if gateway_ip else empty_ping_metrics()
    management_up = probe.get("status") == "up"
    router_reachability_up = management_up or _ping_reachable(ping)
    gateway_up = _ping_reachable(gateway_ping) if gateway_ip else True
    link_up = management_up and gateway_up

    return {
        "role": role,
        "name": f"{role.title()} link",
        "ip": ip,
        "gateway_ip": gateway_ip,
        "status": "up" if link_up else "down",
        "management_status": "up" if management_up else "down",
        "reachability_status": "up" if router_reachability_up else "down",
        "gateway_status": "up" if gateway_up else "down",
        "active": False,
        "device_name": probe.get("name"),
        "error": probe.get("error"),
        "ping": ping,
        "gateway_ping": gateway_ping,
    }


def select_router_uplink(primary: dict, secondary: dict) -> tuple[dict, dict]:
    if primary.get("status") == "up":
        return primary, {
            "active": "primary",
            "active_ip": primary.get("ip"),
            "active_gateway_ip": primary.get("gateway_ip"),
            "state": "primary_active",
            "reason": "Primary router WAN and gateway are reachable.",
        }

    if secondary.get("status") == "up":
        return secondary, {
            "active": "secondary",
            "active_ip": secondary.get("ip"),
            "active_gateway_ip": secondary.get("gateway_ip"),
            "state": "secondary_handover",
            "reason": "Primary link is down; secondary router WAN and gateway have taken handover.",
        }

    return primary, {
        "active": None,
        "active_ip": None,
        "active_gateway_ip": None,
        "state": "all_links_down",
        "reason": "Primary and secondary router WAN or gateway checks are down.",
    }


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
        server_metrics_token=getattr(
            settings, "SERVER_METRICS_EXTEND_TOKEN", "server_metrics"
        ),
        include_optional_metric_errors=False,
    )


def build_topology_snapshot() -> dict:
    community = settings.SNMP_COMMUNITY
    previous_payload = read_snapshot_payload() or {}
    previous_snapshot = (
        previous_payload.get("snapshot")
        if previous_payload.get("schema_version") == SNAPSHOT_SCHEMA_VERSION
        else None
    )
    previous_captured_at = _parse_snapshot_time(previous_payload.get("captured_at"))
    now = datetime.now(timezone.utc)
    elapsed_seconds = (
        (now - previous_captured_at).total_seconds()
        if previous_captured_at is not None
        else None
    )

    primary_router_link = build_router_uplink(
        "primary",
        settings.ROUTER_PRIMARY_LINK_IP,
        getattr(settings, "ROUTER_PRIMARY_GATEWAY_IP", None),
        community,
    )
    secondary_router_link = build_router_uplink(
        "secondary",
        settings.ROUTER_SECONDARY_LINK_IP,
        getattr(settings, "ROUTER_SECONDARY_GATEWAY_IP", None),
        community,
    )
    active_router_link, handover = select_router_uplink(
        primary_router_link,
        secondary_router_link,
    )
    active_router_ip = active_router_link.get("ip") or settings.ROUTER_PRIMARY_LINK_IP
    primary_router_link["active"] = handover.get("active") == "primary"
    secondary_router_link["active"] = handover.get("active") == "secondary"

    router = build_network_device_node(
        active_router_ip,
        community,
        physical_port_walker=walk_router_physical_interfaces,
    )
    router["management"] = {
        "active_link": handover.get("active"),
        "active_ip": handover.get("active_ip"),
        "active_gateway_ip": handover.get("active_gateway_ip"),
        "primary_ip": primary_router_link.get("ip"),
        "primary_gateway_ip": primary_router_link.get("gateway_ip"),
        "secondary_ip": secondary_router_link.get("ip"),
        "secondary_gateway_ip": secondary_router_link.get("gateway_ip"),
        "handover_state": handover.get("state"),
        "handover_reason": handover.get("reason"),
    }
    switch = build_network_device_node(
        settings.SWITCH_IP,
        community,
        physical_port_walker=walk_switch_physical_interfaces,
    )
    laptop = build_laptop_host_metrics(community)
    server = build_server_host_metrics(community)

    router["physical_ports"] = _annotate_physical_port_rates(
        router.get("physical_ports", empty_physical_ports()),
        (previous_snapshot or {}).get("nodes", {}).get("router", {}).get("physical_ports"),
        elapsed_seconds,
    )
    switch["physical_ports"] = _annotate_physical_port_rates(
        switch.get("physical_ports", empty_physical_ports()),
        (previous_snapshot or {}).get("nodes", {}).get("switch", {}).get("physical_ports"),
        elapsed_seconds,
    )

    router_switch_discovery = (
        discover_router_switch_ports(
            active_router_ip,
            settings.SWITCH_IP,
            community,
            router_name=router.get("name"),
            switch_name=switch.get("name"),
            configured_router_port_index=settings.ROUTER_TO_SWITCH_ROUTER_PORT_INDEX,
            configured_switch_port_index=settings.ROUTER_TO_SWITCH_SWITCH_PORT_INDEX,
        )
        if router["status"] == "up" and switch["status"] == "up"
        else {
            "router_port_index": None,
            "switch_port_index": None,
            "router_port_method": "none",
            "switch_port_method": "none",
            "discovery_method": "none",
            "discovery_detail": "router:none switch:none",
        }
    )

    router_to_switch_router_index = router_switch_discovery.get("router_port_index")
    router_to_switch_switch_index = router_switch_discovery.get("switch_port_index")
    router_to_switch_router_side = (
        poll_link_side(active_router_ip, community, router_to_switch_router_index)
        if router["status"] == "up" and router_to_switch_router_index is not None
        else empty_link_side()
    )
    router_to_switch_switch_side = (
        poll_link_side(settings.SWITCH_IP, community, router_to_switch_switch_index)
        if switch["status"] == "up" and router_to_switch_switch_index is not None
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
            active_router_ip,
            settings.SERVER_IP,
            community,
        )

    router_to_server_router_side = (
        poll_link_side(active_router_ip, community, router_to_server_port_index)
        if router["status"] == "up" and router_to_server_port_index is not None
        else empty_link_side()
    )

    previous_links = (previous_snapshot or {}).get("links", {})
    router_to_switch_router_side = _annotate_side_rates(
        router_to_switch_router_side,
        previous_links.get("router_to_switch", {}).get("router_side"),
        elapsed_seconds,
    )
    router_to_switch_switch_side = _annotate_side_rates(
        router_to_switch_switch_side,
        previous_links.get("router_to_switch", {}).get("switch_side"),
        elapsed_seconds,
    )
    switch_to_laptop_switch_side = _annotate_side_rates(
        switch_to_laptop_switch_side,
        previous_links.get("switch_to_laptop", {}).get("switch_side"),
        elapsed_seconds,
    )
    router_to_server_router_side = _annotate_side_rates(
        router_to_server_router_side,
        previous_links.get("router_to_server", {}).get("router_side"),
        elapsed_seconds,
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

    return {
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
                "discovered_router_port_index": router_to_switch_router_index,
                "discovered_switch_port_index": router_to_switch_switch_index,
                "discovery_method": router_switch_discovery.get("discovery_method"),
                "discovery_detail": router_switch_discovery.get("discovery_detail"),
                "router_port_method": router_switch_discovery.get(
                    "router_port_method"
                ),
                "switch_port_method": router_switch_discovery.get(
                    "switch_port_method"
                ),
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
            "primary_router_link": {
                "status": primary_router_link["status"],
                "ip": primary_router_link["ip"],
                "gateway_ip": primary_router_link["gateway_ip"],
                "active": primary_router_link["active"],
                "management_status": primary_router_link["management_status"],
                "reachability_status": primary_router_link["reachability_status"],
                "gateway_status": primary_router_link["gateway_status"],
            },
            "secondary_router_link": {
                "status": secondary_router_link["status"],
                "ip": secondary_router_link["ip"],
                "gateway_ip": secondary_router_link["gateway_ip"],
                "active": secondary_router_link["active"],
                "management_status": secondary_router_link["management_status"],
                "reachability_status": secondary_router_link["reachability_status"],
                "gateway_status": secondary_router_link["gateway_status"],
            },
        },
        "uplinks": {
            "primary": primary_router_link,
            "secondary": secondary_router_link,
            "handover": handover,
        },
        "summary": {
            "online_nodes": sum(1 for n in [router, switch, laptop, server] if n["status"] == "up"),
            "offline_nodes": sum(1 for n in [router, switch, laptop, server] if n["status"] != "up"),
            "active_links": sum(1 for s in [router_switch_up, switch_laptop_up, router_server_up] if s),
            "active_uplink": handover.get("active"),
            "active_uplink_ip": handover.get("active_ip"),
            "uplinks_online": sum(
                1
                for uplink in [primary_router_link, secondary_router_link]
                if uplink.get("status") == "up"
            ),
        },
    }
