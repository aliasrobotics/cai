"""
Data recorder
"""

import os  # pylint: disable=import-error
from datetime import datetime
import json
import socket
import urllib.request
import getpass
import platform
from urllib.error import URLError
import pytz  # pylint: disable=import-error
from cai.util import get_active_time, get_idle_time


class DataRecorder:  # pylint: disable=too-few-public-methods
    """
    Records training data from litellm.completion
    calls in OpenAI-like JSON format.

    Stores both input messages and completion
    responses during execution in a single JSONL file.
    """

    def __init__(self, workspace_name: str | None = None):
        """
        Initializes the DataRecorder.

        Args:
            workspace_name (str | None): The name of the current workspace.
        """
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # Get current username
        try:
            username = getpass.getuser()
        except Exception:  # pylint: disable=broad-except
            username = "unknown"

        # Get operating system and version information
        try:
            os_name = platform.system().lower()
            os_version = platform.release()
            os_info = f"{os_name}_{os_version}"
        except Exception:  # pylint: disable=broad-except
            os_info = "unknown_os"

        # Check internet connection and get public IP
        public_ip = "127.0.0.1"
        try:
            # Quick connection check with minimal traffic
            socket.create_connection(("1.1.1.1", 53), timeout=1)

            # If connected, try to get public IP
            try:
                # Using a simple and lightweight service
                with urllib.request.urlopen(  # nosec: B310
                    "https://api.ipify.org",
                    timeout=2
                ) as response:
                    public_ip = response.read().decode('utf-8')
            except (URLError, socket.timeout):
                # Fallback to another service if the first one fails
                try:
                    with urllib.request.urlopen(  # nosec: B310
                        "https://ifconfig.me",
                        timeout=2
                    ) as response:
                        public_ip = response.read().decode('utf-8')
                except (URLError, socket.timeout):
                    # If both services fail, keep the default value
                    pass
        except (OSError, socket.timeout, socket.gaierror):
            # No internet connection, keep the default value
            pass

        # Create filename with username, OS info, and IP
        timestamp = datetime.now().astimezone(
            pytz.timezone("Europe/Madrid")).strftime("%Y%m%d_%H%M%S")
        base_filename = f'cai_{timestamp}_{username}_{os_info}_{public_ip.replace(".", "_")}.jsonl'

        if workspace_name:
            self.filename = os.path.join(
                log_dir, f'{workspace_name}_{base_filename}'
            )
        else:
            self.filename = os.path.join(log_dir, base_filename)

        # Inicializar el coste total acumulado
        self.total_cost = 0.0

    def rec_training_data(self, create_params, msg, total_cost=None) -> None:
        """
        Records a single training data entry to the JSONL file

        Args:
            create_params: Parameters used for the LLM call
            msg: Response from the LLM
            total_cost: Optional total accumulated cost from CAI instance
        """
        request_data = {
            "model": create_params["model"],
            "messages": create_params["messages"],
            "stream": create_params["stream"]
        }
        if "tools" in create_params:
            request_data.update({
                "tools": create_params["tools"],
                "tool_choice": create_params["tool_choice"],
            })

        # Obtener el coste de la interacción
        interaction_cost = 0.0
        if hasattr(msg, "cost"):
            interaction_cost = float(msg.cost)

        # Usar el total_cost proporcionado o actualizar el interno
        if total_cost is not None:
            self.total_cost = float(total_cost)
        else:
            self.total_cost += interaction_cost

        # Get timing metrics (without units, just numeric values)
        active_time_str = get_active_time()
        idle_time_str = get_idle_time()

        # Convert string time to seconds for storage
        def time_str_to_seconds(time_str):
            if "h" in time_str:
                parts = time_str.split()
                hours = float(parts[0].replace("h", ""))
                minutes = float(parts[1].replace("m", ""))
                seconds = float(parts[2].replace("s", ""))
                return hours * 3600 + minutes * 60 + seconds
            if "m" in time_str:
                parts = time_str.split()
                minutes = float(parts[0].replace("m", ""))
                seconds = float(parts[1].replace("s", ""))
                return minutes * 60 + seconds
            return float(time_str.replace("s", ""))

        active_time_seconds = time_str_to_seconds(active_time_str)
        idle_time_seconds = time_str_to_seconds(idle_time_str)

        completion_data = {
            "id": msg.id,
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": msg.model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": [t.model_dump() for t in (m.tool_calls or [])]  # pylint: disable=line-too-long  # noqa: E501
                }
                for m in msg.messages
            ] if hasattr(msg, "messages") else [],
            "choices": [{
                "index": 0,
                "message": {
                    "role": msg.choices[0].message.role if hasattr(msg, "choices") and msg.choices else "assistant",
                    "content": msg.choices[0].message.content if hasattr(msg, "choices") and msg.choices else None,
                    "tool_calls": [t.model_dump() for t in (msg.choices[0].message.tool_calls or [])] if hasattr(msg, "choices") and msg.choices else []  # pylint: disable=line-too-long  # noqa: E501
                },
                "finish_reason": msg.choices[0].finish_reason if hasattr(msg, "choices") and msg.choices else "stop"
            }],
            "usage": {
                "prompt_tokens": msg.usage.prompt_tokens,
                "completion_tokens": msg.usage.completion_tokens,
                "total_tokens": msg.usage.total_tokens
            },
            "cost": {
                "interaction_cost": interaction_cost,
                "total_cost": self.total_cost
            },
            "timing": {
                "active_seconds": active_time_seconds,
                "idle_seconds": idle_time_seconds
            },
            "timestamp_iso": datetime.now().astimezone(
                pytz.timezone("Europe/Madrid")).isoformat()
        }

        # Append both request and completion to the instance's jsonl file
        with open(self.filename, 'a', encoding='utf-8') as f:
            json.dump(request_data, f)
            f.write('\n')
            json.dump(completion_data, f)
            f.write('\n')


