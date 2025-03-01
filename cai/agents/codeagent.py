"""
A Coding Agent (CodeAgent)

A re-interpretation for CAI of the original CodeAct concept
from the paper "Executable Code Actions Elicit Better LLM Agents"
at https://arxiv.org/pdf/2402.01030.

Briefly, the CodeAgent CAI Agent uses executable Python code to 
consolidate LLM agents' actions into a unified action space 
(CodeAct). Integrated with a Python interpreter, CodeAct can 
execute code actions and dynamically revise prior actions or 
emit new actions upon new observations through multi-turn 
interactions.
"""

import ast
import re
import json
import copy
import os
from typing import Any, Dict, List, Optional, Union, Callable

from cai.types import Agent, Result
from cai.state import State

# Import necessary components for code execution
from cai.agents.local_python_executor import (
    BASE_BUILTIN_MODULES,
    LocalPythonInterpreter,
    truncate_content,
    fix_final_answer_code,
)


class CodeAgentException(Exception):
    """Base exception class for CodeAgent-related errors."""
    pass


class CodeGenerationError(CodeAgentException):
    """Exception raised when there's an error generating code from the model."""
    pass


class CodeParsingError(CodeAgentException):
    """Exception raised when there's an error parsing code from model output."""
    pass


class CodeExecutionError(CodeAgentException):
    """Exception raised when there's an error executing code."""
    pass


def parse_code_blobs(text: str) -> str:
    """
    Extract Python code blocks from the 
    text, with fallback detection for non-marked code.
    
    This function first attempts to find code within 
    markdown-style code blocks (```python ... ``` or ``` ... ```). 
    If no code blocks are found, it tries to identify Python code 
    by looking for common Python syntax patterns.
    
    Args:
        text (str): Text containing code blocks or raw 
            Python code
        
    Returns:
        str: Extracted Python code, stripped of 
            leading/trailing whitespace
        
    Raises:
        CodeParsingError: If no valid Python code can be 
            identified in the text
    """
    # Pattern to match code blocks: ```python ... ``` or just ``` ... ```
    pattern = r"```(?:python)?\s*([\s\S]*?)```"
    matches = re.findall(pattern, text)
    
    if not matches:
        # Try to find code without explicit code block markers
        if "def " in text or "import " in text or "print(" in text:
            # Extract what looks like code
            lines = text.split("\n")
            code_lines = []
            for line in lines:
                if line.strip().startswith((
                    "def ", 
                    "import ", 
                    "from ", 
                    "print(", 
                    "#", 
                    "for ", 
                    "if "
                )):
                    code_lines.append(line)
            if code_lines:
                return "\n".join(code_lines)
        
        raise CodeParsingError("No code block found in the text")
    
    # Return the first code block
    return matches[0].strip()


