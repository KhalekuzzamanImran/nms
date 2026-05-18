import json
from datetime import datetime, timezone

from django.conf import settings

SNAPSHOT_SCHEMA_VERSION = 6


def snapshot_path():
    return settings.BASE_DIR / "runtime" / "latest_snapshot.json"


def ensure_runtime_dir():
    snapshot_path().parent.mkdir(parents=True, exist_ok=True)


def write_snapshot(snapshot: dict) -> None:
    ensure_runtime_dir()
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": snapshot,
    }
    snapshot_path().write_text(json.dumps(payload), encoding="utf-8")


def read_snapshot_payload() -> dict | None:
    path = snapshot_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def read_snapshot() -> dict | None:
    payload = read_snapshot_payload()
    if not payload:
        return None
    if payload.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return None
    return payload.get("snapshot")


def build_status_payload(snapshot: dict, captured_at: str | None = None) -> dict:
    nodes = snapshot.get("nodes", {})
    links = snapshot.get("links", {})
    uplinks = snapshot.get("uplinks", {})
    return {
        "captured_at": captured_at,
        "nodes": {
            name: {
                "status": node.get("status"),
                "error": node.get("error"),
            }
            for name, node in nodes.items()
        },
        "links": {
            name: {"status": link.get("status")}
            for name, link in links.items()
        },
        "uplinks": {
            "handover": uplinks.get("handover", {}),
            "primary": {
                "status": uplinks.get("primary", {}).get("status"),
                "active": uplinks.get("primary", {}).get("active"),
                "ip": uplinks.get("primary", {}).get("ip"),
                "gateway_ip": uplinks.get("primary", {}).get("gateway_ip"),
                "router_management_ip": uplinks.get("primary", {}).get("router_management_ip"),
                "interface_name": uplinks.get("primary", {}).get("interface_name"),
                "interface_index": uplinks.get("primary", {}).get("interface_index"),
                "interface_status": uplinks.get("primary", {}).get("interface_status"),
                "management_status": uplinks.get("primary", {}).get("management_status"),
                "reachability_status": uplinks.get("primary", {}).get("reachability_status"),
                "gateway_status": uplinks.get("primary", {}).get("gateway_status"),
                "gateway_ping": uplinks.get("primary", {}).get("gateway_ping"),
                "error": uplinks.get("primary", {}).get("error"),
            },
            "secondary": {
                "status": uplinks.get("secondary", {}).get("status"),
                "active": uplinks.get("secondary", {}).get("active"),
                "ip": uplinks.get("secondary", {}).get("ip"),
                "gateway_ip": uplinks.get("secondary", {}).get("gateway_ip"),
                "router_management_ip": uplinks.get("secondary", {}).get("router_management_ip"),
                "interface_name": uplinks.get("secondary", {}).get("interface_name"),
                "interface_index": uplinks.get("secondary", {}).get("interface_index"),
                "interface_status": uplinks.get("secondary", {}).get("interface_status"),
                "management_status": uplinks.get("secondary", {}).get("management_status"),
                "reachability_status": uplinks.get("secondary", {}).get("reachability_status"),
                "gateway_status": uplinks.get("secondary", {}).get("gateway_status"),
                "gateway_ping": uplinks.get("secondary", {}).get("gateway_ping"),
                "error": uplinks.get("secondary", {}).get("error"),
            },
        },
        "summary": snapshot.get("summary", {}),
    }


def read_status_payload() -> dict | None:
    payload = read_snapshot_payload()
    if not payload:
        return None
    return build_status_payload(
        payload.get("snapshot", {}),
        payload.get("captured_at"),
    )
