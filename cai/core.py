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
# Package/library imports
import time
from openai import OpenAI  # pylint: disable=import-error
from cai.logger import exploit_logger

# Local imports
from .util import function_to_json, debug_print, merge_chunk
from .types import (
    Agent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Function,
    Response,
    Result,
)

__CTX_VARS_NAME__ = "context_variables"


class CAI:
    """
    Cybersecurity AI (CAI) object
    """

    def __init__(self,
                 ctf=None):
        self.ctf = ctf
        self.brief = False

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
            # "temperature": 0.0,
        }

        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls
            create_params["tools"] = tools
            create_params["tool_choice"] = agent.tool_choice
        
        return litellm.completion(**create_params)


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

    def handle_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        context_variables: dict,
        debug: bool,
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
            args = json.loads(tool_call.function.arguments)
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
            raw_result = function_map[name](**args)

            result: Result = self.handle_function_result(raw_result, debug)
            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "tool_name": name,
                    "content": result.value,
                }
            )
            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent

        return partial_response

    def run_and_stream(  # pylint: disable=too-many-arguments,too-many-locals,dangerous-default-value  # noqa: E501
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
    ):
        """
        Run the cai and stream the results.

        The key difference from run() is that this streams results
        incrementally, while run() returns everything at once.
        """
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        while len(history) - init_len < max_turns:

            message = {
                "content": "",
                "sender": agent.name,
                "role": "assistant",
                "function_call": None,
                "tool_calls": defaultdict(
                    lambda: {
                        "function": {"arguments": "", "name": ""},
                        "id": "",
                        "type": "",
                    }
                ),
            }

            # get completion with current history, agent
            completion = self.get_chat_completion(
                agent=active_agent,
                history=history,
                context_variables=context_variables,
                model_override=model_override,
                stream=True,
                debug=debug,
            )

            yield {"delim": "start"}
            for chunk in completion:
                delta = json.loads(chunk.choices[0].delta.json())
                if delta["role"] == "assistant":
                    delta["sender"] = active_agent.name
                yield delta
                delta.pop("role", None)
                delta.pop("sender", None)
                merge_chunk(message, delta)
            yield {"delim": "end"}

            message["tool_calls"] = list(
                message.get("tool_calls", {}).values())
            if not message["tool_calls"]:
                message["tool_calls"] = None
            debug_print(
                debug,
                "Received completion:",
                message,
                brief=self.brief)
            history.append(message)

            if not message["tool_calls"] or not execute_tools:
                debug_print(debug, "Ending turn.", brief=self.brief)
                break

            # convert tool_calls to objects
            tool_calls = []
            for tool_call in message["tool_calls"]:
                function = Function(
                    arguments=tool_call["function"]["arguments"],
                    name=tool_call["function"]["name"],
                )
                tool_call_object = ChatCompletionMessageToolCall(
                    id=tool_call["id"], function=function, type=tool_call["type"]  # noqa: E501
                )
                tool_calls.append(tool_call_object)

            # handle function calls, updating context_variables, and switching
            # agents
            partial_response = self.handle_tool_calls(
                tool_calls, active_agent.functions, context_variables, debug
            )
            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            if partial_response.agent:
                active_agent = partial_response.agent

        yield {
            "response": Response(
                messages=history[init_len:],
                agent=active_agent,
                context_variables=context_variables,
            )
        }

    @exploit_logger.log_response("CAI")
    # @exploit_logger.log_response(
    #         "🚩" + os.getenv("CTF_NAME") + " @ " + os.getenv("CI_JOB_ID", "local")  # noqa: E501
    # )
    def run(  # pylint: disable=too-many-arguments,dangerous-default-value, too-many-locals # noqa: E501
        self,
        agent: Agent,
        messages: List,
        context_variables: dict = {},
        model_override: str = None,
        stream: bool = False,
        debug: bool = False,
        max_turns: int = float("inf"),
        execute_tools: bool = True,
        brief: bool = False,
    ) -> Response:
        """
        Run the cai and return the final response along
        with execution time in seconds.
        """
        start_time = time.time()
        self.brief = brief
        if stream:
            return self.run_and_stream(
                agent=agent,
                messages=messages,
                context_variables=context_variables,
                model_override=model_override,
                debug=debug,
                max_turns=max_turns,
                execute_tools=execute_tools,
            )
        active_agent = agent
        context_variables = copy.deepcopy(context_variables)
        history = copy.deepcopy(messages)
        init_len = len(messages)

        @exploit_logger.log_agent()
        def process_turn(self, active_agent, history, context_variables,
                         model_override, stream, debug, execute_tools):
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
                debug_print(debug, "Ending turn.", brief=self.brief)
                return None

            # handle function calls, updating context_variables, and switching
            # agents
            partial_response = self.handle_tool_calls(
                message.tool_calls, active_agent.functions,
                context_variables, debug
            )

            history.extend(partial_response.messages)
            context_variables.update(partial_response.context_variables)
            return (partial_response.agent
                    if partial_response.agent
                    else active_agent)

        while len(history) - init_len < max_turns and active_agent:
            active_agent = process_turn(
                self,
                active_agent,
                history,
                context_variables,
                model_override,
                stream,
                debug,
                execute_tools
            )
            if active_agent is None:
                break

        execution_time = time.time() - start_time
        return Response(
            messages=history[init_len:],
            agent=active_agent,
            context_variables=context_variables,
            time=execution_time
        )
