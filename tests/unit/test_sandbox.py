from pathlib import Path

import pytest

from opencode_sandbox import sandbox


@pytest.fixture
def boxes() -> list[sandbox.Sandbox]:
    return [
        sandbox.Sandbox(name="ocs-git", directory=Path("/home/me/git")),
        sandbox.Sandbox(name="ocs-notes", directory=Path("/home/me/notes")),
    ]


def test_default_name_is_valid_and_unique_per_path() -> None:
    first = sandbox.default_name(Path("/home/me/git/My.Repo"))
    second = sandbox.default_name(Path("/srv/My.Repo"))

    assert first.startswith("ocs-my-repo-")
    assert len(first) == len("ocs-my-repo-") + 6
    assert first != second


def test_default_name_for_root() -> None:
    assert sandbox.default_name(Path("/")).startswith("ocs-root-")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("work", "ocs-work"),
        ("ocs-work", "ocs-work"),
        ("My Work", "ocs-my-work"),
    ],
)
def test_custom_name(name: str, expected: str) -> None:
    assert sandbox.custom_name(name) == expected


def test_custom_name_without_usable_characters() -> None:
    with pytest.raises(ValueError, match="no usable characters"):
        sandbox.custom_name("!!!")


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


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/home/me/git", "ocs-git"),
        ("/home/me/git/platform/touchsurgery", "ocs-git"),
        ("/home/me/gitlab", None),
        ("/home/me", None),
    ],
)
def test_containing(boxes: list[sandbox.Sandbox], path: str, expected: str | None) -> None:
    found = sandbox.containing(Path(path), boxes)

    assert (found.name if found else None) == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/home/me/git", None),
        ("/home/me/git/platform", "ocs-git"),
        ("/home/me", "ocs-git"),
        ("/home/me/gitlab", None),
    ],
)
def test_overlapping(boxes: list[sandbox.Sandbox], path: str, expected: str | None) -> None:
    found = sandbox.overlapping(Path(path), boxes)

    assert (found.name if found else None) == expected
