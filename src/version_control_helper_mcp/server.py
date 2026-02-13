"""MCP Server for code version control operations.

This server exposes git operations as MCP tools for use with
LangChain deepagents and other MCP-compatible clients.
"""

import os
import asyncio
import logging

from mcp.server.fastmcp import FastMCP
from .tools import register_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_server(default_repo_path: str | None = None) -> FastMCP:
    """Create and configure the MCP server.
    
    Args:
        default_repo_path: Default repository path for operations
        
    Returns:
        Configured FastMCP Server instance
    """
    mcp = FastMCP("version-control-helper-mcp")
    
    # Register all tools
    register_tools(mcp, default_repo_path=default_repo_path)
    
    logger.info("VersionControlHelperMCP Server initialized")
    if default_repo_path:
        logger.info(f"Default repo path: {default_repo_path}")
    
    return mcp


def run_server():
    """Run the MCP server with stdio transport."""
    # Get default repo path from environment
    default_repo = os.environ.get("REPO_PATH")
    
    mcp = create_server(default_repo_path=default_repo)
    
    logger.info("Starting VersionControlHelperMCP Server (stdio transport)...")
    mcp.run()


def main():
    """Main entry point for the MCP server."""
    run_server()


if __name__ == "__main__":
    main()
