"""Identity and locations of a sandbox for one branch of one repository."""

import dataclasses
import re
from pathlib import Path


PROJECT_PREFIX = "ocs-"


@dataclasses.dataclass(frozen=True)
class Sandbox:
    repo_root: Path
    branch: str
    sandbox_root: Path

    @property
    def repo(self) -> str:
        return self.repo_root.name

    @property
    def clone_dir(self) -> Path:
        return self.sandbox_root / self.repo / self.branch

    @property
    def workdir(self) -> str:
        return f"/work/{self.repo}/{self.branch}"

    @property
    def project(self) -> str:
        """Docker Compose project name (lowercase alphanumerics, '-' and '_')."""
        return PROJECT_PREFIX + slug(f"{self.repo}-{self.branch}")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-")
