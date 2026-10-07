# opencode-sandbox

Run the [opencode](https://opencode.ai) v2 web UI in a container that can only see a
clone of one git branch and can only reach allowlisted hosts.

```
browser ── 127.0.0.1:<random> ──► gateway ──► opencode     (internal network, no route out)
                                    │  socat :4096          opencode serve
                                    │  tinyproxy allowlist  HTTPS_PROXY=gateway:3128
                                    ▼                       /work/<repo>/<branch> = sandbox clone
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
not tied to a shell. Start one from inside a repository (or pass `-C <path>`):

```sh
ocs start <branch> [base-ref]  # start in the background and open the web UI
ocs ls                         # all sandboxes, with status and web UI URL
ocs open <target> [--print]    # open the web UI signed in (or print a sign-in link)
ocs logs <target> [-f]         # container logs
ocs denied <target>            # hosts the gateway refused
ocs sync <target> [--no-push]  # copy sandbox commits to the host repo and push
ocs stop <target> [--no-push]  # stop the containers, sync commits to the host and push
ocs rm <target> [--force]      # sync, then delete a stopped sandbox's clone and state
ocs build                      # (re)build the container images
```

`<target>` is a sandbox name from `ocs ls`, a branch of the current repository, or a
branch name that is unique across sandboxes.

`ocs start`:

1. Makes sure the host repo has a local `<branch>` (from `origin/<branch>` or `base-ref`).
2. Creates or refreshes the clone `~/git/sandbox/<repo>/<branch>` (remote name `host`).
3. Starts the gateway and opencode containers with Docker Compose, waits for the server,
   copies your opencode credentials in, creates a first session in the clone (so the
   project, named `<repo>: <branch>`, appears in the web UI) and opens Chromium with a
   one-time sign-in link.

`ocs stop` (and `ocs sync`) fast-forwards the host branch to the sandbox branch and then
pushes it to a same-named branch on `origin` (`--no-push` to skip). Pushes are never
forced, never go to `main`, `master` or `origin/HEAD`, and set the branch's upstream to
itself. If the branches diverged, or the branch is checked out on the host, the
sandbox tip is left at `refs/sandbox/<branch>` for you to merge and nothing is pushed.

Each sandbox keeps its port and password across restarts, so browser sign-ins (valid
30 days) keep working. Its record lives in `~/.local/state/opencode-sandbox/<name>/`;
opencode sessions persist in a Docker volume. Both are removed by `ocs rm`.

## Credentials and config

At each start, `~/.local/share/opencode/auth.json` (e.g. GitHub Copilot) and
`opencode.json(c)` / `AGENTS.md` from `~/.config/opencode` and `~/.agents` (skills;
symlinks followed, `*.swp` skipped) are copied into the container. Nothing on the host is mounted writable except the sandbox clone.

## Network allowlist

`src/opencode_sandbox/resources/allowlist` holds the default host regexes (GitHub Copilot,
opencode, PyPI, uv and pyenv Python downloads). Add your own, one extended regex per
line, in `~/.config/opencode-sandbox/allowlist`, then restart the sandbox. Refused hosts
appear in `ocs logs` and `ocs denied`.

## Configuration

| Variable               | Default          |
| ---------------------- | ---------------- |
| `OCS_OPENCODE_VERSION` | `2.0.24`         |
| `OCS_SANDBOX_ROOT`     | `~/git/sandbox`  |
| `OCS_BROWSER`          | `chromium`       |

Images are tagged by opencode version; run `ocs build` after changing the Dockerfiles.

## Development

```sh
uv sync
uv run pytest
uv run mypy
```
