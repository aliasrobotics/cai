"""
This module provides common functionality for report agents.
Contains helper functions for generating report instructions and
handling previous reports.
"""
import time
import os
from mako.template import Template  # pylint: disable=import-error


def get_base_instructions(previous_reports):
    """
    Get base instructions for report agents.

    Args:
        previous_reports: List of previous reports to consider

    Returns:
        str: Base instructions for report agents
    """
    previous_reports_str = ""
    if previous_reports:
        previous_reports_str = "\nPrevious reports to consider:\n"
        for i, report in enumerate(previous_reports, 1):
            previous_reports_str += f"\nReport {i}:\n{report}\n"

    return f"""
    {previous_reports_str}

    IMPORTANT: Build a new report upon the previous report.
    Avoid duplicate information
    """


def create_report(report_data: dict, template: str):
    """
    Create a report from a list of messages, merging content from
    Report Agent messages.

    Args:
        report_data (dict): A dictionary containing the
                         report agent's response messages
        template (str): path of the template.md

    Returns:
        None: The function does not return a value. It generates a
              markdown report file and saves it in the './report'
              directory.
    """

    template = Template(
        filename=template)  # nosec: B702
    report_output = template.render(**report_data)
    # Render and seve the template in ./report
    report_output = template.render(**report_data)
    report_dir = "./report"
    os.makedirs(report_dir, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    save_path = f"Report_{timestamp}.md"
    report_path = os.path.join(report_dir, save_path)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_output)
    print(f"Report generated at: {report_path}")
