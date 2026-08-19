"""Start the whole MAS4TE stack: the external services and every agent.

    python launch.py --check      report what is ready and what is missing
    python launch.py              start everything in agents.yml and supervise it
    python launch.py --agents B_01,S_01 --no-services
    python launch.py --terminals          one console window per agent

Which agents run, and where the services they depend on live, is configured in
agents.yml — not in this file.

Replaces the old Windows-only launcher (CREATE_NEW_CONSOLE, cmd /k,
venv/Scripts/*.exe): processes are started head-less on every platform, their
output is tee'd into logs/, and Ctrl-C shuts the whole tree down in order.
A service whose directory is missing is reported and skipped instead of taking
the launch down with it.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs"

sys.path.insert(0, str(SRC))

from agents_config import (  # noqa: E402  (needs SRC on the path first)
    AgentSpec,
    ServiceSpec,
    load_agents,
    load_broker,
    load_services,
)

IS_WINDOWS = os.name == "nt"
AGENT_BOOT_TIMEOUT = 90          # seconds to wait for an agent's web UI
SHUTDOWN_GRACE = 10              # seconds between SIGTERM and SIGKILL


# --------------------------------------------------------------------------
# Process handling
# --------------------------------------------------------------------------
@dataclass
class Child:
    name: str
    process: subprocess.Popen
    log_path: Path
    log_file: object

    @property
    def alive(self) -> bool:
        return self.process.poll() is None


def _spawn(name: str, command: list[str], cwd: Path, env: dict | None = None,
           terminal: bool = False) -> Child:
    """Start one child process.

    Head-less (the default) its output is captured into logs/<name>.log. With
    `terminal`, it gets its own console window instead and writes the same lines
    to that log file itself, via LOG_FILE (see src/logging_setup.py).
    """
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"

    if terminal:
        wrapped = terminal_command(name, command)
        if wrapped is None:
            print(f"      no terminal emulator found — running {name} head-less")
        else:
            env = {**(env or {}), "LOG_FILE": str(log_path)}
            process = subprocess.Popen(
                wrapped, cwd=str(cwd), env={**os.environ, **env},
                **({"creationflags": subprocess.CREATE_NEW_CONSOLE} if IS_WINDOWS
                   else {"start_new_session": True}),
            )
            return Child(name=name, process=process, log_path=log_path,
                         log_file=open(os.devnull, "w"))

    log_file = open(log_path, "w", buffering=1, encoding="utf-8", errors="replace")

    # A separate process group so Ctrl-C in this terminal doesn't race us to the
    # children — the supervisor decides when they stop, and in which order.
    if IS_WINDOWS:
        extra = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        extra = {"start_new_session": True}

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        stdout=log_file,
        stderr=subprocess.STDOUT,
        **extra,
    )
    return Child(name=name, process=process, log_path=log_path, log_file=log_file)


# Terminal emulators we know how to drive, in the order we prefer them. Each
# entry builds the argv that opens a window titled `title` running `inner`
# (a shell command line).
_LINUX_TERMINALS = [
    ("gnome-terminal", lambda title, inner: ["gnome-terminal", f"--title={title}", "--", "bash", "-c", inner]),
    ("konsole",        lambda title, inner: ["konsole", "-p", f"tabtitle={title}", "-e", "bash", "-c", inner]),
    ("xfce4-terminal", lambda title, inner: ["xfce4-terminal", f"--title={title}", "-x", "bash", "-c", inner]),
    ("xterm",          lambda title, inner: ["xterm", "-T", title, "-e", "bash", "-c", inner]),
    ("x-terminal-emulator", lambda title, inner: ["x-terminal-emulator", "-T", title, "-e", "bash", "-c", inner]),
]


def terminal_command(title: str, command: list[str]) -> list[str] | None:
    """Wrap a command so it runs in its own visible terminal window.

    Returns None when there is no terminal to use, so the caller can fall back
    to running head-less instead of failing.
    """
    if IS_WINDOWS:
        # `cmd /k` keeps the window open after the process exits, which is the
        # whole point when you are looking for the traceback that killed it.
        return ["cmd", "/k", "title", title, "&", *command]

    inner = shlex.join(command) + "; echo; echo '--- exited, press enter to close ---'; read"
    for name, build in _LINUX_TERMINALS:
        if shutil.which(name):
            return build(title, inner)
    return None


def _terminate(child: Child) -> None:
    """Ask a child (and anything it spawned) to stop, then insist."""
    if not child.alive:
        return
    try:
        if IS_WINDOWS:
            child.process.terminate()
        else:
            os.killpg(os.getpgid(child.process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        return

    try:
        child.process.wait(timeout=SHUTDOWN_GRACE)
    except subprocess.TimeoutExpired:
        print(f"  {child.name} ignored SIGTERM — killing")
        try:
            if IS_WINDOWS:
                child.process.kill()
            else:
                os.killpg(os.getpgid(child.process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def shutdown(children: list[Child]) -> None:
    print("\nShutting down...")
    for child in reversed(children):          # services started last stop first
        print(f"  stopping {child.name}")
        _terminate(child)
        child.log_file.close()
    print("All stopped.")


# --------------------------------------------------------------------------
# Health checks
# --------------------------------------------------------------------------
def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 500
    except urllib.error.HTTPError as error:
        return error.code < 500          # a 404 still means something is listening
    except (urllib.error.URLError, OSError):
        return False


def wait_for(check, timeout: float, interval: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(interval)
    return False


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _installed_from(dist) -> str:
    """Where a distribution was installed from, per PEP 610 direct_url.json."""
    import json

    raw = dist.read_text("direct_url.json")
    if raw is None:
        return "installed from an index or an unknown source — expected a git pin "\
               "or an editable checkout; reinstall with `pip install -e .`"

    info = json.loads(raw)
    url = info.get("url", "?")
    if "vcs_info" in info:
        vcs = info["vcs_info"]
        revision = vcs.get("requested_revision", "?")
        commit = (vcs.get("commit_id") or "")[:8]
        return f"pinned to {url} @ {revision} ({commit})"
    if info.get("dir_info", {}).get("editable"):
        return f"editable checkout at {url}"
    return f"installed from {url}"


def service_python(service: ServiceSpec) -> Path | None:
    """The interpreter a service runs under — its own venv, never ours.

    Each service has dependencies we do not have and should not have: the
    battery simulation needs fmpy, Chronos needs the forecasting stack. Falling
    back to the agent's interpreter when a service's venv is missing does not
    make the service run, it just turns a clear "no venv" into a confusing
    ModuleNotFoundError deep inside someone else's code.

    Returns None when the service declares a venv that is not there. A service
    that declares none at all (venv: null) shares our interpreter on purpose.
    """
    if not service.venv:
        return Path(sys.executable)

    # Accept the usual alternative name, so a checkout using .venv still works.
    for name in dict.fromkeys([service.venv, "venv", ".venv"]):
        for candidate in (service.path / name / "bin" / "python",
                          service.path / name / "Scripts" / "python.exe"):
            if candidate.exists():
                return candidate
    return None


# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
def preflight(agents: list[AgentSpec], services: list[ServiceSpec]) -> bool:
    """Report everything the stack needs. Returns True if agents can start."""
    ok = True
    print("Python      :", sys.executable)

    print("\nDependencies")
    missing = []
    for module in ("fastapi", "uvicorn", "pandas", "paho.mqtt.client", "openai",
                   "yaml", "requests", "battery_utility_calculator"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        ok = False
        print(f"  MISSING: {', '.join(missing)}")
        print("  fix: uv pip install -e .            (or: pip install -e .)")
    else:
        print("  all installed")

    print("\nBattery Utility Calculator")
    try:
        import battery_utility_calculator as buc
        from importlib.metadata import distribution, version

        print(f"  version {version('battery-utility-calculator')}")
        # PEP 610: pip and uv record where a package actually came from.
        origin = _installed_from(distribution("battery-utility-calculator"))
        print(f"  {origin}")
        print(f"  imported from {Path(buc.__file__).resolve().parent}")
    except ImportError:
        ok = False
        print("  NOT INSTALLED")
        print("  fix: pip install -e .")

    print("\nProsumer data")
    from config import DATA_DIR                    # noqa: PLC0415  (honours MAS4TE_DATA_DIR)

    if not DATA_DIR.is_dir():
        ok = False
        print(f"  MISSING: {DATA_DIR}")
        print("  fix: copy the git-ignored data/ directory (profiles, prices, forecasts) into src/,")
        print("       or point MAS4TE_DATA_DIR at where it already lives")
    else:
        from prosumer import load_profile          # noqa: PLC0415  (needs data/ to exist)

        print(f"  using {DATA_DIR}")
        broken = []
        for agent in agents:
            try:
                load_profile(agent.profile_id)
            except Exception as error:
                broken.append(f"{agent.agent_id} (profile {agent.profile_id}): {error}")
        if broken:
            ok = False
            print("  profiles that will not load:")
            for line in broken:
                print(f"    {line}")
        else:
            print(f"  all {len(agents)} profiles load")

    print("\nMQTT broker")
    host, port = load_broker()
    if tcp_open(host, port):
        print(f"  reachable at {host}:{port}")
    else:
        # Not fatal: the agents connect asynchronously and retry, so they can
        # start now and join the market when the broker comes up.
        print(f"  NOT reachable at {host}:{port} — agents will start and keep retrying")
        print("  fix: start an MQTT broker, e.g. `mosquitto -p 1883`")

    print("\nCredentials")
    if os.environ.get("MISTRAL_API_KEY") or (SRC / "mas4te_mistral_api_key.yml").exists():
        print("  mistral   found — chat assistant enabled")
    else:
        print("  mistral   missing — chat falls back to the offline backend (trading is unaffected)")

    if (SRC / "mas4te_restapi_key.yml").exists():
        print("  brp api   found — buyers can send their schedule")
    elif any(not agent.agent_id.startswith("S") for agent in agents):
        print("  brp api   MISSING — buyers will fail at the last clearing step")
    else:
        print("  brp api   missing — not needed, no buyers configured")

    if not _env_flag("MQTT_ONLINE"):
        print("  battery   not needed — MQTT_ONLINE is off (local broker)")
    elif (SRC / "mas4tecontroller_mqtt_credentials.yml").exists():
        print("  battery   found — live broker credentials present")
    else:
        ok = False
        print("  battery   MISSING — MQTT_ONLINE is on but there are no credentials")

    print("  templates for all three: src/*.example.yml")

    print("\nExternal services")
    for service in services:
        if not service.enabled:
            print(f"  {service.name:9} disabled in agents.yml")
        elif service.available:
            interpreter = service_python(service)
            if interpreter is None:
                ok = False
                print(f"  {service.name:9} found at {service.path}, but its virtualenv "
                      f"({service.venv}) is missing")
                print(f"  {'':9} it needs its own dependencies — ours cannot run it")
            elif interpreter == Path(sys.executable):
                print(f"  {service.name:9} found at {service.path}, sharing our interpreter")
            else:
                print(f"  {service.name:9} found at {service.path}, using {interpreter}")
        else:
            print(f"  {service.name:9} MISSING at {service.path} — will be skipped")

    print("\nAgents")
    for agent in agents:
        busy = " (PORT ALREADY IN USE)" if tcp_open("127.0.0.1", agent.port) else ""
        if busy:
            ok = False
        print(f"  {agent.agent_id:6} profile {agent.profile_id:<4} -> http://localhost:{agent.port}{busy}")

    print("\n" + ("READY" if ok else "NOT READY — fix the items above"))
    return ok


# -------------------------------------------------------------------------
# Ensure proper closing of previous run
# -------------------------------------------------------------------------
def clear_retained_status() -> None:
    """Clear leftover retained MQTT messages before starting (see clear_retained.py)."""
    subprocess.run([sys.executable, str(SRC / "market/clear_retained.py")], cwd=SRC)

# --------------------------------------------------------------------------
# Starting things
# --------------------------------------------------------------------------
def start_service(service: ServiceSpec, terminal: bool = False) -> Child | None:
    if not service.enabled:
        print(f"SKIP  {service.name}: disabled in agents.yml")
        return None
    if not service.available:
        print(f"SKIP  {service.name}: {service.path} does not exist")
        return None

    interpreter = service_python(service)
    if interpreter is None:
        print(f"SKIP  {service.name}: no interpreter — expected a virtualenv at "
              f"{service.path / service.venv}")
        print(f"      {service.name} has its own dependencies (the battery simulation "
              f"needs fmpy, Chronos its forecasting stack); ours will not do.")
        print(f"      fix: create it in {service.path}, or set enabled: false in "
              f"agents.yml and start {service.name} yourself.")
        return None

    command = [str(interpreter), *service.command]
    child = _spawn(service.name, command, cwd=service.path, terminal=terminal)
    print(f"START {service.name} (pid {child.process.pid}) -> {child.log_path}")

    if service.health_url:
        if wait_for(lambda: http_ok(service.health_url), timeout=60):
            print(f"      {service.name} is answering on {service.health_url}")
        else:
            print(f"      WARNING: {service.name} did not answer on {service.health_url} in 60s "
                  f"(see {child.log_path})")
    return child


def start_agent(agent: AgentSpec, terminal: bool = False) -> Child:
    command = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1", "--port", str(agent.port),
    ]
    broker_host, broker_port = load_broker()
    env = {
        "PROFILE_ID": str(agent.profile_id),
        "AGENT_ID": agent.agent_id,
        # agents.yml is the single source of truth for the broker, so config.py
        # picks it up from here rather than from its own default.
        "MQTT_LOCAL_BROKER": broker_host,
        "MQTT_LOCAL_PORT": str(broker_port),
    }
    child = _spawn(agent.agent_id, command, cwd=SRC, env=env, terminal=terminal)
    print(f"START {agent.agent_id:6} profile {agent.profile_id:<4} "
          f"pid {child.process.pid} -> http://localhost:{agent.port}"
          f"{'  (own window)' if terminal else ''}")
    return child


def wait_for_agents(agents: list[AgentSpec], children: list[Child]) -> bool:
    """Block until every agent answers on /pipeline/status, or one dies."""
    by_name = {child.name: child for child in children}
    all_up = True

    for agent in agents:
        child = by_name.get(agent.agent_id)
        url = f"http://127.0.0.1:{agent.port}/pipeline/status"

        def ready(url=url, child=child):
            if child is not None and not child.alive:
                return True                    # died: stop waiting, report below
            return http_ok(url)

        wait_for(ready, timeout=AGENT_BOOT_TIMEOUT)

        if child is not None and not child.alive:
            all_up = False
            print(f"FAILED {agent.agent_id} exited with code {child.process.returncode}")
            print(_tail(child.log_path))
        elif http_ok(url):
            print(f"UP    {agent.agent_id} on http://localhost:{agent.port}")
        else:
            all_up = False
            print(f"SLOW  {agent.agent_id} not answering after {AGENT_BOOT_TIMEOUT}s "
                  f"(see {child.log_path if child else '?'})")
    return all_up


def _tail(path: Path, lines: int = 15) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "  (no log)"
    return "\n".join(f"  | {line}" for line in content[-lines:])


def supervise(children: list[Child]) -> None:
    """Watch the children until Ctrl-C, reporting any that die."""
    print("\nRunning. Ctrl-C to stop everything.\n")
    reported: set[str] = set()
    while True:
        time.sleep(1)
        for child in children:
            if not child.alive and child.name not in reported:
                reported.add(child.name)
                print(f"EXIT  {child.name} stopped with code {child.process.returncode}")
                print(_tail(child.log_path))
        if all(not child.alive for child in children):
            print("\nEvery process has exited.")
            return


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="only report what is ready and what is missing")
    parser.add_argument("--agents", default=None,
                        help="comma-separated agent ids to start (default: all of agents.yml)")
    parser.add_argument("--no-services", "--only-agents", dest="no_services",
                        action="store_true", help="do not start Chronos, battery or ASSUME")
    parser.add_argument("--terminals", action="store_true",
                        help="give each agent its own console window (it still "
                             "writes logs/<AGENT_ID>.log)")
    parser.add_argument("--force", action="store_true",
                        help="start even if the preflight check fails")
    args = parser.parse_args()

    agents = load_agents()
    if args.agents:
        wanted = {name.strip() for name in args.agents.split(",") if name.strip()}
        unknown = wanted - {agent.agent_id for agent in agents}
        if unknown:
            print(f"Unknown agent ids: {sorted(unknown)}", file=sys.stderr)
            return 2
        agents = [agent for agent in agents if agent.agent_id in wanted]

    services = [] if args.no_services else load_services()

    ready = preflight(agents, services)
    if args.check:
        return 0 if ready else 1
    if not ready and not args.force:
        print("\nRefusing to start. Fix the above, or re-run with --force.")
        return 1

    if len(agents) > 3:
        # One agent is one uvicorn process plus an optimiser run per market
        # opening; the full roster needs a machine that can take it.
        print(f"\nNOTE: starting {len(agents)} agents ({len(agents)} processes). "
              f"On a small machine use --agents B_01,S_01 instead.")

    print("\n" + "-" * 70)
    children: list[Child] = []
    try:
        clear_retained_status()

        for service in services:
            if not service.start_after_agents:
                child = start_service(service, terminal=args.terminals)
                if child:
                    children.append(child)

        for agent in agents:
            children.append(start_agent(agent, terminal=args.terminals))

        print("\nWaiting for the agents to come up...")
        wait_for_agents(agents, children)

        # ASSUME drives the market clock, so it goes last: the agents are
        # subscribed by now and won't miss the first market_open.
        for service in services:
            if service.start_after_agents:
                child = start_service(service, terminal=args.terminals)
                if child:
                    children.append(child)

        supervise(children)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown(children)
    return 0


if __name__ == "__main__":
    sys.exit(main())
