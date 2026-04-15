import json
from datetime import datetime, timezone

from django.conf import settings

SNAPSHOT_SCHEMA_VERSION = 4


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
