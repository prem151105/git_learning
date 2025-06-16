"""
Ethical Guardian module for the Security & Ethics components.

This module ensures that the agent operates according to ethical guidelines
and compliance with privacy regulations.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Dict, List, Any, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EthicalGuardian:
    """
    Ensures the agent operates according to ethical guidelines.
    
    This class validates tasks, enforces privacy protections, and ensures
    compliance with regulations like GDPR, CCPA, etc.
    """
    
    def __init__(self):
        """Initialize the EthicalGuardian."""
        self.llm_client = None
        self.ethics_model = os.environ.get("ETHICS_MODEL", "gpt-4-turbo")
        
        # Rules and policies
        self.ethical_guidelines = []
        self.privacy_policies = []
        self.blocked_domains = []
        self.data_retention_policies = {}
        self.risk_thresholds = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.8
        }
        
        # Load default guidelines
        self._load_default_guidelines()
        
        logger.info("EthicalGuardian instance created")
    
    async def initialize(self):
        """Initialize resources."""
        try:
            import openai
            self.llm_client = openai.AsyncClient(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            
            # Load custom guidelines from environment if available
            custom_guidelines_path = os.environ.get("ETHICAL_GUIDELINES_PATH")
            if custom_guidelines_path and os.path.exists(custom_guidelines_path):
                with open(custom_guidelines_path, 'r') as f:
                    custom_guidelines = json.load(f)
                    self.ethical_guidelines.extend(custom_guidelines.get("ethical_guidelines", []))
                    self.privacy_policies.extend(custom_guidelines.get("privacy_policies", []))
                    self.blocked_domains.extend(custom_guidelines.get("blocked_domains", []))
                    
            logger.info("EthicalGuardian initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing ethical guardian: {str(e)}")
            return False
    
    async def validate_task(self, task_description: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a task is ethically permissible.
        
        Args:
            task_description: Description of the task to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, reason if invalid)
        """
        # Basic rule-based checks
        basic_check = self._check_against_rules(task_description)
        if not basic_check[0]:
            logger.warning(f"Task rejected by rule-based check: {basic_check[1]}")
            return basic_check
        
        # Domain check for blocked sites
        domain_check = self._check_blocked_domains(task_description)
        if not domain_check[0]:
            logger.warning(f"Task rejected due to blocked domain: {domain_check[1]}")
            return domain_check
        
        # LLM-based ethical analysis for complex cases
        if self.llm_client:
            analysis = await self._analyze_task_ethics(task_description)
            if not analysis["is_ethical"]:
                logger.warning(f"Task rejected by ethical analysis: {analysis['reasoning']}")
                return False, analysis["reasoning"]
        
        return True, None
    
    def _check_against_rules(self, task_description: str) -> Tuple[bool, Optional[str]]:
        """
        Check a task against predefined ethical rules.
        
        Args:
            task_description: Description of the task to check
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, reason if invalid)
        """
        task_lower = task_description.lower()
        
        # Check against ethical guidelines
        for guideline in self.ethical_guidelines:
            rule = guideline["rule"].lower()
            if rule in task_lower or any(term in task_lower for term in guideline.get("terms", [])):
                return False, guideline["message"]
        
        # Check against privacy policies
        for policy in self.privacy_policies:
            rule = policy["rule"].lower()
            if rule in task_lower or any(term in task_lower for term in policy.get("terms", [])):
                return False, policy["message"]
        
        return True, None
    
    def _check_blocked_domains(self, task_description: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a task involves blocked domains.
        
        Args:
            task_description: Description of the task to check
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, reason if invalid)
        """
        # Extract potential URLs from task
        url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
        urls = url_pattern.findall(task_description)
        
        # Extract domains
        domains = [url.split('//')[1].split('/')[0] for url in urls]
        
        # Check against blocked domains
        for domain in domains:
            for blocked in self.blocked_domains:
                if blocked in domain:
                    return False, f"Domain '{domain}' is blocked by policy"
        
        return True, None
    
    async def _analyze_task_ethics(self, task_description: str) -> Dict:
        """
        Perform a detailed ethical analysis of a task using LLMs.
        
        Args:
            task_description: Description of the task to analyze
            
        Returns:
            Dict: Analysis results
        """
        try:
            # Format guidelines for prompt
            guidelines_text = "\n".join([f"- {g['rule']}" for g in self.ethical_guidelines])
            privacy_text = "\n".join([f"- {p['rule']}" for p in self.privacy_policies])
            
            prompt = f"""
            You are an ethical evaluation system for an AI agent. Assess if this task is ethically permissible:
            
            Task: {task_description}
            
            Ethical guidelines:
            {guidelines_text}
            
            Privacy policies:
            {privacy_text}
            
            Perform the following analysis:
            1. Identify any ethical concerns with the task
            2. Check for privacy implications
            3. Assess potential for harm or misuse
            4. Evaluate legal compliance
            5. Consider data protection requirements
            
            Return your analysis as a JSON object with these fields:
            - is_ethical: boolean indicating if task is ethically permissible
            - risk_level: string ("low", "medium", "high")
            - concerns: array of specific concerns
            - reasoning: detailed explanation of your assessment
            """
            
            response = await self.llm_client.chat.completions.create(
                model=self.ethics_model,
                messages=[
                    {"role": "system", "content": "You are an AI ethics evaluation system that assesses whether tasks comply with ethical guidelines and privacy policies. You are thorough, cautious, and prioritize safety and compliance."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Ensure required fields
            if "is_ethical" not in analysis:
                analysis["is_ethical"] = False
                analysis["reasoning"] = "Could not confirm ethical compliance"
                
            return analysis
            
        except Exception as e:
            logger.error(f"Error in ethical analysis: {str(e)}")
            # Default to cautious approach on error
            return {
                "is_ethical": False,
                "risk_level": "high",
                "concerns": ["Error in ethical analysis"],
                "reasoning": f"Could not complete ethical analysis due to error: {str(e)}"
            }
    
    def validate_data_collection(self, data_type: str, purpose: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if data collection is permissible.
        
        Args:
            data_type: Type of data to collect
            purpose: Purpose of data collection
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, reason if invalid)
        """
        sensitive_data_types = [
            "password", "credit_card", "social_security", "health",
            "biometric", "political", "religious", "sexual_orientation"
        ]
        
        if data_type.lower() in sensitive_data_types:
            return False, f"Collection of {data_type} data is restricted by policy"
        
        valid_purposes = ["task_execution", "debug", "performance_improvement", "error_recovery"]
        
        if purpose.lower() not in valid_purposes:
            return False, f"Purpose '{purpose}' is not an approved data collection purpose"
        
        return True, None
    
    async def validate_action(self, action: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate if an action is ethically permissible.
        
        Args:
            action: Action configuration to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, reason if invalid)
        """
        action_type = action.get("type", "").lower()
        
        # High-risk actions require special validation
        high_risk_actions = ["form_fill", "api_call", "click"]
        
        if action_type in high_risk_actions:
            # For form filling, check what data is being entered
            if action_type == "form_fill" and "fields" in action:
                for field in action["fields"]:
                    if "sensitive" in field and field["sensitive"]:
                        # Special validation for sensitive data
                        return False, "Action involves entering sensitive data"
            
            # For API calls, check the endpoint and payload
            if action_type == "api_call":
                endpoint = action.get("endpoint", "")
                if any(blocked in endpoint for blocked in self.blocked_domains):
                    return False, f"API endpoint contains blocked domain"
        
        return True, None
    
    def check_data_retention(self, data_type: str) -> int:
        """
        Get the retention period for a type of data.
        
        Args:
            data_type: Type of data to check
            
        Returns:
            int: Retention period in seconds
        """
        # Default is 30 days
        default_retention = 30 * 24 * 60 * 60
        
        return self.data_retention_policies.get(data_type, default_retention)
    
    def _load_default_guidelines(self):
        """Load default ethical guidelines and privacy policies."""
        self.ethical_guidelines = [
            {
                "rule": "Do not engage in illegal activities",
                "terms": ["illegal", "unlawful", "crime", "criminal"],
                "message": "Cannot perform illegal activities"
            },
            {
                "rule": "Do not harm individuals or groups",
                "terms": ["harm", "hurt", "damage", "attack"],
                "message": "Cannot perform actions that might harm individuals or groups"
            },
            {
                "rule": "Do not access unauthorized systems or data",
                "terms": ["hack", "breach", "unauthorized", "crack", "steal"],
                "message": "Cannot access unauthorized systems or data"
            },
            {
                "rule": "Do not create or distribute malicious content",
                "terms": ["malware", "virus", "phishing", "scam"],
                "message": "Cannot create or distribute malicious content"
            },
            {
                "rule": "Do not impersonate individuals or organizations",
                "terms": ["impersonate", "pretend", "fake"],
                "message": "Cannot impersonate individuals or organizations"
            }
        ]
        
        self.privacy_policies = [
            {
                "rule": "Do not collect data beyond what's necessary for the task",
                "terms": ["collect", "gather", "harvest"],
                "message": "Cannot collect data beyond what's necessary for the task"
            },
            {
                "rule": "Do not store sensitive personal information",
                "terms": ["password", "credit card", "ssn", "social security"],
                "message": "Cannot store sensitive personal information"
            },
            {
                "rule": "Respect user consent for data processing",
                "terms": ["consent", "permission"],
                "message": "Must respect user consent for data processing"
            },
            {
                "rule": "Comply with GDPR and other privacy regulations",
                "terms": ["gdpr", "ccpa", "privacy regulation"],
                "message": "Must comply with applicable privacy regulations"
            }
        ]
        
        self.blocked_domains = [
            "malware.com",
            "phishing.org",
            "darknet",
            "hacking.net"
        ]
        
        self.data_retention_policies = {
            "browsing_history": 30 * 24 * 60 * 60,  # 30 days in seconds
            "form_data": 7 * 24 * 60 * 60,         # 7 days in seconds
            "user_preferences": 365 * 24 * 60 * 60, # 1 year in seconds
            "error_logs": 90 * 24 * 60 * 60        # 90 days in seconds
        }
