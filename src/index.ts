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

// Define the schema for beneficial owners
const BeneficialOwnersSchema = z.object({
  siren: z.string().regex(/^\d{9}$/, "SIREN must be 9 digits")
});

// Define the schema for company publications
const CompanyPublicationsSchema = z.object({
  siren: z.string().regex(/^\d{9}$/, "SIREN must be 9 digits"),
  type: z.enum(["ACTE", "BILAN", "ALL"]).default("ALL"),
  from: z.string().optional().describe("Start date (YYYY-MM-DD)"),
  to: z.string().optional().describe("End date (YYYY-MM-DD)"),
  includeConfidential: z.boolean().default(false)
});

// Define the schema for differential updates
const DifferentialUpdatesSchema = z.object({
  from: z.string().describe("Start date (YYYY-MM-DD)"),
  to: z.string().optional().describe("End date (YYYY-MM-DD)"),
  pageSize: z.number().min(1).max(1000).default(100),
  searchAfter: z.string().optional().describe("Pagination cursor")
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
      },
      {
        name: "get_beneficial_owners",
        description: "Get beneficial ownership information for a French enterprise (INPI only)",
        inputSchema: BeneficialOwnersSchema
      },
      {
        name: "get_company_publications",
        description: "Get company publications and legal documents (INPI only)",
        inputSchema: CompanyPublicationsSchema
      },
      {
        name: "get_differential_updates",
        description: "Get recent company changes and updates (INPI only)",
        inputSchema: DifferentialUpdatesSchema
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
    
    case "get_beneficial_owners": {
      const { siren } = params as any;
      
      try {
        const inpiAdapter = adapters["inpi"] as any;
        if (!inpiAdapter || !inpiAdapter.getBeneficialOwners) {
          throw new Error("INPI adapter not available or doesn't support beneficial owners");
        }
        
        const beneficialOwners = await inpiAdapter.getBeneficialOwners(siren);
        
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              success: true,
              siren,
              beneficialOwners
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
    
    case "get_company_publications": {
      const { siren, type, from, to, includeConfidential } = params as any;
      
      try {
        const inpiAdapter = adapters["inpi"] as any;
        if (!inpiAdapter || !inpiAdapter.getCompanyPublications) {
          throw new Error("INPI adapter not available or doesn't support company publications");
        }
        
        const options: any = { type, includeConfidential };
        if (from) options.from = new Date(from);
        if (to) options.to = new Date(to);
        
        const publications = await inpiAdapter.getCompanyPublications(siren, options);
        
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              success: true,
              siren,
              publications
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
    
    case "get_differential_updates": {
      const { from, to, pageSize, searchAfter } = params as any;
      
      try {
        const inpiAdapter = adapters["inpi"] as any;
        if (!inpiAdapter || !inpiAdapter.getDifferentialUpdates) {
          throw new Error("INPI adapter not available or doesn't support differential updates");
        }
        
        const options: any = { 
          from: new Date(from),
          pageSize,
          searchAfter
        };
        if (to) options.to = new Date(to);
        
        const updates = await inpiAdapter.getDifferentialUpdates(options);
        
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              success: true,
              updates
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