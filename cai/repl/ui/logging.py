"""
Module for CAI REPL session logging.
"""
from pathlib import Path


def setup_session_logging():
    """
    Set up session logging.

    Returns:
        Tuple of (history_file, session_log, log_interaction function)
    """
    # Setup history file
    history_dir = Path.cwd() / ".cai"
    history_dir.mkdir(exist_ok=True)
    history_file = history_dir / "history.txt"

    # # Setup session log file
    # session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # session_log = history_dir / f"session_{session_id}.log"

    # # Function to log interactions
    # def log_interaction(role, content):
    #     with open(session_log, "a", encoding="utf-8") as f:
    #         f.write(
    #             f"\n[{
    #                 datetime.datetime.now().strftime('%H:%M:%S')}] {
    #                 role.upper()}:\n")
    #         f.write(f"{content}\n")

    # return history_file, session_log, log_interaction
    return history_file
