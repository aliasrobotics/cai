from cai import CAI, Agent
import pentestperf as ptt
from wasabi import color

client = CAI()


def run_ctf(ctf, command, stdout=True):
    try:
        # Ensure the command is executed in a shell that supports command
        # chaining
        output = ctf.get_shell(command)
        # exploit_logger.log_ok()

        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except Exception as e:
        print(color(f"Error executing CTF command: {e}", fg="red"))
        # exploit_logger.log_error(str(e))
        return f"Error executing CTF command: {str(e)}"


def list_dir(path: str, args: str) -> str:
    """
    List the contents of a directory.

    Args:
        path: The directory path to list contents from
        args: Additional arguments to pass to the ls command

    Returns:
        str: The output of running the ls command
    """
    global ctf
    command = f'ls {path} {args}'
    return run_ctf(ctf, command)


def cat_file(args: str, file_path: str) -> str:
    """
    Display the contents of a file.

    Args:
        args: Additional arguments to pass to the cat command
        file_path: Path to the file to display contents of

    Returns:
        str: The output of running the cat command
    """
    global ctf
    command = f'cat {args} {file_path} '
    return run_ctf(ctf, command)

# def flag_checker(flag: str) -> str:
#      """
#      This tool is used to check if the guessed flag is valid.
#      """
#      if ctf.get_flag(ctf.get_challenges()[challenge]) == flag:
#         return "Flag Found: " + flag
#      else:
#         return "Flag Not Found: " + flag


listing_agent = Agent(
    model="qwen2.5:14b",
    name="A file listing tool",
    instructions="You are an agent tailored to list and read files within a file system.",
    # parallel_tool_calls=True,
)

# flag_extractor = Agent(
#     model="qwen2.5:14b",
#     name="A flag extractor",
#     instructions="You are an agent tailored to extract only the flag from a given content.",
# )

# def transfer_to_flag_extractor_agent():
#     """Transfer to flag extractor."""
#     return flag_extractor


#######################################

# PentestPerf setup for "picoctf_static_flag"
ctf = ptt.ctf(
    "picoctf_static_flag",
    subnet="192.168.9.0/24",
    container_name="ancient",
    ip_address="192.168.9.52",
)
ctf.start_ctf()
flag = ctf.get_flag()


listing_agent.functions.append(list_dir)
listing_agent.functions.append(cat_file)
# listing_agent.functions.append(flag_checker)

challenges = list(ctf.get_challenges().keys())
challenge = challenges[0]

messages = [{"role": "user", "content": "Instructions: " + ctf.get_instructions()
             + "\nChallenge: " + ctf.get_challenges()[challenge]
             + "\nTechniques: " + ctf.get_techniques()
             + "\nExtract and return only the flag"}]
response = client.run(agent=listing_agent, messages=messages, debug=True)
print(response.messages[-1]["content"])

# if ctf.check_flag(response.messages[-1]["content"], ctf.get_challenges()[challenge]):
#    print(color(f"Flag found: {response.messages[-1]['content']}", fg="green"))

ctf.stop_ctf()
