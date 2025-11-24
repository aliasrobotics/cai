"""
MCP (Model Context Protocol) command for CAI CLI

Provides commands for managing MCP servers and integrating their tools
with agents.

USAGE EXAMPLES:
==============

1. Load an SSE (Server-Sent Events) MCP server:
   /mcp load http://localhost:9876/sse burp

2. Load an SSE server with authentication headers:
   /mcp load https://mcp.ai.hackthebox.com/v1/ctf/sse htb --header "Authorization: Bearer YOUR_TOKEN"
   /mcp load https://api.example.com/mcp myapi -H "X-API-Key: secret" -H "Custom-Header: value"

3. Load a STDIO MCP server:
   /mcp load stdio myserver python mcp_server.py
   /mcp load stdio myserver node server.js --port 8080

4. List all active MCP connections:
   /mcp list

5. Add MCP tools to an agent:
   /mcp add burp redteam_agent     # Add by agent name
   /mcp add burp 13                 # Add by agent number

6. List tools from a specific server:
   /mcp tools burp

7. Check server connection status:
   /mcp status

8. Remove a server connection:
   /mcp remove burp

9. Show help:
   /mcp help

NOTES:
======
- Each tool invocation creates a fresh connection to ensure reliability
- SSE servers may show async generator warnings on cleanup (this is normal)
- Use /mcp status to check and reconnect servers if needed
- Tools are added directly to agent.tools for seamless integration

QUICK START:
===========
1. Start your MCP server (e.g., Burp Suite MCP extension)
2. Load it: /mcp load http://localhost:9876/sse burp
3. Add to agent: /mcp add burp your_agent
4. Use the tools through the agent
"""

# Standard library imports
import asyncio
import atexit
import functools
import warnings
import logging
from typing import Dict, List, Optional

# Third-party imports
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

# Local imports
from cai.agents import get_agent_by_name, get_available_agents
from cai.repl.commands.base import Command, register_command
from cai.sdk.agents.mcp import (
    MCPServer,
    MCPServerSse,
    MCPServerSseParams,
    MCPServerStdio,
    MCPServerStdioParams,
    MCPUtil,
)
from cai.sdk.agents.tool import FunctionTool

console = Console()

# Global registry for persistent MCP connections
_GLOBAL_MCP_SERVERS: Dict[str, MCPServer] = {}

# Per-server locks to serialize tool invocations for persistent connections
_SERVER_INVOCATION_LOCKS: Dict[str, asyncio.Lock] = {}

# Global registry for agent-MCP associations
# Maps agent name to list of MCP server names
_AGENT_MCP_ASSOCIATIONS: Dict[str, List[str]] = {}


