"""Main FastAPI application."""
"""
How to run? 
Open a terminal per agent (for now)

Windows: 
Agent 1: Buy
set PROFILE_ID=3
set AGENT_ID=B_01
uvicorn main:app --port 8002

Agent 2: Buy
set PROFILE_ID=152
set AGENT_ID=B_02
uvicorn main:app --port 8003

Agent 1: Sell
set PROFILE_ID = 84
set AGENT_ID=S_01
uvicorn main:app --port 8004

Agent 2: Sell
set PROFILE_ID = 92
set AGENT_ID=S_02
uvicorn main:app --port 8005


"""

from contextlib import asynccontextmanager
import os
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi import Request

from api.api_router import api_router
from api.services.cpu.cpu_service import CPUService
from configs.settings import Settings
from core.llm.factory import LLMFactory
from core.llm.tools.registry import tool_registry
import core.llm.tools

from core.pipeline.manager import PipelineManager
from core.pipeline.steps import STEP_MAP

from core.mqtt.agent_client import MqttAgent
import asyncio

from core.main_context import GLOBAL_PROFILE_ID
from core.main_context import set_mqtt_agent
from api.services.chat.chat_service import ChatService
from core.llm.prompts import build_system_message
from core.main_context import set_llm



settings = Settings()

# Lifespan handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup logic ---
    profile_id = int(os.environ.get("PROFILE_ID", 152))
    agent_id = os.environ.get("AGENT_ID", "B_01")
    app.state.profile_id = profile_id
    app.state.agent_id = agent_id
    # Initialize LLM
    factory = LLMFactory()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.LLM_CONFIG_PATH)
    llm = factory.create_from_yaml(config_path, agentic=True)
    
    # Set up tools
    llm.tools = tool_registry.tools
    llm.schemas = tool_registry.schemas
    
    # Store in app state
    app.state.llm = llm
    app.state.chat_service = ChatService(
    llm=llm,
    prompt=build_system_message()
    )
    
    
    set_llm(llm)

    app.state.settings = settings

    # Start CPU logging in background thread
    cpu_service = CPUService()
    thread = threading.Thread(
        target=cpu_service.log_cpu_usage,
        kwargs={"interval_minutes": 1, "log_path": "data/cpu_history"},
        daemon=True
    )
    thread.start()


    # pipeline part
    # 1. Create the pipeline manager
    pipeline = PipelineManager(step_map=STEP_MAP)

    # 2. Start the pipeline worker (runs jobs in the background)
    await pipeline.start_worker()

    #3. Store the pipeline manager in app state for access in routes
    app.state.pipeline = pipeline
    # Enqueue a job immediately on startup
    # await pipeline.enqueue({})  # this triggers the steps automatically


    loop = asyncio.get_running_loop()
    app.state.loop = loop

    # mqtt agent startup
    mqtt_agent = MqttAgent(
            broker="localhost", 
            port = 1883,
            agent_id = agent_id,
            pipeline_manager=pipeline, 
            loop = loop
    )
    mqtt_agent.start()
    set_mqtt_agent(mqtt_agent)

    yield

# def run_app():
#     # Create FastAPI app with lifespan
#     app = FastAPI(
#         title="Solar Battery Assistant API",
#         description="API for monitoring and interacting with a solar battery system, including both direct data access and a conversational assistant interface.",
#         version="0.1.0",
#         lifespan=lifespan,
#         openapi_tags=[
#             {"name": "battery", "description": "Operations related to battery monitoring and status"},
#             {"name": "chat", "description": "Chat interface with AI assistant for natural language interactions"}
#         ]
#     )

#     # Mount static files directoryls
#     project_root = os.path.dirname(__file__)
#     static_dir = os.path.join(project_root, "static")

#     if not os.path.isdir(static_dir):
#         raise RuntimeError(f"Static directory not found at {static_dir}")

#     app.mount("/static", StaticFiles(directory=static_dir), name="static")

#     # Include API routes
#     app.include_router(api_router)

# Create FastAPI app with lifespan
app = FastAPI(
    title="Solar Battery Assistant API",
    description="API for monitoring and interacting with a solar battery system, including both direct data access and a conversational assistant interface.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "battery", "description": "Operations related to battery monitoring and status"},
        {"name": "chat", "description": "Chat interface with AI assistant for natural language interactions"}
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

# GLOBAL_PROFILE_ID = 3
# app.state.global_profile_id = GLOBAL_PROFILE_ID

# @app.get("/run_test_pipeline")
# async def run_test_pipeline(request: Request):
#     # Enqueue a job with empty data
#     job_id = await request.app.state.pipeline.enqueue({})
#     return {"job_id": job_id, "status": "queued"}