"""Test the Firmia MCP server."""

import asyncio
import json
import sys
from mcp import StdioServerTransport
from mcp.client import Client


async def test_server():
    """Test the MCP server with basic operations."""
    # Create a client
    client = Client(
        name="test-client",
        version="1.0.0"
    )
    
    # Connect to the server
    async with StdioServerTransport() as transport:
        async with client.connect(transport):
            print("Connected to server!")
            
            # List available tools
            tools = await client.list_tools()
            print(f"\nAvailable tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            # Test the health_check tool
            print("\nTesting health_check tool...")
            result = await client.call_tool("health_check", {})
            print(f"Health check result: {json.dumps(result, indent=2)}")
            
            # Test the add_numbers tool
            print("\nTesting add_numbers tool...")
            result = await client.call_tool("add_numbers", {"a": 5, "b": 3})
            print(f"5 + 3 = {result}")


if __name__ == "__main__":
    asyncio.run(test_server())