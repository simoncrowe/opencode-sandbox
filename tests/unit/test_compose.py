import os
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


@pytest.mark.parametrize("docker,expected", [(False, ["compose.yaml"]), (True, ["compose.yaml", "compose.docker.yaml"])])
def test_environment_selects_compose_files(images: compose.Images, docker: bool, expected: list[str]) -> None:
    box = sandbox.Sandbox(name="ocs-git", directory=Path("/home/me/git"), docker=docker)

    env = compose.environment(images=images, box=box)

    assert [Path(path).name for path in env["COMPOSE_FILE"].split(os.pathsep)] == expected


@pytest.mark.parametrize("ca_bundle,expected", [(Path("/etc/ca.crt"), "/etc/ca.crt"), (None, os.devnull)])
def test_environment_ca_bundle(images: compose.Images, ca_bundle: Path | None, expected: str) -> None:
    assert compose.environment(images=images, ca_bundle=ca_bundle)["OCS_CA_BUNDLE"] == expected


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
