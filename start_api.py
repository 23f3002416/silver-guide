#!/usr/bin/env python3
"""
Startup script for the Data Analyst AI Agent API

This script starts the FastAPI server with appropriate configuration.
"""

import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Start the FastAPI application"""
    
    # Check for required environment variables
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please create a .env file with your Anthropic API key:")
        print("ANTHROPIC_API_KEY=your_api_key_here")
        exit(1)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    print("🚀 Starting Data Analyst AI Agent API")
    print("=" * 50)
    print(f"🌐 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🔄 Reload: {reload}")
    print(f"📡 URL: http://{host}:{port}")
    print(f"📋 API Endpoint: http://{host}:{port}/api/")
    print(f"🩺 Health Check: http://{host}:{port}/health")
    print("=" * 50)
    print("💡 Usage:")
    print(f'   curl "http://{host}:{port}/api/" -F "file=@question.txt"')
    print("=" * 50)
    
    # Start the server
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main() 