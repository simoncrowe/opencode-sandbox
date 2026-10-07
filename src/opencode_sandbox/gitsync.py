"""Keep a sandbox clone and the host repository's branch in step.

The container only ever sees the clone. Commits flow host -> clone when a
session starts and clone -> host (fast-forward only) when it ends.
"""

import enum
import subprocess
from pathlib import Path

HOST_REMOTE = "host"


class GitError(Exception):
    pass


class SyncResult(enum.StrEnum):
    UP_TO_DATE = "up to date"
    FAST_FORWARDED = "fast-forwarded"
    DIVERGED = "diverged"
    CHECKED_OUT = "checked out on host"


class PushResult(enum.StrEnum):
    PUSHED = "pushed"
    UP_TO_DATE = "already on remote"
    NO_REMOTE = "no remote"
    PROTECTED = "default branch, not pushed"


PUSH_REMOTE = "origin"
PROTECTED_BRANCHES = frozenset({"main", "master"})


def git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def succeeds(*args: str, cwd: Path) -> bool:
    try:
        git(*args, cwd=cwd)
    except GitError:
        return False
    return True


def repo_root(path: Path) -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=path)).resolve()


def has_ref(ref: str, *, cwd: Path) -> bool:
    return succeeds("show-ref", "--verify", "--quiet", ref, cwd=cwd)


def is_dirty(repo: Path) -> bool:
    return bool(git("status", "--porcelain", cwd=repo))


def ensure_host_branch(*, host: Path, branch: str, base: str) -> None:
    if has_ref(f"refs/heads/{branch}", cwd=host):
        return
    if has_ref(f"refs/remotes/origin/{branch}", cwd=host):
        git("branch", "--track", branch, f"origin/{branch}", cwd=host)
    else:
        git("branch", "--no-track", branch, base, cwd=host)


def prepare_clone(*, host: Path, clone: Path, branch: str, base: str) -> list[str]:
    """Create or refresh the clone with `branch` checked out; return warnings."""
    warnings: list[str] = []
    ensure_host_branch(host=host, branch=branch, base=base)

    if (clone / ".git").is_dir():
        git("fetch", "--quiet", HOST_REMOTE, cwd=clone)
    else:
        clone.parent.mkdir(parents=True, exist_ok=True)
        git(
            "clone", "--quiet", "--local", "--no-checkout",
            "--origin", HOST_REMOTE, str(host), str(clone),
            cwd=clone.parent,
        )
        for key in ("user.name", "user.email"):
            if succeeds("config", key, cwd=host):
                git("config", key, git("config", key, cwd=host), cwd=clone)

    if has_ref(f"refs/heads/{branch}", cwd=clone):
        git("checkout", "--quiet", branch, cwd=clone)
        if not succeeds("merge", "--quiet", "--ff-only", f"{HOST_REMOTE}/{branch}", cwd=clone):
            warnings.append(f"sandbox {branch} has diverged from the host branch; left as is")
    else:
        git("checkout", "--quiet", "-b", branch, "--track", f"{HOST_REMOTE}/{branch}", cwd=clone)

    return warnings


def sandbox_ref(branch: str) -> str:
    return f"refs/sandbox/{branch}"


def is_checked_out(*, host: Path, branch: str) -> bool:
    worktrees = git("worktree", "list", "--porcelain", cwd=host).splitlines()
    return f"branch refs/heads/{branch}" in worktrees


def sync_to_host(*, host: Path, clone: Path, branch: str) -> SyncResult:
    """Fast-forward the host branch to the clone's; the clone's tip is always kept at refs/sandbox/<branch>."""
    ref = sandbox_ref(branch)
    git("fetch", "--quiet", str(clone), f"+refs/heads/{branch}:{ref}", cwd=host)
    host_sha = git("rev-parse", f"refs/heads/{branch}", cwd=host)
    sandbox_sha = git("rev-parse", ref, cwd=host)

    if host_sha == sandbox_sha:
        return SyncResult.UP_TO_DATE
    if not succeeds("merge-base", "--is-ancestor", host_sha, sandbox_sha, cwd=host):
        return SyncResult.DIVERGED
    if is_checked_out(host=host, branch=branch):
        return SyncResult.CHECKED_OUT

    git("update-ref", "-m", "ocs sync", f"refs/heads/{branch}", sandbox_sha, host_sha, cwd=host)
    return SyncResult.FAST_FORWARDED


def default_branch(host: Path) -> str | None:
    try:
        ref = git("symbolic-ref", "--short", f"refs/remotes/{PUSH_REMOTE}/HEAD", cwd=host)
    except GitError:
        return None
    return ref.removeprefix(f"{PUSH_REMOTE}/")


def push(*, host: Path, branch: str) -> PushResult:
    """Push the host branch to a same-named branch on origin; never forced, never the default branch."""
    if not succeeds("remote", "get-url", PUSH_REMOTE, cwd=host):
        return PushResult.NO_REMOTE
    if branch in PROTECTED_BRANCHES or branch == default_branch(host):
        return PushResult.PROTECTED

    remote_ref = f"refs/remotes/{PUSH_REMOTE}/{branch}"
    local_sha = git("rev-parse", f"refs/heads/{branch}", cwd=host)
    if has_ref(remote_ref, cwd=host) and git("rev-parse", remote_ref, cwd=host) == local_sha:
        return PushResult.UP_TO_DATE

    # An explicit refspec, because a branch created from origin/<default> may still track it.
    git(
        "push", "--quiet", "--set-upstream", PUSH_REMOTE,
        f"refs/heads/{branch}:refs/heads/{branch}",
        cwd=host,
    )
    return PushResult.PUSHED