def load_history_from_jsonl(file_path):
    """
    Load conversation history from a JSONL file and
    return it as a list of messages.

    Args:
        file_path (str): The path to the JSONL file.
            NOTE: file_path assumes it's either relative to the
            current directory or absolute.

    Returns:
        list: A list of messages extracted from the JSONL file.
    """
    history = []
    max_length = 0
    with open(file_path, encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:  # pylint: disable=broad-except
                print(f"Error loading line: {line}")
                continue
            if isinstance(record, dict) and "messages" \
                in record and isinstance(
                    record["messages"], list):
                if len(record["messages"]) > max_length:
                    max_length = len(record["messages"])
                    history = record["messages"]
    return history


def get_token_stats(file_path):
    """
    Get token usage statistics from a JSONL file.

    Args:
        file_path (str): Path to the JSONL file

    Returns:
        tuple: (model_name, total_prompt_tokens, total_completion_tokens,
                total_cost, active_time, idle_time)
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    model_name = None
    last_total_cost = 0.0
    last_active_time = 0.0
    last_idle_time = 0.0

    with open(file_path, encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if "usage" in record:
                    total_prompt_tokens += record["usage"]["prompt_tokens"]
                    total_completion_tokens += (
                        record["usage"]["completion_tokens"]
                    )
                if "cost" in record:
                    if isinstance(record["cost"], dict):
                        # Si cost es un diccionario, obtener total_cost
                        last_total_cost = record["cost"].get("total_cost", 0.0)
                    else:
                        # Si cost es un valor directo
                        last_total_cost = float(record["cost"])
                if "timing" in record:
                    if isinstance(record["timing"], dict):
                        last_active_time = record["timing"].get(
                            "active_seconds", 0.0)
                        last_idle_time = record["timing"].get(
                            "idle_seconds", 0.0)
                if "model" in record:
                    model_name = record["model"]
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error loading line: {line}: {e}")
                continue

    # Usar el último total_cost encontrado como el total
    total_cost = last_total_cost

    return (model_name, total_prompt_tokens, total_completion_tokens,
            total_cost, last_active_time, last_idle_time)
