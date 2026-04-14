# core/pipeline/dto.py
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PipelineDTO:
    """
    Data Transfer Object for the energy trading pipeline.

    Carries two things through every step:
      - data   : the working payload (forecasts, curves, preferences, etc.)
      - trace  : a growing log of what each step did

    Steps interact with the payload via dict-style access (dto["key"]),
    which keeps all existing step code compatible without changes.
    The trace is written to via dto.log_step(...) at the end of each step.
    """

    data: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)

    # ------------------------------------------------------------------
    # Trace
    # ------------------------------------------------------------------

    def log_step(self, step_name: str, description: str, metadata: dict = None):
        """
        Append a trace entry for a completed pipeline step.

        Args:
            step_name   : machine-readable identifier, e.g. "forecast_demand"
            description : human-readable sentence of what the step did
            metadata    : optional dict of key numbers / facts from this step
        """
        self.trace.append({
            "step":        step_name,
            "description": description,
            "metadata":    metadata or {},
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Dict-style access — keeps existing step code unchanged
    # ------------------------------------------------------------------

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, key):
        return key in self.data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, other: dict):
        self.data.update(other)