from pathlib import Path

import pytest

from opencode_sandbox import session


def test_merge_allowlists_joins_with_single_newlines() -> None:
    assert session.merge_allowlists(["a\n", "b"]) == "a\nb\n"


@pytest.fixture
def host_files(tmp_path: Path) -> dict[str, Path]:
    default = tmp_path / "default-allowlist"
    default.write_text("^pypi\\.org$\n")
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
    return {"default": default, "config": config, "agents": agents_link}


def test_write_seed_stages_allowlist_and_config(
    tmp_path: Path, host_files: dict[str, Path]
) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        allowlists=[host_files["default"], tmp_path / "missing"],
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
    )

    assert (seed / "allowlist").read_text() == "^pypi\\.org$\n"
    assert sorted(p.name for p in (seed / "config").iterdir()) == ["AGENTS.md"]


def test_write_seed_copies_agents_through_symlink_without_swap_files(
    tmp_path: Path, host_files: dict[str, Path]
) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()

    session.write_seed(
        seed,
        allowlists=[host_files["default"]],
        config_dir=host_files["config"],
        agents_dir=host_files["agents"],
    )

    skill_dir = seed / "agents" / "skills" / "python-design"
    assert not (seed / "agents").is_symlink()
    assert [p.name for p in skill_dir.iterdir()] == ["SKILL.md"]
