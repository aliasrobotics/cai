from cai.core import CAI, Agent

client = CAI()

english_agent = Agent(
    model="qwen2.5:14b",
    name="English Agent",
    instructions="You only speak English. If another language is detected, invoke transfer_to_spanish_agent.",
    # instructions="You only speak English.",
    # tool_choice="required",  # not working with ollama and qwen2.5
)

spanish_agent = Agent(
    name="Spanish Agent",
    instructions="You only speak Spanish.",
)

german_agent = Agent(
    name="German Agent",
    instructions="Sie sprechen nur Deutsch.",
)


def transfer_to_spanish_agent():
    """Transfer spanish speaking users immediately."""
    return spanish_agent


def transfer_to_german_agent():
    """Transfer german speaking users immediately."""
    return german_agent


english_agent.functions.append(transfer_to_spanish_agent)
# english_agent.functions.append(transfer_to_german_agent)
spanish_agent.functions.append(transfer_to_german_agent)

# messages = [{"role": "user", "content": "Hola. ¿Como estás?"}]
messages = [{"role": "user", "content": "Hallo. Wie geht es dir?"}]

response = client.run(agent=english_agent, messages=messages, debug=True)
print(response.messages[-1]["content"])
