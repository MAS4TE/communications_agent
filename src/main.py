"""Main FastAPI application."""

import os
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fastapi_app.api import api_router
from fastapi_app.services.cpu.cpu_service import CPUService

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

@app.on_event("startup")
def start_cpu_logging():
    cpu_service = CPUService()
    thread = threading.Thread(
        target=cpu_service.log_cpu_usage,
        kwargs={"interval_minutes": 1, "log_path": "data/cpu_history"},
        daemon=True
    )
    thread.start()