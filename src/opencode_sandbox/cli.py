"""Run opencode web sessions in isolated containers against sandbox clones of git branches."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from opencode_sandbox import compose, gitsync, registry, sandbox, session

DEFAULT_OPENCODE_VERSION = "2.0.24"

Repo = Annotated[Path, Parameter(name=["--repo", "-C"])]

app = App(help=__doc__)


class UsageError(Exception):
    pass


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def sandbox_root() -> Path:
    return Path(os.environ.get("OCS_SANDBOX_ROOT", Path.home() / "git" / "sandbox"))


def browser() -> str:
    return os.environ.get("OCS_BROWSER", "chromium")


def images_from_env() -> compose.Images:
    return compose.Images(
        opencode_version=os.environ.get("OCS_OPENCODE_VERSION", DEFAULT_OPENCODE_VERSION),
        uid=os.getuid(),
        gid=os.getgid(),
    )


def resolve(target: str, repo: Path, *, state_root: Path) -> sandbox.Sandbox:
    """Find a sandbox by name, by branch in `repo`, or by a branch name unique across sandboxes.

    A branch in `repo` without a saved sandbox yields a new, unsaved one.
    """
    if saved := registry.load(state_root, target):
        return saved

    try:
        root: Path | None = gitsync.repo_root(repo)
    except gitsync.GitError:
        root = None

    if root:
        box = sandbox.Sandbox(repo_root=root, branch=target, sandbox_root=sandbox_root())
        if saved := registry.load(state_root, box.project):
            return saved

    matches = [box for box in registry.all_sandboxes(state_root) if box.branch == target]
    if len(matches) == 1:
        return matches[0]
    if root:
        return box
    raise UsageError(
        f"no sandbox matches {target!r}; use a name from `ocs ls` or run inside the repo"
    )


def build(images: compose.Images) -> None:
    compose.run(None, "build", env=compose.environment(images=images))


def is_synced(result: gitsync.SyncResult) -> bool:
    return result in (gitsync.SyncResult.UP_TO_DATE, gitsync.SyncResult.FAST_FORWARDED)


@app.command
def start(
    branch: str,
    base: str = "HEAD",
    *,
    repo: Repo = Path("."),
    open_: Annotated[bool, Parameter(name="--open")] = False,
) -> None:
    """Start a background web session for a branch.

    Parameters
    ----------
    branch
        Branch to work on; created from BASE if it does not exist.
    base
        Starting point for a new branch.
    repo
        Repository path.
    open_
        Open the web UI in the browser.
    """
    state_root = registry.default_root()
    box = sandbox.Sandbox(
        repo_root=gitsync.repo_root(repo), branch=branch, sandbox_root=sandbox_root()
    )
    box = registry.load(state_root, box.project) or box
    images = images_from_env()

    if compose.is_running(box.project, env=compose.environment(images=images)):
        raise UsageError(f"{box.project} is already running; use `ocs open {box.project}`")
    if not compose.images_exist(images):
        session.log(f"building images for opencode {images.opencode_version}")
        build(images)

    for warning in gitsync.prepare_clone(
        host=box.repo_root, clone=box.clone_dir, branch=box.branch, base=base
    ):
        session.log(warning)

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
    )
    print(f"{box.project}  {url}")
    link = session.sign_in_link(box, images=images, state_root=state_root)
    if open_:
        session.launch_browser(link, browser=browser())
    else:
        print(f"sign in (single use, 5 minutes): {link}")


@app.command(name="ls")
def list_sandboxes() -> None:
    """List sandboxes with their status and web UI URL."""
    state_root = registry.default_root()
    images = images_from_env()
    statuses = compose.project_statuses()

    rows = [("NAME", "REPO", "BRANCH", "STATUS", "URL")]
    for box in registry.all_sandboxes(state_root):
        status = statuses.get(box.project, "stopped")
        url = session.url(box, images=images) if status.startswith("running") else None
        rows.append((box.project, box.repo, box.branch, status, url or "-"))

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


@app.command(name="open")
def open_ui(
    target: str,
    *,
    repo: Repo = Path("."),
    print_: Annotated[bool, Parameter(name="--print", negative="")] = False,
) -> None:
    """Open a running sandbox's web UI, signed in.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    print_
        Print a single-use sign-in link instead of launching the browser.
    """
    state_root = registry.default_root()
    box = resolve(target, repo, state_root=state_root)
    link = session.sign_in_link(box, images=images_from_env(), state_root=state_root)
    if print_:
        print(link)
    else:
        session.launch_browser(link, browser=browser())


@app.command
def stop(target: str, *, repo: Repo = Path("."), push: bool = True) -> None:
    """Stop a sandbox, sync its commits to the host branch and push it.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    push
        Push the branch to origin after a successful sync.
    """
    state_root = registry.default_root()
    box = resolve(target, repo, state_root=state_root)
    if not is_synced(session.stop(box, images=images_from_env(), state_root=state_root)):
        sys.exit(1)
    if push and not session.push_branch(box):
        sys.exit(1)


@app.command
def sync(target: str, *, repo: Repo = Path("."), push: bool = True) -> None:
    """Fast-forward the host branch to the sandbox branch and push it.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    push
        Push the branch to origin after a successful sync.
    """
    box = resolve(target, repo, state_root=registry.default_root())
    if not (box.clone_dir / ".git").is_dir():
        raise UsageError(f"no sandbox clone at {box.clone_dir}")
    if not is_synced(session.report_sync(box)):
        sys.exit(1)
    if push and not session.push_branch(box):
        sys.exit(1)


@app.command
def logs(target: str, *, repo: Repo = Path("."), follow: Annotated[bool, Parameter(name=["--follow", "-f"])] = False) -> None:
    """Show a sandbox's container logs.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    follow
        Keep streaming new output.
    """
    box = resolve(target, repo, state_root=registry.default_root())
    args = ["logs", "--follow"] if follow else ["logs"]
    compose.run(box.project, *args, env=compose.environment(images=images_from_env()), check=False)


@app.command
def denied(target: str, *, repo: Repo = Path(".")) -> None:
    """List hosts the gateway refused.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    """
    box = resolve(target, repo, state_root=registry.default_root())
    env = compose.environment(images=images_from_env())
    output = compose.run(box.project, "logs", "--no-log-prefix", "gateway", env=env, capture=True)
    for line in output.stdout.splitlines():
        if "refused on filtered domain" in line:
            print(line)


@app.command
def rm(target: str, *, repo: Repo = Path("."), force: bool = False) -> None:
    """Sync, then delete a stopped sandbox's clone and opencode state.

    Parameters
    ----------
    target
        Sandbox name from `ocs ls`, or a branch name.
    repo
        Repository path used to resolve a branch name.
    force
        Discard unsynced work.
    """
    state_root = registry.default_root()
    box = resolve(target, repo, state_root=state_root)
    env = compose.environment(images=images_from_env())

    if compose.is_running(box.project, env=env):
        raise UsageError(f"{box.project} is running; `ocs stop {box.project}` first")

    if (box.clone_dir / ".git").is_dir() and not force:
        if gitsync.is_dirty(box.clone_dir):
            raise UsageError(f"{box.clone_dir} has uncommitted changes (use --force to discard)")
        if not is_synced(session.report_sync(box)):
            raise UsageError("sync failed (use --force to remove anyway)")

    shutil.rmtree(box.clone_dir, ignore_errors=True)
    parent = box.clone_dir.parent
    while parent != box.sandbox_root and parent.is_relative_to(box.sandbox_root):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    compose.run(box.project, "down", "--volumes", env=env, capture=True, check=False)
    registry.remove(state_root, box.project)
    session.log(f"removed {box.project} (branch {box.branch} still exists)")


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
    except gitsync.GitError as error:
        session.log(f"git: {error}")
        sys.exit(1)
    except subprocess.CalledProcessError as error:
        session.log(f"command failed: {' '.join(map(str, error.cmd))}")
        sys.exit(error.returncode or 1)
