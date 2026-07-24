import subprocess
import sys
import os

# agents = [
#     {"PROFILE_ID": "3",   "AGENT_ID": "B_01"},
#     {"PROFILE_ID": "152", "AGENT_ID": "B_02"},
#     {"PROFILE_ID": "84",  "AGENT_ID": "S_01"},
#     {"PROFILE_ID": "92",  "AGENT_ID": "S_02"},
# ]

agents = [
    {"PROFILE_ID": "3",   "AGENT_ID": "B_01"},
    {"PROFILE_ID": "152", "AGENT_ID": "B_02"},
    {"PROFILE_ID": "9",   "AGENT_ID": "B_03"},
    {"PROFILE_ID": "33",  "AGENT_ID": "B_04"},
    {"PROFILE_ID": "96",  "AGENT_ID": "B_05"},
    {"PROFILE_ID": "168", "AGENT_ID": "B_06"},
    {"PROFILE_ID": "18",  "AGENT_ID": "B_07"},
    {"PROFILE_ID": "84",  "AGENT_ID": "S_01"},
    {"PROFILE_ID": "92",  "AGENT_ID": "S_02"},
    {"PROFILE_ID": "87",  "AGENT_ID": "S_03"},
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