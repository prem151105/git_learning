"""
Metrics Collector module for the Monitoring & Analytics components.

This module implements metrics collection, aggregation, and reporting
to track the agent's performance and operation.
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import uuid

from prometheus_client import Counter, Histogram, Gauge, Summary, push_to_gateway

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects, aggregates, and reports metrics on agent performance.
    
    This class enables monitoring of task execution, action performance,
    resource usage, and other operational metrics.
    """
    
    def __init__(self):
        """Initialize the MetricsCollector."""
        # Configuration
        self.metrics_enabled = True
        self.prometheus_enabled = os.environ.get("PROMETHEUS_ENABLED", "true").lower() == "true"
        self.prometheus_push_gateway = os.environ.get("PROMETHEUS_PUSH_GATEWAY", "localhost:9091")
        self.prometheus_job_name = os.environ.get("PROMETHEUS_JOB_NAME", "agentic_browser")
        self.agent_id = str(uuid.uuid4())[:8]  # Short ID for labeling
        
        # Prometheus metrics
        self.task_counter = None
        self.action_histogram = None
        self.error_counter = None
        self.memory_gauge = None
        self.performance_summary = None
        
        # Internal metrics storage
        self.metrics_data = {
            "tasks": {
                "total": 0,
                "successful": 0,
                "failed": 0
            },
            "actions": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "types": {}
            },
            "performance": {
                "avg_task_time": 0,
                "avg_action_time": 0
            },
            "errors": {
                "total": 0,
                "types": {}
            },
            "resources": {
                "memory_usage": 0,
                "cpu_usage": 0
            }
        }
        
        # Time-series data
        self.time_series = {
            "tasks": [],
            "actions": [],
            "errors": []
        }
        
        # Session tracking
        self.session_start_time = time.time()
        
        logger.info("MetricsCollector instance created")
    
    async def initialize(self):
        """Initialize resources."""
        if self.prometheus_enabled:
            try:
                # Initialize Prometheus metrics
                self.task_counter = Counter(
                    'agentic_browser_tasks_total',
                    'Total number of tasks processed',
                    ['status', 'agent_id']
                )
                
                self.action_histogram = Histogram(
                    'agentic_browser_action_duration_seconds',
                    'Action execution time in seconds',
                    ['action_type', 'agent_id'],
                    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
                )
                
                self.error_counter = Counter(
                    'agentic_browser_errors_total',
                    'Total number of errors',
                    ['error_type', 'agent_id']
                )
                
                self.memory_gauge = Gauge(
                    'agentic_browser_memory_usage_bytes',
                    'Memory usage in bytes',
                    ['agent_id']
                )
                
                self.performance_summary = Summary(
                    'agentic_browser_task_performance_seconds',
                    'Task performance summary in seconds',
                    ['agent_id']
                )
                
                logger.info("Prometheus metrics initialized")
            except Exception as e:
                logger.error(f"Error initializing Prometheus metrics: {str(e)}")
                self.prometheus_enabled = False
                
        logger.info("MetricsCollector initialized successfully")
        return True
    
    def record_task_created(self):
        """Record a task creation event."""
        if not self.metrics_enabled:
            return
            
        self.metrics_data["tasks"]["total"] += 1
        
        if self.prometheus_enabled:
            self.task_counter.labels(status="created", agent_id=self.agent_id).inc()
    
    def record_task_completed(self, duration: float):
        """
        Record a task completion event.
        
        Args:
            duration: Task duration in seconds
        """
        if not self.metrics_enabled:
            return
            
        self.metrics_data["tasks"]["successful"] += 1
        
        # Update average task time
        total_successful = self.metrics_data["tasks"]["successful"]
        current_avg = self.metrics_data["performance"]["avg_task_time"]
        new_avg = ((current_avg * (total_successful - 1)) + duration) / total_successful
        self.metrics_data["performance"]["avg_task_time"] = new_avg
        
        # Add to time series
        self.time_series["tasks"].append({
            "timestamp": time.time(),
            "status": "completed",
            "duration": duration
        })
        
        if self.prometheus_enabled:
            self.task_counter.labels(status="completed", agent_id=self.agent_id).inc()
            self.performance_summary.labels(agent_id=self.agent_id).observe(duration)
    
    def record_task_failed(self):
        """Record a task failure event."""
        if not self.metrics_enabled:
            return
            
        self.metrics_data["tasks"]["failed"] += 1
        
        # Add to time series
        self.time_series["tasks"].append({
            "timestamp": time.time(),
            "status": "failed"
        })
        
        if self.prometheus_enabled:
            self.task_counter.labels(status="failed", agent_id=self.agent_id).inc()
    
    def record_action_executed(self, action_type: str, duration: float, success: bool):
        """
        Record an action execution event.
        
        Args:
            action_type: Type of action executed
            duration: Action duration in seconds
            success: Whether the action was successful
        """
        if not self.metrics_enabled:
            return
            
        self.metrics_data["actions"]["total"] += 1
        
        if success:
            self.metrics_data["actions"]["successful"] += 1
        else:
            self.metrics_data["actions"]["failed"] += 1
        
        # Track by action type
        if action_type not in self.metrics_data["actions"]["types"]:
            self.metrics_data["actions"]["types"][action_type] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_duration": 0
            }
        
        action_stats = self.metrics_data["actions"]["types"][action_type]
        action_stats["total"] += 1
        
        if success:
            action_stats["successful"] += 1
            # Update average duration
            current_avg = action_stats["avg_duration"]
            new_avg = ((current_avg * (action_stats["successful"] - 1)) + duration) / action_stats["successful"]
            action_stats["avg_duration"] = new_avg
        else:
            action_stats["failed"] += 1
        
        # Add to time series
        self.time_series["actions"].append({
            "timestamp": time.time(),
            "type": action_type,
            "duration": duration,
            "success": success
        })
        
        # Update overall average action time
        total_successful_actions = self.metrics_data["actions"]["successful"]
        if total_successful_actions > 0:
            current_avg = self.metrics_data["performance"]["avg_action_time"]
            new_avg = ((current_avg * (total_successful_actions - 1)) + duration) / total_successful_actions
            self.metrics_data["performance"]["avg_action_time"] = new_avg
        
        if self.prometheus_enabled:
            self.action_histogram.labels(action_type=action_type, agent_id=self.agent_id).observe(duration)
    
    def record_error(self, error_type: str, error_details: str):
        """
        Record an error event.
        
        Args:
            error_type: Type of error
            error_details: Error details
        """
        if not self.metrics_enabled:
            return
            
        self.metrics_data["errors"]["total"] += 1
        
        # Track by error type
        if error_type not in self.metrics_data["errors"]["types"]:
            self.metrics_data["errors"]["types"][error_type] = 0
            
        self.metrics_data["errors"]["types"][error_type] += 1
        
        # Add to time series
        self.time_series["errors"].append({
            "timestamp": time.time(),
            "type": error_type,
            "details": error_details
        })
        
        if self.prometheus_enabled:
            self.error_counter.labels(error_type=error_type, agent_id=self.agent_id).inc()
    
    def record_resource_usage(self, memory_bytes: int, cpu_percent: float):
        """
        Record resource usage.
        
        Args:
            memory_bytes: Memory usage in bytes
            cpu_percent: CPU usage as percentage
        """
        if not self.metrics_enabled:
            return
            
        self.metrics_data["resources"]["memory_usage"] = memory_bytes
        self.metrics_data["resources"]["cpu_usage"] = cpu_percent
        
        if self.prometheus_enabled:
            self.memory_gauge.labels(agent_id=self.agent_id).set(memory_bytes)
    
    async def push_metrics_to_prometheus(self):
        """Push current metrics to Prometheus Push Gateway."""
        if not self.prometheus_enabled:
            return
            
        try:
            from prometheus_client import push_to_gateway
            
            # Add instance label
            registry = self.task_counter._registry
            grouping_keys = {'instance': f'agent_{self.agent_id}', 'job': self.prometheus_job_name}
            
            push_to_gateway(self.prometheus_push_gateway, job=self.prometheus_job_name, registry=registry, grouping_key=grouping_keys)
            logger.info(f"Metrics pushed to Prometheus Push Gateway: {self.prometheus_push_gateway}")
            
        except Exception as e:
            logger.error(f"Error pushing metrics to Prometheus: {str(e)}")
    
    def get_metrics_summary(self) -> Dict:
        """
        Get a summary of current metrics.
        
        Returns:
            Dict: Metrics summary
        """
        # Calculate success rates
        task_success_rate = 0
        if self.metrics_data["tasks"]["total"] > 0:
            task_success_rate = self.metrics_data["tasks"]["successful"] / self.metrics_data["tasks"]["total"]
            
        action_success_rate = 0
        if self.metrics_data["actions"]["total"] > 0:
            action_success_rate = self.metrics_data["actions"]["successful"] / self.metrics_data["actions"]["total"]
        
        # Calculate session duration
        session_duration = time.time() - self.session_start_time
        
        # Prepare summary
        return {
            "summary": {
                "task_success_rate": task_success_rate,
                "action_success_rate": action_success_rate,
                "avg_task_time": self.metrics_data["performance"]["avg_task_time"],
                "avg_action_time": self.metrics_data["performance"]["avg_action_time"],
                "error_rate": self.metrics_data["errors"]["total"] / max(1, self.metrics_data["tasks"]["total"]),
                "session_duration": session_duration
            },
            "tasks": {
                "total": self.metrics_data["tasks"]["total"],
                "successful": self.metrics_data["tasks"]["successful"],
                "failed": self.metrics_data["tasks"]["failed"]
            },
            "actions": {
                "total": self.metrics_data["actions"]["total"],
                "successful": self.metrics_data["actions"]["successful"],
                "failed": self.metrics_data["actions"]["failed"],
                "by_type": {
                    action_type: {
                        "success_rate": stats["successful"] / max(1, stats["total"]),
                        "avg_duration": stats["avg_duration"],
                        "count": stats["total"]
                    }
                    for action_type, stats in self.metrics_data["actions"]["types"].items()
                }
            },
            "errors": {
                "total": self.metrics_data["errors"]["total"],
                "by_type": self.metrics_data["errors"]["types"]
            },
            "resources": self.metrics_data["resources"]
        }
    
    def get_time_series(self, metric_type: str, time_range: int = 3600) -> List[Dict]:
        """
        Get time series data for a specific metric.
        
        Args:
            metric_type: Type of metric to retrieve (tasks, actions, errors)
            time_range: Time range in seconds (default 1 hour)
            
        Returns:
            List[Dict]: Time series data points
        """
        if metric_type not in self.time_series:
            return []
            
        # Filter by time range
        start_time = time.time() - time_range
        return [point for point in self.time_series[metric_type] if point["timestamp"] >= start_time]
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics_data = {
            "tasks": {
                "total": 0,
                "successful": 0,
                "failed": 0
            },
            "actions": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "types": {}
            },
            "performance": {
                "avg_task_time": 0,
                "avg_action_time": 0
            },
            "errors": {
                "total": 0,
                "types": {}
            },
            "resources": {
                "memory_usage": 0,
                "cpu_usage": 0
            }
        }
        
        self.time_series = {
            "tasks": [],
            "actions": [],
            "errors": []
        }
        
        self.session_start_time = time.time()
        logger.info("Metrics reset")
    
    async def start_periodic_reporting(self, interval: int = 300):
        """
        Start periodic reporting of metrics.
        
        Args:
            interval: Reporting interval in seconds (default 5 minutes)
        """
        while True:
            try:
                # Get metrics summary
                summary = self.get_metrics_summary()
                
                # Log summary
                logger.info(f"Metrics summary: Task success rate: {summary['summary']['task_success_rate']:.2f}, " +
                           f"Action success rate: {summary['summary']['action_success_rate']:.2f}, " +
                           f"Errors: {summary['errors']['total']}")
                
                # Push to Prometheus if enabled
                if self.prometheus_enabled:
                    await self.push_metrics_to_prometheus()
                
            except Exception as e:
                logger.error(f"Error in periodic metrics reporting: {str(e)}")
                
            # Wait for next interval
            await asyncio.sleep(interval)
    
    def enable_metrics(self, enabled: bool = True):
        """
        Enable or disable metrics collection.
        
        Args:
            enabled: Whether metrics should be enabled
        """
        self.metrics_enabled = enabled
        logger.info(f"Metrics collection {'enabled' if enabled else 'disabled'}")
    
    async def shutdown(self):
        """Clean up resources."""
        # Push final metrics if enabled
        if self.prometheus_enabled:
            try:
                await self.push_metrics_to_prometheus()
            except Exception as e:
                logger.error(f"Error pushing final metrics: {str(e)}")
        
        logger.info("MetricsCollector resources cleaned up")
