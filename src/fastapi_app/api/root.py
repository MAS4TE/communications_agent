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