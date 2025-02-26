"""
A Coding Agent (CodeAgent)

A re-interpretation for CAI of the original CodeAct concept
from the paper "Executable Code Actions Elicit Better LLM Agents"
at https://arxiv.org/pdf/2402.01030.

Briefly, the CodeAgent CAI Agent uses executable Python code to 
consolidate LLM agents' actions into a unified action space 
(CodeAct). Integrated with a Python interpreter, CodeAct can 
execute code actions and dynamically revise prior actions or 
emit new actions upon new observations through multi-turn 
interactions.
"""

from cai.types import Agent

