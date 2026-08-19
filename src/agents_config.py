"""Reading agents.toml — the one place that says which agents exist.

launch.py, start_agents.py and market/clear_retained.py all used to carry their
own copy-pasted agent list, which is how they drifted apart. They all read this
module instead now.

The file lives next to the repo root (../agents.toml relative to src/).
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "agents.toml"


@dataclass(frozen=True)
class AgentSpec:
    """One agent process: which prosumer it is and where its web UI listens."""

    profile_id: int
    agent_id: str
    port: int

    @property
    def is_seller(self) -> bool:
        return self.agent_id.startswith("S")


@dataclass(frozen=True)
class ServiceSpec:
    """An external service the launcher may start alongside the agents."""

    name: str
    enabled: bool
    path: Path
    command: list[str]
    venv: str | None = None
    health_url: str | None = None
    start_after_agents: bool = False

    @property
    def available(self) -> bool:
        return self.path.is_dir()


def _load(config_file: Path = CONFIG_FILE) -> dict:
    if not config_file.exists():
        raise FileNotFoundError(f"{config_file} is missing — it lists the agents to start.")
    with open(config_file, "rb") as f:
        return tomllib.load(f)


def load_agents(config_file: Path = CONFIG_FILE) -> list[AgentSpec]:
    """Every agent in agents.toml, in file order."""
    entries = _load(config_file).get("agents", [])
    if not entries:
        raise ValueError(f"{config_file} lists no agents.")

    agents = [
        AgentSpec(int(e["profile_id"]), str(e["agent_id"]), int(e["port"]))
        for e in entries
    ]

    for field, label in (("agent_id", "agent ids"), ("port", "ports")):
        seen = [getattr(a, field) for a in agents]
        if len(set(seen)) != len(seen):
            duplicates = sorted({v for v in seen if seen.count(v) > 1})
            raise ValueError(f"{config_file}: duplicate {label}: {duplicates}")
    return agents


def load_services(config_file: Path = CONFIG_FILE) -> list[ServiceSpec]:
    """The external services section, with paths resolved against the repo root."""
    root = config_file.parent
    services = []
    for name, entry in _load(config_file).get("services", {}).items():
        services.append(ServiceSpec(
            name=name,
            enabled=bool(entry.get("enabled", True)),
            path=(root / entry["path"]).resolve(),
            command=list(entry.get("command", [])),
            venv=entry.get("venv"),
            health_url=entry.get("health_url"),
            start_after_agents=bool(entry.get("start_after_agents", False)),
        ))
    return services


def load_broker(config_file: Path = CONFIG_FILE) -> tuple[str, int]:
    """(host, port) of the MQTT broker the agents and ASSUME share."""
    broker = _load(config_file).get("broker", {})
    return broker.get("host", "localhost"), int(broker.get("port", 1883))
