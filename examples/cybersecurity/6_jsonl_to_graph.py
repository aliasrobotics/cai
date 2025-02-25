import os
from cai.datarecorder import load_history_from_jsonl
from cai.graph import Node, get_default_graph
from cai.types import Agent, ChatCompletionMessage
from litellm.types.utils import Message
from wasabi import color

def create_graph_from_history(history):
    """
    Creates a graph from a history of messages, emulating how CAI creates it during interactions.
    
    Args:
        history (list): List of messages loaded from JSONL file
    
    Returns:
        Graph: The constructed graph object
    """
    # Initialize graph
    graph = get_default_graph()
    
    # Track turn number
    turn = 0
    
    # Process each message in history
    for i, message in enumerate(history):
        # Skip system messages as they don't need to be in the graph
        if message.get("role") == "system":            
            continue
            
        # Create a basic agent object for the sender
        agent = Agent(
            name=message.get("sender", message.get("role", "unknown")),
            model=message.get("model", "unknown"),
            functions=[]  # We don't have access to original functions
        )
        
        # Create node for this interaction
        node = Node(
            name=agent.name,
            agent=agent,
            turn=turn,
            message=Message(**message),  # Pass the Message object
            history=history[:i+1]  # Include all history up to this point
        )
        
        # # Add node to graph
        # if "tool_calls" in message and message["tool_calls"]:
        #     # Pass tool calls directly as they are in the message
        #     graph.add_to_graph(node, action=message["tool_calls"])
        # else:
        #     # Otherwise just add the node
        #     graph.add_to_graph(node)

        graph.add_to_graph(node)
                    
        turn += 1
    
    return graph

def main():
    pass
    # Load history from JSONL file
    history = load_history_from_jsonl(
        os.path.join(
            # os.path.dirname(__file__),
            # "..",
            # "..",
            # "tests",
            # "agents",
            # "kiddoctf.jsonl"
            "/workspace/caiextensions-memory/caiextensions/memory/it/baby_first/cai_20250224_130334.jsonl"
        )
    )
    
    # Create graph from history
    graph = create_graph_from_history(history)
    
    # Print ASCII representation
    print(graph.ascii())
    
    
if __name__ == "__main__":
    main()
