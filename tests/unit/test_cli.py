from pathlib import Path

import pytest

from opencode_sandbox import cli, gitsync, registry, sandbox


@pytest.fixture
def state_root(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.fixture
def saved(state_root: Path) -> sandbox.Sandbox:
    box = sandbox.Sandbox(
        repo_root=Path("/git/repo"), branch="feat/x", sandbox_root=Path("/git/sandbox")
    )
    registry.save(state_root, box)
    return box


@pytest.fixture
def not_a_repo(tmp_path: Path) -> Path:
    directory = tmp_path / "plain"
    directory.mkdir()
    return directory


def test_resolve_by_name(state_root: Path, saved: sandbox.Sandbox, not_a_repo: Path) -> None:
    assert cli.resolve(saved.project, not_a_repo, state_root=state_root) == saved


def test_resolve_unique_branch_outside_repo(
    state_root: Path, saved: sandbox.Sandbox, not_a_repo: Path
) -> None:
    assert cli.resolve("feat/x", not_a_repo, state_root=state_root) == saved


def test_resolve_ambiguous_branch_outside_repo(
    state_root: Path, saved: sandbox.Sandbox, not_a_repo: Path
) -> None:
    registry.save(state_root, sandbox.Sandbox(
        repo_root=Path("/git/other"), branch="feat/x", sandbox_root=Path("/git/sandbox")
    ))

    with pytest.raises(cli.UsageError, match="no sandbox matches"):
        cli.resolve("feat/x", not_a_repo, state_root=state_root)


def test_resolve_branch_in_repo(state_root: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    gitsync.git("init", "--quiet", cwd=repo)

    box = cli.resolve("new-branch", repo, state_root=state_root)

    assert box.repo_root == repo.resolve()
    assert box.branch == "new-branch"


def test_resolve_prefers_unique_saved_branch_over_unsaved_in_repo(
    state_root: Path, saved: sandbox.Sandbox, tmp_path: Path
) -> None:
    repo = tmp_path / "other-repo"
    repo.mkdir()
    gitsync.git("init", "--quiet", cwd=repo)

    assert cli.resolve("feat/x", repo, state_root=state_root) == saved


def test_resolve_prefers_saved_sandbox_in_current_repo(state_root: Path, saved: sandbox.Sandbox, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    gitsync.git("init", "--quiet", cwd=repo)
    local = sandbox.Sandbox(repo_root=repo.resolve(), branch="feat/x", sandbox_root=Path("/git/sandbox"))
    registry.save(state_root, local)

    assert cli.resolve("feat/x", repo, state_root=state_root) == local
