from pathlib import Path

import pytest

from opencode_sandbox import cli, registry, sandbox


@pytest.fixture
def state_root(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    directory = tmp_path / "git"
    (directory / "platform" / "touchsurgery").mkdir(parents=True)
    (directory / "other").mkdir()
    return directory.resolve()


@pytest.fixture
def saved(state_root: Path, workspace: Path) -> sandbox.Sandbox:
    box = sandbox.Sandbox(name="ocs-git-abc123", directory=workspace / "platform")
    registry.save(state_root, box)
    return box


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "id_bitbucket"
    path.write_text("private")
    return path


def test_resolve_by_name(state_root: Path, saved: sandbox.Sandbox, tmp_path: Path) -> None:
    assert cli.resolve(saved.name, cwd=tmp_path, state_root=state_root) == saved


def test_resolve_unknown_name(state_root: Path, saved: sandbox.Sandbox, tmp_path: Path) -> None:
    with pytest.raises(cli.UsageError, match="no sandbox named"):
        cli.resolve("ocs-nope", cwd=tmp_path, state_root=state_root)


def test_resolve_by_containing_directory(state_root: Path, saved: sandbox.Sandbox) -> None:
    cwd = saved.directory / "touchsurgery"

    assert cli.resolve(None, cwd=cwd, state_root=state_root) == saved


def test_resolve_outside_any_sandbox(state_root: Path, saved: sandbox.Sandbox, workspace: Path) -> None:
    with pytest.raises(cli.UsageError, match="no sandbox contains"):
        cli.resolve(None, cwd=workspace / "other", state_root=state_root)


def test_start_new_for_current_directory(state_root: Path, workspace: Path) -> None:
    box = cli.resolve_start(None, cwd=workspace, name=None, ssh_keys=None, state_root=state_root)

    assert box.directory == workspace
    assert box.name == sandbox.default_name(workspace)
    assert box.ssh_keys == ()


def test_start_new_for_relative_directory_with_name_and_key(
    state_root: Path, workspace: Path, key: Path
) -> None:
    box = cli.resolve_start("other", cwd=workspace, name="mine", ssh_keys=[key], state_root=state_root)

    assert box == sandbox.Sandbox(name="ocs-mine", directory=workspace / "other", ssh_keys=(key,))


def test_start_saved_by_name_keeps_keys(state_root: Path, workspace: Path, key: Path, tmp_path: Path) -> None:
    box = sandbox.Sandbox(name="ocs-other", directory=workspace / "other", ssh_keys=(key,))
    registry.save(state_root, box)

    assert cli.resolve_start("ocs-other", cwd=tmp_path, name=None, ssh_keys=None, state_root=state_root) == box


def test_start_saved_by_directory_replaces_keys(
    state_root: Path, saved: sandbox.Sandbox, workspace: Path, key: Path
) -> None:
    box = cli.resolve_start("platform", cwd=workspace, name=None, ssh_keys=[key], state_root=state_root)

    assert box == sandbox.Sandbox(name=saved.name, directory=saved.directory, ssh_keys=(key,))


@pytest.mark.parametrize("target", ["platform/touchsurgery", "."])
def test_start_refuses_nested_sandbox(
    state_root: Path, saved: sandbox.Sandbox, workspace: Path, target: str
) -> None:
    with pytest.raises(cli.UsageError, match=saved.name):
        cli.resolve_start(target, cwd=workspace, name=None, ssh_keys=None, state_root=state_root)


def test_start_refuses_missing_directory(state_root: Path, workspace: Path) -> None:
    with pytest.raises(cli.UsageError, match="neither a sandbox name nor a directory"):
        cli.resolve_start("nope", cwd=workspace, name=None, ssh_keys=None, state_root=state_root)


def test_start_refuses_missing_key(state_root: Path, workspace: Path, tmp_path: Path) -> None:
    with pytest.raises(cli.UsageError, match="does not exist"):
        cli.resolve_start(
            None, cwd=workspace, name=None, ssh_keys=[tmp_path / "missing"], state_root=state_root
        )


def test_start_refuses_taken_name(state_root: Path, saved: sandbox.Sandbox, workspace: Path) -> None:
    with pytest.raises(cli.UsageError, match="already exists"):
        cli.resolve_start("other", cwd=workspace, name=saved.name, ssh_keys=None, state_root=state_root)


def test_start_refuses_renaming_saved(state_root: Path, saved: sandbox.Sandbox) -> None:
    with pytest.raises(cli.UsageError, match="to rename"):
        cli.resolve_start(None, cwd=saved.directory, name="new", ssh_keys=None, state_root=state_root)
