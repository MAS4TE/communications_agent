# core/llm/tools/preferences_tool.py
from core.llm.tools.decorators import tool, trace_tool
from api.services.prosumer.prosumer_service import ProsumerService


@tool(
    schema={
        "name": "get_preferences",
        "description": "Returns the current trading preferences of the prosumer, including their trading preference, battery tradeable percentage, expertise level, and trading scope (Community, Country, or All). Always call this when you need to know the prosumer's current preferences — do not assume you already have them.",
        "parameters": {}
    }
)
@trace_tool
def get_preferences():
    """
    Tool that returns the current preferences of the prosumer.
    Always fetches live — so changes made during the session are reflected immediately.
    """
    service = ProsumerService()
    return service.get_preferences()