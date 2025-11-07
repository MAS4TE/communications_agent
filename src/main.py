"""Main FastAPI application."""

import os
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import api_router
from services.cpu.cpu_service import CPUService
from configs.settings import Settings
from core.llm.factory import LLMFactory
from core.tools import Tools
from core.llm.tools.tools_manager import ToolManager
from models.tool_schemas import tool_schemas

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
static_dir = os.path.join(os.path.dirname(__file__), "static")
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
    tools = Tools.get_tools()
    tool_manager = ToolManager(tools=tools, schemas=tool_schemas)
    llm.tool_manager = tool_manager
    
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