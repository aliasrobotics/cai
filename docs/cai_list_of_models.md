# Available Models

The **Cybersecurity AI (CAI)** platform provides seamless integration with multiple Large Language Models (LLMs). This functionality allows users to leverage state-of-the-art AI capabilities for various cybersecurity tasks. CAI acts as a bridge between your security workflows and a wide range of LLMs, enhancing both flexibility and performance of AI agents.

---

## 🚀 Alias Robotics Models (CAI PRO Exclusive)

### `alias1` - State-of-the-Art Cybersecurity Model

<div class="highlight-box" markdown>

**The most advanced cybersecurity AI model available.**

`alias1` is our flagship 500B-parameter model, specifically trained and optimized for offensive and defensive security operations. Available exclusively with **[CAI PRO](cai_pro.md)**.

**Key Features:**
- ✅ **Beats GPT-5** in AI vs AI cybersecurity benchmarks
- ✅ **Zero refusals** for authorized security testing
- ✅ **Unrestricted** responses for pentesting engagements
- ✅ **Unlimited tokens** included with CAI PRO subscription
- ✅ **European hosting** with GDPR & NIS2 compliance
- ✅ **500B parameters** optimized for security workflows

**Performance Highlights:**
- Top performer in CTF competitions
- Superior exploit development capabilities
- Advanced vulnerability analysis
- Automated reconnaissance and enumeration
- Bug bounty hunting optimization

