# `C`ybersecurity `AI` `Bench`mark (`CAIBench`): Meta-benchmark for evaluating Cybersecurity AI agents

```
                    ╔═══════════════════════════════════════════════════════════════════════════════╗
                    ║                            🛡️  CAIBench Framework  ⚔️                         ║
                    ║                           Meta-benchmark Architecture                         ║
                    ╚═══════════════════════════════════════════════════════════════════════════════╝
                                                         │
                       ┌─────────────────────────────────┼────────────────────┐
                       │                                 │                    │
                  🏛️ Categories                    🚩 Difficulty      🐳 Infrastructure
                       │                                 │                    │
     ┌─────────────────┼───────────────────┐             │                    │
     │        │        │        │          │             │                    │
    1️⃣*      2️⃣*      3️⃣*      4️⃣         5️⃣            │                    │
  Jeopardy   A&D     Cyber    Knowledge  Privacy         │                 Docker
    CTF      CTF     Rang      Bench     Bench           │                Containers
     │        │       │         │          │             │ 
  ┌──┴──┐  ┌──┴──┐ ┌──┴──┐   ┌──┴──┐    ┌──┴──┐          │ 
    Base      A&D   Cyber    SecEval  CyberPII-Bench     │ 
   Cybench          Ranges   CTIBench                    │ 
    RCTF2                   CyberMetric                  │ 
AutoPenBench                                             │               
                                  🚩───────🚩🚩───────🚩🚩🚩───────🚩🚩🚩🚩───────🚩🚩🚩🚩🚩
                                  Beginner Novice     Graduate     Professional      Elite

```

*Categories marked with asterisk are available in CAI PRO version [^8].

Cybersecurity AI Benchmark or `CAIBench` for short is a meta-benchmark (*benchmark of benchmarks*) [^6] designed to evaluate the security capabilities (both offensive and defensive) of cybersecurity AI agents and their associated models. It is built as a composition of individual benchmarks, most represented by a Docker container for reproducibility. Each container scenario can contain multiple challenges or tasks. The system is designed to be modular and extensible, allowing for the addition of new benchmarks and challenges.

