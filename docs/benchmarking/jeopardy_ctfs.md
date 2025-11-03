# Jeopardy-style CTF Benchmarks

Jeopardy-style Capture The Flag (CTF) challenges evaluate AI agents on independent security tasks across multiple domains: cryptography, web exploitation, binary reversing, forensics, and pwn.

---

## 📊 Available Benchmarks

### Base Benchmark
**21 curated CTF challenges** measuring initial penetration testing capabilities.

- **Difficulty**: 🚩 Very Easy to 🚩🚩🚩 Medium
- **Categories**: Reversing, Miscellaneous, Pwn, Web, Crypto, Forensics
- **Status**: ⚠️ *Saturated* - Frontier cybersecurity models (like alias1) conquer most challenges

<table>
  <tr>
    <th style="text-align:center;"><b>Model Performance in Jeopardy CTFs Base Benchmark</b></th>
  </tr>
  <tr>
    <td align="center"><img src="/assets/images/base_1col.png" alt="Base Benchmark Results" /></td>
  </tr>
</table>

!!! success "alias1 Performance"
    `alias1` achieves **near-perfect scores** on the Base benchmark, demonstrating mastery of fundamental cybersecurity concepts and techniques.

### Cybench Framework
**35 CTF challenges** from the comprehensive Cybench evaluation framework.

- **Difficulty**: 🚩 Very Easy to 🚩🚩🚩🚩🚩 Very Hard
- **Source**: [Cybench Framework for Evaluating Cybersecurity Capabilities and Risk](https://github.com/andyzorigin/cybench)
- **Coverage**: Broad spectrum of real-world security scenarios
- **Note**: 35 of 40 Cybench scenarios (reduced for infrastructure/reproducibility)

### RCTF2 - Robotics CTF
**27 robotics-focused challenges** for attacking and defending robots and robotic frameworks.

- **Difficulty**: 🚩 Very Easy to 🚩🚩🚩🚩🚩 Very Hard
- **Systems Covered**: ROS, ROS 2, manipulators, AGVs, AMRs, collaborative robots, legged robots, humanoids
- **Unique Focus**: Only benchmark evaluating AI capabilities against robotic systems

---

## 🎯 Challenge Categories

### Web Exploitation
Vulnerabilities in web applications and services:
- SQL Injection
- Cross-Site Scripting (XSS)
- Server-Side Template Injection (SSTI)
- Authentication bypasses
- API vulnerabilities

### Binary Exploitation (Pwn)
Memory corruption and exploitation:
- Buffer overflows
- Format string vulnerabilities
- Return-oriented programming (ROP)
- Heap exploitation
- Use-after-free

### Cryptography
Breaking or exploiting cryptographic implementations:
- Weak encryption algorithms
- Poor key management
- Custom cryptography flaws
- Hash collisions
- Padding oracle attacks

### Reverse Engineering
Analyzing and understanding compiled binaries:
- Assembly code analysis
- Decompilation and deobfuscation
- Anti-debugging techniques
- Packed/encrypted binaries
- Firmware analysis

### Forensics
Investigating and extracting information from data:
- File carving
- Steganography
- Memory forensics
- Network traffic analysis
- Log analysis

### Miscellaneous
Challenges that don't fit standard categories:
- OSINT (Open Source Intelligence)
- Scripting and automation
- Logic puzzles
- Unconventional attack vectors

---

## 🏆 alias1 Performance

!!! success "Superior Jeopardy CTF Performance"
    **`alias1` consistently outperforms all other AI models** in Jeopardy-style CTF benchmarks:

    - 🥇 **Highest solve rate** across all difficulty levels
    - 🥇 **Fastest time to solve** for timed challenges
    - 🥇 **Best multi-category performance** - Excels in web, pwn, crypto, forensics, and reversing
    - 🥇 **Zero refusals** - Unrestricted responses for all CTF challenges

    **General-purpose models** (GPT-4o, Claude 3.5) show:
    - ❌ High refusal rates on pwn/exploitation challenges
    - ❌ Inconsistent performance across categories
    - ❌ Limited success on medium+ difficulty challenges

**[Get alias1 with CAI PRO →](../cai_pro.md)**

---

## 🚀 Running Jeopardy CTF Benchmarks

!!! warning "CAI PRO Exclusive"
    Jeopardy-style CTF benchmarks are available exclusively with **[CAI PRO](../cai_pro.md)** subscriptions.

    General users can access:
    - [Knowledge benchmarks](knowledge_benchmarks.md)
    - [Privacy benchmarks](privacy_benchmarks.md)

### For CAI PRO Subscribers

Docker-based CTF environments can be launched individually or in batches:

```bash
# Run single CTF challenge
docker run -it cai-ctf/base:challenge-01

# Run full Base benchmark suite
python benchmarks/eval_ctf.py --benchmark base --model alias1

# Run Cybench evaluation
python benchmarks/eval_ctf.py --benchmark cybench --model alias1

# Run RCTF2 robotics challenges
python benchmarks/eval_ctf.py --benchmark rctf2 --model alias1
```

Contact research@aliasrobotics.com for detailed setup instructions.

---

## 📊 Benchmark Configuration

CTF configurations are defined in [`ctf_configs.jsonl`](https://github.com/aliasrobotics/cai/blob/main/src/cai/caibench/ctf-jsons/ctf_configs.jsonl):

```json
{
  "name": "example-ctf",
  "category": "web",
  "difficulty": "medium",
  "points": 100,
  "flag_format": "CTF{...}",
  "docker_image": "cai-ctf/web-01:latest",
  "timeout": 3600
}
```

---

## 🎓 Why Jeopardy CTFs Matter

Jeopardy-style CTFs are essential for evaluating cybersecurity AI because:

1. **Diverse Skillset** - Tests wide range of security knowledge and techniques
2. **Independent Challenges** - Isolates specific capabilities without dependencies
3. **Scalable Difficulty** - From beginner to elite-level challenges
4. **Real-world Relevance** - Based on actual vulnerabilities and attack patterns
5. **Objective Measurement** - Clear success criteria (flag captured or not)

Unlike traditional benchmarks that test general knowledge, CTFs require **active exploitation and problem-solving** - skills critical for real-world penetration testing.

---

## 📚 Research Papers

- 📊 [**CAIBench: Cybersecurity AI Benchmark**](https://arxiv.org/pdf/2510.24317) (2025)
  Meta-benchmark framework including Jeopardy CTF evaluation methodology.

- 🚀 [**Cybersecurity AI (CAI) Framework**](https://arxiv.org/pdf/2504.06017) (2025)
  Core framework demonstrating 3,600× performance improvement using CTF scenarios.

**[View all research →](https://aliasrobotics.com/research-security.php#papers)**

---

## 🔗 Related Benchmarks

- **[Attack & Defense CTFs](attack_defense.md)** - Real-time competitive environments
- **[Cyber Ranges](cyber_ranges.md)** - Complex multi-system scenarios
- **[Running Benchmarks](running_benchmarks.md)** - Setup and usage guide

---

🚀 **[Upgrade to CAI PRO for access to Jeopardy CTF benchmarks →](../cai_pro.md)**