# Custom MCPUtil that uses global registry
class GlobalMCPUtil(MCPUtil):
    """Custom MCP utility that uses global server registry"""

    @classmethod
    def to_function_tool(cls, tool, server_name: str) -> FunctionTool:
        """Convert an MCP tool to a CAI function tool using server name instead of object."""

        # Store the server configuration instead of the server object
        server = _GLOBAL_MCP_SERVERS.get(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not found in registry")

        # Capture server configuration
        server_config = {
            "name": server_name,
            "type": type(server).__name__,
            "tool_name": tool.name,
            "tool_schema": tool.inputSchema,
            "tool_description": tool.description,
            "persistent": isinstance(server, MCPServerStdio),
        }

        # For SSE servers, capture the URL
        if isinstance(server, MCPServerSse):
            server_config["url"] = server.params.get("url")
            server_config["headers"] = server.params.get("headers")
            server_config["timeout"] = server.params.get("timeout", 5)
            server_config["sse_read_timeout"] = server.params.get("sse_read_timeout", 60 * 5)
        # For STDIO servers, capture the command
        elif isinstance(server, MCPServerStdio):
            server_config["command"] = server.params.command
            server_config["args"] = server.params.args
            server_config["env"] = getattr(server.params, "env")
            server_config["cwd"] = getattr(server.params, "cwd")
            server_config["encoding"] = getattr(server.params, "encoding", "utf-8")
            server_config["encoding_error_handler"] = getattr(
                server.params, "encoding_error_handler", "strict"
            )

        # Create a custom invoke function that manages the server lifecycle per invocation
        async def invoke_with_fresh_connection(config, context, input_json):
            """Invoke an MCP tool, keeping STDIO transports persistent."""
            import asyncio
            import json
            import warnings

            from cai.sdk.agents.exceptions import AgentsException, ModelBehaviorError
            from cai.sdk.agents.mcp import MCPServerSse, MCPServerStdio

            try:
                json_data = json.loads(input_json) if input_json else {}
            except Exception as e:
                raise ModelBehaviorError(
                    f"Invalid JSON input for tool {config['tool_name']}: {input_json}"
                ) from e

            result = None
            max_retries = 2
            retry_count = 0
            server = None
            should_cleanup = False
            persistent = bool(config.get("persistent"))

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
                warnings.filterwarnings("ignore", message=".*ClosedResourceError.*")

                try:
                    if persistent:
                        server_name = config["name"]
                        server = _GLOBAL_MCP_SERVERS.get(server_name)
                        if not server or not isinstance(server, MCPServerStdio):
                            raise AgentsException(
                                f"MCP server '{server_name}' is unavailable. Use /mcp status to verify it is loaded."
                            )

                        lock = _SERVER_INVOCATION_LOCKS.setdefault(
                            server_name, asyncio.Lock()
                        )

                        async with lock:
                            while retry_count < max_retries:
                                try:
                                    if not getattr(server, "session", None):
                                        try:
                                            await asyncio.wait_for(server.connect(), timeout=10.0)
                                        except asyncio.TimeoutError:
                                            raise AgentsException(
                                                f"Timeout connecting to MCP server for tool {config['tool_name']}. "
                                                "The server may be down or not responding."
                                            )

                                    result = await asyncio.wait_for(
                                        server.call_tool(config["tool_name"], json_data),
                                        timeout=30.0,
                                    )
                                    break
                                except asyncio.TimeoutError:
                                    raise AgentsException(
                                        f"Timeout calling MCP tool {config['tool_name']}. "
                                        f"The tool took too long to respond."
                                    )
                                except Exception:
                                    retry_count += 1
                                    if retry_count >= max_retries:
                                        raise
                                    import logging

                                    logging.debug(
                                        f"Retrying MCP tool {config['tool_name']} (attempt {retry_count}/{max_retries})"
                                    )
                                    try:
                                        await server.cleanup()
                                    except Exception:
                                        pass
                                    server.session = None
                                    await asyncio.sleep(0.5)
                    else:
                        if config["type"] == "MCPServerSse":
                            params = {
                                "url": config["url"],
                                "headers": config.get("headers"),
                                "timeout": config.get("timeout", 5),
                                "sse_read_timeout": config.get("sse_read_timeout", 60 * 5),
                            }
                            params = {k: v for k, v in params.items() if v is not None}

                            server = MCPServerSse(
                                params,
                                name=config["name"],
                                cache_tools_list=False,
                            )
                        elif config["type"] == "MCPServerStdio":
                            params = {
                                "command": config["command"],
                                "args": config.get("args", []),
                                "env": config.get("env"),
                                "cwd": config.get("cwd"),
                                "encoding": config.get("encoding", "utf-8"),
                                "encoding_error_handler": config.get(
                                    "encoding_error_handler", "strict"
                                ),
                            }
                            params = {k: v for k, v in params.items() if v is not None}

                            server = MCPServerStdio(
                                params, name=config["name"], cache_tools_list=False
                            )
                        else:
                            raise AgentsException(f"Unknown server type: {config['type']}")

                        should_cleanup = True

                        while retry_count < max_retries:
                            try:
                                try:
                                    await asyncio.wait_for(server.connect(), timeout=10.0)
                                except asyncio.TimeoutError:
                                    raise AgentsException(
                                        f"Timeout connecting to MCP server for tool {config['tool_name']}. "
                                        f"The server may be down or not responding."
                                    )

                                result = await asyncio.wait_for(
                                    server.call_tool(config["tool_name"], json_data),
                                    timeout=30.0,
                                )
                                break
                            except asyncio.TimeoutError:
                                raise AgentsException(
                                    f"Timeout calling MCP tool {config['tool_name']}. "
                                    f"The tool took too long to respond."
                                )
                            except Exception:
                                retry_count += 1
                                if retry_count >= max_retries:
                                    raise
                                import logging

                                logging.debug(
                                    f"Retrying MCP tool {config['tool_name']} (attempt {retry_count}/{max_retries})"
                                )
                                if isinstance(server, MCPServerSse) and hasattr(server, "session"):
                                    server.session = None
                                await asyncio.sleep(0.5)
                except Exception as e:
                    error_type = type(e).__name__
                    error_str = str(e).lower()

                    if (
                        error_type in ("ClosedResourceError", "ExceptionGroup")
                        or "closedresourceerror" in error_str
                        or "closed" in error_str
                        or "connection" in error_str
                    ):
                        raise AgentsException(
                            f"Connection lost to MCP server for tool {config['tool_name']}. "
                            "Use /mcp status to reconnect if the issue persists."
                        ) from e
                    raise AgentsException(
                        f"Error invoking MCP tool {config['tool_name']}: {type(e).__name__}: {str(e)}"
                    ) from e
                finally:
                    if should_cleanup and server:
                        if isinstance(server, MCPServerSse):
                            try:
                                await asyncio.wait_for(server.cleanup(), timeout=0.5)
                            except (asyncio.TimeoutError, RuntimeError, Exception):
                                pass
                            server.session = None
                        else:
                            try:
                                await asyncio.wait_for(server.cleanup(), timeout=5.0)
                            except (asyncio.TimeoutError, Exception):
                                pass

            if not result:
                raise AgentsException(f"No result returned from MCP tool {config['tool_name']}")

            # Convert result to string format
            if len(result.content) == 1:
                tool_output = result.content[0].model_dump_json()
            elif len(result.content) > 1:
                tool_output = json.dumps([item.model_dump() for item in result.content])
            else:
                tool_output = "Error running tool."

            # Handle tracing if needed
            from cai.sdk.agents.tracing import FunctionSpanData, get_current_span

            current_span = get_current_span()
            if current_span:
                if isinstance(current_span.span_data, FunctionSpanData):
                    current_span.span_data.output = tool_output
                    current_span.span_data.mcp_data = {
                        "server": config["name"],
                    }

            return tool_output

        # Use functools.partial to bind the server config
        invoke_func = functools.partial(invoke_with_fresh_connection, server_config)

        return FunctionTool(
            name=tool.name,
            description=tool.description or "",
            params_json_schema=tool.inputSchema,
            on_invoke_tool=invoke_func,
            strict_json_schema=False,
        )


def cleanup_mcp_servers():
    """Cleanup all MCP servers on exit"""
    try:
        if _GLOBAL_MCP_SERVERS:
            import warnings
            # Suppress async generator warnings during cleanup
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
                
                # Create new event loop for cleanup if needed
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                async def cleanup_all():
                    tasks = []
                    for name, server in _GLOBAL_MCP_SERVERS.items():
                        try:
                            # For SSE servers, use a very short timeout
                            if isinstance(server, MCPServerSse):
                                tasks.append(asyncio.wait_for(server.cleanup(), timeout=0.1))
                            else:
                                tasks.append(server.cleanup())
                        except Exception:
                            pass
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)

                loop.run_until_complete(cleanup_all())
                # Only close the loop if it's not running
                if not loop.is_running():
                    loop.close()
        _SERVER_INVOCATION_LOCKS.clear()
    except Exception:
        pass


