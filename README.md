# Solar Battery Assistant API

A FastAPI application for monitoring and interacting with a solar battery system through a chat interface.

## Quick Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the interface
```bash
# From the project root directory
python3 ./communication_agent/main.py
```

Visit http://localhost:8080 for the chat interface.

## API Structure

- `/` - HTML chat interface
- `/docs` - Swagger UI documentation
- `/redoc` - ReDoc documentation

### Main endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Process chat messages |
| `/battery/status` | GET | Get current battery status |
| `/queue` | GET | Checks for  |

## Contributing

Please use pre-commit with the repository's configuration. Install and enable it with:

```bash
pip install pre-commit
pre-commit install
```

Thank you for contributing!
