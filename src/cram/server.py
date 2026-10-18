"""Cram's MCP server."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Cram", host="0.0.0.0", port=8000)


@mcp.tool()
def hello() -> str:
    """Check that the Cram MCP server is available."""
    return "Cram is ready."


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()