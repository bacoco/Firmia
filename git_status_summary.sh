#!/bin/bash

# Git Status Summary for Firmia MCP Server

echo "================================================"
echo "        Firmia MCP Server - Git Status"
echo "================================================"
echo ""

# Show current branch
echo "Current branch: $(git branch --show-current)"
echo ""

# Show modified files
echo "Modified files:"
git diff --name-only
echo ""

# Show untracked files
echo "New files to add:"
git ls-files --others --exclude-standard | grep -v "__pycache__" | grep -v ".pyc" | grep -v ".venv/" | grep -v "mcp-python-sdk/.git"
echo ""

# Suggested git commands
echo "================================================"
echo "Suggested git commands:"
echo ""
echo "# Add all changes except sensitive files:"
echo "git add ."
echo "git reset -- .env"
echo "git reset -- mcp-python-sdk/"  
echo ""
echo "# Create commit:"
echo 'git commit -m "feat: Complete Firmia MCP Server implementation

- Implemented all phases: Foundation, Core APIs, Advanced APIs, Analytics
- Added 23 MCP tools for French company intelligence
- Integrated 8+ French government APIs
- Added health scoring, market analytics, and trend analysis
- Configured MCP SDK and created launch instructions
- Server tested and working with stdio transport

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"'
echo ""
echo "# Push to remote:"
echo "git push"
echo ""
echo "================================================"