# Server SNMP Extend

This project now supports a custom SNMP `extend` token for server telemetry:

- token: `server_metrics`
- script: [scripts/snmp_extend/server_metrics.py](/home/imrankhan/Documents/created_by_imran/nms/scripts/snmp_extend/server_metrics.py)
- installer: [scripts/snmp_extend/install_server_extend.sh](/home/imrankhan/Documents/created_by_imran/nms/scripts/snmp_extend/install_server_extend.sh)

## Install On The Server

Run on the Ubuntu server:

```bash
sudo install -m 0755 ./scripts/snmp_extend/server_metrics.py /usr/local/bin/server_metrics.py
echo 'extend server_metrics /usr/bin/env python3 /usr/local/bin/server_metrics.py' | sudo tee -a /etc/snmp/snmpd.conf
echo 'view   systemonly  included   .1.3.6.1.4.1.8072.1.3.2' | sudo tee -a /etc/snmp/snmpd.conf
sudo systemctl restart snmpd
```

Or use:

```bash
./scripts/snmp_extend/install_server_extend.sh ./scripts/snmp_extend/server_metrics.py
```

## Verify

```bash
snmpget -v2c -c public -On 127.0.0.1 '1.3.6.1.4.1.8072.1.3.2.3.1.2.14.115.101.114.118.101.114.95.109.101.116.114.105.99.115'
```

The extend output is JSON and includes:

- `cpu_usage_percent`
- `load_1m`, `load_5m`, `load_15m`
- `memory_total_mb`, `memory_available_mb`, `memory_used_mb`, `memory_usage_percent`
- `swap_total_mb`, `swap_available_mb`, `swap_used_mb`, `swap_usage_percent`
- `process_count`
- `disks`
- `iface`, `rx_bytes`, `tx_bytes`, `rx_packets`, `tx_packets`

## Django Behavior

The backend now prefers `server_metrics` extend output for the server node when available, and falls back to standard SNMP OIDs otherwise.
