"""
Multimodal Processor module for the Perception & Understanding Layer.

This module handles the analysis and understanding of web page content
using multimodal large foundation models (LFMs).
"""

import base64
import logging
import os
from typing import Dict, Any, Optional, List

import httpx
import cv2
import numpy as np
import pytesseract
from PIL import Image
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultimodalProcessor:
    """
    Processes and analyzes web page content using multimodal LFMs.
    
    This class integrates various foundation models to understand
    text, images, and their relationships on web pages.
    """
    
    def __init__(self):
        """Initialize the MultimodalProcessor."""
        self.vision_model = os.environ.get("VISION_MODEL", "gpt-4-vision-preview")
        self.text_model = os.environ.get("TEXT_MODEL", "gpt-4-turbo")
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_client = None
        
        # OCR settings
        self.ocr_config = '--oem 3 --psm 11'
        
        logger.info("MultimodalProcessor instance created")
    
    async def initialize(self):
        """Initialize clients and resources."""
        # Import API clients here to avoid circular imports
        try:
            import openai
            import anthropic
            import google.generativeai as genai
            
            # Initialize OpenAI client
            self.openai_client = openai.AsyncClient(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            
            # Initialize Anthropic client
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            
            # Initialize Google Gemini client
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            self.gemini_client = genai
            
            logger.info("All LFM clients initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing LFM clients: {str(e)}")
            return False
    
    async def analyze_page(self, screenshot_bytes, dom_text, task_goal):
        """
        Analyze a web page using both visual and textual content.
        
        Args:
            screenshot_bytes: PNG image bytes of the screenshot
            dom_text: Text representation of the DOM
            task_goal: Description of the current task goal
            
        Returns:
            Dict: Analysis results including identified elements and actions
        """
        try:
            # Parallel processing of both visual and text analysis
            import asyncio
            vision_task = self.analyze_image(screenshot_bytes, task_goal)
            text_task = self.analyze_text(dom_text, task_goal)
            
            # Wait for both analyses to complete
            vision_analysis, text_analysis = await asyncio.gather(vision_task, text_task)
            
            # Synthesize the results
            understanding = await self.synthesize_understanding(vision_analysis, text_analysis, task_goal)
            
            return understanding
        
        except Exception as e:
            logger.error(f"Error analyzing page: {str(e)}")
            return {"error": str(e)}
    
    async def analyze_image(self, image_bytes, task_goal):
        """
        Analyze an image using a multimodal vision model.
        
        Args:
            image_bytes: PNG image bytes
            task_goal: Description of the current task goal
            
        Returns:
            Dict: Vision model analysis results
        """
        try:
            # Perform OCR on the image
            ocr_results = await self._extract_text_from_image(image_bytes)
            
            # Encode image to base64 for API
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Determine which LFM client to use
            if self.openai_client and "gpt" in self.vision_model:
                response = await self._analyze_with_openai_vision(base64_image, task_goal, ocr_results)
            elif self.anthropic_client and "claude" in self.vision_model:
                response = await self._analyze_with_anthropic_vision(base64_image, task_goal, ocr_results)
            elif self.gemini_client and "gemini" in self.vision_model:
                response = await self._analyze_with_gemini_vision(base64_image, task_goal, ocr_results)
            else:
                raise ValueError(f"Unsupported vision model: {self.vision_model}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error in image analysis: {str(e)}")
            return {"error": str(e)}
    
    async def _extract_text_from_image(self, image_bytes):
        """
        Extract text from an image using OCR.
        
        Args:
            image_bytes: PNG image bytes
            
        Returns:
            str: Extracted text
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Preprocess the image for better OCR results
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
            # Perform OCR
            text = pytesseract.image_to_string(thresh, config=self.ocr_config)
            
            return text
        except Exception as e:
            logger.error(f"OCR error: {str(e)}")
            return ""
    
    async def _analyze_with_openai_vision(self, base64_image, task_goal, ocr_text):
        """Use OpenAI's vision model for analysis."""
        prompt = f"""
        Analyze this web page screenshot in the context of the following task:
        Task: {task_goal}
        
        OCR extracted text: {ocr_text}
        
        Identify:
        1. Main UI elements visible (buttons, forms, links, etc.)
        2. Their positions and descriptions
        3. Any obstacles to completing the task
        4. Recommended actions to progress the task
        
        Return the analysis as a structured JSON object.
        """
        
        response = await self.openai_client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {"role": "system", "content": "You are a web UI analyzer that identifies elements and actions."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content
    
    async def _analyze_with_anthropic_vision(self, base64_image, task_goal, ocr_text):
        """Use Anthropic's Claude model for analysis."""
        prompt = f"""
        Analyze this web page screenshot in the context of the following task:
        Task: {task_goal}
        
        OCR extracted text: {ocr_text}
        
        Identify:
        1. Main UI elements visible (buttons, forms, links, etc.)
        2. Their positions and descriptions
        3. Any obstacles to completing the task
        4. Recommended actions to progress the task
        
        Return the analysis as a structured JSON object.
        """
        
        response = await self.anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                ]}
            ]
        )
        
        return response.content[0].text
    
    async def _analyze_with_gemini_vision(self, base64_image, task_goal, ocr_text):
        """Use Google's Gemini Vision model for analysis."""
        prompt = f"""
        Analyze this web page screenshot in the context of the following task:
        Task: {task_goal}
        
        OCR extracted text: {ocr_text}
        
        Identify:
        1. Main UI elements visible (buttons, forms, links, etc.)
        2. Their positions and descriptions
        3. Any obstacles to completing the task
        4. Recommended actions to progress the task
        
        Return the analysis as a structured JSON object.
        """
        
        # Convert base64 to image for Gemini
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(BytesIO(image_bytes))
        
        # Generate content with Gemini
        generation_config = self.gemini_client.types.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
        
        model = self.gemini_client.GenerativeModel('gemini-pro-vision')
        response = model.generate_content(
            [
                prompt,
                image,
            ],
            generation_config=generation_config
        )
        
        return response.text
    
    async def analyze_text(self, dom_text, task_goal):
        """
        Analyze text content of a DOM using LFMs.
        
        Args:
            dom_text: Text representation of the DOM
            task_goal: Description of the current task goal
            
        Returns:
            Dict: Analysis results including identified elements and structures
        """
        try:
            prompt = f"""
            Analyze this web page DOM text in the context of the following task:
            Task: {task_goal}
            
            DOM Text:
            {dom_text[:10000]}  # Limit size to avoid token limits
            
            Identify:
            1. Main interactive elements (buttons, forms, links, etc.)
            2. Their IDs, classes, and XPaths where available
            3. Page structure and hierarchy
            4. Any obstacles to completing the task
            5. Recommended actions to progress the task
            
            Return the analysis as a structured JSON object.
            """
            
            if self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.text_model,
                    messages=[
                        {"role": "system", "content": "You are a web DOM analyzer that identifies elements and structures."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content
            
            elif self.anthropic_client:
                response = await self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text
            
            else:
                raise ValueError("No suitable text model client available")
        
        except Exception as e:
            logger.error(f"Error in text analysis: {str(e)}")
            return {"error": str(e)}
    
    async def synthesize_understanding(self, vision_analysis, text_analysis, task_goal):
        """
        Synthesize the results from visual and textual analysis.
        
        Args:
            vision_analysis: Results from image analysis
            text_analysis: Results from DOM text analysis
            task_goal: Description of the current task goal
            
        Returns:
            Dict: Combined understanding with action recommendations
        """
        try:
            prompt = f"""
            Synthesize the following analyses of a web page in the context of this task:
            Task: {task_goal}
            
            Vision Analysis: {vision_analysis}
            
            DOM Text Analysis: {text_analysis}
            
            Create a comprehensive understanding of the page that includes:
            1. All identified UI elements with their properties
            2. The most accurate selectors to target each element
            3. The page structure and navigation flow
            4. Specific actionable steps to progress the task
            5. Any potential challenges and alternative approaches
            
            Return the synthesis as a structured JSON object optimized for a web automation agent.
            """
            
            if self.openai_client:
                response = await self.openai_client.chat.completions.create(
                    model=self.text_model,
                    messages=[
                        {"role": "system", "content": "You are a web automation expert that synthesizes analyses into actionable plans."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                return response.choices[0].message.content
            
            elif self.anthropic_client:
                response = await self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text
            
            else:
                raise ValueError("No suitable text model client available")
        
        except Exception as e:
            logger.error(f"Error in synthesizing understanding: {str(e)}")
            return {"error": str(e)}
