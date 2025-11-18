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
            "market_id": self.upcoming_market["id"],
            "agent_id": "1",
            "type": "supply",   
            "price": 12.0,       # default placeholder
            "volume": 2.0#,      # default placeholder
            # "timestamp": datetime.now().isoformat(),
        }

        self.prosumer_preference = None

        self.prosumer_profile = None

        self.available_storage_capacity = 10

    def set_current_bid(self, price: float, volume: float):
        """Update only the price and volume of the suggested bid."""
        self.suggested_bid["price"] = price
        self.suggested_bid["volume"] = volume
        # self.suggested_bid["timestamp"] = datetime.now().isoformat()

    def get_current_bid(self) -> dict:
        """Retrieve the current suggested bid."""
        return self.suggested_bid
    
    def get_prosumer_profile(self):
        return self.prosumer_profile
    
    def set_next_market(self):
        # Next market ID
        id_parts = self.upcoming_market['id'].split('_')
        new_id = f"market_{int(id_parts[2]) + 1}_{id_parts[3:]}"
        self.upcoming_market['id'] = new_id

        # market closed until ASSUME gives message
        self.upcoming_market['is_open'] = False

        # window = next week (for now -> find this in market information at some point)
        start_time_new = self.upcoming_market["delivery_window"]["start"]+ timedelta(days=7)
        end_time_new = self.upcoming_market["delivery_window"]["end"]+ timedelta(days=7)

        self.upcoming_market['delivery_window'] = {"start":datetime(start_time_new), "end":datetime(end_time_new)}


# Shared instance of the agent state, as redefining it would create a new instance
# shared_agent_state = AgentState()