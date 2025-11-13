"""Root API endpoints."""

from pathlib import Path
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/", response_class=FileResponse)
def index():
    # __file__ is src/api/root.py
    # Go up to src/ (parent of api), then static/index.html
    project_root = Path(__file__).parent.parent.parent  # src/
    index_file = project_root / "static" / "index.html"

    if not index_file.exists():
        raise RuntimeError(f"File at path {index_file} does not exist.")

    return FileResponse(index_file)