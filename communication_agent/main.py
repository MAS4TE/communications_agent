"""Main FastAPI application."""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from communication_agent.api import api_router

# Create FastAPI app with enhanced documentation
def run_app(host="0.0.0.0", port=8080):
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

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_app()