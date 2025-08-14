"""Main MCP server implementation for API-Sports."""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import get_settings
from .logger import get_logger, setup_logging
from .services import ApiSportsService, CacheService
from .tools import FixturesTool, TeamStatisticsTool, TeamsTool

logger = get_logger(__name__)


class ApiSportsMCPServer:
    """MCP Server for API-Sports integration."""

    def __init__(self):
        self.settings = get_settings()
        self.server = Server(self.settings.mcp_server_name)

        # Initialize services
        self.api_service = ApiSportsService()
        self.cache_service = CacheService()

        # Initialize tools
        self.teams_tool = TeamsTool(self.api_service, self.cache_service)
        self.fixtures_tool = FixturesTool(self.api_service, self.cache_service)
        self.statistics_tool = TeamStatisticsTool(self.api_service, self.cache_service)

        # Register handlers
        self._register_handlers()

        logger.info(
            f"Initialized {self.settings.mcp_server_name} v{self.settings.mcp_server_version}"
        )

    def _register_handlers(self):
        """Register MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            tools = [
                Tool(
                    name="teams_search",
                    description="Search for football teams and retrieve their information",
                    inputSchema=self.teams_tool.get_tool_definition()["inputSchema"],
                ),
                Tool(
                    name="fixtures_get",
                    description="Retrieve football fixtures (matches) with comprehensive filtering",
                    inputSchema=self.fixtures_tool.get_tool_definition()["inputSchema"],
                ),
                Tool(
                    name="team_statistics",
                    description="Get comprehensive statistics for a team in a specific league and season",
                    inputSchema=self.statistics_tool.get_tool_definition()["inputSchema"],
                ),
            ]

            logger.debug(f"Listed {len(tools)} tools")
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool with given arguments."""
            logger.info(
                f"Calling tool: {name}",
                extra={"tool": name, "arguments": arguments}
            )

            try:
                result = None

                if name == "teams_search":
                    result = await self.teams_tool.search_teams(**arguments)

                elif name == "fixtures_get":
                    # Map 'from' and 'to' parameters to 'from_date' and 'to_date'
                    if "from" in arguments:
                        arguments["from_date"] = arguments.pop("from")
                    if "to" in arguments:
                        arguments["to_date"] = arguments.pop("to")
                    result = await self.fixtures_tool.get_fixtures(**arguments)

                elif name == "team_statistics":
                    result = await self.statistics_tool.get_team_statistics(**arguments)

                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

                # Format result as JSON string
                result_json = json.dumps(result, indent=2, default=str)

                logger.success(
                    f"Tool {name} executed successfully",
                    extra={"tool": name}
                )

                return [TextContent(type="text", text=result_json)]

            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                logger.error(error_msg, extra={"tool": name, "error": str(e)})
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg})
                )]

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        await self.api_service.close()
        logger.info("Cleanup complete")

    async def run(self):
        """Run the MCP server."""
        logger.info(f"Starting {self.settings.mcp_server_name}...")

        try:
            # Start periodic cache cleanup task
            async def cache_cleanup_task():
                while True:
                    await asyncio.sleep(300)  # Every 5 minutes
                    cleaned = await self.cache_service.cleanup_expired()
                    if cleaned > 0:
                        logger.debug(f"Cleaned {cleaned} expired cache entries")

            # Start cache cleanup in background
            cleanup_task = asyncio.create_task(cache_cleanup_task())

            # Run the server
            async with stdio_server() as (read_stream, write_stream):
                logger.info("MCP server started successfully")
                await self.server.run(read_stream, write_stream)

        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
        finally:
            cleanup_task.cancel()
            await self.cleanup()


async def main():
    """Main entry point."""
    # Setup logging first
    setup_logging()

    # Create and run server
    server = ApiSportsMCPServer()
    await server.run()


def run():
    """Synchronous entry point for the script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