class CodeAgent(Agent):
    """
    CodeAgent executes Python code to solve tasks.
    
    This agent interprets LLM responses as executable Python 
    code, runs the code in a controlled environment, and 
    returns the results. It can use tools through code 
    execution and maintain state between interactions.
    
    Attributes:
        additional_authorized_imports (List[str]): 
            Additional imports allowed beyond base modules
        state (Dict[str, Any]): 
            State variables maintained across executions
        python_executor (LocalPythonInterpreter): 
            The Python code interpreter
    """
    
    def __init__(
        self,
        name: str = "CodeAgent",
        model: str = "gpt-4o",
        instructions: Union[str, Callable[[], str]] = None,
        functions: List[Callable] = None,
        additional_authorized_imports: Optional[List[str]] = None,
        max_print_outputs_length: Optional[int] = None,
        reasoning_effort: Optional[str] = "medium",
        max_steps: int = 6,
    ):
        """
        Initialize a CodeAgent.
        
        Args:
            name (str): Name of the agent
            model (str): Model to use for generating code
            instructions (Union[str, Callable]): Custom instructions for the agent
            functions (List[Callable]): Functions to register with the agent
            additional_authorized_imports (List[str]): Additional Python imports to allow
            max_print_outputs_length (int): Maximum length of print outputs
            reasoning_effort (str): Level of reasoning effort ("low", "medium", "high")
            max_steps (int): Maximum number of steps the agent can take
        """
        # CodeAgent specific attributes
        self.additional_authorized_imports = additional_authorized_imports or []
        self.authorized_imports = list(set(BASE_BUILTIN_MODULES) | set(self.additional_authorized_imports))
        self.max_print_outputs_length = max_print_outputs_length
        self.max_steps = max_steps
        self.context_variables = {}
        self.step_number = 0
        
        # Create the default instructions with authorized imports information
        default_instructions = self._create_instructions()
        
        # Initialize with default or custom instructions
        if instructions is None:
            instructions = default_instructions
            
        # Initialize parent class
        super().__init__(
            name=name,
            model=model,
            instructions=instructions,
            functions=functions or [],
            reasoning_effort=reasoning_effort,
            temperature=0.2,  # Lower temperature for predictable code
        )
        
        # Initialize the Python interpreter
        self.python_executor = LocalPythonInterpreter(
            additional_authorized_imports=self.additional_authorized_imports,
            tools={},  # We'll populate tools from functions
            max_print_outputs_length=max_print_outputs_length,
        )
        
        # Register functions as tools for the Python executor
        self._register_functions_as_tools()
    
    def _create_instructions(self) -> str:
        """Create the system instructions including authorized imports information."""
        imports_info = (
            "You can import any Python module."
            if "*" in self.additional_authorized_imports
            else f"You can only import from these modules: {', '.join(sorted(self.authorized_imports))}"
        )
        
        return f"""You are a coding agent that solves problems by writing and executing Python code.

When presented with a task, you should:
1. Think about the problem and how to approach it
2. Write Python code to solve the problem
3. Present your code in a properly formatted Python code block using ```python and ```
4. Your code will be automatically executed, and the results will be returned to you

Important guidelines:
- Always provide your solution within a Python code block
- Use print() statements to show your reasoning and progress
- {imports_info}
- Use the final_answer() function to provide your final answer when you've solved the problem
- When in doubt, test your approach with small examples first
- Maintain variables in memory across interactions - your state persists

Here's an example of a good response:
```python
# Let's solve this step by step
import math

# Define our approach
def calculate_result(x, y):
    return math.sqrt(x**2 + y**2)

# Test with an example
test_result = calculate_result(3, 4)
print(f"Test result: 5")  # Should print 5.0

# Solve the actual problem
final_result = calculate_result(5, 12)
print(f"Final result: 13.0")  # Should print 13.0 since math.sqrt(5**2 + 12**2) = 13.0

# Return the final answer
final_answer(f"The result is 13.0")
```

I'll execute your code and show you the results.
"""
    
    def _register_functions_as_tools(self):
        """Register agent functions as tools available in the Python executor."""
        for func in self.functions:
            # Use the function name as the tool name
            func_name = func.__name__
            self.python_executor.static_tools[func_name] = func
    
    def process_interaction(self, messages: List[Dict], context_variables: Dict = None) -> Result:
        """
        Process a conversation by generating and executing Python code.
        
        This method takes a list of messages representing the conversation history
        and generates/executes Python code based on the latest user message.
        
        Args:
            messages (List[Dict]): List of messages in the conversation
            context_variables (Dict, optional): Variables to be made available in the code
            
        Returns:
            Result: A Result object containing the execution result and updated context
        """
        if context_variables:
            self.context_variables.update(context_variables)
        
        # Extract the latest user message
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        if not user_messages:
            return Result(
                value="No user message found in the conversation.",
                context_variables=self.context_variables
            )
        
        latest_user_message = user_messages[-1].get("content", "")
        
        try:
            # Try to extract code from the message if it contains code blocks
            if "```" in latest_user_message:
                try:
                    code = parse_code_blobs(latest_user_message)
                    return self._execute_code(code)
                except CodeParsingError:
                    # If parsing fails, generate code based on the message
                    pass
            
            # Generate code using the LLM based on the conversation
            code = self._generate_code(messages)
            return self._execute_code(code)
            
        except CodeAgentException as e:
            # Handle agent-specific exceptions
            return Result(
                value=f"Error: {str(e)}",
                context_variables=self.context_variables
            )
    
    def _generate_code(self, messages: List[Dict]) -> str:
        """
        Generate Python code based on the conversation history.
        
        This method uses the LLM to generate Python code that solves
        the task described in the conversation.
        
        Args:
            messages (List[Dict]): List of messages in the conversation
            
        Returns:
            str: Generated Python code
            
        Raises:
            CodeGenerationError: If code generation fails
        """
        try:
            # Import here to avoid circular imports
            from cai.core import CAI
            
            # Create a message that prompts the LLM to generate code
            code_generation_message = {
                "role": "user",
                "content": "Based on our conversation, please generate Python code to solve this problem. Your response should ONLY include the Python code block."
            }
            
            # Clone the messages and add our code generation prompt
            messages_copy = copy.deepcopy(messages)
            messages_copy.append(code_generation_message)
            
            # Create a temporary CAI instance just for code generation
            # This is efficient as CAI doesn't maintain much state on init
            cai_instance = CAI()
            
            # Get completion from the model
            completion = cai_instance.get_chat_completion(
                agent=self,
                history=messages_copy,
                context_variables=self.context_variables,
                model_override=None,
                stream=False,
                debug=False,
                master_template="system_codeact_template.md"
            )
            
            # Extract the model's response
            model_response = completion.choices[0].message.content
            
            # Parse code blocks from the response
            try:
                code = parse_code_blobs(model_response)
                return code
            except CodeParsingError:
                # If no code block found, but the content looks like code, return it as is
                if "def " in model_response or "import " in model_response or "print(" in model_response:
                    return model_response
                raise  # Re-raise if doesn't look like code
            
        except Exception as e:
            raise CodeGenerationError(f"Failed to generate code: {str(e)}")
    
    def _execute_code(self, code: str) -> Result:
        """
        Execute the Python code and return the result.
        
        Args:
            code (str): Python code to execute
            
        Returns:
            Result: A Result object containing the execution result and updated state
            
        Raises:
            CodeExecutionError: If code execution fails
        """
        try:
            # Fix the code if needed (e.g., ensure final_answer is properly used)
            code = fix_final_answer_code(code)
            
            # Execute the code
            output, execution_logs, is_final_answer = self.python_executor(code, self.context_variables)
            
            # Prepare the result message
            result_message = f"Code execution completed.\n\n"
            
            if execution_logs:
                result_message += f"Execution logs:\n```\n{execution_logs}\n```\n\n"
            
            result_message += f"Output: {truncate_content(str(output))}"
            
            # Return the result
            return Result(
                value=result_message,
                context_variables=self.context_variables
            )
            
        except Exception as e:
            # Get execution logs if available
            execution_logs = ""
            if hasattr(self.python_executor, "state") and "_print_outputs" in self.python_executor.state:
                execution_logs = str(self.python_executor.state.get("_print_outputs", ""))
            
            error_message = f"Code execution failed: {type(e).__name__}: {str(e)}"
            if execution_logs:
                error_message += f"\n\nExecution logs before error:\n```\n{execution_logs}\n```"
            
            raise CodeExecutionError(error_message)
    
    def run(self, messages: List[Dict], context_variables: Dict = None) -> Result:
        """
        Run the agent on a conversation.
        
        This is the main entry point for the agent, aligning with CAI's expectations.
        
        Args:
            messages (List[Dict]): List of messages in the conversation
            context_variables (Dict, optional): Variables to be made available to the agent
            
        Returns:
            Result: A Result object containing the execution result and updated context
        """
        # Update step number
        self.step_number += 1
        if self.step_number > self.max_steps:
            return Result(
                value="Reached maximum number of steps. Please restart the conversation.",
                context_variables=self.context_variables
            )
        
        # Process the conversation
        return self.process_interaction(messages, context_variables)


model = os.getenv('CAI_MODEL', "claude-3-7-sonnet-20250219")
codeagent = CodeAgent(
    model=model,
    name="CodeAgent",
    additional_authorized_imports=["*"],
)