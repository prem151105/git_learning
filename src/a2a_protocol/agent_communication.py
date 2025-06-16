"""
Agent Communication module for the A2A Protocol Layer.

This module implements the Agent-to-Agent (A2A) protocol for enabling
communication and collaboration between multiple AI agents.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union, Callable

import aiohttp
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class A2AProtocol:
    """
    Implements the Agent-to-Agent (A2A) protocol.
    
    This class manages communication between AI agents, enabling task delegation,
    coordination, and information exchange for complex multi-agent workflows.
    """
    
    def __init__(self):
        """Initialize the A2AProtocol."""
        self.agent_id = str(uuid.uuid4())
        self.agent_name = "Browser Agent"
        self.agent_capabilities = [
            "web_browsing",
            "form_filling",
            "data_extraction",
            "api_calling",
            "content_analysis"
        ]
        
        self.known_agents = {}  # agent_id -> agent_info
        self.active_conversations = {}  # conversation_id -> conversation_data
        self.pending_requests = {}  # request_id -> future
        
        self.session = None
        self.message_handlers = []
        
        logger.info("A2AProtocol instance created")
    
    async def initialize(self, agent_name: str = None, capabilities: List[str] = None):
        """
        Initialize the A2A protocol.
        
        Args:
            agent_name: Optional custom name for this agent
            capabilities: Optional list of agent capabilities
            
        Returns:
            bool: True if initialization was successful
        """
        try:
            self.session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"A2A-Protocol/2025 {self.agent_name}"
                }
            )
            
            if agent_name:
                self.agent_name = agent_name
                
            if capabilities:
                self.agent_capabilities = capabilities
            
            # Register default message handlers
            self._register_default_handlers()
            
            logger.info(f"A2A Protocol initialized for agent {self.agent_name} ({self.agent_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing A2A Protocol: {str(e)}")
            return False
    
    async def register_with_directory(self, directory_url: str) -> bool:
        """
        Register this agent with a central agent directory.
        
        Args:
            directory_url: URL of the agent directory service
            
        Returns:
            bool: True if registration was successful
        """
        try:
            registration_data = {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "capabilities": self.agent_capabilities,
                "status": "online",
                "version": "1.0.0",
                "protocol_version": "A2A-2025",
                "timestamp": time.time()
            }
            
            async with self.session.post(
                f"{directory_url}/register",
                json=registration_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully registered with agent directory: {data.get('message', 'OK')}")
                    return True
                else:
                    logger.error(f"Failed to register with agent directory. Status: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error registering with agent directory: {str(e)}")
            return False
    
    async def discover_agents(self, directory_url: str, capabilities: List[str] = None) -> List[Dict]:
        """
        Discover other agents with specific capabilities.
        
        Args:
            directory_url: URL of the agent directory service
            capabilities: Optional list of required capabilities to filter by
            
        Returns:
            List[Dict]: List of discovered agents
        """
        try:
            params = {}
            if capabilities:
                params["capabilities"] = ",".join(capabilities)
            
            async with self.session.get(
                f"{directory_url}/discover",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    agents = data.get("agents", [])
                    
                    # Update known agents
                    for agent in agents:
                        agent_id = agent.get("agent_id")
                        if agent_id and agent_id != self.agent_id:
                            self.known_agents[agent_id] = agent
                    
                    logger.info(f"Discovered {len(agents)} agents")
                    return agents
                else:
                    logger.error(f"Failed to discover agents. Status: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error discovering agents: {str(e)}")
            return []
    
    async def send_message(self, recipient_id: str, message_type: str, content: Dict, conversation_id: str = None) -> Dict:
        """
        Send a message to another agent.
        
        Args:
            recipient_id: ID of the recipient agent
            message_type: Type of message (e.g., 'request', 'response', 'update')
            content: Message content
            conversation_id: Optional ID for an ongoing conversation
            
        Returns:
            Dict: Message receipt confirmation
        """
        try:
            # Create a new conversation if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                self.active_conversations[conversation_id] = {
                    "start_time": time.time(),
                    "participants": [self.agent_id, recipient_id],
                    "messages": []
                }
            
            # Create message
            message = {
                "message_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "sender_id": self.agent_id,
                "sender_name": self.agent_name,
                "recipient_id": recipient_id,
                "message_type": message_type,
                "content": content,
                "timestamp": time.time(),
                "protocol_version": "A2A-2025"
            }
            
            # Store in conversation history
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id]["messages"].append(message)
            
            # Get recipient endpoint
            recipient = self.known_agents.get(recipient_id)
            if not recipient or "endpoint" not in recipient:
                raise ValueError(f"Unknown recipient or missing endpoint: {recipient_id}")
            
            # Send message to recipient
            async with self.session.post(
                f"{recipient['endpoint']}/receive",
                json=message
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Message sent successfully to {recipient_id}: {message_type}")
                    return {
                        "success": True,
                        "message_id": message["message_id"],
                        "conversation_id": conversation_id,
                        "receipt": data
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message to {recipient_id}. Status: {response.status}, Error: {error_text}")
                    return {
                        "success": False,
                        "error": f"Failed to send message. Status: {response.status}"
                    }
                    
        except Exception as e:
            logger.error(f"Error sending message to {recipient_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def request_task(self, recipient_id: str, task_description: str, parameters: Dict = None, timeout: int = 60) -> Dict:
        """
        Request another agent to perform a task.
        
        Args:
            recipient_id: ID of the recipient agent
            task_description: Description of the requested task
            parameters: Optional parameters for the task
            timeout: Timeout in seconds for the request
            
        Returns:
            Dict: Task result or error
        """
        try:
            # Create a unique request ID
            request_id = str(uuid.uuid4())
            
            # Create a future for the response
            future = asyncio.get_event_loop().create_future()
            self.pending_requests[request_id] = future
            
            # Create the task request message
            content = {
                "request_id": request_id,
                "task_description": task_description,
                "parameters": parameters or {},
                "response_required": True,
                "timeout_seconds": timeout
            }
            
            # Send the request
            result = await self.send_message(recipient_id, "task_request", content)
            
            if not result.get("success", False):
                # Failed to send request
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                return {
                    "success": False,
                    "error": result.get("error", "Failed to send task request")
                }
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return {
                    "success": True,
                    "request_id": request_id,
                    "response": response
                }
                
            except asyncio.TimeoutError:
                # Request timed out
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                return {
                    "success": False,
                    "error": f"Request timed out after {timeout} seconds"
                }
                
        except Exception as e:
            logger.error(f"Error requesting task from {recipient_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_incoming_message(self, message: Dict) -> Dict:
        """
        Handle an incoming message from another agent.
        
        Args:
            message: Incoming message data
            
        Returns:
            Dict: Response data
        """
        try:
            # Validate message format
            if not self._validate_message(message):
                return {
                    "success": False,
                    "error": "Invalid message format"
                }
            
            # Store in conversation history
            conversation_id = message.get("conversation_id")
            if conversation_id not in self.active_conversations:
                self.active_conversations[conversation_id] = {
                    "start_time": time.time(),
                    "participants": [message.get("sender_id"), self.agent_id],
                    "messages": []
                }
            
            self.active_conversations[conversation_id]["messages"].append(message)
            
            # Process message based on type
            message_type = message.get("message_type", "").lower()
            content = message.get("content", {})
            
            # Find handler for message type
            for handler in self.message_handlers:
                if handler["type"] == message_type:
                    return await handler["handler"](message, content)
            
            # Default handler if no specific handler found
            logger.warning(f"No handler for message type: {message_type}")
            return {
                "success": True,
                "message": "Message received but not processed",
                "handled": False
            }
            
        except Exception as e:
            logger.error(f"Error handling incoming message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def respond_to_task(self, request_id: str, result: Dict, conversation_id: str, recipient_id: str) -> Dict:
        """
        Respond to a task request from another agent.
        
        Args:
            request_id: Original request ID
            result: Task execution result
            conversation_id: Ongoing conversation ID
            recipient_id: ID of the requesting agent
            
        Returns:
            Dict: Response status
        """
        content = {
            "request_id": request_id,
            "result": result,
            "timestamp": time.time()
        }
        
        return await self.send_message(recipient_id, "task_response", content, conversation_id)
    
    def register_message_handler(self, message_type: str, handler: Callable[[Dict, Dict], Dict]) -> bool:
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of messages to handle
            handler: Async function to handle messages of this type
            
        Returns:
            bool: True if registration was successful
        """
        # Check for existing handler of the same type
        for existing in self.message_handlers:
            if existing["type"] == message_type:
                # Update existing handler
                existing["handler"] = handler
                logger.info(f"Updated handler for message type: {message_type}")
                return True
        
        # Add new handler
        self.message_handlers.append({
            "type": message_type,
            "handler": handler
        })
        
        logger.info(f"Registered new handler for message type: {message_type}")
        return True
    
    def _validate_message(self, message: Dict) -> bool:
        """
        Validate the format of an incoming message.
        
        Args:
            message: Message to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = ["message_id", "conversation_id", "sender_id", "message_type", "content"]
        
        for field in required_fields:
            if field not in message:
                logger.error(f"Missing required field in message: {field}")
                return False
        
        return True
    
    async def _handle_task_request(self, message: Dict, content: Dict) -> Dict:
        """
        Handle a task request from another agent.
        
        Args:
            message: Full message data
            content: Message content
            
        Returns:
            Dict: Response data
        """
        # This would typically delegate to the appropriate handler based on task type
        # For now, we'll just acknowledge receipt
        return {
            "success": True,
            "message": "Task request acknowledged",
            "request_id": content.get("request_id")
        }
    
    async def _handle_task_response(self, message: Dict, content: Dict) -> Dict:
        """
        Handle a task response from another agent.
        
        Args:
            message: Full message data
            content: Message content
            
        Returns:
            Dict: Response data
        """
        request_id = content.get("request_id")
        
        # Check if we have a pending request with this ID
        if request_id in self.pending_requests:
            future = self.pending_requests[request_id]
            if not future.done():
                # Resolve the future with the response
                future.set_result(content.get("result"))
            
            # Clean up
            del self.pending_requests[request_id]
            
            return {
                "success": True,
                "message": "Task response processed"
            }
        else:
            logger.warning(f"Received response for unknown request: {request_id}")
            return {
                "success": True,
                "message": "No pending request found for this ID",
                "request_id": request_id
            }
    
    def _register_default_handlers(self):
        """Register default message handlers."""
        self.register_message_handler("task_request", self._handle_task_request)
        self.register_message_handler("task_response", self._handle_task_response)
        
        # Other default handlers could be registered here
    
    async def get_conversation_history(self, conversation_id: str) -> Dict:
        """
        Get the history of a conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Dict: Conversation data
        """
        if conversation_id in self.active_conversations:
            return {
                "success": True,
                "conversation": self.active_conversations[conversation_id]
            }
        else:
            return {
                "success": False,
                "error": f"Conversation not found: {conversation_id}"
            }
    
    async def shutdown(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
        
        logger.info("A2A Protocol resources cleaned up")
