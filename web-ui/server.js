const express = require('express');
const cors = require('cors');
const path = require('path');
const { spawn } = require('child_process');
const dotenv = require('dotenv');

// Load environment variables from parent directory
dotenv.config({ path: path.join(__dirname, '..', '.env') });

const app = express();
const PORT = process.env.WEB_UI_PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Store MCP server process
let mcpServerProcess = null;

// MCP Server management (stdio-based)
let mcpServerReady = false;

// Start MCP server
function startMCPServer() {
  if (mcpServerProcess) {
    console.log('MCP server already running');
    return;
  }

  console.log('Starting MCP server...');
  
  // Start the MCP server from the parent directory
  mcpServerProcess = spawn('node', ['../dist/index.js'], {
    cwd: __dirname,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { 
      ...process.env, 
      NODE_ENV: 'development',
      // Explicitly pass the working INSEE API key
      INSEE_API_KEY_INTEGRATION: process.env.INSEE_API_KEY_INTEGRATION || 'c1e98007-96f9-498a-a980-0796f9a98a23'
    }
  });

  mcpServerProcess.stdout.on('data', (data) => {
    const output = data.toString().trim();
    console.log(`MCP Server: ${output}`);
    
    // Check if server is ready
    if (output.includes('running on stdio')) {
      mcpServerReady = true;
    }
  });

  mcpServerProcess.stderr.on('data', (data) => {
    console.error(`MCP Server Error: ${data.toString().trim()}`);
  });

  mcpServerProcess.on('close', (code) => {
    console.log(`MCP server exited with code ${code}`);
    mcpServerProcess = null;
    mcpServerReady = false;
  });

  // Give it time to start
  setTimeout(() => {
    mcpServerReady = true;
  }, 2000);
}

// Stop MCP server
function stopMCPServer() {
  if (mcpServerProcess) {
    console.log('Stopping MCP server...');
    mcpServerProcess.kill();
    mcpServerProcess = null;
    mcpServerReady = false;
  }
}

// API Routes

// Get server status
app.get('/api/status', (req, res) => {
  res.json({
    webUI: 'running',
    mcpServer: mcpServerProcess && mcpServerReady ? 'running' : 'stopped',
    timestamp: new Date().toISOString()
  });
});

// Start MCP server
app.post('/api/mcp/start', (req, res) => {
  startMCPServer();
  res.json({ message: 'MCP server starting...', status: 'starting' });
});

// Stop MCP server
app.post('/api/mcp/stop', (req, res) => {
  stopMCPServer();
  res.json({ message: 'MCP server stopped', status: 'stopped' });
});

// Real MCP tool communication
app.post('/api/mcp/test/:tool', async (req, res) => {
  const { tool } = req.params;
  const { params } = req.body;

  try {
    if (!mcpServerProcess || !mcpServerReady) {
      throw new Error('MCP server is not running. Please start it first.');
    }

    const result = await callMCPTool(tool, params);
    res.json(result);
  } catch (error) {
    console.error(`MCP Tool Error (${tool}):`, error);
    res.status(400).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// Function to communicate with MCP server via JSON-RPC
async function callMCPTool(toolName, params) {
  return new Promise((resolve, reject) => {
    if (!mcpServerProcess) {
      reject(new Error('MCP server is not running'));
      return;
    }

    const requestId = Date.now();
    const jsonRpcRequest = {
      jsonrpc: '2.0',
      id: requestId,
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: params || {}
      }
    };

    let responseReceived = false;
    const timeout = setTimeout(() => {
      if (!responseReceived) {
        responseReceived = true;
        reject(new Error('MCP request timeout'));
      }
    }, 30000); // 30 second timeout

    // Listen for response
    const responseHandler = (data) => {
      if (responseReceived) return;
      
      try {
        const lines = data.toString().split('\n').filter(line => line.trim());
        
        for (const line of lines) {
          let response;
          try {
            response = JSON.parse(line);
          } catch (parseError) {
            continue; // Skip non-JSON lines
          }

          if (response.id === requestId) {
            responseReceived = true;
            clearTimeout(timeout);
            mcpServerProcess.stdout.removeListener('data', responseHandler);

            if (response.error) {
              reject(new Error(response.error.message || 'MCP server error'));
            } else {
              resolve({
                success: true,
                result: response.result,
                timestamp: new Date().toISOString()
              });
            }
            return;
          }
        }
      } catch (error) {
        console.error('Error parsing MCP response:', error);
      }
    };

    mcpServerProcess.stdout.on('data', responseHandler);

    // Send request to MCP server
    try {
      mcpServerProcess.stdin.write(JSON.stringify(jsonRpcRequest) + '\n');
    } catch (error) {
      responseReceived = true;
      clearTimeout(timeout);
      mcpServerProcess.stdout.removeListener('data', responseHandler);
      reject(new Error(`Failed to send MCP request: ${error.message}`));
    }
  });
}

// Serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\\nShutting down gracefully...');
  stopMCPServer();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\\nShutting down gracefully...');
  stopMCPServer();
  process.exit(0);
});

// Start the web server
app.listen(PORT, () => {
  console.log(`\\n🚀 Firmia Web UI running at http://localhost:${PORT}`);
  console.log(`📖 Open your browser to test the MCP server`);
  console.log(`🔧 MCP server will be started automatically when needed\\n`);
});

module.exports = app;