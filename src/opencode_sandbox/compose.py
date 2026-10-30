"""Thin wrapper around `docker compose` for the packaged compose project."""

import dataclasses
import importlib.metadata
import importlib.resources
import json
import os
import subprocess
from pathlib import Path

from opencode_sandbox import sandbox

PLACEHOLDER_PATH = "/nonexistent"
CACHE_VOLUME = "opencode-sandbox-cache"
DOCKER_RUNTIME = "sysbox-runc"


@dataclasses.dataclass(frozen=True)
class Images:
    opencode_version: str
    uid: int
    gid: int

    @property
    def opencode(self) -> str:
        return f"localhost/opencode-sandbox:{self.opencode_version}"

    @property
    def gateway(self) -> str:
        return f"localhost/opencode-sandbox-gateway:{package_version()}"


def package_version() -> str:
    return importlib.metadata.version("opencode-sandbox")


def resources_dir() -> Path:
    return Path(str(importlib.resources.files("opencode_sandbox") / "resources"))


def compose_files(box: sandbox.Sandbox | None) -> list[Path]:
    files = [resources_dir() / "compose.yaml"]
    if box and box.docker:
        files.append(resources_dir() / "compose.docker.yaml")
    return files


def environment(
    *,
    images: Images,
    box: sandbox.Sandbox | None = None,
    seed_dir: Path | None = None,
    password: str = "",
    port: int = 0,
    ca_bundle: Path | None = None,
) -> dict[str, str]:
    """Variables interpolated into compose.yaml; paths are placeholders when only building."""
    return {
        "COMPOSE_FILE": os.pathsep.join(str(path) for path in compose_files(box)),
        "OCS_OPENCODE_VERSION": images.opencode_version,
        "OCS_GATEWAY_TAG": package_version(),
        "OCS_UID": str(images.uid),
        "OCS_GID": str(images.gid),
        "OCS_DIR": str(box.directory) if box else PLACEHOLDER_PATH,
        "OCS_SEED_DIR": str(seed_dir) if seed_dir else PLACEHOLDER_PATH,
        "OPENCODE_SERVER_PASSWORD": password,
        "OCS_PORT": str(port),
        "OCS_CA_BUNDLE": str(ca_bundle) if ca_bundle else os.devnull,
    }


def command(project: str | None, *args: str) -> list[str]:
    cmd = ["docker", "compose", "--progress", "quiet"]
    if project:
        cmd += ["-p", project]
    return [*cmd, *args]


def run(
    project: str | None,
    *args: str,
    env: dict[str, str],
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command(project, *args),
        env={**os.environ, **env},
        capture_output=capture,
        text=True,
        check=check,
    )


def ensure_cache_volume() -> None:
    subprocess.run(
        ["docker", "volume", "create", CACHE_VOLUME], capture_output=True, check=True
    )


def has_docker_runtime() -> bool:
    proc = subprocess.run(
        ["docker", "info", "--format", "{{json .Runtimes}}"],
        capture_output=True, text=True, check=True,
    )
    return DOCKER_RUNTIME in json.loads(proc.stdout or "{}")


def images_exist(images: Images) -> bool:
    return all(
        subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, check=False
        ).returncode == 0
        for image in (images.opencode, images.gateway)
    )


def published_port(project: str, *, env: dict[str, str]) -> int | None:
    proc = run(project, "port", "gateway", "4096", env=env, capture=True, check=False)
    return parse_port(proc.stdout) if proc.returncode == 0 else None


def parse_port(output: str) -> int | None:
    address = output.strip().splitlines()[0] if output.strip() else ""
    _, _, port = address.rpartition(":")
    return int(port) if port.isdigit() else None


def is_running(project: str, *, env: dict[str, str]) -> bool:
    proc = run(project, "ps", "-q", env=env, capture=True, check=False)
    return bool(proc.stdout.strip())


def project_statuses() -> dict[str, str]:
    """Map each sandbox compose project to its status, e.g. 'running(2)'."""
    proc = subprocess.run(
        ["docker", "compose", "ls", "-a", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    return parse_statuses(proc.stdout)


def parse_statuses(output: str) -> dict[str, str]:
    return {
        entry["Name"]: entry.get("Status", "")
        for entry in json.loads(output or "[]")
        if entry["Name"].startswith(sandbox.PROJECT_PREFIX)
    }
