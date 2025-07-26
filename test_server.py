"""Test the Firmia MCP server using FastMCP client."""

import asyncio
import json
from fastmcp import Client

# Import the server module directly for in-memory testing
from src.server_new import mcp as server_new
from src.server_demo import mcp as server_demo


async def test_basic_server():
    """Test the basic server with 2 tools."""
    print("Testing Basic Server (server_new.py)")
    print("=" * 60)
    
    # Connect via in-memory transport
    async with Client(server_new) as client:
        print("✅ Connected to server")
        
        # List available tools
        tools = await client.list_tools()
        print(f"\n📦 Available tools: {len(tools)}")
        for tool in tools:
            print(f"  • {tool.name}: {tool.description}")
        
        # Test health_check tool
        print("\n🧪 Testing health_check...")
        try:
            result = await client.call_tool("health_check", {})
            # Extract the actual data from CallToolResult
            if hasattr(result, 'data'):
                print(f"  ✅ Result: {json.dumps(result.data, indent=2)}")
            else:
                print(f"  ✅ Result: {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test add_numbers tool
        print("\n🧪 Testing add_numbers...")
        try:
            result = await client.call_tool("add_numbers", {"a": 5, "b": 3})
            # Extract the actual data from CallToolResult
            if hasattr(result, 'data'):
                print(f"  ✅ 5 + 3 = {result.data}")
            else:
                print(f"  ✅ 5 + 3 = {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def test_demo_server():
    """Test the demo server with all 23 tools."""
    print("\n\nTesting Demo Server (server_demo.py)")
    print("=" * 60)
    
    # Connect via in-memory transport
    async with Client(server_demo) as client:
        print("✅ Connected to server")
        
        # List available tools
        tools = await client.list_tools()
        print(f"\n📦 Available tools: {len(tools)}")
        
        # Group tools by category
        categories = {
            "Search & Discovery": [],
            "Company Information": [],
            "Documents & Legal": [],
            "Analytics & Market Intelligence": [],
            "Data Operations": [],
            "System": []
        }
        
        for tool in tools:
            name = tool.name
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            
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
        
        # Test a few tools
        print("\n🧪 Testing Selected Tools")
        print("-" * 40)
        
        # Test search_companies
        print("\n1️⃣ Testing search_companies...")
        try:
            result = await client.call_tool("search_companies", {
                "query": "Carrefour",
                "page": 1,
                "per_page": 3
            })
            # Extract the actual data from CallToolResult
            data = result.data if hasattr(result, 'data') else result
            print(f"  ✅ Found {data['pagination']['total']} results")
            print(f"  📊 First {len(data['results'])} results:")
            for r in data['results'][:3]:
                print(f"     - {r.get('nom_complet', 'N/A')} (SIREN: {r.get('siren', 'N/A')})")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test get_certification_domains
        print("\n2️⃣ Testing get_certification_domains...")
        try:
            result = await client.call_tool("get_certification_domains", {})
            # Extract the actual data from CallToolResult
            data = result.data if hasattr(result, 'data') else result
            print(f"  ✅ Found {len(data['certification_types'])} certification types")
            for cert, desc in list(data['certification_types'].items())[:3]:
                print(f"     - {cert}: {desc}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def main():
    """Run all tests."""
    print("🚀 Firmia FastMCP Server Tests")
    print("=" * 60)
    
    # Test basic server
    await test_basic_server()
    
    # Test demo server
    await test_demo_server()
    
    print("\n\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())