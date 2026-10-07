"""Copy provider credentials from the host's opencode into a sandbox server.

opencode v2 keeps credentials (e.g. GitHub Copilot OAuth tokens) in its
database, so they are transferred through the API rather than as files.
"""

import json
import subprocess

from opencode_sandbox import server


def host_credentials() -> list[dict[str, object]]:
    proc = subprocess.run(
        ["opencode", "api", "get", "/api/credential"],
        capture_output=True, text=True, check=True,
    )
    entries: list[dict[str, object]] = json.loads(proc.stdout)["data"]
    return entries


def to_create_input(entry: dict[str, object]) -> dict[str, object]:
    return {
        "id": entry["id"],
        "integrationID": entry["integrationID"],
        "label": entry.get("label", ""),
        "value": entry["value"],
        "activate": True,
    }


def plan(
    host: list[dict[str, object]], sandbox: list[dict[str, object]]
) -> tuple[list[str], list[dict[str, object]]]:
    """Return sandbox credential IDs to delete and credentials to create so the sandbox mirrors the host's active ones."""
    active = [entry for entry in host if entry.get("active")]
    active_ids = {entry["id"] for entry in active}
    stale = [str(entry["id"]) for entry in sandbox if entry["id"] in active_ids]
    return stale, [to_create_input(entry) for entry in active]


def copy_to_sandbox(base_url: str, *, password: str) -> list[str]:
    """Mirror the host's active credentials into the sandbox; return the integration IDs copied."""
    stale, create = plan(host_credentials(), server.credentials(base_url, password=password))
    for credential_id in stale:
        server.delete_credential(base_url, credential_id, password=password)
    for credential in create:
        server.create_credential(base_url, credential, password=password)
    return [str(credential["integrationID"]) for credential in create]
