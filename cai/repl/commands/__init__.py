"""
Command handlers for the CAI REPL.
This module contains all the command handlers for the CAI REPL.
"""

from cai.repl.commands.memory_commands import (
    handle_memory_list,
    handle_memory_delete,
    handle_memory_load,
    handle_memory_create
)

from cai.repl.commands.model_commands import (
    handle_model_command,
    handle_turns_command
)

from cai.repl.commands.help_commands import (
    handle_help,
    handle_help_memory,
    handle_help_aliases,
    handle_help_model,
    handle_help_turns
)

from cai.repl.commands.system_commands import (
    handle_shell_command,
    handle_kill_command,
    handle_env_command,
    handle_graph_show
)

from cai.repl.commands.platform_commands import (
    handle_platform_command
)

__all__ = [
    # Memory commands
    'handle_memory_list',
    'handle_memory_delete',
    'handle_memory_load',
    'handle_memory_create',
    
    # Model commands
    'handle_model_command',
    'handle_turns_command',
    
    # Help commands
    'handle_help',
    'handle_help_memory',
    'handle_help_aliases',
    'handle_help_model',
    'handle_help_turns',
    
    # System commands
    'handle_shell_command',
    'handle_kill_command',
    'handle_env_command',
    'handle_graph_show',
    
    # Platform commands
    'handle_platform_command'
] 