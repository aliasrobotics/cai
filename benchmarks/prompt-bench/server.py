from cai.sdk.agents import Agent, Runner, gen_trace_id, trace, OpenAIChatCompletionsModel
from cai.sdk.agents.mcp import MCPServer, MCPServerSse
from cai.sdk.agents.model_settings import ModelSettings

#cai tools
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command
from cai.tools.web.search_web import make_web_search_with_explanation
from cai.tools.reconnaissance.exec_code import execute_code
from cai.tools.command_and_control.sshpass import run_ssh_command_with_credentials
from cai.tools.reconnaissance.shodan import shodan_search, shodan_host_info
from cai.tools.web.search_web import make_google_search
from cai.tools.misc.reasoning import think 
from cai.tools.web.google_search import google_search
from cai.tools.network.capture_traffic import capture_remote_traffic,remote_capture_session


#Portswigger web scraper bot
import utils.portswiggerbot as pb

#Other utilities
import utils.helpers as hp
from openai import AsyncOpenAI
import asyncio
import os 
import yaml
import sys 
import shutil
from datetime import datetime
import subprocess
import time
from typing import Any
from dotenv import load_dotenv
load_dotenv(override=True)


#MAIN PARAMETERS
USERNAME = os.getenv("PORTSWIGGER_USERNAME")
PASSWORD = os.getenv("PORTSWIGGER_PASSWORD")
MODEL = os.getenv("CAI_MODEL")
SERVER_URL = "http://127.0.0.1:9876/sse"
REMOVE_LABS_WITH_EXPLOIT_SERVER = True


SECTIONS = ["sql-injection",
            "cross-site-scripting",
            "cross-site-request-forgery-csrf",
            "xml-external-entity-xxe-injection",
            "server-side-request-forgery-ssrf",
            "http-request-smuggling",
            "os-command-injection",
            "server-side-template-injection",
            "path-traversal",
            "access-control-vulnerabilities",
            "authentication",
            "web-cache-poisoning",
            "insecure-deserialization",
            "information-disclosure",
            "file-upload-vulnerabilities",
            "prototype-pollution",
            "race-conditions",
            "api-testing",
            "business-logic-vulnerabilities"]

SECTION = "cross-site-request-forgery-csrf"       
            
             # Change this to the desired section or type of portswigger lab
N_LABS = 5 # If you want to test all the labs in the section, change this to -1

AGENT = "webbounty"
PROMPT_TYPE = "zero-shot" # Change this to the desired prompt method
TOOLS = [generic_linux_command,
         execute_code]


#function to save command terminal logs
def setup_tee_logging(log_dir="terminal_output",model="openai/gpt-4o",log_name_prefix="console_log"):
    """
        Save command line outputs of the experiments in folder.

        Args:
            log_dir (str): the name of the main directory.
            log_dir (str): the name of the model used.
            log_name_prefix (str): the prefix for the log file name.
    """
    
    model = model.replace("/","-")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(f"{log_dir}/{model}", exist_ok=True)
    full_dir = os.path.join(log_dir, model)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(full_dir, f"{log_name_prefix}_{timestamp}.txt")
    
    logfile = open(log_path, "w", buffering=1)
    tee_out = hp.TeeStream(sys.stdout, logfile)
    tee_err = hp.TeeStream(sys.stderr, logfile)
    
    sys.stdout = tee_out
    sys.stderr = tee_err
    
    return log_path


#function to run the agent
async def run_agent(agent,user_prompt):
    """
        Run the agent with the provided user prompt.
        Args:
            agent (Agent): The CAI Agent to run.
            user_prompt (str): The user prompt to provide to the agent.
        Returns:
            response (class): The response from the agent after processing the user prompt.
    """
    response = await Runner.run(agent, user_prompt)
    return response


def delete_files(folder="logs"):
    """
        Delete all files in the specified folder.
        Args:
            folder (str): The folder from which to delete files. Default is "logs".
    """
    # List all files in the folder
    files = os.listdir(folder)
    # Check if there are any files

    if files:
        for filename in files:
            file_path = os.path.join(folder, filename)
            os.remove(file_path)
            print(f"Deleted file: {filename}")


def create_folder_and_move_logs(lab,section,agent,prompt_type,model,lab_status):
    """
        Create a folder structure based on the lab information and move the cai logs to that folder.
        Args:
            lab (dict): The lab information containing title, url, and other metadata.
            section (str): The section or type of lab.
            agent (str): The name of the agent used.
            prompt_type (str): The type of prompt used.
            model (str): The model used for the agent.
            lab_status (str): The status of the lab (e.g., solved, not-solved, interrupted, unknown).
    """
    
    #create folder for results 
    model = model.replace("/","-")
    lab_name = lab['url'].split("/")[-1]
    if lab_name == 'lab-html-context-nothing-encoded':
        lab_name = f"{lab_name}-{lab['url'].split("/")[-2]}"
        
        
        
    if lab_status:
        lab_status = lab_status.lower().replace(" ","-")
        destination_folder = os.path.join("results",model, agent, prompt_type, section, lab_status, lab_name)
    else:
        destination_folder = os.path.join("results",model, agent, prompt_type, section, lab_name)
        
    os.makedirs(destination_folder, exist_ok=True)
    
    #move logs folder to results folder
    logs_file = os.listdir("logs")[0]
    source_file = os.path.join("logs", logs_file)
    destination_file = os.path.join(destination_folder, logs_file)
    shutil.move(source_file, destination_file)


