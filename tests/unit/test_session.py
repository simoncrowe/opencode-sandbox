from pathlib import Path

import pytest

from opencode_sandbox import session


@pytest.fixture
def host_files(tmp_path: Path) -> dict[str, Path]:
    config = tmp_path / "config"
    config.mkdir()
    (config / "AGENTS.md").write_text("be nice")
    (config / "service.json").write_text("{}")
    agents = tmp_path / "dotfiles-agents"
    (agents / "skills" / "python-design").mkdir(parents=True)
    (agents / "skills" / "python-design" / "SKILL.md").write_text("# skill")
    (agents / "skills" / "python-design" / ".SKILL.md.swp").write_text("swap")
    agents_link = tmp_path / ".agents"
    agents_link.symlink_to(agents)
    return {"config": config, "agents": agents_link}


def test_write_seed_stages_config(
    tmp_path: Path, host_files: dict[str, Path]
) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
        known_hosts=tmp_path / "missing",
        git_identity={},
    )

    assert sorted(p.name for p in (seed / "config").iterdir()) == ["AGENTS.md"]


def test_write_seed_copies_agents_through_symlink_without_swap_files(
    tmp_path: Path, host_files: dict[str, Path]
) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
        known_hosts=tmp_path / "missing",
        git_identity={},
    )

    skill_dir = seed / "agents" / "skills" / "python-design"
    assert not (seed / "agents").is_symlink()
    assert [p.name for p in skill_dir.iterdir()] == ["SKILL.md"]


def test_write_seed_copies_ca_bundle(tmp_path: Path, host_files: dict[str, Path]) -> None:
    bundle = tmp_path / "bundle.crt"
    bundle.write_text("-----BEGIN CERTIFICATE-----\n")
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
        known_hosts=tmp_path / "missing",
        git_identity={},
        ca_bundle=bundle,
    )

    assert (seed / "ca-certificates.crt").read_text() == bundle.read_text()


def test_write_seed_copies_mcp_auth(tmp_path: Path, host_files: dict[str, Path]) -> None:
    mcp_auth = tmp_path / "mcp-auth.json"
    mcp_auth.write_text('{"atlassian": {}}')
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
        known_hosts=tmp_path / "missing",
        git_identity={},
        mcp_auth=mcp_auth,
    )

    assert (seed / "mcp-auth.json").read_text() == '{"atlassian": {}}'


@pytest.fixture
def ssh_files(tmp_path: Path) -> dict[str, Path]:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"id_{name}").write_text(f"key {name}")
    (tmp_path / "known_hosts").write_text("bitbucket.org ssh-ed25519 AAAA\n")
    return {
        "a": tmp_path / "a" / "id_a",
        "b": tmp_path / "b" / "id_b",
        "known_hosts": tmp_path / "known_hosts",
    }


def test_write_ssh_seed_copies_keys_and_known_hosts(tmp_path: Path, ssh_files: dict[str, Path]) -> None:
    ssh_dir = tmp_path / "ssh"

    session.write_ssh_seed(ssh_dir, keys=[ssh_files["a"], ssh_files["b"]], known_hosts=ssh_files["known_hosts"])

    assert sorted(p.name for p in ssh_dir.iterdir()) == ["config", "id_a", "id_b", "known_hosts"]
    assert (ssh_dir / "id_a").read_text() == "key a"
    assert ssh_dir.stat().st_mode & 0o077 == 0


def test_write_ssh_seed_refuses_duplicate_key_names(tmp_path: Path, ssh_files: dict[str, Path]) -> None:
    other = tmp_path / "c" / "id_a"
    other.parent.mkdir()
    other.write_text("other")

    with pytest.raises(session.SessionError, match="id_a"):
        session.write_ssh_seed(tmp_path / "ssh", keys=[ssh_files["a"], other], known_hosts=ssh_files["known_hosts"])


def test_ssh_config_uses_only_given_keys() -> None:
    assert session.ssh_config(["id_a", "id_b"]) == (
        "Host *\n"
        "    IdentitiesOnly yes\n"
        "    IdentityFile ~/.ssh/id_a\n"
        "    IdentityFile ~/.ssh/id_b\n"
    )


def test_gitconfig_sets_user() -> None:
    assert session.gitconfig({"name": "Me", "email": "me@example.com"}) == (
        "[user]\n    name = Me\n    email = me@example.com\n"
    )


def test_gitconfig_empty_without_identity() -> None:
    assert session.gitconfig({}) == ""
