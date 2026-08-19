"""Start every agent from agents.toml, without the external services.

Kept for the workflow the README describes (`python start_agents.py` from src/).
It is a thin wrapper around launch.py so there is only one agent list and one
piece of process-handling code — the old copy-pasted list here is gone, as is
the Windows-only CREATE_NEW_CONSOLE that made this script unusable elsewhere.

    python start_agents.py                 all agents, no services
    python start_agents.py --agents B_01   just one
"""
import runpy
import sys
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent.parent / "launch.py"

if __name__ == "__main__":
    sys.argv = [str(LAUNCHER), "--no-services", *sys.argv[1:]]
    runpy.run_path(str(LAUNCHER), run_name="__main__")
