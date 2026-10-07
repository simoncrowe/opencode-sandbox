from opencode_sandbox import credentials

COPILOT = {
    "id": "cred_1",
    "integrationID": "github-copilot",
    "label": "OAuth",
    "active": True,
    "value": {"type": "oauth", "refresh": "r", "access": "a", "expires": 0},
}
INACTIVE = {**COPILOT, "id": "cred_2", "active": False}


def test_plan_creates_active_host_credentials() -> None:
    stale, create = credentials.plan([COPILOT, INACTIVE], [])

    assert stale == []
    assert create == [{
        "id": "cred_1",
        "integrationID": "github-copilot",
        "label": "OAuth",
        "value": COPILOT["value"],
        "activate": True,
    }]


def test_plan_replaces_existing_copies() -> None:
    stale, create = credentials.plan([COPILOT], [{**COPILOT, "value": {"type": "oauth"}}])

    assert stale == ["cred_1"]
    assert [c["id"] for c in create] == ["cred_1"]


def test_plan_leaves_sandbox_only_credentials() -> None:
    stale, _ = credentials.plan([COPILOT], [{**COPILOT, "id": "cred_sandbox"}])

    assert stale == []
