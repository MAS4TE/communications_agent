# core/main_context.py

import os

# Globale variabelen die je tools kunnen gebruiken
# buy: 152, 3
# sell: 84, 92
# GLOBAL_PROFILE_ID = 152
GLOBAL_PROFILE_ID = int(os.environ.get("PROFILE_ID", 84))

MQTT_AGENT = None
LLM = None

PIPELINE_TRACE_BID = []
PIPELINE_TRACE_CLEARING = []

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



def set_pipeline_trace_bid(trace: list):
    global PIPELINE_TRACE_BID
    PIPELINE_TRACE_BID = trace

def get_pipeline_trace_bid() -> list:
    return PIPELINE_TRACE_BID

def set_pipeline_trace_clearing(trace: list):
    global PIPELINE_TRACE_CLEARING
    PIPELINE_TRACE_CLEARING = trace

def get_pipeline_trace_clearing() -> list:
    return PIPELINE_TRACE_CLEARING