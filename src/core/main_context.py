# core/main_context.py

# Globale variabelen die je tools kunnen gebruiken
GLOBAL_PROFILE_ID = 3#84

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