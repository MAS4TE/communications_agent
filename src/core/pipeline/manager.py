import asyncio
# import uuid
from core.pipeline import steps 

class PipelineManager:
    def __init__(self, step_map):
        self.step_map = step_map  # list of async functions
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
                job_type = data.get("type")
                steps = self.step_map.get(job_type, [])

                for step in steps:
                    data = await step(data)

                self.jobs[job_id]["result"] = data
                self.jobs[job_id]["status"] = "done"

            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
                print(f"STEPS : error in job {job_id}: {e}")

            finally:
                self.queue.task_done()


    # async def enqueue(self, data):
    #     """Add a new job to the queue."""
    #     job_id = str(uuid.uuid4())
    #     self.jobs[job_id] = {"status": "queued", "result": None}
    #     await self.queue.put((job_id, data))
    #     return job_id
    async def enqueue(self, job: dict):
        job_type = job["type"]
        
        STEP_MAP = steps.retrieve_step_map()
        
        if job_type not in STEP_MAP:
            print(f"No steps defined for job type: {job_type}")
            return
        
        context = job# {"payload": job["payload"] }
        
        for step in STEP_MAP[job_type]:
            context = await step(context)

    def get_status(self, job_id):
        """Return the status/result of a job."""
        return self.jobs.get(job_id, {"status": "not_found"})
