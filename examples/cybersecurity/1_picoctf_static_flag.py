from cai import CAI, Agent
import pentestperf as ptt

client = CAI()

english_agent = Agent(
    model="qwen2.5:14b",
    name="A file listing tool",
    instructions="You only speak English. If another language is detected, invoke transfer_to_spanish_agent.",
    # instructions="You only speak English.",
    # tool_choice="required",  # not working with ollama and qwen2.5
)

spanish_agent = Agent(
    name="Spanish Agent",
    instructions="You only speak Spanish.",
)


def transfer_to_spanish_agent():
    """Transfer spanish speaking users immediately."""
    return spanish_agent


english_agent.functions.append(transfer_to_spanish_agent)
messages = [{"role": "user", "content": "Hola, cómo estás?"}]


response = client.run(agent=english_agent, messages=messages, debug=True)
print(response.messages[-1]["content"])


# # PentestPerf setup for "picoctf_static_flag"
# ctf = ptt.ctf(
#         "picoctf_static_flag",
#         subnet="192.168.9.0/24",
#         container_name="ancient",
#         ip_address="192.168.9.52",
#     )
# ctf.start_ctf()
# flag = ctf.get_flag()
# ctf.stop_ctf()
