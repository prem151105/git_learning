"""
API Interaction Module for the Action Execution Layer.

This module handles direct API interactions, allowing the agent to bypass
browser interactions when more efficient API-based approaches are available.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union

import aiohttp
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIInteractionModule:
    """
    Manages API-based interactions for more efficient task execution.
    
    This class allows the agent to generate and execute API calls
    based on task descriptions, improving performance over browser-only methods.
    """
    
    def __init__(self):
        """Initialize the APIInteractionModule."""
        self.session = None
        self.api_key_storage = {}
        self.default_headers = {
            "User-Agent": "AgenticBrowser/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.api_registry = {}  # Stores API specs and schemas
        self.llm_client = None
        
        logger.info("APIInteractionModule instance created")
    
    async def initialize(self):
        """Initialize resources."""
        self.session = aiohttp.ClientSession(headers=self.default_headers)
        
        # Load API key environment variables
        for key, value in os.environ.items():
            if key.endswith("_API_KEY") or key.endswith("_TOKEN"):
                self.api_key_storage[key] = value
        
        # Setup LLM client for API operation generation
        try:
            import openai
            self.llm_client = openai.AsyncClient(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            logger.info("LLM client initialized for API generation")
        except Exception as e:
            logger.error(f"Error initializing LLM client: {str(e)}")
        
        logger.info("APIInteractionModule initialized successfully")
        return True
    
    async def call_api(self, config: Dict) -> Dict:
        """
        Execute an API call based on the provided configuration.
        
        Args:
            config: API call configuration including endpoint, method, payload, etc.
            
        Returns:
            Dict: API response and metadata
        """
        endpoint = config.get("endpoint")
        method = config.get("method", "GET").upper()
        payload = config.get("payload", {})
        params = config.get("params", {})
        headers = {**self.default_headers, **(config.get("headers", {}))}
        auth_type = config.get("auth_type")
        
        if not endpoint:
            return {"success": False, "error": "API endpoint is required"}
        
        # Handle authentication
        await self._apply_authentication(headers, auth_type, endpoint)
        
        start_time = time.time()
        
        try:
            # Execute the API request
            response = await self._execute_request(method, endpoint, payload, params, headers)
            
            elapsed_time = time.time() - start_time
            
            return {
                "success": response.get("success", False),
                "status_code": response.get("status_code"),
                "data": response.get("data"),
                "headers": response.get("response_headers"),
                "elapsed_time": elapsed_time
            }
        
        except Exception as e:
            elapsed_time = time.time() - start_time
            
            logger.error(f"Error executing API call to {endpoint}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "elapsed_time": elapsed_time
            }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _execute_request(self, method: str, url: str, payload: Dict, params: Dict, headers: Dict) -> Dict:
        """
        Execute an HTTP request with retry capability.
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            url: API endpoint URL
            payload: Request body for POST/PUT methods
            params: Query parameters
            headers: HTTP headers
            
        Returns:
            Dict: Response data and metadata
        """
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.default_headers)
        
        try:
            if method == "GET":
                async with self.session.get(url, params=params, headers=headers) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data,
                        "response_headers": dict(response.headers)
                    }
                    
            elif method == "POST":
                async with self.session.post(url, json=payload, params=params, headers=headers) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data,
                        "response_headers": dict(response.headers)
                    }
                    
            elif method == "PUT":
                async with self.session.put(url, json=payload, params=params, headers=headers) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data,
                        "response_headers": dict(response.headers)
                    }
                    
            elif method == "DELETE":
                async with self.session.delete(url, params=params, headers=headers) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data,
                        "response_headers": dict(response.headers)
                    }
                    
            elif method == "PATCH":
                async with self.session.patch(url, json=payload, params=params, headers=headers) as response:
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()
                    
                    return {
                        "success": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data,
                        "response_headers": dict(response.headers)
                    }
                    
            else:
                return {
                    "success": False,
                    "error": f"Unsupported HTTP method: {method}"
                }
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {str(e)}")
            raise e
    
    async def _apply_authentication(self, headers: Dict, auth_type: str, endpoint: str):
        """
        Apply authentication to the request headers.
        
        Args:
            headers: HTTP headers to modify
            auth_type: Type of authentication (bearer, basic, etc.)
            endpoint: API endpoint URL for domain-specific auth
        """
        if not auth_type:
            return
            
        auth_type = auth_type.lower()
        
        if auth_type == "bearer":
            # Look for appropriate token based on domain
            domain = self._extract_domain(endpoint)
            token_key = f"{domain.upper().replace('.', '_')}_TOKEN"
            
            token = self.api_key_storage.get(token_key) or self.api_key_storage.get("DEFAULT_BEARER_TOKEN")
            
            if token:
                headers["Authorization"] = f"Bearer {token}"
                
        elif auth_type == "basic":
            # Look for appropriate credentials based on domain
            domain = self._extract_domain(endpoint)
            username_key = f"{domain.upper().replace('.', '_')}_USERNAME"
            password_key = f"{domain.upper().replace('.', '_')}_PASSWORD"
            
            username = self.api_key_storage.get(username_key) or self.api_key_storage.get("DEFAULT_USERNAME")
            password = self.api_key_storage.get(password_key) or self.api_key_storage.get("DEFAULT_PASSWORD")
            
            if username and password:
                import base64
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {auth_string}"
                
        elif auth_type == "api-key":
            # Look for appropriate API key based on domain
            domain = self._extract_domain(endpoint)
            api_key_name = f"{domain.upper().replace('.', '_')}_API_KEY"
            
            api_key = self.api_key_storage.get(api_key_name) or self.api_key_storage.get("DEFAULT_API_KEY")
            api_key_header = self.api_key_storage.get(f"{domain.upper().replace('.', '_')}_API_KEY_HEADER") or "X-API-Key"
            
            if api_key:
                headers[api_key_header] = api_key
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract the domain from a URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            str: Domain name
        """
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        return parsed_url.netloc
    
    async def execute_api_task(self, task_description: str) -> Dict:
        """
        Generate and execute an API call based on a task description.
        
        Args:
            task_description: Natural language description of the API task
            
        Returns:
            Dict: API response and metadata
        """
        if not self.llm_client:
            return {"success": False, "error": "LLM client not initialized for API generation"}
        
        try:
            # Generate API call specification
            api_call = await self._generate_api_call(task_description)
            
            if not api_call:
                return {"success": False, "error": "Failed to generate API call"}
            
            # Execute the generated API call
            result = await self.call_api(api_call)
            
            return {
                "success": result.get("success", False),
                "generated_api_call": api_call,
                "api_response": result
            }
            
        except Exception as e:
            logger.error(f"Error in API task execution: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _generate_api_call(self, task_description: str) -> Optional[Dict]:
        """
        Generate an API call specification based on a task description using LLMs.
        
        Args:
            task_description: Natural language description of the API task
            
        Returns:
            Optional[Dict]: Generated API call specification or None if failed
        """
        try:
            # Use available API registry to inform generation
            api_registry_summary = self._summarize_api_registry()
            
            prompt = f"""
            Generate an API call specification based on this task description:
            
            Task: {task_description}
            
            Available API endpoints: {api_registry_summary}
            
            Output should be a JSON object with these fields:
            - endpoint: The full URL of the API endpoint
            - method: HTTP method (GET, POST, PUT, DELETE, etc.)
            - payload: JSON request body (for POST/PUT)
            - params: URL query parameters (for GET/DELETE)
            - headers: Custom headers (if needed)
            - auth_type: Authentication type (bearer, basic, api-key, or null)
            
            Only include necessary fields for this specific API call.
            """
            
            response = await self.llm_client.chat.completions.create(
                model="gpt-4-turbo",  # Use appropriate model
                messages=[
                    {"role": "system", "content": "You are a specialized API call generator that converts natural language task descriptions into precise API call specifications. Generate only valid JSON with no explanation."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            api_call_json = response.choices[0].message.content
            
            # Parse and validate the API call specification
            api_call = json.loads(api_call_json)
            
            # Basic validation
            if "endpoint" not in api_call:
                return None
            
            return api_call
            
        except Exception as e:
            logger.error(f"Error generating API call: {str(e)}")
            return None
    
    def _summarize_api_registry(self) -> str:
        """
        Generate a summary of available API endpoints in the registry.
        
        Returns:
            str: Summary of available API endpoints
        """
        if not self.api_registry:
            return "No pre-registered APIs available. Generate based on task description."
        
        summary_parts = []
        
        for api_name, api_spec in self.api_registry.items():
            endpoints = api_spec.get("endpoints", [])
            endpoint_summary = ", ".join([f"{e.get('method', 'GET')} {e.get('path')}" for e in endpoints[:5]])
            
            if len(endpoints) > 5:
                endpoint_summary += f" and {len(endpoints) - 5} more"
                
            summary_parts.append(f"{api_name}: {endpoint_summary}")
        
        return "; ".join(summary_parts)
    
    async def register_api_spec(self, api_name: str, spec_url: str = None, spec_json: Dict = None) -> bool:
        """
        Register an API specification for improved generation.
        
        Args:
            api_name: Name of the API
            spec_url: URL to OpenAPI/Swagger specification
            spec_json: OpenAPI/Swagger specification as JSON
            
        Returns:
            bool: True if registration was successful, False otherwise
        """
        try:
            if spec_url:
                # Fetch OpenAPI spec from URL
                async with self.session.get(spec_url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        
                        if 'application/json' in content_type:
                            spec_json = await response.json()
                        else:
                            spec_text = await response.text()
                            try:
                                spec_json = json.loads(spec_text)
                            except:
                                return False
            
            if not spec_json:
                return False
                
            # Process OpenAPI spec to extract endpoints
            endpoints = []
            
            if "paths" in spec_json:
                for path, methods in spec_json["paths"].items():
                    for method, details in methods.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            endpoints.append({
                                "path": path,
                                "method": method.upper(),
                                "summary": details.get("summary", ""),
                                "description": details.get("description", ""),
                                "parameters": details.get("parameters", []),
                                "requestBody": details.get("requestBody")
                            })
            
            # Store in registry
            self.api_registry[api_name] = {
                "name": api_name,
                "base_url": spec_json.get("servers", [{}])[0].get("url", ""),
                "endpoints": endpoints,
                "full_spec": spec_json
            }
            
            logger.info(f"Successfully registered API spec for {api_name} with {len(endpoints)} endpoints")
            return True
            
        except Exception as e:
            logger.error(f"Error registering API spec: {str(e)}")
            return False
    
    async def shutdown(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
        
        logger.info("APIInteractionModule resources cleaned up")
