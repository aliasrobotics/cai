import pytest
import os
import json
from pydantic import ValidationError
from cai.core import CAI
from extensions.report.nis2.nis2_report_agent import reporter_agent  # pylint: disable=import-error
from cai.datarecorder import load_history_from_jsonl # pylint: disable=import-error # noqa: E501


# Test for NIS2Report Model
def test_nis2_report_agent():

    history = load_history_from_jsonl("tests/agents/alias_pentesting.jsonl")
    messages=[{"role": "user", "content": "Do a report from " +
                            "\n".join(msg['content'] for msg in history if msg.get('content') is not None)}]
    client = CAI()
    response = client.run(
        agent=reporter_agent,
        messages=messages,
        debug=float(os.getenv('CAI_DEBUG', '2')),
        max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
        brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')
   
    content_dict = json.loads(response.messages[0]['content'])

    # Extraer el valor de 'final_flag'
    client = content_dict.get("client")
    assert client == "Alias Robotics", f"Expected client = Alias Robotics but got {client}"
