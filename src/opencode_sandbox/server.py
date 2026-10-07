"""Talk to a running opencode server: wait until it is up and create sign-in links."""

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request

USERNAME = "opencode"


def _request(url: str, *, password: str, method: str = "GET", body: object = None) -> bytes:
    token = base64.b64encode(f"{USERNAME}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=5) as response:
        result: bytes = response.read()
        return result


def wait_until_ready(base_url: str, *, password: str, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _request(f"{base_url}/api/info", password=password)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.5)
        else:
            return True
    return False


def sign_in_link(base_url: str, *, password: str) -> str:
    """Return a single-use link that signs a browser in to the web UI."""
    body = _request(f"{base_url}/api/pair", password=password, method="POST")
    code = json.loads(body)["code"]
    return f"{base_url}/auth/connect/{code}"


def credentials(base_url: str, *, password: str) -> list[dict[str, object]]:
    body = json.loads(_request(f"{base_url}/api/credential", password=password))
    entries: list[dict[str, object]] = body["data"]
    return entries


def delete_credential(base_url: str, credential_id: str, *, password: str) -> None:
    _request(f"{base_url}/api/credential/{credential_id}", password=password, method="DELETE")


def create_credential(base_url: str, credential: dict[str, object], *, password: str) -> None:
    _request(f"{base_url}/api/credential", password=password, method="POST", body=credential)


def has_sessions(base_url: str, directory: str, *, password: str) -> bool:
    query = urllib.parse.urlencode({"directory": directory, "limit": 1})
    body = json.loads(_request(f"{base_url}/api/session?{query}", password=password))
    return bool(body["data"])


def create_session(base_url: str, directory: str, *, title: str, password: str) -> None:
    body = {"title": title, "location": {"directory": directory}}
    _request(f"{base_url}/api/session", password=password, method="POST", body=body)


def project_id(base_url: str, directory: str, *, password: str) -> str | None:
    projects = json.loads(_request(f"{base_url}/api/project", password=password))
    return next((str(p["id"]) for p in projects if p["canonical"] == directory), None)


def rename_project(base_url: str, project: str, *, name: str, password: str) -> None:
    _request(f"{base_url}/api/project/{project}", password=password, method="PATCH", body={"name": name})
