#!/usr/bin/env python3
"""
Example:

CAI_MODEL="claude-sonnet-4-20250514" CAI_STREAM=True python3 case_study_generator.py --jsonl_file logs/cai_b97af8fc-3d51-45d3-8393-6c3341d33807_20250602_201144_luijait_darwin_24.5.0_81_38_189_27.jsonl --output_php_file alias_web/case_study_test.php      

CAI Case Study Generator - Generate PHP case studies from JSONL files.

This script loads context from JSONL files using the same mechanism as CAI's /load command,
runs the UseCase agent with streaming output, and generates PHP case studies.

Usage:
    python case_study_generator.py --jsonl_file logs/session.jsonl --output_php_file output.php
    python case_study_generator.py --jsonl_file logs/last --output_php_file case_studies/latest.php
"""
import os
from dotenv import load_dotenv
load_dotenv()

import sys
import asyncio
import argparse
from pathlib import Path
import json
import re
from typing import List, Dict, Any, Optional

# Import CAI SDK components
from cai.sdk.agents import Runner
from cai.sdk.agents.models.openai_chatcompletions import message_history, add_to_message_history
from cai.sdk.agents.run_to_jsonl import load_history_from_jsonl
from cai.sdk.agents.stream_events import RunItemStreamEvent
from cai.sdk.agents.items import ToolCallOutputItem

# Import UseCase agent
from src.cai.agents.usecase import use_case_agent

# Rich console for better output
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def extract_php_code(text: str) -> Optional[str]:
    """Extract PHP code from markdown code blocks."""
    if not text:
        return None
    
    # Try to extract PHP code between ```php and ```
    php_matches = re.findall(r'```php\n(.*?)```', text, re.DOTALL)
    if php_matches:
        return php_matches[0].strip()
    
    # If no code blocks, check if the entire text looks like PHP
    if text.strip().startswith('<?php') or text.strip().startswith('<!doctype'):
        return text.strip()
    
    return None


