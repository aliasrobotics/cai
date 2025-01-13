import os  # pylint: disable=import-error
from datetime import datetime
import pytz
import json


class TrainingDataRecorder:
    """
    Records training data from litellm.completion calls in OpenAI-like JSON format.
    Stores both input messages and completion responses during execution in a single JSONL file.
    """

    def __init__(self):

        os.makedirs('train_data', exist_ok=True)
        self.filename = f'train_data/test_{datetime.now().astimezone(
            pytz.timezone("Europe/Madrid")).strftime("%Y%m%d_%H%M%S")}.jsonl'

    def rec_training_data(self, create_params, msg) -> None:
        """Records a single training data entry to the JSONL file"""
        request_data = {
            "model": create_params["model"],
            "messages": create_params["messages"],
            "stream": create_params["stream"]
        }
        if "tools" in create_params:
            request_data.update({
                "tools": create_params["tools"],
                "tool_choice": create_params["tool_choice"],
                "parallel_tool_calls": create_params["parallel_tool_calls"]
            })

        completion_data = {
            "id": msg.id,
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": msg.model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": [t.model_dump() for t in (m.tool_calls or [])]
                }
                for m in msg.messages
            ] if hasattr(msg, "messages") else [],
            "choices": [{
                "index": 0,
                "message": {
                    "role": msg.choices[0].message.role,
                    "content": msg.choices[0].message.content,
                    "tool_calls": [t.model_dump() for t in (msg.choices[0].message.tool_calls or [])]
                },
                "finish_reason": msg.choices[0].finish_reason
            }],
            "usage": {
                "prompt_tokens": msg.usage.prompt_tokens,
                "completion_tokens": msg.usage.completion_tokens,
                "total_tokens": msg.usage.total_tokens
            }
        }

        # Append both request and completion to the instance's jsonl file
        with open(self.filename, 'a', encoding='utf-8') as f:
            json.dump(request_data, f)
            f.write('\n')
            json.dump(completion_data, f)
            f.write('\n')
