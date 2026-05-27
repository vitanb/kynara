"""
Demo MCP Server — a simple upstream MCP server for testing the Tier 1 wrapper.

Has 4 tools:
  - get_weather(city)         → safe, always allowed
  - read_document(path)       → safe, always allowed
  - send_email(to, subject)   → DENIED by mock sidecar
  - delete_file(path)         → DENIED by mock sidecar

Usage:
  python tests/demo_mcp_server.py
  # Runs on http://localhost:8000/sse
"""
import sys

import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="demo-tools",
    host="127.0.0.1",
    port=8000,
    instructions="Demo tool server for Kynara Tier 1 testing.",
)


@mcp.tool()
def get_weather(city: str):
    """Get current weather for a city."""
    # Fake data — real integration would call a weather API
    # No return type annotation: prevents FastMCP from generating an outputSchema
    # that newer MCP SDK clients validate as structured JSON instead of TextContent.
    weather = {
        "London": "12°C, cloudy",
        "New York": "22°C, sunny",
        "Tokyo": "28°C, humid",
    }
    return weather.get(city, f"Weather for {city}: 18°C, partly cloudy")


@mcp.tool()
def read_document(path: str):
    """Read a document from the filesystem."""
    return f"[Document content from {path}]\nThis is sample content for testing Kynara enforcement."


@mcp.tool()
def send_email(to: str, subject: str, body: str = ""):
    """Send an email to a recipient. (BLOCKED by Kynara in test config)"""
    return f"Email sent to {to} with subject '{subject}'"


@mcp.tool()
def delete_file(path: str):
    """Permanently delete a file. (BLOCKED by Kynara in test config)"""
    return f"File {path} deleted"


if __name__ == "__main__":
    print("\n🔧 Demo MCP Server running on http://localhost:8000/sse")
    print("   Tools: get_weather, read_document, send_email*, delete_file*")
    print("   (* = blocked by Kynara mock policy)\n")
    mcp.run(transport="sse")
