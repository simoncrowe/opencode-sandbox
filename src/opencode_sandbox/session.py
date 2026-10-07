"""Lifecycle of detached sandbox sessions: start, stop, sign in and sync."""

import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from opencode_sandbox import compose, credentials, gitsync, registry, sandbox, server

CONFIG_FILES = ("opencode.json", "opencode.jsonc", "AGENTS.md")


class SessionError(Exception):
    pass


def log(message: str) -> None:
    print(f"ocs: {message}", file=sys.stderr, flush=True)


def merge_allowlists(texts: Iterable[str]) -> str:
    return "\n".join(text.rstrip("\n") for text in texts) + "\n"


def write_seed(
    seed_dir: Path,
    *,
    allowlists: list[Path],
    config_dir: Path,
    agents_dir: Path,
) -> None:
    """Stage the files the containers need without exposing their host paths."""
    texts = [path.read_text() for path in allowlists if path.is_file()]
    (seed_dir / "allowlist").write_text(merge_allowlists(texts))

    seed_config = seed_dir / "config"
    seed_config.mkdir()
    for name in CONFIG_FILES:
        if (config_dir / name).is_file():
            shutil.copy(config_dir / name, seed_config / name)

    if agents_dir.is_dir():
        shutil.copytree(agents_dir, seed_dir / "agents", ignore=shutil.ignore_patterns("*.swp", ".git"))


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
    allowlists: list[Path],
    config_dir: Path,
    agents_dir: Path,
) -> str:
    """Start the sandbox's containers in the background and return the web UI URL."""
    registry.save(state_root, box)
    password = registry.password(state_root, box.project)

    seed = registry.seed_dir(state_root, box.project)
    shutil.rmtree(seed, ignore_errors=True)
    seed.mkdir(mode=0o700)
    write_seed(seed, allowlists=allowlists, config_dir=config_dir, agents_dir=agents_dir)

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


def project_name(box: sandbox.Sandbox) -> str:
    return f"{box.repo}: {box.branch}"


def prepare_project(address: str, box: sandbox.Sandbox, *, password: str) -> None:
    """Make the clone show up in the web UI: opencode only registers a project once a session exists there."""
    if not server.has_sessions(address, box.workdir, password=password):
        server.create_session(address, box.workdir, title=box.branch, password=password)
    if project := server.project_id(address, box.workdir, password=password):
        server.rename_project(address, project, name=project_name(box), password=password)


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


def stop(box: sandbox.Sandbox, *, images: compose.Images, state_root: Path) -> gitsync.SyncResult:
    compose.run(box.project, "down", env=compose.environment(images=images), capture=True, check=False)
    shutil.rmtree(registry.seed_dir(state_root, box.project), ignore_errors=True)
    return report_sync(box)


def report_sync(box: sandbox.Sandbox) -> gitsync.SyncResult:
    if gitsync.is_dirty(box.clone_dir):
        log(f"{box.clone_dir} has uncommitted changes (not synced)")
    result = gitsync.sync_to_host(host=box.repo_root, clone=box.clone_dir, branch=box.branch)
    ref = gitsync.sandbox_ref(box.branch)
    match result:
        case gitsync.SyncResult.UP_TO_DATE | gitsync.SyncResult.FAST_FORWARDED:
            log(f"{box.branch}: {result}")
        case gitsync.SyncResult.DIVERGED:
            log(f"{box.branch} has diverged; sandbox commits are at {ref}")
        case gitsync.SyncResult.CHECKED_OUT:
            log(f"{box.branch} is checked out on the host; run `git merge --ff-only {ref}` there")
    return result


def push_branch(box: sandbox.Sandbox) -> bool:
    try:
        result = gitsync.push(host=box.repo_root, branch=box.branch)
    except gitsync.GitError as error:
        log(f"push of {box.branch} failed: {error}")
        return False
    log(f"{box.branch}: {result}")
    return True
