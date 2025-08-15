#!/usr/bin/env python
"""Standalone script to run the MCP server - useful for IDE debugging."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_server_api_sports.server import run  # noqa: E402

if __name__ == "__main__":
    run()
