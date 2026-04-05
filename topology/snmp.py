import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SNMP_TIMEOUT = "2"
SNMP_RETRIES = "0"

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
    names = parse_walk_map(run_snmpwalk(ip, community, "1.3.6.1.2.1.31.1.1.1.1"))
    oper = parse_walk_map(run_snmpwalk(ip, community, "1.3.6.1.2.1.2.2.1.8"))
    macs = parse_walk_map(run_snmpwalk(ip, community, "1.3.6.1.2.1.2.2.1.6", numeric=True))
    candidates = []
    for oid, raw_name in names.items():
        idx = oid.split(".")[-1]
        name = extract_string(raw_name)
        oper_oid = f"IF-MIB::ifOperStatus.{idx}"
        oper_value = oper.get(oper_oid)
        oper_num = extract_integer(oper_value) if oper_value else None
        mac_oid = f".1.3.6.1.2.1.2.2.1.6.{idx}"
        mac_value = macs.get(mac_oid)
        mac = value_to_mac(mac_value) if mac_value else None

        if not name or name == "lo":
            continue
        if oper_num != 1:
            continue
        if not mac or mac == "00:00:00:00:00:00":
            continue
        candidates.append({"if_index": int(idx), "if_name": name, "mac": normalize_mac(mac)})
    return candidates[0] if candidates else None

def discover_switch_port_for_laptop(switch_ip: str, laptop_ip: str, community: str, switch_uplink_port_index: int) -> Optional[int]:
    laptop_iface = get_laptop_active_interface(laptop_ip, community)
    if not laptop_iface:
        return None
    laptop_mac = laptop_iface["mac"]

    base_port_to_ifindex = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.17.1.4.1.2", numeric=True))
    fdb_addr = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.17.4.3.1.1", numeric=True))
    fdb_port = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.17.4.3.1.2", numeric=True))

    suffix_to_mac = {}
    prefix_addr = ".1.3.6.1.2.1.17.4.3.1.1."
    for oid, value in fdb_addr.items():
        if oid.startswith(prefix_addr):
            suffix = oid[len(prefix_addr):]
            mac = value_to_mac(value)
            if mac:
                suffix_to_mac[suffix] = normalize_mac(mac)

    prefix_port = ".1.3.6.1.2.1.17.4.3.1.2."
    for oid, value in fdb_port.items():
        if not oid.startswith(prefix_port):
            continue
        suffix = oid[len(prefix_port):]
        mac = suffix_to_mac.get(suffix)
        if mac != laptop_mac:
            continue
        bridge_port = extract_integer(value)
        if bridge_port is None:
            continue
        base_oid = f".1.3.6.1.2.1.17.1.4.1.2.{bridge_port}"
        if_index = extract_integer(base_port_to_ifindex.get(base_oid))
        if if_index and if_index != switch_uplink_port_index:
            return if_index
    return None

def fallback_discover_access_port(switch_ip: str, community: str, switch_uplink_port_index: int) -> Optional[int]:
    names = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.1"))
    oper = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.2.2.1.8"))
    speed = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.15"))
    in_octets = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.6"))
    out_octets = parse_walk_map(run_snmpwalk(switch_ip, community, "1.3.6.1.2.1.31.1.1.1.10"))

    best_idx = None
    best_score = -1

    for oid, raw_name in names.items():
        idx = int(oid.split(".")[-1])
        name = extract_string(raw_name) or ""
        if idx == switch_uplink_port_index or not name.startswith("ether"):
            continue
        oper_num = extract_integer(oper.get(f"IF-MIB::ifOperStatus.{idx}"))
        speed_num = extract_integer(speed.get(f"IF-MIB::ifHighSpeed.{idx}"))
        if oper_num != 1 or not speed_num or speed_num <= 0:
            continue
        score = (extract_integer(in_octets.get(f"IF-MIB::ifHCInOctets.{idx}")) or 0) + (extract_integer(out_octets.get(f"IF-MIB::ifHCOutOctets.{idx}")) or 0)
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx
