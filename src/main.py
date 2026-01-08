"""Main FastAPI application."""
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
from core.pipeline.steps import STEPS

settings = Settings()

# Lifespan handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup logic ---
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
    pipeline = PipelineManager(steps=STEPS)

    # 2. Start the pipeline worker (runs jobs in the background)
    await pipeline.start_worker()

    #3. Store the pipeline manager in app state for access in routes
    app.state.pipeline = pipeline
    # Enqueue a job immediately on startup
    await pipeline.enqueue({})  # this triggers the steps automatically

    yield

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

# @app.get("/run_test_pipeline")
# async def run_test_pipeline(request: Request):
#     # Enqueue a job with empty data
#     job_id = await request.app.state.pipeline.enqueue({})
#     return {"job_id": job_id, "status": "queued"}