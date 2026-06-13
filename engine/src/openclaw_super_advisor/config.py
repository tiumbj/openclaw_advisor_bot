from __future__ import annotations

import json
from dataclasses import dataclass

from .constants import CONFIG_PATH, WORKSPACE_DIR


@dataclass(frozen=True)
class AgentPolicy:
    agent_id: str
    name: str
    workspace: str
    allowed_tools: tuple[str, ...]
    denied_tools: tuple[str, ...]


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_agent_policy() -> AgentPolicy:
    config = load_config()
    agents = config["agents"]["list"]
    if len(agents) != 1:
        raise ValueError("Expected exactly one configured agent.")
    agent = agents[0]
    tools = agent["tools"]
    return AgentPolicy(
        agent_id=agent["id"],
        name=agent["name"],
        workspace=agent["workspace"],
        allowed_tools=tuple(tools["allow"]),
        denied_tools=tuple(tools["deny"]),
    )


def validate_config_paths() -> None:
    config = load_config()
    defaults_workspace = config["agents"]["defaults"]["workspace"]
    if defaults_workspace != str(WORKSPACE_DIR):
        raise ValueError("agents.defaults.workspace must point to the clean workspace.")
