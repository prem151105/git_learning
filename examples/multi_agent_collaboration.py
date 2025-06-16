#!/usr/bin/env python3
"""
Example script demonstrating the Enhanced AI Agentic Browser Agent's
A2A Protocol integration for multi-agent collaboration.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List
from dotenv import load_dotenv

# Add parent directory to path for importing the agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import AgentOrchestrator
from src.a2a_protocol.agent_communication import A2AProtocol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class SpecialistAgent:
    """A specialist agent that can perform specific tasks."""
    
    def __init__(self, name: str, capabilities: List[str]):
        """
        Initialize the specialist agent.
        
        Args:
            name: Name of the agent
            capabilities: List of agent capabilities
        """
        self.agent_name = name
        self.capabilities = capabilities
        self.a2a_protocol = None
        self.orchestrator = None
    
    async def initialize(self):
        """Initialize the agent."""
        # Initialize the A2A protocol
        self.a2a_protocol = A2AProtocol()
        await self.a2a_protocol.initialize(
            agent_name=self.agent_name,
            capabilities=self.capabilities
        )
        
        # Initialize the orchestrator for task execution
        self.orchestrator = await AgentOrchestrator.initialize()
        
        # Register message handlers
        self.a2a_protocol.register_message_handler("task_request", self.handle_task_request)
        
        logger.info(f"Specialist Agent '{self.agent_name}' initialized with capabilities: {self.capabilities}")
        return self
    
    async def handle_task_request(self, message: Dict, content: Dict) -> Dict:
        """
        Handle a task request from another agent.
        
        Args:
            message: Full message data
            content: Message content
            
        Returns:
            Dict: Response data
        """
        logger.info(f"Agent '{self.agent_name}' received task request: {content.get('task_description', 'No description')}")
        
        request_id = content.get("request_id")
        task_description = content.get("task_description")
        parameters = content.get("parameters", {})
        
        # Create a task configuration
        task_config = {
            "task_description": task_description,
            "parameters": parameters,
            "human_assisted": False,
            "max_retries": 2
        }
        
        # Execute the task
        try:
            # Create and execute the task
            task_id = await self.orchestrator.create_task(task_config)
            await self.orchestrator.execute_task(task_id)
            
            # Wait for completion
            result = None
            while True:
                status = await self.orchestrator.get_task_status(task_id)
                if status["status"] in ["completed", "failed", "cancelled"]:
                    result = status
                    break
                await asyncio.sleep(1)
            
            # Send response back
            conversation_id = message.get("conversation_id")
            sender_id = message.get("sender_id")
            
            if result["status"] == "completed":
                await self.a2a_protocol.respond_to_task(
                    request_id=request_id,
                    result=result["result"],
                    conversation_id=conversation_id,
                    recipient_id=sender_id
                )
                logger.info(f"Agent '{self.agent_name}' completed task and sent response")
            else:
                await self.a2a_protocol.respond_to_task(
                    request_id=request_id,
                    result={"error": result.get("error", "Task execution failed")},
                    conversation_id=conversation_id,
                    recipient_id=sender_id
                )
                logger.info(f"Agent '{self.agent_name}' failed to complete task")
            
            return {
                "success": True,
                "message": "Task processed",
                "request_id": request_id
            }
            
        except Exception as e:
            logger.error(f"Error handling task request: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }
    
    async def shutdown(self):
        """Clean up resources."""
        if self.orchestrator:
            await self.orchestrator.shutdown()
        
        logger.info(f"Agent '{self.agent_name}' shut down")


async def run_multi_agent_scenario():
    """Run a multi-agent collaboration scenario."""
    # Create and initialize two specialist agents
    data_agent = await SpecialistAgent(
        name="Data Extraction Specialist",
        capabilities=["web_browsing", "data_extraction", "content_analysis"]
    ).initialize()
    
    analysis_agent = await SpecialistAgent(
        name="Analysis Specialist",
        capabilities=["data_processing", "summarization", "insight_generation"]
    ).initialize()
    
    # Register agents with a mock directory
    mock_directory = {
        data_agent.a2a_protocol.agent_id: {
            "agent_name": data_agent.agent_name,
            "capabilities": data_agent.capabilities,
            "endpoint": "http://localhost:8001/receive"  # Mock endpoint
        },
        analysis_agent.a2a_protocol.agent_id: {
            "agent_name": analysis_agent.agent_name,
            "capabilities": analysis_agent.capabilities,
            "endpoint": "http://localhost:8002/receive"  # Mock endpoint
        }
    }
    
    # Make agents aware of each other
    data_agent.a2a_protocol.known_agents = mock_directory
    analysis_agent.a2a_protocol.known_agents = mock_directory
    
    # Create an orchestrator for coordinating the multi-agent workflow
    coordinator = await AgentOrchestrator.initialize()
    
    # Define a complex task that requires collaboration
    complex_task = {
        "task_description": "Research and analyze the impact of artificial intelligence on healthcare, "
                           "including current applications, benefits, challenges, and future trends.",
        "sub_tasks": [
            {
                "agent": data_agent.a2a_protocol.agent_id,
                "task": "Extract data about AI applications in healthcare from reputable sources",
                "parameters": {
                    "data_points": ["applications", "benefits", "challenges", "trends"],
                    "min_sources": 3
                }
            },
            {
                "agent": analysis_agent.a2a_protocol.agent_id,
                "task": "Analyze the extracted data to identify patterns, insights, and recommendations",
                "parameters": {
                    "format": "report",
                    "include_charts": True
                }
            }
        ]
    }
    
    # Simulate task delegation and execution
    logger.info("Starting multi-agent collaboration workflow")
    
    # Step 1: Delegate data extraction task to data agent
    data_task = complex_task["sub_tasks"][0]
    logger.info(f"Delegating data extraction task to {data_agent.agent_name}")
    
    # In a real implementation, we would use the actual A2A protocol
    # Here we simulate the communication by directly calling the handler
    data_message = {
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "sender_id": "coordinator",
        "sender_name": "Coordinator",
        "recipient_id": data_agent.a2a_protocol.agent_id,
        "message_type": "task_request",
        "content": {
            "request_id": "req-data-1",
            "task_description": data_task["task"],
            "parameters": data_task["parameters"],
            "response_required": True,
            "timeout_seconds": 60
        },
        "timestamp": 123456789
    }
    
    # Simulate receiving data extraction results
    logger.info("Simulating data extraction task execution...")
    data_result = {
        "applications": [
            "Medical imaging analysis",
            "Drug discovery and development",
            "Virtual health assistants",
            "Predictive analytics for patient outcomes"
        ],
        "benefits": [
            "Improved accuracy in diagnostics",
            "Reduced healthcare costs",
            "Enhanced patient experience",
            "Accelerated research and development"
        ],
        "challenges": [
            "Data privacy and security concerns",
            "Regulatory hurdles",
            "Integration with existing systems",
            "Potential bias in algorithms"
        ],
        "trends": [
            "Personalized medicine",
            "Remote patient monitoring",
            "AI-powered robotic surgery",
            "Genomics and precision medicine"
        ],
        "sources": [
            "New England Journal of Medicine",
            "Healthcare IT News",
            "World Health Organization"
        ]
    }
    
    # Step 2: Delegate analysis task to analysis agent
    analysis_task = complex_task["sub_tasks"][1]
    logger.info(f"Delegating analysis task to {analysis_agent.agent_name}")
    
    analysis_message = {
        "message_id": "msg-2",
        "conversation_id": "conv-1",
        "sender_id": "coordinator",
        "sender_name": "Coordinator",
        "recipient_id": analysis_agent.a2a_protocol.agent_id,
        "message_type": "task_request",
        "content": {
            "request_id": "req-analysis-1",
            "task_description": analysis_task["task"],
            "parameters": {
                **analysis_task["parameters"],
                "extracted_data": data_result  # Pass data from first agent
            },
            "response_required": True,
            "timeout_seconds": 60
        },
        "timestamp": 123456790
    }
    
    # Simulate receiving analysis results
    logger.info("Simulating analysis task execution...")
    analysis_result = {
        "title": "Impact of AI on Healthcare: Analysis Report",
        "summary": "Artificial Intelligence is transforming healthcare through various applications, offering significant benefits while presenting challenges that need to be addressed. Future trends indicate continued innovation in personalized medicine and remote care solutions.",
        "key_insights": [
            "AI applications in medical imaging show 30% higher accuracy in early disease detection",
            "Virtual health assistants are reducing administrative workloads by 40%",
            "Data privacy remains the top concern among healthcare providers adopting AI",
            "Personalized medicine powered by AI is expected to grow at 28% CAGR through 2030"
        ],
        "recommendations": [
            "Healthcare organizations should invest in robust data security frameworks",
            "Physician training should include AI literacy components",
            "Regulatory frameworks need to evolve to address AI-specific challenges",
            "Ethical guidelines for AI in healthcare should be standardized globally"
        ],
        "visualization_links": [
            "chart1.png",
            "chart2.png"
        ]
    }
    
    # Final step: Combine results into a comprehensive output
    logger.info("Combining results from both agents...")
    
    final_result = {
        "title": complex_task["task_description"],
        "data_extraction": {
            "agent": data_agent.agent_name,
            "result": data_result
        },
        "analysis": {
            "agent": analysis_agent.agent_name,
            "result": analysis_result
        },
        "combined_insights": [
            "AI is revolutionizing healthcare through multiple avenues, with medical imaging and drug discovery showing the most immediate impact.",
            "While benefits include improved accuracy and reduced costs, organizations must address significant privacy and regulatory challenges.",
            "Future healthcare will likely see increased personalization and remote capabilities powered by AI technologies."
        ]
    }
    
    logger.info("Multi-agent collaboration completed successfully")
    print(json.dumps(final_result, indent=2))
    
    # Clean up resources
    await data_agent.shutdown()
    await analysis_agent.shutdown()
    await coordinator.shutdown()


if __name__ == "__main__":
    asyncio.run(run_multi_agent_scenario())
