from fastapi import APIRouter, Request
from core.main_context import get_pipeline_trace_bid, get_pipeline_trace_clearing


router = APIRouter(prefix="/pipeline")

@router.get("/status")
async def get_pipeline_status(request: Request):
    pipeline = request.app.state.pipeline
    tracker = pipeline.tracker

    return tracker.snapshot()

@router.get("/debug/traces")
def get_traces():
    return {
        "bid_trace_steps":      len(get_pipeline_trace_bid()),
        "clearing_trace_steps": len(get_pipeline_trace_clearing()),
    }