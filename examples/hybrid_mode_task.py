#!/usr/bin/env python3
"""
Example script demonstrating the Enhanced AI Agentic Browser Agent's
hybrid operation mode with human assistance for complex tasks.
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
from src.user_interaction.hybrid_executor import HybridExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class MockUserInterface:
    """Mock user interface to simulate user interactions."""
    
    def __init__(self):
        """Initialize the mock UI."""
        self.hybrid_executor = None
    
    def register_executor(self, hybrid_executor):
        """Register the hybrid executor."""
        self.hybrid_executor = hybrid_executor
    
    async def simulate_user_approval(self, request_id, task):
        """Simulate user approval of a task."""
        logger.info("USER: Reviewing task for approval...")
        logger.info(f"Task description: {task.get('task_description', 'No description')}")
        
        # Simulate user thinking time
        await asyncio.sleep(2)
        
        # Simulate user providing approval with slight modification
        modified_task = task.copy()
        if "task_description" in modified_task:
            modified_task["task_description"] += " Include visual examples if available."
        
        logger.info("USER: Approving task with minor modifications")
        self.hybrid_executor.provide_user_approval(request_id, True, modified_task)
    
    async def simulate_user_input(self, request_id, context):
        """Simulate user providing input during task execution."""
        logger.info("USER: Providing input for current step...")
        logger.info(f"Context: {context}")
        
        # Simulate user thinking time
        await asyncio.sleep(3)
        
        # Simulate user specifying a preference
        user_input = {
            "preference": "Prefer solutions with recent research (after 2023)",
            "focus_areas": ["renewable energy", "carbon capture", "policy changes"]
        }
        
        logger.info(f"USER: Providing input: {user_input}")
        self.hybrid_executor.provide_user_input(request_id, user_input)
    
    async def simulate_user_feedback(self, action_id, result):
        """Simulate user providing feedback after action completion."""
        logger.info("USER: Providing feedback on completed action...")
        
        # Simulate user thinking time
        await asyncio.sleep(1.5)
        
        # Simulate user feedback
        feedback = {
            "rating": 4,  # 1-5 scale
            "comment": "Good extraction, but missed some important details in the sidebar",
            "suggestions": ["Include sidebar content", "Better formatting of tables"]
        }
        
        logger.info(f"USER: Submitting feedback: {feedback}")
        self.hybrid_executor.provide_feedback(action_id, feedback)


async def main():
    """Main function to run the example."""
    logger.info("Initializing the Agent Orchestrator")
    orchestrator = await AgentOrchestrator.initialize()
    
    # Create mock user interface
    mock_ui = MockUserInterface()
    mock_ui.register_executor(orchestrator.hybrid_executor)
    
    # Define a task with human assistance
    task_config = {
        "task_description": "Research the latest breakthroughs in quantum computing and create a summary of their potential impacts on cryptography.",
        "urls": ["https://en.wikipedia.org/wiki/Quantum_computing", "https://www.research-papers.org/quantum-computing"],
        "human_assisted": True,
        "human_assist_mode": "approval",  # Options: review, approval, manual, autonomous
        "max_retries": 3,
        "timeout": 300
    }
    
    # Create the task
    logger.info("Creating the hybrid mode task")
    task_id = await orchestrator.create_task(task_config)
    
    # Extract request ID for approval simulation (this would normally be received via a callback)
    # In a real implementation, this would be handled by event listeners
    request_id = f"req-{task_id}"
    
    # Start task execution
    logger.info(f"Executing task: {task_id}")
    
    # Simulate user approval in a separate task
    asyncio.create_task(mock_ui.simulate_user_approval(request_id, task_config))
    
    # Execute the task (this will wait for user approval)
    execution_task = asyncio.create_task(orchestrator.execute_task(task_id))
    
    # Wait for a while to simulate task running
    await asyncio.sleep(5)
    
    # Simulate user providing input during task execution
    await mock_ui.simulate_user_input(f"input-{task_id}", {"current_step": "research", "needs_focus": True})
    
    # Wait for task completion
    await execution_task
    
    # Get and print the result
    result = await orchestrator.get_task_status(task_id)
    logger.info(f"Task completed with status: {result['status']}")
    
    if result["status"] == "completed":
        logger.info("Task result:")
        print(json.dumps(result["result"], indent=2))
        
        # Simulate user providing feedback
        await mock_ui.simulate_user_feedback(f"action-{task_id}", result["result"])
    else:
        logger.error(f"Task failed: {result.get('error', 'Unknown error')}")
    
    # Clean up resources
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
