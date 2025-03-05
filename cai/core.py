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
from typing import List, Tuple
# Package/library imports
import time
import os
import litellm  # pylint: disable=import-error
from mako.template import Template  # pylint: disable=import-error
from dotenv import load_dotenv  # pylint: disable=import-error # noqa: E501
from wasabi import color  # pylint: disable=import-error
from cai.logger import exploit_logger
from cai import graph
# Local imports
from cai.datarecorder import DataRecorder
from cai import (
    transfer_to_state_agent,
)
from cai.state.common import StateAgent
from cai.cost.llm_cost import (
    calculate_conversation_cost
)
from .agents.codeagent import CodeAgent
from .util import (
    function_to_json,
    debug_print,
    cli_print_agent_messages,
    cli_print_tool_call,
    fix_message_list,
    cli_print_state,
    get_ollama_api_base,
    check_flag,
    cli_print_codeagent_output,
    initialize_global_timer,
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


class CAI:  # pylint: disable=too-many-instance-attributes
    """
    Cybersecurity AI (CAI) object
    """
    STATE_INTERACTIONS_INTERVAL = 2  # number of interactions between state updates  # noqa: E501

    def __init__(self,  # pylint: disable=too-many-arguments
                 ctf=None,
                 log_training_data=True,
                 state_agent=None,
                 force_until_flag=False,
                 challenge=None,
                 ctf_inside=True,
                 source="cli",  # Add source parameter with default value
                 ):
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
            ctf_inside: Whether the CTF is inside a docker container
            source: Source of the CAI call ("cli" or "test_generic")

        The CAI object manages the core conversation loop, handling messages,
        tool calls, and agent interactions. It maintains state like:
        - Token counts for input/output
        - Message history length
        - Network state (if state_agent provided)
        - Training data recording (if enabled)
        """
        # Initialize global timer at CAI instantiation
        initialize_global_timer()

        self.ctf = ctf
        self.ctf_inside = ctf_inside
        self.brief = False
        self.init_len = 0  # initial length of history
        self.source = source  # Store the source

        # graph
        self._graph = graph.get_default_graph()

        # state
        self.state_agent = state_agent
        self.stateful = self.state_agent is not None
        if self.stateful:
            self.state_interactions_count = 0
            self.last_state = None

        # metrics
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_reasoning_tokens = 0
        self.interaction_input_tokens = 0
        self.interaction_output_tokens = 0
        self.interaction_reasoning_tokens = 0
        self.max_chars_per_message = 5000  # number of characters

        # training data
        if log_training_data:
            self.rec_training_data = DataRecorder()

        # memory attributes
        self.episodic_rag = (os.getenv("CAI_MEMORY", "?").lower() == "episodic"
                             or os.getenv("CAI_MEMORY", "?").lower() == "all")
        self.semantic_rag = (os.getenv("CAI_MEMORY", "?").lower() == "semantic"
                             or os.getenv("CAI_MEMORY", "?").lower() == "all")
        self.rag_online = os.getenv(
            "CAI_MEMORY_ONLINE",
            "false").lower() == "true"
        self.rag_interval = int(os.getenv("CAI_MEMORY_ONLINE_INTERVAL", "5"))

        self.force_until_flag = force_until_flag
        if self.episodic_rag:
            from cai.agents.memory import (  # pylint: disable=import-outside-toplevel # noqa: E501
                episodic_builder,
            )
            self.episodic_builder = episodic_builder
        if self.semantic_rag:
            from cai.agents.memory import (  # pylint: disable=import-outside-toplevel # noqa: E501
                semantic_builder,
            )
            self.semantic_builder = semantic_builder
        self.challenge = challenge
        self.total_cost = 0
        # load env variables
        load_dotenv()

    def get_chat_completion(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,line-too-long,too-many-statements # noqa: E501
        self,
        agent: Agent,
        history: List,
        context_variables: dict,
        model_override: str,
        stream: bool,
        debug: bool,
        master_template: str = "system_master_template.md"
    ) -> ChatCompletionMessage:
        """
        Get a chat completion for the given agent, history,
        and context variables.
        """
        context_variables = defaultdict(str, context_variables)

        # --------------------------------
        # Messages
        # --------------------------------
        messages = [{"role": "system", "content": Template(  # nosec: B702
            filename=f"cai/prompts/core/{master_template}").render(
                agent=agent,
                ctf_instructions=history[0]["content"],
                context_variables=context_variables)
        }]
        for msg in history:
            if (msg.get("sender") not in ["Report Agent"] and
                not any("add_memory" in call.get("function", {}).get("name", "")  # noqa: E501
                        for call in (msg.get("tool_calls") if msg.get("tool_calls")  # noqa: E501
                                     else []))):
                messages.append(msg)

        # --------------------------------
        # Debug
        # --------------------------------
        debug_print(
            debug,
            "Getting chat completion for...:",
            messages,
            brief=self.brief)

        # --------------------------------
        # Tools
        # --------------------------------
        tools = [function_to_json(f) for f in agent.functions if callable(f)]
        # hide context_variables from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params["required"]:
                params["required"].remove(__CTX_VARS_NAME__)

        # --------------------------------
        # Inference parameters
        # --------------------------------
        create_params = {
            "model": model_override or agent.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls
            create_params["tools"] = tools
            create_params["tool_choice"] = agent.tool_choice
            create_params["stream_options"] = {"include_usage": True}
            if not isinstance(agent, CodeAgent):  # Don't set temperature for CodeAgent  # noqa: E501
                create_params["temperature"] = 0.7
        # Refer to https://docs.litellm.ai/docs/completion/json_mode
        if agent.structured_output_class:
            # if providing the schema
            #
            # # NOTE: this is not working
            # # other than for Ollama-served models
            # create_params["response_format"] =
            #   agent.structured_output_class.model_json_schema()
            #
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
        if any(x in agent.model for x in ["claude"]):
            litellm.modify_params = True

        # --------------------------------
        # Inference
        # --------------------------------
        try:
            if os.getenv("OLLAMA", "").lower() == "true":
                litellm_completion = litellm.completion(
                    **create_params,
                    api_base=get_ollama_api_base(),
                    custom_llm_provider="openai"
                )
            else:
                try:
                    litellm_completion = litellm.completion(**create_params)
                except Exception:  # pylint: disable=W0718
                    create_params["api_base"] = get_ollama_api_base()
                    create_params["custom_llm_provider"] = "openai"
                    os.environ["OLLAMA"] = "true"
                    os.environ["OPENAI_API_KEY"] = "Placeholder"
                    litellm_completion = litellm.completion(**create_params)

        except litellm.exceptions.BadRequestError as e:
            if "LLM Provider NOT provided" in str(e):
                create_params["api_base"] = get_ollama_api_base()
                create_params["custom_llm_provider"] = "openai"
                os.environ["OLLAMA"] = "true"
                os.environ["OPENAI_API_KEY"] = "Placeholder"
                try:
                    litellm_completion = litellm.completion(**create_params)
                except litellm.exceptions.BadRequestError as e:  # pylint: disable=W0621,C0301 # noqa: E501
                    #
                    # CTRL C handler for ollama models
                    #
                    if "invalid message content type" in str(e):
                        create_params["messages"] = fix_message_list(
                            create_params["messages"])
                        litellm_completion = litellm.completion(
                            **create_params)
                    else:
                        raise e
            elif "An assistant message with 'tool_calls'" in str(e) or "`tool_use` blocks must be followed by a user message with `tool_result`" in str(e):  # noqa: E501 # pylint: disable=C0301
                print(f"Error: {str(e)}")
                # EDGE CASE: Report Agent CTRL C error
                # This fix CTRL C error when message list is incomplete
                # When a tool is not finished but the LLM generates a tool call
                create_params["messages"] = fix_message_list(
                    create_params["messages"])
                litellm_completion = litellm.completion(**create_params)
            else:
                raise e

        except litellm.exceptions.RateLimitError as e:
            print("Rate Limit Error:" + str(e))
            time.sleep(60)
            litellm_completion = litellm.completion(**create_params)

        # --------------------------------
        # Training data
        # --------------------------------
        if self.rec_training_data:
            self.rec_training_data.rec_training_data(
                create_params, litellm_completion)

        # --------------------------------
        # Token counts
        # --------------------------------
        if litellm_completion.usage:
            self.interaction_input_tokens = (
                litellm_completion.usage.prompt_tokens
            )
            self.interaction_output_tokens = (
                litellm_completion.usage.completion_tokens
            )
            if (hasattr(litellm_completion.usage, 'completion_tokens_details') and  # noqa: E501  # pylint: disable=C0103
                    litellm_completion.usage.completion_tokens_details and
                    hasattr(litellm_completion.usage.completion_tokens_details,
                            'reasoning_tokens') and
                    litellm_completion.usage.completion_tokens_details.reasoning_tokens):  # noqa: E501  # pylint: disable=C0103
                self.interaction_reasoning_tokens = (
                    litellm_completion.usage.completion_tokens_details.reasoning_tokens)  # noqa: E501  # pylint: disable=C0103
                self.total_reasoning_tokens += self.interaction_reasoning_tokens  # noqa: E501  # pylint: disable=C0103
            else:
                self.interaction_reasoning_tokens = 0

            self.total_input_tokens += (
                self.interaction_input_tokens
            )
            self.total_output_tokens += (
                self.interaction_output_tokens
            )

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
                    error_message = (
                        f"Failed to cast response to string: {result}. "
                        "Make sure agent functions return a string or "
                        f"Result object. Error: {str(e)}"
                    )  # noqa: E501 # pylint: disable=C0301
                    debug_print(debug, error_message, brief=self.brief)
                    raise TypeError(error_message) from e

    def handle_tool_calls(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements  # noqa: E501
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: dict,
        debug: bool,
        agent: Agent,
        n_turn: int = 0,
        message: str = ""
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

            # # NOTE: this becomes cumbersome to follow
            # if "transfer" in name or "handoff" in name:
            #     visualize_agent_graph(func())

            # pass context_variables to agent functions
            if __CTX_VARS_NAME__ in func.__code__.co_varnames:
                args[__CTX_VARS_NAME__] = context_variables
            if self.ctf and self.ctf_inside:
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
                except KeyboardInterrupt:
                    print("\nCtrl+C pressed")
                    raw_result = ("\n\nCOMMAND INTERRUPTED by user, "
                                  "probably cause you are bad")
                    return raw_result
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

    def process_interaction_codeagent(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements,too-many-branches,useless-return # noqa: E501
            self, active_agent, history,
            context_variables, debug, n_turn) -> None:
        """
        Process an interaction specifically for CodeAgent type.

        Args:
            active_agent: The CodeAgent instance
            history: List of previous messages
            context_variables: Dictionary of context variables
            debug: Debug level
            n_turn: Current turn number

        Returns:
            None: CodeAgent interactions always complete in one turn
        """
        # Call CodeAgent's specialized process_interaction method
        result, code, completion = active_agent.process_interaction(  # pylint: disable=unused-variable # noqa: E501
            cai_instance=self,
            messages=history,
            context_variables=context_variables,
            debug=False
        )

        # Create a message from the result
        message_content = result.value
        message = {
            "role": "assistant",
            "content": message_content,
            "sender": active_agent.name
        }

        # Add message to history
        history.append(message)

        # Print the message using the specialized CodeAgent output printer
        cli_print_codeagent_output(
            active_agent.name,
            message_content,
            code,
            n_turn,
            active_agent.model,
            debug,
            interaction_input_tokens=self.interaction_input_tokens,
            interaction_output_tokens=self.interaction_output_tokens,
            interaction_reasoning_tokens=self.interaction_reasoning_tokens,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            total_reasoning_tokens=self.total_reasoning_tokens
        )

        # Register in the graph
        self._graph.add_to_graph(graph.Node(
            name=active_agent.name,
            agent=active_agent,
            turn=n_turn,
            message=message,
            history=history
        ))

        # Update context variables from the result
        context_variables.update(result.context_variables)

        # Handle tool calls
        # NOTE: this doesn't seem to work very well
        # with CodeAgent, so we're disabling it for now
        #
        # if completion:
        #     completion_message = completion.choices[0].message
        #     if completion_message.tool_calls and execute_tools:
        #         partial_response = self.handle_tool_calls(
        #             completion_message.tool_calls,
        #             active_agent.functions,
        #             context_variables, debug, active_agent, n_turn,
        #             message=completion_message.content
        #         )
        #         return (partial_response.agent
        #                 if partial_response.agent
        #                 else active_agent)
        #

        # Turn complete
        #
        # NOTE: considered handoffs but they don't
        # seem to perform well when in combination
        # with code gen.
        #
        # For now, return the same CodeAgent
        return active_agent

    @exploit_logger.log_agent()
    def process_interaction(self, active_agent, history, context_variables,  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements,too-many-branches # noqa: E501
                            model_override, stream, debug,
                            execute_tools, n_turn) -> Tuple[Agent, None]:
        """
        Process an interaction with the AI agent.

        Args:
            active_agent: The agent to interact with
            history: List of previous messages
            context_variables: Dictionary of context variables
            model_override: Override the model specified in the agent
            stream: Whether to stream the response
            debug: Debug level
            execute_tools: Whether to execute tools
            n_turn: Current turn number

        Returns:
            Agent or None: Returns a new agent if there's a handoff,
                          or None if the turn is complete
        """
        # Special handling for CodeAgent
        if isinstance(active_agent, CodeAgent):
            return self.process_interaction_codeagent(
                active_agent, history, context_variables, debug, n_turn)

        # Regular agent processing (existing code)
        # get completion with current history, agent
        completion = self.get_chat_completion(
            agent=active_agent,
            history=history,
            context_variables=context_variables,
            model_override=model_override,
            stream=stream,
            debug=debug,
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
            if not isinstance(active_agent, StateAgent):
                cli_print_agent_messages(active_agent.name,
                                         message.content,
                                         n_turn,
                                         active_agent.model,
                                         debug)
            else:
                cli_print_state(active_agent.name,
                                message.content,
                                n_turn,
                                active_agent.model,
                                debug,
                                interaction_input_tokens=self.interaction_input_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                interaction_output_tokens=self.interaction_output_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                interaction_reasoning_tokens=self.interaction_reasoning_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                total_input_tokens=self.total_input_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                total_output_tokens=self.total_output_tokens,  # noqa: E501  # pylint: disable=line-too-long
                                total_reasoning_tokens=self.total_reasoning_tokens)  # noqa: E501  # pylint: disable=line-too-long
            debug_print(debug, "Ending turn.", brief=self.brief)

            # Register in the graph
            self._graph.add_to_graph(graph.Node(
                name=active_agent.name,
                agent=active_agent,
                turn=n_turn,
                message=message,
                history=history
            ))
            return None  # returning None to indicate
            # the turn is complete

        # handle function calls, updating context_variables, and switching
        # agents
        partial_response = self.handle_tool_calls(
            message.tool_calls, active_agent.functions,
            context_variables, debug, active_agent, n_turn,
            message=message.content
        )

        history.extend(partial_response.messages)

        # Register in the graph
        self._graph.add_to_graph(graph.Node(
            name=active_agent.name,
            agent=active_agent,
            turn=n_turn,
            message=message,
            history=history
        ), action=message.tool_calls)

        # update context variables
        context_variables.update(partial_response.context_variables)
        return (partial_response.agent
                if partial_response.agent
                else active_agent)

    def _get_turn_name(self):  # pylint disable=inconsistent-return-statements
        """Get the turn name based on the source."""
        return (
            "Turn" if self.source == "cli"
            else "🚩 " + os.getenv('CTF_NAME', 'test') + " @ " +
                 os.getenv('CI_JOB_ID', 'local')
        )

    @exploit_logger.log_response(_get_turn_name)
    def run(  # pylint: disable=too-many-arguments,dangerous-default-value,too-many-locals,too-many-statements,too-many-branches # noqa: E501
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
        # No need to initialize timer here since ya se hizo en __init__
        start_time = time.time()
        self.brief = brief
        self.init_len = len(messages)

        # visualize_agent_graph(agent)  # Do not show the agent
        #                               # graph for every run()

        # TODO: consider moving this outside of CAI  # pylint: disable=fixme  # noqa: E501
        # as the logging URL has a harcoded bit which is
        # dependent on the file that invokes it
        #
        if os.getenv("CAI_TRACING", "true").lower() == "true":
            # Get logging URL based on source
            logging_url = exploit_logger.get_logger_url(source=self.source)
            print(
                color("Logging URL: " + logging_url,
                      fg="white", bg="pink")
            )

        if self.rec_training_data:
            print(
                color(
                    "Logging at " + self.rec_training_data.filename,
                    fg="white",
                    bg="yellow"
                )
            )

        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        n_turn = 0

        while len(history) - self.init_len < max_turns and active_agent and self.total_cost < float(  # noqa: E501 # pylint: disable=line-too-long
                os.getenv("CAI_PRICE_LIMIT", "100")):
            # Needs to be inside while loop to avoid using the same function
            # for all iterations
            def agent_iteration(agent):
                return self.process_interaction(
                    agent,
                    history,
                    context_variables,
                    model_override,
                    stream,
                    debug,
                    execute_tools,
                    n_turn
                )

            try:
                # Memory agent iteration
                # If RAG is active and the turn is at a RAG interval, process
                # using the memory agent
                if (self.episodic_rag and
                        (n_turn != 0 and n_turn % self.rag_interval == 0)
                        and self.rag_online):

                    prev_agent = active_agent
                    active_agent = self.episodic_builder
                    agent_iteration(active_agent)
                    active_agent = prev_agent

                # Standard agent iteration
                active_agent = agent_iteration(active_agent)
                n_turn += 1
                if (self.semantic_rag and
                        (n_turn != 0 and n_turn % self.rag_interval == 0)
                        and self.rag_online):
                    prev_agent = active_agent
                    active_agent = self.semantic_builder
                    agent_iteration(active_agent)
                    active_agent = prev_agent

                # Stateful agent iteration
                # If the session is stateful, invoke the memory agent at
                # defined intervals
                if self.stateful:
                    self.state_interactions_count += 1
                    if (self.state_interactions_count
                            >= self.STATE_INTERACTIONS_INTERVAL):
                        prev_agent = active_agent
                        active_agent = transfer_to_state_agent()
                        agent_iteration(active_agent)
                        active_agent = prev_agent
                        self.state_interactions_count = 0

            except KeyboardInterrupt:
                print("\nCtrl+C pressed")
                break

            # Check if the flag is found in the last tool output
            # Accountability
            all_costs = calculate_conversation_cost(
                self.total_input_tokens, self.total_output_tokens, agent.model
            )
            self.total_cost = all_costs["total_cost"]
            if active_agent is None and self.force_until_flag and self.total_cost < float(  # noqa: E501 # pylint: disable=line-too-long
                    os.getenv("CAI_PRICE_LIMIT", "1")):
                # Check if the flag is found in the last tool output
                flag_found, flag = check_flag(
                    history[-1]["content"], self.ctf, self.challenge)

                # # Check if flag is found anywhere in history
                # for message in history:
                #     flag_found, _ = check_flag(message["content"],
                #                                self.ctf,
                #                                self.challenge)

                if flag_found:
                    break

                # If flag is not found, continue with the next turn
                # adding to the history that the flag was not found
                history.append({
                    "role": "user",
                    "content": (
                        "Turn finished, checking whether flag is found. "
                        f"Flag detected: {flag} is not the expected one.\n"
                        "Keep looking for it and reflect on your previous "
                        "steps."
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
