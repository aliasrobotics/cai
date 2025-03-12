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

# Standard library imports
import copy
import platform
import re
import signal
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Third-party imports
from wasabi import color  # pylint: disable=import-error # noqa: E402

# Local imports
from cai.agents.meta.local_python_executor import (
    BASE_BUILTIN_MODULES,
    LocalPythonInterpreter,
    fix_final_answer_code,
    truncate_content,
)
from cai.types import Agent, Result


class CodeAgentException(Exception):
    """Base exception class for CodeAgent-related errors."""
    pass  # pylint: disable=unnecessary-pass


class CodeGenerationError(CodeAgentException):
    """
    Exception raised when there's an
    error generating code from the model.
    """
    pass  # pylint: disable=unnecessary-pass


class CodeParsingError(CodeAgentException):
    """Exception raised when there's an
    error parsing code from model output."""
    pass  # pylint: disable=unnecessary-pass


class CodeExecutionError(CodeAgentException):
    """Exception raised when there's an error
    executing code."""
    pass  # pylint: disable=unnecessary-pass


class CodeExecutionTimeoutError(CodeAgentException):
    """Exception raised when code execution times out."""
    pass  # pylint: disable=unnecessary-pass


# Define a timeout handler function
def timeout_handler(signum, frame):  # pylint: disable=unused-argument # noqa
    """
    Signal handler for timeouts.

    This handler is designed to be used with SIGALRM but can handle
    other signals gracefully. It raises a TimeoutError to indicate
    that the code execution has timed out.

    Args:
        signum (int): The signal number
        frame (frame): The current stack frame

    Raises:
        TimeoutError: Always raised to indicate timeout
    """
    if signum == signal.SIGALRM:  # pylint: disable=no-else-raise # noqa: E702
        raise TimeoutError("Code execution timed out")
    else:  # pylint: disable=no-else-raise # noqa: E702
        # Handle other signals gracefully
        raise TimeoutError(f"Code execution interrupted by signal {signum}")