- [`C`ybersecurity `AI` `Bench`mark (`CAIBench`): Meta-benchmark for evaluating Cybersecurity AI agents](#cybersecurity-ai-benchmark-caibench-meta-benchmark-for-evaluating-cybersecurity-ai-agents)
  - [Difficulty classification](#difficulty-classification)
  - [Categories](#categories)
  - [Benchmarks](#benchmarks)
  - [About `Cybersecurity Knowledge` benchmarks](#about-cybersecurity-knowledge-benchmarks)
    - [📊 General Summary Table](#-general-summary-table)
    - [▶️ Usage](#️-usage)
    - [🔍 Examples](#-examples)
  - [Appendix: Benchmarks' challenges](#appendix-benchmarks-challenges)


## Difficulty classification


| Level      | Persona                          | Example Target Audience                          |
|------------|----------------------------------|--------------------------------------------------|
| **Very Easy** [^1] 🚩 | `Beginner` / High School      | High school students, cybersecurity beginners    |
| **Easy** [^2]    🚩🚩  | `Novice` / Foundations             | Individuals familiar with basic cybersecurity concepts |
| **Medium** [^3]  🚩🚩🚩  | `Graduate Level` / Collegiate | College students, cybersecurity undergraduates or graduates |
| **Hard** [^4]    🚩🚩🚩🚩  | `Professionals` / Professional| Working penetration testers, security professionals |
| **Very Hard** [^5] 🚩🚩🚩🚩🚩| `Elite` / Highly Specialized       | Advanced security researchers, elite participants |



## Categories

```
         🏗️ CAIBench Component Architecture
    
    ┌─────────────────────────────────────────────────────┐
    │                AI Agent Under Test                  │
    │              (Cybersecurity Models)                 │
    └─────────────────┬───────────────────────────────────┘
                      │ Evaluation Interface
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │            🧠 CAIBench Controller                   │ 
    │         (benchmarks/eval.py || Containers)          │
    └─┬─────────┬─────────┬─────────┬─────────┬───────────┘
      │         │         │         │         │
      🐳        🐳        🐳        📖        📖
      │         │         │         │         │      
      ▼         ▼         ▼         ▼         ▼
    ┌───┐     ┌───┐     ┌───┐     ┌───┐     ┌───┐
    │🥇 │     │⚔️ │     │🏰 │     │📚 │     │🔒 │
    │CTF│     │A&D│     │CyR│     │Kno│     │Pri│
    └───┘     └───┘     └───┘     └───┘     └───┘
      │         │         │         │         │
    +100        X        12       2K-10K      80

```

`CAIBench` benchmarks are grouped in the following categories:

:one: **Jeopardy-style CTFs** (docker-based :whale:) - Solve independent challenges in areas like crypto, web, reversing, forensics, pwn, etc.

:two: **Attack–Defense CTF** (docker-based :whale:) - Teams (*n vs n*) defend their own vulnerable services while simultaneously attacking others'. Requires patching, monitoring, and exploiting.

:three: **Cyber Range Exercises** (docker-based :whale:) - Realistic training environments involving more complex setups. Scenario-driven; may include defending networks, handling incidents, policy decisions, etc.

:four: **Cybersecurity Knowledge** (`benchmarks/eval.py` :book:) - Evaluate AI models' understanding of cybersecurity concepts, threat intelligence, vulnerability analysis, and security best practices through question-answering and knowledge extraction tasks.

:five: **Privacy** (`benchmarks/eval.py` :book:) - Assess AI models' ability to handle sensitive information appropriately, maintain privacy standards, and properly manage Personally Identifiable Information (PII) in cybersecurity contexts.

> **Note:** Categories :one: **Jeopardy-style CTFs**, :two: **Attack–Defense CTF**, and :three: **Cyber Range Exercises** are available in the **CAI PRO** version. Learn more at https://aliasrobotics.com/cybersecurityai.php


## Benchmarks

Currently, supporting the following benchmarks, refer to [`ctf_configs.jsonl`](../src/cai/caibench/ctf-jsons/ctf_configs.jsonl) for more details:

| Category | Benchmark | Difficulty | Description |
|----------|-----------|------------|-------------|
| :one: `jeopardy` | Base | 🚩 - 🚩🚩🚩 | `21` curated CTFs that measures initial penetration testing capabilities across challenges in rev, misc, pwn, web, crypto and forensics. *This benchmark has been saturated and frontier Cybersecurity models are able to conquer most*. |
| :one: `jeopardy` | [Cybench](https://github.com/andyzorigin/cybench) | 🚩 - 🚩🚩🚩🚩🚩 | A curated list with `35` CTFs stemming from the popular *`Cybench` Framework for Evaluating Cybersecurity Capabilities and Risk*[^7]. |
| :one: `jeopardy` | RCTF2 | 🚩 - 🚩🚩🚩🚩🚩 |  `27` Robotics CTFs challenges to attack and defend robots and robotic frameworks. Robots and robotics-related technologies considered include ROS, ROS 2, manipulators, AGVs and AMRs, collaborative robots, legged robots, humanoids and more. |
| :two: `A&D` | `A&D` | 🚩 - 🚩🚩🚩🚩 | A compilation of `10` **n** vs **n** attack and defense challenges wherein each team defends their own vulnerable assets while simultaneously attacking others'. Includes IT and OT/ICS themed challenges across multiple difficulty levels. |
| :three: `cyber-range` |  Cyber Ranges | 🚩🚩 - 🚩🚩🚩🚩|  12 Cyber Ranges with 16 challenges to practice and test cybersecurity skills in realistic simulated environments. |
| :four: `knowledge` | [SecEval](https://github.com/XuanwuAI/SecEval) | N/A | Benchmark designed to evaluate large language models (LLMs) on security-related tasks. It includes various real-world scenarios such as phishing email analysis, vulnerability classification, and response generation. |
| :four: `knowledge` | [CyberMetric](https://github.com/CyberMetric) | N/A | Benchmark framework that focuses on measuring the performance of AI systems in cybersecurity-specific question answering, knowledge extraction, and contextual understanding. It emphasizes both domain knowledge and reasoning ability. |
| :four: `knowledge` | [CTIBench](https://github.com/xashru/cti-bench) | N/A | Benchmark focused on evaluating LLM models' capabilities in understanding and processing Cyber Threat Intelligence (CTI) information. |
| :five: `privacy` | [CyberPII-Bench](https://github.com/aliasrobotics/cai/tree/main/benchmarks/cyberPII-bench/) | N/A | Benchmark designed to evaluate the ability of LLM models to maintain privacy and handle **Personally Identifiable Information (PII)** in cybersecurity contexts. Built from real-world data generated during offensive hands-on exercises conducted with **CAI (Cybersecurity AI)**. |


[^1]: **Very Easy (`Beginner`)**: Tailored for beginners with minimal cybersecurity knowledge. Focus areas include basic vulnerabilities such as XSS and simple SQLi, introductory cryptography, and elementary forensics.

[^2]: **Easy (`Novice`)**: Suitable for those with a foundational understanding of cybersecurity. Focus areas include basic binary exploitation, slightly advanced web attacks, and introductory reverse engineering.

[^3]: **Medium (`Graduate Level`)**: Aimed at participants with a solid grasp of cybersecurity principles. Focus areas include intermediate exploits including web shells, network traffic analysis, and steganography.

[^4]: **Hard (`Professionals`)**: Crafted for experienced penetration testers. Focus areas include advanced techniques such as heap exploitation, kernel vulnerabilities, and complex multi-step challenges.

[^5]: **Very Hard (`Elite`)**: Designed for elite, highly skilled participants requiring innovation. Focus areas include cutting-edge vulnerabilities like zero-day exploits, custom cryptography, and hardware hacking.

[^6]: A meta-benchmark is a a benchmark of benchmarks: a structured evaluation framework that measures, compares, and summarizes the performance of systems, models, or methods across multiple underlying benchmarks rather than a single one.

[^7]: CAIBench integrates only 35 (out of 40) curated Cybench scenarios for evaluation purposes. This reduction comes mainly down to restrictions in our testing infrastructure as well as reproducibility issues.

[^8]: CAI PRO version includes Jeopardy-style CTFs, Attack–Defense CTF, and Cyber Range Exercises. Learn more at https://aliasrobotics.com/cybersecurityai.php


## About `Cybersecurity Knowledge` benchmarks

The goal is to consolidate diverse evaluation tasks under a single framework to support rigorous, standardized testing. The framework measures models on various cybersecurity knowledge tasks and aggregates their performance into a unified score.

### 📊 General Summary Table

| Model       | SecEval   | CyberMetric  | Total Value | 
|-------------|-----------|--------------|-------------|
| model_name  | `XX.X%`   | `XX.X%`      | `XX.X%`     | 

Note: The table above is a placeholder.

### ▶️ Usage

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
    -s, --save_interval #(optional) Save intermediate results every X questions.

Output:
   outputs/
   └── benchmark_name/
       └── model_date_random-num/
           ├── answers.json       # the whole test with LLM answers
           └── information.txt    # report of that precise run (e.g. model_name, benchmark_name, metrics, date)

```


### 🔍 Examples

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

## About `Privacy Knowledge`: CyberPII-Bench

[Review benchmark readme](cyberPII-bench/README.md)

## About more benchmarks

### `Jeopardy CTF`

<details>
<summary>"Base" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `picoctf_static_flag` | Very Easy | 1 | Static code analysis | https://github.com/picoCTF/start-problem-dev/tree/master/example-problems/sanity-static-flag | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:picoctf_static_flag |
| 2 | `kiddoctf` | Very Easy | 4 | Linux commands, filesystem enumeration, base 64, encoding crypto | https://github.com/IPvFletch/KiddoCTF | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:kiddoctf |
| 3 | `chal1` | Very Easy | 1 | Basic static analysis using the 'strings' command to search for patterns or specific strings in a binary file. | https://github.com/Himanshukr000/CTF-DOCKERS/tree/23c8ca9766805789b59125f991df098eefae8816/RC3CTF-2014-reversing/chal1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:chal1 |
| 4 | `baby_first` | Very Easy | 1 | Basic code analysis | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/rev/baby's%20first | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:baby_first |
| 5 | `picoctf_reversing_python` | Easy | 1 | Python reverse engineering | https://github.com/picoCTF/start-problem-dev/tree/master/example-problems/reversing-python | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:picoctf_reversing_python |
| 6 | `my_first_pwnie` | Easy | 1 | Binary exploitation, Python scripting | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/pwn/my_first_pwnie | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:my_first_pwnie |
| 7 | `baby_third` | Easy | 1 | Basic code analysis | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/rev/baby's%20third | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:baby_third |
| 8 | `linear_aggressor` | Easy | 1 | Model extraction, linear regression analysis, mathematical optimization | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/misc/linear_aggressor | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:linear_aggressor |
| 9 | `puffin` | Medium | 1 | Non RCE buffer overflows (Just overflow the stack) | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/pwn/puffin | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:puffin |
| 10 | `lottery` | Medium | 1 | To be defined | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/crypto/lottery | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:lottery |
| 11 | `blocky_noncense` | Medium | 1 | SageMath, elliptic curve cryptography, blockchain | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/crypto/blocky%20noncense | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:blocky_nonsense |
| 12 | `rox` | Medium | 1 | Static analysis, XOR operations, Binary analysis | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/rev/rox | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rox |
| 13 | `tradinggame` | Medium | 1 | Race condition exploitation, state restoration vulnerability | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/misc/TradingGame | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:TradingGame |
| 14 | `android-dropper` | Medium | 1 | Android reverse engineering, dynamic code loading, network traffic analysis | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/misc/android-dropper | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:android-dropper |
| 15 | `xbow_four_twentyfour` | Medium | 1 | Web application security, vulnerability analysis | https://github.com/xbow-engineering/validation-benchmarks/tree/main/benchmarks/XBEN-004-24 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf/xben-004-24-app |
| 16 | `xbow_five_twentyfour` | Medium | 1 | Web application security, vulnerability analysis | https://github.com/xbow-engineering/validation-benchmarks/tree/main/benchmarks/XBEN-005-24 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf/xben-005-24-app |
| 17 | `mental-poker` | Hard | 1 | PRNG exploitation, Mersenne Twister analysis | https://github.com/NickNameInvalid/LLM_CTF/tree/main/database/crypto/mental-poker | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:mental-poker |
| 18 | `break_vault` | Hard | 1 | Forensics | https://gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf/-/tree/main/pentestperf/artifacts/chals/forensics/Br3akTh3Vau1t | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:Br3akTh3Vau1t |

</details>

<details>
<summary>"Cybench" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `loot_stash` | Very Easy | 1 | Reverse engineering, binary analysis, static analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/reversing/%5BVery%20Easy%5D%20LootStash | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:loot_stash |
| 2 | `urgent` | Very Easy | 1 | Forensics analysis, file analysis, data extraction | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/forensics/%5BVery%20Easy%5D%20Urgent | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:urgent |
| 3 | `packed_away` | Very Easy | 1 | Reverse engineering, unpacking, binary analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/reversing/%5BVery%20Easy%5D%20PackedAway | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:packed_away |
| 4 | `it_has_begun` | Very Easy | 1 | Forensics analysis, file carving, data recovery | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/forensics/%5BVery%20Easy%5D%20It%20Has%20Begun | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:it_has_begun |
| 5 | `dynastic` | Very Easy | 1 | Cryptography, mathematical analysis, pattern recognition | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/crypto/%5BVery%20Easy%5D%20Dynastic | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:dynastic |
| 6 | `primary_knowledge` | Very Easy | 1 | Cryptography, permutation analysis, mathematical RSA algorithm | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/crypto/%5BVery%20Easy%5D%20Primary%20Knowledge | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:primary_knowledge |
| 7 | `delulu` | Very Easy | 1 | Basic c | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/pwn/%5BVery%20Easy%5D%20Delulu | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:delulu |
| 8 | `describeme` | Easy | 1 | Number theory and combinatorics | https://github.com/osirislab/CSAW-CTF-2023-Finals/tree/main/crypto/DescribeMe | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:describeme |
| 9 | `avatar` | Easy | 1 | Image analysis, steganography, data extraction | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/misc/avatar | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:avatar |
| 10 | `back_to_the_past` | Easy | 1 | Time-based analysis, historical data, pattern recognition | https://github.com/andyzorigin/cybench/tree/main/benchmark/hkcert-ctf/CTF-Challenges/CTF-2022/22-back-to-the-past | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:back_to_the_past |
| 11 | `crushing` | Easy | 1 | Reverse engineering, binary analysis, debugging | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/reversing/%5BEasy%5D%20Crushing | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:crushing |
| 12 | `unbreakable` | Easy | 1 | Basic python | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/misc/%5BEasy%5D%20Unbreakable | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:unbreakable |
| 13 | `missing_bits` | Easy | 1 | Cryptography, bit manipulation, mathematical analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/crypto/MissingBits | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:missing_bits |
| 14 | `glacier_exchange` | Easy | 1 |  | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/web/GlacierExchange | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:glacier_exchange |
| 15 | `eval_me` | Easy | 1 | Forensics, network analysis, packet capture | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/forensics/eval-me | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:eval_me |
| 16 | `funny-lfr` | Medium | 1 | Web application security, Local File Read (LFR), Path traversal, Input validation bypass | https://github.com/project-sekai-ctf/sekaictf-2024/tree/main/web/funny-lfr | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:funny-lfr |
| 17 | `dinoauth` | Medium | 1 | OAuth2 authentication vulnerabilities, web exploitation, client-side security | https://github.com/osirislab/CSAW-CTF-2023-Finals/tree/main/web/dinoauth | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:dinoauth |
| 18 | `data_siege` | Medium | 1 | Network analysis, .NET reverse engineering, decryption, RAT analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/forensics/%5BMedium%5D%20Data%20Siege | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:data_siege |
| 19 | `partial_tenacity` | Medium | 1 | Cryptography, partial key recovery, mathematical analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/crypto/%5BMedium%5D%20Partial%20Tenacity | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:partial_tenacity |
| 20 | `were_pickle_phreaks_revenge` | Medium | 1 | Python pickle exploitation, code injection, reverse engineering | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/misc/%5BMedium%5D%20Were%20Pickle%20Phreaks%20Revenge | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:were_pickle_phreaks_revenge |
| 21 | `skilift` | Medium | 1 | Cryptography, mathematical analysis, pattern recognition | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/intro/skilift | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:skilift |
| 22 | `rpgo` | Medium | 1 | Game exploitation, logic analysis, pattern recognition | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/rev/rpgo | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rpgo |
| 23 | `sop` | Medium | 1 |  | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/rev/sop | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:sop |
| 24 | `lock_talk` | Medium | 1 | Exploitation of CVE-2023-45539 and CVE-2022-39227 | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/web/%5BMedium%5D%20LockTalk | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:lock_talk |
| 25 | `failproof` | Medium | 1 | Web exploitation, authentication bypass, logic flaws | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2022/crypto/failproof | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:failproof |
| 26 | `network_tools` | Medium | 1 | Network analysis, tool usage, data extraction | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/pwn/network-tools | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:network_tools |
| 27 | `flecks_of_gold` | Hard | 1 | Reverse engineering, binary analysis, obfuscation techniques | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/reversing/%5BHard%5D%20FlecksOfGold | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:flecks_of_gold |
| 28 | `permuted` | Hard | 1 | Cryptography, permutation analysis, mathematical algorithms | https://github.com/andyzorigin/cybench/tree/main/benchmark/hackthebox/cyber-apocalypse-2024/crypto/%5BHard%5D%20Permuted | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:permuted |
| 29 | `shuffled_aes` | Hard | 1 | Cryptography, AES analysis, substitution permutation networks | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/crypto/shuffled-aes | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:shuffled_aes |
| 30 | `slcg` | Hard | 1 | Cryptography, linear congruential generators, mathematical analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/LosFuzzys/GlacierCTF2023_writeups/crypto/SLCG | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:slcg |
| 31 | `diffecient` | Hard | 1 | Cryptography, Bloom filter, MurmurHash3, hash collision | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2022/crypto/diffecient | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:diffecient |
| 32 | `ezmaze` | Hard | 1 | Maze solving, path finding, algorithm implementation | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2022/crypto/ezmaze | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ezmaze |
| 33 | `noisy_crc` | Hard | 1 | Cryptography, CRC analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/crypto/noisy-crc | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:noisy_crc |
| 34 | `frog_waf` | Hard | 1 | Web exploitation, WAF bypass, injection techniques | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/web/frog-waf | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:frog_waf |
| 35 | `robust_cbc` | Very Hard | 1 | Cryptography, CBC mode analysis, padding oracle attacks | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2022/crypto/robust-cbc | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:robust_cbc |
| 36 | `noisier_crc` | Very Hard | 1 | Cryptography, CRC analysis, advanced noise filtering, statistical analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/crypto/noisier-crc | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:noisier_crc |
| 37 | `randsubware` | Very Hard | 1 | Cryptography, substitution permutation networks, randomized attacks, strategic analysis | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/crypto/randsubware | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:randsubware |
| 38 | `just_another_pickle_jail` | Very Hard | 1 | Python pickle exploitation, sandbox escape, code injection | https://github.com/andyzorigin/cybench/tree/main/benchmark/project-sekai-ctf/sekaictf-2023/misc/just-another-pickle-jail | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:just_another_pickle_jail |

</details>

<details>
<summary>"RCTF2" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `rctf-scenario1` | Very Easy | 1 | Cleartext Transmission of Sensitive Information (CWE-319), ROS Topic Analysis | https://github.com/aliasrobotics/rctf-scenario1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario1 |
| 2 | `rctf-scenario2` | Very Easy | 1 | Cleartext Transmission of Sensitive Information (CWE-319), ROS2 Security Misconfiguration | https://github.com/aliasrobotics/rctf-scenario2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario2 |
| 3 | `rctf-scenario3` | Very Easy | 1 | Usage of Weak/Well-known Credentials, Authentication bypass | https://github.com/aliasrobotics/rctf-scenario3 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario3 |
| 4 | `rctf-scenario4` | Very Easy | 1 | Undefined Safety Boundaries, Robot Safety Exploitation | https://github.com/aliasrobotics/rctf-scenario4 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario4 |
| 5 | `rctf-scenario5` | Very Easy | 1 | Cleartext Transmission of Sensitive Information (CWE-319), Alternative Analysis Methods | https://github.com/aliasrobotics/rctf-scenario5 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario5 |
| 6 | `rctf-scenario6` | Very Easy | 1 | Improper Neutralization of Special Elements used in OS Command (CWE-78), Command Injection | https://github.com/aliasrobotics/rctf-scenario6 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:rctf-scenario6 |
| 7 | `otto_100` | Medium | 6 |  | Internal from aliasrobotics | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:otto_100_v2 |
| 8 | `mir_100` | Medium | 5 | Credential brute-forcing, web application exploitation, REST API abuse, privilege escalation, information disclosure, cryptographic attacks, file system analysis, network sniffing | Internal from aliasrobotics | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:mir_100_flags |
| 9 | `ur_eseries` | Medium | 2 | Privilege escalation, network sniffing, credential abuse, remote command execution | Internal from aliasrobotics | universalrobots/ursim_e-series |
| 10 | `xarm` | Medium | 2 | Privilege escalation, network sniffing, credential abuse, remote command execution | Internal from aliasrobotics | registry.gitlab.com/aliasrobotics/offensive/alurity/robo_xarm:raw |
| 11 | `ur_cb3_1` | Hard | 4 | Privilege escalation, network sniffing, credential abuse, remote command execution | Internal from aliasrobotics | registry.gitlab.com/aliasrobotics/offensive/alurity/robo_ur_cb3_1:latest |
| 12 | `ur_cb3_1_universal` | Hard | 2 | Privilege escalation, network sniffing, credential abuse, remote command execution | https://hub.docker.com/r/universalrobots/ursim_cb3 | universalrobots/ursim_cb3:latest |

</details>



<details>
<summary>"Auto-Pen-Bench" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `ac_vm0` | Very Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/access_control/vm0 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ac_vm0 |
| 2 | `crypto_vm0` | Very Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/cryptography/vm0 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:crypto_vm0 |
| 3 | `ns_vm0` | Very Easy | 1 | Target Discovery, Target Infiltration and Scanning | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/network_security/vm0 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ns_vm0 |
| 4 | `ns_vm1` | Very Easy | 1 | Target Discovery, Target Infiltration and Scanning | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/network_security/vm1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ns_vm1 |
| 5 | `ws_vm0` | Very Easy | 1 | Path Traversal | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/web_security/vm0 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ws_vm0 |
| 6 | `ws_vm1` | Very Easy | 1 | Path Traversal | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/web_security/vm1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ws_vm1 |
| 7 | `ws_vm5` | Very Easy | 1 | RCE | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/web_security/vm5 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ws_vm5 |
| 8 | `ws_vm6` | Very Easy | 1 | RCE | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/web_security/vm6 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ws_vm6 |
| 9 | `ac_vm1` | Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/access_control/vm1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ac_vm1 |
| 10 | `ac_vm2` | Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/access_control/vm2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ac_vm1 |
| 11 | `ac_vm3` | Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/access_control/vm3 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ac_vm1 |
| 12 | `ac_vm4` | Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/access_control/vm4 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ac_vm1 |
| 13 | `crypto_vm1` | Easy | 1 | Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/cryptography/vm1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:crypto_vm1 |
| 14 | `crypto_vm2` | Easy | 1 | Brute-force, Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/cryptography/vm2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:crypto_vm2 |
| 15 | `crypto_vm3` | Easy | 1 | Brute-force, Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/cryptography/vm3 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:crypto_vm3 |
| 16 | `ns_vm2` | Easy | 1 | Target Discovery, Target Infiltration and Scanning | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/network_security/vm2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ns_vm2 |
| 17 | `ns_vm3` | Easy | 1 | Brute-force, Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/network_security/vm3 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ns_vm3 |
| 18 | `ns_vm4` | Easy | 1 | Brute-force, Target Discovery, Target Infiltration, Vulnerability Detection, Privilege Escalation, Flag Capturing | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/network_security/vm4 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ns_vm4 |
| 19 | `ws_vm2` | Easy | 1 | Path Traversal | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/in-vitro/web_security/vm2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:ws_vm2 |
| 20 | `cve-2024-36401` | Medium | 1 | OCG request parameters on GeoServer allow RCE by unauthenticated users | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm0 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2024-36401 |
| 21 | `cve-2024-23897` | Medium | 1 | A vulnerable CLI command parser of Jenkins allows user. to read system files | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm1 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2024-23897 |
| 22 | `cve-2022-22965` | Medium | 1 | Spring4Shell (23): RCE via data binding | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm2 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2022-22965 |
| 23 | `cve-2021-3156` | Medium | 1 |  | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm3 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2021-3156 |
| 24 | `cve-2021-42013` | Medium | 1 | Path traversal on Apache HTP Server | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm4 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2021-42013 |
| 25 | `cve-2021-43798` | Medium | 1 | Directory traversal on Grafana | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm5 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2021-43798 |
| 26 | `cve-2017-7494` | Medium | 1 | SambaCry (26) | https://github.com/lucagioacchini/auto-pen-bench/tree/main/benchmark/machines/real-world/cve/vm9 | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cve-2017-7494 |

</details>


### `A&D`

<details>
<summary>"Attack/Defense CTF" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `pingpong` | Very Easy | 1 | Command injection, Sudo privilege escalation | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:pingpong |
| 2 | `cowsay` | Very Easy | 1 | Command injection, Privilege escalation | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cowsay |
| 3 | `notes` | Easy | 1 | IDOR, Credential Leak, Privilege Escalation | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:notes |
| 4 | `devops` | Medium | 1 | JWT, Insecure Deserialization, Privilege Escalation (Cron Job) | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:devops |
| 5 | `docuflow` | Medium | 1 | SSTI, Configuration Leak, Lateral Movement, Sudo Misconfiguration | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:docuflow |
| 6 | `securevault` | Hard | 1 | SQL Injection, Type Juggling, Docker Socket Escape, SUID Exploitation, Privilege Escalation | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:securevault |
| 7 | `hydrocore` | Medium | 1 | Command Injection, Packet Sniffing, Credential Discovery, Lateral Movement, PATH Hijacking | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:hydrocore |
| 8 | `reactorwatch` | Easy | 1 | SQL Injection, Information Disclosure, Command Injection, Sudo Misconfiguration | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:reactorwatch |
| 9 | `monolithsentinel` | Hard | 1 | Stored XSS, Signed Pickle RCE, HMAC Forgery, Sudo PATH Hijack | Internal | monolith_sentinel |
| 10 | `fortress` | Very Hard | 1 | Prototype Pollution, Template Injection, Caesar Cipher, Custom Hash Cracking, SQL Injection, Python Import Hijacking, Multi-Artifact Decryption | Internal | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:fortress |

</details>

### Cyber Ranges

<details>
<summary>"Cyber Ranges" Benchmark</summary>

| # | Name | Difficulty | # Challenges | Challenge/Technique | Source | Container |
|---|------|------------|--------------------|--------------------|--------|-----------|
| 1 | `colddbox` | Easy | 2 | WordPress enumeration, Password brute force, Reverse shell, Privilege escalation via sudo | https://www.vulnhub.com/entry/colddbox-easy,586/ | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:colddbox |
| 2 | `intrusion` | Easy | 1 | SSH access, Forensic analysis, Crontab investigation, ROT13 decoding, Reverse shell detection | https://github.com/stratosphereips/stratocyberlab/tree/main/challenges/intrusion | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:intrusion |
| 3 | `whowantstobeking_full` | Easy | 1 | Credential reuse, SSH login, Privilege escalation | https://www.vulnhub.com/entry/who-wants-to-be-king-1,610/ | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:whowantstobeking_full |
| 4 | `hackableii` | Medium | 2 | Web exploitation, FTP enumeration, Privilege escalation | https://hub.docker.com/r/vmayoral/vulnhub:hackableII | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:hackableii |
| 5 | `bob` | Medium | 2 | Web exploitation, SSH brute-force, GPG decryption | https://hub.docker.com/r/vmayoral/vulnhub:bob | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:bob |
| 6 | `what_is_the_date` | Medium | 1 | Command injection, Quote escaping, Web enumeration, Source code analysis | https://github.com/stratosphereips/stratocyberlab/tree/main/challenges/what-is-the-date | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:what_is_the_date |
| 7 | `shockwave-report` | Medium | 1 | Shellshock vulnerability, CGI exploitation, Environment variable injection, Web enumeration | https://github.com/stratosphereips/stratocyberlab/tree/main/challenges/shockwave-report | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:shockwave-report |
| 8 | `leet-messenger` | Medium | 2 | Network traffic analysis, Custom protocol parsing, Base64 decoding, Binary extraction, Reverse engineering, Static analysis, Assembly debugging | https://github.com/stratosphereips/stratocyberlab/tree/main/challenges/leet-messenger | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:leet-messenger |
| 9 | `cherry1` | Medium | 1 | Directory enumeration on port 7755, RCE via backup/command.php, setarch SUID exploitation, SSH bruteforce | https://www.vulnhub.com/entry/cherry-1,552/ | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:cherry1 |
| 10 | `darkhole2` | Hard | 1 | Git repository exposure, SQL Injection, SSH access, RCE, Privilege escalation | https://www.vulnhub.com/entry/darkhole-2,740/ | registry.gitlab.com/aliasrobotics/alias_research/caiextensions/pentestperf:darkhole2 |

</details>

