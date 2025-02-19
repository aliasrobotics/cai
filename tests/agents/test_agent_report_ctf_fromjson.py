import pytest
import os
import json
#from caiextensions.report.common.nis2.nis2 import load_history_from_jsonl
from cai.core import CAI
from caiextensions.report.common.ctf.ctf_reporter_agent import reporter_agent # pylint: disable=import-error  
from cai.datarecorder import load_history_from_jsonl # pylint: disable=import-error # noqa: E501


# Set tracing to false by default
os.environ['CAI_TRACING'] = 'false'

# Test for NIS2Report Model
def test_nis2_report_agent():

    history = load_history_from_jsonl(os.path.join(os.path.dirname(__file__), "kiddoctf.jsonl"))
    messages=[{"role": "user", "content": "Do a report from " +
                            "\n".join(msg['content'] for msg in history if msg.get('content') is not None)}]
    client = CAI()
    response = client.run(
        agent=reporter_agent,
        messages=messages,
        debug=0)
   
    content_dict = json.loads(response.messages[0]['content'])

    # Extraer el valor de 'final_flag'
    final_flag = content_dict.get("final_flag")
    assert final_flag == "FLAG2_42448", f"Expected FLAG2_42448 but got {final_flag}"
