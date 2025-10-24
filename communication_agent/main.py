"""Main FastAPI application."""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from communication_agent.api import api_router

from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("CHAT_ENDPOINT")
TOKEN = os.getenv("CHAT_TOKEN")
MODEL = os.getenv("CHAT_MODEL")

# Create FastAPI app with enhanced documentation
def run_app(
    host="0.0.0.0",
    port=8080,
    endpoint: str = ENDPOINT,
    token: str = TOKEN,
    model: str = MODEL,
    market_to_llm_queue=None,
    llm_to_market_queue=None,
):
    # TODO OPEN UNIVERSITY
    # make those parameters useable
    # as this is hardcoded right now in the services/chat_service.py

    app = FastAPI(
        title="Solar Battery Assistant API",
        description="API for monitoring and interacting with a solar battery system, including both direct data access and a conversational assistant interface.",
        version="0.1.0",
        openapi_tags=[
            {
                "name": "battery",
                "description": "Operations related to battery monitoring and status",
            },
            {
                "name": "chat",
                "description": "Chat interface with AI assistant for natural language interactions",
            },
        ],
    )

    # taken from
    # https://stackoverflow.com/questions/71298179/fastapi-how-to-get-app-instance-inside-a-router
    app.state.market_to_llm_queue = market_to_llm_queue
    app.state.llm_to_market_queue = llm_to_market_queue

    # Mount static files directoryls
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Include API routes
    app.include_router(api_router)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_app()
