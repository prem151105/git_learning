#!/usr/bin/env python3
"""
Setup script for the Enhanced AI Agentic Browser Agent package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agentic-browser",
    version="1.0.0",
    author="AI Automation Team",
    author_email="team@example.com",
    description="Enhanced AI Agentic Browser Agent Architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/agentic-browser",
    project_urls={
        "Bug Tracker": "https://github.com/your-org/agentic-browser/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
    ],
    packages=find_packages(exclude=["tests", "examples"]),
    python_requires=">=3.9",
    install_requires=[
        "asyncio>=3.4.3",
        "fastapi>=0.110.0",
        "uvicorn>=0.30.0",
        "pydantic>=2.6.1",
        "playwright>=1.42.0",
        "selenium>=4.16.0",
        "openai>=1.12.0",
        "anthropic>=0.8.1",
        "google-generativeai>=0.4.0",
        "transformers>=4.39.0",
        "sentence-transformers>=2.5.1",
        "spacy>=3.7.2",
        "torch>=2.2.0",
        "opencv-python>=4.8.1",
        "pytesseract>=0.3.10",
        "aiohttp>=3.9.3",
        "httpx>=0.27.0",
        "python-dotenv>=1.0.1",
        "prometheus-client>=0.19.0",
        "tenacity>=8.2.3",
    ],
    entry_points={
        "console_scripts": [
            "agentic-browser=src.main:run_server",
        ],
    },
)
