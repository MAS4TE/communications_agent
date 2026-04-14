# core/llm/tools/explain_tool.py
import json
from core.main_context import get_pipeline_trace_bid, get_pipeline_trace_clearing
from core.llm.tools.registry import tool_registry


def explain_pipeline(pipeline: str = "bid") -> str:
    """
    Returns the pipeline trace so the LLM can explain what happened.

    Args:
        pipeline: "bid" for the market_open pipeline, "clearing" for market_clearing
    """
    if pipeline == "bid":
        trace = get_pipeline_trace_bid()
    else:
        trace = get_pipeline_trace_clearing()

    if not trace:
        return "The pipeline hasn't run yet, so there is nothing to explain."

    return json.dumps(trace, indent=2, default=str)


EXPLAIN_PIPELINE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "explain_pipeline",
        "description": (
            "Returns what the energy trading pipeline did. "
            "Call this when the user asks what the pipeline did, how the bid was made, "
            "what happened during market clearing, or wants a summary of the system's actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pipeline": {
                    "type": "string",
                    "enum": ["bid", "clearing"],
                    "description": "Which pipeline to explain. 'bid' for the bidding pipeline, 'clearing' for market clearing."
                }
            },
            "required": ["pipeline"]
        }
    }
}

tool_registry.register_tool(explain_pipeline, EXPLAIN_PIPELINE_SCHEMA)