# Solar Battery Assistant API

A FastAPI application for monitoring and interacting with a solar battery system through a chat interface.

## Quick Start

```bash
# From the project root directory
cd fastapi_app
uvicorn fastapi_app.main:app --app-dir src --reload
```

Visit http://localhost:8000 for the chat interface.

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
├── src/fastapi_app/
│   ├── api/              # API endpoints
│   ├── core/             # Core functionality
│   ├── dependencies/     # FastAPI dependencies
│   ├── models/           # Data models
│   ├── services/         # Business logic
│   └── static/           # Static files
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
- Create a new Pydantic model in `src/fastapi_app/models/` (e.g., `new_feature.py`).

**b. Implement the Service Logic:**
- Add a new service class or function in `src/fastapi_app/services/` (e.g., `new_feature_service.py`).

**c. Create the API Route:**
- Add a new route in the appropriate API router in `src/fastapi_app/api/` (e.g., `api/new_feature.py`).
- Use FastAPI’s decorators (`@router.get`, `@router.post`, etc.) to define the endpoint.

**d. Register the Router:**
- Import and include the new router in `main.py`:
	```python
	from fastapi_app.api.new_feature import router as new_feature_router
	app.include_router(new_feature_router)
	```

**e. (Optional) Update Static Files/UI:**
- If the endpoint needs a web page, add or update HTML/JS in `src/fastapi_app/static/`.

## Adding a New Tool (for function calling/chat)

**a. Implement the Tool Function:**
- Add the function to your tools registry (e.g., in `src/fastapi_app/core/tools.py` or similar).
- If needed, use services/models for business logic.

**b. Add Tool to Registry:**
- Update the `get_tools` method to include your new tool, wrapped with tracing if needed.

**c. Update Tool Schemas:**
- Add a schema for the new tool in `src/fastapi_app/models/tool_schemas.py`:
	```python
	{
			"name": "new_tool_name",
			"description": "Description of what the tool does.",
			"parameters": { ... }
	}
	```

**d. (Optional) Update Prompts:**
- If your chat agent uses system prompts, update them to mention the new tool and its usage format.
