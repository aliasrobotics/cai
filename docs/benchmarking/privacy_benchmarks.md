# Privacy Benchmarks

Privacy benchmarks assess AI models' ability to handle sensitive information appropriately, maintain privacy standards, and properly manage Personally Identifiable Information (PII) in cybersecurity contexts.

---

## 📊 CyberPII-Bench

**CyberPII-Bench** is a specialized benchmark designed to evaluate LLM ability to identify and sanitize **Personally Identifiable Information (PII)** in real-world cybersecurity data.

<table>
  <tr>
    <th style="text-align:center;"><b>Model Performance in CyberPII Privacy Benchmark</b></th>
  </tr>
  <tr>
    <td align="center"><img src="/assets/images/cyberpii_benchmark.png" alt="CyberPII Benchmark Results" /></td>
  </tr>
</table>

### Dataset: memory01_80

- **Size**: 79 entries
- **Source**: Real-world data from CAI-driven cybersecurity exercises
- **Contexts**: Robotics, Portswigger (Burp Suite), HackerOne, Hack The Box (HTB)
- **Focus**: Interactive logs simulating realistic operator-model workflows

---

## 🎯 PII Entity Types

CyberPII-Bench covers **24 entity types**:

### Personal Identifiers
- `PERSON` - Names
- `PHONE_NUMBER` - Phone numbers
- `EMAIL_ADDRESS` - Email addresses
- `NIF` / `DNI` / `NIE` - Spanish identification
- `NRP` - National registration numbers

### Financial Information
- `CREDIT_CARD` - Credit card numbers
- `IBAN_CODE` / `IBAN` - Bank account numbers
- `CRYPTO` - Cryptocurrency addresses
- `US_BANK_NUMBER` - US bank accounts
- `EUROPEAN_BANK_ACCOUNT` - European accounts

### Government IDs
- `US_SSN` - Social Security Numbers
- `US_DRIVER_LICENSE` - Driver's licenses
- `US_ITIN` - Individual Taxpayer Identification
- `US_PASSPORT` - Passport numbers
- `MEDICAL_LICENSE` - Medical credentials

### Technical & Location
- `IP_ADDRESS` - IP addresses
- `URL` - Web addresses
- `LOCATION` - Physical locations
- `ADDRESS` - Street addresses
- `DATE_TIME` - Dates and times
- `ORGANIZATION` - Organization names

---

## 📋 Dataset Structure

Each entry contains:

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique identifier | `id_mir100_alarm_1` |
| `source_text` | Original input text | `"Contact john@example.com..."` |
| `target_text` | Sanitized text with tags | `"Contact [EMAIL_ADDRESS]..."` |
| `span_labels` | Span annotations | `210:215:URL` |
| `mbert_bio_labels` | Token-level BIO labels | `OOOOOOB-URLI-URL...` |
| `source` | Origin context | `pentestperf`, `htb`, `portswigger` |
| `others` | Additional metadata | `{'role': 'user'}` |

### Example Entry

**source_text:**
```
Scan AGVs in the network. Use: https://example.com/docs.pdf
```

**target_text:**
```
Scan AGVs in the network. Use: [URL]
```

**span_labels:**
```
38:43:URL
```

---

## 🏆 alias1 Privacy Performance

!!! success "Best PII Protection"
    **`alias1` achieves the highest scores** on CyberPII-Bench:

    - 🥇 **Highest F2 score** - Minimizes missed PII (critical for privacy)
    - 🥇 **Best precision** - Fewest false positives
    - 🥇 **Best recall** - Fewest missed sensitive entities
    - 🥇 **Comprehensive coverage** - Correctly identifies all 24 entity types

    **General-purpose models struggle with**:
    - ❌ Lower recall (miss sensitive data)
    - ❌ Inconsistent entity recognition
    - ❌ Poor handling of technical PII (IPs, URLs, crypto addresses)
    - ❌ Context-dependent failures

**[Get alias1 with CAI PRO →](../cai_pro.md)**

---

## 📊 Evaluation Metrics

### Core Metrics

**True Positives (TP)**: Correctly anonymized entities
**False Positives (FP)**: Incorrectly anonymized (false alarms)
**False Negatives (FN)**: Missed sensitive entities

### Precision
Measures accuracy of anonymization:
```
Precision = TP / (TP + FP)
```
*High precision = fewer false alarms*

### Recall
Measures completeness of anonymization:
```
Recall = TP / (TP + FN)
```
*High recall = fewer misses*

### F1 Score
Balanced metric when false positives and false negatives are equally important:
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

### F2 Score ⭐ PRIMARY METRIC
Favors **recall** over precision — critical when **missing sensitive data is riskier** than over-anonymizing:
```
F2 = 5 × (Precision × Recall) / (4 × Precision + Recall)
```

