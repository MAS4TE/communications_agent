"""Tool schemas for function calling."""

tool_schemas = [
    {
        "name": "get_battery_status",
        "description": "Returns the current battery level of the device as a percentage.",
        "parameters": {}
    },
    {
        "name": "get_cpu_status",
        "description": "Returns the current CPU usage percentage and core count.",
        "parameters": {}
    },
    {
        "type": "function",
        "function": {
            "name": "echo_test",
            "description": "Echoes back the provided integer value (for debugging argument passing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "Any numeric value to echo back"
                    }
                },
                "required": ["value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multi_argument_test",
            "description": "Returns a dictionary with the received value and a computed result (for debugging multiple arguments).",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "integer",
                        "description": "Main input value"
                    },
                    "factor": {
                        "type": "number",
                        "description": "Multiplier for the value",
                        "default": 1.0
                    }
                },
                "required": ["value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpu_forecast",
            "description": "Returns the average CPU usage percent from the log as a forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prediction_length": {
                        "type": "number",
                        "description": "Number of time steps to forecast",

                    }
                },
                "required": ["prediction_length"],
            }
        }
    },
    {
        "name": "battery_utility_calculator",
        "description": (
            "Calculate the utility of a battery given its size and time series data. "
            "Returns baseline cost, optimized cost, cost savings, and a bidding curve."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "storage_size_kwh": {
                    "type": "number",
                    "description": "Size of the battery in kWh"
                },
                "demand_series": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of demand values"
                },
                "solar_series": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of solar generation values"
                },
                "grid_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of grid prices"
                },
                "eeg_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of EEG prices"
                },
                "community_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of community market prices"
                },
                "wholesale_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Array of wholesale market prices"
                },
                "solver": {
                    "type": "string",
                    "description": "Solver to use (default 'appsi_highs')",
                    "default": "appsi_highs"
                }
            },
            "required": [
                "storage_size_kwh",
                "demand_series",
                "solar_series",
                "grid_prices",
                "eeg_prices",
                "community_prices",
                "wholesale_prices"
            ]
        }
    }
]

'''
OpenAI function calling schemas for various tools.
    {
        "name": "get_cpu_forecast",
        "description": "Returns the average CPU usage percent from the log as a forecast.",
        "parameters": {
            "type": "object",
            "properties": {
                "prediction_length": {
                    "type": "integer",
                    "description": "Number of time steps to forecast",
                    "default": 1
                }
            },
            "required": ["prediction_length"]
        }
    },
'''