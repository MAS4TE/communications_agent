"""Chat backend for running without any LLM credentials.

The agent must boot and trade even when no API key is configured — the market
side does not need a language model, only the chat assistant does. Rather than
crashing at startup (or, worse, at the first chat request), the factory falls
back to this backend: it answers from the agent's own tools and data instead of
from a model.

It is deliberately dumb and deterministic. It picks the tool that matches the
question, runs it, and reports the result as plain text. That is enough to keep
the web UI usable and to let the bidding pipeline's LLM step fall back to its
documented default.
"""
import json

from llm.base import ChatLLM, Tool

NO_MODEL_NOTE = (
    "No language model is configured for this agent, so I can only report the raw "
    "data I have. Add src/mas4te_mistral_api_key.yml (or set MISTRAL_API_KEY) and "
    "restart to get proper answers."
)

# Which tool answers which kind of question. First match wins.
_KEYWORDS = [
    ("explain_pipeline", ("bid", "bod", "gebot", "clearing", "pipeline", "happen",
                          "passiert", "gemacht", "accepted", "angenommen", "forecast")),
    ("get_preferences", ("preference", "einstellung", "präferenz", "setting", "scope",
                         "expertise", "tradeable")),
    ("get_profile", ("profile", "profil", "household", "haushalt", "battery", "batterie",
                     "solar", "location", "standort")),
    ("get_onboarding_info", ("how does", "wie funktioniert", "what is mas4te", "was ist mas4te",
                             "getting started", "onboarding", "help", "hilfe", "new here")),
    ("get_current_time", ("time", "uhrzeit", "date", "datum", "zeit")),
]


class OfflineLLM(ChatLLM):
    """Answers from the agent's tools; never contacts a remote service."""

    def invoke(self, messages: list[dict], tools: list[Tool]) -> str:
        question = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )

        tool = self._pick_tool(question, tools)
        if tool is None:
            return NO_MODEL_NOTE

        try:
            result = tool.fn(**self._default_arguments(tool))
        except Exception as error:                      # a tool may need live data
            return f"{NO_MODEL_NOTE}\n\nI tried to look this up and it failed: {error}"

        if isinstance(result, str):
            body = result
        else:
            body = json.dumps(result, indent=2, default=str)
        return f"{NO_MODEL_NOTE}\n\nHere is the raw {tool.name} result:\n{body}"

    @staticmethod
    def _pick_tool(question: str, tools: list[Tool]) -> Tool | None:
        by_name = {t.name: t for t in tools}
        lowered = question.lower()
        for name, keywords in _KEYWORDS:
            if name in by_name and any(word in lowered for word in keywords):
                return by_name[name]
        return None

    @staticmethod
    def _default_arguments(tool: Tool) -> dict:
        """Fill required parameters with the first value their schema allows."""
        parameters = tool.schema["function"].get("parameters", {})
        properties = parameters.get("properties", {})
        arguments = {}
        for name in parameters.get("required", []):
            spec = properties.get(name, {})
            if "enum" in spec:
                arguments[name] = spec["enum"][0]
            elif spec.get("type") == "string":
                arguments[name] = ""
            elif spec.get("type") in ("integer", "number"):
                arguments[name] = 0
        return arguments
