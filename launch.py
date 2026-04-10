import os
import subprocess
import sys
import time

print(sys.executable)


BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))

# Chronos
chronos_cwd     = os.path.join(ROOT, "chronos_forecaster")
chronos_uvicorn = os.path.join(ROOT, "chronos_forecaster", "venv", "Scripts", "uvicorn.exe")

subprocess.Popen(
    [chronos_uvicorn, "src.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=chronos_cwd,
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("Chronos started!")

# Assume
assume_cwd    = os.path.join(ROOT, "assume", "assume", "mas4te")
assume_python = os.path.join(assume_cwd, "venv", "Scripts", "python.exe")

subprocess.Popen(
    [assume_python, "simulation.py"],
    cwd=assume_cwd,
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("Assume started!")

# Battery
battery_cwd    = os.path.join(ROOT, "mas4te_battery", "battery_simulation")
battery_python = os.path.join(ROOT, "mas4te_battery", "battery_simulation", "venv", "Scripts", "python.exe")

# use battery venv if it exists, otherwise fall back to system python
if os.path.exists(battery_python):
    battery_exe = battery_python
else:
    battery_exe = "python"

subprocess.Popen(
    [battery_exe, "main_api_mqtt.py"],
    cwd=battery_cwd,
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("Battery started!")

# Wait for everything to boot before starting agents
print("\nWaiting 3s for services to boot...")
time.sleep(3)

# Agents
agents = [
    {"PROFILE_ID": "3",   "AGENT_ID": "B_01"},
    {"PROFILE_ID": "152", "AGENT_ID": "B_02"},
    {"PROFILE_ID": "84",  "AGENT_ID": "S_01"},
    {"PROFILE_ID": "92",  "AGENT_ID": "S_02"},
]

agents_src    = os.path.join(BASE, "src")
agents_python = os.path.join(BASE, "venv2", "Scripts", "python.exe")

port = 8001
for agent in agents:
    port += 1
    env = os.environ.copy()
    env["PROFILE_ID"] = agent["PROFILE_ID"]
    env["AGENT_ID"]   = agent["AGENT_ID"]

    subprocess.Popen(
        [agents_python, "start_agents.py"],
        cwd=agents_src,
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(f"{agent['AGENT_ID']}  (profile {agent['PROFILE_ID']})  →  port {port}")

print("\nAll systems launched!")