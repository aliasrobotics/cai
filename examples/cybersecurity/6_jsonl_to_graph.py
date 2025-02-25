import os
from cai.datarecorder import load_history_from_jsonl
from importlib.resources import files
from cai import is_caiextensions_memory_available
from cai.util import create_graph_from_history

if is_caiextensions_memory_available():
    import caiextensions.memory.it.baby_first


def main():
    if is_caiextensions_memory_available():
        history = load_history_from_jsonl(
            files(caiextensions.memory.it.baby_first) / "cai_20250224_130334.jsonl"
        )
    else:
        # Load history from JSONL file using package resources
            history = load_history_from_jsonl(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "tests",
                    "agents",
                    "kiddoctf.jsonl"
            )
        )
    
    # Create graph from history
    graph = create_graph_from_history(history)
    
    # Print ASCII representation
    print(graph.ascii())
    
    
if __name__ == "__main__":
    main()
