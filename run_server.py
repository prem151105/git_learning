#!/usr/bin/env python3
"""
Script to start the Enhanced AI Agentic Browser Agent server.
"""

import argparse
import asyncio
import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Start the Enhanced AI Agentic Browser Agent server")
    
    parser.add_argument(
        "--host", 
        default=os.environ.get("HOST", "0.0.0.0"),
        help="Host to bind the server to"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=int(os.environ.get("PORT", "8000")),
        help="Port to bind the server to"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true", 
        default=os.environ.get("RELOAD", "false").lower() == "true",
        help="Enable auto-reload on code changes (development mode)"
    )
    
    parser.add_argument(
        "--workers", 
        type=int, 
        default=int(os.environ.get("WORKERS", "1")),
        help="Number of worker processes"
    )
    
    parser.add_argument(
        "--log-level", 
        default=os.environ.get("LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level"
    )
    
    parser.add_argument(
        "--headless", 
        action="store_true",
        default=os.environ.get("HEADLESS_MODE", "false").lower() == "true",
        help="Run browser in headless mode"
    )
    
    return parser.parse_args()

def main():
    """Main entry point for running the server."""
    args = parse_args()
    
    # Set environment variables based on arguments
    os.environ["HEADLESS_MODE"] = str(args.headless).lower()
    
    # Run the server
    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=args.log_level
    )

if __name__ == "__main__":
    main()
