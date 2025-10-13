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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Process chat messages |
| `/battery/status` | GET | Get current battery status |

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
