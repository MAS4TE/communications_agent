"""How a pipeline runs. No framework, no async — a list of functions.

A pipeline is a plain list of functions. Each one takes the same MarketContext,
reads and writes ``ctx.data``, and writes one line into ``ctx.trace`` saying what
it did. Running a pipeline is a for loop:

    for step in steps:
        step(ctx)

That is the whole mechanism. ``bidding.py`` and ``clearing.py`` are each just a
list of such functions plus the functions themselves, so you can read either file
top to bottom and see everything that happens.

``ctx.trace`` is what the chat assistant reads back when the prosumer asks what
the agent did on their behalf. ``PipelineStatus`` is the live view the web-based
pipeline viewer polls while a run is in progress.

Everything here runs on the agent's single worker thread (see agent.py), so
steps never run concurrently and need no locking.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("pipeline")


@dataclass
class MarketContext:
    """Carries everything one pipeline run needs from step to step."""

    agent: object                       # the Agent this run belongs to
    market_data: dict                   # the MQTT message that triggered the run
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
    """Live progress of the current run, polled by the pipeline viewer."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps: list[str] = []
        self.current: str | None = None
        self.done: dict[str, float] = {}
        self.status = "Waiting for market opening"
        self.message = "Waiting for market_open trigger..."
        self._started_at: float | None = None

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

    def finish(self, status: str = "done", message: str | None = None):
        self.current = None
        self.status = status
        self.message = message or ("Waiting for next market message" if status == "done" else None)

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


def run_pipeline(ctx: MarketContext, steps: list, status: PipelineStatus,
                 name: str = "pipeline") -> MarketContext:
    """Run the steps in order. Raises whatever a step raises, after recording it."""
    status.start([step.__name__ for step in steps])
    log.info("%s start steps=%d", name, len(steps))
    started = time.time()

    for number, step in enumerate(steps, start=1):
        status.begin(step.__name__)
        step_started = time.time()
        try:
            step(ctx)
        except Exception as error:
            status.finish("failed", f"failed in {step.__name__}: {error}")
            log.error("%s step %d/%d %s FAILED after %.2fs: %s: %s", name, number,
                      len(steps), step.__name__, time.time() - step_started,
                      type(error).__name__, error)
            raise
        status.finish_step(step.__name__)
        log.info("%s step %d/%d %s done in %.2fs", name, number, len(steps),
                 step.__name__, time.time() - step_started)

    status.finish("done")
    log.info("%s done in %.2fs", name, time.time() - started)
    return ctx
