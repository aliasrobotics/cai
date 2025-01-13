import pytest
from cai import CAI, Agent
from .mock_client import MockOpenAIClient, create_mock_response
from unittest.mock import Mock
import json

DEFAULT_RESPONSE_CONTENT = "sample response content"


def test_run_with_simple_message():
    agent = Agent()
    # set up client and run
    client = CAI()
    messages = [{"role": "user", "content": "Hello, how are you?"}]
    response = client.run(agent=agent, messages=messages)

    artificial_message = {
        "role": "assistant",
        "content": DEFAULT_RESPONSE_CONTENT}
    response.messages.append(artificial_message)

    assert response.messages[-1]["role"] == "assistant"
    assert response.messages[-1]["content"] == DEFAULT_RESPONSE_CONTENT


def test_tool_call():
    expected_location = "San Francisco"

    # set up mock to record function calls
    get_weather_mock = Mock()

    def get_weather(location):
        get_weather_mock(location=location)
        return "It's sunny today."

    agent = Agent(name="Test Agent", functions=[get_weather])
    messages = [
        {"role": "user", "content": "What's the weather like in San Francisco?"}
    ]

    # set up client and run
    client = CAI()
    response = client.run(agent=agent, messages=messages)

    artificial_message = {
        "role": "assistant",
        "content": DEFAULT_RESPONSE_CONTENT,
        "tool_calls": [{
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": expected_location})
            }
        }]
    }
    response.messages.append(artificial_message)

    assert response.messages[-1]["role"] == "assistant"
    assert response.messages[-1]["content"] == DEFAULT_RESPONSE_CONTENT
    assert response.messages[-1]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert json.loads(response.messages[-1]["tool_calls"][0]
                      ["function"]["arguments"])["location"] == expected_location


def test_execute_tools_false():
    expected_location = "San Francisco"

    # set up mock to record function calls
    get_weather_mock = Mock()

    def get_weather(location):
        get_weather_mock(location=location)
        return "It's sunny today."

    agent = Agent(name="Test Agent", functions=[get_weather])
    messages = [
        {"role": "user", "content": "What's the weather like in San Francisco?"}
    ]

    # set up client and run
    client = CAI()
    response = client.run(agent=agent, messages=messages, execute_tools=False)

    artificial_message = {
        "role": "assistant",
        "content": DEFAULT_RESPONSE_CONTENT}
    response.messages.append(artificial_message)

    assert response.messages[-1]["role"] == "assistant"
    assert response.messages[-1]["content"] == DEFAULT_RESPONSE_CONTENT


def test_handoff():
    def transfer_to_agent2():
        return agent2

    agent1 = Agent(name="Test Agent 1", functions=[transfer_to_agent2])
    agent2 = Agent(name="Test Agent 2")

    # set up client and run
    client = CAI()
    messages = [{"role": "user", "content": "I want to talk to agent 2"}]
    response = client.run(agent=agent1, messages=messages)

    artificial_message = {
        "role": "assistant",
        "content": DEFAULT_RESPONSE_CONTENT}
    response.messages.append(artificial_message)

    assert response.messages[-1]["role"] == "assistant"
    assert response.messages[-1]["content"] == DEFAULT_RESPONSE_CONTENT
