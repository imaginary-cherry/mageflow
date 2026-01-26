"""MageFlow MCP Server implementation."""

import asyncio
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

from mageflow.mcp.resources import get_workflow_guide
from mageflow.mcp import tools


def create_mcp_server() -> Server:
    """Create and configure the MageFlow MCP server."""
    server = Server("mageflow")

    @server.list_resources()
    async def list_resources():
        """List available resources."""
        return [
            Resource(
                uri="mageflow://workflow-guide",
                name="MageFlow Workflow Guide",
                description="Comprehensive guide explaining task types, statuses, lifecycle, and how to interpret task state",
                mimeType="text/markdown",
            )
        ]

    @server.read_resource()
    async def read_resource(uri: str):
        """Read a resource by URI."""
        if uri == "mageflow://workflow-guide":
            return get_workflow_guide()
        raise ValueError(f"Unknown resource: {uri}")

    @server.list_tools()
    async def list_tools():
        """List available tools."""
        return [
            Tool(
                name="get_task",
                description="Get complete task information by ID. Returns task type, name, status, kwargs, callbacks count, and other metadata.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The task identifier (e.g., 'TaskSignature:abc123...')",
                        },
                    },
                    "required": ["task_id"],
                },
            ),
            Tool(
                name="get_task_callbacks",
                description="Get success and/or error callbacks of a task. Returns detailed callback task information.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The task identifier",
                        },
                        "include_success": {
                            "type": "boolean",
                            "description": "Whether to include success callbacks (default: true)",
                            "default": True,
                        },
                        "include_error": {
                            "type": "boolean",
                            "description": "Whether to include error callbacks (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["task_id"],
                },
            ),
            Tool(
                name="get_task_graph",
                description="Get the full task graph recursively. Shows children (for chains/swarms) and callback relationships.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The root task identifier",
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum recursion depth (default: 5)",
                            "default": 5,
                        },
                        "include_callbacks": {
                            "type": "boolean",
                            "description": "Whether to include callback graphs (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["task_id"],
                },
            ),
            Tool(
                name="get_chain_tasks",
                description="Get subtasks of a chain with pagination. Use this when a chain has many tasks.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chain_id": {
                            "type": "string",
                            "description": "The chain task identifier",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting position, 0-indexed (default: 0)",
                            "default": 0,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tasks to return (default: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["chain_id"],
                },
            ),
            Tool(
                name="get_chain_status",
                description="Get chain execution status summary. Shows current task, progress, and completion counts.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chain_id": {
                            "type": "string",
                            "description": "The chain task identifier",
                        },
                    },
                    "required": ["chain_id"],
                },
            ),
            Tool(
                name="get_swarm_tasks",
                description="Get subtasks of a swarm with pagination. Can filter by status (pending, completed, failed).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "swarm_id": {
                            "type": "string",
                            "description": "The swarm task identifier",
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting position, 0-indexed (default: 0)",
                            "default": 0,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tasks to return (default: 20)",
                            "default": 20,
                        },
                        "filter_status": {
                            "type": "string",
                            "description": "Optional status filter: 'pending', 'completed', or 'failed'",
                            "enum": ["pending", "completed", "failed"],
                        },
                    },
                    "required": ["swarm_id"],
                },
            ),
            Tool(
                name="get_swarm_status",
                description="Get swarm execution status summary. Shows running, completed, failed, pending counts and configuration.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "swarm_id": {
                            "type": "string",
                            "description": "The swarm task identifier",
                        },
                    },
                    "required": ["swarm_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        try:
            if name == "get_task":
                result = await tools.get_task(arguments["task_id"])
                if result is None:
                    return [TextContent(type="text", text="Task not found")]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_task_callbacks":
                result = await tools.get_task_callbacks(
                    task_id=arguments["task_id"],
                    include_success=arguments.get("include_success", True),
                    include_error=arguments.get("include_error", True),
                )
                if result is None:
                    return [TextContent(type="text", text="Task not found")]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_task_graph":
                result = await tools.get_task_graph(
                    task_id=arguments["task_id"],
                    max_depth=arguments.get("max_depth", 5),
                    include_callbacks=arguments.get("include_callbacks", True),
                )
                if result is None:
                    return [TextContent(type="text", text="Task not found")]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_chain_tasks":
                result = await tools.get_chain_tasks(
                    chain_id=arguments["chain_id"],
                    offset=arguments.get("offset", 0),
                    limit=arguments.get("limit", 20),
                )
                if result is None:
                    return [
                        TextContent(
                            type="text", text="Chain not found or task is not a chain"
                        )
                    ]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_chain_status":
                result = await tools.get_chain_status(arguments["chain_id"])
                if result is None:
                    return [
                        TextContent(
                            type="text", text="Chain not found or task is not a chain"
                        )
                    ]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_swarm_tasks":
                result = await tools.get_swarm_tasks(
                    swarm_id=arguments["swarm_id"],
                    offset=arguments.get("offset", 0),
                    limit=arguments.get("limit", 20),
                    filter_status=arguments.get("filter_status"),
                )
                if result is None:
                    return [
                        TextContent(
                            type="text", text="Swarm not found or task is not a swarm"
                        )
                    ]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            elif name == "get_swarm_status":
                result = await tools.get_swarm_status(arguments["swarm_id"])
                if result is None:
                    return [
                        TextContent(
                            type="text", text="Swarm not found or task is not a swarm"
                        )
                    ]
                return [TextContent(type="text", text=result.model_dump_json(indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def run_mcp_server():
    """Run the MCP server using stdio transport."""
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
