# llm_client.py
import os
import requests
# Flag to choose backend:
# True  = use your local LM Studio + Mistral
# False = use Ollama / Gemma (university setup)
USE_LMSTUDIO = True

if USE_LMSTUDIO:
    MODEL_NAME = "mistral-7b-instruct-v0.3"  # your local model in LM Studio
    API_URL = "http://localhost:1234/v1/chat/completions"
else:
    from ollama import Ollama
    MODEL_NAME = "gemma:27B"  # the university model
    client = Ollama(model=MODEL_NAME)

def chat(messages, model=None):
    """
    Sends messages to the chosen LLM backend.
    messages: list of dicts [{"role": "user", "content": "Hello"}]
    """
    m = model if model else MODEL_NAME
    if USE_LMSTUDIO:
        payload = {
            "model": m,
            "messages": messages
        }
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()  # raises error if something goes wrong
        return response.json()['choices'][0]['message']['content']
    else:
        return client.chat(m,messages)
