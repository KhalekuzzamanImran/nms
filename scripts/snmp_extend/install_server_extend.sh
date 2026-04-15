#!/usr/bin/env bash
set -euo pipefail

SCRIPT_SOURCE="${1:-./scripts/snmp_extend/server_metrics.py}"
TARGET_SCRIPT="/usr/local/bin/server_metrics.py"
SNMPD_CONF="/etc/snmp/snmpd.conf"

sudo install -m 0755 "$SCRIPT_SOURCE" "$TARGET_SCRIPT"

if ! grep -q '^extend server_metrics ' "$SNMPD_CONF"; then
  echo 'extend server_metrics /usr/bin/env python3 /usr/local/bin/server_metrics.py' | sudo tee -a "$SNMPD_CONF" >/dev/null
fi

if ! grep -q '^view[[:space:]]\+systemonly[[:space:]]\+included[[:space:]]\+\.1\.3\.6\.1\.4\.1\.8072\.1\.3\.2' "$SNMPD_CONF"; then
  echo 'view   systemonly  included   .1.3.6.1.4.1.8072.1.3.2' | sudo tee -a "$SNMPD_CONF" >/dev/null
fi

sudo systemctl restart snmpd
sudo systemctl status --no-pager snmpd

echo
echo "Verify with:"
echo "snmpget -v2c -c public -On 127.0.0.1 '1.3.6.1.4.1.8072.1.3.2.3.1.2.14.115.101.114.118.101.114.95.109.101.116.114.105.99.115'"
