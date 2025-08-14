#!/usr/bin/env python
"""Simple MCP server test."""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create server
server = Server("test-server", "1.0.0")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List tools."""
    return [
        Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Call tool."""
    return [TextContent(type="text", text=f"Called {name} with {arguments}")]

async def main():
    """Run server."""
    async with stdio_server() as (read_stream, write_stream):
        print("Server starting...")
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())