# Benchmarking Agentic AI in Cybersecurity: Comparing Models and Prompting Methods in Lab Challenges with CAI.

## Introduction

This project explores and evaluates the integration of **Large Language Models (LLMs)** into web application attack scenarios using the **Cybersecurity AI (CAI)** framework. The goal is to test various prompting methods and different LLMs to assess their effectiveness in identifying vulnerabilities within web applications.

**Fully Automated (No HITL):**  
The pipeline is designed to be **fully automated, with no Human-in-the-Loop (HITL)**. When the agent attempts to solve the challenge labs, **no human interaction with the model is required**; all decisions, iterations, and actions are executed autonomously according to the experiment’s configuration and the prompt templates.


## Objectives

This project focuses on the following objectives:

- Compare the performance of different LLMs within the [**CAI Framework**](https://aliasrobotics.github.io/cai/).
- Use [*PortSwigger labs*](https://portswigger.net/web-security) as an environment to test the LLMs.
- Evaluate the effectiveness of the models in identifying and exploiting common web vulnerabilities.
- Compare the models using prompting methods such as **zero-shot**, **few-shot**, and **chain-of-thought**.
- Assess performance using metrics such as **turns, time, cost, tokens,** and **number of payloads (tools) generated**.
- Create a reproducible framework to evaluate the LLMs.

## Methodolody
The program follows a sequence of steps to evaluate the models. These steps are defined below:

- 1. The user configures the variables for the LLM, the prompt method, and the PortSwigger lab environment.
- 2. The PortSwigger bot extracts the data from the labs.
- 3. The prompt method templates are formatted with the lab information.
- 4. The custom AI agent in CAI runs and attempts to solve the lab challenges.
- 5. The PortSwigger bot verifies if each lab is solved.
- 6. The logs of the labs and terminal outputs are saved.
- 7. After the agent completes all tasks, the lab logs can be evaluated using the metrics.ipynb notebook.


## Project Folder Structure
In this section, the main folder structure is described.
```plaintext
llm-cai-project/                  # Root directory of the project
├── logs/                         # CAI log outputs
├── results/                      # Final experiment logs
├── terminal-output/              # Saved terminal output sessions
├── metrics-experiment/           # Metrics of the experiment
│   ├── calculated-evaluation-metrics.xlsx   # Average and sum-based metrics (generated after running main.py)
│   └── evaluation-metrics.xlsx              # Metrics of each lab (generated after running main.py)
├── utils/                        # Utility scripts and configs
│   ├── helpers.py                # General helper functions
│   ├── portswiggerbot.py         # Automation for PortSwigger bot
│   └── topics-prefixes.json      # Topic prefixes for PortSwigger bot
├── main.py                       # Main execution script (it uses simple curl tools to interact with labs)
├── server.py                     # Main execution script (it uses Burp Suite MCP server to interact with labs)
├── metrics.ipynb                 # Notebook for evaluating metrics
└── prompts.yml                   # Prompt templates
```
## Steps for Reproducibility

1. Create a `.env` file in the main folder. For more details, see [**.env.example**](https://github.com/cristobalvch/llm-cai-project/blob/main/.env.example) file.  
2. Configure the variables related to the PortSwigger account and the LLM used. You can create a PortSwigger account [here](https://portswigger.net/web-security).
3. Install the Python dependencies with the command:  
   ```bash
   pip install -r requirements.txt
   ```
4. Configure the labs and agent parameters in the main.py script as follows. To see more available sections, see  [**topic_prefixes.json**](https://github.com/cristobalvch/llm-cai-project/blob/main/utils/topics_prefixes.json) file.
   ```python
    SECTION = "sql-injection"  # Change this to the type of lab
    N_LABS = 4                 # To test all the labs in the section, change this to -1
    AGENT = "webbounty"
    PROMPT_TYPE = "zero-shot"  # Change this to the desired prompt method
   ```
   To see more information about the prompt templates by type, see the [**promts.yml**](https://github.com/cristobalvch/llm-cai-project/blob/main/prompts.yml) file.
5. Open a terminal in the main folder and run the main script with the command:
    ```bash
    python main.py
    ```
    In case you want to run the script using Burp Suite MCP server to interact with the labs, you need first to install the MCP server. More information on this [link](https://portswigger.net/bappstore/9952290f04ed4f628e624d0aa9dccebc).
    Then, set up the variable SERVER_URL in the script server.py as follows:
    ```python
    SERVER_URL = "http://127.0.0.1:9876/sse"
    ```
    Finally run the script with python.
     ```bash
    python server.py
    ```
6. Once the script stops, create the metrics table and graphs running the notebook
[**metrics.ipynb**](https://github.com/cristobalvch/llm-cai-project/blob/main/metrics.ipynb)

