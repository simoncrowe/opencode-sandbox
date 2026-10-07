#!/bin/sh
# Egress: tinyproxy on :3128 only allows hosts matching /etc/opencode-sandbox/allowlist.
# Ingress: socat forwards :4096 to the opencode container on the internal network.
set -eu

: "${UPSTREAM:?UPSTREAM must name the opencode container}"

grep -Ev '^[[:space:]]*(#|$)' /etc/opencode-sandbox/allowlist > /tmp/filter

cat > /tmp/tinyproxy.conf <<EOF
Port 3128
Listen 0.0.0.0
Timeout 600
MaxClients 100
Allow 10.0.0.0/8
Allow 172.16.0.0/12
Allow 192.168.0.0/16
Filter "/tmp/filter"
FilterType ere
FilterURLs Off
FilterCaseSensitive Off
FilterDefaultDeny Yes
ConnectPort 443
LogLevel ${LOG_LEVEL:-Notice}
EOF

tinyproxy -d -c /tmp/tinyproxy.conf &
exec socat TCP-LISTEN:4096,fork,reuseaddr "TCP:${UPSTREAM}:4096"
