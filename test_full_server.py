"""Test the full Firmia MCP server with all 23 tools."""

import asyncio
import os
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",
    args=["-m", "src.server_demo"],  # Use demo server for testing
    env=dict(os.environ)  # Pass through environment variables
)


async def test_server():
    """Test the MCP server with all tools."""
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            print("Connecting to Firmia MCP server...")
            await session.initialize()
            print("Connected successfully!")
            
            # List available tools
            tools = await session.list_tools()
            print(f"\n✨ Available tools: {len(tools.tools)}")
            
            # Group tools by category
            categories = {
                "Search & Discovery": [],
                "Company Information": [],
                "Documents & Legal": [],
                "Analytics & Market Intelligence": [],
                "Data Operations": [],
                "System": []
            }
            
            for tool in tools.tools:
                name = tool.name
                desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
                
                # Categorize based on tool name
                if name in ["search_companies", "search_legal_announcements", "search_associations", "search_certified_companies"]:
                    categories["Search & Discovery"].append((name, desc))
                elif name in ["get_company_profile", "get_company_analytics", "get_company_health_score", "get_association_details", "check_if_association", "check_certifications"]:
                    categories["Company Information"].append((name, desc))
                elif name in ["download_document", "list_documents", "get_announcement_timeline", "check_financial_health"]:
                    categories["Documents & Legal"].append((name, desc))
                elif name in ["get_market_analytics", "get_trend_analysis", "get_certification_domains"]:
                    categories["Analytics & Market Intelligence"].append((name, desc))
                elif name in ["export_data", "batch_operation", "update_static_data", "get_pipeline_status"]:
                    categories["Data Operations"].append((name, desc))
                else:
                    categories["System"].append((name, desc))
            
            # Display categorized tools
            for category, tool_list in categories.items():
                if tool_list:
                    print(f"\n📂 {category}:")
                    for name, desc in tool_list:
                        print(f"  • {name}: {desc}")
            
            # Test some tools
            print("\n" + "="*60)
            print("🧪 Testing Selected Tools")
            print("="*60)
            
            # Test 1: Health check
            print("\n1️⃣ Testing health_check...")
            try:
                result = await session.call_tool("health_check", {})
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"   ✅ Status: {data['status']}")
                        print(f"   ✅ Version: {data['version']}")
                        print(f"   ✅ Tools available: {data['tools_available']}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            # Test 2: Search companies
            print("\n2️⃣ Testing search_companies...")
            try:
                result = await session.call_tool("search_companies", {
                    "query": "Carrefour",
                    "page": 1,
                    "per_page": 5
                })
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"   ✅ Found {data['pagination']['total']} results")
                        print(f"   📊 Showing first {len(data['results'])} results:")
                        for r in data['results'][:3]:
                            print(f"      - {r.get('nom_complet', 'N/A')} (SIREN: {r.get('siren', 'N/A')})")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            # Test 3: Get certification domains
            print("\n3️⃣ Testing get_certification_domains...")
            try:
                result = await session.call_tool("get_certification_domains", {})
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"   ✅ Certification types: {len(data['certification_types'])}")
                        for cert_type, desc in list(data['certification_types'].items())[:3]:
                            print(f"      - {cert_type}: {desc}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_server())