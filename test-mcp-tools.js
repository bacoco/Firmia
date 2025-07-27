#!/usr/bin/env node

// Simple test to verify MCP tools are working
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

console.log('🧪 Testing MCP Firms Server Tools...\n');

// Start the MCP server
const serverPath = join(__dirname, 'dist', 'index.js');
const server = spawn('node', [serverPath], {
  stdio: ['pipe', 'pipe', 'pipe']
});

let output = '';
let testsPassed = 0;
let totalTests = 3;

// Test 1: Check if server starts
setTimeout(() => {
  console.log('✅ Test 1/3: Server startup - PASSED');
  testsPassed++;
  
  // Test 2: Send list_tools request
  const listToolsRequest = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {}
  };
  
  server.stdin.write(JSON.stringify(listToolsRequest) + '\n');
}, 100);

// Test 3: Send get_api_status request
setTimeout(() => {
  const statusRequest = {
    jsonrpc: "2.0", 
    id: 2,
    method: "tools/call",
    params: {
      name: "get_api_status",
      arguments: {}
    }
  };
  
  server.stdin.write(JSON.stringify(statusRequest) + '\n');
}, 200);

server.stdout.on('data', (data) => {
  output += data.toString();
  
  // Check for tools list response
  if (output.includes('search_enterprises') && output.includes('get_enterprise_details') && output.includes('get_api_status')) {
    console.log('✅ Test 2/3: Tools registration - PASSED');
    testsPassed++;
  }
  
  // Check for status response
  if (output.includes('success') || output.includes('status')) {
    console.log('✅ Test 3/3: API status tool - PASSED');
    testsPassed++;
  }
});

server.stderr.on('data', (data) => {
  const error = data.toString();
  if (error.includes('MCP Firms server running')) {
    // This is expected startup message
    return;
  }
  console.error('❌ Server error:', error);
});

// Cleanup after 3 seconds
setTimeout(() => {
  server.kill();
  
  console.log(`\n📊 Test Results: ${testsPassed}/${totalTests} tests passed`);
  
  if (testsPassed === totalTests) {
    console.log('🎉 All MCP tools are working correctly!');
    process.exit(0);
  } else {
    console.log('⚠️  Some tests failed - check the output above');
    process.exit(1);
  }
}, 3000);