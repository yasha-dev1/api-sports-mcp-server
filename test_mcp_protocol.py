#!/usr/bin/env python
"""Test MCP protocol messages directly."""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Test initialization message
init_message = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
        "protocolVersion": "0.1.0",
        "capabilities": {
            "tools": {}
        },
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    },
    "id": 1
}

print("Sending initialization message:")
print(json.dumps(init_message, indent=2))

# This would normally be sent to the server's stdin
# and we'd read the response from stdout