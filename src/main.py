"""Main FastAPI application."""

import os
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.api_router import api_router
from api.services.cpu.cpu_service import CPUService
from configs.settings import Settings
from core.llm.factory import LLMFactory
from core.llm.tools.registry import tool_registry

# Import to ensure tool are registered in the central ToolRegistry
import core.llm.tools.battery_tool
import core.llm.tools.cpu_tool
import core.llm.tools.echo_tool
import core.llm.tools.multi_argument_tool
import core.llm.tools.forecast_tool
# import core.llm.tools.battery_utility_tool  # After installing the BatteryUtilityCalculator


# Create FastAPI app with enhanced documentation
app = FastAPI(
    title="Solar Battery Assistant API",
    description="API for monitoring and interacting with a solar battery system, including both direct data access and a conversational assistant interface.",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "battery",
            "description": "Operations related to battery monitoring and status"
        },
        {
            "name": "chat",
            "description": "Chat interface with AI assistant for natural language interactions"
        }
    ]
)

# Mount static files directoryls
project_root = os.path.dirname(__file__)
static_dir = os.path.join(project_root, "static")

if not os.path.isdir(static_dir):
    raise RuntimeError(f"Static directory not found at {static_dir}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include API routes
app.include_router(api_router)

# Load settings
settings = Settings()

@app.on_event("startup")
async def startup_event():
    # Initialize LLM
    factory = LLMFactory()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.LLM_CONFIG_PATH)
    llm = factory.create_from_yaml(config_path, agentic=True)
    
    # Set up tools
    llm.tools = tool_registry.tools
    llm.schemas = tool_registry.schemas
    
    # Store in app state
    app.state.llm = llm
    app.state.settings = settings

    # Start CPU logging
    cpu_service = CPUService()
    thread = threading.Thread(
        target=cpu_service.log_cpu_usage,
        kwargs={"interval_minutes": 1, "log_path": "data/cpu_history"},
        daemon=True
    )
    thread.start()