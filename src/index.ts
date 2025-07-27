#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import dotenv from "dotenv";
import { setupAdapters } from "./adapters/index.js";
import { createRateLimiter } from "./rate-limiter/index.js";
import { createCache } from "./cache/index.js";

// Load environment variables
dotenv.config();

// Initialize the MCP server
const server = new Server({
  name: "mcp-firms",
  version: "1.0.0"
}, {
  capabilities: {
    tools: {}
  }
});

// Initialize rate limiter and cache
const rateLimiter = createRateLimiter();
const cache = createCache();

// Setup adapters for different data sources
const adapters = setupAdapters({ rateLimiter, cache });

// Define the schema for enterprise search
const SearchSchema = z.object({
  query: z.string().describe("Enterprise name or SIREN/SIRET number"),
  source: z.enum(["all", "insee", "banque-france", "inpi"]).default("all"),
  includeHistory: z.boolean().default(false),
  maxResults: z.number().min(1).max(100).default(10)
});

// Define the schema for detailed enterprise info
const EnterpriseDetailSchema = z.object({
  siren: z.string().regex(/^\d{9}$/, "SIREN must be 9 digits"),
  source: z.enum(["all", "insee", "banque-france", "inpi"]).default("all"),
  includeFinancials: z.boolean().default(true),
  includeIntellectualProperty: z.boolean().default(true)
});

// Register list_tools handler
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_enterprises",
        description: "Search for French enterprises across multiple data sources",
        inputSchema: SearchSchema
      },
      {
        name: "get_enterprise_details", 
        description: "Get detailed information about a French enterprise by SIREN",
        inputSchema: EnterpriseDetailSchema
      },
      {
        name: "get_api_status",
        description: "Check the status and rate limits of connected APIs",
        inputSchema: z.object({})
      }
    ]
  };
});

// Register call_tool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: params } = request.params;
  
  switch (name) {
    case "search_enterprises": {
      const { query, source, includeHistory, maxResults } = params as any;
    
    try {
      let results = [];
      
      if (source === "all") {
        // Search across all adapters
        const searchPromises = Object.entries(adapters).map(([name, adapter]) => 
          adapter.search(query, { includeHistory, maxResults })
            .then(data => ({ source: name, data }))
            .catch(error => ({ source: name, error: error.message }))
        );
        
        results = await Promise.all(searchPromises);
      } else {
        // Search specific adapter
        const adapter = adapters[source];
        if (!adapter) {
          throw new Error(`Unknown source: ${source}`);
        }
        
        const data = await adapter.search(query, { includeHistory, maxResults });
        results = [{ source, data }];
      }
      
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            success: true,
            results
          }, null, 2)
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: "text", 
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : "Unknown error"
          }, null, 2)
        }]
      };
    }
    }
    
    case "get_enterprise_details": {
      const { siren, source, includeFinancials, includeIntellectualProperty } = params as any;
    
    try {
      let details = {};
      
      if (source === "all") {
        // Fetch from all adapters
        const detailPromises = Object.entries(adapters).map(([name, adapter]) => 
          adapter.getDetails(siren, { includeFinancials, includeIntellectualProperty })
            .then(data => ({ [name]: data }))
            .catch(error => ({ [name]: { error: error.message } }))
        );
        
        const results = await Promise.all(detailPromises);
        details = Object.assign({}, ...results);
      } else {
        // Fetch from specific adapter
        const adapter = adapters[source];
        if (!adapter) {
          throw new Error(`Unknown source: ${source}`);
        }
        
        (details as any)[source] = await adapter.getDetails(siren, { 
          includeFinancials, 
          includeIntellectualProperty 
        });
      }
      
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            success: true,
            siren,
            details
          }, null, 2)
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : "Unknown error"
          }, null, 2)
        }]
      };
    }
    }
    
    case "get_api_status": {
    try {
      const statusPromises = Object.entries(adapters).map(async ([name, adapter]) => {
        try {
          const status = await adapter.getStatus();
          return { [name]: status };
        } catch (error) {
          return { 
            [name]: { 
              available: false, 
              error: error instanceof Error ? error.message : "Unknown error" 
            } 
          };
        }
      });
      
      const results = await Promise.all(statusPromises);
      const status = Object.assign({}, ...results);
      
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            success: true,
            status
          }, null, 2)
        }]
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : "Unknown error"
          }, null, 2)
        }]
      };
    }
    }
    
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP Firms server running on stdio");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error("Failed to start MCP server:", error);
    process.exit(1);
  });
}

export default server;