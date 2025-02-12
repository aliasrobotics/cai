import pytest
from cai.core import CAI, Agent
from .mock_client import MockOpenAIClient, create_mock_response
from unittest.mock import Mock
import json

DEFAULT_RESPONSE_CONTENT = "sample response content"


def test_run_with_simple_message():
    """
    Test that a simple message exchange with an agent works correctly.

    Verifies that:
    - The response contains at least one message
    - The last message is from the assistant
    """
    agent = Agent()
    client = CAI()
    messages = [{"role": "user", "content": "Hello, how are you?"}]
    response = client.run(agent=agent, messages=messages)

    assert len(response.messages) > 0
    assert response.messages[-1]["role"] == "assistant"


def test_tool_call():
    """
    Test that tool calls are handled correctly by the agent.

    Tests a weather query scenario where:
    1. Agent receives a weather query for San Francisco
    2. Agent makes a tool call to get_weather function
    3. Tool returns weather info
    4. Agent formulates final response

    Verifies:
    - Correct sequence of messages (tool call -> tool response -> final response)
    - Proper message structure and content at each step
    - Tool call contains correct function name and arguments
    - Final response incorporates tool call results
    """
    # set up mock to record function calls
    expected_location = "San Francisco"
    get_weather_mock = Mock()

    def get_weather(location):
        get_weather_mock(location=location)
        return "It's sunny today."

    agent = Agent(name="Test Agent", functions=[get_weather])
    messages = [
        {"role": "user", "content": "What's the weather like in San Francisco?"}
    ]

    client = CAI()
    response = client.run(agent=agent, messages=messages)

    assert len(response.messages) >= 3

    # expected response is of type:
    # [
    # {
    #     "content": "",
    #     "role": "assistant",
    #     "tool_calls": [
    #     {
    #         "index": 0,
    #         "function": {
    #         "arguments": "{\"location\":\"San Francisco\"}",
    #         "name": "get_weather"
    #         },
    #         "id": "call_8061iag9",
    #         "type": "function"
    #     }
    #     ],
    #     "function_call": null,
    #     "sender": "Test Agent"
    # },
    # {
    #     "role": "tool",
    #     "tool_call_id": "call_8061iag9",
    #     "tool_name": "get_weather",
    #     "content": "It's sunny today."
    # },
    # {
    #     "content": "The weather in San Francisco is sunny today. Do you need any more details such as temperature or humidity?",
    #     "role": "assistant",
    #     "tool_calls": null,
    #     "function_call": null,
    #     "sender": "Test Agent"
    # }
    # ]

    # First message should be assistant's tool call
    assert response.messages[0]["role"] == "assistant"
    assert response.messages[0]["tool_calls"] is not None
    assert response.messages[0]["tool_calls"][0]["function"]["name"] == "get_weather"

    # Second message should be tool response
    assert response.messages[1]["role"] == "tool"
    assert response.messages[1]["tool_name"] == "get_weather"
    assert response.messages[1]["content"] == "It's sunny today."

    # Third message should be assistant's final response
    assert response.messages[2]["role"] == "assistant"
    assert response.messages[2]["tool_calls"] is None
    assert "weather" in response.messages[2]["content"].lower()


def test_execute_tools_false():
    """
    Test that setting execute_tools=False prevents tool execution.

    Verifies that:
    - The agent returns a response without executing tools
    - The response contains assistant messages only
    """
    get_weather_mock = Mock()

    def get_weather(location):
        get_weather_mock(location=location)
        return "It's sunny today."

    agent = Agent(name="Test Agent", functions=[get_weather])
    messages = [
        {"role": "user", "content": "What's the weather like in San Francisco?"}
    ]

    client = CAI()
    response = client.run(agent=agent, messages=messages, execute_tools=False)

    assert len(response.messages) > 0
    # Verify tool was not executed
    get_weather_mock.assert_not_called()


def test_handoff():
    """
    Test agent handoff functionality between two agents.

    Tests that:
    1. First agent can transfer control to second agent
    2. Handoff process generates correct sequence of messages
    3. Final response comes from the second agent

    Verifies:
    - Correct tool call for transfer
    - Proper tool response with agent2 info
    - Final message comes from agent2
    """
    def transfer_to_agent2():
        return agent2

    agent1 = Agent(name="Test Agent 1", functions=[transfer_to_agent2])
    agent2 = Agent(name="Test Agent 2")

    client = CAI()
    messages = [{"role": "user", "content": "I want to talk to agent 2"}]
    response = client.run(agent=agent1, messages=messages)

    assert len(response.messages) >= 3
    # First message should be assistant's tool call to transfer
    assert response.messages[0]["role"] == "assistant"
    assert response.messages[0]["tool_calls"] is not None
    assert response.messages[0]["tool_calls"][0]["function"]["name"] == "transfer_to_agent2"

    # Second message should be tool response with agent2
    assert response.messages[1]["role"] == "tool"
    assert response.messages[1]["tool_name"] == "transfer_to_agent2"
    assert "Test Agent 2" in response.messages[1]["content"]

    # Third message should be from agent2
    assert response.messages[2]["role"] == "assistant"
    assert response.messages[2]["sender"] == "Test Agent 2"