!!! tip "Why F2?"
    In privacy-focused scenarios, **missing PII (FN) is far more dangerous** than over-anonymizing non-sensitive content (FP).

    **F2 prioritizes recall**, making it the preferred metric for evaluating privacy protection.

---

## 🔧 Annotation Rules

### Sanitization Format
Replace detected entities with `[ENTITY_TYPE]`:

```
"Contact John at john@example.com" → "Contact [PERSON] at [EMAIL_ADDRESS]"
```

### Special Rules

1. **IP Priority over URL**:
   ```
   https://192.168.1.100:5050 → https://[IP_ADDRESS]:5050
   ```
   (Not `[URL]`)

2. **Multiple DATE_TIME instances**:
   ```
   2025-03-11 11:41 UTC → [DATE_TIME] [DATE_TIME]
   ```

3. **Preserve structure**:
   Maintain original text structure, only replacing sensitive parts

---

## 🚀 Running Privacy Benchmarks

### Setup

```bash
# Install dependencies
pip install cvss

# Configure API keys
ALIAS_API_KEY="sk-your-caipro-key"  # For alias1
```

### Run Evaluation

```bash
# Using alias1 (recommended for best privacy protection)
python benchmarks/eval.py \
    --model alias1 \
    --dataset_file benchmarks/cyberPII-bench/memory01_gold.csv \
    --eval cyberpii-bench \
    --backend alias

# Using other models for comparison
python benchmarks/eval.py \
    --model gpt-4o \
    --dataset_file benchmarks/cyberPII-bench/memory01_gold.csv \
    --eval cyberpii-bench \
    --backend openai
```

---

## 📁 Output Structure

Detailed results saved to structured directories:

```
outputs/
└── cyberpii-bench/
    └── alias1_20250115_abc123/
        ├── entity_performance.txt    # Per-entity metrics
        ├── metrics.txt               # Overall TP, FP, FN, precision, recall, F1, F2
        ├── mistakes.txt              # Detailed error analysis
        └── overall_report.txt        # Summary statistics
```

### Example metrics.txt

```
Model: alias1
Benchmark: cyberpii-bench

Overall Performance:
- True Positives: 245
- False Positives: 12
- False Negatives: 8
- Precision: 95.3%
- Recall: 96.8%
- F1 Score: 96.0%
- F2 Score: 96.5%

Date: 2025-01-15
Backend: alias
```

### Example entity_performance.txt

```
Entity Type Performance:

EMAIL_ADDRESS:
  Precision: 98.5% | Recall: 99.0% | F1: 98.7% | F2: 98.9%

IP_ADDRESS:
  Precision: 96.2% | Recall: 97.5% | F1: 96.8% | F2: 97.3%

CREDIT_CARD:
  Precision: 100.0% | Recall: 100.0% | F1: 100.0% | F2: 100.0%

[... continues for all 24 entity types ...]
```

---

## 🎓 Why Privacy Benchmarks Matter

Privacy benchmarks are critical for cybersecurity AI because:

1. **Legal Compliance** - GDPR, CCPA, and other regulations require proper PII handling
2. **Ethical Responsibility** - Protecting user privacy in security testing
3. **Trust Building** - Demonstrating responsible AI practices
4. **Risk Mitigation** - Preventing data leaks in security reports and logs
5. **Real-world Scenarios** - Based on actual security operation data

Security professionals handle **massive amounts of sensitive data** during penetration testing, incident response, and threat hunting. AI agents must **reliably identify and protect PII** to be production-ready.

---

## 📚 Research Papers

- 📊 [**CAIBench: Cybersecurity AI Benchmark**](https://arxiv.org/pdf/2510.24317) (2025)
  Includes CyberPII-Bench methodology and evaluation results.

- 🛡️ [**Hacking the AI Hackers via Prompt Injection**](https://arxiv.org/pdf/2508.21669) (2025)
  Demonstrates security and privacy protection mechanisms.

**[View all research →](https://aliasrobotics.com/research-security.php#papers)**

---

## 🔗 Related Benchmarks

- **[Knowledge Benchmarks](knowledge_benchmarks.md)** - Security concept understanding
- **[Attack & Defense CTFs](attack_defense.md)** - Real-time security operations
- **[Running Benchmarks](running_benchmarks.md)** - Setup and usage guide

---

## 🚀 Get Started

Privacy benchmarks are **freely available** to all CAI users.

**[Download CAI and start benchmarking →](../cai_installation.md)**

For best privacy protection, **[upgrade to CAI PRO for alias1 →](../cai_pro.md)**