async def generate_case_study(jsonl_file: str, output_php_file: str) -> Optional[str]:
    """
    Generate a PHP case study from a JSONL file using streaming output.
    
    Args:
        jsonl_file: Path to the JSONL file to load context from
        output_php_file: Path to save the PHP output to
    
    Returns:
        Path to the saved PHP file or None if failed
    """
    # Clear any existing messages in message_history to start fresh
    message_history.clear()
    
    # Load context from JSONL file (simulating /load command)
    try:
        console.print(f"[yellow]Loading JSONL file: {jsonl_file}[/yellow]")
        messages = load_history_from_jsonl(jsonl_file)
        
        if not messages:
            console.print("[red]Error: No messages found in JSONL file[/red]")
            return None
            
        console.print(f"[green]✓ Loaded {len(messages)} messages from JSONL[/green]")
        
        # Add messages to message_history (exactly like /load command does)
        for message in messages:
            message_history.append(message)
            
        # Display loaded context summary
        user_messages = sum(1 for msg in messages if msg.get("role") == "user")
        assistant_messages = sum(1 for msg in messages if msg.get("role") == "assistant")
        tool_messages = sum(1 for msg in messages if msg.get("role") == "tool")
        
        console.print(Panel(
            f"Context loaded:\n"
            f"• User messages: {user_messages}\n"
            f"• Assistant messages: {assistant_messages}\n"
            f"• Tool messages: {tool_messages}",
            title="[bold]JSONL Context Summary[/bold]",
            border_style="blue"
        ))
        
    except Exception as e:
        console.print(f"[red]Error loading JSONL file: {str(e)}[/red]")
        return None
    
    # Analyze the loaded context to provide better guidance
    context_summary = []
    if messages:
        # Find the main topic/challenge from user messages
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                content = msg.get("content", "")[:300]  # First 300 chars
                if content and len(content) > 20:  # Skip very short messages
                    context_summary.append(content.strip())
                    if len(context_summary) >= 5:  # Get first few meaningful messages
                        break
    
    # Generate case study prompt with context
    prompt = "Generate the PHP code for a cybersecurity case study based on the template. "
    prompt += "Analyze the conversation context that has been loaded and create a comprehensive case study. "
    prompt += "Fill in all TEMPLATE-TODO sections with relevant information from the session. "
    prompt += "Explain step by step the problem and the solution in this scenario"
    prompt += "The output should be complete PHP code ready to save to a file."
    
    # Add a summary of the JSONL conversation to the prompt
    if messages:
        prompt += "\n\n## Conversation Context from JSONL:\n"
        
        # Get key information from the conversation
        user_msgs = [msg for msg in messages if msg.get("role") == "user"]
        assistant_msgs = [msg for msg in messages if msg.get("role") == "assistant"]
        tool_msgs = [msg for msg in messages if msg.get("role") == "tool"]
        
        # Add user messages
        if user_msgs:
            prompt += "\n### User Messages:\n"
            for i, msg in enumerate(user_msgs[:5], 1):
                content = msg.get("content", "")[:500]
                if content:
                    prompt += f"{i}. {content}\n"
        
        # Add key assistant responses
        if assistant_msgs:
            prompt += "\n### Key Assistant Responses:\n"
            for i, msg in enumerate(assistant_msgs[:3], 1):
                content = msg.get("content", "")[:500]
                if content and "I'll help" not in content:  # Skip generic responses
                    prompt += f"{i}. {content}\n"
        
        # Add tool outputs that might contain important data
        if tool_msgs:
            prompt += "\n### Tool Outputs (key findings):\n"
            important_tools = []
            for msg in tool_msgs:
                content = msg.get("content", "")
                # Look for important patterns in tool output
                if any(keyword in content.lower() for keyword in ["map", "credential", "password", "auth", "endpoint", "192.168", "http"]):
                    important_tools.append(content[:500])
            
            for i, content in enumerate(important_tools[:5], 1):
                prompt += f"{i}. {content}\n"
    
    console.print(f"\n[cyan]Generating case study with UseCase agent...[/cyan]")
    
    # Configure streaming mode based on environment variable
    stream_mode = os.getenv('CAI_STREAM', 'true').lower() != 'false'
    
    try:
        if stream_mode:
            # Streaming mode - similar to CLI implementation
            console.print("[dim]Using streaming mode...[/dim]")
            
            # Track if we've seen any output
            has_output = False
            accumulated_text = []
            php_code = None
            
            # Run the streaming process like CLI does
            async def process_streamed_response():
                try:
                    result_stream = Runner.run_streamed(use_case_agent, prompt)
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("[cyan]Processing with UseCase agent...", total=None)
                        
                        # Consume events so the async generator is executed
                        async for event in result_stream.stream_events():
                            if isinstance(event, RunItemStreamEvent):
                                # Handle tool outputs
                                if event.name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
                                    progress.update(task, description=f"[cyan]Tool: {event.item.raw_item.get('name', 'unknown')}...")
                                    
                                    # Add tool message to history (like CLI does)
                                    tool_msg = {
                                        "role": "tool",
                                        "tool_call_id": event.item.raw_item["call_id"],
                                        "content": event.item.output,
                                    }
                                    add_to_message_history(tool_msg)
                        
                        progress.update(task, description="[green]Finalizing output...")
                    
                    # The result is available after streaming completes
                    # But we need to extract the output from message_history
                    # since streaming doesn't provide direct access to final output
                    
                    # Get the last assistant message from message_history
                    for msg in reversed(message_history):
                        if msg.get("role") == "assistant" and msg.get("content"):
                            return msg.get("content")
                    
                    return None
                    
                except Exception as e:
                    console.print(f"[red]Error in streaming: {str(e)}[/red]")
                    import traceback
                    console.print(f"[red]{traceback.format_exc()}[/red]")
                    return None
            
            # Run the streaming process
            final_output = await process_streamed_response()
            
            if final_output:
                php_code = extract_php_code(final_output)
                if not php_code:
                    php_code = final_output
                
            if php_code:
                console.print(f"[green]✓ Generated {len(php_code)} characters of output[/green]")
            else:
                console.print("[red]Error: No output from UseCase agent[/red]")
                return None
                
        else:
            # Non-streaming mode (simpler, like in examples)
            console.print("[dim]Using non-streaming mode...[/dim]")
            
            # Show progress
            with console.status("[bold green]Generating case study...") as status:
                # Instead of passing the conversation history directly,
                # just use the prompt with all the context embedded in it
                # This avoids issues with incomplete tool call/response pairs
                
                # Run with just the prompt
                result = await Runner.run(use_case_agent, prompt)
            
            # Extract PHP code from result
            if hasattr(result, 'final_output') and result.final_output:
                output_text = result.final_output
                
                # Process the output to handle tool outputs
                for item in result.new_items:
                    if isinstance(item, ToolCallOutputItem):
                        # Add tool messages to history
                        tool_msg = {
                            "role": "tool", 
                            "tool_call_id": item.raw_item["call_id"],
                            "content": item.output,
                        }
                        add_to_message_history(tool_msg)
                
                php_code = extract_php_code(output_text)
                if not php_code:
                    # If extraction failed, use the raw output
                    php_code = output_text
                    
                console.print(f"[green]✓ Generated {len(php_code)} characters of output[/green]")
            else:
                console.print("[red]Error: No output from UseCase agent[/red]")
                return None
    
    except Exception as e:
        console.print(f"[red]Error generating case study: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        return None
    
    # Validate PHP code
    if not php_code or len(php_code) < 100:
        console.print("[red]Error: Generated output is too short or invalid[/red]")
        return None
    
    # Save PHP code to file
    try:
        output_path = Path(output_php_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(php_code)
        
        console.print(f"\n[green]✓ PHP case study saved to: {output_php_file}[/green]")
        
        # Display file size and preview
        file_size = output_path.stat().st_size
        console.print(f"[dim]File size: {file_size:,} bytes[/dim]")
        
        # Show first few lines as preview
        lines = php_code.split('\n')[:15]
        preview = '\n'.join(lines)
        if len(php_code.split('\n')) > 15:
            preview += '\n...'
        
        console.print(Panel(
            preview,
            title="[bold]PHP File Preview[/bold]",
            border_style="blue"
        ))
        
        return str(output_path)
        
    except Exception as e:
        console.print(f"[red]Error saving PHP file: {str(e)}[/red]")
        return None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate PHP case studies from JSONL files using CAI UseCase agent.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate case study from a specific JSONL file
  python case_study_generator.py --jsonl_file logs/session_20240102_123456.jsonl --output_php_file case_studies/ctf_writeup.php
  
  # Use the last session log (default behavior like /load command)
  python case_study_generator.py --jsonl_file logs/last --output_php_file case_studies/latest.php
  
  # Generate with custom output directory
  python case_study_generator.py --jsonl_file logs/last --output_php_file ~/Documents/case_studies/analysis.php
  
  # Override the model
  python case_study_generator.py --jsonl_file logs/last --output_php_file output.php --model gpt-4o
  
  # Disable streaming
  CAI_STREAM=false python case_study_generator.py --jsonl_file logs/last --output_php_file output.php
        """
    )
    parser.add_argument(
        '--jsonl_file',
        type=str,
        default='logs/last',
        help='Path to the JSONL file containing conversation context (default: logs/last)'
    )
    parser.add_argument(
        '--output_php_file',
        type=str,
        required=True,
        help='Path where the generated PHP file will be saved'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Override the model to use (e.g., claude-sonnet-4-20250514, gpt-4o)'
    )
    return parser.parse_args()


async def main():
    """Main entry point for the script."""
    args = parse_args()
    
    # Display banner
    console.print(Panel(
        "[bold cyan]CAI Case Study Generator[/bold cyan]\n"
        "Generate professional cybersecurity case studies from JSONL session logs\n\n"
        "[dim]This tool uses the CAI UseCase agent to analyze session context and generate\n"
        "comprehensive PHP case studies based on the conversation history.[/dim]",
        border_style="cyan"
    ))
    
    # Override model if specified
    if args.model:
        os.environ["CAI_MODEL"] = args.model
        console.print(f"[yellow]Using model override: {args.model}[/yellow]")
    
    current_model = os.getenv("CAI_MODEL", "alias0")
    console.print(f"[yellow]Model: {current_model}[/yellow]")
    
    # Check if JSONL file exists
    jsonl_path = Path(args.jsonl_file)
    if not jsonl_path.exists() and args.jsonl_file != "logs/last":
        console.print(f"[red]Error: JSONL file not found: {args.jsonl_file}[/red]")
        return 1
    
    # Generate the case study
    result = await generate_case_study(args.jsonl_file, args.output_php_file)
    
    if result:
        console.print("\n[bold green]✨ Case study generation completed successfully![/bold green]")
        console.print(f"[dim]You can now open {result} in your browser or editor[/dim]")
        return 0
    else:
        console.print("\n[bold red]❌ Case study generation failed[/bold red]")
        console.print("[dim]Please check the error messages above and ensure:[/dim]")
        console.print("[dim]1. The JSONL file contains valid session data[/dim]")
        console.print("[dim]2. The UseCase agent has access to the template file[/dim]")
        console.print("[dim]3. Your API keys are properly configured[/dim]")
        return 1


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)