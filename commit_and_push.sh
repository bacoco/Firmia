#!/bin/bash

# Commit and Push Script for Firmia MCP Server

set -e  # Exit on error

echo "================================================"
echo "    Firmia MCP Server - Commit & Push"
echo "================================================"
echo ""

# Add all files except sensitive ones
echo "Adding files to git..."
git add .
git reset -- .env
git reset -- mcp-python-sdk/
echo "✓ Files added (excluding .env and mcp-python-sdk)"

# Show what will be committed
echo ""
echo "Files to be committed:"
git status --short | grep -E "^[AM]"
echo ""

# Create commit
echo "Creating commit..."
git commit -m "feat: Complete Firmia MCP Server implementation

- Implemented all phases: Foundation, Core APIs, Advanced APIs, Analytics
- Added 23 MCP tools for French company intelligence
- Integrated 8+ French government APIs
- Added health scoring, market analytics, and trend analysis
- Configured MCP SDK and created launch instructions
- Server tested and working with stdio transport

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"

echo "✓ Commit created"

# Show commit info
echo ""
echo "Latest commit:"
git log -1 --oneline
echo ""

echo "================================================"
echo "Ready to push! Run 'git push' when ready."
echo "================================================"