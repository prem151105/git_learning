"""
Action Executor module for the Action Execution Layer.

This module implements execution of both browser-based and API-driven actions
with human-like behavior and error recovery mechanisms.
"""

import asyncio
import json
import logging
import random
import time
from typing import Dict, List, Any, Optional, Union, Tuple

from ..browser_control.browser_controller import BrowserController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes both browser-based and API-driven actions.
    
    This class implements primitive actions (click, type, scroll) and complex actions
    (form filling, menu navigation) with human-like behavior.
    """
    
    def __init__(self, browser_controller, api_module):
        """
        Initialize the ActionExecutor.
        
        Args:
            browser_controller: BrowserController instance
            api_module: APIInteractionModule instance
        """
        self.browser = browser_controller
        self.api_module = api_module
        self.max_retries = 3
        
        # Action execution metrics
        self.action_history = []
        self.success_rate = 1.0
        
        logger.info("ActionExecutor instance created")
    
    async def initialize(self):
        """Initialize resources."""
        logger.info("ActionExecutor initialized successfully")
        return True
    
    async def execute_action(self, action_config: Dict) -> Dict:
        """
        Execute an action based on its configuration.
        
        Args:
            action_config: Dictionary containing action configuration
            
        Returns:
            Dict: Result of the action execution
        """
        action_type = action_config.get("type", "").lower()
        start_time = time.time()
        result = {"success": False, "elapsed_time": 0}
        
        try:
            # Determine action type and execute accordingly
            if action_type == "navigate":
                result = await self._execute_navigate(action_config)
            
            elif action_type == "click":
                result = await self._execute_click(action_config)
            
            elif action_type == "type":
                result = await self._execute_type(action_config)
            
            elif action_type == "select":
                result = await self._execute_select(action_config)
            
            elif action_type == "extract":
                result = await self._execute_extract(action_config)
            
            elif action_type == "scroll":
                result = await self._execute_scroll(action_config)
            
            elif action_type == "wait":
                result = await self._execute_wait(action_config)
            
            elif action_type == "evaluate":
                result = await self._execute_evaluate(action_config)
            
            elif action_type == "api_call":
                result = await self._execute_api_call(action_config)
            
            elif action_type == "form_fill":
                result = await self._execute_form_fill(action_config)
            
            elif action_type == "extract_table":
                result = await self._execute_extract_table(action_config)
            
            else:
                result = {
                    "success": False,
                    "error": f"Unknown action type: {action_type}"
                }
            
            # Record execution time
            result["elapsed_time"] = time.time() - start_time
            
            # Record action history for analytics
            self._record_action(action_config, result)
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_result = {
                "success": False,
                "error": str(e),
                "elapsed_time": elapsed_time
            }
            
            # Record failed action
            self._record_action(action_config, error_result)
            
            logger.error(f"Error executing {action_type} action: {str(e)}")
            return error_result
    
    async def _execute_navigate(self, config: Dict) -> Dict:
        """Execute a navigate action."""
        url = config.get("url")
        if not url:
            return {"success": False, "error": "URL is required for navigate action"}
        
        wait_for_load = config.get("wait_for_load", True)
        timeout = config.get("timeout", 60000)
        
        success = await self.browser.navigate(url)
        
        if success and wait_for_load:
            await self.browser.wait_for_navigation(timeout=timeout)
        
        return {
            "success": success,
            "current_url": await self.browser.eval_javascript("window.location.href")
        }
    
    async def _execute_click(self, config: Dict) -> Dict:
        """Execute a click action with retries."""
        selector = config.get("selector")
        if not selector:
            return {"success": False, "error": "Selector is required for click action"}
        
        timeout = config.get("timeout", 10000)
        retries = min(config.get("retries", self.max_retries), self.max_retries)
        
        for attempt in range(retries):
            success = await self.browser.click(selector, timeout)
            if success:
                return {"success": True}
            
            if attempt < retries - 1:
                # Add exponential backoff between retries
                await asyncio.sleep(0.5 * (2 ** attempt))
                logger.info(f"Retrying click on {selector}, attempt {attempt + 2}/{retries}")
        
        return {
            "success": False,
            "error": f"Failed to click on {selector} after {retries} attempts"
        }
    
    async def _execute_type(self, config: Dict) -> Dict:
        """Execute a type action."""
        selector = config.get("selector")
        text = config.get("text")
        
        if not selector or text is None:
            return {"success": False, "error": "Selector and text are required for type action"}
        
        # Convert to string in case text is a number or other type
        text = str(text)
        
        delay = config.get("delay", 10)  # Default 10ms between keystrokes
        
        success = await self.browser.type_text(selector, text, delay)
        
        return {"success": success}
    
    async def _execute_select(self, config: Dict) -> Dict:
        """Execute a select action for dropdowns."""
        selector = config.get("selector")
        value = config.get("value")
        
        if not selector or value is None:
            return {"success": False, "error": "Selector and value are required for select action"}
        
        success = await self.browser.select_option(selector, value)
        
        return {"success": success}
    
    async def _execute_extract(self, config: Dict) -> Dict:
        """Execute a data extraction action."""
        selector = config.get("selector")
        attribute = config.get("attribute", "textContent")
        
        if not selector:
            return {"success": False, "error": "Selector is required for extract action"}
        
        try:
            element = await self.browser.find_element(selector)
            if not element:
                return {"success": False, "error": f"Element with selector {selector} not found"}
            
            if attribute == "textContent":
                value = await element.text_content()
            else:
                value = await element.get_attribute(attribute)
            
            return {
                "success": True,
                "value": value
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_scroll(self, config: Dict) -> Dict:
        """Execute a scroll action."""
        selector = config.get("selector")
        x = config.get("x")
        y = config.get("y")
        
        try:
            if selector:
                # Scroll element into view
                element = await self.browser.find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element with selector {selector} not found"}
                
                await element.scroll_into_view_if_needed()
                return {"success": True}
                
            elif x is not None or y is not None:
                # Scroll to coordinates
                script = f"window.scrollTo({x or 0}, {y or 0});"
                await self.browser.eval_javascript(script)
                return {"success": True}
            
            else:
                return {"success": False, "error": "Either selector or x/y coordinates are required for scroll action"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_wait(self, config: Dict) -> Dict:
        """Execute a wait action."""
        wait_type = config.get("wait_type", "timeout")
        value = config.get("value")
        
        if wait_type == "timeout":
            # Wait for a specified time in milliseconds
            duration = value if value is not None else 1000
            await asyncio.sleep(duration / 1000)
            return {"success": True}
            
        elif wait_type == "selector":
            # Wait for an element to appear
            selector = value
            timeout = config.get("timeout", 10000)
            
            element = await self.browser.find_element(selector, timeout)
            return {"success": element is not None}
            
        elif wait_type == "navigation":
            # Wait for navigation to complete
            timeout = value if value is not None else 30000
            success = await self.browser.wait_for_navigation(timeout)
            return {"success": success}
            
        else:
            return {"success": False, "error": f"Unknown wait type: {wait_type}"}
    
    async def _execute_evaluate(self, config: Dict) -> Dict:
        """Execute a JavaScript evaluation action."""
        script = config.get("script")
        
        if not script:
            return {"success": False, "error": "Script is required for evaluate action"}
        
        try:
            result = await self.browser.eval_javascript(script)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_api_call(self, config: Dict) -> Dict:
        """Execute an API call action using the API module."""
        if not self.api_module:
            return {"success": False, "error": "API module not available"}
        
        return await self.api_module.call_api(config)
    
    async def _execute_form_fill(self, config: Dict) -> Dict:
        """Execute a complex form filling action."""
        form_selector = config.get("form_selector")
        fields = config.get("fields", [])
        submit_selector = config.get("submit_selector")
        
        if not form_selector or not fields:
            return {"success": False, "error": "Form selector and fields are required for form_fill action"}
        
        results = []
        
        try:
            # Find the form element
            form = await self.browser.find_element(form_selector)
            if not form:
                return {"success": False, "error": f"Form element with selector {form_selector} not found"}
            
            # Fill each field
            for field in fields:
                field_selector = field.get("selector")
                field_type = field.get("type", "text")
                field_value = field.get("value")
                
                if not field_selector or field_value is None:
                    results.append({
                        "field": field_selector,
                        "success": False,
                        "error": "Field selector and value are required"
                    })
                    continue
                
                if field_type == "text":
                    success = await self.browser.type_text(field_selector, str(field_value))
                elif field_type == "select":
                    success = await self.browser.select_option(field_selector, field_value)
                elif field_type == "checkbox":
                    # Toggle checkbox according to value
                    script = f"""
                        (function() {{
                            const checkbox = document.querySelector("{field_selector}");
                            if (checkbox) {{
                                checkbox.checked = {str(field_value).lower()};
                                return true;
                            }}
                            return false;
                        }})()
                    """
                    success = await self.browser.eval_javascript(script)
                elif field_type == "radio":
                    # Select radio button
                    script = f"""
                        (function() {{
                            const radio = document.querySelector("{field_selector}[value='{field_value}']");
                            if (radio) {{
                                radio.checked = true;
                                return true;
                            }}
                            return false;
                        }})()
                    """
                    success = await self.browser.eval_javascript(script)
                else:
                    success = False
                    
                results.append({
                    "field": field_selector,
                    "success": success
                })
                
                # Add a small delay between field operations
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Submit the form if required
            if submit_selector:
                submit_success = await self.browser.click(submit_selector)
                results.append({
                    "submit": submit_selector,
                    "success": submit_success
                })
                
                # Wait for navigation if form submission causes page change
                await self.browser.wait_for_navigation()
            
            # Check overall success
            all_success = all(r.get("success", False) for r in results)
            
            return {
                "success": all_success,
                "results": results
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_extract_table(self, config: Dict) -> Dict:
        """Execute a table data extraction action."""
        table_selector = config.get("table_selector")
        
        if not table_selector:
            return {"success": False, "error": "Table selector is required for extract_table action"}
        
        try:
            # Use JavaScript to extract table data
            script = f"""
                (function() {{
                    const table = document.querySelector("{table_selector}");
                    if (!table) return null;
                    
                    const headers = Array.from(table.querySelectorAll("th")).map(th => th.textContent.trim());
                    
                    const rows = Array.from(table.querySelectorAll("tr")).slice(1);
                    const data = rows.map(row => {{
                        const cells = Array.from(row.querySelectorAll("td"));
                        return cells.map(cell => cell.textContent.trim());
                    }});
                    
                    return {{ headers, data }};
                }})()
            """
            
            result = await self.browser.eval_javascript(script)
            
            if not result:
                return {"success": False, "error": f"Table with selector {table_selector} not found or empty"}
            
            return {
                "success": True,
                "headers": result.get("headers", []),
                "data": result.get("data", [])
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _record_action(self, action_config: Dict, result: Dict):
        """Record action execution for analytics and learning."""
        self.action_history.append({
            "timestamp": time.time(),
            "action": action_config,
            "result": result
        })
        
        # Update success rate
        successful_actions = sum(1 for action in self.action_history if action["result"].get("success", False))
        total_actions = len(self.action_history)
        self.success_rate = successful_actions / total_actions if total_actions > 0 else 1.0
    
    async def shutdown(self):
        """Clean up resources."""
        logger.info("ActionExecutor resources cleaned up")
