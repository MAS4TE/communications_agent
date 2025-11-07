from datetime import datetime, timedelta


class AgentState:
    """Tracks the information that the communication agent has received. """
    def __init__(self):

        self.upcoming_market = {
            "id": "market_001",
            'is_open':False,
            "delivery_window": {"start": datetime(2023, 1, 1, 13), "end": datetime(2023, 1, 1, 13)+ timedelta(days=7)  },
        }

        self.suggested_bid: dict = {
            "market_id": self.upcoming_market["market_id"],
            "agent_id": "1",
            "type": "supply",   
            "price": 12.0,       # default placeholder
            "volume": 2.0,      # default placeholder
            "timestamp": datetime.now().isoformat(),
        }

        self.prosumer_preference = None

        self.prosumer_profile = None

        self.available_storage_capacity = None

    def set_suggested_bid(self, price: float, volume: float):
        """Update only the price and volume of the suggested bid."""
        self.suggested_bid["price"] = price
        self.suggested_bid["volume"] = volume
        self.suggested_bid["timestamp"] = datetime.now().isoformat()

    def get_suggested_bid(self) -> dict:
        """Retrieve the current suggested bid."""
        return self.suggested_bid

# Shared instance of the agent state, as redefining it would create a new instance
shared_agent_state = AgentState()