# Define a class for thread-based timeout (for Windows compatibility)
class ThreadWithResult(threading.Thread):
    """Thread class that can return a result and catch exceptions."""

    def __init__(self, target, args=(), kwargs=None):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.result = None
        self.exception = None

    def run(self):
        try:
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.exception = e


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

    NOTE: This class is implemented using exceptional techniques
    due to how Pydantic handles model inheritance and field
    initialization, which avoids using the
    `self.attribute = value` syntax and defining the pydantic
    model fields as class variables.
    """

    # Define model configuration for Pydantic
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }

    def __init__(  # pylint: disable=too-many-arguments,too-many-locals # noqa: E501
        self,
        name: str = "CodeAgent",
        model: str = "qwen2.5:14b",
        instructions: Union[str, Callable[[], str]] = None,
        functions: List[Callable] = None,
        additional_authorized_imports: Optional[List[str]] = None,
        description: str = """Agent focused on writing and executing code.
                   State-of-the-art in code production.""",
        max_print_outputs_length: Optional[int] = None,
        reasoning_effort: Optional[str] = "medium",
        max_steps: int = 10,
        execution_timeout: int = 60,  # Default timeout of 60 seconds
        tool_choice: str = "auto",
    ):
        """Initialize a CodeAgent.

        Args:
            name: Name of the agent
            model: Model to use for the agent
            instructions: Instructions for the agent
            functions: List of functions available to the agent
            additional_authorized_imports: List of additional imports to allow
            max_print_outputs_length: Maximum length of print outputs
            reasoning_effort: Level of reasoning effort (low, medium, high)
            max_steps: Maximum number of steps to execute
            execution_timeout: Maximum time in seconds to allow for execution
            tool_choice: Tool choice strategy
        """
        # Store CodeAgent-specific parameters as local variables first
        _additional_imports = additional_authorized_imports or []
        _max_print_length = max_print_outputs_length
        _max_steps = max_steps
        _execution_timeout = execution_timeout
        _tool_choice = tool_choice
        # Calculate authorized imports
        _authorized_imports = list(
            set(BASE_BUILTIN_MODULES) | set(_additional_imports))

        # Store attributes as instance variables before creating instructions
        # Using object.__setattr__ to bypass Pydantic's attribute setting
        # mechanism
        object.__setattr__(
            self,
            'additional_authorized_imports',
            _additional_imports)
        object.__setattr__(self, 'authorized_imports', _authorized_imports)
        object.__setattr__(self, 'execution_timeout', _execution_timeout)
        object.__setattr__(self, 'tool_choice', _tool_choice)
        object.__setattr__(self, 'cai_instance', None)

        # Create instructions if needed
        if instructions is None:
            # Use the _create_instructions method to generate the default
            # instructions
            instructions = self._create_instructions()

        # Initialize parent class first
        super().__init__(
            name=name,
            model=model,
            description=description,
            instructions=instructions,
            functions=functions or [],
            reasoning_effort=reasoning_effort,
            temperature=0.2,  # Lower temperature for predictable code
        )

        # Store remaining attributes as instance variables
        # Using object.__setattr__ to bypass Pydantic's attribute setting
        # mechanism
        object.__setattr__(self, 'max_print_outputs_length', _max_print_length)
        object.__setattr__(self, 'max_steps', _max_steps)
        object.__setattr__(self, 'execution_timeout', _execution_timeout)
        object.__setattr__(self, 'context_variables', {'__name__': '__main__'})
        object.__setattr__(self, 'step_number', 0)

        # Initialize the Python interpreter
        python_executor = LocalPythonInterpreter(
            additional_authorized_imports=_additional_imports,
            tools={},  # We'll populate tools from functions
            max_print_outputs_length=_max_print_length,
        )
        object.__setattr__(self, 'python_executor', python_executor)

        # Register functions as tools for the Python executor
        self._register_functions_as_tools()

    def _create_instructions(self) -> str:
        """Create the system instructions including
        authorized imports information."""
        imports_info = (
            "You can import any Python module."
            if "*" in self.additional_authorized_imports
            else (
                f"You can only import from these modules: "
                f"{', '.join(sorted(self.authorized_imports))}"
            )
        )

        return f"""
You are a coding agent that solves problems by
writing and executing Python code.

When presented with a task, you should:
1. Think about the problem and how to approach it
2. Write Python code to solve the problem
3. Present your code in a properly formatted Python
    code block using ```python and ```
4. Your code will be automatically executed, and the
    results will be returned to you

Important guidelines:
- Always provide your solution within a Python code block
- Use print() statements to show your reasoning and progress
- {imports_info}
- Use the final_answer() function to provide your final
    answer when you've solved the problem
- When in doubt, test your approach with small examples first
- Maintain variables in memory across interactions - your state persists
- Your code execution has a timeout of {self.execution_timeout} seconds
    - avoid infinite loops or long-running operations
- The variable __name__ is set to "__main__" so you can use standard
Python patterns like:
  ```python
  if __name__ == "__main__":
      main()
  ```

Here's an example of a good response:```python
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
# Should print 13.0 since math.sqrt(5**2 + 12**2) = 13.0
print(f"Final result: 13.0")

