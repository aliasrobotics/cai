"""
Core module for the CAI library.

This module contains the main CAI class which handles chat completions,
tool calls, and agent interactions. It provides both synchronous and
streaming interfaces for running conversations with AI agents.

Imports are organized into standard library, third-party packages,
and local modules.
"""

# Standard library imports
import copy
import json
from collections import defaultdict
from typing import List
import math
# Package/library imports
import time
import os
from collections import deque
import litellm  # pylint: disable=import-error
from dotenv import load_dotenv  # pylint: disable=import-error  # noqa: E501
from wasabi import color  # pylint: disable=import-error
from cai.logger import exploit_logger
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
# Local imports
from cai.datarecorder import DataRecorder
from .util import (
    function_to_json,
    debug_print,
    cli_print_agent_messages,
    cli_print_tool_call,
    cli_print_state,
    get_ollama_api_base,
    check_flag
)
from .types import (
    Agent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Response,
    Result,
)

__CTX_VARS_NAME__ = "context_variables"
litellm.suppress_debug_info = True
def visualize_agent_graph(start_agent):
    """
    Visualize agent graph showing all bidirectional connections between agents.
    Uses Rich library for pretty printing.
    """
    if start_agent is None:
        Console().print("[red]No agent provided to visualize.[/red]")
        return

    console = Console()
    tree = Tree("🤖 Agent Graph", guide_style="bold blue")

    # Track visited agents and their nodes to handle cross-connections
    visited = {}
    agent_nodes = {}

    def add_agent_node(agent, parent=None, is_transfer=False):
        """Add agent node and track for cross-connections"""
        if agent is None:
            return None
            
        # Create or get existing node for this agent
        if id(agent) in visited:
            return agent_nodes[id(agent)]
            
        visited[id(agent)] = True
        
        # Create node for current agent
        if is_transfer:
            node = parent.add(f"[green]{agent.name}[/green]")
        else:
            node = parent.add(f"[green]{agent.name}[/green]") if parent else tree
            
        agent_nodes[id(agent)] = node
        
        # Add tools as children
        tools_node = node.add("[yellow]Tools[/yellow]")
        for fn in getattr(agent, "functions", []):
            if callable(fn):
                fn_name = getattr(fn, "__name__", "")
                if "handoff" not in fn_name.lower() and not fn_name.startswith("transfer_to"):
                    tools_node.add(f"[blue]{fn_name}[/blue]")

        # Add transfers section
        transfers_node = node.add("[magenta]Transfers[/magenta]")
        
        # Process handoff functions
        for fn in getattr(agent, "functions", []):
            if callable(fn):
                fn_name = getattr(fn, "__name__", "")
                if "handoff" in fn_name.lower() or fn_name.startswith("transfer_to"):
                    try:
                        next_agent = fn()
                        if next_agent:
                            # Show bidirectional connection
                            transfer = transfers_node.add(f"[red]⟷[/red] [green]{next_agent.name}[/green]")
                            if id(next_agent) not in visited:
                                add_agent_node(next_agent, transfer, True)
                            else:
                                # Add cross-connection reference
                                transfer.add(f"[cyan]↑ See {next_agent.name} above[/cyan]")
                    except Exception:
                        continue
                        
        return node

    # Start recursive traversal from root agent
    add_agent_node(start_agent)
    console.print(tree)

