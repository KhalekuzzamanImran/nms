# Docker Realtime Stack

This stack runs:

- `backend`: Django ASGI app serving cached current state, SSH, historical APIs, and websocket status updates
- `poller`: background polling service that gathers SNMP snapshots, writes the latest snapshot to shared runtime storage, and stores historical metrics in InfluxDB
- `influxdb`: historical metric storage
- `frontend`: static React app

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

- For SSH and SNMP to work from containers, the containers must have network reachability to your actual router, switch, laptop, and server.
- The current `docker-compose.yml` uses the same device IPs already configured in the project. Override them with environment variables if needed.
- The server-side SNMP `extend` setup for `server_metrics` must already be installed on the Ubuntu server for server CPU/memory/disk/network metrics to appear.
