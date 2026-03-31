from fastapi import APIRouter, Request

router = APIRouter(prefix="/pipeline")

@router.get("/status")
async def get_pipeline_status(request: Request):
    pipeline = request.app.state.pipeline
    tracker = pipeline.tracker

    return tracker.snapshot()