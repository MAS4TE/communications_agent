# core/llm/tools/__init__.py

# Import all tool modules here so that they register with the central ToolRegistry
# This is for side-effects only — no objects are needed from these imports
import core.llm.tools.battery_tool
import core.llm.tools.cpu_tool
import core.llm.tools.echo_tool
import core.llm.tools.multi_argument_tool
import core.llm.tools.forecast_tool
import core.llm.tools.battery_utility_tool