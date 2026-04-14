# core/pipeline/manager.py
import asyncio
import uuid
import time

from core.pipeline.dto import PipelineDTO
from core.main_context import set_pipeline_trace_bid, set_pipeline_trace_clearing

class PipelineTracker:
    """Tracks which step is currently running and how long each one took."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.job_type = None
        self.steps = []          # ordered list of step names for current job
        self.current = None      # name of the step currently running
        self.current_start = None
        self.done = {}           # { step_name: duration_seconds }
        self.status = "Waiting for market opening"     # idle | running | done | failed
        self.message = "Waiting for market_open trigger..."

    def start_job(self, job_type: str, step_names: list):
        self.reset()
        self.job_type = job_type
        self.steps = list(step_names)
        self.status = "running"
        self.message = None

    def begin(self, name: str):
        self.current = name
        self.current_start = time.time()

    def finish(self, name: str):
        if self.current_start is not None:
            self.done[name] = round(time.time() - self.current_start, 2)
        self.current = None

    def finish_job(self, status: str = "done"):
        self.current = None
        self.status = status
        if status == "done":
            self.message = "Waiting for next market message"

    def snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot of the current state."""
        now = time.time()
        active_duration = (
            round(now - self.current_start, 1)
            if self.current and self.current_start
            else None
        )
        return {
            "status": self.status,
            "job_type": self.job_type,
            "steps": self.steps,
            "progress": {
                "total_steps": len(self.steps),
                "completed_steps": len(self.done),
                "percentage": round(len(self.done) / len(self.steps) * 100, 1) if self.steps else 0
            },
            "current": self.current,
            "current_duration": active_duration,
            "done": self.done,
            "message":self.message,
        }


class PipelineManager:
    def __init__(self, step_map):
        self.step_map = step_map
        self.queue = asyncio.Queue()
        self.jobs = {}
        self.worker_task = None
        self.tracker = PipelineTracker()   # <-- single shared tracker

    async def start_worker(self):
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker())
            print("PIPELINE: background worker started")

    async def _worker(self):
        
        while True:
            job_id, data = await self.queue.get()
            print(f"PIPELINE: starting job {job_id} (type={data.get('type')})")

            try:
                job_type = data.get("type")
                steps = self.step_map[job_type]#.get(job_type, [])

                if not steps:
                    print(f"PIPELINE: no steps defined for job type '{job_type}'")
                    self.jobs[job_id]["status"] = "failed"
                    self.jobs[job_id]["error"] = f"No steps for type '{job_type}'"
                    continue

                dto = PipelineDTO(data=data)

                # --- tracker: start job ---
                self.tracker.start_job(job_type, [s.__name__ for s in steps])

                for step in steps:
                    print(f"PIPELINE: running step '{step.__name__}'")
                    self.tracker.begin(step.__name__)      # <-- begin
                    dto = await step(dto)
                    self.tracker.finish(step.__name__)     # <-- finish

                # --- tracker: job done ---
                self.tracker.finish_job("done")

                self.jobs[job_id]["result"] = dto.data
                self.jobs[job_id]["trace"] = dto.trace
                self.jobs[job_id]["status"] = "done"

                if job_type == "market_open":
                    set_pipeline_trace_bid(dto.trace)
                elif job_type == "market_clearing":
                    set_pipeline_trace_clearing(dto.trace)
                print(f"PIPELINE: job {job_id} completed successfully")

            except Exception as e:
                self.tracker.finish_job("failed")
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
                print(f"PIPELINE: error in job {job_id}: {e}")

            finally:
                self.queue.task_done()

    async def enqueue(self, job: dict) -> str:
        job_type = job.get("type")

        if job_type not in self.step_map:
            print(f"PIPELINE: no steps defined for job type '{job_type}', ignoring")
            return None

        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {"status": "queued", "result": None, "error": None}

        await self.queue.put((job_id, job))
        print(f"PIPELINE: job {job_id} (type={job_type}) queued")

        return job_id

    def get_status(self, job_id: str) -> dict:
        return self.jobs.get(job_id, {"status": "not_found"})