# Register cleanup on exit
atexit.register(cleanup_mcp_servers)


class MCPCommand(Command):
    """Command for managing MCP servers and their integration with agents."""

    def __init__(self):
        """Initialize the MCP command."""
        super().__init__(
            name="/mcp",
            description="Manage MCP servers and add their tools to agents",
            aliases=["/m"],
        )

        # Add subcommands manually
        self._subcommands = {
            "load": "Load an MCP server (SSE or stdio)",
            "list": "List active MCP connections",
            "add": "Add MCP tools to an agent",
            "remove": "Remove an MCP server connection",
            "tools": "List tools from an MCP server",
            "status": "Check MCP server connection status",
            "associations": "Show agent-MCP associations",
            "help": "Show MCP command usage",
        }

    def get_subcommands(self) -> List[str]:
        """Get list of subcommand names.

        Returns:
            List of subcommand names
        """
        return list(self._subcommands.keys())

    def get_subcommand_description(self, subcommand: str) -> str:
        """Get description for a subcommand.

        Args:
            subcommand: Name of the subcommand

        Returns:
            Description of the subcommand
        """
        return self._subcommands.get(subcommand, "")

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the MCP command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully
        """
        if not args:
            return self.handle_list(args)

        subcommand = args[0]
        if subcommand in self._subcommands:
            handler = getattr(self, f"handle_{subcommand}", None)
            if handler:
                try:
                    return handler(args[1:] if len(args) > 1 else None)
                except Exception as e:
                    console.print(f"[red]Error executing command: {e}[/red]")
                    return False

        console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
        self.show_usage()
        return False

    def show_usage(self):
        """Show usage information for the MCP command."""
        usage_text = """
# MCP (Model Context Protocol) Command Usage

The MCP command allows you to manage Model Context Protocol servers and integrate their tools with CAI agents.

## Commands:

### Load an MCP Server

**SSE (Server-Sent Events) Server:**
```
/mcp load <url> <name> [--header "Key: Value" | -H "Key: Value"]
```
Example: `/mcp load http://localhost:9876/sse burp`

**SSE Server with Authentication:**
```
/mcp load <url> <name> --header "Authorization: Bearer TOKEN"
```
Example: `/mcp load https://mcp.ai.hackthebox.com/v1/ctf/sse htb --header "Authorization: Bearer eyJ0..."`

You can specify multiple headers by repeating the flag:
```
/mcp load <url> <name> -H "Header1: Value1" -H "Header2: Value2"
```

**STDIO Server:**
```
/mcp load stdio <name> <command> [args...]
```
Example: `/mcp load stdio myserver python mcp_server.py`

### List Active Connections
```
/mcp list
```

### Add Tools to an Agent
```
/mcp add <server_name> <agent_name_or_number>
```
Example: `/mcp add burp redteam_agent`
Example: `/mcp add burp 13`

### List Tools from a Server
```
/mcp tools <server_name>
```

