"""Persisted records of sandboxes, so detached sessions can be found from any shell.

Each sandbox gets a directory under the state root holding its identity, the
web UI password and the seed files mounted into its containers.
"""

import json
import os
import secrets
import shutil
import socket
from pathlib import Path

from opencode_sandbox import sandbox

RECORD = "sandbox.json"


def default_root() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "opencode-sandbox"


def sandbox_dir(root: Path, project: str) -> Path:
    return root / project


def seed_dir(root: Path, project: str) -> Path:
    return sandbox_dir(root, project) / "seed"


def to_json(box: sandbox.Sandbox) -> str:
    return json.dumps(
        {
            "name": box.name,
            "directory": str(box.directory),
            "ssh_keys": [str(key) for key in box.ssh_keys],
        },
        indent=2,
    )


def from_json(text: str) -> sandbox.Sandbox:
    data = json.loads(text)
    return sandbox.Sandbox(
        name=data["name"],
        directory=Path(data["directory"]),
        ssh_keys=tuple(Path(key) for key in data["ssh_keys"]),
    )


def save(root: Path, box: sandbox.Sandbox) -> None:
    directory = sandbox_dir(root, box.project)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / RECORD).write_text(to_json(box))


def load(root: Path, project: str) -> sandbox.Sandbox | None:
    record = sandbox_dir(root, project) / RECORD
    return from_json(record.read_text()) if record.is_file() else None


def all_sandboxes(root: Path) -> list[sandbox.Sandbox]:
    if not root.is_dir():
        return []
    return [from_json(record.read_text()) for record in sorted(root.glob(f"*/{RECORD}"))]


def password(root: Path, project: str) -> str:
    """Return the sandbox's web UI password, creating it on first use."""
    path = sandbox_dir(root, project) / "password"
    if not path.is_file():
        path.touch(mode=0o600)
        path.write_text(secrets.token_urlsafe(32))
    return path.read_text().strip()


def port(root: Path, project: str) -> int:
    """Return the sandbox's host port, keeping it stable so browser sign-ins survive restarts."""
    path = sandbox_dir(root, project) / "port"
    saved = int(path.read_text()) if path.is_file() else None
    if saved is None or not is_port_free(saved):
        saved = free_port()
        path.write_text(str(saved))
    return saved


def is_port_free(number: int) -> bool:
    with socket.socket() as sock:
        # Ignore TIME_WAIT connections left by the previous run; only a listener makes the port unavailable.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", number))
        except OSError:
            return False
    return True


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        number: int = sock.getsockname()[1]
        return number


def remove(root: Path, project: str) -> None:
    shutil.rmtree(sandbox_dir(root, project), ignore_errors=True)
