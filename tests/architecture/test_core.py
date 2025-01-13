import pytest
from cai import CAI, Agent
from .mock_client import MockOpenAIClient, create_mock_response
from unittest.mock import Mock
import json

DEFAULT_RESPONSE_CONTENT = "sample response content"


def test_run_with_simple_message():
    agent = Agent()
    client = CAI()
    messages = [{"role": "user", "content": "Hello, how are you?"}]
    response = client.run(agent=agent, messages=messages)

    assert len(response.messages) > 0
    assert response.messages[-1]["role"] == "assistant"


def test_tool_call():
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

    assert len(response.messages) > 0
    assert response.messages[-1]["role"] == "assistant"


def test_execute_tools_false():
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
    assert response.messages[-1]["role"] == "assistant"


def test_handoff():
    def transfer_to_agent2():
        return agent2

    agent1 = Agent(name="Test Agent 1", functions=[transfer_to_agent2])
    agent2 = Agent(name="Test Agent 2")

    client = CAI()
    messages = [{"role": "user", "content": "I want to talk to agent 2"}]
    response = client.run(agent=agent1, messages=messages)

    assert len(response.messages) > 0
    assert response.messages[-1]["role"] == "assistant"
