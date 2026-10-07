from pathlib import Path

import pytest

from opencode_sandbox import gitsync


def commit(repo: Path, message: str) -> str:
    gitsync.git("commit", "--quiet", "--allow-empty", "-m", message, cwd=repo)
    return gitsync.git("rev-parse", "HEAD", cwd=repo)


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    gitsync.git("init", "--quiet", "--initial-branch", "main", cwd=repo)
    gitsync.git("config", "user.name", "Test", cwd=repo)
    gitsync.git("config", "user.email", "test@example.com", cwd=repo)
    commit(repo, "init")
    return repo


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    return tmp_path / "sandbox" / "repo" / "feat" / "x"


def test_prepare_creates_branch_on_host_and_clone(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")

    assert gitsync.has_ref("refs/heads/feat/x", cwd=host)
    assert gitsync.git("branch", "--show-current", cwd=clone) == "feat/x"
    assert gitsync.git("config", "user.email", cwd=clone) == "test@example.com"


def test_prepare_fast_forwards_existing_clone(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")
    gitsync.git("checkout", "--quiet", "feat/x", cwd=host)
    new_tip = commit(host, "on host")
    gitsync.git("checkout", "--quiet", "main", cwd=host)

    warnings = gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")

    assert warnings == []
    assert gitsync.git("rev-parse", "HEAD", cwd=clone) == new_tip


def test_sync_fast_forwards_host_branch(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")
    tip = commit(clone, "in sandbox")

    result = gitsync.sync_to_host(host=host, clone=clone, branch="feat/x")

    assert result is gitsync.SyncResult.FAST_FORWARDED
    assert gitsync.git("rev-parse", "feat/x", cwd=host) == tip


def test_sync_without_changes_is_up_to_date(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")

    assert gitsync.sync_to_host(host=host, clone=clone, branch="feat/x") is gitsync.SyncResult.UP_TO_DATE


def test_sync_diverged_keeps_sandbox_ref(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")
    sandbox_tip = commit(clone, "in sandbox")
    gitsync.git("checkout", "--quiet", "feat/x", cwd=host)
    host_tip = commit(host, "on host")
    gitsync.git("checkout", "--quiet", "main", cwd=host)

    result = gitsync.sync_to_host(host=host, clone=clone, branch="feat/x")

    assert result is gitsync.SyncResult.DIVERGED
    assert gitsync.git("rev-parse", "feat/x", cwd=host) == host_tip
    assert gitsync.git("rev-parse", "refs/sandbox/feat/x", cwd=host) == sandbox_tip


def test_sync_leaves_checked_out_branch_alone(host: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="HEAD")
    commit(clone, "in sandbox")
    gitsync.git("checkout", "--quiet", "feat/x", cwd=host)

    result = gitsync.sync_to_host(host=host, clone=clone, branch="feat/x")

    assert result is gitsync.SyncResult.CHECKED_OUT


@pytest.fixture
def origin(tmp_path: Path, host: Path) -> Path:
    bare = tmp_path / "origin.git"
    gitsync.git("init", "--quiet", "--bare", str(bare), cwd=tmp_path)
    gitsync.git("remote", "add", "origin", str(bare), cwd=host)
    gitsync.git("push", "--quiet", "origin", "main", cwd=host)
    gitsync.git("remote", "set-head", "origin", "main", cwd=host)
    return bare


def test_new_branch_from_origin_default_does_not_track_it(host: Path, origin: Path) -> None:
    gitsync.ensure_host_branch(host=host, branch="feat/x", base="origin/main")

    assert not gitsync.succeeds("config", "branch.feat/x.merge", cwd=host)


def test_push_creates_remote_branch_and_sets_upstream(host: Path, origin: Path, clone: Path) -> None:
    gitsync.prepare_clone(host=host, clone=clone, branch="feat/x", base="origin/main")
    tip = commit(clone, "in sandbox")
    gitsync.sync_to_host(host=host, clone=clone, branch="feat/x")

    result = gitsync.push(host=host, branch="feat/x")

    assert result is gitsync.PushResult.PUSHED
    assert gitsync.git("rev-parse", "refs/heads/feat/x", cwd=origin) == tip
    assert gitsync.git("rev-parse", "refs/heads/main", cwd=origin) != tip
    assert gitsync.git("config", "branch.feat/x.merge", cwd=host) == "refs/heads/feat/x"


def test_push_again_is_up_to_date(host: Path, origin: Path) -> None:
    gitsync.ensure_host_branch(host=host, branch="feat/x", base="HEAD")
    gitsync.push(host=host, branch="feat/x")

    assert gitsync.push(host=host, branch="feat/x") is gitsync.PushResult.UP_TO_DATE


def test_push_refuses_default_branch(host: Path, origin: Path) -> None:
    commit(host, "on main")

    assert gitsync.push(host=host, branch="main") is gitsync.PushResult.PROTECTED


def test_push_without_origin(host: Path) -> None:
    gitsync.ensure_host_branch(host=host, branch="feat/x", base="HEAD")

    assert gitsync.push(host=host, branch="feat/x") is gitsync.PushResult.NO_REMOTE


def test_push_does_not_force_over_remote_changes(host: Path, origin: Path, tmp_path: Path) -> None:
    gitsync.ensure_host_branch(host=host, branch="feat/x", base="HEAD")
    gitsync.push(host=host, branch="feat/x")
    other = tmp_path / "other"
    gitsync.git("clone", "--quiet", "--branch", "feat/x", str(origin), str(other), cwd=tmp_path)
    gitsync.git("config", "user.email", "o@example.com", cwd=other)
    gitsync.git("config", "user.name", "Other", cwd=other)
    commit(other, "elsewhere")
    gitsync.git("push", "--quiet", cwd=other)
    gitsync.git("checkout", "--quiet", "feat/x", cwd=host)
    commit(host, "here")
    gitsync.git("checkout", "--quiet", "main", cwd=host)

    with pytest.raises(gitsync.GitError):
        gitsync.push(host=host, branch="feat/x")


def test_push_of_branch_tracking_default_goes_to_own_name(host: Path, origin: Path) -> None:
    gitsync.git("branch", "--track", "feat/x", "origin/main", cwd=host)
    gitsync.git("checkout", "--quiet", "feat/x", cwd=host)
    tip = commit(host, "work")
    gitsync.git("checkout", "--quiet", "main", cwd=host)
    main_before = gitsync.git("rev-parse", "refs/heads/main", cwd=origin)

    gitsync.push(host=host, branch="feat/x")

    assert gitsync.git("rev-parse", "refs/heads/main", cwd=origin) == main_before
    assert gitsync.git("rev-parse", "refs/heads/feat/x", cwd=origin) == tip
    assert gitsync.git("config", "branch.feat/x.merge", cwd=host) == "refs/heads/feat/x"
