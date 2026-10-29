"""Lifecycle of detached sandbox sessions: start, stop and sign in."""

import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from opencode_sandbox import compose, credentials, registry, sandbox, server

CONFIG_FILES = ("opencode.json", "opencode.jsonc", "AGENTS.md")


class SessionError(Exception):
    pass


def log(message: str) -> None:
    print(f"ocs: {message}", file=sys.stderr, flush=True)


def ssh_config(key_names: Iterable[str]) -> str:
    identities = "".join(f"    IdentityFile ~/.ssh/{name}\n" for name in key_names)
    return f"Host *\n    IdentitiesOnly yes\n{identities}"


def gitconfig(identity: dict[str, str]) -> str:
    entries = "".join(f"    {key} = {value}\n" for key, value in identity.items())
    return f"[user]\n{entries}" if entries else ""


def write_ssh_seed(ssh_dir: Path, *, keys: Iterable[Path], known_hosts: Path) -> None:
    ssh_dir.mkdir(mode=0o700)
    names = []
    for key in keys:
        if (ssh_dir / key.name).exists():
            raise SessionError(f"two SSH keys are named {key.name}; rename one")
        shutil.copy(key, ssh_dir / key.name)
        names.append(key.name)
    if known_hosts.is_file():
        shutil.copy(known_hosts, ssh_dir / "known_hosts")
    (ssh_dir / "config").write_text(ssh_config(names))


def write_seed(
    seed_dir: Path,
    *,
    config_dir: Path,
    agents_dir: Path,
    ssh_keys: Iterable[Path] = (),
    known_hosts: Path,
    git_identity: dict[str, str],
    ca_bundle: Path | None = None,
    mcp_auth: Path | None = None,
) -> None:
    """Stage the files the containers need without exposing their host paths."""
    seed_config = seed_dir / "config"
    seed_config.mkdir()
    for name in CONFIG_FILES:
        if (config_dir / name).is_file():
            shutil.copy(config_dir / name, seed_config / name)

    if agents_dir.is_dir():
        shutil.copytree(agents_dir, seed_dir / "agents", ignore=shutil.ignore_patterns("*.swp", ".git"))

    if git_identity:
        (seed_dir / "gitconfig").write_text(gitconfig(git_identity))
    write_ssh_seed(seed_dir / "ssh", keys=ssh_keys, known_hosts=known_hosts)
    if ca_bundle:
        shutil.copy(ca_bundle, seed_dir / "ca-certificates.crt")
    if mcp_auth and mcp_auth.is_file():
        shutil.copy(mcp_auth, seed_dir / "mcp-auth.json")


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def url(box: sandbox.Sandbox, *, images: compose.Images) -> str | None:
    env = compose.environment(images=images, box=box)
    port = compose.published_port(box.project, env=env)
    return base_url(port) if port else None


def start(
    box: sandbox.Sandbox,
    *,
    images: compose.Images,
    state_root: Path,
    config_dir: Path,
    agents_dir: Path,
    known_hosts: Path,
    git_identity: dict[str, str],
    ca_bundle: Path | None = None,
    mcp_auth: Path | None = None,
) -> str:
    """Start the sandbox's containers in the background and return the web UI URL."""
    registry.save(state_root, box)
    password = registry.password(state_root, box.project)

    seed = registry.seed_dir(state_root, box.project)
    shutil.rmtree(seed, ignore_errors=True)
    seed.mkdir(mode=0o700)
    write_seed(
        seed,
        config_dir=config_dir,
        agents_dir=agents_dir,
        ssh_keys=box.ssh_keys,
        known_hosts=known_hosts,
        git_identity=git_identity,
        ca_bundle=ca_bundle,
        mcp_auth=mcp_auth,
    )

    env = compose.environment(
        images=images,
        box=box,
        seed_dir=seed,
        password=password,
        port=registry.port(state_root, box.project),
    )
    compose.ensure_cache_volume()
    compose.run(box.project, "up", "--detach", "--no-build", "--wait", env=env)

    port = compose.published_port(box.project, env=env)
    if not port:
        raise SessionError("gateway port not published")
    if not server.wait_until_ready(base_url(port), password=password):
        raise SessionError(f"server at {base_url(port)} did not become ready")

    copied = credentials.copy_to_sandbox(base_url(port), password=password)
    log(f"credentials: {', '.join(copied) or 'none found on host'}")
    prepare_project(base_url(port), box, password=password)
    return base_url(port)


def prepare_project(address: str, box: sandbox.Sandbox, *, password: str) -> None:
    """Make the directory show up in the web UI: opencode only registers a project once a session exists there."""
    directory = str(box.directory)
    if not server.has_sessions(address, directory, password=password):
        server.create_session(address, directory, title=box.directory.name, password=password)
    if project := server.project_id(address, directory, password=password):
        server.rename_project(address, project, name=box.directory.name, password=password)


def sign_in_link(box: sandbox.Sandbox, *, images: compose.Images, state_root: Path) -> str:
    """Return a single-use link (valid 5 minutes) that signs a browser in to the web UI."""
    address = url(box, images=images)
    if not address:
        raise SessionError(f"{box.project} is not running")
    return server.sign_in_link(address, password=registry.password(state_root, box.project))


def launch_browser(link: str, *, browser: str) -> None:
    try:
        subprocess.Popen(
            [browser, f"--app={link}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        log(f"could not start {browser} ({error}); sign in at {link}")


def stop(box: sandbox.Sandbox, *, images: compose.Images, state_root: Path) -> None:
    compose.run(box.project, "down", env=compose.environment(images=images), capture=True, check=False)
    shutil.rmtree(registry.seed_dir(state_root, box.project), ignore_errors=True)
