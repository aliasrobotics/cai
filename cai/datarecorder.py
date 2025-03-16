"""
Data recorder
"""

import os  # pylint: disable=import-error
from datetime import datetime
import json
import pytz  # pylint: disable=import-error


class DataRecorder:  # pylint: disable=too-few-public-methods
    """
    Records training data from litellm.completion
    calls in OpenAI-like JSON format.

    Stores both input messages and completion
    responses during execution in a single JSONL file.
    """

    def __init__(self):
        os.makedirs('logs', exist_ok=True)
        self.filename = f'logs/cai_{datetime.now().astimezone(
            pytz.timezone("Europe/Madrid")).strftime("%Y%m%d_%H%M%S")}.jsonl'
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
                    "role": msg.choices[0].message.role,
                    "content": msg.choices[0].message.content,
                    "tool_calls": [t.model_dump() for t in (msg.choices[0].message.tool_calls or [])]  # pylint: disable=line-too-long  # noqa: E501
                },
                "finish_reason": msg.choices[0].finish_reason
            }],
            "usage": {
                "prompt_tokens": msg.usage.prompt_tokens,
                "completion_tokens": msg.usage.completion_tokens,
                "total_tokens": msg.usage.total_tokens
            },
            "cost": {
                "interaction_cost": interaction_cost,
                "total_cost": self.total_cost
            }
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
                total_cost)
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    model_name = None
    last_total_cost = 0.0

    with open(file_path, encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if "usage" in record:
                    total_prompt_tokens += record["usage"]["prompt_tokens"]
                    total_completion_tokens += record["usage"]["completion_tokens"]
                if "cost" in record:
                    if isinstance(record["cost"], dict):
                        # Si cost es un diccionario, obtener total_cost
                        last_total_cost = record["cost"].get("total_cost", 0.0)
                    else:
                        # Si cost es un valor directo
                        last_total_cost = float(record["cost"])
                if "model" in record:
                    model_name = record["model"]
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error loading line: {line}: {e}")
                continue

    # Usar el último total_cost encontrado como el total
    total_cost = last_total_cost

    return model_name, total_prompt_tokens, total_completion_tokens, total_cost
