# MCP Firms - Installation Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Integration with MCP Clients](#integration-with-mcp-clients)
- [Configuration](#configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- **Node.js**: 18.0.0 or higher
- **npm**: 8.0.0 or higher (or yarn/pnpm equivalent)
- **Operating System**: macOS, Linux, or Windows

### API Access Requirements
Before using MCP Firms, you'll need to obtain API credentials from:

1. **INSEE** (Required for company identification)
   - Visit [INSEE Developer Portal](https://api.insee.fr)
   - Create a free account
   - Subscribe to the "Sirene - V3" API

2. **Banque de France** (Optional for financial data)
   - Contact [webstat@banque-france.fr](mailto:webstat@banque-france.fr)
   - Request access to enterprise data API

3. **INPI** (Optional for intellectual property data)
   - Visit [INPI Data Portal](https://data.inpi.fr)
   - Create developer account and request API access

## Installation Methods

### Method 1: NPM Installation (Recommended)

```bash
# Install globally for system-wide access
npm install -g mcp-firms

# Or install locally in your project
npm install mcp-firms
```

### Method 2: From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-firms.git
cd mcp-firms

# Install dependencies
npm install

# Build the project
npm run build

# Install globally
npm install -g .
```

### Method 3: Direct Download

Download the latest release from GitHub:
```bash
# Download and install from GitHub releases
wget https://github.com/yourusername/mcp-firms/releases/latest/download/mcp-firms-1.0.0.tgz
npm install -g mcp-firms-1.0.0.tgz
```

## Integration with MCP Clients

### Claude Desktop

1. **Locate configuration file**:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add MCP Firms configuration**:
   ```json
   {
     "mcpServers": {
       "mcp-firms": {
         "command": "mcp-firms",
         "env": {
           "INSEE_API_KEY": "your_insee_api_key",
           "BANQUE_FRANCE_API_KEY": "your_banque_france_api_key",
           "INPI_API_KEY": "your_inpi_api_key"
         }
       }
     }
   }
   ```

3. **Alternative configuration with Node.js path**:
   ```json
   {
     "mcpServers": {
       "mcp-firms": {
         "command": "node",
         "args": ["/path/to/global/node_modules/mcp-firms/dist/index.js"],
         "env": {
           "INSEE_API_KEY": "your_insee_api_key",
           "BANQUE_FRANCE_API_KEY": "your_banque_france_api_key",
           "INPI_API_KEY": "your_inpi_api_key"
         }
       }
     }
   }
   ```

### VS Code Extension

If using the MCP VS Code extension:

1. **Install the MCP extension** from the VS Code marketplace
2. **Add server configuration** in VS Code settings:
   ```json
   {
     "mcp.servers": {
       "mcp-firms": {
         "command": "mcp-firms",
         "env": {
           "INSEE_API_KEY": "your_insee_api_key"
         }
       }
     }
   }
   ```

### Other MCP Clients

For other MCP-compatible clients, use the stdio transport:

```javascript
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";

const client = new Client({
  name: "mcp-firms-client",
  version: "1.0.0"
});

const transport = new StdioClientTransport({
  command: "mcp-firms",
  env: {
    INSEE_API_KEY: "your_api_key"
  }
});

await client.connect(transport);
```

## Configuration

### Environment Variables

Create a `.env` file in your project or set environment variables:

```env
# Required - INSEE API for company identification
INSEE_API_KEY=your_insee_api_key

# Optional - Banque de France for financial data
BANQUE_FRANCE_API_KEY=your_banque_france_api_key
BANQUE_FRANCE_USERNAME=your_username
BANQUE_FRANCE_PASSWORD=your_password

# Optional - INPI for intellectual property data
INPI_API_KEY=your_inpi_api_key
INPI_CLIENT_ID=your_client_id
INPI_CLIENT_SECRET=your_client_secret

# Cache configuration (optional)
CACHE_TTL=3600                    # 1 hour cache
RATE_LIMIT_INSEE=5000            # Requests per hour
RATE_LIMIT_BANQUE_FRANCE=1000    # Requests per hour
RATE_LIMIT_INPI=2000             # Requests per hour
```

### Configuration File

Alternatively, create a configuration file:

```json
{
  "apis": {
    "insee": {
      "apiKey": "your_insee_api_key",
      "baseUrl": "https://api.insee.fr/entreprises/sirene/V3"
    },
    "banqueFrance": {
      "apiKey": "your_banque_france_api_key",
      "username": "your_username", 
      "password": "your_password"
    },
    "inpi": {
      "apiKey": "your_inpi_api_key",
      "clientId": "your_client_id",
      "clientSecret": "your_client_secret"
    }
  },
  "cache": {
    "ttl": 3600,
    "maxSize": 100
  },
  "rateLimits": {
    "insee": 5000,
    "banqueFrance": 1000,
    "inpi": 2000
  }
}
```

## Verification

### Test the Installation

1. **Check if globally installed**:
   ```bash
   npm list -g mcp-firms
   ```

2. **Verify the binary**:
   ```bash
   which mcp-firms
   ```

3. **Test basic functionality**:
   
   Create a test script:
   ```javascript
   // test-mcp-firms.js
   import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
   import { Client } from "@modelcontextprotocol/sdk/client/index.js";

   async function test() {
     const client = new Client({ name: "test", version: "1.0.0" });
     const transport = new StdioClientTransport({
       command: "mcp-firms",
       env: { INSEE_API_KEY: "your_key" }
     });

     try {
       await client.connect(transport);
       const tools = await client.listTools();
       console.log("Available tools:", tools.tools.map(t => t.name));
       await client.close();
     } catch (error) {
       console.error("Connection failed:", error.message);
     }
   }

   test();
   ```

   Run the test:
   ```bash
   node test-mcp-firms.js
   ```

### Expected Output

You should see:
```
Available tools: [ 'search_enterprises', 'get_enterprise_details', 'get_api_status' ]
```

## Troubleshooting

### Common Issues

#### 1. "mcp-firms: command not found"

**Solution**: Ensure the global npm bin directory is in your PATH:
```bash
# Check npm global bin directory
npm config get prefix

# Add to your shell profile (.bashrc, .zshrc, etc.)
export PATH="$(npm config get prefix)/bin:$PATH"
```

#### 2. "Cannot find module @modelcontextprotocol/sdk"

**Solution**: Reinstall with correct dependencies:
```bash
npm uninstall -g mcp-firms
npm install -g mcp-firms
```

#### 3. API Authentication Failures

**Solution**: Verify API credentials:
- Check that API keys are correctly set in environment variables
- Ensure API keys have proper permissions
- Test API access independently:

```bash
# Test INSEE API
curl -H "Authorization: Bearer YOUR_INSEE_TOKEN" \
  "https://api.insee.fr/entreprises/sirene/V3/siret/12345678912345"
```

#### 4. "Permission denied" on macOS/Linux

**Solution**: Fix npm permissions:
```bash
# Option 1: Use npx
npx mcp-firms

# Option 2: Fix npm permissions
sudo chown -R $(whoami) $(npm config get prefix)/{lib/node_modules,bin,share}
```

#### 5. Rate Limit Exceeded

**Solution**: Adjust rate limits in configuration:
```env
RATE_LIMIT_INSEE=1000        # Reduce from default 5000
CACHE_TTL=7200              # Increase cache time
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug environment variable
DEBUG=mcp-firms:* mcp-firms

# Or in your MCP client configuration
{
  "env": {
    "DEBUG": "mcp-firms:*",
    "MCP_LOG_LEVEL": "debug"
  }
}
```

### Logging

Check logs in:
- **macOS**: `~/Library/Logs/Claude/mcp-firms.log`
- **Linux**: `~/.local/share/claude/logs/mcp-firms.log`
- **Windows**: `%LOCALAPPDATA%\Claude\Logs\mcp-firms.log`

### Getting Help

If you continue to experience issues:

1. **Check GitHub Issues**: [https://github.com/yourusername/mcp-firms/issues](https://github.com/yourusername/mcp-firms/issues)
2. **Create a Bug Report**: Include:
   - Node.js version (`node --version`)
   - npm version (`npm --version`)
   - Operating system
   - Error messages
   - Configuration (without sensitive data)
3. **Community Support**: Join our Discord server or discussions

## Advanced Configuration

### Performance Optimization

For high-volume usage:

```env
# Increase cache settings
CACHE_TTL=7200                    # 2 hour cache
CACHE_MAX_SIZE=500               # 500MB cache

# Optimize concurrent requests
MAX_CONCURRENT_REQUESTS_INSEE=10
MAX_CONCURRENT_REQUESTS_BANQUE_FRANCE=5

# Enable batching
ENABLE_BATCHING=true
BATCH_SIZE=20
```

### Production Deployment

For production environments:

```env
NODE_ENV=production
MCP_LOG_LEVEL=warn
ENABLE_MONITORING=true
ENABLE_ANALYTICS=false           # Disable analytics for privacy
```

### Custom API Endpoints

If using custom or proxy endpoints:

```env
INSEE_API_URL=https://your-proxy.com/insee
BANQUE_FRANCE_API_URL=https://your-proxy.com/banque-france
INPI_API_URL=https://your-proxy.com/inpi
```

## Next Steps

After successful installation:

1. **Read the API Documentation**: [docs/API.md](../API.md)
2. **Try the Examples**: [docs/examples/](../examples/)
3. **Explore Use Cases**: [docs/examples/use-cases.md](../examples/use-cases.md)
4. **Configure for Production**: Optimize cache and rate limits for your usage patterns