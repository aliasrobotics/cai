"""
Module for handling continuous agent execution with automatic continuation prompts.

Uses CAIConfig singleton for model/key configuration instead of os.getenv() calls [S].
"""

import logging
import os
import asyncio
from typing import List, Dict, Any, Optional
from rich.console import Console

from cai.config import get_config
from cai.sdk.agents.models.chatcompletions.litellm_adapter import acompletion_with_timeout

logger = logging.getLogger(__name__)


async def generate_continuation_advice(
    agent_name: str,
    message_history: List[Dict[str, Any]],
    console: Optional[Console] = None
) -> str:
    """
    Generate intelligent continuation advice based on the current conversation context
    using the model to analyze the situation and provide contextual advice.
    
    Args:
        agent_name: Name of the current agent
        message_history: List of previous messages in the conversation
        console: Optional Rich console for output
    
    Returns:
        A continuation prompt string to keep the agent working
    """
    # Get the model from CAIConfig singleton [S]
    cfg = get_config()
    model_name = cfg.model
    
    # Check if we should use a fallback model for local testing [S]
    # This allows the continuation feature to work even without alias1 credentials
    fallback = cfg.continuation_fallback_model
    if model_name == "alias1" and fallback:
        model_name = fallback
    
    # Find the original user request (first user message)
    original_request = None
    for msg in message_history:
        if msg.get("role") == "user" and msg.get("content"):
            original_request = msg.get("content")
            break
    
    # Get recent context for analysis (last 10 messages)
    recent_messages = message_history[-10:] if len(message_history) > 10 else message_history
    
    # Analyze recent activity
    last_assistant_message = None
    last_tool_output = None
    recent_tool_calls = []
    errors_found = []
    
    for msg in reversed(recent_messages):
        role = msg.get("role", "")
        
        if role == "assistant" and last_assistant_message is None:
            last_assistant_message = msg.get("content", "")
            if msg.get("tool_calls"):
                for tc in msg.get("tool_calls", []):
                    if "function" in tc:
                        recent_tool_calls.append(tc["function"].get("name", "unknown"))
                
        elif role == "tool" and last_tool_output is None:
            last_tool_output = msg.get("content", "")
            # Check for errors in tool output
            if "error" in str(last_tool_output).lower():
                errors_found.append(last_tool_output)
    
    # Build a more detailed context for better continuation advice
    # Include more message history for context
    conversation_summary = []
    for msg in recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and content:
            conversation_summary.append(f"User: {content[:100]}..." if len(content) > 100 else f"User: {content}")
        elif role == "assistant" and content:
            conversation_summary.append(f"Agent: {content[:100]}..." if len(content) > 100 else f"Agent: {content}")
        elif role == "tool":
            conversation_summary.append(f"Tool Output: {content[:50]}..." if len(content) > 50 else f"Tool Output: {content}")
    
    context_summary = f"""You are an AI assistant helping a cybersecurity agent continue its work. Based on the conversation history, generate a specific continuation prompt.

ORIGINAL TASK: {original_request or "Not specified"}

CONVERSATION FLOW:
{chr(10).join(conversation_summary[-5:])}

CURRENT STATUS:
- Last action: {last_assistant_message[:150] + "..." if last_assistant_message and len(last_assistant_message) > 150 else last_assistant_message or "No recent action"}
- Tools used: {', '.join(recent_tool_calls) if recent_tool_calls else "None"}
- Errors: {'Yes - ' + str(errors_found[0])[:50] if errors_found else 'No'}

Generate a specific, actionable continuation prompt that:
1. Directly addresses what should happen next
2. Is relevant to the current context
3. Helps achieve the original task
4. Is concise (one sentence)

IMPORTANT: Respond with ONLY the continuation prompt. No explanations, no "Here's a prompt:", just the direct instruction."""

    try:
        # Use LiteLLM through CAI's timeout wrapper.
        # Enable debug logging for litellm if in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Generating continuation advice with model: {model_name}")
            logger.debug(f"Context length: {len(context_summary)} chars")
        
        # Prepare kwargs for litellm based on model type
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": context_summary}],
            "temperature": 0.3,  # Override default (0.7) - lower temperature for focused continuation
            "max_tokens": 150,  # Slightly more tokens for complete thoughts
            "stream": False
        }
        
        # Configure for alias2-mini (compact Alias model; same API gateway as other alias models)
        if model_name.lower() == "alias2-mini":
            kwargs["api_base"] = "https://api.aliasrobotics.com:666/"
            kwargs["custom_llm_provider"] = "openai"
            kwargs["api_key"] = (cfg.alias_api_key or "sk-alias-1234567890").strip()
        # Configure for alias models (following the pattern in openai_chatcompletions.py) [S]
        elif "alias" in model_name.lower() and "alias0.5" not in model_name.lower():
            kwargs["api_base"] = "https://api.aliasrobotics.com:666/"
            kwargs["custom_llm_provider"] = "openai"
            kwargs["api_key"] = (cfg.alias_api_key or "sk-alias-1234567890").strip()
        
        # Make the API call
        logger.debug(f"Making API call with kwargs: {kwargs.get('model')}, provider: {kwargs.get('custom_llm_provider', 'default')}")
        response = await acompletion_with_timeout(kwargs, stream=False, model_name=model_name)
        
        # Extract content safely
        continuation_prompt = None
        if response:
            logger.debug(f"Got response: {response}")
            if hasattr(response, 'choices') and response.choices:
                if hasattr(response.choices[0], 'message') and response.choices[0].message:
                    content = response.choices[0].message.content
                    reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
                    if reasoning_content and content:
                        content = reasoning_content + "\n\n" + content
                    elif reasoning_content:
                        content = reasoning_content
                    continuation_prompt = content.strip() if content else None
                    logger.debug(f"Extracted prompt: {continuation_prompt}")
        
        # Check for generic responses that should trigger better fallbacks
        generic_responses = [
            "continue working on the task",
            "proceed with the next step",
            "keep going",
            "continue"
        ]
        
        is_generic = continuation_prompt and any(
            generic in continuation_prompt.lower() 
            for generic in generic_responses
        ) and len(continuation_prompt) < 50
        
        # Fallback if the response is empty, too short, or too generic
        if not continuation_prompt or len(continuation_prompt) < 10 or is_generic:
            logger.debug(f"Response too generic or short, using contextual fallback")
            raise ValueError("Generic response - using fallback")
        
    except Exception as e:
        # Log the error but don't expose authentication details to the user
        if "AuthenticationError" in str(type(e)):
            logger.debug(f"Model authentication error: {str(e)}")
        else:
            logger.error(f"Error generating continuation advice: {str(e)}")
        
        # Provide much more specific fallback based on detailed context analysis
        logger.debug(f"Using fallback logic. Errors: {bool(errors_found)}, Tools: {recent_tool_calls}, Last msg: {last_assistant_message[:50] if last_assistant_message else 'None'}")
        
        if errors_found:
            error_text = str(errors_found[0]).lower()
            if "not found" in error_text or "does not exist" in error_text:
                continuation_prompt = "Search for the correct file path or create the missing resource."
            elif "permission" in error_text or "denied" in error_text:
                continuation_prompt = "Check permissions and try accessing the resource with appropriate credentials."
            elif "syntax" in error_text or "parse" in error_text:
                continuation_prompt = "Fix the syntax error and retry the operation."
            else:
                continuation_prompt = "Analyze the specific error message and implement a solution."
                
        elif recent_tool_calls:
            # Much more specific based on tool combinations and context
            tool_str = ' '.join(recent_tool_calls).lower()
            
            if "grep" in tool_str or "search" in tool_str:
                if last_tool_output and "found" in str(last_tool_output).lower():
                    continuation_prompt = "Examine the search results in detail and investigate the most relevant findings."
                else:
                    continuation_prompt = "Broaden the search parameters or try different search terms."
                    
            elif "read" in tool_str or "file" in tool_str:
                if last_assistant_message and "security" in original_request.lower():
                    continuation_prompt = "Analyze the code for security vulnerabilities like injection flaws or authentication issues."
                else:
                    continuation_prompt = "Process the file contents and extract the relevant information."
                    
            elif "write" in tool_str or "edit" in tool_str:
                continuation_prompt = "Verify the changes were applied correctly and test the modified code."
                
            elif "bash" in tool_str or "shell" in tool_str:
                continuation_prompt = "Check the command output and proceed based on the results."
                
            else:
                continuation_prompt = "Build on the tool results to progress toward the goal."
                
        elif last_assistant_message:
            # Analyze the last message for better context
            last_msg_lower = last_assistant_message.lower()
            
            if "joke" in original_request.lower() or "joke" in last_msg_lower:
                continuation_prompt = "Tell another cybersecurity joke or pun."
            elif "found" in last_msg_lower or "discovered" in last_msg_lower:
                continuation_prompt = "Investigate these findings in greater detail."
            elif "analyzing" in last_msg_lower or "checking" in last_msg_lower:
                continuation_prompt = "Complete the analysis and summarize the results."
            elif "error" in last_msg_lower or "issue" in last_msg_lower:
                continuation_prompt = "Resolve the identified issue and continue."
            else:
                # Task-specific fallbacks based on original request
                if "security" in original_request.lower() or "vulnerabilit" in original_request.lower():
                    continuation_prompt = "Continue the security assessment by checking for additional vulnerabilities."
                elif "analyze" in original_request.lower() or "review" in original_request.lower():
                    continuation_prompt = "Deepen the analysis by examining more files or aspects."
                elif "test" in original_request.lower():
                    continuation_prompt = "Run additional tests to ensure comprehensive coverage."
                else:
                    continuation_prompt = "Take the next logical step toward completing the original task."
        else:
            continuation_prompt = "Begin working on the task by taking the first concrete action."
    
    if console:
        console.print(f"\n[cyan]🤖 Auto-continuing with:[/cyan] {continuation_prompt}")
    
    return continuation_prompt


def should_continue_automatically(
    message_history: List[Dict[str, Any]],
    force_continue: bool = False
) -> bool:
    """
    Determine if the agent should automatically continue based on conversation state.
    
    Args:
        message_history: List of previous messages
        force_continue: Force continuation regardless of state
        
    Returns:
        Boolean indicating whether to continue automatically
    """
    if force_continue:
        return True
    
    if not message_history:
        return False
    
    # Get the last few messages
    recent_messages = message_history[-5:]
    
    # Check if agent is actively working (recent tool usage)
    has_recent_tools = any(
        msg.get("role") == "assistant" and msg.get("tool_calls")
        for msg in recent_messages
    )
    
    # Check if agent explicitly said it's done or completed
    last_assistant_msg = None
    for msg in reversed(recent_messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            last_assistant_msg = msg.get("content", "").lower()
            break
    
    if last_assistant_msg:
        completion_indicators = [
            "completed", "finished", "done", "accomplished",
            "achieved", "succeeded", "concluded", "no further",
            "that's all", "nothing more"
        ]
        
        if any(indicator in last_assistant_msg for indicator in completion_indicators):
            return False
    
    # Continue if agent is actively using tools or investigating
    return has_recent_tools