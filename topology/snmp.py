import re
import subprocess
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SNMP_TIMEOUT = "2"
SNMP_RETRIES = "0"
HOST_RESOURCES_STORAGE_TYPES = {
    "1.3.6.1.2.1.25.2.1.3": "virtual_memory",
    "1.3.6.1.2.1.25.2.1.4": "fixed_disk",
    "1.3.6.1.2.1.25.2.1.5": "removable_disk",
    "1.3.6.1.2.1.25.2.1.7": "flash_memory",
}
NS_EXTEND_OUTPUT1_BASE = "1.3.6.1.4.1.8072.1.3.2.3.1.2"
PHYSICAL_INTERFACE_TYPES = {
    6,    # ethernetCsmacd
    62,   # fastEther
    69,   # fastEtherFX
    117,  # gigabitEthernet
}
NON_PHYSICAL_NAME_HINTS = (
    "loopback",
    "vlan",
    "tunnel",
    "null",
    "dialer",
    "bvi",
    "svi",
    "virtual",
)

@dataclass
class SnmpResult:
    ok: bool
    value: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None

def _run(cmd: List[str], timeout: int = 8) -> Tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, result.stdout.strip()

def run_snmpget(ip: str, community: str, oid: str) -> SnmpResult:
    cmd = [
        "snmpget", "-v2c", "-c", community, "-t", SNMP_TIMEOUT, "-r", SNMP_RETRIES, ip, oid
    ]
    ok, output = _run(cmd, timeout=5)
    if not ok:
        return SnmpResult(ok=False, error=output)
    value = output.split(" = ", 1)[-1] if " = " in output else output
    return SnmpResult(ok=True, value=value, raw=output)

def run_snmpwalk(ip: str, community: str, oid: str, numeric: bool = False) -> List[str]:
    cmd = ["snmpwalk"]
    if numeric:
        cmd.append("-On")
    cmd += ["-v2c", "-c", community, "-t", SNMP_TIMEOUT, "-r", SNMP_RETRIES, ip, oid]
    ok, output = _run(cmd, timeout=12)
    if not ok or not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]

def extract_string(snmp_value: Optional[str]) -> Optional[str]:
    if not snmp_value:
        return None
    if ":" in snmp_value:
        head, tail = snmp_value.split(":", 1)
        if "STRING" in head or "OCTET STRING" in head or "octet-string" in head:
            return tail.strip().strip('"')
    return snmp_value.strip().strip('"')

def extract_integer(snmp_value: Optional[str]) -> Optional[int]:
    if not snmp_value:
        return None
    tail = snmp_value.split(":", 1)[1].strip() if ":" in snmp_value else snmp_value.strip()
    match = re.search(r"(-?\d+)", tail)
    return int(match.group(1)) if match else None

def extract_timeticks_text(snmp_value: Optional[str]) -> Optional[str]:
    if not snmp_value:
        return None
    match = re.search(r"\)\s*(.*)$", snmp_value)
    return match.group(1).strip() if match else snmp_value

def extract_float(snmp_value: Optional[str]) -> Optional[float]:
    if not snmp_value:
        return None
    tail = snmp_value.split(":", 1)[1].strip() if ":" in snmp_value else snmp_value.strip()
    match = re.search(r"(-?\d+(?:\.\d+)?)", tail)
    return float(match.group(1)) if match else None

def extract_oid(snmp_value: Optional[str]) -> Optional[str]:
    if not snmp_value:
        return None
    match = re.search(r"((?:\.)?\d+(?:\.\d+)+)", snmp_value)
    if not match:
        return None
    return match.group(1).lstrip(".")

def oper_label(value: Optional[int]) -> str:
    return {
        1: "up",
        2: "down",
        3: "testing",
        4: "unknown",
        5: "dormant",
        6: "notPresent",
        7: "lowerLayerDown",
    }.get(value, "unknown")

def admin_label(value: Optional[int]) -> str:
    return {1: "up", 2: "down", 3: "testing"}.get(value, "unknown")

def is_probably_physical_interface(name: Optional[str], if_type: Optional[int]) -> bool:
    if if_type not in PHYSICAL_INTERFACE_TYPES:
        return False
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return False
    return not any(hint in normalized_name for hint in NON_PHYSICAL_NAME_HINTS)

