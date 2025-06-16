"""
Hybrid Executor module for the User Interaction Layer.

This module supports both autonomous and human-assisted operation modes,
allowing users to pause, override, or provide input during task execution.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HybridExecutor:
    """
    Enables hybrid operation with human assistance.
    
    This class manages the execution of tasks with optional human intervention
    and incorporates feedback for continuous improvement.
    """
    
    def __init__(self, action_executor):
        """
        Initialize the HybridExecutor.
        
        Args:
            action_executor: ActionExecutor instance for executing actions
        """
        self.action_executor = action_executor
        self.pending_user_inputs = {}  # Request ID -> future object
        self.user_feedback = {}        # Action ID -> feedback
        self.human_assistance_mode = "review"  # "review", "approval", "manual", "autonomous"
        
        logger.info("HybridExecutor instance created")
    
    async def initialize(self):
        """Initialize resources."""
        logger.info("HybridExecutor initialized successfully")
        return True
    
    async def execute_task(self, task: Dict, human_assist: bool = False) -> Dict:
        """
        Execute a task with optional human assistance.
        
        Args:
            task: Task configuration
            human_assist: Whether to use human-assisted mode
            
        Returns:
            Dict: Task execution result
        """
        task_id = task.get("id", str(uuid.uuid4()))
        start_time = time.time()
        
        # If human assistance is not required, execute autonomously
        if not human_assist:
            return await self.execute_autonomous_action(task)
        
        # Determine the mode of human assistance
        mode = task.get("human_assist_mode", self.human_assistance_mode)
        
        try:
            if mode == "review":
                # Execute autonomously but allow human review after execution
                result = await self.execute_autonomous_action(task)
                # Store result for potential review
                self.user_feedback[task_id] = {
                    "task": task,
                    "result": result,
                    "feedback": None,
                    "timestamp": time.time()
                }
                return result
                
            elif mode == "approval":
                # Get approval before execution
                approval = await self.get_user_approval(task)
                
                if approval.get("approved", False):
                    # Execute with any user modifications
                    modified_task = approval.get("modified_task", task)
                    return await self.execute_autonomous_action(modified_task)
                else:
                    # User rejected the task
                    return {
                        "success": False,
                        "error": "Task rejected by user",
                        "elapsed_time": time.time() - start_time
                    }
                    
            elif mode == "manual":
                # Let user specify the exact action to take
                user_action = await self.get_user_input(task)
                
                if user_action:
                    # Execute the user-specified action
                    return await self.execute_user_action(user_action)
                else:
                    # User did not provide input
                    return {
                        "success": False,
                        "error": "No user input provided",
                        "elapsed_time": time.time() - start_time
                    }
                    
            else:  # "autonomous" or any other value
                # Execute autonomously
                return await self.execute_autonomous_action(task)
                
        except Exception as e:
            logger.error(f"Error in hybrid execution: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "elapsed_time": time.time() - start_time
            }
    
    async def execute_autonomous_action(self, task: Dict) -> Dict:
        """
        Execute an action autonomously without human intervention.
        
        Args:
            task: Task configuration
            
        Returns:
            Dict: Action execution result
        """
        # Use the action executor to perform the action
        return await self.action_executor.execute_action(task)
    
    async def execute_user_action(self, action: Dict) -> Dict:
        """
        Execute an action specified by the user.
        
        Args:
            action: User-specified action configuration
            
        Returns:
            Dict: Action execution result
        """
        # Record that this is a user-specified action
        action["source"] = "user"
        
        # Use the action executor to perform the action
        return await self.action_executor.execute_action(action)
    
    async def get_user_approval(self, task: Dict) -> Dict:
        """
        Get user approval for a task.
        
        Args:
            task: Task configuration to get approval for
            
        Returns:
            Dict: Approval result with potential task modifications
        """
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_user_inputs[request_id] = future
        
        try:
            # Here, we'd typically send a request to the UI for approval
            # For now, we'll simulate with a timeout
            approval = await asyncio.wait_for(future, timeout=60)  # 60-second timeout
            
            # Clean up
            del self.pending_user_inputs[request_id]
            
            return approval
            
        except asyncio.TimeoutError:
            # Handle timeout (no user response)
            del self.pending_user_inputs[request_id]
            
            return {
                "approved": False,
                "reason": "User did not respond within the timeout period",
                "request_id": request_id
            }
    
    async def get_user_input(self, context: Dict) -> Optional[Dict]:
        """
        Get input from the user for an action.
        
        Args:
            context: Context information for the user input
            
        Returns:
            Optional[Dict]: User input or None if not provided
        """
        request_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_user_inputs[request_id] = future
        
        try:
            # Here, we'd typically send a request to the UI for input
            # For now, we'll simulate with a timeout
            user_input = await asyncio.wait_for(future, timeout=60)  # 60-second timeout
            
            # Clean up
            del self.pending_user_inputs[request_id]
            
            return user_input
            
        except asyncio.TimeoutError:
            # Handle timeout (no user response)
            del self.pending_user_inputs[request_id]
            return None
    
    def provide_user_input(self, request_id: str, input_data: Dict) -> bool:
        """
        Provide user input for a pending request.
        
        This method is called externally when user input is received.
        
        Args:
            request_id: ID of the request
            input_data: User input data
            
        Returns:
            bool: True if the input was provided to a pending request, False otherwise
        """
        if request_id in self.pending_user_inputs:
            future = self.pending_user_inputs[request_id]
            if not future.done():
                future.set_result(input_data)
                return True
        
        return False
    
    def provide_user_approval(self, request_id: str, approved: bool, modified_task: Dict = None) -> bool:
        """
        Provide user approval for a pending request.
        
        This method is called externally when user approval is received.
        
        Args:
            request_id: ID of the approval request
            approved: Whether the task is approved
            modified_task: Optional modified task configuration
            
        Returns:
            bool: True if the approval was provided to a pending request, False otherwise
        """
        if request_id in self.pending_user_inputs:
            future = self.pending_user_inputs[request_id]
            if not future.done():
                future.set_result({
                    "approved": approved,
                    "modified_task": modified_task,
                    "timestamp": time.time(),
                    "request_id": request_id
                })
                return True
        
        return False
    
    def provide_feedback(self, action_id: str, feedback: Dict) -> bool:
        """
        Provide feedback for a completed action.
        
        Args:
            action_id: ID of the action
            feedback: Feedback data
            
        Returns:
            bool: True if feedback was recorded, False otherwise
        """
        if action_id in self.user_feedback:
            self.user_feedback[action_id]["feedback"] = feedback
            self.user_feedback[action_id]["feedback_timestamp"] = time.time()
            return True
        
        return False
    
    def set_assistance_mode(self, mode: str) -> bool:
        """
        Set the human assistance mode.
        
        Args:
            mode: Assistance mode ("review", "approval", "manual", "autonomous")
            
        Returns:
            bool: True if the mode was set successfully, False otherwise
        """
        valid_modes = ["review", "approval", "manual", "autonomous"]
        
        if mode.lower() in valid_modes:
            self.human_assistance_mode = mode.lower()
            logger.info(f"Human assistance mode set to {mode}")
            return True
        
        logger.warning(f"Invalid human assistance mode: {mode}")
        return False
    
    def get_assistance_mode(self) -> str:
        """
        Get the current human assistance mode.
        
        Returns:
            str: Current assistance mode
        """
        return self.human_assistance_mode
    
    def register_user_input_callback(self, callback: Callable[[str, Dict], None]) -> str:
        """
        Register a callback for when user input is needed.
        
        Args:
            callback: Callback function taking request_id and context
            
        Returns:
            str: Registration ID
        """
        # This would typically be implemented with a proper event system
        # For now, we'll just return a placeholder
        return "callback-registration-placeholder"