class CAI:  # pylint: disable=too-many-instance-attributes
    """
    Cybersecurity AI (CAI) object
    """
    STATE_INTERACTIONS_INTERVAL = 5  # number of interactions between state updates  # noqa: E501

    def __init__(self,  # pylint: disable=too-many-arguments
                 ctf=None,
                 log_training_data=True,
                 state_agent=None,
                 force_until_flag=False,
                 challenge=None):
        """
        Initialize the CAI object.

        Args:
            ctf: Optional CTF configuration object
            log_training_data: Whether to record training data, defaults to
                True
            state_agent: Optional state tracking agent for maintaining network
                state
            force_until_flag: Whether to force execution until the expected
                flag is found
            challenge: Optional challenge to force execution until the expected
                flag is found. NOTE: This is only used when force_until_flag is
                True

        The CAI object manages the core conversation loop, handling messages,
        tool calls, and agent interactions. It maintains state like:
        - Token counts for input/output
        - Message history length
        - Network state (if state_agent provided)
        - Training data recording (if enabled)
        """
        self.ctf = ctf
        self.brief = False
        self.init_len = 0  # initial length of history
        self.state_agent = state_agent
        self.stateful = self.state_agent is not None
        if self.stateful:
            self.state_interactions_count = 0
            self.last_state = None
        #
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_reasoning_tokens = 0
        self.interaction_input_tokens = 0
        self.interaction_output_tokens = 0
        self.interaction_reasoning_tokens = 0
        self.max_chars_per_message = 5000  # number of characters
        #
        if log_training_data:
            self.rec_training_data = DataRecorder()

        self.force_until_flag = force_until_flag
        self.challenge = challenge
        load_dotenv()

    def get_chat_completion(  # pylint: disable=too-many-arguments
        self,
        agent: Agent,
        history: List,
        context_variables: dict,
        model_override: str,
        stream: bool,
        debug: bool,
    ) -> ChatCompletionMessage:
        """
        Get a chat completion for the given agent, history,
        and context variables.
        """
        context_variables = defaultdict(str, context_variables)
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        messages = [{"role": "system", "content": instructions}] + history

        debug_print(
            debug,
            "Getting chat completion for...:",
            messages,
            brief=self.brief)

        tools = [function_to_json(f) for f in agent.functions]
        # hide context_variables from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params["required"]:
                params["required"].remove(__CTX_VARS_NAME__)

        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "stream": stream,
        }

        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls
            create_params["tools"] = tools
            create_params["tool_choice"] = agent.tool_choice
            create_params["temperature"] = 0.7
            create_params["stream_options"] = {"include_usage": True}

        # Refer to https://docs.litellm.ai/docs/completion/json_mode
        if agent.structured_output_class:

            # if providing the schema
            #
            # # NOTE: this is not working
            # # other than for Ollama-served models
            # create_params["response_format"] =
            #   agent.structured_output_class.model_json_schema()

            # when using pydantic
            create_params["response_format"] = agent.structured_output_class

            # set temperature to 0 when using structured output
            create_params["temperature"] = 0.0

        # NOTE: This is a workaround to avoid errors with O1 and O3 models
        # since reasoners don't support parallel tool calls, nor
        # temperature
        #
        # NOTE 2: See further details on reasoners @
        # https://platform.openai.com/docs/guides/reasoning
        #
        if any(x in agent.model for x in ["o1", "o3"]):
            create_params.pop("temperature", None)
            create_params.pop("parallel_tool_calls", None)
            # See https://platform.openai.com/docs/api-reference/chat/create#chat-create-reasoning_effort  # noqa: E501  # pylint: disable=line-too-long
            create_params["reasoning_effort"] = agent.reasoning_effort
        try:
            if os.getenv("OLLAMA", "").lower() == "true":
                litellm_completion = litellm.completion(
                    **create_params,
                    api_base=get_ollama_api_base(),
                    custom_llm_provider="openai"
                )
            else:
                litellm_completion = litellm.completion(**create_params)

        except litellm.exceptions.BadRequestError as e:
            if "LLM Provider NOT provided" in str(e):
                create_params["api_base"] = get_ollama_api_base()
                create_params["custom_llm_provider"] = "openai"
                os.environ["OLLAMA"] = "true"
                os.environ["OPENAI_API_KEY"] = "Placeholder"
                litellm_completion = litellm.completion(**create_params)
            else:
                raise e

        except litellm.exceptions.RateLimitError as e:
            print("Rate Limit Error:" + str(e))
            time.sleep(60)
            litellm_completion = litellm.completion(**create_params)

        if self.rec_training_data:
            self.rec_training_data.rec_training_data(
                create_params, litellm_completion)

        # print(litellm_completion)  # debug
        return litellm_completion

    def handle_function_result(self, result, debug) -> Result:
        """
        Handle the result of a function call by
        converting it into a standardized Result type.

        The Result type encapsulates the possible
        return values (Result, Agent, or context variables)
        that functions can produce into a consistent
        format for the framework to process.
        """
        match result:
            case Result() as result:
                return result

            case Agent() as agent:
                return Result(
                    value=json.dumps({"assistant": agent.name}),
                    agent=agent,
                )
            case _:
                try:
                    return Result(value=str(result))
                except Exception as e:
                    error_message = f"Failed to cast response to string: {result}. Make sure agent functions return a string or Result object. Error: {str(e)}"  # noqa: E501 # pylint: disable=C0301
                    debug_print(debug, error_message, brief=self.brief)
                    raise TypeError(error_message) from e

    def handle_tool_calls(  # pylint: disable=too-many-arguments,too-many-locals  # noqa: E501
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: dict,
        debug: bool,
        agent: Agent,
        n_turn: int = 0,
        message: str = "",

    ) -> Response:
        """
        Execute and handle tool calls made by the AI agent.

        Processes a list of tool calls by:
        1. Looking up each function in the provided function map
        2. Handling missing tools gracefully by skipping them
        3. Parsing and validating function arguments
        4. Executing functions with provided arguments and context
        5. Processing results into standardized Response format
        6. Accumulating results from multiple tool calls

        Args:
            tool_calls (List[ChatCompletionMessageToolCall]): Tool
                calls requested by AI agent
            functions (List[AgentFunction]): Available functions
                that can be called
            context_variables (dict): Context variables to pass
                to functions
            debug (bool): Flag to enable debug logging
            agent: Agent object
            n_turn: Number of the turn
        Returns:
            Response: Object containing:
                messages (List): Tool call results
                agent (Optional[Agent]): Updated agent
                    if returned by a function
                context_variables (dict): Updated context variables

        Note:
            Results from multiple tool calls are accumulated
                into a single Response.
            Context variables are updated iteratively as
                functions are called.
        """
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(
            messages=[], agent=None, context_variables={})

        cli_print_agent_messages(agent.name, message,
                                 n_turn, agent.model, debug)

        for tool_call in tool_calls:
            name = tool_call.function.name
            # handle missing tool case, skip to next tool
            if name not in function_map:
                debug_print(
                    debug,
                    f"Tool {name} not found in function map.",
                    brief=self.brief)
                partial_response.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "tool_name": name,
                        "content": f"Error: Tool {name} not found.",
                    }
                )
                continue
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                debug_print(
                    debug,
                    f"Invalid JSON in tool arguments: {
                        tool_call.function.arguments}",
                    brief=self.brief)
                partial_response.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "tool_name": name,
                        "content": "Error: Invalid JSON in tool arguments.",
                    }
                )

                continue
            debug_print(
                debug,
                "Processing tool call",
                name,
                "with arguments",
                args,
                brief=self.brief)

            func = function_map[name]
            # pass context_variables to agent functions
            if __CTX_VARS_NAME__ in func.__code__.co_varnames:
                args[__CTX_VARS_NAME__] = context_variables
            if self.ctf:
                args["ctf"] = self.ctf

            @exploit_logger.log_tool()
            def execute_tool(tool_name, **tool_args):
                """Execute a tool function with logging.

                Args:
                    tool_name (str): The name of the tool to execute
                    **tool_args: Variable keyword arguments to pass
                        to the tool function

                Returns:
                    The result from executing the tool function with
                        the given arguments
                """
                try:
                    raw_result = function_map[tool_name](**tool_args)
                except TypeError as e:
                    if "unexpected keyword argument" in str(
                            e):  # Usual Error when open source model try do a handoff # noqa: E501
                        print(f"Warning: {e}. Executing tool {
                              tool_name} without arguments.")
                        raw_result = function_map[tool_name]()
                    else:
                        print(f"Error executing tool {tool_name}: {e}")
                        raise e
                except Exception as e:
                    print(f"Error executing tool {tool_name}: {e}")
                    raise e
                return raw_result

            raw_result = execute_tool(name, **args)

            # print result if not in debug mode so that at least
            # something is visible in the terminal
            if not debug:
                if isinstance(raw_result, str):
                    print("\033[32m" + raw_result + "\033[0m")
                elif isinstance(raw_result, Agent):  # handoffs
                    print("\033[33m" + raw_result.name + "\033[0m")

            result: Result = self.handle_function_result(raw_result, debug)
            # truncate tool output if it exceeds the max_chars_per_message
            if len(result.value) > self.max_chars_per_message:
                # pick the first half from the beginning and the second half
                # from the end
                half_len = self.max_chars_per_message // 2
                result.value = (result.value[:half_len] +
                                result.value[-half_len:])

            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "tool_name": name,
                    "content": result.value,
                }
            )
            cli_print_tool_call(
                tool_name=name,
                tool_args=args,
                tool_output=result.value,
                interaction_input_tokens=self.interaction_input_tokens,
                interaction_output_tokens=self.interaction_output_tokens,
                interaction_reasoning_tokens=self.interaction_reasoning_tokens,
                total_input_tokens=self.total_input_tokens,
                total_output_tokens=self.total_output_tokens,
                total_reasoning_tokens=self.total_reasoning_tokens,
                model=agent.model,
                debug=debug)

            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent

        return partial_response

    @exploit_logger.log_agent()
    def process_interaction(self, active_agent, history, context_variables,  # pylint: disable=too-many-arguments  # noqa: E501
                            model_override, stream, debug, execute_tools,
                            n_turn):
        """
        Process an interaction with the AI agent.
        """
        # stateful
        #
        # NOTE: consider adding state to the context variables,
        # and then adding it to the messages
        #
        if self.stateful:
            self.state_interactions_count += 1
            if self.state_interactions_count >= CAI.STATE_INTERACTIONS_INTERVAL:  # noqa: E501

                # fill in context variables
                context_variables["state"] = self.last_state  # state
                # initial messages
                context_variables["initial_history"] = history[:self.init_len]

                # get state from existing messages
                completion = self.get_chat_completion(
                    agent=self.state_agent,
                    history=history,
                    context_variables=context_variables,
                    model_override=model_override,
                    stream=stream,
                    debug=debug
                )

                # update token counts
                if completion and completion.usage and completion.choices:  # noqa: E501  # pylint: disable=C0103
                    # Update interaction and total token counts
                    self.interaction_input_tokens = completion.usage.prompt_tokens  # noqa: E501  # pylint: disable=C0103
                    self.interaction_output_tokens = completion.usage.completion_tokens  # noqa: E501  # pylint: disable=C0103
                    if (hasattr(completion.usage, 'completion_tokens_details') and  # noqa: E501  # pylint: disable=C0103
                            completion.usage.completion_tokens_details and
                            hasattr(completion.usage.completion_tokens_details,
                                    'reasoning_tokens') and
                            completion.usage.completion_tokens_details.reasoning_tokens):  # noqa: E501  # pylint: disable=C0103
                        self.interaction_reasoning_tokens = (
                            completion.usage.completion_tokens_details.reasoning_tokens)  # noqa: E501  # pylint: disable=C0103
                        self.total_reasoning_tokens += self.interaction_reasoning_tokens  # noqa: E501  # pylint: disable=C0103
                    else:
                        self.interaction_reasoning_tokens = 0

                    self.total_input_tokens += self.interaction_input_tokens  # noqa: E501  # pylint: disable=C0103
                    self.total_output_tokens += self.interaction_output_tokens  # noqa: E501  # pylint: disable=C0103

                    # get new state
                    message = completion.choices[0].message
                    self.last_state = message.content
                    message.sender = "state_agent"

                    # update history
                    # set back to initial prompt
                    history = history[:self.init_len]
                    # add state to history
                    history.append(
                        json.loads(message.model_dump_json()))

                    # log
                    debug_print(
                        debug,
                        "State: ",
                        message,
                        brief=self.brief)
                    cli_print_state(self.state_agent.name,
                                    message.content,
                                    n_turn,
                                    self.state_agent.model,
                                    debug,
                                    interaction_input_tokens=self.interaction_input_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                    interaction_output_tokens=self.interaction_output_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                    interaction_reasoning_tokens=self.interaction_reasoning_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                    total_input_tokens=self.total_input_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                    total_output_tokens=self.total_output_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                    total_reasoning_tokens=self.total_reasoning_tokens)  # noqa: E501  # pylint: disable=line-too-long

                # reset counter regardless of timeout
                self.state_interactions_count = 0

        # get completion with current history, agent
        completion = self.get_chat_completion(
            agent=active_agent,
            history=history,
            context_variables=context_variables,
            model_override=model_override,
            stream=stream,
            debug=debug,
        )
        if completion.usage:
            self.interaction_input_tokens = (
                completion.usage.prompt_tokens
            )
            self.interaction_output_tokens = (
                completion.usage.completion_tokens
            )
            if (hasattr(completion.usage, 'completion_tokens_details') and  # noqa: E501  # pylint: disable=C0103
                    completion.usage.completion_tokens_details and
                    hasattr(completion.usage.completion_tokens_details,
                            'reasoning_tokens') and
                    completion.usage.completion_tokens_details.reasoning_tokens):  # noqa: E501  # pylint: disable=C0103
                self.interaction_reasoning_tokens = (
                    completion.usage.completion_tokens_details.reasoning_tokens)  # noqa: E501  # pylint: disable=C0103
                self.total_reasoning_tokens += self.interaction_reasoning_tokens  # noqa: E501  # pylint: disable=C0103
            else:
                self.interaction_reasoning_tokens = 0

            self.total_input_tokens += (
                self.interaction_input_tokens
            )
            self.total_output_tokens += (
                self.interaction_output_tokens
            )

        message = completion.choices[0].message

        debug_print(
            debug,
            "Received completion:",
            message,
            brief=self.brief)
        message.sender = active_agent.name
        history.append(
            json.loads(message.model_dump_json())
        )  # to avoid OpenAI types (?)

        if not message.tool_calls or not execute_tools:
            cli_print_agent_messages(active_agent.name,
                                     message.content,
                                     n_turn,
                                     active_agent.model,
                                     debug)
            debug_print(debug, "Ending turn.", brief=self.brief)
            return None

        # handle function calls, updating context_variables, and switching
        # agents
        partial_response = self.handle_tool_calls(
            message.tool_calls, active_agent.functions,
            context_variables, debug, active_agent, n_turn,
            message=message.content
        )

        history.extend(partial_response.messages)
        context_variables.update(partial_response.context_variables)
        return (partial_response.agent
                if partial_response.agent
                else active_agent)


    @exploit_logger.log_response("🚩" + os.getenv('CTF_NAME', 'test') +
                                 " @ " + os.getenv('CI_JOB_ID', 'local'))
    def run(  # pylint: disable=too-many-arguments,dangerous-default-value,too-many-locals,too-many-statements # noqa: E501
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        stream: bool = False,
        debug: int = 0,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
        brief: bool = False,
    ) -> Response:
        """
        Run the cai and return the final response along
        with execution time in seconds.

        This method returns when the "turn" finalizes. Each "turn"
        is composed by one or more "interactions". For clarify,
        some definitions:
        - "turn": a single interaction with CAI
        - "interaction": a single interaction with the LLM, with
            its corresponding tool calls and responses.
        """
        start_time = time.time()
        self.brief = brief
        visualize_agent_graph(agent)
        self.init_len = len(messages)

        # TODO: consider moving this outside of CAI  # pylint: disable=fixme  # noqa: E501
        # as the logging URL has a harcoded bit which is
        # dependent on the file that invokes it
        #
        if os.getenv("CAI_TRACING", "true").lower() == "true":
            print(
                color("Logging URL: " +
                      exploit_logger.get_logger_url(),
                      fg="white", bg="pink")
            )

        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        n_turn = 0
        while len(history) - self.init_len < max_turns and active_agent:
            try:
                active_agent = self.process_interaction(
                    active_agent,
                    history,
                    context_variables,
                    model_override,
                    stream,
                    debug,
                    execute_tools,
                    n_turn
                )
                n_turn += 1
            except EOFError:
                print("\nCtrl+D pressed, exiting current turn...")
                break

            if active_agent is None and self.force_until_flag:
                # Check if the flag is found in the last tool output
                flag_found, flag = check_flag(
                    history[-1]["content"], self.ctf, self.challenge)
                if flag_found:
                    break

                # # Check if flag is found anywhere in history
                # for message in history:
                #     flag_found, _ = check_flag(message["content"],
                #                                self.ctf,
                #                                self.challenge)
                #     if flag_found:
                #         break

                # If flag is not found, continue with the next turn
                # adding to the history that the flag was not found
                history.append({
                    "role": "user",
                    "content": (
                        f"Detected flag {flag} is not the expected one. "
                        "Keep looking for it and reflect on your "
                        "previous steps."
                    )
                })
                active_agent = agent
            elif active_agent is None:
                break

        execution_time = time.time() - start_time
        return Response(
            messages=history[self.init_len:],
            agent=active_agent,
            context_variables=context_variables,
            time=execution_time
        )
