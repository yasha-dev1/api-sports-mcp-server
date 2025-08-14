#!/usr/bin/env python
"""Test server initialization directly."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_server_api_sports.server import ApiSportsMCPServer


async def test_init():
    """Test server initialization."""
    try:
        server = ApiSportsMCPServer()
        print(f"Server initialized: {server.settings.mcp_server_name}")
        print(f"Version: {server.settings.mcp_server_version}")
        
        # Check if handlers are registered
        print(f"Server object: {server.server}")
        print(f"Server name: {server.server.name}")
        print(f"Server version: {server.server.version}")
        
        # Test list_tools handler
        handlers = server.server._tool_handlers
        print(f"Tool handlers registered: {len(handlers) if handlers else 0}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_init())