def poll_device(ip: str, community: str) -> dict:
    name = run_snmpget(ip, community, "1.3.6.1.2.1.1.5.0")
    uptime = run_snmpget(ip, community, "1.3.6.1.2.1.1.3.0")
    descr = run_snmpget(ip, community, "1.3.6.1.2.1.1.1.0")
    return {
        "ip": ip,
        "status": "up" if name.ok else "down",
        "name": extract_string(name.value) if name.ok else None,
        "description": extract_string(descr.value) if descr.ok else None,
        "uptime": extract_timeticks_text(uptime.value) if uptime.ok else None,
        "error": None if name.ok else name.error,
    }

def poll_link_side(ip: str, community: str, port_index: int) -> dict:
    port_name = run_snmpget(ip, community, f"1.3.6.1.2.1.31.1.1.1.1.{port_index}")
    admin = run_snmpget(ip, community, f"1.3.6.1.2.1.2.2.1.7.{port_index}")
    oper = run_snmpget(ip, community, f"1.3.6.1.2.1.2.2.1.8.{port_index}")
    speed = run_snmpget(ip, community, f"1.3.6.1.2.1.31.1.1.1.15.{port_index}")
    last_change = run_snmpget(ip, community, f"1.3.6.1.2.1.2.2.1.9.{port_index}")
    in_octets = run_snmpget(ip, community, f"1.3.6.1.2.1.31.1.1.1.6.{port_index}")
    out_octets = run_snmpget(ip, community, f"1.3.6.1.2.1.31.1.1.1.10.{port_index}")
    in_errors = run_snmpget(ip, community, f"1.3.6.1.2.1.2.2.1.14.{port_index}")
    out_errors = run_snmpget(ip, community, f"1.3.6.1.2.1.2.2.1.20.{port_index}")

    admin_status = extract_integer(admin.value) if admin.ok else None
    oper_status = extract_integer(oper.value) if oper.ok else None

    return {
        "port_index": port_index,
        "port_name": extract_string(port_name.value) if port_name.ok else None,
        "admin_status": admin_status,
        "admin_status_label": admin_label(admin_status),
        "oper_status": oper_status,
        "oper_status_label": oper_label(oper_status),
        "speed_mbps": extract_integer(speed.value) if speed.ok else None,
        "last_change": extract_timeticks_text(last_change.value) if last_change.ok else None,
        "in_octets": extract_integer(in_octets.value) if in_octets.ok else None,
        "out_octets": extract_integer(out_octets.value) if out_octets.ok else None,
        "in_errors": extract_integer(in_errors.value) if in_errors.ok else None,
        "out_errors": extract_integer(out_errors.value) if out_errors.ok else None,
    }

def is_link_up(link_side: dict) -> bool:
    return link_side.get("admin_status") == 1 and link_side.get("oper_status") == 1

def parse_walk_map(lines: List[str]) -> Dict[str, str]:
    result = {}
    for line in lines:
        if " = " not in line:
            continue
        oid, value = line.split(" = ", 1)
        result[oid.strip()] = value.strip()
    return result

def normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").replace(" ", ":").lower()

def walk_suffix_map(ip: str, community: str, oid: str) -> Dict[str, str]:
    prefix = f".{oid}."
    result = {}
    for full_oid, value in parse_walk_map(run_snmpwalk(ip, community, oid, numeric=True)).items():
        if full_oid.startswith(prefix):
            result[full_oid[len(prefix):]] = value
    return result

def safe_snmpwalk_map(ip: str, community: str, oid: str) -> Tuple[Dict[str, str], Optional[str]]:
    lines = run_snmpwalk(ip, community, oid, numeric=True)
    if lines:
        return parse_walk_map(lines), None

    probe = run_snmpget(ip, community, oid)
    if probe.ok:
        return {}, "SNMP subtree returned no rows"
    if probe.error:
        return {}, probe.error
    return {}, "SNMP walk returned no data"

def extend_output_oid(token: str) -> str:
    encoded = ".".join(str(ord(char)) for char in token)
    return f"{NS_EXTEND_OUTPUT1_BASE}.{len(token)}.{encoded}"

