# Knowledge Benchmarks

Knowledge benchmarks evaluate AI models' understanding of cybersecurity concepts, threat intelligence, vulnerability analysis, and security best practices through question-answering and knowledge extraction tasks.

---

## 📊 Available Benchmarks

### SecEval
Benchmark designed to evaluate LLMs on security-related tasks including phishing email analysis, vulnerability classification, and response generation.

- **Type**: Multiple choice and open-ended questions
- **Coverage**: Phishing detection, malware analysis, vulnerability assessment, security policy
- **Dataset**: Real-world security scenarios
- **Source**: [SecEval Repository](https://github.com/XuanwuAI/SecEval)

### CyberMetric
Framework focusing on measuring AI performance in cybersecurity-specific question answering, knowledge extraction, and contextual understanding.

- **Type**: Question-answering with contextual reasoning
- **Coverage**: Security concepts, best practices, incident response, threat modeling
- **Emphasis**: Domain knowledge and reasoning ability
- **Source**: [CyberMetric Repository](https://github.com/CyberMetric)

### CTIBench
Benchmark focused on evaluating LLM capabilities in understanding and processing Cyber Threat Intelligence (CTI) information.

- **Type**: Multiple choice questions and attribute extraction
- **Coverage**: Threat actor analysis, malware attribution, IOC extraction, MITRE ATT&CK mapping
- **Dataset**: CTI-MCQ (multiple choice) and CTI-ATE (attribute extraction)
- **Source**: [CTIBench Repository](https://github.com/xashru/cti-bench)

---

## 🎯 What Knowledge Benchmarks Measure

### Security Concept Understanding
- Vulnerability types and classifications
- Attack vectors and techniques
- Defense mechanisms and controls
- Security principles and best practices

### Threat Intelligence
- Threat actor capabilities and motivations
- Malware families and characteristics
- Indicators of Compromise (IOCs)
- Tactics, Techniques, and Procedures (TTPs)

### Incident Response
- Incident detection and classification
- Response procedures and priorities
- Forensic analysis techniques
- Recovery and remediation strategies

### Risk Assessment
- Threat modeling methodologies
- Vulnerability scoring (CVSS)
- Risk prioritization frameworks
- Security architecture evaluation

---

## 🏆 alias1 Knowledge Performance

!!! success "Superior Knowledge Capabilities"
    **`alias1` demonstrates exceptional performance** on cybersecurity knowledge benchmarks:

    - 🥇 **Highest accuracy** across all three major knowledge benchmarks
    - 🥇 **Contextual understanding** - Correctly interprets complex security scenarios
    - 🥇 **Zero refusals** - Provides comprehensive answers for all security questions
    - 🥇 **Technical depth** - Detailed explanations with practical examples

    **General-purpose models show**:
    - ❌ Lower accuracy on specialized security concepts
    - ❌ Oversimplified or generic responses
    - ❌ Refusals on sensitive security topics
    - ❌ Missing contextual nuances in CTI analysis

**[Get alias1 with CAI PRO →](../cai_pro.md)**

---

## 🚀 Running Knowledge Benchmarks

### Prerequisites

```bash
# Install dependencies
pip install cvss

# Configure API keys in .env file
ALIAS_API_KEY="sk-your-caipro-key"  # For alias1
OPENAI_API_KEY="sk-..."             # For OpenAI models
ANTHROPIC_API_KEY="sk-ant-..."      # For Anthropic models
OLLAMA_API_BASE="http://localhost:11434/v1"  # For local models
```

### CyberMetric Evaluation

```bash
# Using alias1 (recommended)
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

### SecEval Evaluation

```bash
# Using alias1
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/seceval/eval/datasets/questions-2.json \
    --eval seceval \
    --backend alias

# Using Anthropic Claude
python benchmarks/eval.py \
    --model claude-3-7-sonnet-20250219 \
    --dataset_file benchmarks/seceval/eval/datasets/questions-2.json \
    --eval seceval \
    --backend anthropic
```

### CTIBench Evaluation

```bash
# Multiple choice questions
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cti_bench/data/cti-mcq1.tsv \
    --eval cti_bench \
    --backend alias

# Attribute extraction tasks
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cti_bench/data/cti-ate2.tsv \
    --eval cti_bench \
    --backend alias

# Using OpenRouter
python benchmarks/eval.py \
    --model qwen/qwen3-32b:free \
    --dataset_file benchmarks/cti_bench/data/cti-mcq1.tsv \
    --eval cti_bench \
    --backend openrouter
```

---

## 📁 Output Structure

Results are saved to structured directories:

```
outputs/
└── cybermetric/  (or seceval, cti_bench)
    └── alias1_20250115_abc123/
        ├── answers.json       # Complete test with responses
        └── information.txt    # Performance metrics
```

### Example information.txt

```
Model: alias1
Benchmark: cybermetric
Accuracy: 92.5%
Total Questions: 100
Correct: 92
Incorrect: 8
Runtime: 145 seconds
Date: 2025-01-15
Backend: alias
```

---

## 📊 Evaluation Metrics

### Accuracy
Percentage of correctly answered questions:
```
Accuracy = (Correct Answers / Total Questions) × 100%
```

### Category Performance
Breakdown by question category:
- Vulnerability analysis: 95%
- Threat intelligence: 90%
- Incident response: 88%
- Security architecture: 92%

### Response Quality
Qualitative assessment of answer quality:
- Correctness
- Completeness
- Technical depth
- Practical applicability

---

## 🎓 Why Knowledge Benchmarks Matter

Knowledge benchmarks are essential for evaluating cybersecurity AI because:

1. **Foundation Skills** - Tests understanding of core security concepts
2. **Decision Making** - Evaluates ability to make informed security judgments
3. **Contextual Reasoning** - Assesses comprehension beyond memorization
4. **Practical Application** - Measures ability to apply knowledge to scenarios
5. **Domain Expertise** - Validates specialized cybersecurity understanding

Unlike hands-on CTF challenges, knowledge benchmarks assess the **theoretical foundation** that enables effective security analysis and decision-making.

---

## 📚 Research Papers

- 📊 [**CAIBench: Cybersecurity AI Benchmark**](https://arxiv.org/pdf/2510.24317) (2025)
  Includes knowledge benchmark evaluation methodology.

- 🚀 [**Cybersecurity AI (CAI) Framework**](https://arxiv.org/pdf/2504.06017) (2025)
  Demonstrates knowledge-driven security operations.

**[View all research →](https://aliasrobotics.com/research-security.php#papers)**

---

## 🔗 Related Benchmarks

- **[Privacy Benchmarks](privacy_benchmarks.md)** - PII handling evaluation
- **[Jeopardy CTFs](jeopardy_ctfs.md)** - Practical skill assessment
- **[Running Benchmarks](running_benchmarks.md)** - Setup and usage guide

---

## 🚀 Get Started

Knowledge benchmarks are **freely available** to all CAI users.

**[Download CAI and start benchmarking →](../cai_installation.md)**

For best performance, **[upgrade to CAI PRO for alias1 →](../cai_pro.md)**