# Return the final answer
final_answer(f"The result is 13.0")
```

I'll execute your code and show you the results.
"""

    def _register_functions_as_tools(self):
        """
        Register agent functions as tools
        available in the Python executor.
        """
        for func in self.functions:
            # Use the function name as the tool name
            func_name = func.__name__
            self.python_executor.static_tools[func_name] = func

    def _setup_signal_handlers(self):
        """
        Set up signal handlers for the CodeAgent.

        This method sets up signal handlers to ensure that the agent
        can handle interruptions gracefully. It's particularly important
        for long-running code executions.

        Returns:
            dict: A dictionary of original signal handlers that were replaced
        """
        original_handlers = {}

        # Only set up signal handlers on Unix-like systems
        if platform.system() != "Windows":
            # Save original handlers
            original_handlers[signal.SIGINT] = signal.getsignal(signal.SIGINT)
            original_handlers[signal.SIGTERM] = signal.getsignal(
                signal.SIGTERM)

            # Define a handler for SIGINT and SIGTERM
            def signal_handler(signum, frame):  # pylint: disable=unused-argument # noqa
                # Restore original handlers
                for sig, handler in original_handlers.items():
                    signal.signal(sig, handler)
                # Raise an exception to interrupt execution
                raise KeyboardInterrupt(
                    f"Execution interrupted by signal {signum}")

            # Set up handlers
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        return original_handlers

    def _restore_signal_handlers(self, original_handlers):
        """
        Restore original signal handlers.

        Args:
            original_handlers (dict): Dictionary of original signal handlers
        """
        if platform.system() != "Windows":
            for sig, handler in original_handlers.items():
                signal.signal(sig, handler)

    def process_interaction(
        self,
        cai_instance: object,
        messages: List[Dict],
        context_variables: Dict = None,
        debug: bool = False
    ) -> Tuple[Result, str, Optional[Any]]:
        """
        Process a conversation by generating and executing
        Python code.

        This method takes a list of messages representing
        the conversation history and generates/executes
        Python code based on the latest user message.

        Args:
            cai_instance (object):
                The CAI instance that is calling the CodeAgent
            messages (List[Dict]):
                List of messages in the conversation
            context_variables (Dict, optional):
                Variables to be made available in the code
            debug (bool, optional):
                Whether to print debug information

        Returns:
            Tuple[Result, str, Optional[Any]]:
                A tuple containing:
                - Result object with execution results
                - Generated code string
                - Optional completion object from LLM
        """
        if context_variables:
            self.context_variables.update(context_variables)

        # Ensure __name__ is set to "__main__" to simulate script execution
        self.context_variables["__name__"] = "__main__"

        # Extract the latest user message
        user_messages = [
            msg for msg in messages
            if msg.get("role") == "user"
        ]
        if not user_messages:
            return Result(
                value="No user message found in the conversation.",
                context_variables=self.context_variables
            ), "", None

        latest_user_message = user_messages[-1].get("content", "")

        try:
            # Try to extract code from the message
            # if it contains code blocks
            if "```" in latest_user_message:
                try:
                    code = parse_code_blobs(latest_user_message)
                    result = self._execute_code(code, debug)
                    return result, code, None
                except CodeParsingError:
                    # If parsing fails, generate code based on the message
                    pass

            # Generate code using the LLM based on the conversation
            code, completion = self._generate_code(
                cai_instance, messages, debug)
            result = self._execute_code(code, debug)
            return result, code, completion

        except CodeAgentException as e:
            # Handle agent-specific exceptions
            # Initialize code to empty string if it's not defined
            if 'code' not in locals():
                code = ""
            return Result(
                value=f"Error: {str(e)}",
                context_variables=self.context_variables
            ), code, None

    def _generate_code(self, cai_instance: object,
                       messages: List[Dict], debug: bool = False) -> str:
        """
        Generate Python code based on the conversation history.

        This method uses the LLM to generate Python code that solves
        the task described in the conversation.

        Args:
            cai_instance (object):
                The CAI instance that is calling the CodeAgent
            messages (List[Dict]):
                List of messages in the conversation
            debug (bool, optional):
                Whether to print debug information

        Returns:
            str: Generated Python code

        Raises:
            CodeGenerationError: If code generation fails
        """
        try:
            if debug:
                print(
                    color(
                        "🧠 Starting code generation...",
                        fg="blue",
                        bold=True))

            # Create a message that prompts the LLM to generate code
            code_generation_message = {
                "role": "user",
                "content": ("Based on our conversation, please generate "
                            "Python code to solve this problem. "
                            "Your response should ONLY include the "
                            "Python code block.")
            }

            # Clone the messages and add our code generation prompt
            messages_copy = copy.deepcopy(messages)
            messages_copy.append(code_generation_message)

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
                if debug:
                    print(color("📝 Generated code:", fg="green", bold=True))
                    print(color(f"```python\n{code}\n```", fg="green"))
                    print(
                        color(
                            "✅ Code generation completed",
                            fg="blue",
                            bold=True))
                return code, completion
            except CodeParsingError:
                # If no code block found, but the content looks like code,
                # return it as is
                if ("def " in model_response or
                    "import " in model_response or
                        "print(" in model_response):
                    if debug:
                        print(
                            color(
                                "📝 Generated code (no code block"
                                "found, but looks like code):",
                                fg="yellow",
                                bold=True))
                        print(
                            color(
                                f"```python\n{model_response}\n```",
                                fg="yellow"))
                        print(
                            color(
                                "✅ Code generation completed",
                                fg="blue",
                                bold=True))
                    return model_response, completion
                if debug:
                    print(
                        color(
                            "❌ No code found in model response",
                            fg="red",
                            bold=True))
                raise  # Re-raise if doesn't look like code

        except Exception as e:
            if debug:
                print(
                    color(
                        f"❌ Code generation failed: {
                            str(e)}",
                        fg="red",
                        bold=True))
            raise CodeGenerationError(f"Failed to generate code: {str(e)}")  # pylint: disable=raise-missing-from # noqa: E702,E501

    def _execute_code(self, code: str, debug: bool = False) -> Result:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements # noqa: E501
        """
        Execute the Python code and return the result.

        Args:
            code (str): Python code to execute
            debug (bool, optional): Whether to print debug information

        Returns:
            Result:
                A Result object containing the
                    execution result and updated state

        Raises:
            CodeExecutionError: If code execution fails
            CodeExecutionTimeoutError: If code execution times out
        """
        # Set up signal handlers
        original_handlers = self._setup_signal_handlers()

        try:
            if debug:
                print(
                    color(
                        "🚀 Starting code execution...",
                        fg="blue",
                        bold=True))

            # Fix the code if needed (e.g., ensure final_answer is properly
            # used)
            code = fix_final_answer_code(code)

            # Add __name__ to context_variables to simulate script execution
            self.context_variables["__name__"] = "__main__"

            # Execute the code with timeout
            if debug:
                print(color("⚙️ Executing code...", fg="cyan"))

            # Check if we're on a Unix-like system (Linux, macOS) or Windows
            # as the timeout implementation differs
            is_windows = platform.system() == "Windows"

            if is_windows:
                # Windows implementation using threads
                execution_logs = ""
                output = None
                is_final_answer = False

                # Define a function to execute the code
                def execute_code():
                    return self.python_executor(code, self.context_variables)

                # Create and start the thread
                thread = ThreadWithResult(target=execute_code)
                thread.start()
                thread.join(timeout=self.execution_timeout)

                # Check if the thread is still alive (timeout occurred)
                if thread.is_alive():
                    # Thread is still running, timeout occurred
                    # We can't easily kill the thread in Python, but we can
                    # proceed without waiting for it
                    if hasattr(
                        self.python_executor, "state") \
                            and "_print_outputs" in self.python_executor.state:
                        execution_logs = str(
                            self.python_executor.state.get(
                                "_print_outputs", ""))

                    timeout_message = f"Code execution timed out after {
                        self.execution_timeout} seconds."
                    if debug:
                        print(
                            color(
                                "⏱️ Code execution timed out:",
                                fg="red",
                                bold=True))
                        print(color(f"{timeout_message}", fg="red"))

                        if execution_logs:
                            print(
                                color(
                                    "📋 Logs before timeout:",
                                    fg="yellow",
                                    bold=True))
                            print(color(f"{execution_logs}", fg="yellow"))

                    result_message = f"Code execution timed out after {
                        self.execution_timeout} seconds.\n\n"
                    if execution_logs:
                        result_message += (
                            f"Execution logs before timeout:\n```\n{
                                execution_logs}\n```\n\n")
                    result_message += ("Please optimize your code to run "
                                       "more efficiently or break it into "
                                       "smaller steps.")

                    return Result(
                        value=result_message,
                        context_variables=self.context_variables
                    )

                # If we get here, the thread completed within the timeout
                if thread.exception:
                    # Re-raise the exception
                    raise thread.exception

                # Get the result
                output, execution_logs, is_final_answer = thread.result
            else:
                # Unix implementation using signals
                # Use a more robust approach with a context manager for signal
                # handling
                class SignalTimeout:
                    """
                    Context manager for handling signals
                    """

                    def __init__(self, seconds):
                        self.seconds = seconds
                        self.original_handler = None

                    def __enter__(self):
                        self.original_handler = signal.getsignal(
                            signal.SIGALRM)
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(self.seconds)
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        # Always reset the alarm and restore the original
                        # handler
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, self.original_handler)
                        # Don't suppress exceptions
                        return False

                try:
                    # Execute the code with timeout using context manager
                    with SignalTimeout(self.execution_timeout):
                        output, execution_logs, is_final_answer = (
                            self.python_executor(
                                code, self.context_variables))
                except TimeoutError:
                    # Get execution logs if available
                    execution_logs = ""
                    if (hasattr(
                        self.python_executor, "state") and
                            "_print_outputs" in self.python_executor.state):
                        execution_logs = str(
                            self.python_executor.state.get(
                                "_print_outputs", ""))

                    timeout_message = f"Code execution timed out after {
                        self.execution_timeout} seconds."
                    if debug:
                        print(
                            color(
                                "⏱️ Code execution timed out:",
                                fg="red",
                                bold=True))
                        print(color(f"{timeout_message}", fg="red"))

                        if execution_logs:
                            print(
                                color(
                                    "📋 Logs before timeout:",
                                    fg="yellow",
                                    bold=True))
                            print(color(f"{execution_logs}", fg="yellow"))

                    result_message = (
                        f"Code execution timed out after {
                            self.execution_timeout} seconds.\n\n")
                    if execution_logs:
                        result_message += (
                            f"Execution logs before timeout:\n```\n{
                                execution_logs}\n```\n\n")
                    result_message += ("Please optimize your code to run "
                                       "more efficiently or break it into "
                                       "smaller steps.")

                    return Result(
                        value=result_message,
                        context_variables=self.context_variables
                    )
                except Exception as e:
                    # Handle any other exceptions that might occur
                    # during execution. Get execution logs if available
                    execution_logs = ""
                    if (hasattr(
                        self.python_executor, "state") and
                            "_print_outputs" in self.python_executor.state):
                        execution_logs = str(
                            self.python_executor.state.get(
                                "_print_outputs", ""))

                    error_message = (
                        f"Code execution failed: {type(e).__name__}: {
                            str(e)}")
                    if debug:
                        print(
                            color(
                                "❌ Code execution failed:",
                                fg="red",
                                bold=True))
                        print(color(f"{error_message}", fg="red"))

                        if execution_logs:
                            print(
                                color(
                                    "📋 Logs before error:",
                                    fg="yellow",
                                    bold=True))
                            print(color(f"{execution_logs}", fg="yellow"))

                    error_message += (
                        f"\n\nExecution logs before error:\n```\n{
                            execution_logs}\n```")

                    raise CodeExecutionError(error_message)  # pylint: disable=raise-missing-from # noqa

            # Prepare the result message
            result_message = (
                "Code execution completed.\n\n")

            if execution_logs:
                result_message += (
                    f"Execution logs:\n```\n{
                        execution_logs}\n```\n\n")

            result_message += (
                f"Output: {truncate_content(str(output))}")

            # Print execution results with color if debug is enabled
            if debug:
                print(color("📊 Execution results:", fg="green", bold=True))
                if execution_logs:
                    print(color("📋 Logs:", fg="cyan", bold=True))
                    print(color(f"{execution_logs}", fg="cyan"))

                print(color("🔍 Output:", fg="yellow", bold=True))
                print(color(f"{truncate_content(str(output))}", fg="yellow"))

                if is_final_answer:
                    print(
                        color(
                            "🏁 Final answer provided",
                            fg="green",
                            bold=True))

                print(
                    color(
                        "✅ Code execution completed",
                        fg="blue",
                        bold=True))

            # Return the result
            return Result(
                value=result_message,
                context_variables=self.context_variables
            )

        except Exception as e:
            # Get execution logs if available
            execution_logs = ""
            if (hasattr(self.python_executor,
                        "state") and
                    "_print_outputs" in self.python_executor.state):
                execution_logs = str(
                    self.python_executor.state.get(
                        "_print_outputs", ""))

            error_message = f"Code execution failed: {type(e).__name__}: {
                str(e)}"
            if debug:
                print(color("❌ Code execution failed:", fg="red", bold=True))
                print(color(f"{error_message}", fg="red"))

                if execution_logs:
                    print(
                        color(
                            "📋 Logs before error:",
                            fg="yellow",
                            bold=True))
                    print(color(f"{execution_logs}", fg="yellow"))

            error_message += f"\n\nExecution logs before error:\n```\n{
                execution_logs}\n```"

            raise CodeExecutionError(error_message)  # pylint: disable=raise-missing-from # noqa: E702,E501
        finally:
            # Always restore original signal handlers
            self._restore_signal_handlers(original_handlers)

    def run(self, messages: List[Dict],
            context_variables: Dict = None, debug: bool = True) -> Result:
        """
        Run the agent on a conversation.

        This is the main entry point for the agent,
        aligning with CAI's expectations.

        Args:
            messages (List[Dict]):
                List of messages in the conversation
            context_variables (Dict, optional):
                Variables to be made available to the agent
            debug (bool, optional):
                Whether to print debug information

        Returns:
            Result: A Result object containing the execution
                result and updated context
        """
        # Set up signal handlers
        original_handlers = self._setup_signal_handlers()

        try:
            # Update step number
            self.step_number += 1  # pylint: disable=no-member # noqa: E702
            if self.step_number > self.max_steps:  # pylint: disable=no-member # noqa: E702,E501
                return Result(
                    value="Reached maximum number of steps in CodeAgent. "
                    "Stopping execution.",
                    context_variables=self.context_variables
                )

            # Process the conversation
            result, _, _ = self.process_interaction(
                None, messages, context_variables, debug)
            return result
        except Exception as e:  # pylint: disable=broad-exception-caught # noqa
            # Handle any exceptions that might occur during execution
            error_message = f"Agent execution failed: {type(e).__name__}: {
                str(e)}"
            if debug:
                print(color("❌ Agent execution failed:", fg="red", bold=True))
                print(color(f"{error_message}", fg="red"))

            return Result(
                value=error_message,
                context_variables=self.context_variables
            )
        finally:
            # Always restore original signal handlers
            self._restore_signal_handlers(original_handlers)


def transfer_to_codeagent(**kwargs):  # pylint: disable=W0613
    """Transfer to codeagent."""
    return codeagent


# agent
codeagent = CodeAgent(
    name="CodeAgent",
    additional_authorized_imports=["*"],
    execution_timeout=150,
    description="""Agent focused on writing code iteratively.
                   State-of-the-art in code production."""
    # functions=[],
    # tool_choice="required",  # force tool call for handoffs
    # execution_timeout=int(os.getenv('CAI_CODE_TIMEOUT', '30')),  # Get
    # timeout from env var or use default 30 seconds
)