async def run(mcp_server: MCPServer):
    
    #configuration to write terminal output to a file
    log_file_path = "terminal_output"
    log_name_prefix = f"{SECTION}.{AGENT}.{PROMPT_TYPE}"
    _ = setup_tee_logging(log_file_path, model= MODEL, log_name_prefix=log_name_prefix)
    print(f"[INFO] Console output is being saved to: {log_file_path}")
    
    #delete logs files
    delete_files()
    
    #Read Prompt yaml file
    with open('prompts.yml', 'r') as f:
        prompts = yaml.load(f, Loader=yaml.SafeLoader)
    
    #Create CAI Agent
    custom_agent = Agent(
        name="Custom Agent",
        instructions=prompts['prompts']['system'][AGENT],
        description="""Agent for AI project to test models with different prompts types on PortSwigger Labs.""",
        tools=TOOLS,
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(tool_choice="required"),
        model=OpenAIChatCompletionsModel(
            model=os.getenv('CAI_MODEL', "openai/gpt-4o"),
            openai_client=AsyncOpenAI(),
            )
        )
    
    print(f"Getting PortSwigger Labs of {SECTION}.....")
    #Initialize bot
    bot = pb.Bot(headless=True)

    #Login to Portswigger Academy
    bot.login(USERNAME,PASSWORD)

    #Get labs urls by section or type of lab
    topics = bot.choose_topic(SECTION)
   

    #Get lab metadata
    #To remove labs that interact with an internal exploit server to be solved
    if REMOVE_LABS_WITH_EXPLOIT_SERVER:
        labs = [bot.obtain_lab_information(link) for link in topics]
        labs = [lab for lab in labs if not 'exploit server' in lab['solution'].lower()]
        labs = labs[0:N_LABS]

    else:
        labs = [bot.obtain_lab_information(link) for link in topics[0:N_LABS]]
    
    #format session cookies
    cookies = bot.driver.get_cookies()

    # Define names of essential cookies
    essential_cookies = {'SessionId','Authenticated_UserVerificationId','t'}
    # Extract only the essential cookies
    essential_cookies = [cookie for cookie in cookies if cookie['name'] in essential_cookies]
    
    print(f"Total Labs extracted: {len(labs)}")
    
    #Iterate through each lab
    for lab in labs:
        lab_was_interrupted = False  # <--- reset for each lab
        
        print(f"\n####################################")
        print(f"Trying to hack Lab: {lab['title']}")
        
        user_prompt = prompts['prompts']['user'][PROMPT_TYPE][AGENT]
        user_prompt = (user_prompt
                    .replace("**LAB_TITLE**", lab['title'])
                    .replace("**LAB_DESCRIPTION**", lab['description'])
                    .replace("**COOKIES**", str(essential_cookies))
                    .replace("**LAB_ENVIRONMENT_URL**", lab['environment_url'])
                    )
        print(f"\nUser Prompt: {user_prompt}")
        
        try:
            response = await run_agent(agent=custom_agent, user_prompt=user_prompt)
            print("Agent executed successfully.")
        except KeyboardInterrupt:
            print("\n[!] User interrupted this lab with Ctrl+C. Skipping lab status check.")
            response = None
            lab_was_interrupted = True
        
        if lab_was_interrupted:
            LAB_STATUS = "interrupted"
        else:
            try:
                LAB_STATUS = bot.check_solved_lab(lab['url'])
            except Exception as e:
                try:
                    bot.login(USERNAME,PASSWORD)
                    LAB_STATUS = bot.check_solved_lab(lab['url'])
                except Exception as e:
                    print(f"[!] Error checking lab status: {e}")
                    LAB_STATUS = "unknown"
          
        
        print(f"Lab Status: {LAB_STATUS}")
        
        create_folder_and_move_logs(lab, SECTION, AGENT, PROMPT_TYPE, MODEL, LAB_STATUS)

        
    #delete logs files and close bot browser
    delete_files()
    bot.driver.close()
    

async def main():
    async with MCPServerSse(
        name="SSE Python Server",
        params={
            "url": SERVER_URL,
        },
    ) as server:
        await run(server)


if __name__ == "__main__":
    asyncio.run(main())