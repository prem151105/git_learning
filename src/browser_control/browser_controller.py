"""
Browser Controller module for the Browser Control Layer.

This module manages browser interactions, supports headless and non-headless modes,
and implements self-healing mechanisms for locating elements in dynamic environments.
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Union, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrowserController:
    """
    Manages browser interactions with self-healing capabilities.
    
    This class provides methods for browser automation using Playwright,
    with smart element locating strategies and real-time monitoring.
    """
    
    def __init__(self):
        """Initialize the BrowserController."""
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.active_pages = {}  # url -> page
        self.is_initialized = False
        self.default_timeout = 30000  # 30 seconds in milliseconds
        
        # Configuration
        self.headless = os.environ.get("HEADLESS_MODE", "false").lower() == "true"
        self.browser_type = os.environ.get("BROWSER_TYPE", "chromium").lower()
        self.user_agent = os.environ.get(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        logger.info("BrowserController instance created")
    
    async def initialize(self):
        """Initialize the browser and context."""
        if self.is_initialized:
            return True
        
        try:
            self.playwright = await async_playwright().start()
            
            # Select browser type
            if self.browser_type == "chromium":
                browser_instance = self.playwright.chromium
            elif self.browser_type == "firefox":
                browser_instance = self.playwright.firefox
            elif self.browser_type == "webkit":
                browser_instance = self.playwright.webkit
            else:
                browser_instance = self.playwright.chromium
            
            # Launch browser
            self.browser = await browser_instance.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials'
                ]
            )
            
            # Create context with various bypass settings
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=self.user_agent,
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation", "notifications"],
                java_script_enabled=True
            )
            
            # Configure page timeouts and behaviors
            self.page = await self.context.new_page()
            await self.page.set_default_timeout(self.default_timeout)
            
            # Set up additional event listeners
            self.page.on("dialog", self._handle_dialog)
            self.page.on("console", self._handle_console_message)
            
            self.is_initialized = True
            logger.info(f"Browser initialized: {self.browser_type} (headless: {self.headless})")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing browser: {str(e)}")
            return False
    
    async def navigate(self, url: str) -> bool:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                return False
        
        try:
            response = await self.page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait for any lazy-loaded content
            await asyncio.sleep(2)
            
            if response and response.ok:
                logger.info(f"Successfully navigated to {url}")
                return True
            else:
                status = response.status if response else "unknown"
                logger.warning(f"Navigation to {url} returned status {status}")
                return False
        
        except Exception as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            return False
    
    async def get_page_data(self) -> Dict:
        """
        Get current page data including screenshot, DOM, and metadata.
        
        Returns:
            Dict: Page data including screenshot, DOM text, and metadata
        """
        if not self.is_initialized or not self.page:
            logger.error("Browser not initialized")
            return {"error": "Browser not initialized"}
        
        try:
            # Take screenshot
            screenshot_bytes = await self.page.screenshot(type="png", full_page=True)
            
            # Get DOM content
            dom_text = await self.page.content()
            
            # Get page metadata
            title = await self.page.title()
            url = self.page.url
            
            # Extract important elements for accessibility tree
            accessibility_tree = await self.page.accessibility.snapshot()
            
            return {
                "screenshot": screenshot_bytes,
                "dom_text": dom_text,
                "title": title,
                "url": url,
                "accessibility_tree": accessibility_tree,
                "timestamp": time.time()
            }
        
        except Exception as e:
            logger.error(f"Error getting page data: {str(e)}")
            return {"error": str(e)}
    
    async def find_element(self, selector: str, timeout: int = 10000) -> Optional[ElementHandle]:
        """
        Find an element using multiple strategies with self-healing capabilities.
        
        Args:
            selector: Initial selector to try (CSS, XPath, text, etc.)
            timeout: Maximum time to wait in milliseconds
            
        Returns:
            Optional[ElementHandle]: Element handle if found, None otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return None
        
        try:
            # Try the direct selector first
            try:
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element:
                    return element
            except Exception:
                pass  # Continue to self-healing strategies
            
            # Self-healing strategy 1: Try relaxed CSS selectors
            if selector.startswith("#") or selector.startswith("."):
                parts = selector.split(" ")
                if len(parts) > 1:
                    # Try with just the last part
                    try:
                        relaxed_selector = parts[-1]
                        elements = await self.page.query_selector_all(relaxed_selector)
                        if elements and len(elements) == 1:
                            return elements[0]
                    except Exception:
                        pass
            
            # Self-healing strategy 2: Try text-based search
            if not selector.startswith("text=") and not selector.startswith("xpath="):
                try:
                    text_selector = f"text=\"{selector}\""
                    element = await self.page.wait_for_selector(text_selector, timeout=5000)
                    if element:
                        return element
                except Exception:
                    pass
            
            # Self-healing strategy 3: Try AI-based element detection
            # (This would integrate with the perception layer in a real implementation)
            
            logger.warning(f"Could not find element with selector: {selector}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding element: {str(e)}")
            return None
    
    async def is_page_loaded(self) -> bool:
        """
        Check if a page is currently loaded.
        
        Returns:
            bool: True if a page is loaded, False otherwise
        """
        return self.is_initialized and self.page is not None
    
    async def click(self, selector: str, timeout: int = 10000) -> bool:
        """
        Click on an element with self-healing retry mechanisms.
        
        Args:
            selector: Selector to identify the element
            timeout: Maximum time to wait in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return False
        
        try:
            element = await self.find_element(selector, timeout)
            if not element:
                return False
            
            # Ensure element is visible and enabled
            is_visible = await element.is_visible()
            if not is_visible:
                logger.warning(f"Element {selector} is not visible")
                return False
            
            # Scroll element into view
            await element.scroll_into_view_if_needed()
            
            # Add human-like delay
            await asyncio.sleep(0.3)
            
            # Click with human-like behavior
            await element.click(delay=50, force=False)
            
            # Wait for potential page changes
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            
            logger.info(f"Successfully clicked on {selector}")
            return True
            
        except Exception as e:
            logger.error(f"Error clicking on {selector}: {str(e)}")
            return False
    
    async def type_text(self, selector: str, text: str, delay: int = 10) -> bool:
        """
        Type text into an input field with human-like behavior.
        
        Args:
            selector: Selector to identify the input element
            text: Text to type
            delay: Delay between keystrokes in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return False
        
        try:
            element = await self.find_element(selector)
            if not element:
                return False
            
            # Clear existing text
            await element.click(click_count=3)  # Triple click to select all text
            await element.press("Backspace")
            
            # Type with human-like delay
            await element.type(text, delay=delay)
            
            logger.info(f"Successfully typed text into {selector}")
            return True
            
        except Exception as e:
            logger.error(f"Error typing text into {selector}: {str(e)}")
            return False
    
    async def select_option(self, selector: str, value: str) -> bool:
        """
        Select an option from a dropdown.
        
        Args:
            selector: Selector to identify the select element
            value: Value to select
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return False
        
        try:
            result = await self.page.select_option(selector, value=value)
            if result:
                logger.info(f"Successfully selected option {value} in {selector}")
                return True
            else:
                logger.warning(f"Failed to select option {value} in {selector}")
                return False
                
        except Exception as e:
            logger.error(f"Error selecting option: {str(e)}")
            return False
    
    async def eval_javascript(self, script: str) -> Any:
        """
        Evaluate JavaScript in the page context.
        
        Args:
            script: JavaScript code to evaluate
            
        Returns:
            Any: Result of the evaluation
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return None
        
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            logger.error(f"Error evaluating JavaScript: {str(e)}")
            return None
    
    async def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """
        Wait for navigation to complete.
        
        Args:
            timeout: Maximum time to wait in milliseconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return False
        
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Error waiting for navigation: {str(e)}")
            return False
    
    async def open_new_page(self, url: str = None) -> Optional[str]:
        """
        Open a new browser page.
        
        Args:
            url: Optional URL to navigate to
            
        Returns:
            Optional[str]: Page ID if successful, None otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return None
        
        try:
            new_page = await self.context.new_page()
            page_id = f"page_{len(self.active_pages) + 1}"
            self.active_pages[page_id] = new_page
            
            if url:
                await new_page.goto(url, wait_until="networkidle")
            
            logger.info(f"Successfully opened new page with ID {page_id}")
            return page_id
            
        except Exception as e:
            logger.error(f"Error opening new page: {str(e)}")
            return None
    
    async def switch_to_page(self, page_id: str) -> bool:
        """
        Switch to a specific page.
        
        Args:
            page_id: ID of the page to switch to
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.error("Browser not initialized")
            return False
        
        try:
            if page_id in self.active_pages:
                self.page = self.active_pages[page_id]
                logger.info(f"Successfully switched to page {page_id}")
                return True
            else:
                logger.warning(f"Page {page_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error switching to page: {str(e)}")
            return False
    
    async def _handle_dialog(self, dialog):
        """Handle browser dialogs automatically."""
        try:
            logger.info(f"Handling dialog: {dialog.message}")
            await dialog.accept()
        except Exception as e:
            logger.error(f"Error handling dialog: {str(e)}")
    
    async def _handle_console_message(self, message):
        """Log browser console messages."""
        if message.type == "error":
            logger.warning(f"Browser console error: {message.text}")
    
    async def shutdown(self):
        """Clean up browser resources."""
        try:
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            self.is_initialized = False
            logger.info("Browser resources cleaned up")
            
        except Exception as e:
            logger.error(f"Error shutting down browser: {str(e)}")
