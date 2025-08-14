#!/usr/bin/env python
"""Test script to simulate MCP client connection."""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.client import ClientSession
from mcp.client.stdio import stdio_client


async def test_connection():
    """Test MCP server connection."""
    print("Testing MCP server connection...")
    
    async with stdio_client() as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            
            print(f"Connected to: {session.server_info.name}")
            print(f"Version: {session.server_info.version}")
            
            # List available tools
            tools = await session.list_tools()
            print(f"\nAvailable tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")
            
            # Test calling a tool
            print("\nTesting teams_search tool...")
            result = await session.call_tool(
                "teams_search",
                {"name": "Manchester United"}
            )
            
            print("Result:", json.dumps(json.loads(result.content[0].text), indent=2)[:500])


if __name__ == "__main__":
    asyncio.run(test_connection())