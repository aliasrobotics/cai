import json
import os
from cai.core import CAI  # pylint: disable=import-error
from extensions.report.common import create_report  # pylint: disable=import-error # noqa: E501

def load_history_from_jsonl(file_path):
    """
    Load conversation history from a JSONL file and
    return it as a list of messages.

    Args:
        file_path (str): The path to the JSONL file.

    Returns:
        list: A list of messages extracted from the JSONL file.
    """
    history = []
    max_length = 0
    with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if isinstance(record, dict) and "messages" in record and isinstance(record["messages"], list):
                    if len(record["messages"]) > max_length:
                        max_length = len(record["messages"])
                        history = record["messages"]
    return history




if __name__ == "__main__":
    #user_input = input("Please enter the path to the JSONL fot the report" )
    user_input="tests/agents/alias_pentesting.jsonl"
    # Check if the file path exists
    if not os.path.isfile(user_input):
        print("The file does not exist. Exit ...")
        exit(-1)
  
    history=load_history_from_jsonl(user_input)

    if os.getenv("CAI_REPORT"):
        if os.getenv("CAI_REPORT", "ctf").lower() == "pentesting":
            from extensions.report.pentesting.pentesting_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            template = "extensions/report/pentesting/template.md"
        elif os.getenv("CAI_REPORT", "ctf").lower() == "nis2":
            from extensions.report.pentesting.pentesting_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            template = "extensions/report/nis2/template.md"
        else:
            from extensions.report.ctf.ctf_reporter_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            template = "extensions/report/ctf/template.md"
        
        model = os.getenv('CTF_MODEL', "qwen2.5:14b")
        state_agent = None
        stateful = os.getenv('CAI_STATE', "false").lower() == "true"
        if stateful:
            from cai.state.pydantic import state_agent  # pylint: disable=import-error,import-outside-toplevel # noqa: E501
            state_agent.model = model  # set model 
        client = CAI(state_agent=state_agent, force_until_flag=False)
        response_report = client.run(
                agent=reporter_agent,
                 messages=[{"role": "user", "content": "Do a report from " +
                            "\n".join(
                                msg['content'] for msg in history
                                if msg.get('content') is not None
                            )}],
                debug=float(os.getenv('CAI_DEBUG', '2')),
                max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
                )

        report_data = json.loads(response_report.messages[0]['content'])
        report_data["history"] = json.dumps(history, indent=4)
        create_report(report_data, template)