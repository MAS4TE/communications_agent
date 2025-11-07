tool_schemas = [
    # {
    #     "name": "get_battery_status",
    #     "description": "Returns the current battery level of the device as a percentage.",
    #     "parameters": {}  # no inputs needed for now
    # },
    # {
    #     "name": "battery_utility_calculator",
    #     "description": (
    #         "Calculate the utility of a battery given its size and time series data. "
    #         "Returns baseline cost, optimized cost, cost savings, and a bidding curve."
    #     ),
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "storage_size_kwh": {
    #                 "type": "number",
    #                 "description": "Size of the battery in kWh"
    #             },
    #             "demand_series": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of demand values"
    #             },
    #             "solar_series": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of solar generation values"
    #             },
    #             "grid_prices": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of grid prices"
    #             },
    #             "eeg_prices": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of EEG prices"
    #             },
    #             "community_prices": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of community market prices"
    #             },
    #             "wholesale_prices": {
    #                 "type": "array",
    #                 "items": {"type": "number"},
    #                 "description": "Array of wholesale market prices"
    #             },
    #             "solver": {
    #                 "type": "string",
    #                 "description": "Solver to use (default 'appsi_highs')",
    #                 "default": "appsi_highs"
    #             }
    #         },
    #         "required": [
    #             "storage_size_kwh",
    #             "demand_series",
    #             "solar_series",
    #             "grid_prices",
    #             "eeg_prices",
    #             "community_prices",
    #             "wholesale_prices"
    #         ]
    #     }
    # },
    # {
    #     "name": "get_suggested_bid",
    #     "description": "Return the current suggested bid from the agent state.",
    #     "parameters": {}
    # },
    # {
    #     "name": "set_suggested_bid",
    #     "description": "Update the suggested bid with a new price and volume.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "price": {"type": "number", "description": "Bid price in €/kWh"},
    #             "volume": {"type": "number", "description": "Bid volume in kWh"}
    #         },
    #         "required": ["price", "volume"]
    #     }
    # }
    {
        "name": "get_time_and_date",
        "description": "Returns the current time and/or date.",
        "parameters": {}  # no inputs needed for now
    }
]
