# opencode-sandbox

Run the [opencode](https://opencode.ai) v2 web UI in a container that can only see one
host directory (mounted read-write at the same path) and can only reach allowlisted hosts.
The directory can be a single repository, a folder of repositories or anything else, so
an agent can work across several repositories while host credentials (cloud, Teleport,
other SSH keys) stay out of reach.

```
browser ── 127.0.0.1:<random> ──► gateway ──► opencode     (internal network, no route out)
                                    │  socat :4096          opencode serve
                                    │  tinyproxy allowlist  HTTPS_PROXY=gateway:3128
                                    ▼  (ports 443 and 22)   <dir> mounted at <dir>
                                 internet (allowlisted hosts only)
```

## Install

Requires Docker with the Compose plugin and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/simoncrowe/opencode-sandbox
# or, from a checkout, editable:
uv tool install --editable .
```

## Usage

Sandboxes run detached under the Docker daemon (restarting with it), so they are
not tied to a shell.

```sh
ocs start [dir|name] [--ssh-key PATH]... [--name NAME] [--open]
ocs ls                         # all sandboxes, with directory, status and web UI URL
ocs open [name] [--print]      # open the web UI signed in (or print a sign-in link)
ocs logs [name] [-f]           # container logs
ocs denied [name]              # hosts the gateway refused
ocs stop [name]                # stop the containers
ocs rm [name]                  # delete a stopped sandbox's record and opencode state
ocs build                      # (re)build the container images
```

`ocs start` mounts `dir` (default: the current directory) or restarts a saved sandbox
by name. Sandboxes are named `ocs-<dir name>-<hash>` unless `--name` is given. Starting
an already-saved directory reuses its sandbox; a directory inside, or containing,
another sandbox's directory is refused. Without a name, the other commands use the
sandbox whose directory contains the current directory.

`--ssh-key` (repeatable) copies an unencrypted private key into the container's
`~/.ssh`, with your `~/.ssh/known_hosts` and an SSH config that uses only those keys and
tunnels through the gateway. Keys are saved with the sandbox; passing `--ssh-key` on a
later start replaces them. Your global git `user.name` and `user.email` are copied too.

Each sandbox keeps its port and password across restarts, so browser sign-ins (valid
30 days) keep working. Its record lives in `~/.local/state/opencode-sandbox/<name>/`;
opencode sessions persist in a Docker volume. Both are removed by `ocs rm`, which never
touches the mounted directory.

### Trade-offs

The agent can change anything in the mounted directory, including files that run on the
host later: git hooks and config, `justfile`s, `.envrc`, pre-commit config. It can also
read any secrets stored there, and push with the keys you give it. Review changes before
running them on the host and prefer narrowly scoped deploy or access keys.

## Credentials and config

At each start, `~/.local/share/opencode/auth.json` (e.g. GitHub Copilot) and
`opencode.json(c)` / `AGENTS.md` from `~/.config/opencode` and `~/.agents` (skills;
symlinks followed, `*.swp` skipped) are copied into the container. Nothing on the host is mounted writable except the sandbox directory.

The host's CA bundle (`/etc/ssl/certs/ca-certificates.crt` or equivalent, overridable with
`OCS_CA_BUNDLE`) is copied in too, so TLS-inspecting proxies such as Zscaler that the
host trusts are trusted inside the container.

## Network allowlist

`src/opencode_sandbox/resources/allowlist` holds the default host regexes (GitHub Copilot,
opencode, Bitbucket, PyPI, uv and pyenv Python downloads). Add your own, one extended regex per
line, in `~/.config/opencode-sandbox/allowlist`, then restart the sandbox. Refused hosts
appear in `ocs logs` and `ocs denied`.

## Configuration

| Variable               | Default          |
| ---------------------- | ---------------- |
| `OCS_OPENCODE_VERSION` | `2.0.24`         |
| `OCS_BROWSER`          | `chromium`       |

Images are tagged by opencode version; run `ocs build` after changing the Dockerfiles.

## Development

```sh
uv sync
uv run pytest
uv run mypy
```