def parse_key_value_text(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    text = extract_string(raw) or raw
    pairs = {}
    for chunk in re.split(r"[;,]\s*", text):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        pairs[key.strip()] = value.strip()
    return pairs

def parse_json_text(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    candidates = [raw]
    if '\\"' in raw:
        candidates.append(raw.replace('\\"', '"'))
    try:
        candidates.append(bytes(raw, "utf-8").decode("unicode_escape"))
    except UnicodeDecodeError:
        pass

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

def parse_maybe_number(value: Optional[str]):
    if value is None:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value

def value_to_mac(value: str) -> Optional[str]:
    if not value:
        return None
    if "Hex-STRING:" in value:
        tail = value.split("Hex-STRING:", 1)[1].strip()
        parts = [p.strip().lower() for p in tail.split() if p.strip()]
        if len(parts) == 6:
            return ":".join(p.zfill(2) for p in parts)
    if "STRING:" in value:
        tail = value.split("STRING:", 1)[1].strip().strip('"')
        hex_like = re.findall(r"[0-9A-Fa-f]{2}", tail)
        if len(hex_like) == 6:
            return ":".join(p.lower() for p in hex_like)
    return None

def get_laptop_active_interface(ip: str, community: str) -> Optional[dict]:
    names = walk_suffix_map(ip, community, "1.3.6.1.2.1.31.1.1.1.1")
    oper = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.8")
    macs = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.6")
    candidates = []
    for idx, raw_name in names.items():
        name = extract_string(raw_name)
        oper_value = oper.get(idx)
        oper_num = extract_integer(oper_value) if oper_value else None
        mac_value = macs.get(idx)
        mac = value_to_mac(mac_value) if mac_value else None

        if not name or name == "lo":
            continue
        if oper_num != 1:
            continue
        if not mac or mac == "00:00:00:00:00:00":
            continue
        candidates.append({"if_index": int(idx), "if_name": name, "mac": normalize_mac(mac)})
    return candidates[0] if candidates else None

def discover_router_port_for_host(router_ip: str, host_ip: str, community: str) -> Optional[int]:
    arp_entries = walk_suffix_map(router_ip, community, "1.3.6.1.2.1.4.22.1.2")
    target_suffix = f".{host_ip}"

    for suffix in arp_entries.keys():
        if not suffix.endswith(target_suffix):
            continue
        if_index_text = suffix[: -len(target_suffix)]
        if_index = extract_integer(if_index_text)
        if if_index is not None:
            return if_index
    return None

def discover_switch_port_for_laptop(switch_ip: str, laptop_ip: str, community: str, switch_uplink_port_index: int) -> Optional[int]:
    laptop_iface = get_laptop_active_interface(laptop_ip, community)
    if not laptop_iface:
        return None
    laptop_mac = laptop_iface["mac"]

    base_port_to_ifindex = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.17.1.4.1.2")
    fdb_addr = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.17.4.3.1.1")
    fdb_port = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.17.4.3.1.2")

    suffix_to_mac = {}
    for suffix, value in fdb_addr.items():
        mac = value_to_mac(value)
        if mac:
            suffix_to_mac[suffix] = normalize_mac(mac)

    for suffix, value in fdb_port.items():
        mac = suffix_to_mac.get(suffix)
        if mac != laptop_mac:
            continue
        bridge_port = extract_integer(value)
        if bridge_port is None:
            continue
        if_index = extract_integer(base_port_to_ifindex.get(str(bridge_port)))
        if if_index and if_index != switch_uplink_port_index:
            return if_index
    return None

def fallback_discover_access_port(switch_ip: str, community: str, switch_uplink_port_index: int) -> Optional[int]:
    names = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.1")
    oper = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.2.2.1.8")
    speed = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.15")
    in_octets = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.6")
    out_octets = walk_suffix_map(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.10")

    best_idx = None
    best_score = -1

    for idx_text, raw_name in names.items():
        idx = int(idx_text)
        name = extract_string(raw_name) or ""
        if idx == switch_uplink_port_index or not name.startswith("ether"):
            continue
        oper_num = extract_integer(oper.get(idx_text))
        speed_num = extract_integer(speed.get(idx_text))
        if oper_num != 1 or not speed_num or speed_num <= 0:
            continue
        score = (extract_integer(in_octets.get(idx_text)) or 0) + (extract_integer(out_octets.get(idx_text)) or 0)
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx

def walk_router_physical_interfaces(router_ip: str, community: str) -> dict:
    return walk_physical_interfaces(router_ip, community)

def walk_switch_physical_interfaces(switch_ip: str, community: str) -> dict:
    return walk_physical_interfaces(switch_ip, community)

def walk_physical_interfaces(ip: str, community: str) -> dict:
    names = walk_suffix_map(ip, community, "1.3.6.1.2.1.31.1.1.1.1")
    descriptions = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.2")
    types = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.3")
    admin = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.7")
    oper = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.8")
    speed = walk_suffix_map(ip, community, "1.3.6.1.2.1.31.1.1.1.15")
    last_change = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.9")
    in_octets = walk_suffix_map(ip, community, "1.3.6.1.2.1.31.1.1.1.6")
    out_octets = walk_suffix_map(ip, community, "1.3.6.1.2.1.31.1.1.1.10")
    in_errors = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.14")
    out_errors = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.20")
    in_discards = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.13")
    out_discards = walk_suffix_map(ip, community, "1.3.6.1.2.1.2.2.1.19")

    physical_ports = []
    for index_text, type_value in types.items():
        index = extract_integer(index_text)
        if index is None:
            continue

        port_name = (
            extract_string(names.get(index_text))
            or extract_string(descriptions.get(index_text))
        )
        if_type = extract_integer(type_value)
        if not is_probably_physical_interface(port_name, if_type):
            continue

        admin_status = extract_integer(admin.get(index_text))
        oper_status = extract_integer(oper.get(index_text))
        physical_ports.append({
            "port_index": index,
            "port_name": port_name or f"port-{index}",
            "admin_status": admin_status,
            "admin_status_label": admin_label(admin_status),
            "oper_status": oper_status,
            "oper_status_label": oper_label(oper_status),
            "speed_mbps": extract_integer(speed.get(index_text)),
            "last_change": extract_timeticks_text(last_change.get(index_text)),
            "in_octets": extract_integer(in_octets.get(index_text)),
            "out_octets": extract_integer(out_octets.get(index_text)),
            "in_errors": extract_integer(in_errors.get(index_text)),
            "out_errors": extract_integer(out_errors.get(index_text)),
            "in_discards": extract_integer(in_discards.get(index_text)),
            "out_discards": extract_integer(out_discards.get(index_text)),
        })

    physical_ports.sort(key=lambda port: port["port_index"])
    return {
        "total_physical_ports": len(physical_ports),
        "up_physical_ports": sum(1 for port in physical_ports if port["oper_status"] == 1),
        "down_physical_ports": sum(1 for port in physical_ports if port["oper_status"] != 1),
        "ports": physical_ports,
        "totals": {
            "in_octets": sum(port["in_octets"] or 0 for port in physical_ports),
            "out_octets": sum(port["out_octets"] or 0 for port in physical_ports),
            "in_errors": sum(port["in_errors"] or 0 for port in physical_ports),
            "out_errors": sum(port["out_errors"] or 0 for port in physical_ports),
            "in_discards": sum(port["in_discards"] or 0 for port in physical_ports),
            "out_discards": sum(port["out_discards"] or 0 for port in physical_ports),
        },
    }

def poll_ping(ip: str) -> dict:
    ok, output = _run(["ping", "-c", "4", "-W", "2", ip], timeout=12)
    summary = {
        "sent": None,
        "received": None,
        "packet_loss_percent": None,
        "avg_latency_ms": None,
        "error": None,
    }
    if not ok:
        summary["error"] = output or "Ping failed"
        return summary

    packet_match = re.search(
        r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received,.*?(\d+(?:\.\d+)?)%\s+packet loss",
        output,
    )
    if packet_match:
        summary["sent"] = int(packet_match.group(1))
        summary["received"] = int(packet_match.group(2))
        summary["packet_loss_percent"] = float(packet_match.group(3))

    rtt_match = re.search(
        r"(?:rtt|round-trip)\s+min/avg/max(?:/mdev)?\s*=\s*[\d.]+/([\d.]+)/",
        output,
    )
    if rtt_match:
        summary["avg_latency_ms"] = float(rtt_match.group(1))

    return summary

def poll_disk_usage(ip: str, community: str) -> Tuple[List[dict], Optional[str]]:
    raw_storage_types, storage_type_error = safe_snmpwalk_map(ip, community, "1.3.6.1.2.1.25.2.3.1.2")
    raw_descriptions, _ = safe_snmpwalk_map(ip, community, "1.3.6.1.2.1.25.2.3.1.3")
    raw_allocation_units, _ = safe_snmpwalk_map(ip, community, "1.3.6.1.2.1.25.2.3.1.4")
    raw_sizes, _ = safe_snmpwalk_map(ip, community, "1.3.6.1.2.1.25.2.3.1.5")
    raw_used, _ = safe_snmpwalk_map(ip, community, "1.3.6.1.2.1.25.2.3.1.6")

    prefix_map = {
        "storage_types": "1.3.6.1.2.1.25.2.3.1.2",
        "descriptions": "1.3.6.1.2.1.25.2.3.1.3",
        "allocation_units": "1.3.6.1.2.1.25.2.3.1.4",
        "sizes": "1.3.6.1.2.1.25.2.3.1.5",
        "used": "1.3.6.1.2.1.25.2.3.1.6",
    }

    def to_suffix_map(values: Dict[str, str], base_oid: str) -> Dict[str, str]:
        prefix = f".{base_oid}."
        return {
            key[len(prefix):]: value
            for key, value in values.items()
            if key.startswith(prefix)
        }

    storage_types = to_suffix_map(raw_storage_types, prefix_map["storage_types"])
    descriptions = to_suffix_map(raw_descriptions, prefix_map["descriptions"])
    allocation_units = to_suffix_map(raw_allocation_units, prefix_map["allocation_units"])
    sizes = to_suffix_map(raw_sizes, prefix_map["sizes"])
    used = to_suffix_map(raw_used, prefix_map["used"])

    disks = []
    for index, storage_type in storage_types.items():
        numeric_type = extract_oid(storage_type)
        storage_type_label = HOST_RESOURCES_STORAGE_TYPES.get(numeric_type)
        if storage_type_label is None:
            continue

        mount_name = extract_string(descriptions.get(index)) or f"storage-{index}"
        if mount_name == "Physical memory":
            continue

        unit_bytes = extract_integer(allocation_units.get(index))
        total_units = extract_integer(sizes.get(index))
        used_units = extract_integer(used.get(index))
        if not unit_bytes or total_units is None or used_units is None:
            continue

        total_bytes = unit_bytes * total_units
        used_bytes = unit_bytes * used_units
        disks.append({
            "index": int(index),
            "mount": mount_name,
            "storage_type": storage_type_label,
            "total_bytes": total_bytes,
            "used_bytes": used_bytes,
            "free_bytes": max(total_bytes - used_bytes, 0),
            "usage_percent": round((used_bytes / total_bytes) * 100, 2) if total_bytes else None,
        })

    if disks:
        return disks, None
    if storage_type_error:
        return [], storage_type_error
    return [], "No supported storage entries exposed by HOST-RESOURCES-MIB"

def poll_extend_value(ip: str, community: str, token: str) -> Tuple[Optional[str], Optional[str]]:
    result = run_snmpget(ip, community, extend_output_oid(token))
    if not result.ok:
        return None, result.error
    return extract_string(result.value) or result.value, None

def poll_cpu_usage_percent(ip: str, community: str) -> Optional[float]:
    cpu_idle = extract_integer(run_snmpget(ip, community, "1.3.6.1.4.1.2021.11.11.0").value)
    if cpu_idle is not None:
        return max(0, min(100, 100 - cpu_idle))

    hr_processor_load = extract_integer(
        run_snmpget(ip, community, "1.3.6.1.2.1.25.3.3.1.2.1").value
    )
    if hr_processor_load is not None:
        return max(0, min(100, hr_processor_load))

    return None

def poll_memory_metrics(ip: str, community: str) -> Tuple[Optional[float], Optional[float]]:
    mem_total_kb = extract_integer(run_snmpget(ip, community, "1.3.6.1.4.1.2021.4.5.0").value)
    mem_available_kb = extract_integer(run_snmpget(ip, community, "1.3.6.1.4.1.2021.4.6.0").value)
    if mem_total_kb is not None and mem_available_kb is not None:
        return mem_total_kb / 1024, mem_available_kb / 1024

    hr_total_kb = extract_integer(run_snmpget(ip, community, "1.3.6.1.2.1.25.2.2.0").value)
    hr_alloc_units = extract_integer(
        run_snmpget(ip, community, "1.3.6.1.2.1.25.2.3.1.4.65536").value
    )
    hr_used_units = extract_integer(
        run_snmpget(ip, community, "1.3.6.1.2.1.25.2.3.1.6.65536").value
    )

    if hr_total_kb is None or hr_alloc_units is None or hr_used_units is None:
        return None, None

    used_mb = (hr_alloc_units * hr_used_units) / (1024 * 1024)
    total_mb = hr_total_kb / 1024
    available_mb = max(total_mb - used_mb, 0)
    return total_mb, available_mb

def merge_server_extend_metrics(metrics: dict, extend_data: Optional[dict], token: Optional[str]) -> dict:
    if not token:
        return metrics

    if extend_data is None:
        metrics["cpu_error"] = metrics.get("cpu_error") or (
            f"Server extend token '{token}' returned invalid JSON"
        )
        metrics["memory_error"] = metrics.get("memory_error") or (
            f"Server extend token '{token}' returned invalid JSON"
        )
        metrics["disk_error"] = metrics.get("disk_error") or (
            f"Server extend token '{token}' returned invalid JSON"
        )
        metrics["network_error"] = metrics.get("network_error") or (
            f"Server extend token '{token}' returned invalid JSON"
        )
        return metrics

    cpu = metrics.get("cpu", {})
    memory = metrics.get("memory", {})
    processes = metrics.get("processes", {})
    network = metrics.get("network") or {}

    cpu_usage = extend_data.get("cpu_usage_percent")
    if cpu_usage is not None:
        cpu["usage_percent"] = cpu_usage
        metrics["cpu_error"] = None
    for key in ("1m", "5m", "15m"):
        extend_key = f"load_{key}"
        if extend_data.get(extend_key) is not None:
            cpu.setdefault("load_average", {})[key] = extend_data.get(extend_key)

    if extend_data.get("memory_total_mb") is not None:
        memory["total_mb"] = extend_data.get("memory_total_mb")
        metrics["memory_error"] = None
    if extend_data.get("memory_available_mb") is not None:
        memory["available_mb"] = extend_data.get("memory_available_mb")
    if extend_data.get("memory_used_mb") is not None:
        memory["used_mb"] = extend_data.get("memory_used_mb")
    if extend_data.get("memory_usage_percent") is not None:
        memory["usage_percent"] = extend_data.get("memory_usage_percent")
    if extend_data.get("swap_total_mb") is not None:
        memory["swap_total_mb"] = extend_data.get("swap_total_mb")
    if extend_data.get("swap_available_mb") is not None:
        memory["swap_available_mb"] = extend_data.get("swap_available_mb")
    if extend_data.get("swap_used_mb") is not None:
        memory["swap_used_mb"] = extend_data.get("swap_used_mb")
    if extend_data.get("swap_usage_percent") is not None:
        memory["swap_usage_percent"] = extend_data.get("swap_usage_percent")

    if extend_data.get("process_count") is not None:
        processes["count"] = extend_data.get("process_count")

    disks = extend_data.get("disks")
    if isinstance(disks, list) and disks:
        metrics["disk"] = disks
        metrics["disk_error"] = None

    if any(extend_data.get(key) is not None for key in ("iface", "rx_bytes", "tx_bytes", "rx_packets", "tx_packets")):
        network = {
            "iface": extend_data.get("iface"),
            "rx_bytes": extend_data.get("rx_bytes"),
            "tx_bytes": extend_data.get("tx_bytes"),
            "rx_packets": extend_data.get("rx_packets"),
            "tx_packets": extend_data.get("tx_packets"),
        }
        metrics["network_error"] = None

    metrics["cpu"] = cpu
    metrics["memory"] = memory
    metrics["processes"] = processes
    metrics["network"] = network or None
    return metrics

def poll_host_metrics(
    ip: str,
    community: str,
    wifi_token: Optional[str] = None,
    gpu_token: Optional[str] = None,
    server_metrics_token: Optional[str] = None,
    include_optional_metric_errors: bool = True,
) -> dict:
    cpu_usage_percent = poll_cpu_usage_percent(ip, community)
    load_1m = extract_float(run_snmpget(ip, community, "1.3.6.1.4.1.2021.10.1.3.1").value)
    load_5m = extract_float(run_snmpget(ip, community, "1.3.6.1.4.1.2021.10.1.3.2").value)
    load_15m = extract_float(run_snmpget(ip, community, "1.3.6.1.4.1.2021.10.1.3.3").value)

    mem_total_mb, mem_available_mb = poll_memory_metrics(ip, community)
    swap_total_kb = extract_integer(run_snmpget(ip, community, "1.3.6.1.4.1.2021.4.3.0").value)
    swap_available_kb = extract_integer(run_snmpget(ip, community, "1.3.6.1.4.1.2021.4.4.0").value)
    swap_total_mb = None if swap_total_kb is None else swap_total_kb / 1024
    swap_available_mb = (
        None if swap_available_kb is None else swap_available_kb / 1024
    )
    process_count = extract_integer(run_snmpget(ip, community, "1.3.6.1.2.1.25.1.6.0").value)

    memory_used_mb = None
    memory_usage_percent = None
    if mem_total_mb is not None and mem_available_mb is not None:
        memory_used_mb = max(mem_total_mb - mem_available_mb, 0)
        if mem_total_mb:
            memory_usage_percent = round((memory_used_mb / mem_total_mb) * 100, 2)

    swap_used_mb = None
    swap_usage_percent = None
    if swap_total_mb is not None and swap_available_mb is not None:
        swap_used_mb = max(swap_total_mb - swap_available_mb, 0)
        if swap_total_mb:
            swap_usage_percent = round((swap_used_mb / swap_total_mb) * 100, 2)

    disks, disk_error = poll_disk_usage(ip, community)

    wifi = None
    wifi_error = None
    if wifi_token:
        wifi_raw, wifi_error = poll_extend_value(ip, community, wifi_token)
        wifi = {
            key: parse_maybe_number(value)
            for key, value in parse_key_value_text(wifi_raw).items()
        } or None
        if wifi is None and wifi_error is None:
            wifi_error = f"No parsable output returned by extend token '{wifi_token}'"
    elif include_optional_metric_errors:
        wifi_error = "Wi-Fi extend token not configured"

    gpu = None
    gpu_error = None
    if gpu_token:
        gpu_raw, gpu_error = poll_extend_value(ip, community, gpu_token)
        gpu = {
            key: parse_maybe_number(value)
            for key, value in parse_key_value_text(gpu_raw).items()
        } or None
        if gpu is None and gpu_error is None:
            gpu_error = f"No parsable output returned by extend token '{gpu_token}'"
    elif include_optional_metric_errors:
        gpu_error = "GPU extend token not configured"

    cpu_error = None
    if cpu_usage_percent is None and load_1m is None and load_5m is None and load_15m is None:
        cpu_error = "CPU OIDs are not exposed by this SNMP agent"

    memory_error = None
    if mem_total_mb is None and mem_available_mb is None:
        memory_error = "Memory OIDs are not exposed by this SNMP agent"

    network = None
    network_error = "Network interface counters are not exposed by this SNMP agent"

    metrics = {
        "cpu": {
            "usage_percent": cpu_usage_percent,
            "load_average": {
                "1m": load_1m,
                "5m": load_5m,
                "15m": load_15m,
            },
        },
        "cpu_error": cpu_error,
        "memory": {
            "total_mb": mem_total_mb,
            "available_mb": mem_available_mb,
            "used_mb": memory_used_mb,
            "usage_percent": memory_usage_percent,
            "swap_total_mb": swap_total_mb,
            "swap_available_mb": swap_available_mb,
            "swap_used_mb": swap_used_mb,
            "swap_usage_percent": swap_usage_percent,
        },
        "memory_error": memory_error,
        "disk": disks,
        "disk_error": disk_error,
        "processes": {
            "count": process_count,
        },
        "network": network,
        "network_error": network_error,
        "wifi": wifi,
        "wifi_error": wifi_error,
        "gpu": gpu,
        "gpu_error": gpu_error,
    }

    if server_metrics_token:
        extend_raw, extend_error = poll_extend_value(ip, community, server_metrics_token)
        if extend_raw:
            metrics = merge_server_extend_metrics(
                metrics,
                parse_json_text(extend_raw),
                server_metrics_token,
            )
        elif extend_error:
            metrics["cpu_error"] = metrics.get("cpu_error") or extend_error
            metrics["memory_error"] = metrics.get("memory_error") or extend_error
            metrics["disk_error"] = metrics.get("disk_error") or extend_error
            metrics["network_error"] = metrics.get("network_error") or extend_error

    return metrics
