import socket
from pathlib import Path

import pytest

from opencode_sandbox import registry, sandbox


@pytest.fixture
def box() -> sandbox.Sandbox:
    return sandbox.Sandbox(
        repo_root=Path("/git/repo"), branch="feat/x", sandbox_root=Path("/git/sandbox")
    )


def test_json_round_trip(box: sandbox.Sandbox) -> None:
    assert registry.from_json(registry.to_json(box)) == box


def test_save_then_load(tmp_path: Path, box: sandbox.Sandbox) -> None:
    registry.save(tmp_path, box)

    assert registry.load(tmp_path, box.project) == box
    assert registry.all_sandboxes(tmp_path) == [box]


def test_load_unknown_returns_none(tmp_path: Path) -> None:
    assert registry.load(tmp_path, "ocs-nope") is None


def test_all_sandboxes_without_state_dir(tmp_path: Path) -> None:
    assert registry.all_sandboxes(tmp_path / "missing") == []


def test_password_is_stable_and_private(tmp_path: Path, box: sandbox.Sandbox) -> None:
    registry.save(tmp_path, box)

    first = registry.password(tmp_path, box.project)

    assert registry.password(tmp_path, box.project) == first
    assert (registry.sandbox_dir(tmp_path, box.project) / "password").stat().st_mode & 0o077 == 0


def test_remove_deletes_record(tmp_path: Path, box: sandbox.Sandbox) -> None:
    registry.save(tmp_path, box)

    registry.remove(tmp_path, box.project)

    assert registry.all_sandboxes(tmp_path) == []


def test_port_is_stable(tmp_path: Path, box: sandbox.Sandbox) -> None:
    registry.save(tmp_path, box)

    first = registry.port(tmp_path, box.project)

    assert registry.port(tmp_path, box.project) == first


def test_port_is_replaced_when_taken(tmp_path: Path, box: sandbox.Sandbox) -> None:
    registry.save(tmp_path, box)
    first = registry.port(tmp_path, box.project)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", first))
        sock.listen()
        second = registry.port(tmp_path, box.project)

    assert second != first
