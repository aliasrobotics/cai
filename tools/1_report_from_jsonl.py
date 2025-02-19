"""
This script is used to generate a report from a JSONL file.

Usage:
    # Create a report from tests/agents/alias_pentesting.jsonl
    #   pentesting JSONL file (defaults to this one)
    $ CAI_REPORT=pentesting python3 tools/1_report_from_jsonl.py
"""


import json
import os
import sys
from importlib.resources import files

# Set tracing to false by default - must be set before importing CAI
os.environ['CAI_TRACING'] = 'false'

from cai.core import CAI  # pylint: disable=import-error
from cai.datarecorder import load_history_from_jsonl  # pylint: disable=import-error # noqa: E501

from caiextensions.report.common import create_report  # pylint: disable=import-error # noqa: E501


if __name__ == "__main__":
    # Get input file from command line arg or use default
    user_input = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "tests",
                "agents",
                "alias_pentesting.jsonl"
            )
        )
    )

    # Check if the file path exists
    if not os.path.isfile(user_input):
        print("The file does not exist. Exit ...")
        sys.exit(1)  # Using sys.exit() instead of exit()

    history = load_history_from_jsonl(user_input)

    # Get the report type from the environment variable
    # or use "ctf" by default
    report_type = os.getenv("CAI_REPORT", "ctf").lower()

    if report_type:
        if report_type == "pentesting":
            # pylint: disable=import-outside-toplevel
            from caiextensions.report.pentesting.pentesting_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            TEMPLATE = str(
                files('caiextensions.report.pentesting') /
                'template.md')
        elif report_type == "nis2":
            # pylint: disable=import-outside-toplevel
            from caiextensions.report.nis2.nis2_report_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            TEMPLATE = str(files('caiextensions.report.nis2') / 'template.md')
        else:
            # pylint: disable=import-outside-toplevel
            from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent  # pylint: disable=import-error # noqa: E501
            TEMPLATE = str(files('caiextensions.report.ctf') / 'template.md')

        client = CAI()

        # Create message content by joining non-None messages
        MESSAGE_CONTENT = "Do a report from " + "\n".join(
            msg['content']
            for msg in history
            if msg.get('content') is not None
        )

        response_report = client.run(
            agent=reporter_agent,
            messages=[{
                "role": "user",
                "content": MESSAGE_CONTENT
            }],
            debug=0
        )

        report_data = json.loads(response_report.messages[0]['content'])
        report_data["history"] = json.dumps(history, indent=4)
        create_report(report_data, TEMPLATE)