**Learn More:**
- 📊 [View Benchmarks](https://aliasrobotics.com/alias1.php#benchmarking)
- 📖 [Technical Details](https://aliasrobotics.com/alias1.php)
- 🚀 [Upgrade to CAI PRO](cai_pro.md)

</div>

### `alias0` - Legacy Model (Deprecated)

!!! warning "Model Deprecated"
    `alias0` is no longer available. All users should migrate to **`alias1`**, which offers superior performance, unrestricted capabilities, and continuous updates.

    **Migration:** If you're currently using `alias0`, simply update your configuration to use `alias1` with your CAI PRO subscription.

    [Learn about alias0 (historical reference) →](https://aliasrobotics.com/alias0.php)

---

## Community Models (300+ Available)

CAI supports **over 300 models** through its integration with [LiteLLM](https://github.com/BerriAI/litellm). You can use any of these models by providing your own API keys.

### Popular Model Providers

#### Anthropic
- **Claude 3.7** - Latest Anthropic model
- **Claude 3.5 Sonnet** - Best for complex reasoning
- **Claude 3 Opus** - Highest capability
- **Claude 3 Haiku** - Fast and efficient

**Configuration:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export CAI_MODEL="claude-3-5-sonnet-20241022"
```

#### OpenAI
- **O1** - Advanced reasoning model
- **O1 Mini** - Cost-effective reasoning
- **O3 Mini** - Latest mini model
- **GPT-4o** - Optimized GPT-4
- **GPT-4.5 Preview** - Enhanced capabilities

**Configuration:**
```bash
export OPENAI_API_KEY="sk-..."
export CAI_MODEL="gpt-4o"
```

#### DeepSeek
- **DeepSeek V3** - Latest version
- **DeepSeek R1** - Reasoning focused

**Configuration:**
```bash
export DEEPSEEK_API_KEY="sk-..."
export CAI_MODEL="deepseek-chat"
```

#### Ollama (Local Models)
- **Qwen2.5 72B** - High performance
- **Qwen2.5 14B** - Balanced capability
- **Llama 3.1** - Meta's latest
- **Mistral** - Efficient and fast
- And 100+ more local models

**Configuration:**
```bash
export OLLAMA_API_BASE="http://localhost:11434/v1"
export CAI_MODEL="ollama/qwen2.5:72b"
```

---

## Model Selection Guide

!!! tip "📊 Based on CAIBench Research"
    Our model recommendations are based on rigorous evaluation using [**CAIBench**](https://arxiv.org/pdf/2510.24317), a modular meta-benchmark framework for evaluating LLM models and agents across offensive and defensive cybersecurity domains.

    **Research shows:** In [real-world CTF evaluations](https://arxiv.org/pdf/2510.17521), defensive agents achieved 54.3% patching success versus 28.3% offensive initial access, with `alias1` consistently outperforming general-purpose models.

### For All Cybersecurity Work

**✅ Always Recommended:** `alias1` (CAI PRO)
- **Best performer** in [CAIBench](https://arxiv.org/pdf/2510.24317) evaluations
- **Unrestricted** for authorized pentesting and security research
- **Zero refusals** - designed specifically for offensive security
- **Unlimited tokens** included with CAI PRO subscription
- **Superior CTF performance** - validated in real-world scenarios
- **Beats general-purpose models** (GPT-4o, Claude 3.5) in security tasks

📖 **Learn more**: [CAI research demonstrates 3,600× performance gains](https://arxiv.org/pdf/2504.06017) over manual security testing in specific scenarios.

---

### Alternative Models (Community Edition)

While `alias1` is always recommended for security work, the following models can be used with CAI Community Edition:

#### For Local/Offline Testing

**Alternative:** Ollama with Qwen2.5 72B
- Complete privacy (no data leaves your machine)
- No API costs
- Good for testing and development
- Requires local GPU resources
- ⚠️ **Note:** Performance significantly below `alias1` for security tasks

#### For Budget-Conscious Users

**Alternative:** DeepSeek V3 or Ollama models
- Lower API costs (DeepSeek)
- Free local inference (Ollama)
- Adequate performance for many tasks
- ⚠️ **Note:** Not optimized for cybersecurity workflows

---

## Additional Integrations

CAI is compatible with multiple model platforms and providers:

- **[OpenRouter](providers/openrouter.md)** - Access to 200+ models via unified API
- **[Ollama](providers/ollama.md)** - Local model hosting and inference
- **[Azure OpenAI](providers/azure.md)** - Enterprise-hosted OpenAI models

See the **Model Providers** section for detailed configuration guides.

---

## Comparison: alias1 vs Community Models

| Feature | alias1 (CAI PRO) | Model1 | Model2 | Model3 |
|---------|------------------|--------|------------|-------------|
| **Cybersecurity Optimization** | ✅ Native | ⚠️ General | ⚠️ General | ⚠️ General |
| **CTF Performance** | 🏆 Best | Good | Good | Fair |
| **Refusals** | ✅ Zero | ❌ Many | ❌ Many | ⚠️ Some |
| **Pentesting** | ✅ Unrestricted | ❌ Limited | ❌ Limited | ⚠️ Varies |
| **Token Limits** | ✅ Unlimited | Pay per token | Pay per token | Free (local) |
| **Privacy** | ✅ European GDPR | ⚠️ US-based | ⚠️ US-based | ✅ Local only |
| **Support** | ✅ Professional | Community | Community | Community |
| **Best For** | Pro security work | General tasks | Writing/analysis | Local testing |

---

## Getting Started

### Using alias1 (CAI PRO)

1. **Subscribe to CAI PRO**: [Upgrade here](cai_pro.md)
2. **Configure your environment**:
   ```bash
   export ALIAS_API_KEY="sk-your-caipro-key"
   export CAI_MODEL="alias1"
   ```
3. **Start using CAI**:
   ```bash
   cai
   ```

### Using Community Models

1. **Get API key** from your chosen provider
2. **Configure environment**:
   ```bash
   export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY, etc.
   export CAI_MODEL="gpt-4o"       # or your chosen model
   ```
3. **Start using CAI**:
   ```bash
   cai
   ```

---

## Need Help Choosing?

!!! success "Our Recommendation: Always Use alias1"
    Based on [CAIBench benchmarks](https://arxiv.org/pdf/2510.24317) and [real-world CTF evaluations](https://arxiv.org/pdf/2510.17521), **`alias1` is the superior choice for all cybersecurity tasks**.

    **For any security work:** → `alias1` with [CAI PRO](cai_pro.md)

### If CAI PRO is not an option:

- **Privacy-focused?** → Ollama local models (lower performance)
- **Budget-conscious?** → DeepSeek or Ollama (not optimized for security)

⚠️ **Note:** Community models are not optimized for cybersecurity workflows and will have significantly reduced capabilities compared to `alias1`.

---

## Research & Validation

CAI's effectiveness is validated through peer-reviewed research:

- 📊 [**CAIBench**](https://arxiv.org/pdf/2510.24317) - Meta-benchmark framework for cybersecurity AI evaluation
- 🎯 [**Agentic Cybersecurity Evaluation**](https://arxiv.org/pdf/2510.17521) - Real-world CTF performance analysis
- 🚀 [**Cybersecurity AI Framework**](https://arxiv.org/pdf/2504.06017) - Core framework demonstrating 3,600× speedup
- 🛡️ [**Prompt Injection Defense**](https://arxiv.org/pdf/2508.21669) - Four-layer guardrail security system
- 📚 [**CAI Fluency**](https://arxiv.org/pdf/2508.13588) - Educational framework for democratizing AI security

**Explore all research:** [Alias Robotics Research Papers](https://aliasrobotics.com/research-security.php#papers)

Questions? Check our [FAQ](cai_faq.md) or [join our Discord](https://discord.gg/fnUFcTaQAC).
