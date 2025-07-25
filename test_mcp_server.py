"""Test the Firmia MCP server using stdio client."""

import asyncio
import os
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.context import RequestContext

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",
    args=["-m", "src.server_new"],
    env=dict(os.environ)  # Pass through environment variables
)


async def test_server():
    """Test the MCP server with basic operations."""
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            print("Connecting to Firmia MCP server...")
            await session.initialize()
            print("Connected successfully!")
            
            # Server info is available after initialization
            print("\nServer connected successfully!")
            
            # List available tools
            tools = await session.list_tools()
            print(f"\nAvailable tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")
                if tool.inputSchema:
                    print(f"    Input schema: {json.dumps(tool.inputSchema, indent=6)}")
            
            # Test the health_check tool
            print("\n--- Testing health_check tool ---")
            try:
                result = await session.call_tool("health_check", {})
                # Extract the text content from the result
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"Result: {content.text}")
            except Exception as e:
                print(f"Error: {e}")
            
            # Test the add_numbers tool
            print("\n--- Testing add_numbers tool ---")
            try:
                result = await session.call_tool("add_numbers", {"a": 5, "b": 3})
                # Extract the text content from the result
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(f"5 + 3 = {content.text}")
            except Exception as e:
                print(f"Error: {e}")
            
            print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(test_server())