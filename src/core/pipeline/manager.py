import asyncio
import uuid

class PipelineManager:
    def __init__(self, steps):
        self.steps = steps  # list of async functions
        self.queue = asyncio.Queue()  # jobs go here
        self.jobs = {}  # job_id -> result/status
        self.worker_task = None

    async def start_worker(self):
        """Start the background worker."""
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self.worker())
    
    async def worker(self):
        """Continuously process jobs from the queue."""
        while True:
            job_id, data = await self.queue.get()
            try:
                for step in self.steps:
                    data = await step(data)
                self.jobs[job_id]["result"] = data
                self.jobs[job_id]["status"] = "done"
            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
            finally:
                self.queue.task_done()

    async def enqueue(self, data):
        """Add a new job to the queue."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {"status": "queued", "result": None}
        await self.queue.put((job_id, data))
        return job_id

    def get_status(self, job_id):
        """Return the status/result of a job."""
        return self.jobs.get(job_id, {"status": "not_found"})
