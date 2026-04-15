from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .current_state import read_snapshot
from .influx import query_chart_history
from .snapshot import build_topology_snapshot
from .ssh_gateway import session_manager
from django.conf import settings


def ssh_device_registry() -> dict:
    return {
        "router": {"name": "Router", "host": settings.ROUTER_IP, "port": 22},
        "switch": {"name": "Switch", "host": settings.SWITCH_IP, "port": 22},
        "laptop": {"name": "Laptop", "host": settings.LAPTOP_IP, "port": 22},
        "server": {"name": "Server", "host": settings.SERVER_IP, "port": 22},
    }


def get_or_build_snapshot() -> dict:
    snapshot = read_snapshot()
    if snapshot is not None:
        return snapshot
    return build_topology_snapshot()


@api_view(["GET"])
def topology_view(request):
    return Response(get_or_build_snapshot())


@api_view(["GET"])
def host_metrics_view(request):
    snapshot = get_or_build_snapshot()
    laptop = snapshot.get("nodes", {}).get("laptop", {})
    return Response({"node": laptop, "host_metrics": laptop.get("host_metrics", {})})


@api_view(["GET"])
def router_ports_view(request):
    snapshot = get_or_build_snapshot()
    router = snapshot.get("nodes", {}).get("router", {})
    return Response({"router": router, "physical_ports": router.get("physical_ports", {})})


@api_view(["GET"])
def history_charts_view(request):
    range_minutes = request.query_params.get("range_minutes", "30")
    window = request.query_params.get("window", "1m")
    try:
        parsed_range = max(5, min(24 * 60, int(range_minutes)))
    except ValueError:
        parsed_range = 30
    return Response(query_chart_history(range_minutes=parsed_range, window=window))


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

    return Response(
        {
            "device": {
                "id": device_id,
                "name": device["name"],
                "host": device["host"],
                "port": device["port"],
            },
            "token": token,
            "ws_path": "/ws/ssh/",
        }
    )
