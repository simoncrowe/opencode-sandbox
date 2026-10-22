"""Identity of a sandbox: a host directory mounted into an isolated opencode container."""

import dataclasses
import hashlib
import re
from collections.abc import Iterable
from pathlib import Path

PROJECT_PREFIX = "ocs-"


@dataclasses.dataclass(frozen=True)
class Sandbox:
    name: str
    directory: Path
    ssh_keys: tuple[Path, ...] = ()

    @property
    def project(self) -> str:
        """Docker Compose project name."""
        return self.name


def slug(text: str) -> str:
    """Lowercase alphanumerics, '-' and '_', as Docker Compose project names require."""
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-")


def default_name(directory: Path) -> str:
    digest = hashlib.sha256(str(directory).encode()).hexdigest()[:6]
    return f"{PROJECT_PREFIX}{slug(directory.name) or 'root'}-{digest}"


def custom_name(name: str) -> str:
    base = slug(name.removeprefix(PROJECT_PREFIX))
    if not base:
        raise ValueError(f"{name!r} has no usable characters for a sandbox name")
    return PROJECT_PREFIX + base


def containing(path: Path, sandboxes: Iterable[Sandbox]) -> Sandbox | None:
    """Return the sandbox whose directory is `path` or one of its parents."""
    return next((box for box in sandboxes if path.is_relative_to(box.directory)), None)


def overlapping(directory: Path, sandboxes: Iterable[Sandbox]) -> Sandbox | None:
    """Return a sandbox whose directory strictly contains, or is strictly inside, `directory`."""
    return next(
        (
            box for box in sandboxes
            if box.directory != directory
            and (directory.is_relative_to(box.directory) or box.directory.is_relative_to(directory))
        ),
        None,
    )
