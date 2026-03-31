# core/main_context.py

import os

# Globale variabelen die je tools kunnen gebruiken
# buy: 152, 3
# sell: 84, 92
# GLOBAL_PROFILE_ID = 152
GLOBAL_PROFILE_ID = int(os.environ.get("PROFILE_ID", 84))

MQTT_AGENT = None
LLM = None


def set_mqtt_agent(agent):
    global MQTT_AGENT
    MQTT_AGENT = agent

def get_mqtt_agent():
    return MQTT_AGENT


def set_llm(llm):
    global LLM
    LLM = llm

def get_llm():
    return LLM