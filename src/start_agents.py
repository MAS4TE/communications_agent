import subprocess
import sys
import os

# agents = [
#     {"PROFILE_ID": "3",   "AGENT_ID": "B_01", "port": "8002"},
#     {"PROFILE_ID": "152", "AGENT_ID": "B_02", "port": "8003"},
#     {"PROFILE_ID": "84",  "AGENT_ID": "S_01", "port": "8004"},
#     {"PROFILE_ID": "92",  "AGENT_ID": "S_02", "port": "8005"},
# ]

agents = [
    {"PROFILE_ID": "3",   "AGENT_ID": "B_01"},
    {"PROFILE_ID": "152", "AGENT_ID": "B_02"},
    {"PROFILE_ID": "84",  "AGENT_ID": "S_01"},
    {"PROFILE_ID": "92",  "AGENT_ID": "S_02"},
]

port = 8001

for agent in agents:
    env = os.environ.copy()
    env["PROFILE_ID"] = agent["PROFILE_ID"]
    env["AGENT_ID"] = agent["AGENT_ID"]
    port = port + 1
    
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)],
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(f"Started agent {agent['AGENT_ID']} with profile {agent['PROFILE_ID']} on port {port}")