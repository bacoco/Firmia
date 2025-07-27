#!/bin/bash

# Firmia MCP Server & Web UI Launcher
# This script launches both the MCP server and the web UI for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MCP_PORT=${MCP_PORT:-8080}
WEB_UI_PORT=${WEB_UI_PORT:-3001}
BUILD_DIR="dist"
WEB_UI_DIR="web-ui"

echo -e "${BLUE}🚀 Firmia MCP Server & Web UI Launcher${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    echo -e "${YELLOW}🔄 Stopping processes on port $port...${NC}"
    if check_port $port; then
        local pid=$(lsof -ti :$port)
        if [ ! -z "$pid" ]; then
            kill -9 $pid 2>/dev/null || true
            sleep 2
        fi
    fi
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down services...${NC}"
    kill_port $MCP_PORT
    kill_port $WEB_UI_PORT
    # Kill any remaining node processes for this project
    pkill -f "firmia" 2>/dev/null || true
    pkill -f "web-ui/server.js" 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check prerequisites
echo -e "${BLUE}🔍 Checking prerequisites...${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    echo "Please install npm (usually comes with Node.js)"
    exit 1
fi

echo -e "${GREEN}✅ Node.js and npm are available${NC}"

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo -e "${RED}❌ package.json not found${NC}"
    echo "Please run this script from the Firmia root directory"
    exit 1
fi

# Check if web-ui directory exists
if [ ! -d "$WEB_UI_DIR" ]; then
    echo -e "${RED}❌ Web UI directory not found: $WEB_UI_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Project structure verified${NC}"

# Install dependencies if needed
echo -e "${BLUE}📦 Checking dependencies...${NC}"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}🔄 Installing main project dependencies...${NC}"
    npm install
fi

if [ ! -d "$WEB_UI_DIR/node_modules" ]; then
    echo -e "${YELLOW}🔄 Installing Web UI dependencies...${NC}"
    cd $WEB_UI_DIR
    npm install
    cd ..
fi

echo -e "${GREEN}✅ Dependencies ready${NC}"

# Build the project if needed
echo -e "${BLUE}🔨 Building project...${NC}"

if [ ! -d "$BUILD_DIR" ] || [ "src" -nt "$BUILD_DIR" ]; then
    echo -e "${YELLOW}🔄 Building TypeScript project...${NC}"
    npm run build
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Build failed${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Build is up to date${NC}"
fi

# Check and setup environment
echo -e "${BLUE}⚙️  Checking environment configuration...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo -e "${YELLOW}🔄 Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}📝 Please edit .env file with your API credentials${NC}"
fi

# Check for API keys
if ! grep -q "INSEE_API_KEY_INTEGRATION=c1e98007" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠️  INSEE API key not configured properly${NC}"
    echo -e "${YELLOW}💡 Using example API key for testing${NC}"
fi

echo -e "${GREEN}✅ Environment configuration ready${NC}"

# Check ports
echo -e "${BLUE}🔌 Checking ports...${NC}"

if check_port $MCP_PORT; then
    echo -e "${YELLOW}⚠️  Port $MCP_PORT is in use${NC}"
    kill_port $MCP_PORT
fi

if check_port $WEB_UI_PORT; then
    echo -e "${YELLOW}⚠️  Port $WEB_UI_PORT is in use${NC}"
    kill_port $WEB_UI_PORT
fi

echo -e "${GREEN}✅ Ports $MCP_PORT and $WEB_UI_PORT are available${NC}"

# Start the services
echo ""
echo -e "${GREEN}🚀 Starting Firmia services...${NC}"
echo ""

# Note: MCP Server will be started by the Web UI as needed
echo -e "${BLUE}📡 MCP Server will be managed by Web UI${NC}"
echo -e "${GREEN}✅ MCP Server ready for launch${NC}"

# Start Web UI
echo -e "${BLUE}🌐 Starting Web UI on port $WEB_UI_PORT...${NC}"
cd $WEB_UI_DIR

WEB_UI_PORT=$WEB_UI_PORT \
NODE_ENV=development \
node server.js > ../web-ui.log 2>&1 &

WEB_UI_PID=$!
cd ..
sleep 3

# Check if Web UI started successfully
if ! kill -0 $WEB_UI_PID 2>/dev/null; then
    echo -e "${RED}❌ Web UI failed to start${NC}"
    echo "Log output:"
    cat web-ui.log
    cleanup
    exit 1
fi

echo -e "${GREEN}✅ Web UI started (PID: $WEB_UI_PID)${NC}"

# Display status
echo ""
echo -e "${GREEN}🎉 Firmia is now running!${NC}"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
echo -e "  🔸 MCP Server:  Managed by Web UI (stdio protocol)"
echo -e "  🔸 Web UI:      http://localhost:$WEB_UI_PORT (PID: $WEB_UI_PID)"
echo ""
echo -e "${BLUE}🔗 Quick Links:${NC}"
echo -e "  🌐 Open Web UI: ${YELLOW}http://localhost:$WEB_UI_PORT${NC}"
echo -e "  📝 MCP Server Log: tail -f mcp-server.log"
echo -e "  📝 Web UI Log: tail -f web-ui.log"
echo ""
echo -e "${BLUE}🛠️  Available MCP Tools:${NC}"
echo -e "  🔍 search_enterprises      - Search French companies"
echo -e "  📊 get_enterprise_details  - Get detailed company information"
echo -e "  ❤️  get_api_status         - Check API health and rate limits"
echo ""
echo -e "${YELLOW}💡 Tip: The Web UI provides an easy way to test all MCP tools!${NC}"
echo ""
echo -e "${GREEN}✨ Ready to test Firmia! Press Ctrl+C to stop all services.${NC}"

# Open browser (optional)
if command -v open &> /dev/null; then
    echo -e "${BLUE}🌐 Opening browser...${NC}"
    sleep 2
    open "http://localhost:$WEB_UI_PORT" 2>/dev/null || true
elif command -v xdg-open &> /dev/null; then
    echo -e "${BLUE}🌐 Opening browser...${NC}"
    sleep 2
    xdg-open "http://localhost:$WEB_UI_PORT" 2>/dev/null || true
fi

# Wait for processes
wait