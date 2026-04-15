import csv
import io
import json
from datetime import datetime, timezone
from urllib import error, parse, request

from django.conf import settings


def influx_enabled() -> bool:
    return bool(
        getattr(settings, "INFLUXDB_URL", "")
        and getattr(settings, "INFLUXDB_TOKEN", "")
        and getattr(settings, "INFLUXDB_ORG", "")
        and getattr(settings, "INFLUXDB_BUCKET", "")
    )


def _headers(content_type: str) -> dict:
    return {
        "Authorization": f"Token {settings.INFLUXDB_TOKEN}",
        "Content-Type": content_type,
        "Accept": "application/csv",
    }


def _request(url: str, data: bytes, content_type: str) -> str:
    req = request.Request(url, data=data, headers=_headers(content_type), method="POST")
    with request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8")


def _escape_tag(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def _field_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value}i"
    if isinstance(value, float):
        return json.dumps(value)
    return json.dumps(str(value))


def write_snapshot_metrics(snapshot: dict) -> None:
    if not influx_enabled():
        return

    timestamp = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
    lines = []
    for device, node in snapshot.get("nodes", {}).items():
        metrics = node.get("host_metrics", {})
        fields = {
            "online": 1 if node.get("status") == "up" else 0,
            "cpu_usage": metrics.get("cpu", {}).get("usage_percent"),
            "memory_usage": metrics.get("memory", {}).get("usage_percent"),
            "memory_used_mb": metrics.get("memory", {}).get("used_mb"),
            "latency_ms": node.get("ping", {}).get("avg_latency_ms"),
            "packet_loss": node.get("ping", {}).get("packet_loss_percent"),
            "process_count": metrics.get("processes", {}).get("count"),
        }
        network = metrics.get("network") or {}
        fields.update(
            {
                "rx_bytes": network.get("rx_bytes"),
                "tx_bytes": network.get("tx_bytes"),
                "rx_packets": network.get("rx_packets"),
                "tx_packets": network.get("tx_packets"),
            }
        )

        encoded_fields = []
        for key, value in fields.items():
            encoded = _field_value(value)
            if encoded is not None:
                encoded_fields.append(f"{key}={encoded}")
        if encoded_fields:
            lines.append(
                f"device_metrics,device={_escape_tag(device)} {','.join(encoded_fields)} {timestamp}"
            )

    for link_name, link in snapshot.get("links", {}).items():
        status = 1 if link.get("status") == "up" else 0
        lines.append(
            f"link_status,link={_escape_tag(link_name)} status={status}i {timestamp}"
        )

    if not lines:
        return

    url = (
        f"{settings.INFLUXDB_URL.rstrip('/')}/api/v2/write?"
        f"org={parse.quote(settings.INFLUXDB_ORG)}&bucket={parse.quote(settings.INFLUXDB_BUCKET)}&precision=ns"
    )
    try:
        _request(url, "\n".join(lines).encode("utf-8"), "text/plain; charset=utf-8")
    except error.URLError:
        return


def query_overview_history(range_minutes: int = 30, window: str = "1m") -> dict:
    if not influx_enabled():
        return {"series": {}}

    flux = f"""
from(bucket: "{settings.INFLUXDB_BUCKET}")
  |> range(start: -{int(range_minutes)}m)
  |> filter(fn: (r) => r._measurement == "device_metrics")
  |> filter(fn: (r) => r._field == "cpu_usage" or r._field == "memory_usage" or r._field == "latency_ms" or r._field == "packet_loss")
  |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
  |> keep(columns: ["_time", "_field", "_value", "device"])
"""

    url = f"{settings.INFLUXDB_URL.rstrip('/')}/api/v2/query?org={parse.quote(settings.INFLUXDB_ORG)}"
    body = json.dumps({"query": flux, "type": "flux"}).encode("utf-8")
    try:
        csv_text = _request(url, body, "application/json")
    except error.URLError:
        return {"series": {}}

    series: dict[str, dict[str, list[dict]]] = {}
    filtered_lines = "\n".join(
        line for line in csv_text.splitlines() if line and not line.startswith("#")
    )
    reader = csv.DictReader(io.StringIO(filtered_lines))
    for row in reader:
        if not row.get("_time") or not row.get("_field") or row.get("_value") in (None, ""):
            continue
        device = row.get("device")
        field = row.get("_field")
        if not device or not field:
            continue
        try:
            value = float(row["_value"])
        except ValueError:
            continue
        series.setdefault(device, {}).setdefault(field, []).append(
            {"time": row["_time"], "value": value}
        )
    return {"series": series}
