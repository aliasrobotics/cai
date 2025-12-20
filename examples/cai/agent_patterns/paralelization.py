"""
Parallelization Pattern:
This pattern runs multiple agents in parallel to perform a task, generating different responses. 
Afterward, a separate agent is used to evaluate and pick the best result. 
"""

import asyncio
import os
import asyncio
from openai import AsyncOpenAI
from cai.sdk.agents import function_tool
from cai.tools.common import run_command
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel, HandoffInputData, Runner, function_tool, handoff, trace, ItemHelpers
from cai.sdk.agents.extensions import handoff_filters



@function_tool
def execute_cli_command(command: str) -> str:
    return run_command(command)
# Create the CTF agent
ctf_agent = Agent(
    name="CTF agent",
    description="Agent focused on conquering security challenges",
    instructions="You are a Cybersecurity expert Leader facing a CTF",
    tools=[
        execute_cli_command,
    ],
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
        openai_client=AsyncOpenAI(),
    )
)

# An agent to pick the best solution after multiple attempts
best_solution_picker = Agent(
    name="best_solution_picker",
    description="Agent focused on  picking the best security solution",
    instructions="You pick the best security solution from the given attempts.",
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
        openai_client=AsyncOpenAI(),
    )
)

async def main():
    # Define your CTF challenge
    challenge = input("Enter the CTF challenge you're facing:\n\n")

    # Ensure the entire workflow is a single trace
    res_1, res_2, res_3 = await asyncio.gather(
            Runner.run(
                ctf_agent,
                challenge,
            ),
            Runner.run(
                ctf_agent,
                challenge,
            ),
            Runner.run(
                ctf_agent,
                challenge,
            ),
        )

        # Gather the results from the CTF attempts
    outputs = [
            ItemHelpers.text_message_outputs(res_1.new_items),
            ItemHelpers.text_message_outputs(res_2.new_items),
            ItemHelpers.text_message_outputs(res_3.new_items),
        ]

        # Show all the results
    results = "\n\n".join(outputs)
    print(f"\n\nCTF Results:\n\n{results}")

        # Run the best solution picker agent
    best_solution = await Runner.run(
            best_solution_picker,
            f"Input: {challenge}\n\nResults:\n{results}",
    )

    print("\n\n-----")
    print(f"Best solution: {best_solution.final_output}")

if __name__ == "__main__":
    asyncio.run(main())