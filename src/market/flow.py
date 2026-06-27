"""Shared machinery for the bidding and clearing pipelines.

A pipeline is just a list of small async "step" functions run one after another.
Each step receives the same MarketContext, reads and writes ``ctx.data``, and
records a human-readable line in ``ctx.trace`` — that trace is what the chat
assistant later reads back to explain what happened.

There is no queue and no worker: the MQTT client schedules ``run_pipeline`` on
the event loop and an asyncio.Lock (held by the agent) makes sure only one runs
at a time. ``PipelineStatus`` is a tiny live view of the current run for the
web-based pipeline viewer.
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial

# CPU-heavy work (Chronos, the optimiser, the LLM, REST calls) is blocking, so
# we run it in this single background thread to avoid stalling the event loop.
_THREAD_POOL = ThreadPoolExecutor(max_workers=1)


async def run_blocking(fn, *args, **kwargs):
    """Run a blocking function off the event loop and await the result."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_THREAD_POOL, partial(fn, *args, **kwargs))


@dataclass
class MarketContext:
    """Carries everything a pipeline run needs from step to step."""

    agent: object                       # the Agent this run belongs to
    market_data: dict                   # the raw MQTT message that triggered the run
    data: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)

    def log(self, step: str, description: str, metadata: dict | None = None) -> None:
        """Record what a step did, for the chat assistant to explain later."""
        self.trace.append({
            "step": step,
            "description": description,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class PipelineStatus:
    """Live progress of the current pipeline run, polled by the UI."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps: list[str] = []
        self.current: str | None = None
        self._started_at: float | None = None
        self.done: dict[str, float] = {}
        self.status = "Waiting for market opening"
        self.message = "Waiting for market_open trigger..."

    def start(self, step_names: list[str]):
        self.reset()
        self.steps = list(step_names)
        self.status = "running"
        self.message = None

    def begin(self, name: str):
        self.current = name
        self._started_at = time.time()

    def finish_step(self, name: str):
        if self._started_at is not None:
            self.done[name] = round(time.time() - self._started_at, 2)
        self.current = None

    def finish(self, status: str = "done"):
        self.current = None
        self.status = status
        if status == "done":
            self.message = "Waiting for next market message"

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "steps": self.steps,
            "current": self.current,
            "done": self.done,
            "message": self.message,
            "progress": {
                "total_steps": len(self.steps),
                "completed_steps": len(self.done),
                "percentage": round(len(self.done) / len(self.steps) * 100, 1) if self.steps else 0,
            },
        }


async def run_pipeline(ctx: MarketContext, steps: list, status: PipelineStatus) -> MarketContext:
    """Run the given steps in order against ``ctx``, updating ``status``."""
    status.start([step.__name__ for step in steps])
    try:
        for step in steps:
            print(f"PIPELINE: {step.__name__}")
            status.begin(step.__name__)
            await step(ctx)
            status.finish_step(step.__name__)
        status.finish("done")
    except Exception as error:
        status.finish("failed")
        print(f"PIPELINE: failed in step '{status.current}': {error}")
        raise
    return ctx
