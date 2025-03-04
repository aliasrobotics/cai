from cai.repl import run_cai_cli
from agents import weather_agent

if __name__ == "__main__":
    run_cai_cli(weather_agent, stream=True)
