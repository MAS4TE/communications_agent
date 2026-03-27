# core/pipeline/manager.py
import asyncio
import uuid


class PipelineManager:
    def __init__(self, step_map):
        self.step_map = step_map  # { job_type: [list of async step functions] }
        self.queue = asyncio.Queue()  # jobs go here
        self.jobs = {}              # job_id -> { status, result, error }
        self.worker_task = None

    async def start_worker(self):
        """
        Start the background worker as an asyncio task.
        asyncio.create_task() schedules it on the event loop without blocking —
        so startup continues immediately and the worker runs in the background.
        """
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker())
            print("PIPELINE: background worker started")

    async def _worker(self):
        """
        Continuously pull jobs from the queue and process them one at a time.

        Because this runs as an asyncio task, every `await step(data)` call
        yields control back to the event loop between steps — meaning the
        chatbot can handle incoming requests in between pipeline steps.

        The heavy lifting (Chronos, BUC) is offloaded to a thread pool inside
        each step via run_blocking, so the event loop stays free even during
        those calls.
        """
        while True:
            job_id, data = await self.queue.get()
            print(f"PIPELINE: starting job {job_id} (type={data.get('type')})")

            try:
                job_type = data.get("type")
                steps = self.step_map.get(job_type, [])

                if not steps:
                    print(f"PIPELINE: no steps defined for job type '{job_type}'")
                    self.jobs[job_id]["status"] = "failed"
                    self.jobs[job_id]["error"] = f"No steps for type '{job_type}'"
                    continue

                for step in steps:
                    print(f"PIPELINE: running step '{step.__name__}'")
                    data = await step(data)  # yields to event loop between each step

                self.jobs[job_id]["result"] = data
                self.jobs[job_id]["status"] = "done"
                print(f"PIPELINE: job {job_id} completed successfully")

            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
                print(f"PIPELINE: error in job {job_id}: {e}")

            finally:
                self.queue.task_done()

    async def enqueue(self, job: dict) -> str:
        """
        Add a job to the queue and return its job_id immediately.

        This method returns straight away — it does NOT run any steps itself.
        The background worker picks up the job and processes it independently,
        so the caller (e.g. an MQTT callback or API route) is never blocked.
        """
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
        """Return the current status and result of a job."""
        return self.jobs.get(job_id, {"status": "not_found"})

# import asyncio
# # import uuid
# from core.pipeline import steps 

# class PipelineManager:
#     def __init__(self, step_map):
#         self.step_map = step_map  # list of async functions
#         self.queue = asyncio.Queue()  # jobs go here
#         self.jobs = {}  # job_id -> result/status
#         self.worker_task = None

#     async def start_worker(self):
#         """Start the background worker."""
#         if self.worker_task is None:
#             self.worker_task = asyncio.create_task(self.worker())
    
#     async def worker(self):
#         """Continuously process jobs from the queue."""
#         while True:
#             job_id, data = await self.queue.get()
#             try:
#                 job_type = data.get("type")
#                 steps = self.step_map.get(job_type, [])

#                 for step in steps:
#                     data = await step(data)

#                 self.jobs[job_id]["result"] = data
#                 self.jobs[job_id]["status"] = "done"

#             except Exception as e:
#                 self.jobs[job_id]["status"] = "failed"
#                 self.jobs[job_id]["error"] = str(e)
#                 print(f"STEPS : error in job {job_id}: {e}")

#             finally:
#                 self.queue.task_done()


#     # async def enqueue(self, data):
#     #     """Add a new job to the queue."""
#     #     job_id = str(uuid.uuid4())
#     #     self.jobs[job_id] = {"status": "queued", "result": None}
#     #     await self.queue.put((job_id, data))
#     #     return job_id
#     async def enqueue(self, job: dict):
#         job_type = job["type"]
        
#         STEP_MAP = steps.retrieve_step_map()
        
#         if job_type not in STEP_MAP:
#             print(f"No steps defined for job type: {job_type}")
#             return
        
#         context = job# {"payload": job["payload"] }
        
#         for step in STEP_MAP[job_type]:
#             context = await step(context)

#     def get_status(self, job_id):
#         """Return the status/result of a job."""
#         return self.jobs.get(job_id, {"status": "not_found"})
