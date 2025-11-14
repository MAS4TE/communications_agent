from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/", response_class=FileResponse)
def index():
    project_root = Path(__file__).parent.parent.parent  # src/
    index_file = project_root / "static" / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=500,
            detail=f"File at path {index_file} does not exist."
        )

    return FileResponse(index_file)
