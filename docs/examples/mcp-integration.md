# MCP Integration Examples

This guide shows how to integrate MCP Firms with various MCP clients.

## Table of Contents
- [Claude Desktop Integration](#claude-desktop-integration)
- [VS Code Extension Integration](#vs-code-extension-integration)
- [Custom MCP Client Integration](#custom-mcp-client-integration)
- [Programmatic Usage](#programmatic-usage)
- [WebSocket Integration](#websocket-integration)

## Claude Desktop Integration

### Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-firms": {
      "command": "node",
      "args": ["/Users/yourusername/mcp-firms/dist/index.js"],
      "env": {
        "NODE_ENV": "production",
        "INSEE_API_KEY": "your_key_here",
        "BANQUE_FRANCE_API_KEY": "your_key_here",
        "INPI_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Usage in Claude

Once configured, you can use natural language queries:

```
"Search for information about Airbus"
"Get the financial data for SIREN 383474814"
"Show me all trademarks owned by company 552100554"
"Compare the financial performance of French aerospace companies"
```

Claude will automatically use the appropriate MCP tools:

```json
// Claude generates this internally:
{
  "tool": "search_enterprises",
  "params": {
    "query": "Airbus",
    "source": "all"
  }
}
```

## VS Code Extension Integration

### Installation

1. Install the MCP extension for VS Code
2. Configure in `.vscode/settings.json`:

```json
{
  "mcp.servers": {
    "mcp-firms": {
      "command": "node",
      "args": ["${workspaceFolder}/node_modules/mcp-firms/dist/index.js"],
      "env": {
        "NODE_ENV": "development",
        "DEBUG": "mcp-firms:*"
      }
    }
  }
}
```

### Using in VS Code

Access through Command Palette (`Ctrl+Shift+P`):

```
MCP: Search French Enterprises
MCP: Get Enterprise Details
MCP: Check API Status
```

Or use in integrated terminal:

```typescript
// In a TypeScript file
import { MCPClient } from '@modelcontextprotocol/client';

const client = new MCPClient();
await client.connect('mcp-firms');

const result = await client.callTool('search_enterprises', {
  query: 'technology',
  maxResults: 10
});
```

## Custom MCP Client Integration

### Node.js Client

```javascript
import { MCPClient } from '@modelcontextprotocol/client';
import { spawn } from 'child_process';

class FrenchEnterpriseClient {
  constructor() {
    this.client = new MCPClient();
  }

  async connect() {
    const server = spawn('node', [
      '/path/to/mcp-firms/dist/index.js'
    ], {
      env: {
        ...process.env,
        NODE_ENV: 'production'
      }
    });

    await this.client.connectToProcess(server);
    console.log('Connected to MCP Firms server');
  }

  async searchEnterprises(query, options = {}) {
    return this.client.callTool('search_enterprises', {
      query,
      ...options
    });
  }

  async getEnterpriseDetails(siren, options = {}) {
    return this.client.callTool('get_enterprise_details', {
      siren,
      ...options
    });
  }

  async getAPIStatus() {
    return this.client.callTool('get_api_status', {});
  }

  async disconnect() {
    await this.client.disconnect();
  }
}

// Usage
const client = new FrenchEnterpriseClient();
await client.connect();

try {
  const results = await client.searchEnterprises('Airbus');
  console.log(results);
} finally {
  await client.disconnect();
}
```

### Python Client

```python
import asyncio
import json
from mcp import MCPClient

class FrenchEnterpriseClient:
    def __init__(self):
        self.client = MCPClient()
    
    async def connect(self):
        await self.client.connect_to_server(
            command=['node', '/path/to/mcp-firms/dist/index.js'],
            env={
                'NODE_ENV': 'production',
                'INSEE_API_KEY': 'your_key',
                'BANQUE_FRANCE_API_KEY': 'your_key',
                'INPI_API_KEY': 'your_key'
            }
        )
    
    async def search_enterprises(self, query, **kwargs):
        return await self.client.call_tool('search_enterprises', {
            'query': query,
            **kwargs
        })
    
    async def get_enterprise_details(self, siren, **kwargs):
        return await self.client.call_tool('get_enterprise_details', {
            'siren': siren,
            **kwargs
        })
    
    async def close(self):
        await self.client.close()

# Usage
async def main():
    client = FrenchEnterpriseClient()
    await client.connect()
    
    try:
        # Search for aerospace companies
        results = await client.search_enterprises(
            query="aerospace",
            source="insee",
            max_results=20
        )
        
        # Get details for each company
        for company in results['results'][0]['data'][:5]:
            details = await client.get_enterprise_details(
                siren=company['siren'],
                include_financials=True
            )
            print(f"{company['name']}: {details}")
            
    finally:
        await client.close()

asyncio.run(main())
```

## Programmatic Usage

### TypeScript/JavaScript SDK

```typescript
// mcp-firms-sdk.ts
import { MCPClient } from '@modelcontextprotocol/client';

export interface SearchOptions {
  source?: 'all' | 'insee' | 'banque-france' | 'inpi';
  includeHistory?: boolean;
  maxResults?: number;
}

export interface DetailsOptions {
  source?: 'all' | 'insee' | 'banque-france' | 'inpi';
  includeFinancials?: boolean;
  includeIntellectualProperty?: boolean;
}

export class MCPFirmsSDK {
  private client: MCPClient;
  private connected: boolean = false;

  constructor(private serverPath: string) {
    this.client = new MCPClient();
  }

  async connect(): Promise<void> {
    if (this.connected) return;
    
    await this.client.connectToServer({
      command: 'node',
      args: [this.serverPath],
      env: process.env
    });
    
    this.connected = true;
  }

  async searchEnterprises(
    query: string, 
    options: SearchOptions = {}
  ): Promise<any> {
    await this.connect();
    
    return this.client.callTool('search_enterprises', {
      query,
      source: options.source || 'all',
      includeHistory: options.includeHistory || false,
      maxResults: options.maxResults || 10
    });
  }

  async getEnterpriseDetails(
    siren: string,
    options: DetailsOptions = {}
  ): Promise<any> {
    await this.connect();
    
    return this.client.callTool('get_enterprise_details', {
      siren,
      source: options.source || 'all',
      includeFinancials: options.includeFinancials ?? true,
      includeIntellectualProperty: options.includeIntellectualProperty ?? true
    });
  }

  async getAPIStatus(): Promise<any> {
    await this.connect();
    return this.client.callTool('get_api_status', {});
  }

  async disconnect(): Promise<void> {
    if (this.connected) {
      await this.client.disconnect();
      this.connected = false;
    }
  }
}

// Usage example
async function example() {
  const sdk = new MCPFirmsSDK('/path/to/mcp-firms/dist/index.js');
  
  try {
    // Search for companies
    const searchResults = await sdk.searchEnterprises('technology', {
      source: 'insee',
      maxResults: 20
    });
    
    // Get detailed information
    for (const company of searchResults.results[0].data) {
      const details = await sdk.getEnterpriseDetails(company.siren, {
        includeFinancials: true,
        includeIntellectualProperty: true
      });
      
      console.log(`Company: ${company.name}`);
      console.log(`Financial Rating: ${details.details['banque-france']?.rating?.score}`);
      console.log(`Patents: ${details.details.inpi?.patents?.length || 0}`);
    }
  } finally {
    await sdk.disconnect();
  }
}
```

### React Integration

```jsx
// useMCPFirms.js
import { useState, useEffect, useCallback } from 'react';
import { MCPFirmsSDK } from './mcp-firms-sdk';

export function useMCPFirms(serverPath) {
  const [sdk, setSdk] = useState(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const client = new MCPFirmsSDK(serverPath);
    setSdk(client);
    
    return () => {
      client.disconnect();
    };
  }, [serverPath]);

  const connect = useCallback(async () => {
    if (!sdk || connected) return;
    
    try {
      setLoading(true);
      await sdk.connect();
      setConnected(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [sdk, connected]);

  const searchEnterprises = useCallback(async (query, options) => {
    await connect();
    return sdk.searchEnterprises(query, options);
  }, [sdk, connect]);

  const getEnterpriseDetails = useCallback(async (siren, options) => {
    await connect();
    return sdk.getEnterpriseDetails(siren, options);
  }, [sdk, connect]);

  return {
    connected,
    loading,
    error,
    searchEnterprises,
    getEnterpriseDetails
  };
}

// Component example
function EnterpriseSearch() {
  const { searchEnterprises, getEnterpriseDetails, loading, error } = useMCPFirms(
    '/path/to/mcp-firms/dist/index.js'
  );
  const [results, setResults] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState(null);

  const handleSearch = async (query) => {
    try {
      const response = await searchEnterprises(query);
      if (response.success) {
        setResults(response.results[0].data);
      }
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  const handleSelectCompany = async (siren) => {
    try {
      const response = await getEnterpriseDetails(siren);
      if (response.success) {
        setSelectedCompany(response.details);
      }
    } catch (err) {
      console.error('Failed to get details:', err);
    }
  };

  return (
    <div>
      <SearchBar onSearch={handleSearch} disabled={loading} />
      <ResultsList 
        results={results} 
        onSelect={handleSelectCompany}
      />
      {selectedCompany && (
        <CompanyDetails details={selectedCompany} />
      )}
      {error && <ErrorMessage message={error} />}
    </div>
  );
}
```

## WebSocket Integration

### Server Setup

```javascript
// websocket-bridge.js
import { WebSocketServer } from 'ws';
import { MCPClient } from '@modelcontextprotocol/client';
import { spawn } from 'child_process';

const wss = new WebSocketServer({ port: 8080 });
const mcpClients = new Map();

wss.on('connection', (ws) => {
  const clientId = generateClientId();
  const mcpClient = new MCPClient();
  
  // Connect to MCP server
  const server = spawn('node', ['/path/to/mcp-firms/dist/index.js']);
  mcpClient.connectToProcess(server).then(() => {
    mcpClients.set(clientId, mcpClient);
    ws.send(JSON.stringify({ type: 'connected', clientId }));
  });

  ws.on('message', async (message) => {
    try {
      const request = JSON.parse(message);
      const client = mcpClients.get(clientId);
      
      if (!client) {
        ws.send(JSON.stringify({ 
          error: 'Not connected to MCP server' 
        }));
        return;
      }

      const response = await client.callTool(
        request.tool, 
        request.params
      );
      
      ws.send(JSON.stringify({
        id: request.id,
        response
      }));
    } catch (error) {
      ws.send(JSON.stringify({
        id: request.id,
        error: error.message
      }));
    }
  });

  ws.on('close', () => {
    const client = mcpClients.get(clientId);
    if (client) {
      client.disconnect();
      mcpClients.delete(clientId);
    }
  });
});
```

### WebSocket Client

```javascript
// websocket-client.js
class MCPFirmsWebSocketClient {
  constructor(url = 'ws://localhost:8080') {
    this.url = url;
    this.ws = null;
    this.pendingRequests = new Map();
    this.requestId = 0;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = () => resolve();
      this.ws.onerror = (error) => reject(error);
      
      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'connected') {
          console.log('Connected with ID:', message.clientId);
        } else if (message.id) {
          const pending = this.pendingRequests.get(message.id);
          if (pending) {
            if (message.error) {
              pending.reject(new Error(message.error));
            } else {
              pending.resolve(message.response);
            }
            this.pendingRequests.delete(message.id);
          }
        }
      };
    });
  }

  async callTool(tool, params) {
    const id = ++this.requestId;
    
    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      
      this.ws.send(JSON.stringify({
        id,
        tool,
        params
      }));
      
      // Timeout after 30 seconds
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error('Request timeout'));
        }
      }, 30000);
    });
  }

  async searchEnterprises(query, options = {}) {
    return this.callTool('search_enterprises', {
      query,
      ...options
    });
  }

  async getEnterpriseDetails(siren, options = {}) {
    return this.callTool('get_enterprise_details', {
      siren,
      ...options
    });
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const client = new MCPFirmsWebSocketClient();
await client.connect();

const results = await client.searchEnterprises('Airbus');
console.log(results);

client.close();
```

## Best Practices

1. **Connection Management**: Always properly connect and disconnect
2. **Error Handling**: Implement robust error handling for network issues
3. **Rate Limiting**: Respect API rate limits in your client
4. **Caching**: Implement client-side caching for frequently accessed data
5. **Timeout Handling**: Set appropriate timeouts for long-running requests
6. **Retry Logic**: Implement exponential backoff for failed requests
7. **Logging**: Add comprehensive logging for debugging
8. **Security**: Never expose API keys in client-side code