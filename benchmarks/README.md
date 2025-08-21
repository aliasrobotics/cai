# AI Model Evaluation Benchmarks

This chapter is a curated collection of benchmark datasets and evaluation tools designed to assess the capabilities of custom AI models, particularly in domains related to cybersecurity.

The collection is intended to support researchers and developers who are evaluating their own models using reliable, task-specific benchmarks.

Currently, this are the benchmarks included:

| Benchmark | Description |
|-----------|-------------|
| [SecEval](https://github.com/XuanwuAI/SecEval) | Benchmark designed to evaluate large language models (LLMs) on security-related tasks. It includes various real-world scenarios such as phishing email analysis, vulnerability classification, and response generation. |
| [CyberMetric](https://github.com/CyberMetric) | Benchmark framework that focuses on measuring the performance of AI systems in cybersecurity-specific question answering, knowledge extraction, and contextual understanding. It emphasizes both domain knowledge and reasoning ability. |
| [CTIBench](https://github.com/xashru/cti-bench) | Benchmark focused on evaluating LLM models' capabilities in understanding and processing Cyber Threat Intelligence (CTI) information. |
| [PentestPerf](https://gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf) | An internal benchmarking framework that measures penetration testing capabilities of LLM models in a proprietary set of IT, OT and robotics scenarios. Reach out if you wish to cooperate in this direction. |
| [CyberPII-Bench](https://github.com/aliasrobotics/cai/tree/main/benchmarks/cyberPII-bench/) | Benchmark designed to evaluate the ability of LLM models to maintain privacy and handle **Personally Identifiable Information (PII)** in cybersecurity contexts. Built from real-world data generated during offensive hands-on exercises conducted with **CAI (Cybersecurity AI)**. |
| [Prompt-Bench](https://github.com/aliasrobotics/cai/tree/main/benchmarks/prompt-bench/) | Benchmark designed to evaluate a fully automated integration of LLMs (Large Language Models) with no HITL (Human-in-the-Loop) into web application attack scenarios using **CAI (Cybersecurity AI)**. Its goal is to test various prompting strategies and different LLMs to assess their effectiveness in identifying vulnerabilities within web applications. |







The goal is to consolidate diverse evaluation tasks under a single framework to support rigorous, standardized testing.

## 📊 General Summary Table

| Model       | SecEval   | CyberMetric  | Total Value | 
|-------------|-----------|--------------|-------------|
| model_name  | `XX.X%`   | `XX.X%`      | `XX.X%`     | 



#### ▶️ Usage

```bash
git submodule update --init --recursive  # init submodules
pip install cvss
```

Set the API_KEY for the corresponding backend as follows in .env: NAME_BACKEND + API_KEY

```bash
OPENAI_API_KEY = "..."
ANTHROPIC_API_KEY="..."
OPENROUTER_API_KEY="..."
````

Some of the backends need and url to the api base, set as follows in .env: NAME_BACKEND + API_BASE:

```bash
OLLAMA_API_BASE="..."
OPENROUTER_API_BASE="..."
````
Once evething is configured run the script

```bash
python benchmarks/eval.py --model MODEL_NAME --dataset_file INPUT_FILE --eval EVAL_TYPE --backend BACKEND
```
```bash
Arguments:
    -m, --model         # Specify the model to evaluate (e.g., "gpt-4", "ollama/qwen2.5:14b")
    -d, --dataset_file  # IMPORTANT! By default: small test data of 2 samples 
    -B, --backend       # Backend to use: "openai", "openrouter", "ollama" (required)
    -e, --eval          # Specify the evaluation benchmark

Output:
   outputs/
   └── benchmark_name/
       └── model_date_random-num/
           ├── answers.json       # the whole test with LLM answers
           └── information.txt    # report of that precise run (e.g. model_name, benchmark_name, metrics, date)

```


#### 🔍 Examples

**How to run different CTI Bench tests with the "llama/qwen2.5:14b" model using Ollama as the backend**

```bash
python benchmarks/eval.py --model ollama/qwen2.5:14b --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json --eval cybermetric --backend ollama
````

```bash
python benchmarks/eval.py --model ollama/qwen2.5:14b --dataset_file benchmarks/seceval/eval/datasets/questions-2.json --eval seceval --backend ollama
```

**How to run different CTI Bench tests with the "qwen/qwen3-32b:free" model using Openrouter as the backend**

```bash
python benchmarks/eval.py --model qwen/qwen3-32b:free  --dataset_file benchmarks/cti_bench/data/cti-mcq1.tsv --eval cti_bench --backend openrouter
````
```bash
python benchmarks/eval.py --model qwen/qwen3-32b:free  --dataset_file benchmarks/cti_bench/data/cti-ate2.tsv --eval cti_bench --backend openrouter
````

**How to run different backends such as openai and anthropic**

```bash
python benchmarks/eval.py --model gpt-4o-mini --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json --eval cybermetric --backend openai
````

```bash
python benchmarks/eval.py --model claude-3-7-sonnet-20250219 --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json --eval cybermetric --backend anthropic
````
