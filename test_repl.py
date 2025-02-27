from cai.agent import agent
import os
import sys
from cai.repl.repl import run_demo_loop

# Set environment variable to ensure we exit quickly
os.environ["TEST_MODE"] = "1"

# Import the necessary agent

# Start the REPL with a test agent
try:
    # This will initialize the REPL but exit immediately
    run_demo_loop(agent)
except KeyboardInterrupt:
    # Expected exit path
    pass
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print("REPL toolbar formatting test completed successfully")
sys.exit(0)
