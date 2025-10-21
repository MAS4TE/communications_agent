"""Root API endpoints."""

from pathlib import Path
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/", response_class=FileResponse)
def index():
    # Get the path to the static directory relative to this file
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    return Path(static_dir) / "index.html"

@router.get('/get_queue')
def some_router_function(request):
    market_message = request.app.state.market_to_llm_queue.get()
    print(f"Comm agent: {market_message=}")
    request.app.state.llm_to_market_queue.put("is okay market is open i got it!")
    return market_message
