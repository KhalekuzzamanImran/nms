# Docker Realtime Stack

This stack runs:

- `backend`: Django ASGI app serving cached current state, SSH, historical APIs, and websocket status updates
- `poller`: background polling service that gathers SNMP snapshots, writes the latest snapshot to shared runtime storage, and stores historical metrics in InfluxDB
- `influxdb`: historical metric storage
- `frontend`: static React app

## Router Handover

The router is monitored through two WAN management paths:

- Primary router WAN: `ROUTER_PRIMARY_LINK_IP` (`103.4.116.146` by default)
- Primary ISP gateway: `ROUTER_PRIMARY_GATEWAY_IP` (`103.4.116.145` by default)
- Secondary router WAN: `ROUTER_SECONDARY_LINK_IP` (`202.51.186.226` by default)
- Secondary ISP gateway: `ROUTER_SECONDARY_GATEWAY_IP` (`202.51.186.225` by default)

The poller prefers the primary link while the router WAN answers SNMP and its
ISP gateway answers ping. If either primary check fails, router polling and
router SSH hand over to the secondary router WAN when its SNMP and gateway
checks are up. When the primary checks recover, it becomes the active path
again.

## Link Discovery

Router-to-switch port detection is automatic. The poller tries, in order:

1. LLDP neighbor data, then CDP neighbor data
2. Bridge MAC forwarding table lookup
3. Active physical port traffic/status heuristic
4. The configured fallback indexes in `config/settings.py`

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

- For SSH and SNMP to work from containers, the containers must have network reachability to your actual router primary/secondary WAN IPs, ISP gateways, switch, laptop, and server.
- The current `docker-compose.yml` uses the same device IPs already configured in the project. Override them with environment variables if needed.
- The server-side SNMP `extend` setup for `server_metrics` must already be installed on the Ubuntu server for server CPU/memory/disk/network metrics to appear.
