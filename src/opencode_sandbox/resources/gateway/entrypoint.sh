#!/bin/sh
# Forwards :4096 to the opencode container so only the gateway publishes a host port.
set -eu

: "${UPSTREAM:?UPSTREAM must name the opencode container}"

exec socat TCP-LISTEN:4096,fork,reuseaddr "TCP:${UPSTREAM}:4096"
