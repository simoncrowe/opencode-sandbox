from pathlib import Path

import pytest

from opencode_sandbox import compose, sandbox


@pytest.fixture
def images() -> compose.Images:
    return compose.Images(opencode_version="2.0.24", uid=1000, gid=1000)


def test_environment_for_session(images: compose.Images) -> None:
    box = sandbox.Sandbox(name="ocs-git", directory=Path("/home/me/git"))

    env = compose.environment(images=images, box=box, seed_dir=Path("/tmp/seed"), password="pw")

    assert env["OCS_DIR"] == "/home/me/git"
    assert env["OCS_SEED_DIR"] == "/tmp/seed"
    assert env["OPENCODE_SERVER_PASSWORD"] == "pw"


def test_environment_for_build_uses_placeholders(images: compose.Images) -> None:
    env = compose.environment(images=images)

    assert env["OCS_DIR"] == compose.PLACEHOLDER_PATH
    assert env["OCS_SEED_DIR"] == compose.PLACEHOLDER_PATH
    assert env["OCS_OPENCODE_VERSION"] == "2.0.24"


@pytest.mark.parametrize(
    "output,expected",
    [
        ("127.0.0.1:32768\n", 32768),
        ("127.0.0.1:32768\n[::1]:32768\n", 32768),
        ("", None),
        (":0\n", 0),
    ],
)
def test_parse_port(output: str, expected: int | None) -> None:
    assert compose.parse_port(output) == expected


def test_parse_statuses_keeps_only_sandboxes() -> None:
    output = '[{"Name": "ocs-git-abc123", "Status": "running(2)"}, {"Name": "other", "Status": "running(1)"}]'

    assert compose.parse_statuses(output) == {"ocs-git-abc123": "running(2)"}
