"""Main FastAPI application."""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fastapi_app.api import api_router

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
