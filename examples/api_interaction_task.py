#!/usr/bin/env python3
"""
Example script demonstrating how to use the Enhanced AI Agentic Browser Agent
for API-driven tasks: generating and executing API calls based on task descriptions.
"""

import asyncio
import json
import logging
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path for importing the agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import AgentOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def main():
    """Main function to run the example."""
    logger.info("Initializing the Agent Orchestrator")
    orchestrator = await AgentOrchestrator.initialize()
    
    # Define an API task using OpenAI API as an example
    task_config = {
        "task_description": "Generate a summary of the key features of electric vehicles using an API.",
        "human_assisted": False,
        "max_retries": 2,
        "timeout": 60,
        "preferred_approach": "api",  # Prefer API over browser automation
        "api_hint": "Use an LLM API to generate a summary about electric vehicles"
    }
    
    # Create and execute the task
    logger.info("Creating the API task")
    task_id = await orchestrator.create_task(task_config)
    
    logger.info(f"Executing task: {task_id}")
    await orchestrator.execute_task(task_id)
    
    # Wait for the task to complete
    while True:
        task_status = await orchestrator.get_task_status(task_id)
        if task_status["status"] in ["completed", "failed", "cancelled"]:
            break
        logger.info(f"Task status: {task_status['status']}")
        await asyncio.sleep(2)
    
    # Get and print the result
    result = await orchestrator.get_task_status(task_id)
    logger.info(f"Task completed with status: {result['status']}")
    
    if result["status"] == "completed":
        logger.info("API Task result:")
        print(json.dumps(result["result"], indent=2))
    else:
        logger.error(f"Task failed: {result.get('error', 'Unknown error')}")
    
    # Clean up resources
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
