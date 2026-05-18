# Docker Realtime Stack

This stack runs:

- `backend`: Django ASGI app serving cached current state, SSH, historical APIs, and websocket status updates
- `poller`: background polling service that gathers SNMP snapshots, writes the latest snapshot to shared runtime storage, and stores historical metrics in InfluxDB
- `influxdb`: historical metric storage
- `frontend`: static React app

## Router Handover

The router itself is monitored through the stable VPN/LAN management IP:

- Router management IP: `ROUTER_IP` (`10.10.10.1` by default)

The WAN links are monitored separately:

- Primary router WAN: `ROUTER_PRIMARY_LINK_IP` (`103.4.116.146` by default)
- Primary RouterOS interface: `ROUTER_PRIMARY_INTERFACE_NAME` (`WAN1` by default)
- Primary ISP gateway: `ROUTER_PRIMARY_GATEWAY_IP` (`103.4.116.145` by default)
- Secondary router WAN: `ROUTER_SECONDARY_LINK_IP` (`202.51.186.226` by default)
- Secondary RouterOS interface: `ROUTER_SECONDARY_INTERFACE_NAME` (`WAN2` by default)
- Secondary ISP gateway: `ROUTER_SECONDARY_GATEWAY_IP` (`202.51.186.225` by default)

The poller uses SNMP over the VPN/LAN management IP to read the WAN interface
state. It prefers the primary link while the primary RouterOS interface is up
and the primary ISP gateway answers ping. If either primary check fails, the
handover state changes to secondary when the secondary interface and gateway are
up. Router polling and router SSH continue to use `ROUTER_IP`.

## Link Discovery

Router-to-switch port detection is automatic. The poller tries, in order:

1. LLDP neighbor data, then CDP neighbor data
2. Bridge MAC forwarding table lookup
3. Active physical port traffic/status heuristic
4. The configured fallback indexes in `config/settings.py`

Router-to-server detection first uses the router ARP table for `SERVER_IP`.
If that ARP entry is not present but the server itself is up, the poller falls
back to `ROUTER_TO_SERVER_ROUTER_INTERFACE_NAME` (`LAN` by default). This avoids
showing the server link as down just because the router ARP cache expired.

For the most accurate router-to-switch mapping, enable LLDP or CDP on both
devices and allow SNMP read access to the neighbor tables. Without LLDP/CDP, the
MAC-table and traffic fallbacks can still work, but they are less deterministic
on busy switches or multi-port routers.

## Start

```bash
docker compose up --build
```

## URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- InfluxDB: `http://localhost:8086`

## Architecture

- The poller runs `python manage.py poll_network`
- Each poll:
  - collects SNMP data
  - writes `/app/runtime/latest_snapshot.json`
  - writes historical points to InfluxDB
- The backend:
  - serves `/api/topology/` from the cached snapshot
  - serves `/api/history/overview/` from InfluxDB
  - pushes `/ws/status/` updates when the shared snapshot file changes
- The frontend:
  - fetches current snapshot data
  - subscribes to `/ws/status/` for realtime status-only updates
  - fetches historical chart data from `/api/history/overview/`

## Notes

- For SSH and SNMP to work from containers, the containers must have VPN/LAN reachability to `ROUTER_IP`, switch, laptop, and server. WAN link status also needs reachability to the ISP gateway probe IPs.
- The current `docker-compose.yml` uses the same device IPs already configured in the project. Override them with environment variables if needed.
- The server-side SNMP `extend` setup for `server_metrics` must already be installed on the Ubuntu server for server CPU/memory/disk/network metrics to appear.
