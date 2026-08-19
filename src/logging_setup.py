"""One place that configures logging, so every line says who and when.

One process is one agent, so the agent id is stamped onto every record by a
filter instead of being passed around. A line looks like this:

    14:22:07 S_01  market   INFO    publish topic=mas4te/bids/agentS_01 orders=37
    14:22:07 S_01  pipeline INFO    step 8/10 battery_utility done in 4.31s

Loggers are named after what they do, so you can raise or lower one of them:

    market     MQTT: what was received, what was published, and on which topic
    pipeline   which step of which pipeline is running, and how long it took
    bidding    decisions inside the bidding steps
    clearing   decisions inside the clearing steps
    agent      the worker thread and its queue
    llm        which chat backend is in use
    buc        the optimiser, when BUC_DEBUG is on

Environment:
    LOG_FILE=path        also append every line to this file (the launcher sets
                         it when each agent gets its own terminal, so you get the
                         live view and a record of it)
    LOG_LEVEL=DEBUG      how much to show (default INFO)
    LOG_ACCESS=1         include uvicorn's per-request access log, which is
                         noisy because the pipeline viewer polls /pipeline/status
    BUC_DEBUG=2          include the solver's own output (off at any LOG_LEVEL,
                         because it is dozens of lines per optimiser solve)
"""
import logging
import os
import sys

FORMAT = "%(asctime)s %(agent)-5s %(name)-8s %(levelname)-7s %(message)s"
DATE_FORMAT = "%H:%M:%S"


class _StampAgent(logging.Filter):
    """Put this process's agent id on every record."""

    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.agent = self.agent_id
        return True


def setup(agent_id: str) -> None:
    """Configure logging for this agent process. Call once, early."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(_StampAgent(agent_id))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))
        file_handler.addFilter(_StampAgent(agent_id))
        root.addHandler(file_handler)

    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

    # uvicorn installs its own handlers and does not propagate; route it through
    # ours so everything in this process looks the same and lands in one place.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    if os.environ.get("LOG_ACCESS", "").strip().lower() not in ("1", "true", "yes", "on"):
        # The pipeline viewer polls /pipeline/status every second; that would
        # bury everything else.
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # pyomo logs the solver's entire output at INFO, once per solve — dozens of
    # lines times (locations x volumes) for a single bid. Off unless asked for:
    # BUC_DEBUG=2 turns it back on (see market/buc_debug.py).
    logging.getLogger("pyomo").setLevel(logging.WARNING)
