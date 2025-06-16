# Enhanced AI Agentic Browser Agent: User Guide

This guide provides practical examples of how to use the Enhanced AI Agentic Browser Agent for various automation tasks. No technical background required!

## What Can This Agent Do?

The Enhanced AI Agentic Browser Agent can help you:

- Research topics across multiple websites
- Fill out forms automatically
- Extract structured data from websites
- Monitor websites for changes
- Automate multi-step workflows
- Interact with web applications intelligently

## Getting Started: The Basics

### Setting Up

1. **Install the agent**:
   ```bash
   # Clone the repository
   git clone https://github.com/prem151105/agentic-browser.git
   cd agentic-browser

   # Install dependencies
   pip install -r requirements.txt

   # Set up environment variables
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start the agent server**:
   ```bash
   python run_server.py
   ```

3. **Access the web interface**: Open your browser and go to `http://localhost:8000`

### Your First Task

Let's start with a simple example: searching for information about climate change on Wikipedia.

#### Using the Web Interface

1. Navigate to the Web Interface at `http://localhost:8000`
2. Click "Create New Task"
3. Fill out the task form:
   - **Task Description**: "Search for information about climate change on Wikipedia and summarize the key points."
   - **URLs**: `https://www.wikipedia.org`
   - **Human Assistance**: No (autonomous mode)
4. Click "Submit Task"
5. Monitor the progress in real-time
6. View the results when complete

#### Using the API

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Search for information about climate change on Wikipedia and summarize the key points.",
    "urls": ["https://www.wikipedia.org"],
    "human_assisted": false
  }'
```

#### Using the Python Client

```python
import asyncio
from src.orchestrator import AgentOrchestrator

async def run_task():
    # Initialize the orchestrator
    orchestrator = await AgentOrchestrator.initialize()
    
    # Create a task
    task_id = await orchestrator.create_task({
        "task_description": "Search for information about climate change on Wikipedia and summarize the key points.",
        "urls": ["https://www.wikipedia.org"],
        "human_assisted": False
    })
    
    # Execute the task
    await orchestrator.execute_task(task_id)
    
    # Wait for completion and get results
    while True:
        status = await orchestrator.get_task_status(task_id)
        if status["status"] in ["completed", "failed"]:
            print(status)
            break
        await asyncio.sleep(2)

