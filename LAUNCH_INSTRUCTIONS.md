# Firmia MCP Server Launch Instructions

## Quick Start

The Firmia MCP server has been successfully configured and tested. Here's how to launch it:

### 1. Prerequisites

Ensure you have:
- Python 3.12+ installed
- Virtual environment activated
- Dependencies installed (already done)

### 2. Launch the Server

From the Firmia directory, you have three server options:

#### Option A: Basic Server (2 test tools)
```bash
cd /Users/loic/develop/pappersv2/Firmia
source .venv/bin/activate
python -m src.server_new
```

#### Option B: Demo Server (23 tools with mock data)
```bash
cd /Users/loic/develop/pappersv2/Firmia
source .venv/bin/activate
python -m src.server_demo
```

#### Option C: Full Server (23 tools with real APIs - requires credentials)
```bash
cd /Users/loic/develop/pappersv2/Firmia
source .venv/bin/activate
python -m src.server_full
```

The server will start in stdio mode, waiting for MCP client connections.

### 3. Test the Server

In another terminal, run the test script:

```bash
cd /Users/loic/develop/pappersv2/Firmia
source .venv/bin/activate
python test_mcp_server.py
```

You should see:
- Server connects successfully
- Available tools listed (currently health_check and add_numbers)
- Health check showing server status
- Test calculations working

### 4. Current Status

✅ **What's Working:**
- MCP server framework configured with correct imports
- Basic tools (health_check, add_numbers) functional
- Authentication manager initialized (for public APIs)
- Server accepts stdio connections

⚠️ **What Needs Configuration:**
- Redis server (optional - server runs without it)
- API credentials in .env file (optional - public APIs work without auth)

🔧 **Next Steps:**
- Migrate existing class-based tools to FastMCP decorators (optional)
- Add API credentials for authenticated endpoints
- Install and configure Redis for caching

### 5. Environment Variables

The server uses the following environment variables from `.env`:

```env
# Optional API Credentials (server works without these)
INSEE_CLIENT_ID=your_insee_client_id
INSEE_CLIENT_SECRET=your_insee_client_secret
INPI_USERNAME=your_inpi_username
INPI_PASSWORD=your_inpi_password
API_ENTREPRISE_TOKEN=your_api_entreprise_token

# Infrastructure (optional)
REDIS_URL=redis://localhost:6379/0

# Server Configuration
MCP_HOST=0.0.0.0
MCP_PORT=8789
ENVIRONMENT=development
```

### 6. Available APIs Without Authentication

The following APIs work without any credentials:
- Recherche Entreprises (company search)
- BODACC (legal announcements)
- RNA (associations)
- RGE (environmental certifications)

### 7. Using with Claude Desktop

To use with Claude Desktop, add to your MCP settings:

#### For Demo Server (recommended for testing):
```json
{
  "servers": {
    "firmia-demo": {
      "command": "python",
      "args": ["-m", "src.server_demo"],
      "cwd": "/Users/loic/develop/pappersv2/Firmia",
      "env": {
        "PYTHONPATH": "/Users/loic/develop/pappersv2/Firmia"
      }
    }
  }
}
```

#### For Full Server (requires API credentials):
```json
{
  "servers": {
    "firmia": {
      "command": "python",
      "args": ["-m", "src.server_full"],
      "cwd": "/Users/loic/develop/pappersv2/Firmia",
      "env": {
        "PYTHONPATH": "/Users/loic/develop/pappersv2/Firmia"
      }
    }
  }
}
```

---

The server is now ready to use! Even without API credentials or Redis, you can access French company data through the public APIs.