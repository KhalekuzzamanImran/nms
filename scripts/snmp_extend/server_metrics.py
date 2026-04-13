#!/usr/bin/env python3
import json
import os
from pathlib import Path


def read_first_line(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip().splitlines()[0]
    except Exception:
        return ""


def read_float(path: str):
    try:
        return float(read_first_line(path))
    except Exception:
        return None


def read_int(path: str):
    try:
        return int(read_first_line(path))
    except Exception:
        return None


def memory_info():
    data = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parts = value.strip().split()
        if not parts:
            continue
        try:
            data[key] = int(parts[0])
        except ValueError:
            continue

    total_kb = data.get("MemTotal")
    available_kb = data.get("MemAvailable")
    swap_total_kb = data.get("SwapTotal")
    swap_free_kb = data.get("SwapFree")

    used_kb = None if total_kb is None or available_kb is None else max(total_kb - available_kb, 0)
    swap_used_kb = None if swap_total_kb is None or swap_free_kb is None else max(swap_total_kb - swap_free_kb, 0)

    return {
        "memory_total_mb": None if total_kb is None else round(total_kb / 1024, 2),
        "memory_available_mb": None if available_kb is None else round(available_kb / 1024, 2),
        "memory_used_mb": None if used_kb is None else round(used_kb / 1024, 2),
        "memory_usage_percent": None if not total_kb or used_kb is None else round((used_kb / total_kb) * 100, 2),
        "swap_total_mb": None if swap_total_kb is None else round(swap_total_kb / 1024, 2),
        "swap_available_mb": None if swap_free_kb is None else round(swap_free_kb / 1024, 2),
        "swap_used_mb": None if swap_used_kb is None else round(swap_used_kb / 1024, 2),
        "swap_usage_percent": None if not swap_total_kb or swap_used_kb is None else round((swap_used_kb / swap_total_kb) * 100, 2),
    }


def load_info():
    load1, load5, load15 = os.getloadavg()
    return {
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
    }


def cpu_info():
    stat1 = read_first_line("/proc/stat")
    if not stat1.startswith("cpu "):
        return {"cpu_usage_percent": None}
    values1 = [int(part) for part in stat1.split()[1:]]
    idle1 = values1[3] + values1[4]
    total1 = sum(values1)

    import time

    time.sleep(0.2)
    stat2 = read_first_line("/proc/stat")
    values2 = [int(part) for part in stat2.split()[1:]]
    idle2 = values2[3] + values2[4]
    total2 = sum(values2)

    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    usage = None if total_delta <= 0 else round((1 - (idle_delta / total_delta)) * 100, 2)
    return {"cpu_usage_percent": usage}


def process_count():
    count = 0
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            count += 1
    return {"process_count": count}


def disk_info():
    disks = []
    for mount in (Path("/"), Path("/home")):
        try:
            stat = os.statvfs(mount)
        except OSError:
            continue
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = max(total - free, 0)
        disks.append(
            {
                "index": len(disks) + 1,
                "mount": str(mount),
                "storage_type": "fixed_disk",
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "usage_percent": round((used / total) * 100, 2) if total else None,
            }
        )
    return {"disks": disks}


def network_info():
    route_lines = Path("/proc/net/route").read_text(encoding="utf-8").splitlines()[1:]
    iface = None
    for line in route_lines:
        parts = line.split()
        if len(parts) > 1 and parts[1] == "00000000":
            iface = parts[0]
            break

    if not iface:
        return {"iface": None, "rx_bytes": None, "tx_bytes": None, "rx_packets": None, "tx_packets": None}

    base = Path("/sys/class/net") / iface / "statistics"
    return {
        "iface": iface,
        "rx_bytes": read_int(str(base / "rx_bytes")),
        "tx_bytes": read_int(str(base / "tx_bytes")),
        "rx_packets": read_int(str(base / "rx_packets")),
        "tx_packets": read_int(str(base / "tx_packets")),
    }


def main():
    payload = {}
    payload.update(cpu_info())
    payload.update(load_info())
    payload.update(memory_info())
    payload.update(process_count())
    payload.update(disk_info())
    payload.update(network_info())
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
