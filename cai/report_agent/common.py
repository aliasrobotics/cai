"""
This module provides common functionality for report agents.
Contains helper functions for generating report instructions and
handling previous reports.
"""


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
