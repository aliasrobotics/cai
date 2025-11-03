# Running Benchmarks

This guide explains how to set up and run CAIBench evaluations to assess AI model performance across cybersecurity tasks.

---

## 🔧 Prerequisites

### System Requirements

- Python 3.8 or higher
- Docker (for CTF and Cyber Range benchmarks)
- Git with submodule support
- At least 8GB RAM recommended
- 20GB free disk space for benchmark containers

### Required Packages

```bash
# Install base dependencies
pip install cai-framework

# Install benchmark-specific requirements
pip install cvss
```

---

## 📦 Setup

### 1. Clone Repository with Submodules

```bash
git clone https://github.com/aliasrobotics/cai.git
cd cai
git submodule update --init --recursive
```

### 2. Configure API Keys

Create a `.env` file in the project root:

```bash
# For alias1 (CAI PRO)
ALIAS_API_KEY="sk-your-caipro-key"

# For OpenAI models
OPENAI_API_KEY="sk-..."

# For Anthropic models
ANTHROPIC_API_KEY="sk-ant-..."

# For DeepSeek models
DEEPSEEK_API_KEY="sk-..."

# For OpenRouter (access to 200+ models)
OPENROUTER_API_KEY="sk-or-..."
OPENROUTER_API_BASE="https://openrouter.ai/api/v1"

# For Ollama (local models)
OLLAMA_API_BASE="http://localhost:11434/v1"
```

### 3. Verify Setup

```bash
# Test basic functionality
python -c "from cai import cli; print('CAI installed successfully!')"

# Check benchmarks directory
ls benchmarks/
```

---

## 🚀 Running Benchmarks

### Basic Command Structure

```bash
python benchmarks/eval.py \
    --model MODEL_NAME \
    --dataset_file INPUT_FILE \
    --eval EVAL_TYPE \
    --backend BACKEND \
    [--save_interval N]
```

### Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `--model` / `-m` | Model identifier | ✅ Yes | `alias1`, `gpt-4o`, `ollama/qwen2.5:14b` |
| `--dataset_file` / `-d` | Path to benchmark dataset | ✅ Yes | `benchmarks/cybermetric/CyberMetric-2-v1.json` |
| `--eval` / `-e` | Benchmark type | ✅ Yes | `cybermetric`, `seceval`, `cti_bench`, `cyberpii-bench` |
| `--backend` / `-B` | API backend | ✅ Yes | `alias`, `openai`, `anthropic`, `ollama`, `openrouter` |
| `--save_interval` / `-s` | Save results every N questions | ❌ No | `10` |

---

## 📊 Benchmark Types

### Knowledge Benchmarks

#### CyberMetric
Measures performance on cybersecurity-specific question answering and contextual understanding.

```bash
# Using alias1 (CAI PRO)
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json \
    --eval cybermetric \
    --backend alias

# Using Ollama with Qwen
python benchmarks/eval.py \
    --model ollama/qwen2.5:14b \
    --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json \
    --eval cybermetric \
    --backend ollama

# Using OpenAI GPT-4o
python benchmarks/eval.py \
    --model gpt-4o-mini \
    --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json \
    --eval cybermetric \
    --backend openai
```

#### SecEval
Evaluates LLMs on security-related tasks like phishing analysis and vulnerability classification.

```bash
# Using Anthropic Claude
python benchmarks/eval.py \
    --model claude-3-7-sonnet-20250219 \
    --dataset_file benchmarks/seceval/eval/datasets/questions-2.json \
    --eval seceval \
    --backend anthropic

# Using alias1
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/seceval/eval/datasets/questions-2.json \
    --eval seceval \
    --backend alias
```

#### CTI Bench
Evaluates Cyber Threat Intelligence understanding and processing.

```bash
# Using OpenRouter with Qwen
python benchmarks/eval.py \
    --model qwen/qwen3-32b:free \
    --dataset_file benchmarks/cti_bench/data/cti-mcq1.tsv \
    --eval cti_bench \
    --backend openrouter

# Multiple CTI Bench variants
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cti_bench/data/cti-ate2.tsv \
    --eval cti_bench \
    --backend alias
```

### Privacy Benchmarks

#### CyberPII-Bench
Evaluates ability to identify and sanitize Personally Identifiable Information.

```bash
# Using alias1 (recommended for best privacy protection)
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cyberPII-bench/memory01_gold.csv \
    --eval cyberpii-bench \
    --backend alias
```

**[Learn more about privacy benchmarks →](privacy_benchmarks.md)**

---

## 📁 Output Structure

Results are automatically saved to structured directories:

