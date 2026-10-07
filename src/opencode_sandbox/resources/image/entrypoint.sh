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

exec opencode serve --hostname 0.0.0.0 --port 4096 "$@"
