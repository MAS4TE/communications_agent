# Solar Battery Assistant API

A FastAPI application for monitoring and interacting with a solar battery system through a chat interface.

## Quickstart

1. Start the server:
   ```bash
   cd fastapi_app
   uvicorn src.main:app --reload
   ```

2. Visit http://localhost:8000 in your browser to access the chat interface.

3. Try asking questions like:
   - "Hello" - The assistant will greet you and explain its capabilities
   - "What is my current battery status and forecasted CPU usage?" - Get information about battery charge and CPU predictions
   - Note: While the assistant can provide battery and CPU information, it cannot provide the current date and time as this functionality is not implemented.

Example conversation:
```
You: Hello
Assistant: Hello! I'm your solar battery assistant. I can help you monitor your battery status, check CPU usage, and provide forecasts. What would you like to know?

You: What is my current battery status and CPU forecast?
Assistant: Let me check that for you...
Battery is at 85% and charging. Based on recent patterns, I forecast CPU usage will average around 45% over the next hour.
```

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
│   ├── api/                    # API endpoints for different features
│   │   ├── battery.py         # Battery monitoring endpoints
│   │   ├── chat.py           # Chat interface endpoints
│   │   └── cpu.py            # CPU monitoring endpoints
│   ├── core/                  # Core functionality
│   │   ├── llm/              # LLM integration framework
│   │   │   ├── backends/     # Different LLM implementations
│   │   │   ├── interfaces/   # Abstract base classes for LLMs
│   │   │   └── tools/        # LLM function calling tools
│   │   └── tools.py          # Core tool implementations
│   ├── configs/              # Configuration files
│   │   ├── config_lms.yaml   # LMStudio configuration
│   │   └── config_openai.yaml # OpenAI configuration
│   ├── dependencies/         # FastAPI dependencies
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic layer
│   │   ├── battery/        # Battery monitoring services
│   │   ├── chat/          # Chat processing services
│   │   └── cpu/           # CPU monitoring services
│   └── static/             # Static web files
├── data/                   # Data storage (untracked)
└── tests/                 # Unit and integration tests
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest
```

## Architecture TODOs

### Service Layer Improvements
Consider implementing Protocol-based service architecture for better maintainability:

1. **Why?**
   - Makes services easier to test (can mock dependencies)
   - Makes it easier to change implementations
   - Centralizes configuration in settings
   - Provides clear contracts for service capabilities

2. **How?**
   - Define service protocols (interfaces) that specify what services can do
   - Move service creation to app startup
   - Use dependency injection via FastAPI's dependency system
   - Store service instances in app.state

3. **Example Pattern**:
   ```python
   # Protocol defines the contract
   class ServiceProtocol(Protocol):
       def do_something(self) -> str: ...

   # Implementation fulfills the contract
   class ServiceImpl(ServiceProtocol):
       def __init__(self, config: Settings):
           self.config = config
       
       def do_something(self) -> str:
           # implementation
           pass

   # FastAPI uses dependency injection
   def get_service(request: Request) -> ServiceProtocol:
       return request.app.state.service
   ```

This maintains the same basic workflow for adding new features while making the code more maintainable and testable.

## Note on the forecaster

The CPU forecaster currently uses a hardcoded Chronos URL in `src/services/cpu/cpu_forecaster.py`:

```python
class CPUForecaster:
	def __init__(self, log_path="data/cpu_history", chronos_url="http://127.0.0.1:8000/forecast"):
		...
```

If you run the Chronos forecasting server in a separate terminal, start it with:

```bash
uvicorn main:app  --host 127.0.0.1 --port 8000
```

Make sure the `chronos_url` in `cpu_forecaster.py` matches the address where Chronos is running. To avoid mismatches, consider configuring the URL via an environment variable (CHRONOS_URL) or a settings file.

## Adding a New API Endpoint

**a. Define the Data Model (if needed):**
- Create a new Pydantic model in `src/models/` (e.g., `new_feature.py`).

**b. Implement the Service Logic:**
- Add a new service class or function in `src/services/` (e.g., `new_feature_service.py`).

**c. Create the API Route:**
- Add a new route in the appropriate API router in `src/api/` (e.g., `api/new_feature.py`).
- Use FastAPI’s decorators (`@router.get`, `@router.post`, etc.) to define the endpoint.

**d. Register the Router:**
- Import and include the new router in `main.py`:
	```python
	from fastapi_app.api.new_feature import router as new_feature_router
	app.include_router(new_feature_router)
	```

**e. (Optional) Update Static Files/UI:**
- If the endpoint needs a web page, add or update HTML/JS in `src/static/`.

## Adding a New Tool (for function calling/chat)

**a. Create a New Service (if needed):**
- Add a new service class in `src/services/new_feature/new_service.py`:
	```python
	class NewFeatureService:
	    """Service for handling new feature business logic."""
	    
	    def __init__(self):
	        # Initialize any dependencies
	        pass
	    
	    def perform_operation(self, param: str):
	        """Implement the actual business logic."""
	        # Your implementation here
	        return {"result": "data"}
	```

**b. Implement the Tool Function:**
- Add the function to your tools registry in `src/core/tools.py`:
	```python
	from services.new_feature.new_service import NewFeatureService
	
	class Tools:
	    @staticmethod
	    def get_tools(tracer=trace_tool):
	        # Create service instance
	        new_feature_service = NewFeatureService()
	        
	        # Define tool function that uses the service
	        def new_tool_function(param: str):
	            """Description of what this tool does."""
	            return new_feature_service.perform_operation(param)
	        
	        return [
	            # ... existing tools
	            tracer(new_tool_function),
	        ]
	```

**c. Add Tool to Schema:**
- Add a schema for the new tool in `src/models/tool_schemas.py`:
	```python
	{
	    "name": "new_tool_function",
	    "description": "Description of what the tool does.",
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
	```

**d. (Optional) Update Prompts:**
- If your chat agent uses system prompts, update them to mention the new tool and its usage format.

**e. (Optional) Add Service to Dependencies:**
- If the service needs to be injected elsewhere, add it to the dependency system.


User: What's my current battery status?

User: How is the CPU performing right now?

User: Please predict CPU usage for the next 3 time steps.

User: Can you calculate the utility of a 15 kWh battery with sample data?

User: Echo the number 42 for me using the debug tool.

User: Test multi-argument tool with value=10 and factor=2.5.