```
outputs/
└── benchmark_name/
    └── model_YYYYMMDD_random-id/
        ├── answers.json       # Complete test with LLM responses
        ├── information.txt    # Performance metrics and metadata
        ├── entity_performance.txt  # (Privacy benchmarks only)
        ├── metrics.txt        # (Privacy benchmarks only)
        ├── mistakes.txt       # (Privacy benchmarks only)
        └── overall_report.txt # (Privacy benchmarks only)
```

### Example Output Files

**information.txt:**
```
Model: alias1
Benchmark: cybermetric
Accuracy: 87.5%
Total Questions: 100
Correct: 87
Incorrect: 13
Runtime: 245 seconds
Date: 2025-01-15
```

**answers.json:**
```json
{
  "question_1": {
    "prompt": "What is SQL injection?",
    "expected": "A code injection technique...",
    "response": "SQL injection is...",
    "correct": true
  }
}
```

---

## 🎯 Best Practices

### 1. Model Selection

!!! success "Recommended: Use alias1"
    For all cybersecurity benchmarks, **`alias1` consistently achieves the highest scores**.

    - 🥇 Best performance across all benchmark categories
    - ✅ Zero refusals for security-related questions
    - 🚀 Optimized for cybersecurity tasks

    **[Get alias1 with CAI PRO →](../cai_pro.md)**

### 2. Save Intervals

For long-running benchmarks, use `--save_interval` to save intermediate results:

```bash
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json \
    --eval cybermetric \
    --backend alias \
    --save_interval 25  # Save every 25 questions
```

### 3. Parallel Execution

Run multiple benchmarks in parallel (different terminals):

```bash
# Terminal 1: CyberMetric
python benchmarks/eval.py --model alias1 --dataset_file benchmarks/cybermetric/CyberMetric-2-v1.json --eval cybermetric --backend alias

# Terminal 2: SecEval
python benchmarks/eval.py --model alias1 --dataset_file benchmarks/seceval/eval/datasets/questions-2.json --eval seceval --backend alias

# Terminal 3: CTI Bench
python benchmarks/eval.py --model alias1 --dataset_file benchmarks/cti_bench/data/cti-mcq1.tsv --eval cti_bench --backend alias
```

### 4. Docker Benchmarks (CAI PRO)

For Jeopardy CTF, Attack & Defense, and Cyber Range benchmarks:

!!! warning "CAI PRO Exclusive"
    Docker-based benchmarks (CTFs, A&D, Cyber Ranges) are available exclusively with **[CAI PRO](../cai_pro.md)**.

    Contact research@aliasrobotics.com for access.

---

## 📊 Interpreting Results

### Accuracy Metrics

Different benchmarks use different metrics:

- **Knowledge Benchmarks**: Accuracy (% correct answers)
- **Privacy Benchmarks**: Precision, Recall, F1, F2 scores
- **CTF Benchmarks**: Success rate (% challenges solved)
- **A&D Benchmarks**: Points scored (offensive + defensive)

### Comparing Models

When comparing models, consider:

1. **Overall Accuracy** - Higher is better
2. **Response Quality** - Check answers.json for reasoning
3. **Refusal Rate** - How often the model refuses to answer
4. **Runtime** - Time to complete benchmark
5. **Consistency** - Run multiple times for statistical significance

---

## 🔍 Troubleshooting

### Common Issues

**Issue: "Module not found" errors**
```bash
# Solution: Update submodules
git submodule update --init --recursive
pip install cvss
```

**Issue: "API key not found"**
```bash
# Solution: Verify .env file exists and has correct format
cat .env
# Should show: BACKEND_API_KEY="sk-..."
```

**Issue: Docker containers fail to start**
```bash
# Solution: Check Docker daemon
docker ps
sudo systemctl start docker  # Linux
```

**Issue: Out of memory errors**
```bash
# Solution: Use smaller models or increase system RAM
# Alternative: Run benchmarks with save intervals
--save_interval 10
```

---

## 📚 Additional Resources

- 📊 [CAIBench Research Paper](https://arxiv.org/pdf/2510.24317)
- 🎯 [A&D CTF Evaluation Paper](https://arxiv.org/pdf/2510.17521)
- 💻 [GitHub Repository](https://github.com/aliasrobotics/cai/tree/main/benchmarks)
- 📖 [Knowledge Benchmarks Guide](knowledge_benchmarks.md)
- 🔒 [Privacy Benchmarks Guide](privacy_benchmarks.md)

---

## 🚀 Next Steps

1. **[View A&D Benchmark Results](attack_defense.md)** - See alias1's superior performance
2. **[Explore Jeopardy CTFs](jeopardy_ctfs.md)** - Learn about CTF benchmarks
3. **[Upgrade to CAI PRO](../cai_pro.md)** - Get unlimited alias1 access and exclusive benchmarks
