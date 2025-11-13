# Solar Battery Assistant API

A FastAPI application for monitoring and interacting with a solar battery system through a chat interface.

## Quickstart

1. Start the server:
   ```bash
   cd fastapi_app/src
   uvicorn main:app --port 8002
   ```

2. Visit http://localhost:8002 in your browser to access the chat interface.


## API Structure

- `/` - HTML chat interface
- `/docs` - Swagger UI documentation
- `/redoc` - ReDoc documentation

### Endpoints

| Endpoint            | Method | Description |
|---------------------|--------|---------------------------------------------------------------|
| `/`                 | GET    | HTML chat interface (serves index.html)                        |
| `/chat`             | POST   | Process chat messages with AI assistant                        |
| `/battery/status`   | GET    | Get current battery status (charge %, plugged, time, status)   |
| `/cpu/status`       | GET    | Get current CPU status (usage %, core count)                   |
| `/cpu/forecast`     | GET    | Get average CPU usage forecast                                 |
| `/cpu/history`      | GET    | Get historical CPU usage log                                   |

## Project Organization

```
fastapi_app/
├── src/
│ ├── api/ # API endpoints for different features
│ │ ├── api_router.py # Main API router
│ │ ├── routes/ # Individual route modules
│ │ │ ├── battery_endpoint.py
│ │ │ ├── chat_endpoint.py
│ │ │ ├── cpu_endpoint.py
│ │ │ └── root_endpoint.py
│ ├── core/ # Core functionality
│ │ ├── domain/ # Business logic
│ │ ├── llm/ # LLM integration framework
│ │ │ ├── tools/ # LLM function calling tools
│ │ │ ├── backends/ # Different LLM implementations
│ │ │ ├── interfaces/ # Abstract base classes for LLMs
│ │ │ └── prompts/ # Prompt management
│ ├── configs/ # Configuration files
│ ├── utils/ # Utility functions
│ └── static/ # Static web files
├── data/ # Data storage (untracked)
└── tests/ # Unit and integration tests
```

### Tools

The following tools are implemented under `core/llm/tools/`:

- `battery_tool.py`: Queries the current battery status.
- `battery_utility_tool.py`: Provides utility calculations for battery usage.
- `cpu_tool.py`: Queries the current CPU usage.
- `forecast_tool.py`: Predicts CPU usage for future time steps.
- `echo_tool.py`: A debug tool for echoing input.
- `multi_argument_tool.py`: Demonstrates handling multiple arguments in tools.

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest
```

## Note on the forecaster


If you run the Chronos forecasting server in a separate terminal, start it with:

```bash
uvicorn main:app  --host 127.0.0.1 --port 8000
```

Ensure the paths are correct in `configs/settings.py`
```python
    # URLs and Endpoints
    CHRONOS_URL: str = "http://127.0.0.1:8000"
    CPU_LOG_PATH: str = "../../data/cpu_history"
```



## Adding a New API Endpoint

**a. Define the Data Model (if needed):**
- Create a new Pydantic model in `src/api/models/` (e.g., `new_feature.py`).

**b. Implement the Service Logic:**
- Add a new service class or function in `src/api/services/` (e.g., `new_feature_service.py`).

**c. Create the API Route:**
- Add a new route in the appropriate API router in `src/api/routes/` (e.g., `new_feature_endpoint.py`).
- Use FastAPI’s decorators (`@router.get`, `@router.post`, etc.) to define the endpoint.

**d. Register the Router:**
- Import and include the new router in `src/api/api_router.py`:
    ```python
    from .routes.new_feature_endpoint import router as new_feature_router
    api_router.include_router(new_feature_router, prefix="/new-feature")
    ```

**e. (Optional) Update Static Files/UI:**
- If the endpoint needs a web page, add or update HTML/JS in `src/static/`.

## Adding a New Tool (for function calling/chat)

**a. Define the Tool Function:**
- Create a new tool function in `src/core/llm/tools/` (e.g., `new_tool.py`):
    ```python
    from core.llm.tools.decorators import tool, trace_tool
    from core.domain.new_feature_logic import perform_new_feature_logic

    @tool(
        schema={
            "name": "new_tool_function",
            "description": "Description of what this tool does.",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param"]
            }
        }
    )
    @trace_tool
    def new_tool_function(param: str):
        """Description of what this tool does."""
        return perform_new_feature_logic(param)
    ```

**b. Implement the Logic Function:**
- Add the core logic for the tool in `src/core/domain/` (e.g., `new_feature_logic.py`):
    ```python
    def perform_new_feature_logic(param: str):
        """Core logic for the new tool."""
        # Your implementation here
        return {"result": f"Processed {param}"}
    ```

**c. Register the Tool in `main.py`:**
- Add an import statement in `src/main.py` to ensure the tool is registered in the central `ToolRegistry`:
    ```python
    # Import to ensure tool is registered in the central ToolRegistry
    import core.llm.tools.new_tool
    ```

**d. Test the Tool:**
- Write unit tests for the tool in `tests/` to ensure it behaves as expected.
