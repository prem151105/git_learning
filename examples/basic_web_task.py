#!/usr/bin/env python3
"""
Example script demonstrating how to use the Enhanced AI Agentic Browser Agent
for a basic web task: searching for information and extracting data.
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
    
    # Define a basic web task
    task_config = {
        "task_description": "Search for information about 'climate change solutions' on Wikipedia, "
                           "extract the main categories of solutions, and create a summary.",
        "urls": ["https://www.wikipedia.org"],
        "human_assisted": False,
        "max_retries": 3,
        "timeout": 300
    }
    
    # Create and execute the task
    logger.info("Creating the task")
    task_id = await orchestrator.create_task(task_config)
    
    logger.info(f"Executing task: {task_id}")
    await orchestrator.execute_task(task_id)
    
    # Wait for the task to complete
    while True:
        task_status = await orchestrator.get_task_status(task_id)
        if task_status["status"] in ["completed", "failed", "cancelled"]:
            break
        logger.info(f"Task status: {task_status['status']}")
        await asyncio.sleep(5)
    
    # Get and print the result
    result = await orchestrator.get_task_status(task_id)
    logger.info(f"Task completed with status: {result['status']}")
    
    if result["status"] == "completed":
        logger.info("Task result:")
        print(json.dumps(result["result"], indent=2))
    else:
        logger.error(f"Task failed: {result.get('error', 'Unknown error')}")
    
    # Clean up resources
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
