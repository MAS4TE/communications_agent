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

**a. Implement the Tool Function:**
- Add the function to your tools registry (e.g., in `src/core/tools.py` or similar).
- If needed, use services/models for business logic.

**b. Add Tool to Registry:**
- Update the `get_tools` method to include your new tool, wrapped with tracing if needed.

**c. Update Tool Schemas:**
- Add a schema for the new tool in `src/models/tool_schemas.py`:
	```python
	{
			"name": "new_tool_name",
			"description": "Description of what the tool does.",
			"parameters": { ... }
	}
	```

**d. (Optional) Update Prompts:**
- If your chat agent uses system prompts, update them to mention the new tool and its usage format.
