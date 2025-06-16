# Development Guide - Enhanced AI Agentic Browser Agent

This document provides guidelines and information for developers who want to extend or contribute to the Enhanced AI Agentic Browser Agent Architecture.

## Architecture Overview

The architecture follows a layered design pattern, with each layer responsible for specific functionality:

```
┌───────────────────────────────────────────────────────┐
│                  Agent Orchestrator                   │
└───────────────────────────────────────────────────────┘
         ↑           ↑            ↑            ↑
         │           │            │            │
┌─────────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐
│ Perception  │ │ Browser │ │ Action  │ │ Planning     │
│ Layer       │ │ Control │ │ Layer   │ │ Layer        │
└─────────────┘ └─────────┘ └─────────┘ └──────────────┘
         ↑           ↑            ↑            ↑
         │           │            │            │
┌─────────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐
│ Memory      │ │ User    │ │ A2A     │ │ Security &   │
│ Layer       │ │ Layer   │ │ Protocol│ │ Monitoring   │
└─────────────┘ └─────────┘ └─────────┘ └──────────────┘
```

## Development Environment Setup

### Prerequisites

1. Python 3.9+ installed
2. Docker and Docker Compose installed
3. Required API keys for LFMs (OpenAI, Anthropic, Google)

### Initial Setup

1. Clone the repository and navigate to it:
   ```bash
   git clone https://github.com/your-org/agentic-browser.git
   cd agentic-browser
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file with your API keys and configuration
   ```

5. Install browser automation dependencies:
   ```bash
   playwright install chromium
   playwright install-deps chromium
   ```

## Project Structure

- `src/` - Core application code
  - `perception/` - Web content analysis components
  - `browser_control/` - Browser automation components
  - `action_execution/` - Action execution components
  - `planning/` - Task planning components
  - `memory/` - Memory and learning components
  - `user_interaction/` - User interaction components
  - `a2a_protocol/` - Agent-to-agent communication components
  - `security/` - Security and ethics components
  - `monitoring/` - Metrics and monitoring components
  - `orchestrator.py` - Central orchestration component
  - `main.py` - FastAPI application
- `examples/` - Example usage scripts
- `tests/` - Unit and integration tests
- `config/` - Configuration files
  - `prometheus/` - Prometheus configuration
  - `grafana/` - Grafana dashboard configuration
- `docker-compose.yml` - Docker Compose configuration
- `Dockerfile` - Docker image definition
- `requirements.txt` - Python dependencies

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_browser_control.py

# Run tests with coverage report
pytest --cov=src
```

## Code Style Guidelines

This project follows PEP 8 style guidelines and uses type annotations:

```python
def add_numbers(a: int, b: int) -> int:
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        int: Sum of the two numbers
    """
    return a + b
```

Use the following tools to maintain code quality:

```bash
# Code formatting with black
black src/ tests/

# Type checking with mypy
mypy src/

# Linting with flake8
flake8 src/ tests/
```

## Adding New Components

### Creating a New Layer

1. Create a new directory under `src/` for your layer
2. Add an `__init__.py` file
3. Add your component classes
4. Update the orchestrator to integrate your layer

### Example: Adding a New Browser Action

1. Open `src/action_execution/action_executor.py`
2. Add a new method for your action:

```python
async def _execute_new_action(self, config: Dict) -> Dict:
    """Execute a new custom action."""
    # Implement your action logic here
    # ...
    return {"success": True, "result": "Action completed"}
```

3. Add your action to the `execute_action` method's action type mapping:

```python
elif action_type == "new_action":
    result = await self._execute_new_action(action_config)
```

### Example: Adding a New AI Model Provider

1. Open `src/perception/multimodal_processor.py`
2. Add support for the new provider:

```python
async def _analyze_with_new_provider_vision(self, base64_image, task_goal, ocr_text):
    """Use a new provider's vision model for analysis."""
    # Implement the model-specific analysis logic
    # ...
    return response_data
```

## Debugging

### Local Development Server

Run the server in development mode for automatic reloading:

```bash
python run_server.py --reload --log-level debug
```

### Accessing Logs

- Server logs: Standard output when running the server
- Browser logs: Stored in `data/browser_logs.txt` when enabled
- Prometheus metrics: Available at `http://localhost:9090`
- Grafana dashboards: Available at `http://localhost:3000`

### Common Issues

1. **Browser automation fails**
   - Check if the browser binary is installed
   - Ensure proper permissions for browser process
   - Check network connectivity and proxy settings

2. **API calls fail**
   - Verify API keys in `.env` file
   - Check rate limiting on API provider side
   - Ensure network connectivity

3. **Memory issues**
   - Check vector database connectivity
   - Verify embedding dimensions match database configuration

## Deployment

### Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f browser-agent

# Scale services
docker-compose up -d --scale browser-agent=3
```

### Kubernetes Deployment

Basic Kubernetes deployment files are provided in the `k8s/` directory:

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -l app=agentic-browser
```

## Continuous Integration

This project uses GitHub Actions for CI/CD:

- **Test workflow**: Runs tests on pull requests
- **Build workflow**: Builds Docker image on merge to main
- **Deploy workflow**: Deploys to staging environment on tag

## Performance Optimization

For best performance:

1. Use API-first approach when possible instead of browser automation
2. Implement caching for frequent operations
3. Use batch processing for embedding generation
4. Scale horizontally for concurrent task processing

## Contribution Guidelines

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Implement your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Submit a pull request

## Security Considerations

- Never store API keys in the code
- Validate all user inputs
- Implement rate limiting for API endpoints
- Follow least privilege principle
- Regularly update dependencies
