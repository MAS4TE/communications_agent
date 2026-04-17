# core/main_context.py

import os

# Globale variabelen die je tools kunnen gebruiken
# buy: 152, 3
# sell: 84, 92
# GLOBAL_PROFILE_ID = 152
GLOBAL_PROFILE_ID = int(os.environ.get("PROFILE_ID", 84))

MQTT_AGENT_BATTERY = None
MQTT_AGENT_ASSUME = None
LLM = None

PIPELINE_TRACE_BID = []
PIPELINE_TRACE_CLEARING = []

def set_mqtt_agent_battery(agent):
    global MQTT_AGENT_BATTERY
    MQTT_AGENT_BATTERY = agent

def get_mqtt_agent_battery():
    return MQTT_AGENT_BATTERY

def set_mqtt_agent_assume(agent):
    global MQTT_AGENT_ASSUME
    MQTT_AGENT_ASSUME = agent

def get_mqtt_agent_assume():
    return MQTT_AGENT_ASSUME


def set_llm(llm):
    global LLM
    LLM = llm

def get_llm():
    return LLM



def set_pipeline_trace_bid(trace: list):
    global PIPELINE_TRACE_BID
    PIPELINE_TRACE_BID = trace

def get_pipeline_trace_bid() -> list:
    return PIPELINE_TRACE_BID

def set_pipeline_trace_clearing(trace: list):
    global PIPELINE_TRACE_CLEARING
    PIPELINE_TRACE_CLEARING.append(trace) # keep all market clearings

def get_pipeline_trace_clearing() -> list:
    return PIPELINE_TRACE_CLEARING