"""Run opencode web sessions in isolated containers against a mounted host directory."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from opencode_sandbox import compose, registry, sandbox, session

DEFAULT_OPENCODE_VERSION = "2.0.24"
HOST_CA_BUNDLES = (
    Path("/etc/ssl/certs/ca-certificates.crt"),
    Path("/etc/pki/tls/certs/ca-bundle.crt"),
    Path("/etc/ssl/cert.pem"),
)

app = App(help=__doc__)


class UsageError(Exception):
    pass


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def browser() -> str:
    return os.environ.get("OCS_BROWSER", "chromium")


def images_from_env() -> compose.Images:
    return compose.Images(
        opencode_version=os.environ.get("OCS_OPENCODE_VERSION", DEFAULT_OPENCODE_VERSION),
        uid=os.getuid(),
        gid=os.getgid(),
    )


def git_identity() -> dict[str, str]:
    identity = {}
    for key in ("name", "email"):
        proc = subprocess.run(
            ["git", "config", "--global", "--get", f"user.{key}"],
            capture_output=True, text=True, check=False,
        )
        if value := proc.stdout.strip():
            identity[key] = value
    return identity


def host_ca_bundle() -> Path | None:
    """Return the host's CA bundle, which may include a TLS-inspecting proxy's root."""
    if override := os.environ.get("OCS_CA_BUNDLE"):
        return Path(override)
    return next((path for path in HOST_CA_BUNDLES if path.is_file()), None)


def resolve(target: str | None, *, cwd: Path, state_root: Path) -> sandbox.Sandbox:
    """Find a sandbox by name, or the one whose directory contains `cwd`."""
    if target:
        if saved := registry.load(state_root, target):
            return saved
        raise UsageError(f"no sandbox named {target!r}; see `ocs ls`")
    if box := sandbox.containing(cwd.resolve(), registry.all_sandboxes(state_root)):
        return box
    raise UsageError(f"no sandbox contains {cwd.resolve()}; pass a name from `ocs ls`")


def resolve_start(
    target: str | None,
    *,
    cwd: Path,
    name: str | None,
    ssh_keys: list[Path] | None,
    state_root: Path,
) -> sandbox.Sandbox:
    """Find a saved sandbox by name or directory, or describe a new one; never one nested in another."""
    if target and (saved := registry.load(state_root, target)):
        directory = saved.directory
    else:
        directory = (cwd / target if target else cwd).resolve()
        if not directory.is_dir():
            raise UsageError(f"{target!r} is neither a sandbox name nor a directory")

    existing = registry.all_sandboxes(state_root)
    if other := sandbox.overlapping(directory, existing):
        relation = "is inside" if directory.is_relative_to(other.directory) else "contains"
        raise UsageError(
            f"{directory} {relation} sandbox {other.name} ({other.directory});"
            f" start that instead or remove it with `ocs rm {other.name}`"
        )

    current = next((box for box in existing if box.directory == directory), None)
    try:
        new_name = sandbox.custom_name(name) if name else None
    except ValueError as error:
        raise UsageError(str(error)) from None
    if current and new_name and new_name != current.name:
        raise UsageError(f"{directory} is already sandbox {current.name}; `ocs rm` it to rename")
    if not current and new_name and registry.load(state_root, new_name):
        raise UsageError(f"a sandbox named {new_name} already exists")

    keys = tuple(key.expanduser().resolve() for key in ssh_keys) if ssh_keys is not None else None
    for key in keys or ():
        if not key.is_file():
            raise UsageError(f"SSH key {key} does not exist")

    if current:
        return current if keys is None else sandbox.Sandbox(current.name, directory, keys)
    return sandbox.Sandbox(new_name or sandbox.default_name(directory), directory, keys or ())


def build(images: compose.Images) -> None:
    compose.run(None, "build", env=compose.environment(images=images))


@app.command
def start(
    target: str | None = None,
    *,
    name: str | None = None,
    ssh_key: Annotated[list[Path] | None, Parameter(name="--ssh-key")] = None,
    open_: Annotated[bool, Parameter(name="--open")] = False,
) -> None:
    """Start a background web session with a directory mounted read-write.

    Parameters
    ----------
    target
        Directory to mount (default: the current one), or a sandbox name from `ocs ls`.
    name
        Name for a new sandbox, instead of one derived from the directory.
    ssh_key
        Private key to make available inside the sandbox; repeat for several. Replaces saved keys.
    open_
        Open the web UI in the browser.
    """
    state_root = registry.default_root()
    box = resolve_start(target, cwd=Path.cwd(), name=name, ssh_keys=ssh_key, state_root=state_root)
    images = images_from_env()

    if compose.is_running(box.project, env=compose.environment(images=images)):
        raise UsageError(f"{box.name} is already running; use `ocs open {box.name}`")
    if not compose.images_exist(images):
        session.log(f"building images for opencode {images.opencode_version}")
        build(images)

    url = session.start(
        box,
        images=images,
        state_root=state_root,
        allowlists=[
            compose.resources_dir() / "allowlist",
            config_home() / "opencode-sandbox" / "allowlist",
        ],
        config_dir=config_home() / "opencode",
        agents_dir=Path.home() / ".agents",
        known_hosts=Path.home() / ".ssh" / "known_hosts",
        git_identity=git_identity(),
        ca_bundle=host_ca_bundle(),
    )
    print(f"{box.name}  {box.directory}  {url}")
    link = session.sign_in_link(box, images=images, state_root=state_root)
    if open_:
        session.launch_browser(link, browser=browser())
    else:
        print(f"sign in (single use, 5 minutes): {link}")


@app.command(name="ls")
def list_sandboxes() -> None:
    """List sandboxes with their directory, status and web UI URL."""
    state_root = registry.default_root()
    images = images_from_env()
    statuses = compose.project_statuses()

    rows = [("NAME", "DIRECTORY", "STATUS", "URL")]
    for box in registry.all_sandboxes(state_root):
        status = statuses.get(box.project, "stopped")
        url = session.url(box, images=images) if status.startswith("running") else None
        rows.append((box.name, str(box.directory), status, url or "-"))

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


@app.command(name="open")
def open_ui(
    target: str | None = None,
    *,
    print_: Annotated[bool, Parameter(name="--print", negative="")] = False,
) -> None:
    """Open a running sandbox's web UI, signed in.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls` (default: the sandbox containing the current directory).
    print_
        Print a single-use sign-in link instead of launching the browser.
    """
    state_root = registry.default_root()
    box = resolve(target, cwd=Path.cwd(), state_root=state_root)
    link = session.sign_in_link(box, images=images_from_env(), state_root=state_root)
    if print_:
        print(link)
    else:
        session.launch_browser(link, browser=browser())


@app.command
def stop(target: str | None = None) -> None:
    """Stop a sandbox's containers.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls` (default: the sandbox containing the current directory).
    """
    state_root = registry.default_root()
    box = resolve(target, cwd=Path.cwd(), state_root=state_root)
    session.stop(box, images=images_from_env(), state_root=state_root)
    session.log(f"stopped {box.name}")


@app.command
def logs(target: str | None = None, *, follow: Annotated[bool, Parameter(name=["--follow", "-f"])] = False) -> None:
    """Show a sandbox's container logs.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls` (default: the sandbox containing the current directory).
    follow
        Keep streaming new output.
    """
    box = resolve(target, cwd=Path.cwd(), state_root=registry.default_root())
    args = ["logs", "--follow"] if follow else ["logs"]
    compose.run(box.project, *args, env=compose.environment(images=images_from_env()), check=False)


@app.command
def denied(target: str | None = None) -> None:
    """List hosts the gateway refused.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls` (default: the sandbox containing the current directory).
    """
    box = resolve(target, cwd=Path.cwd(), state_root=registry.default_root())
    env = compose.environment(images=images_from_env())
    output = compose.run(box.project, "logs", "--no-log-prefix", "gateway", env=env, capture=True)
    for line in output.stdout.splitlines():
        if "refused on filtered domain" in line:
            print(line)


@app.command
def rm(target: str | None = None) -> None:
    """Delete a stopped sandbox's record and opencode state; the directory is left alone.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls` (default: the sandbox containing the current directory).
    """
    state_root = registry.default_root()
    box = resolve(target, cwd=Path.cwd(), state_root=state_root)
    env = compose.environment(images=images_from_env())

    if compose.is_running(box.project, env=env):
        raise UsageError(f"{box.name} is running; `ocs stop {box.name}` first")

    compose.run(box.project, "down", "--volumes", env=env, capture=True, check=False)
    registry.remove(state_root, box.project)
    session.log(f"removed {box.name} ({box.directory} untouched)")


@app.command(name="build")
def build_images() -> None:
    """Build the container images."""
    build(images_from_env())


def main() -> None:
    try:
        app()
    except (UsageError, session.SessionError) as error:
        session.log(str(error))
        sys.exit(1)
    except subprocess.CalledProcessError as error:
        session.log(f"command failed: {' '.join(map(str, error.cmd))}")
        sys.exit(error.returncode or 1)
