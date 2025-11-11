"""
Battery domain objects and entities.
"""

class Storage:
    """Represents a storage unit for energy."""
    def __init__(
        self,
        id: int,
        c_rate: float,
        volume: float,
        charge_efficiency: float = 1,
        discharge_efficiency: float = 1,
    ):
        self.id = id
        self.c_rate = c_rate
        self.volume = volume
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency