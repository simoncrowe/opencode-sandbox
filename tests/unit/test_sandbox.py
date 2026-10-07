from pathlib import Path

import pytest

from opencode_sandbox import sandbox


@pytest.fixture
def box() -> sandbox.Sandbox:
    return sandbox.Sandbox(
        repo_root=Path("/home/me/git/My.Repo"),
        branch="feat/Add-Thing",
        sandbox_root=Path("/home/me/git/sandbox"),
    )


def test_clone_dir_nests_branch_under_repo(box: sandbox.Sandbox) -> None:
    assert box.clone_dir == Path("/home/me/git/sandbox/My.Repo/feat/Add-Thing")


def test_workdir_mirrors_repo_and_branch(box: sandbox.Sandbox) -> None:
    assert box.workdir == "/work/My.Repo/feat/Add-Thing"


def test_project_is_valid_compose_name(box: sandbox.Sandbox) -> None:
    assert box.project == "ocs-my-repo-feat-add-thing"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("simple", "simple"),
        ("UPPER_case", "upper_case"),
        ("a//b..c", "a-b-c"),
        ("-edge-", "edge"),
    ],
)
def test_slug(text: str, expected: str) -> None:
    assert sandbox.slug(text) == expected
