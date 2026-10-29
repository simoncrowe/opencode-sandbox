#!/bin/sh
# Seed files are copied rather than mounted so config edits inside the
# container never touch the host.
set -eu

seed=/run/opencode-sandbox

if [ -d "$seed/config" ]; then
  cp -r "$seed/config/." "$HOME/.config/opencode/"
fi

if [ -d "$seed/agents" ]; then
  rm -rf "$HOME/.agents"
  cp -r "$seed/agents" "$HOME/.agents"
fi

if [ -f "$seed/gitconfig" ]; then
  cp "$seed/gitconfig" "$HOME/.gitconfig"
fi

if [ -d "$seed/ssh" ]; then
  rm -rf "$HOME/.ssh"
  cp -r "$seed/ssh" "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  chmod 600 "$HOME/.ssh"/*
fi

# Only seed MCP tokens once: OAuth servers may rotate refresh tokens, so
# overwriting the container's copy could replace a fresh token with a stale one.
mcp_auth="$HOME/.local/share/opencode/mcp-auth.json"
if [ -f "$seed/mcp-auth.json" ] && [ ! -f "$mcp_auth" ]; then
  cp "$seed/mcp-auth.json" "$mcp_auth"
  chmod 600 "$mcp_auth"
fi

if [ -f "$seed/ca-certificates.crt" ]; then
  export SSL_CERT_FILE="$seed/ca-certificates.crt"
  export NODE_EXTRA_CA_CERTS="$SSL_CERT_FILE"
  export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
  export CURL_CA_BUNDLE="$SSL_CERT_FILE"
  export GIT_SSL_CAINFO="$SSL_CERT_FILE"
fi

exec opencode serve --hostname 0.0.0.0 --port 4096 "$@"