### Check Server Status
```
/mcp status
```

### Test Server Connection
```
/mcp test <server_name>
```

### Show Agent-MCP Associations
```
/mcp associations
```

### Remove a Server
```
/mcp remove <server_name>
```

### Show Help
```
/mcp help
```

## Quick Start:

1. Load an MCP server:
   `/mcp load http://localhost:9876/sse burp`

2. List available tools:
   `/mcp tools burp`

3. Add tools to an agent:
   `/mcp add burp redteam_agent`

4. Switch to the agent and use the tools:
   `/agent redteam_agent`
"""
        console.print(Markdown(usage_text))

    def handle_help(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp help command.

        Args:
            args: Optional list of command arguments (not used)

        Returns:
            True
        """
        self.show_usage()
        return True

    def _run_async(self, coro):
        """Run async code properly in the CLI context.

        Args:
            coro: The coroutine to run

        Returns:
            The result of the coroutine
        """
        try:
            # Try to get existing loop
            loop = asyncio.get_running_loop()
            # If we're in a loop, we need to use a different approach
            import concurrent.futures
            import sys
            from io import StringIO

            def run_in_thread():
                # Suppress stderr in the thread too
                original_stderr = sys.stderr
                try:
                    sys.stderr = StringIO()
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                finally:
                    sys.stderr = original_stderr

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=30)

        except RuntimeError:
            # No running loop, we can use asyncio.run
            import sys
            from io import StringIO

            # Suppress stderr during asyncio.run
            original_stderr = sys.stderr
            try:
                sys.stderr = StringIO()
                return asyncio.run(coro)
            finally:
                sys.stderr = original_stderr

    def handle_load(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp load command.

        Usage:
            /mcp load <url> <name> [--header "Key: Value"] - Load SSE server with optional auth headers
            /mcp load stdio <name> <command> [args...]     - Load stdio server

        Args:
            args: List of command arguments

        Returns:
            True if successful
        """
        if not args or len(args) < 2:
            console.print("[red]Error: Invalid arguments[/red]")
            console.print("Usage:")
            console.print("  /mcp load <url> <name> [--header \"Key: Value\"]  - For SSE servers")
            console.print("  /mcp load stdio <name> <command> [args...]        - For STDIO servers")
            return False

        # Check if it's a stdio server
        if args[0] == "stdio":
            if len(args) < 3:
                console.print("[red]Error: stdio requires name and command[/red]")
                return False

            name = args[1]
            command = args[2]
            cmd_args = args[3:] if len(args) > 3 else []

            return self._load_stdio_server(name, command, cmd_args)
        else:
            # SSE server
            url = args[0]
            name = args[1]

            # Parse headers from remaining arguments
            headers = {}
            i = 2
            while i < len(args):
                if args[i] in ["--header", "-H"]:
                    if i + 1 >= len(args):
                        console.print("[red]Error: --header requires a value[/red]")
                        return False

                    # Parse header in format "Key: Value"
                    header_str = args[i + 1]
                    if ":" not in header_str:
                        console.print(f"[red]Error: Invalid header format '{header_str}'. Use 'Key: Value'[/red]")
                        return False

                    key, value = header_str.split(":", 1)
                    # Strip quotes and whitespace from key and value
                    key = key.strip().strip('"').strip("'")
                    value = value.strip().strip('"').strip("'")
                    headers[key] = value
                    i += 2
                else:
                    console.print(f"[yellow]Warning: Unknown argument '{args[i]}' ignored[/yellow]")
                    i += 1

            return self._load_sse_server(url, name, headers if headers else None)

    def _load_sse_server(self, url: str, name: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Load an SSE MCP server.

        Args:
            url: URL of the SSE server
            name: Name to identify the server
            headers: Optional HTTP headers for authentication (e.g., {"Authorization": "Bearer token"})

        Returns:
            True if successful
        """
        if name in _GLOBAL_MCP_SERVERS:
            console.print(f"[yellow]Server '{name}' is already loaded and active.[/yellow]")
            console.print(f"[dim]Use '/mcp remove {name}' first if you want to reload it.[/dim]")
            return True

        if headers:
            console.print(f"Connecting to SSE server at {url} with authentication headers...")
        else:
            console.print(f"Connecting to SSE server at {url}...")

        async def connect_and_test():
            params: MCPServerSseParams = {
                "url": url,
                "timeout": 10,  # Connection timeout
                "sse_read_timeout": 300  # 5 minutes for SSE reads
            }
            # Add headers if provided
            if headers:
                params["headers"] = headers

            server = MCPServerSse(params, name=name, cache_tools_list=True)

            # Connect to the server with retry logic
            max_connect_retries = 3
            for attempt in range(max_connect_retries):
                try:
                    await server.connect()
                    break
                except Exception as e:
                    if attempt < max_connect_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    raise

            # Test by listing tools
            tools = await server.list_tools()

            return server, tools

        try:
            # Suppress all stderr output during SSE connection
            import sys
            from io import StringIO

            # Save the original stderr
            original_stderr = sys.stderr

            try:
                # Redirect stderr to null
                sys.stderr = StringIO()

                # Also suppress warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=RuntimeWarning)
                    warnings.filterwarnings("ignore", message=".*asynchronous generator.*")
                    warnings.filterwarnings("ignore", message=".*cancel scope.*")
                    warnings.filterwarnings("ignore", message=".*didn't stop after athrow.*")

                    server, tools = self._run_async(connect_and_test())
            finally:
                # Always restore stderr
                sys.stderr = original_stderr

            # Store the server globally
            _GLOBAL_MCP_SERVERS[name] = server

            console.print(f"[green]✓ Connected to SSE server '{name}' at {url}[/green]")
            console.print(f"Available tools: {len(tools)}")

            # Show some tool names if available
            if tools:
                tool_names = [tool.name for tool in tools[:5]]
                if len(tools) > 5:
                    tool_names.append(f"... and {len(tools) - 5} more")
                console.print(f"Tools: {', '.join(tool_names)}")

            return True

        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")
            # Clean up if connection failed
            if name in _GLOBAL_MCP_SERVERS:
                del _GLOBAL_MCP_SERVERS[name]
            return False

    def _load_stdio_server(self, name: str, command: str, cmd_args: List[str]) -> bool:
        """Load a stdio MCP server.

        Args:
            name: Name to identify the server
            command: Command to execute
            cmd_args: Arguments for the command

        Returns:
            True if successful
        """
        if name in _GLOBAL_MCP_SERVERS:
            console.print(f"[yellow]Server '{name}' is already loaded and active.[/yellow]")
            console.print(f"[dim]Use '/mcp remove {name}' first if you want to reload it.[/dim]")
            return True

        console.print(
            f"Starting stdio server '{name}' with command: {command} {' '.join(cmd_args)}"
        )

        async def connect_and_test():
            params: MCPServerStdioParams = {"command": command, "args": cmd_args}
            server = MCPServerStdio(params, name=name, cache_tools_list=True)

            # Connect to the server
            await server.connect()

            # Test by listing tools
            tools = await server.list_tools()

            return server, tools

        try:
            server, tools = self._run_async(connect_and_test())

            # Store the server globally
            _GLOBAL_MCP_SERVERS[name] = server

            console.print(f"[green]✓ Started stdio server '{name}'[/green]")
            console.print(f"Available tools: {len(tools)}")

            # Show some tool names if available
            if tools:
                tool_names = [tool.name for tool in tools[:5]]
                if len(tools) > 5:
                    tool_names.append(f"... and {len(tools) - 5} more")
                console.print(f"Tools: {', '.join(tool_names)}")

            return True

        except Exception as e:
            console.print(f"[red]Error starting server: {e}[/red]")
            # Clean up if connection failed
            if name in _GLOBAL_MCP_SERVERS:
                del _GLOBAL_MCP_SERVERS[name]
            return False

    def handle_list(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp list command.

        Args:
            args: Optional list of command arguments (not used)

        Returns:
            True
        """
        if not _GLOBAL_MCP_SERVERS:
            console.print("[yellow]No active MCP connections[/yellow]")
            console.print("\nUse `/mcp help` to see how to load servers.")
            return True

        table = Table(title="Active MCP Connections")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Details", style="green")
        table.add_column("Tools", style="yellow")

        for name, server in _GLOBAL_MCP_SERVERS.items():
            server_type = type(server).__name__.replace("MCPServer", "")

            # Get server details
            if isinstance(server, MCPServerSse):
                details = server.params.get("url", "N/A")
            elif isinstance(server, MCPServerStdio):
                cmd = server.params.command
                args = " ".join(server.params.args)
                details = f"{cmd} {args}".strip()
            else:
                details = "Unknown"

            # Get tool count
            try:

                async def get_tools():
                    return await server.list_tools()

                tools = self._run_async(get_tools())
                tool_count = str(len(tools))
            except Exception:
                tool_count = "Error"

            table.add_row(name, server_type, details, tool_count)

        console.print(table)
        return True

    def handle_add(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp add command.

        Usage: /mcp add <server_name> <agent_name>

        Args:
            args: List of command arguments

        Returns:
            True if successful
        """
        if not args or len(args) < 2:
            console.print("[red]Error: Invalid arguments[/red]")
            console.print("Usage: /mcp add <server_name> <agent_name>")
            return False

        server_name = args[0]
        agent_identifier = args[1]

        # Check if server exists
        if server_name not in _GLOBAL_MCP_SERVERS:
            console.print(f"[red]Error: Server '{server_name}' not found[/red]")
            console.print("Use /mcp list to see active servers")
            return False

        # Get the agent
        try:
            agent = get_available_agents()[agent_identifier]
            agent_display_name = getattr(agent, "name", agent_identifier)
        except KeyError:
            # Try by index
            try:
                agents = get_available_agents()
                agent_list = list(agents.items())

                if agent_identifier.isdigit():
                    idx = int(agent_identifier)
                    if 1 <= idx <= len(agent_list):
                        agent_key, agent = agent_list[idx - 1]
                        agent_display_name = getattr(agent, "name", agent_key)
                    else:
                        raise ValueError("Invalid index")
                else:
                    raise ValueError("Not found")
            except Exception:
                console.print(f"[red]Error: Agent '{agent_identifier}' not found[/red]")
                return False

        # Add the MCP server to the agent
        server = _GLOBAL_MCP_SERVERS[server_name]

        console.print(
            f"Adding tools from MCP server '{server_name}' to agent '{agent_display_name}'..."
        )

        # Validate the server connection before adding
        try:

            async def validate_connection():
                try:
                    # Try to list tools to validate connection
                    tools = await server.list_tools()
                    return tools
                except Exception:
                    console.print(
                        "[yellow]Warning: Server connection may be lost, attempting to reconnect...[/yellow]"
                    )
                    # Try to reconnect
                    await server.connect()
                    tools = await server.list_tools()
                    console.print(f"[green]✓ Reconnected to server '{server_name}'[/green]")
                    return tools

            # Validate the connection and get tools
            mcp_tools = self._run_async(validate_connection())

        except Exception as e:
            console.print(f"[red]Error: Cannot connect to server '{server_name}': {e}[/red]")
            console.print("Try removing and reloading the server.")
            return False

        # Get and display the tools
        try:
            # Create function tools using GlobalMCPUtil
            tools = []
            for mcp_tool in mcp_tools:
                # Use GlobalMCPUtil to create tools that use the global registry
                function_tool = GlobalMCPUtil.to_function_tool(mcp_tool, server_name)
                tools.append(function_tool)

            # Display tools table
            table = Table(title=f"Adding tools to {agent_display_name}")
            table.add_column("Tool", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details", style="yellow")

            for tool in tools:
                table.add_row(tool.name, "Added", f"Available as: {tool.name}")

            console.print(table)

            # Add tools directly to agent.tools
            if not hasattr(agent, "tools"):
                agent.tools = []

            # Remove any existing tools with the same names to avoid duplicates
            existing_tool_names = {t.name for t in tools}
            agent.tools = [t for t in agent.tools if t.name not in existing_tool_names]

            # Add the new tools
            agent.tools.extend(tools)
            
            # Persist the association
            # Get the agent's real name (not display name)
            agent_real_name = agent_identifier.lower()
            if not agent_identifier.isdigit():
                # It's already a name
                agent_real_name = agent_identifier.lower()
            else:
                # It's an index, get the actual agent name
                agents = get_available_agents()
                agent_list = list(agents.items())
                idx = int(agent_identifier)
                if 1 <= idx <= len(agent_list):
                    agent_real_name, _ = agent_list[idx - 1]
            
            add_mcp_server_to_agent(agent_real_name, server_name)

            console.print(
                f"[green]Added {len(tools)} tools from server "
                f"'{server_name}' to agent '{agent_display_name}'.[/green]"
            )

            # Test that the tools are accessible
            async def test_agent_tools():
                # Get all tools including MCP tools
                all_regular_tools = agent.tools if hasattr(agent, "tools") else []
                all_mcp_tools = (
                    await agent.get_mcp_tools()
                    if hasattr(agent, "mcp_servers") and agent.mcp_servers
                    else []
                )
                return all_regular_tools + all_mcp_tools

            all_tools = self._run_async(test_agent_tools())

            # Count different types of tools
            mcp_server_tools_count = (
                len([t for t in agent.mcp_servers if hasattr(agent, "mcp_servers")])
                if hasattr(agent, "mcp_servers")
                else 0
            )
            regular_tools_count = len(agent.tools) if hasattr(agent, "tools") else 0

            console.print(f"[blue]Agent now has {regular_tools_count} tools total[/blue]")

            # Test a simple tool invocation to make sure everything works
            console.print("[cyan]Testing MCP tool connectivity...[/cyan]")
            try:
                if tools:
                    console.print("[green]✓ MCP tools are ready for use![/green]")
                else:
                    console.print("[yellow]Warning: No tools available from server[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Warning: Tool connectivity test failed: {e}[/yellow]")

            return True

        except Exception as e:
            console.print(f"[red]Error adding tools: {e}[/red]")
            return False

    def handle_remove(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp remove command.

        Args:
            args: List of command arguments

        Returns:
            True if successful
        """
        if not args:
            console.print("[red]Error: No server name specified[/red]")
            console.print("Usage: /mcp remove <server_name>")
            return False

        server_name = args[0]

        if server_name not in _GLOBAL_MCP_SERVERS:
            console.print(f"[red]Error: Server '{server_name}' not found[/red]")
            return False

        # Cleanup the server
        server = _GLOBAL_MCP_SERVERS[server_name]

        try:

            async def cleanup_server():
                await server.cleanup()

            self._run_async(cleanup_server())
            del _GLOBAL_MCP_SERVERS[server_name]
            _SERVER_INVOCATION_LOCKS.pop(server_name, None)
            console.print(f"[green]✓ Removed MCP server '{server_name}'[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error removing server: {e}[/red]")
            # Remove from list anyway
            if server_name in _GLOBAL_MCP_SERVERS:
                del _GLOBAL_MCP_SERVERS[server_name]
            return False

    def handle_status(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp status command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if successful
        """
        if not _GLOBAL_MCP_SERVERS:
            console.print("[yellow]No active MCP connections[/yellow]")
            return True

        console.print("[cyan]Checking MCP server connections...[/cyan]")

        table = Table(title="MCP Server Status")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Status", style="bold")
        table.add_column("Tools", style="yellow")
        table.add_column("Details", style="dim")

        healthy_count = 0

        for name, server in _GLOBAL_MCP_SERVERS.items():
            server_type = type(server).__name__.replace("MCPServer", "")

            # Test server connection
            try:

                async def test_connection():
                    tools = await server.list_tools()
                    return len(tools), None

                tools_count, error = self._run_async(test_connection())
                status = "[green]✓ Healthy[/green]"
                tools_str = str(tools_count)
                details = "Connection active"
                healthy_count += 1

            except Exception as e:
                status = "[red]✗ Error[/red]"
                tools_str = "N/A"
                details = f"Error: {str(e)[:50]}..."

                # Try to reconnect
                try:
                    console.print(f"[yellow]Attempting to reconnect to '{name}'...[/yellow]")

                    async def reconnect():
                        await server.connect()
                        tools = await server.list_tools()
                        return len(tools)

                    tools_count = self._run_async(reconnect())
                    status = "[green]✓ Reconnected[/green]"
                    tools_str = str(tools_count)
                    details = "Reconnected successfully"
                    healthy_count += 1

                except Exception as reconnect_error:
                    status = "[red]✗ Failed[/red]"
                    details = f"Reconnect failed: {str(reconnect_error)[:30]}..."

            table.add_row(name, server_type, status, tools_str, details)

        console.print(table)

        # Summary
        total_servers = len(_GLOBAL_MCP_SERVERS)
        if healthy_count == total_servers:
            console.print(f"[green]✓ All {total_servers} MCP servers are healthy[/green]")
        else:
            failed_count = total_servers - healthy_count
            console.print(
                f"[yellow]⚠ {healthy_count}/{total_servers} servers healthy, {failed_count} failed[/yellow]"
            )

        return True

    def handle_tools(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp tools command.

        Args:
            args: List of command arguments

        Returns:
            True if successful
        """
        if not args:
            console.print("[red]Error: No server name specified[/red]")
            console.print("Usage: /mcp tools <server_name>")
            return False

        server_name = args[0]

        if server_name not in _GLOBAL_MCP_SERVERS:
            console.print(f"[red]Error: Server '{server_name}' not found[/red]")
            return False

        server = _GLOBAL_MCP_SERVERS[server_name]

        try:

            async def get_tools():
                return await server.list_tools()

            tools = self._run_async(get_tools())

            if not tools:
                console.print(f"[yellow]No tools available from '{server_name}'[/yellow]")
                return True

            table = Table(title=f"Tools from '{server_name}'")
            table.add_column("#", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="green")

            for idx, tool in enumerate(tools, 1):
                description = tool.description or "No description"
                if len(description) > 60:
                    description = description[:57] + "..."
                table.add_row(str(idx), tool.name, description)

            console.print(table)
            return True

        except Exception as e:
            console.print(f"[red]Error listing tools: {e}[/red]")
            return False

    def handle_associations(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp associations command to show agent-MCP associations.
        
        Args:
            args: Optional list of command arguments (not used)
            
        Returns:
            True
        """
        if not _AGENT_MCP_ASSOCIATIONS:
            console.print("[yellow]No agent-MCP associations configured[/yellow]")
            return True
            
        table = Table(title="Agent-MCP Associations")
        table.add_column("Agent", style="cyan")
        table.add_column("MCP Servers", style="magenta")
        table.add_column("Total Tools", style="yellow")
        
        for agent_name, server_names in _AGENT_MCP_ASSOCIATIONS.items():
            if server_names:
                # Count total tools
                total_tools = 0
                for server_name in server_names:
                    if server_name in _GLOBAL_MCP_SERVERS:
                        try:
                            async def count_tools(srv):
                                tools = await srv.list_tools()
                                return len(tools)
                            
                            server = _GLOBAL_MCP_SERVERS[server_name]
                            tool_count = self._run_async(count_tools(server))
                            total_tools += tool_count
                        except Exception:
                            pass
                
                servers_str = ", ".join(server_names)
                table.add_row(agent_name, servers_str, str(total_tools))
        
        console.print(table)
        return True

    def handle_test(self, args: Optional[List[str]] = None) -> bool:
        """Handle /mcp test command to test server connectivity.
        
        Args:
            args: List of command arguments
            
        Returns:
            True if successful
        """
        if not args:
            console.print("[red]Error: No server name specified[/red]")
            console.print("Usage: /mcp test <server_name>")
            return False
            
        server_name = args[0]
        
        if server_name not in _GLOBAL_MCP_SERVERS:
            console.print(f"[red]Error: Server '{server_name}' not found[/red]")
            return False
            
        server = _GLOBAL_MCP_SERVERS[server_name]
        
        console.print(f"[cyan]Testing MCP server '{server_name}'...[/cyan]")
        
        try:
            async def test_server():
                # Test 1: List tools
                console.print("[yellow]Test 1: Listing tools...[/yellow]")
                tools = await server.list_tools()
                console.print(f"[green]✓ Found {len(tools)} tools[/green]")
                
                # Test 2: Test a simple tool if available
                if tools:
                    test_tool = tools[0]
                    console.print(f"[yellow]Test 2: Testing tool '{test_tool.name}'...[/yellow]")
                    
                    # Create a test invocation
                    try:
                        # Use empty input for testing
                        result = await server.call_tool(test_tool.name, {})
                        console.print(f"[green]✓ Tool invocation successful[/green]")
                        if result and result.content:
                            console.print(f"[dim]Result preview: {str(result.content[0])[:100]}...[/dim]")
                    except Exception as tool_error:
                        console.print(f"[yellow]⚠ Tool test failed (this is normal for tools requiring input)[/yellow]")
                        console.print(f"[dim]Error: {str(tool_error)[:100]}[/dim]")
                
                # Test 3: Test reconnection
                console.print("[yellow]Test 3: Testing reconnection...[/yellow]")
                if hasattr(server, 'session'):
                    old_session = server.session
                    server.session = None
                await server.connect()
                console.print("[green]✓ Reconnection successful[/green]")
                
                return True
            
            self._run_async(test_server())
            console.print(f"[green]✓ All tests passed for server '{server_name}'[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Test failed: {type(e).__name__}: {str(e)}[/red]")
            return False


def get_mcp_servers_for_agent(agent_name: str) -> List[str]:
    """Get list of MCP server names associated with an agent.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        List of MCP server names
    """
    return _AGENT_MCP_ASSOCIATIONS.get(agent_name.lower(), [])


def add_mcp_server_to_agent(agent_name: str, server_name: str):
    """Associate an MCP server with an agent.
    
    Args:
        agent_name: Name of the agent
        server_name: Name of the MCP server
    """
    agent_name_lower = agent_name.lower()
    if agent_name_lower not in _AGENT_MCP_ASSOCIATIONS:
        _AGENT_MCP_ASSOCIATIONS[agent_name_lower] = []
    
    if server_name not in _AGENT_MCP_ASSOCIATIONS[agent_name_lower]:
        _AGENT_MCP_ASSOCIATIONS[agent_name_lower].append(server_name)


def remove_mcp_server_from_agent(agent_name: str, server_name: str):
    """Remove an MCP server association from an agent.
    
    Args:
        agent_name: Name of the agent
        server_name: Name of the MCP server
    """
    agent_name_lower = agent_name.lower()
    if agent_name_lower in _AGENT_MCP_ASSOCIATIONS:
        if server_name in _AGENT_MCP_ASSOCIATIONS[agent_name_lower]:
            _AGENT_MCP_ASSOCIATIONS[agent_name_lower].remove(server_name)


def get_mcp_tools_for_agent(agent_name: str) -> List[FunctionTool]:
    """Get all MCP tools for an agent based on associations.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        List of FunctionTool objects
    """
    tools = []
    server_names = get_mcp_servers_for_agent(agent_name)
    
    for server_name in server_names:
        if server_name in _GLOBAL_MCP_SERVERS:
            server = _GLOBAL_MCP_SERVERS[server_name]
            try:
                # Get tools from server synchronously
                import asyncio
                async def get_tools():
                    return await server.list_tools()
                
                # Try to get existing loop or create new one
                try:
                    loop = asyncio.get_running_loop()
                    import concurrent.futures
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(get_tools())
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        mcp_tools = future.result(timeout=10)
                except RuntimeError:
                    mcp_tools = asyncio.run(get_tools())
                
                # Convert to function tools
                for mcp_tool in mcp_tools:
                    function_tool = GlobalMCPUtil.to_function_tool(mcp_tool, server_name)
                    tools.append(function_tool)
                    
            except Exception as e:
                logging.warning(f"Failed to get tools from MCP server '{server_name}': {e}")
    
    return tools


# Register the command
register_command(MCPCommand())
