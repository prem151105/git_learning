#!/usr/bin/env python3
"""
Agent Orchestrator module for the Enhanced AI Agentic Browser Agent Architecture.

This module serves as the central coordinator for all layers in the architecture,
managing task execution flow and communication between components.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional, Any

from fastapi import WebSocket

from src.perception.multimodal_processor import MultimodalProcessor
from src.browser_control.browser_controller import BrowserController
from src.action_execution.action_executor import ActionExecutor, APIInteractionModule
from src.planning.task_planner import TaskPlanner
from src.memory.continuous_memory import ContinuousMemory
from src.user_interaction.hybrid_executor import HybridExecutor
from src.a2a_protocol.agent_communication import A2AProtocol
from src.security.ethical_guardian import EthicalGuardian
from src.monitoring.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Orchestrates all layers of the AI Agent Architecture.
    
    This class manages the lifecycle of tasks, coordinates between different 
    layers, and handles communication with external systems.
    """
    
    def __init__(self):
        """Initialize the Agent Orchestrator."""
        self.perception = None
        self.browser_control = None
        self.action_executor = None
        self.api_module = None
        self.task_planner = None
        self.memory = None
        self.hybrid_executor = None
        self.a2a_protocol = None
        self.ethical_guardian = None
        self.metrics = None
        
        # Task tracking
        self.tasks = {}  # task_id -> task_info
        self.websockets = {}  # task_id -> List[WebSocket]
        
        logger.info("Agent Orchestrator instance created")
    
    @classmethod
    async def initialize(cls):
        """
        Initialize all components of the architecture.
        
        Returns:
            AgentOrchestrator: Initialized orchestrator instance
        """
        instance = cls()
        
        # Initialize components in parallel for efficiency
        await asyncio.gather(
            instance._init_perception(),
            instance._init_browser_control(),
            instance._init_action_execution(),
            instance._init_planning(),
            instance._init_memory(),
            instance._init_user_interaction(),
            instance._init_a2a_protocol(),
            instance._init_security(),
            instance._init_monitoring(),
        )
        
        logger.info("All components initialized successfully")
        return instance
    
    async def _init_perception(self):
        """Initialize the Perception & Understanding Layer."""
        self.perception = MultimodalProcessor()
        await self.perception.initialize()
        logger.info("Perception & Understanding Layer initialized")
    
    async def _init_browser_control(self):
        """Initialize the Browser Control Layer."""
        self.browser_control = BrowserController()
        await self.browser_control.initialize()
        logger.info("Browser Control Layer initialized")
    
    async def _init_action_execution(self):
        """Initialize the Action Execution Layer."""
        self.api_module = APIInteractionModule()
        self.action_executor = ActionExecutor(self.browser_control, self.api_module)
        await self.action_executor.initialize()
        logger.info("Action Execution Layer initialized")
    
    async def _init_planning(self):
        """Initialize the Planning & Reasoning Layer."""
        self.task_planner = TaskPlanner()
        await self.task_planner.initialize()
        logger.info("Planning & Reasoning Layer initialized")
    
    async def _init_memory(self):
        """Initialize the Memory & Learning Layer."""
        self.memory = ContinuousMemory()
        await self.memory.initialize()
        logger.info("Memory & Learning Layer initialized")
    
    async def _init_user_interaction(self):
        """Initialize the User Interaction Layer."""
        self.hybrid_executor = HybridExecutor(self.action_executor)
        await self.hybrid_executor.initialize()
        logger.info("User Interaction Layer initialized")
    
    async def _init_a2a_protocol(self):
        """Initialize the Agent-to-Agent Protocol."""
        self.a2a_protocol = A2AProtocol()
        await self.a2a_protocol.initialize()
        logger.info("Agent-to-Agent Protocol initialized")
    
    async def _init_security(self):
        """Initialize the Security & Ethics components."""
        self.ethical_guardian = EthicalGuardian()
        await self.ethical_guardian.initialize()
        logger.info("Security & Ethics components initialized")
    
    async def _init_monitoring(self):
        """Initialize the Monitoring & Analytics components."""
        self.metrics = MetricsCollector()
        await self.metrics.initialize()
        logger.info("Monitoring & Analytics components initialized")
    
    async def create_task(self, task_config: Dict) -> str:
        """
        Create a new task with the given configuration.
        
        Args:
            task_config: Dictionary containing task configuration
            
        Returns:
            str: Task ID
        """
        task_id = str(uuid.uuid4())
        
        # Validate the task with ethical guardian
        is_valid, reason = await self.ethical_guardian.validate_task(task_config["task_description"])
        if not is_valid:
            self.tasks[task_id] = {
                "status": "rejected",
                "error": f"Task rejected due to ethical concerns: {reason}",
                "config": task_config,
                "result": None,
                "created_at": time.time()
            }
            return task_id
        
        # Create and store task
        self.tasks[task_id] = {
            "status": "created",
            "config": task_config,
            "result": None,
            "created_at": time.time()
        }
        
        logger.info(f"Created task {task_id}: {task_config['task_description']}")
        self.metrics.record_task_created()
        
        return task_id
    
    async def execute_task(self, task_id: str):
        """
        Execute a task with the given ID.
        
        Args:
            task_id: ID of the task to execute
        """
        if task_id not in self.tasks:
            logger.error(f"Task {task_id} not found")
            return
        
        task = self.tasks[task_id]
        task["status"] = "running"
        await self._notify_task_update(task_id, {"status": "running"})
        
        try:
            # Record start time for metrics
            start_time = time.time()
            
            # Retrieve task configuration
            task_config = task["config"]
            human_assisted = task_config.get("human_assisted", False)
            
            # 1. Planning phase
            await self._notify_task_update(task_id, {"status": "planning"})
            plan = await self.task_planner.decompose_task(
                task_config["task_description"],
                urls=task_config.get("urls", [])
            )
            
            # 2. Check similar past tasks in memory
            similar_tasks = await self.memory.retrieve_similar_tasks(task_config["task_description"])
            
            # 3. Execute plan steps
            results = []
            for step_idx, step in enumerate(plan["steps"]):
                # Update task status with current step
                step_status = f"Executing step {step_idx+1}/{len(plan['steps'])}: {step['description']}"
                await self._notify_task_update(task_id, {"status": step_status})
                
                # Process current web page if browser is initialized
                if self.browser_control.is_page_loaded():
                    page_data = await self.browser_control.get_page_data()
                    understanding = await self.perception.analyze_page(
                        page_data["screenshot"], 
                        page_data["dom_text"], 
                        step["description"]
                    )
                
                # Execute the step based on operation mode
                if human_assisted:
                    step_result = await self.hybrid_executor.execute_task(
                        step, 
                        human_assist=True
                    )
                else:
                    step_result = await self.action_executor.execute_action(step)
                
                # Record results
                results.append({
                    "step": step["description"],
                    "result": step_result
                })
                
                # Check for cancellation after each step
                if task["status"] == "cancelling":
                    task["status"] = "cancelled"
                    await self._notify_task_update(task_id, {"status": "cancelled"})
                    return
            
            # 4. Store experience in memory
            await self.memory.store_experience(
                task_config["task_description"],
                plan["steps"],
                {
                    "success": True,
                    "results": results
                }
            )
            
            # 5. Update task status to completed
            task["status"] = "completed"
            task["result"] = {
                "steps_executed": len(results),
                "results": results,
                "execution_time": time.time() - start_time
            }
            
            # Record metrics
            self.metrics.record_task_completed(time.time() - start_time)
            
            await self._notify_task_update(task_id, {
                "status": "completed",
                "result": task["result"]
            })
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            # Handle errors and update task status
            logger.exception(f"Error executing task {task_id}: {str(e)}")
            task["status"] = "failed"
            task["error"] = str(e)
            
            # Record metrics
            self.metrics.record_task_failed()
            
            await self._notify_task_update(task_id, {
                "status": "failed",
                "error": str(e)
            })
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if task was found and cancellation was initiated, False otherwise
        """
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task["status"] == "running":
            task["status"] = "cancelling"
            await self._notify_task_update(task_id, {"status": "cancelling"})
            logger.info(f"Initiated cancellation of task {task_id}")
            return True
        
        return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Get the current status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Optional[Dict]: Task status and results if found, None otherwise
        """
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "status": task["status"],
            "result": task.get("result"),
            "error": task.get("error")
        }
    
    async def register_websocket(self, task_id: str, websocket: WebSocket):
        """
        Register a WebSocket connection for real-time task updates.
        
        Args:
            task_id: ID of the task to subscribe to
            websocket: WebSocket connection
        """
        if task_id not in self.websockets:
            self.websockets[task_id] = []
        
        self.websockets[task_id].append(websocket)
        
        # Send initial status
        status = await self.get_task_status(task_id)
        if status:
            await websocket.send_text(json.dumps(status))
    
    async def unregister_websocket(self, task_id: str, websocket: WebSocket):
        """
        Unregister a WebSocket connection.
        
        Args:
            task_id: ID of the task
            websocket: WebSocket connection to unregister
        """
        if task_id in self.websockets:
            try:
                self.websockets[task_id].remove(websocket)
            except ValueError:
                pass
    
    async def _notify_task_update(self, task_id: str, update: Dict):
        """
        Send task updates to all registered WebSocket connections.
        
        Args:
            task_id: ID of the task
            update: Update data to send
        """
        if task_id not in self.websockets:
            return
        
        full_update = {"task_id": task_id, **update}
        
        dead_sockets = []
        for websocket in self.websockets[task_id]:
            try:
                await websocket.send_text(json.dumps(full_update))
            except Exception:
                dead_sockets.append(websocket)
        
        # Clean up dead connections
        for dead in dead_sockets:
            try:
                self.websockets[task_id].remove(dead)
            except ValueError:
                pass
    
    async def shutdown(self):
        """Clean up resources when the application is shutting down."""
        # Cancel all running tasks
        for task_id, task in self.tasks.items():
            if task["status"] == "running":
                task["status"] = "cancelled"
        
        # Close all websocket connections
        for task_id, sockets in self.websockets.items():
            for socket in sockets:
                try:
                    await socket.close()
                except Exception:
                    pass
        
        # Shutdown all components
        await asyncio.gather(
            self.browser_control.shutdown(),
            self.action_executor.shutdown(),
            self.memory.shutdown(),
            self.metrics.shutdown(),
        )
        
        logger.info("Agent Orchestrator shut down successfully")
