"""
Task Planner module for the Planning & Reasoning Layer.

This module implements task decomposition and decision-making capabilities,
using chain-of-thought or tree-of-thought reasoning for complex tasks.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskPlanner:
    """
    Decomposes tasks and makes dynamic decisions.
    
    This class uses LFMs for chain-of-thought or tree-of-thought reasoning
    to break down high-level goals into actionable steps.
    """
    
    def __init__(self):
        """Initialize the TaskPlanner."""
        self.llm_client = None
        self.planning_model = os.environ.get("PLANNING_MODEL", "gpt-4-turbo")
        self.planning_approach = os.environ.get("PLANNING_APPROACH", "chain-of-thought")
        
        # Cache for similar tasks planning
        self.plan_cache = {}
        
        logger.info("TaskPlanner instance created")
    
    async def initialize(self):
        """Initialize resources."""
        try:
            import openai
            self.llm_client = openai.AsyncClient(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            
            logger.info("TaskPlanner initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing task planner: {str(e)}")
            return False
    
    async def decompose_task(self, high_level_goal: str, current_state: Dict = None, urls: List[str] = None) -> Dict:
        """
        Decompose a high-level goal into actionable steps.
        
        Args:
            high_level_goal: The high-level task description
            current_state: Current state of the system (optional)
            urls: Relevant URLs for the task (optional)
            
        Returns:
            Dict: Decomposed task plan with actionable steps
        """
        start_time = time.time()
        
        try:
            # Check for cached similar plans
            cache_key = self._generate_cache_key(high_level_goal, urls)
            if cache_key in self.plan_cache:
                # Adapt the cached plan to the current task
                return await self._adapt_cached_plan(self.plan_cache[cache_key], high_level_goal, current_state)
            
            # Generate a plan based on the planning approach
            if self.planning_approach == "chain-of-thought":
                plan = await self._chain_of_thought_planning(high_level_goal, current_state, urls)
            elif self.planning_approach == "tree-of-thought":
                plan = await self._tree_of_thought_planning(high_level_goal, current_state, urls)
            else:
                # Default to chain-of-thought
                plan = await self._chain_of_thought_planning(high_level_goal, current_state, urls)
            
            # Cache the plan for future reference
            self.plan_cache[cache_key] = plan
            
            elapsed_time = time.time() - start_time
            logger.info(f"Task decomposition completed in {elapsed_time:.2f} seconds")
            
            return plan
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Error decomposing task: {str(e)}")
            
            # Return a minimal plan with the error
            return {
                "task": high_level_goal,
                "error": str(e),
                "steps": [],
                "elapsed_time": elapsed_time
            }
    
    async def _chain_of_thought_planning(self, goal: str, current_state: Dict = None, urls: List[str] = None) -> Dict:
        """
        Use chain-of-thought reasoning to decompose a task.
        
        Args:
            goal: High-level goal description
            current_state: Current state of the system (optional)
            urls: Relevant URLs for the task (optional)
            
        Returns:
            Dict: Decomposed task plan
        """
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        url_context = "No specific URLs provided."
        if urls:
            url_context = f"Task involves the following URLs: {', '.join(urls)}"
        
        state_context = "No specific current state information provided."
        if current_state:
            state_context = f"Current state: {json.dumps(current_state, indent=2)}"
        
        prompt = f"""
        I need to decompose this high-level task into a sequence of executable steps:
        
        Task: {goal}
        
        {url_context}
        
        {state_context}
        
        Please think step by step and break this task down into:
        1. A sequence of actionable steps that a browser automation agent can execute
        2. Each step should have a specific action type (navigate, click, type, etc.)
        3. Include necessary parameters for each action
        4. Consider potential error cases and decision points
        
        For each step, provide:
        - A clear description of what the step does
        - The action type (navigate, click, type, select, wait, extract, api_call, etc.)
        - All required parameters for that action type
        - Any conditional logic or decision points
        
        Structure your response as a valid JSON object with fields:
        - task: the original task
        - steps: array of step objects with action parameters
        - estimated_time_seconds: estimated time to complete all steps
        - potential_issues: array of potential issues that might arise
        """
        
        response = await self.llm_client.chat.completions.create(
            model=self.planning_model,
            messages=[
                {"role": "system", "content": "You are a specialized AI task planner that decomposes high-level tasks into precise, executable steps for a browser automation agent. You excel at translating goals into structured action plans."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and validate the plan
        plan_json = response.choices[0].message.content
        plan = json.loads(plan_json)
        
        # Ensure plan has required fields
        if "steps" not in plan:
            plan["steps"] = []
            
        if "task" not in plan:
            plan["task"] = goal
            
        if "estimated_time_seconds" not in plan:
            plan["estimated_time_seconds"] = 60  # Default estimate
            
        if "potential_issues" not in plan:
            plan["potential_issues"] = []
        
        return plan
    
    async def _tree_of_thought_planning(self, goal: str, current_state: Dict = None, urls: List[str] = None) -> Dict:
        """
        Use tree-of-thought reasoning to decompose a task with alternatives.
        
        Args:
            goal: High-level goal description
            current_state: Current state of the system (optional)
            urls: Relevant URLs for the task (optional)
            
        Returns:
            Dict: Decomposed task plan with alternatives
        """
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        url_context = "No specific URLs provided."
        if urls:
            url_context = f"Task involves the following URLs: {', '.join(urls)}"
        
        state_context = "No specific current state information provided."
        if current_state:
            state_context = f"Current state: {json.dumps(current_state, indent=2)}"
        
        prompt = f"""
        I need to decompose this high-level task into a sequence of executable steps with alternatives for complex decision points:
        
        Task: {goal}
        
        {url_context}
        
        {state_context}
        
        Please use tree-of-thought reasoning to:
        1. Break this task down into a primary sequence of actionable steps
        2. For complex steps, provide alternative approaches (creating a tree structure)
        3. Each step should have a specific action type and parameters
        4. Include decision logic to choose between alternatives based on runtime conditions
        
        For each step, provide:
        - A clear description of what the step does
        - The action type (navigate, click, type, select, wait, extract, api_call, etc.)
        - All required parameters for that action type
        - For complex steps, alternative approaches with conditions for choosing each approach
        
        Structure your response as a valid JSON object with fields:
        - task: the original task
        - steps: array of step objects with action parameters and alternatives
        - decision_points: array of points where runtime decisions must be made
        - estimated_time_seconds: estimated time to complete
        - potential_issues: array of potential issues
        """
        
        response = await self.llm_client.chat.completions.create(
            model=self.planning_model,
            messages=[
                {"role": "system", "content": "You are a specialized AI task planner that decomposes complex tasks using tree-of-thought reasoning, considering multiple approaches and decision points. You create structured plans with alternatives for a browser automation agent."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and validate the plan
        plan_json = response.choices[0].message.content
        plan = json.loads(plan_json)
        
        # Ensure plan has required fields
        if "steps" not in plan:
            plan["steps"] = []
            
        if "task" not in plan:
            plan["task"] = goal
            
        if "decision_points" not in plan:
            plan["decision_points"] = []
            
        if "estimated_time_seconds" not in plan:
            plan["estimated_time_seconds"] = 60  # Default estimate
            
        if "potential_issues" not in plan:
            plan["potential_issues"] = []
        
        return plan
    
    def _generate_cache_key(self, goal: str, urls: List[str] = None) -> str:
        """
        Generate a cache key for plan caching.
        
        Args:
            goal: High-level goal description
            urls: Relevant URLs for the task (optional)
            
        Returns:
            str: Cache key
        """
        # Simple cache key generation, could be enhanced with embedding-based similarity
        key_parts = [goal.lower().strip()]
        
        if urls:
            key_parts.append(",".join(sorted(urls)))
            
        return "_".join(key_parts)
    
    async def _adapt_cached_plan(self, cached_plan: Dict, new_goal: str, current_state: Dict = None) -> Dict:
        """
        Adapt a cached plan to a new similar task.
        
        Args:
            cached_plan: Previously generated plan
            new_goal: New high-level goal
            current_state: Current state of the system (optional)
            
        Returns:
            Dict: Adapted plan for new task
        """
        if not self.llm_client:
            # Just return the cached plan with updated task field
            adapted_plan = cached_plan.copy()
            adapted_plan["task"] = new_goal
            return adapted_plan
        
        prompt = f"""
        I have a previously generated plan for a similar task. Please adapt this plan to fit the new task:
        
        Original Plan: {json.dumps(cached_plan, indent=2)}
        
        New Task: {new_goal}
        
        Current State: {json.dumps(current_state, indent=2) if current_state else "No specific state information provided."}
        
        Modify the plan as needed while maintaining its structure. You can:
        1. Update step descriptions and parameters
        2. Add or remove steps as necessary
        3. Adjust decision points and alternatives
        4. Update time estimates and potential issues
        
        Return the adapted plan as a valid JSON object with the same structure as the original plan.
        """
        
        response = await self.llm_client.chat.completions.create(
            model=self.planning_model,
            messages=[
                {"role": "system", "content": "You are a specialized AI task planner that can adapt existing plans to new but similar tasks. You maintain the structure while making appropriate adjustments."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and validate the adapted plan
        adapted_plan_json = response.choices[0].message.content
        adapted_plan = json.loads(adapted_plan_json)
        
        # Ensure plan has required fields
        if "task" not in adapted_plan:
            adapted_plan["task"] = new_goal
            
        return adapted_plan
    
    async def replan_on_failure(self, original_plan: Dict, failed_step: int, failure_reason: str, current_state: Dict = None) -> Dict:
        """
        Generate a new plan when a step fails.
        
        Args:
            original_plan: The original plan that failed
            failed_step: Index of the step that failed
            failure_reason: Reason for the failure
            current_state: Current state of the system (optional)
            
        Returns:
            Dict: Updated plan to handle the failure
        """
        if not self.llm_client:
            raise ValueError("LLM client not initialized")
        
        prompt = f"""
        A step in our task execution plan has failed. Please generate a revised plan to handle this failure:
        
        Original Plan: {json.dumps(original_plan, indent=2)}
        
        Failed Step: Step #{failed_step + 1} - {json.dumps(original_plan["steps"][failed_step], indent=2) if failed_step < len(original_plan.get("steps", [])) else "Unknown step"}
        
        Failure Reason: {failure_reason}
        
        Current State: {json.dumps(current_state, indent=2) if current_state else "No specific state information provided."}
        
        Please:
        1. Analyze the failure and determine if we need to retry the step with modifications, try an alternative approach, or skip the failed step
        2. Create a revised plan that adapts to this failure
        3. Include any additional error handling steps that may be needed
        
        Return the revised plan as a valid JSON object with the same structure as the original plan.
        """
        
        response = await self.llm_client.chat.completions.create(
            model=self.planning_model,
            messages=[
                {"role": "system", "content": "You are a specialized AI task planner that can revise plans when steps fail. You adapt plans to handle failures and continue making progress toward the goal."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and validate the revised plan
        revised_plan_json = response.choices[0].message.content
        revised_plan = json.loads(revised_plan_json)
        
        # Add metadata about the replanning
        revised_plan["replanned"] = True
        revised_plan["original_failed_step"] = failed_step
        revised_plan["failure_reason"] = failure_reason
        
        return revised_plan
    
    async def analyze_decision_point(self, decision_point: Dict, current_state: Dict) -> Dict:
        """
        Analyze a decision point and recommend the best option.
        
        Args:
            decision_point: Decision point configuration
            current_state: Current state of the system
            
        Returns:
            Dict: Decision analysis with recommended option
        """
        if not self.llm_client:
            # Return first option as default if no LLM is available
            return {
                "decision_id": decision_point.get("id", "unknown"),
                "recommended_option": decision_point.get("options", [{}])[0].get("id", "default"),
                "confidence": 0.5,
                "reasoning": "Default selection due to LLM unavailability."
            }
        
        prompt = f"""
        I need to analyze this decision point based on the current state:
        
        Decision Point: {json.dumps(decision_point, indent=2)}
        
        Current State: {json.dumps(current_state, indent=2)}
        
        Please:
        1. Analyze each option in the decision point
        2. Consider the current state and how it affects the decision
        3. Provide reasoning for your recommendation
        4. Return your analysis with a confidence score
        
        Structure your response as a valid JSON object with fields:
        - decision_id: the ID from the decision point
        - recommended_option: the ID of your recommended option
        - confidence: a number between 0 and 1 indicating confidence
        - reasoning: explanation of your recommendation
        - alternative_options: ranked list of other options in order of preference
        """
        
        response = await self.llm_client.chat.completions.create(
            model=self.planning_model,
            messages=[
                {"role": "system", "content": "You are a specialized AI decision analyzer that evaluates options at decision points based on current state. You provide clear recommendations with confidence scores and reasoning."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse and validate the decision analysis
        analysis_json = response.choices[0].message.content
        analysis = json.loads(analysis_json)
        
        # Ensure analysis has required fields
        if "decision_id" not in analysis:
            analysis["decision_id"] = decision_point.get("id", "unknown")
            
        if "recommended_option" not in analysis:
            # Default to first option
            analysis["recommended_option"] = decision_point.get("options", [{}])[0].get("id", "default")
            
        if "confidence" not in analysis:
            analysis["confidence"] = 0.5  # Default confidence
            
        if "reasoning" not in analysis:
            analysis["reasoning"] = "No specific reasoning provided."
            
        return analysis
