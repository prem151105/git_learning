#!/usr/bin/env python3
"""
Main entry point for the Enhanced AI Agentic Browser Agent Architecture.
This module initializes the FastAPI application and all core components.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.orchestrator import AgentOrchestrator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="Enhanced AI Agentic Browser Agent",
    description="A robust, scalable, and intelligent system for automating complex web tasks.",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Agent Orchestrator
orchestrator = None

@app.on_event("startup")
async def startup_event():
    """Initialize components on application startup."""
    global orchestrator
    orchestrator = await AgentOrchestrator.initialize()
    logger.info("Agent Orchestrator initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    if orchestrator:
        await orchestrator.shutdown()
        logger.info("Agent Orchestrator shut down successfully")

# Model definitions
class TaskRequest(BaseModel):
    """Model for task execution requests."""
    task_description: str
    urls: Optional[List[str]] = None
    human_assisted: bool = False
    max_retries: int = 3
    timeout: int = 300  # seconds

class TaskResponse(BaseModel):
    """Model for task execution responses."""
    task_id: str
    status: str
    message: str

class TaskResult(BaseModel):
    """Model for task execution results."""
    task_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None
    
# API routes
@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "online", "service": "Enhanced AI Agentic Browser Agent"}

@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskRequest, background_tasks: BackgroundTasks):
    """
    Create and start a new task.
    
    Args:
        task: TaskRequest object containing task details
        background_tasks: FastAPI background tasks object
    
    Returns:
        TaskResponse: Task creation response with task ID
    """
    task_id = await orchestrator.create_task(task.dict())
    background_tasks.add_task(orchestrator.execute_task, task_id)
    return {"task_id": task_id, "status": "started", "message": "Task created and started"}

@app.get("/tasks/{task_id}", response_model=TaskResult)
async def get_task(task_id: str):
    """
    Get the status and result of a task.
    
    Args:
        task_id: The ID of the task to retrieve
        
    Returns:
        TaskResult: Task result object with status and data
    """
    result = await orchestrator.get_task_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a running task.
    
    Args:
        task_id: The ID of the task to cancel
    
    Returns:
        Dict: Cancellation status
    """
    success = await orchestrator.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    return {"status": "cancelled", "message": "Task cancelled successfully"}

@app.websocket("/ws/tasks/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task updates.
    
    Args:
        websocket: WebSocket connection
        task_id: Task ID to subscribe to
    """
    await websocket.accept()
    try:
        await orchestrator.register_websocket(task_id, websocket)
        while True:
            # Keep the connection open and handle incoming messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await orchestrator.unregister_websocket(task_id, websocket)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