# Run the task
asyncio.run(run_task())
```

## Common Use Cases with Examples

### 1. Data Extraction from Websites

**Task**: Extract product information from an e-commerce site.

```python
task_config = {
    "task_description": "Extract product names, prices, and ratings from the first page of best-selling laptops on Amazon.",
    "urls": ["https://www.amazon.com/s?k=laptops"],
    "output_format": "table",  # Options: table, json, csv
    "human_assisted": False
}
```

**Result Example**:
```
| Product Name                      | Price    | Rating |
|-----------------------------------|----------|--------|
| Acer Aspire 5 Slim Laptop         | $549.99  | 4.5/5  |
| ASUS VivoBook 15 Thin and Light   | $399.99  | 4.3/5  |
| HP 15 Laptop, 11th Gen Intel Core | $645.00  | 4.4/5  |
```

### 2. Form Filling with Human Approval

**Task**: Fill out a contact form on a website.

```python
task_config = {
    "task_description": "Fill out the contact form on the company website with my information and submit it.",
    "urls": ["https://example.com/contact"],
    "human_assisted": True,
    "human_assist_mode": "approval",
    "form_data": {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "I'm interested in your services and would like to schedule a demo."
    }
}
```

**Workflow**:
1. Agent navigates to the contact page
2. Identifies all form fields
3. Prepares the data to fill in each field
4. **Requests your approval** before submission
5. Submits the form after approval
6. Confirms successful submission

### 3. Multi-Site Research Project

**Task**: Research information about electric vehicles from multiple sources.

```python
task_config = {
    "task_description": "Research the latest developments in electric vehicles. Focus on battery technology, charging infrastructure, and market growth. Create a comprehensive summary with key points from each source.",
    "urls": [
        "https://en.wikipedia.org/wiki/Electric_vehicle",
        "https://www.caranddriver.com/electric-vehicles/",
        "https://www.energy.gov/eere/electricvehicles/electric-vehicles"
    ],
    "human_assisted": True,
    "human_assist_mode": "review"
}
```

**Workflow**:
1. Agent visits each website in sequence
2. Extracts relevant information on the specified topics
3. Compiles data from all sources
4. Organizes information by category
5. Generates a comprehensive summary
6. Presents the results for your review

### 4. API Integration Example

**Task**: Using direct API calls instead of browser automation.

```python
task_config = {
    "task_description": "Get current weather information for New York City and create a summary.",
    "preferred_approach": "api",
    "api_hint": "Use a weather API to get the current conditions",
    "parameters": {
        "location": "New York City",
        "units": "imperial"
    },
    "human_assisted": False
}
```

**Result Example**:
```
Current Weather in New York City:
Temperature: 72°F
Conditions: Partly Cloudy
Humidity: 65%
Wind: 8 mph NW
Forecast: Temperatures will remain steady through tomorrow with a 30% chance of rain in the evening.
```

### 5. Monitoring a Website for Changes

**Task**: Monitor a website for specific changes.

```python
task_config = {
    "task_description": "Monitor the company blog for new articles about AI. Check daily and notify me when new content is published.",
    "urls": ["https://company.com/blog"],
    "schedule": {
        "frequency": "daily",
        "time": "09:00"
    },
    "monitoring": {
        "type": "content_change",
        "selector": ".blog-articles",
        "keywords": ["artificial intelligence", "AI", "machine learning"]
    },
    "notifications": {
        "email": "user@example.com"
    }
}
```

**Workflow**:
1. Agent visits the blog at scheduled times
2. Captures the current content
3. Compares with previous visits
4. If new AI-related articles are found, sends a notification
5. Provides a summary of the changes

## Working with Human Assistance Modes

The agent supports four modes of human interaction:

### Autonomous Mode
Agent works completely independently with no human interaction.
```python
"human_assisted": False
```

### Review Mode
Agent works independently, then presents results for your review.
```python
"human_assisted": True,
"human_assist_mode": "review"
```

### Approval Mode
Agent asks for your approval before key actions.
```python
"human_assisted": True,
"human_assist_mode": "approval"
```

### Manual Mode
You provide specific instructions for each step.
```python
"human_assisted": True,
"human_assist_mode": "manual"
```

## Tips for Best Results

1. **Be specific in your task descriptions**: The more detail you provide, the better the agent can understand your goals.

2. **Start with URLs**: Always provide starting URLs for web tasks to help the agent begin in the right place.

3. **Use human assistance for complex tasks**: For critical or complex tasks, start with human-assisted modes until you're confident in the agent's performance.

4. **Check task status regularly**: Monitor long-running tasks to ensure they're progressing as expected.

5. **Provide feedback**: When using review mode, provide detailed feedback to help the agent learn and improve.

## Troubleshooting Common Issues

### Agent can't access a website
- Check if the website requires login credentials
- Verify the website doesn't have anti-bot protections
- Try using a different browser type in the configuration

### Form submission fails
- Ensure all required fields are properly identified
- Check if the form has CAPTCHA protection
- Try using approval mode to verify the form data before submission

### Results are incomplete
- Make the task description more specific
- Check if pagination is handled properly
- Consider using API mode if available

### Agent gets stuck
- Set appropriate timeouts in the task configuration
- Use more specific selectors in your task description
- Try breaking the task into smaller sub-tasks

## Need More Help?

- Check the detailed [Architecture Flow](ARCHITECTURE_FLOW.md) document
- View the [Visual Flow Guide](VISUAL_FLOW.md) for diagrams
- Explore the [example scripts](examples/) for more use cases
- Refer to the [API Documentation](API.md) for advanced usage
