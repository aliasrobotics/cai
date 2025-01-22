"""
Example demonstrating how to use different NetworkState implementations 
with a state-building agent.
"""

from typing import List, Dict, Any
from cai.core import CAI
from cai.types import Agent
from cai.state.json import NetworkState as JsonNetworkState
from cai.state.pydantic import NetworkState as PydanticNetworkState

def build_state_agent(state_class) -> Agent:
    """Creates an agent that builds network state from chat history"""
    
    def parse_history(history: List[Dict[str, Any]], **kwargs) -> str:
        """Function to parse chat history and extract network state information"""
        state = state_class()
        
        # Convert history to list if it's a string
        if isinstance(history, str):
            history = [{"content": history}]
            
        for message in history:
            # Ensure message is a dict and get content safely
            if not isinstance(message, dict):
                continue
                
            content = message.get("content", "")
            if not isinstance(content, str):
                continue
                
            # Look for port scan results
            if "Port 80 is open" in content:
                state.add_endpoint("192.168.1.1")
                if hasattr(state, "states"):  # Pydantic implementation
                    state.states["192.168.1.1"].ports.append({
                        "port": 80,
                        "open": True,
                        "name": "http"
                    })
                else:  # JSON implementation
                    state.network["192.168.1.1"].ports.append({
                        "port": 80,
                        "open": True,
                        "service": "http"
                    })
                    
            # Look for exploit results    
            if "Successfully exploited" in content:
                if hasattr(state, "states"):  # Pydantic implementation
                    state.states["192.168.1.1"].exploits.append({
                        "type_exploit": "buffer_overflow",
                        "launched": True,
                        "name": "exploit1" 
                    })
                else:  # JSON implementation
                    state.network["192.168.1.1"].exploits.append({
                        "name": "exploit1",
                        "type": "buffer_overflow",
                        "status": "success"
                    })
                    
        return str(state)

    return Agent(
        name="StateBuilder",
        instructions="""
        I am a state building agent that analyzes chat history to construct network state.
        I look for information about ports, services, exploits and build a structured state representation.
        """,
        functions=[parse_history],
    )

def main():
    """Main function demonstrating both NetworkState implementations"""
    
    # Sample chat history - using proper message format
    history = [
        {
            "role": "assistant",
            "content": "Scanning target...\nPort 80 is open running HTTP service",
            "sender": "scanner"
        },
        {
            "role": "assistant", 
            "content": "Attempting exploit...\nSuccessfully exploited target through buffer overflow",
            "sender": "exploiter"
        }
    ]
    
    cai = CAI()
    
    # Test with JSON NetworkState implementation
    print("\nTesting with JSON NetworkState implementation:")
    json_agent = build_state_agent(JsonNetworkState)
    json_response = cai.run(
        agent=json_agent,
        messages=history,
        debug=2
    )
    print("\nFinal JSON State:")
    print(json_response.messages[-1]["content"])
    
    # Test with Pydantic NetworkState implementation 
    print("\nTesting with Pydantic NetworkState implementation:")
    pydantic_agent = build_state_agent(PydanticNetworkState)
    pydantic_response = cai.run(
        agent=pydantic_agent,
        messages=history,
        debug=2
    )
    print("\nFinal Pydantic State:")
    print(pydantic_response.messages[-1]["content"])

if __name__ == "__main__":
    main()
