"""CTR Results Digestion and Interpretation Module.

This module provides functionality to digest CTR (Cut The Rope) game-theoretic
security analysis results into concise, actionable intelligence for agent system prompts.

Two interpretation modes are supported:
1. LLM-based (default): Flexible, nuanced interpretation using language models
2. Algorithmic: Fast, deterministic, rule-based interpretation

Environment Variables:
    CAI_CTR_DIGEST_MODE: Set to "llm" for LLM interpretation, "algorithmic" for rule-based (default: llm)
    CAI_CTR_DIGEST_MODEL: Model to use for LLM interpretation (default: alias1)
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from rich.console import Console

from cai.sdk.agents.models.chatcompletions.litellm_adapter import acompletion_with_timeout

console = Console()

# Global cache for digest results (per-run caching)
# Structure: {(ctr_dir_realpath, mode): digest_string}
_DIGEST_CACHE: Dict[Tuple[str, str], str] = {}

# Global cache for incomplete run directories
# Structure: {ctr_dir_realpath: timestamp_of_last_check}
# This prevents spamming error messages while CTR is running in background
_INCOMPLETE_RUNS: Dict[str, float] = {}
_INCOMPLETE_RETRY_DELAY = 5.0  # Wait 5 seconds before retrying incomplete runs

# Session-level digest cache - stores the CURRENT active digest for each session
# Structure: {(session_id, mode): digest_string}
# This cache provides digest continuity: old digest is used until new one is generated
# Updated ONLY when CTR completes and new digest is ready
_SESSION_DIGEST_CACHE: Dict[Tuple[str, str], str] = {}


def parse_graph_information(graph_text: str) -> Dict[str, Dict[str, any]]:
    """Extract node information from graph_information.txt.

    Args:
        graph_text: Content of graph_information.txt file

    Returns:
        Dictionary mapping node_id to node metadata:
        {
            node_id: {
                'name': str,
                'info': str,
                'vulnerability': bool,
                'message_id': int
            }
        }
    """
    nodes = {}

    # Find the JSON section with nodes
    match = re.search(r'"nodes":\s*\[(.*?)\]', graph_text, re.DOTALL)
    if match:
        nodes_json = f'[{match.group(1)}]'
        try:
            nodes_list = json.loads(nodes_json)
            for node in nodes_list:
                node_id = str(node.get('id', ''))
                nodes[node_id] = {
                    'name': node.get('name', f'Node {node_id}'),
                    'info': node.get('info', ''),
                    'vulnerability': node.get('vulnerability', False),
                    'message_id': node.get('message_id', 0)
                }
        except json.JSONDecodeError as e:
            console.print(f"[yellow]Warning: Could not parse nodes from graph_information.txt: {e}[/yellow]")

    return nodes


def parse_edge_probabilities(graph_text: str) -> Dict[str, float]:
    """Extract edge exploitation probabilities from graph_information.txt.

    Args:
        graph_text: Content of graph_information.txt file

    Returns:
        Dictionary mapping edge description to probability (0-1 decimal):
        {
            'Source Node -> Target Node': 0.99
        }
    """
    edges = {}

    # Find "Edge Exploitation Probabilities:" section
    section_match = re.search(
        r'Edge Exploitation Probabilities:(.*?)(?:\n-{5,}|\Z)',
        graph_text,
        re.DOTALL
    )

    if section_match:
        section = section_match.group(1)
        # Match lines like "Edge (A -> B): 99.00%"
        for match in re.finditer(r'Edge \((.*?)\):\s*([\d.]+)%', section):
            edge_desc = match.group(1)
            probability = float(match.group(2)) / 100.0  # Convert to 0-1
            edges[edge_desc] = probability

    return edges


def interpret_nash_equilibrium(nash_data: Dict) -> Dict[str, any]:
    """Interpret Nash equilibrium for strategic positioning.

    Returns game-theoretic assessment that's generic across all security scenarios.

    Args:
        nash_data: Nash equilibrium results from CTR analysis

    Returns:
        Dictionary with strategic assessment including position, game_value,
        tactical_stance, and confidence level
    """
    attacker_success = nash_data.get('attacker_success', 0)
    defender_success = nash_data.get('defender_success', 0)
    game_value = attacker_success  # In zero-sum games, this is the game value

    # Strategic position based on game value thresholds
    if game_value > 0.5:
        position = "ATTACKER-FAVORED"
        tactical_stance = "High success probability. Exploit identified weaknesses aggressively."
        confidence = "HIGH"
    elif game_value > 0.1:
        position = "CONTESTED"
        tactical_stance = "Moderate success probability. Focus on improving weak transitions."
        confidence = "MEDIUM"
    elif game_value > 0.01:
        position = "DEFENDER-FAVORED"
        tactical_stance = "Low success probability. Extensive reconnaissance needed or consider alternative approaches."
        confidence = "LOW"
    else:
        position = "STRONGLY DEFENDER-FAVORED"
        tactical_stance = "Minimal success probability. Current path unlikely to succeed."
        confidence = "VERY LOW"

    return {
        'position': position,
        'game_value': game_value,
        'tactical_stance': tactical_stance,
        'confidence': confidence
    }


def identify_critical_nodes(paths_data: Dict, edges_prob: Dict[str, float],
                           nodes: Dict[str, Dict]) -> List[Dict[str, any]]:
    """Identify nodes that appear in multiple high-probability paths.

    A node is critical if:
    1. It appears in multiple attack paths
    2. Edges through it have high variance (indicating it's a decision point)
    3. It's not the initial or terminal node

    This is generic for all attack graphs regardless of domain.

    Args:
        paths_data: Attack paths data from CTR
        edges_prob: Edge probability mapping
        nodes: Node metadata mapping

    Returns:
        List of critical nodes sorted by criticality score
    """
    from collections import defaultdict

    # Track node appearances and associated edge probabilities
    node_appearances = defaultdict(list)
    node_path_count = defaultdict(int)

    paths_list = paths_data.get('paths', [])

    for path_data in paths_list:
        path_nodes = path_data if isinstance(path_data, list) else path_data.get('sequence', [])

        # Skip first and last nodes (always start/end)
        for node_id in path_nodes[1:-1]:
            node_id_str = str(node_id).replace('leaf_', '')
            node_path_count[node_id_str] += 1

            # Find edges connected to this node
            node_name = nodes.get(node_id_str, {}).get('name', f'Node {node_id_str}')
            for edge_desc, prob in edges_prob.items():
                if node_name in edge_desc:
                    node_appearances[node_id_str].append(prob)

    # Calculate criticality score
    critical_nodes = []
    for node_id, edge_probs in node_appearances.items():
        if len(edge_probs) < 2:  # Need multiple edges to be a decision point
            continue

        # Criticality = path_count × probability_variance
        # High variance means this node has both strong and weak transitions (decision point)
        variance = max(edge_probs) - min(edge_probs) if edge_probs else 0
        path_count = node_path_count[node_id]
        criticality_score = path_count * variance

        if criticality_score > 0.1:  # Threshold for significance
            node_info = nodes.get(node_id, {})
            critical_nodes.append({
                'node_id': node_id,
                'name': node_info.get('name', f'Node {node_id}'),
                'path_count': path_count,
                'edge_variance': variance,
                'criticality_score': criticality_score,
                'min_prob': min(edge_probs),
                'max_prob': max(edge_probs)
            })

    # Sort by criticality score
    critical_nodes.sort(key=lambda x: x['criticality_score'], reverse=True)
    return critical_nodes


def identify_exploitation_opportunities(nash_data: Dict, nodes: Dict[str, Dict],
                                        threshold: float = 0.15) -> List[Dict[str, any]]:
    """Identify nodes where defender allocates minimal resources.

    These represent exploitation opportunities based on optimal mixed strategy.
    Generic for all security scenarios.

    Args:
        nash_data: Nash equilibrium results
        nodes: Node metadata
        threshold: Nodes with <threshold defense allocation are opportunities

    Returns:
        List of under-defended nodes sorted by opportunity score
    """
    optimal_defense = nash_data.get('optimal_defense', {})

    if not optimal_defense:
        return []

    opportunities = []

    for node_id, allocation in optimal_defense.items():
        allocation_float = float(allocation)

        # Under-defended nodes are opportunities
        if allocation_float < threshold:
            node_info = nodes.get(str(node_id), {})

            # Opportunity score: inverse of allocation (less defense = more opportunity)
            opportunity_score = threshold - allocation_float

            opportunities.append({
                'node_id': node_id,
                'name': node_info.get('name', f'Node {node_id}'),
                'defense_allocation': allocation_float,
                'opportunity_score': opportunity_score,
                'message_id': node_info.get('message_id', 0)
            })

    opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
    return opportunities


def generate_algorithmic_digest(ctr_dir: str) -> str:
    """Generate CTR digest using algorithmic rule-based interpretation.

    This function parses CTR results and applies deterministic rules to identify:
    - Attack paths with node names and transition probabilities
    - Critical bottlenecks (weak attack transitions)
    - High-risk transitions (strong attack transitions)
    - Nash equilibrium interpretation
    - Optimal defense allocation
    - Tactical recommendations

    Args:
        ctr_dir: Path to CTR results directory

    Returns:
        Markdown-formatted digest string

    Raises:
        FileNotFoundError: If required CTR data files are missing
    """
    ctr_path = Path(ctr_dir)

    # Load data files
    try:
        with open(ctr_path / 'nash_equilibrium.json') as f:
            nash_data = json.load(f)
        with open(ctr_path / 'attack_paths.json') as f:
            paths_data = json.load(f)
        with open(ctr_path / 'graph_information.txt') as f:
            graph_text = f.read()
    except FileNotFoundError as e:
        error_msg = f"CTR data incomplete: {e}"
        console.print(f"[red]{error_msg}[/red]")
        raise

    # Parse graph structure
    nodes = parse_graph_information(graph_text)
    edges_prob = parse_edge_probabilities(graph_text)

    # Start building digest
    digest = "## CTR Security Analysis\n\n"

    # Section 1: Attack Paths with enriched information
    paths_list = paths_data.get('paths', [])
    if paths_list:
        digest += "**Identified Attack Paths:**\n"
        for idx, path_data in enumerate(paths_list, 1):
            path_nodes = path_data if isinstance(path_data, list) else path_data.get('sequence', [])

            # Build enriched path string
            path_str = f"Path {idx}: "
            for i, node_id in enumerate(path_nodes):
                # Handle leaf nodes
                node_id_str = str(node_id).replace('leaf_', '')
                node = nodes.get(node_id_str, {})
                node_name = node.get('name', f'Node {node_id}')

                # Handle vulnerability nodes
                if 'leaf_' in str(node_id):
                    node_name = f"Target ({node_name})"

                path_str += node_name

                # Add transition probability if not last node
                if i < len(path_nodes) - 1:
                    next_id = str(path_nodes[i + 1]).replace('leaf_', '')
                    next_node = nodes.get(next_id, {})
                    next_name = next_node.get('name', f'Node {next_id}')

                    # Find edge probability
                    edge_key = f"{node_name} -> {next_name}"
                    prob = edges_prob.get(edge_key, 0)

                    # Symbol based on probability
                    if prob > 0.9:
                        symbol = "═►"  # High probability
                    elif prob > 0.5:
                        symbol = "─→"  # Medium
                    else:
                        symbol = "··→"  # Low (bottleneck)

                    path_str += f" {symbol}[{prob:.0%}] "

            digest += f"{path_str}\n"
        digest += "\n"

    # Section 2: Bottlenecks (defensive opportunities)
    if edges_prob:
        sorted_edges = sorted(edges_prob.items(), key=lambda x: x[1])
        bottlenecks = [(edge, prob) for edge, prob in sorted_edges if prob < 0.95][:3]

        if bottlenecks:
            digest += "**Critical Bottlenecks** (Attack Weaknesses):\n"
            for edge_desc, prob in bottlenecks:
                digest += f"- `{edge_desc}`: {prob:.1%} success rate\n"
            digest += "\n"

    # Section 2.5: Critical Decision Points
    critical_nodes = identify_critical_nodes(paths_data, edges_prob, nodes)

    if critical_nodes:
        digest += "**Critical Decision Points:**\n"
        digest += "These nodes control multiple attack paths with high probability variance:\n"
        for node_info in critical_nodes[:3]:
            digest += f"- **{node_info['name']}**: "
            digest += f"Appears in {node_info['path_count']} paths, "
            digest += f"transition success ranges {node_info['min_prob']:.0%}-{node_info['max_prob']:.0%}\n"

            # Provide actionable interpretation
            if node_info['edge_variance'] > 0.5:
                digest += f"  → High variance indicates this is a key decision point\n"
            else:
                digest += f"  → Moderate variance suggests some alternative paths exist\n"
        digest += "\n"

    # Section 3: High-risk transitions (defense priorities)
    if edges_prob:
        high_risk = sorted(edges_prob.items(), key=lambda x: x[1], reverse=True)[:3]
        high_risk_filtered = [(edge, prob) for edge, prob in high_risk if prob > 0.9]

        if high_risk_filtered:
            digest += "**High-Risk Transitions** (Defend These):\n"
            for edge_desc, prob in high_risk_filtered:
                digest += f"- `{edge_desc}`: {prob:.1%} exploitation rate\n"
            digest += "\n"

    # Section 4: Enhanced Nash Equilibrium with Strategic Framing
    attacker_success = nash_data.get('attacker_success', 0)
    defender_success = nash_data.get('defender_success', 0)

    # Get strategic interpretation
    strategic_assessment = interpret_nash_equilibrium(nash_data)

    digest += "**Game-Theoretic Analysis:**\n"
    digest += f"- **Strategic Position:** {strategic_assessment['position']}\n"
    digest += f"- **Attacker Success Probability:** {attacker_success:.6f} ({attacker_success:.1%})\n"
    digest += f"- **Defender Success Ceiling:** {defender_success:.6f}\n"
    digest += f"- **Confidence Level:** {strategic_assessment['confidence']}\n\n"

    digest += f"**Strategic Assessment:** {strategic_assessment['tactical_stance']}\n\n"

    # Section 5: Enhanced Defense Allocation with Exploitation Opportunities
    optimal_defense = nash_data.get('optimal_defense', {})

    if optimal_defense:
        # Show top defended nodes (where defender focuses resources)
        top_defenses = sorted(optimal_defense.items(), key=lambda x: float(x[1]), reverse=True)[:3]
        significant_defenses = [(node_id, alloc) for node_id, alloc in top_defenses if float(alloc) > 0.05]

        if significant_defenses:
            digest += "**Defender Resource Allocation** (Optimal Mixed Strategy):\n"
            for node_id, allocation in significant_defenses:
                node = nodes.get(str(node_id), {})
                node_name = node.get('name', f'Node {node_id}')
                digest += f"- **{node_name}**: {float(allocation):.1%} resources\n"
            digest += "\n"

        # Identify exploitation opportunities (under-defended nodes)
        opportunities = identify_exploitation_opportunities(nash_data, nodes)

        if opportunities:
            digest += "**Exploitation Opportunities** (Under-Defended Nodes):\n"
            for opp in opportunities[:3]:
                digest += f"- **{opp['name']}**: Only {opp['defense_allocation']:.1%} defender attention\n"
                digest += f"  → Opportunity score: {opp['opportunity_score']:.2f} (higher = better target)\n"
            digest += "\n"

    # Section 6: Tactical recommendation
    digest += "**Tactical Guidance:**\n"
    if bottlenecks:
        weakest_edge, weakest_prob = bottlenecks[0]
        digest += f"- Primary constraint: `{weakest_edge}` ({weakest_prob:.1%})\n"
        digest += f"- Consider alternative attack vectors or capability enhancement at this transition\n"
    else:
        digest += "- No significant bottlenecks detected in attack path\n"

    return digest


async def generate_llm_digest(ctr_dir: str) -> str:
    """Generate CTR digest using LLM-based interpretation.

    This function sends CTR analysis results to an LLM for flexible, nuanced
    interpretation that can identify non-obvious patterns and provide contextual insights.

    Args:
        ctr_dir: Path to CTR results directory

    Returns:
        Markdown-formatted digest string from LLM

    Raises:
        FileNotFoundError: If required CTR data files are missing
        Exception: If LLM API call fails
    """
    ctr_path = Path(ctr_dir)

    # Load data
    try:
        with open(ctr_path / 'nash_equilibrium.json') as f:
            nash_data = json.load(f)
        with open(ctr_path / 'attack_paths.json') as f:
            paths_data = json.load(f)
        with open(ctr_path / 'graph_information.txt') as f:
            graph_text = f.read()
    except FileNotFoundError as e:
        error_msg = f"CTR data incomplete: {e}"
        console.print(f"[red]{error_msg}[/red]")
        raise

    # Truncate graph text for token limits (keep first 4000 chars)
    graph_text_truncated = graph_text[:4000] if len(graph_text) > 4000 else graph_text

    # Calculate strategic assessment for game-theoretic framing
    strategic_assessment = interpret_nash_equilibrium(nash_data)

    prompt = f"""You are a cybersecurity analyst interpreting game-theoretic CTF security analysis results.

**Attack Graph Information:**
{graph_text_truncated}

**Nash Equilibrium (Game-Theoretic Assessment):**
- Strategic Position: {strategic_assessment['position']}
- Game Value: {strategic_assessment['game_value']:.6f} ({strategic_assessment['game_value']:.1%} attacker success probability)
- Confidence Level: {strategic_assessment['confidence']}
- Tactical Assessment: {strategic_assessment['tactical_stance']}

Full Nash Data:
{json.dumps(nash_data, indent=2)}

**Attack Paths:**
{json.dumps(paths_data, indent=2)}

**Instructions:**
Provide a strategic digest (max 350 words) with these sections:

1. **Attack Path Summary**: Describe the primary attack path with specific node names and transition probabilities
2. **Critical Bottlenecks**: Identify 2-3 weakest transitions (<90% success) - these are where the attacker struggles
3. **High-Risk Transitions**: Identify 2-3 strongest transitions (>90% success) - defender should focus here
4. **Strategic Position**: Interpret the game-theoretic position based on the assessment above. Explain:
   - What the strategic position (ATTACKER-FAVORED/CONTESTED/DEFENDER-FAVORED) means for the attacker
   - Why the game value indicates this position
   - What the confidence level tells us about attack feasibility
   - How the optimal defense allocation reveals strategic priorities
5. **Tactical Recommendation**: One specific actionable step for improving attack success, informed by the strategic assessment

OUTPUT REQUIREMENTS:
- Format ONLY as markdown
- Output ONLY the final digest with the 5 sections above
- Do NOT include any reasoning, thinking process, or explanations about how you analyzed the data
- Be concise and specific with node names and probabilities
- Maximum 350 words"""

    # Use LiteLLM for model compatibility (handles alias1, OpenRouter, etc.)

    model = os.getenv("CAI_CTR_DIGEST_MODEL", "alias1")

    console.print(f"[cyan]CTR: Generating LLM digest using model '{model}'...[/cyan]")

    # Configure LiteLLM for custom models (e.g., alias1)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a cybersecurity analyst specialized in game-theoretic security analysis."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 5000  # Increased for reasoning models
    }

    # Apply custom configuration for alias models (same logic as OpenAIChatCompletionsModel)
    model_str = str(model).lower()
    # Configure for alias2-mini (compact Alias model; same API gateway as other alias models)
    if model_str == "alias2-mini":
        kwargs["api_base"] = "https://api.aliasrobotics.com:666/"
        kwargs["custom_llm_provider"] = "openai"
        kwargs["api_key"] = os.getenv("ALIAS_API_KEY", "sk-alias-1234567890")
    elif "alias" in model_str and "alias0.5" not in model_str:
        kwargs["api_base"] = "https://api.aliasrobotics.com:666/"
        kwargs["custom_llm_provider"] = "openai"
        kwargs["api_key"] = os.getenv("ALIAS_API_KEY", "sk-alias-1234567890")

    try:
        response = await acompletion_with_timeout(kwargs, stream=False, model_name=model)

        # Extract content (handle reasoning models like alias1/o1 that use reasoning_content)
        message = response.choices[0].message
        digest = message.content

        # For reasoning models, the actual content is in reasoning_content
        # We need to extract the final answer from the reasoning process
        if digest is None and hasattr(message, 'reasoning_content'):
            reasoning = message.reasoning_content
            console.print("[cyan]CTR: Using reasoning_content from reasoning model[/cyan]")

            # Try to extract markdown sections from reasoning content
            # Look for the final output after any "Draft" or similar markers
            import re

            # Try to find markdown sections (starting with ##)
            markdown_sections = re.findall(r'((?:^|\n)#{1,3}\s+\*?\*?[A-Z].*?)(?=\n#{1,3}\s+\*?\*?[A-Z]|\Z)', reasoning, re.MULTILINE | re.DOTALL)

            if markdown_sections and len(''.join(markdown_sections)) > 200:
                # Found structured markdown output
                digest = '\n'.join(markdown_sections).strip()
                console.print("[cyan]CTR: Extracted markdown sections from reasoning[/cyan]")
            else:
                # Fallback: use last 2000 chars which likely contain the final answer
                digest = reasoning[-2000:] if len(reasoning) > 2000 else reasoning
                console.print("[cyan]CTR: Using tail of reasoning content[/cyan]")

        if digest is None or len(str(digest).strip()) == 0:
            console.print("[yellow]CTR: LLM returned empty content[/yellow]")
            raise ValueError("LLM returned empty or None content")

        console.print("[green]CTR: LLM digest generated successfully[/green]")
        return digest

    except Exception as e:
        console.print(f"[yellow]CTR: LLM digest generation failed: {e}[/yellow]")
        raise


async def get_ctr_digest_async(ctr_dir: str, mode: Optional[str] = None) -> str:
    """Get CTR digest with specified interpretation mode (async version).

    Example of CTR digest with mode "algorithmic":
    ```
        ## CTR Security Analysis

        **Identified Attack Paths:**
        Path 1: CTF Challenge →[66%] Nmap Scan →[80%] Open Ports Discovery →[85%] FTP Service (Port 21) ··→[0%] Target (FTP Service (Port 21))
        Path 2: CTF Challenge ··→[30%] FTP Download Attempt 1 →[57%] FTP Service (Port 21) ··→[0%] Target (FTP Service (Port 21))
        Path 3: CTF Challenge ··→[17%] FTP Download Attempt 2 ··→[3%] FTP Service (Port 21) ··→[0%] Target (FTP Service (Port 21))

        **Critical Bottlenecks** (Attack Weaknesses):
        - `FTP Download Attempt 2 -> FTP Service (Port 21)`: 3.1% success rate
        - `CTF Challenge -> FTP Download Attempt 2`: 17.0% success rate
        - `CTF Challenge -> FTP Download Attempt 1`: 30.2% success rate

        **High-Risk Transitions** (Defend These):
        - `FTP Service (Port 21) -> leaf_5`: 100.0% exploitation rate

        **Game-Theoretic Equilibrium:**
        - Attacker can guarantee success probability of: 0.040008
        - Defender can keep attacker success below: 0.040008
        - **Assessment:** Attacker-favorable: Current defenses face significant challenges.

        **Optimal Defense Allocation:**
        - **Open Ports Discovery**: 52.0% resources
        - **FTP Download Attempt 2**: 24.0% resources
        - **FTP Download Attempt 1**: 24.0% resources

        **Tactical Guidance:**
        - Primary constraint: `FTP Download Attempt 2 -> FTP Service (Port 21)` (3.1%)
        - Consider alternative attack vectors or capability enhancement at this transition    
    ```

    Example of CTR digest with mode "llm":
    ```
        ### Attack Path Summary
            The primary attack path proceeds from `CTF Challenge: Gain Access` to `Target IP 192.168.3.100` (39.05%), 
            then to `Nmap Reconnaissance` (39.05%), followed by `Open Ports Discovery` (59.37%), 
            then to `FTP Anonymous Access` (68.01%), and finally to successful exploitation (100.00%).

        ### Critical Bottlenecks
            The weakest transitions are the initial steps: `CTF Challenge: Gain Access -> Target IP 192.168.3.100` (39.05%) 
            and `Target IP 192.168.3.100 -> Nmap Reconnaissance` (39.05%). 
            These represent points where the attacker's initial reconnaissance is most likely to fail.

        ### High-Risk Transitions
            The strongest transition is `FTP Anonymous Access -> leaf_5` (100.00%). 
            Once the attacker identifies the anonymous FTP vulnerability, successful exploitation is guaranteed. 
            This is the most critical point for the defender to address.

        ### Equilibrium Interpretation
            The defender has a decisive advantage. The optimal defense strategy focuses all resources on node `4` (`Open Ports Discovery`), 
            which reduces the attacker's probability of success to near zero (`1e-07`). 
            This effectively neutralizes the attack path.

        ### Tactical Recommendation
            To improve attack success, the attacker should manually enumerate the FTP service after `Open Ports Discovery` 
            to confirm anonymous access, rather than relying solely on `nmap`'s script output. 
            This directly addresses the 68.01% bottleneck.
    ```

    Args:
        ctr_dir: Path to CTR results directory
        mode: Interpretation mode - "llm" or "algorithmic". If None, uses CAI_CTR_DIGEST_MODE env var

    Returns:
        Markdown-formatted digest string

    Raises:
        FileNotFoundError: If required CTR data files are missing
    """
    # Determine mode
    if mode is None:
        mode = os.getenv("CAI_CTR_DIGEST_MODE", "llm").lower()

    # Generate digest with fallback
    if mode == "llm":
        try:
            return await generate_llm_digest(ctr_dir)
        except Exception as e:
            console.print(f"[yellow]CTR: LLM digest failed, falling back to algorithmic: {e}[/yellow]")
            return generate_algorithmic_digest(ctr_dir)
    else:
        return generate_algorithmic_digest(ctr_dir)


def get_ctr_digest(ctr_dir: str, mode: Optional[str] = None, use_cache: bool = True) -> Optional[str]:
    """Get CTR digest with specified interpretation mode (sync wrapper with caching).

    This function implements intelligent caching to avoid regenerating digests
    for the same CTR data. The cache key is based on the resolved real path
    of the CTR directory, so symlink changes are automatically detected.

    Args:
        ctr_dir: Path to CTR results directory (can be a symlink)
        mode: Interpretation mode - "llm" or "algorithmic". If None, uses CAI_CTR_DIGEST_MODE env var
        use_cache: If True, use cached digest if available (default: True)

    Returns:
        Markdown-formatted digest string, or None if CTR data is incomplete/missing

    Raises:
        None - All errors are caught and None is returned
    """
    import asyncio
    import time

    # Determine mode
    if mode is None:
        mode = os.getenv("CAI_CTR_DIGEST_MODE", "llm").lower()

    # Resolve symlinks to get the real directory path
    # This ensures that when /tmp/cai/ctr/latest points to a new run directory,
    # we'll detect it and regenerate the digest
    try:
        ctr_dir_real = str(Path(ctr_dir).resolve())
    except Exception:
        ctr_dir_real = str(ctr_dir)

    # Check cache first
    cache_key = (ctr_dir_real, mode)
    if use_cache and cache_key in _DIGEST_CACHE:
        console.print(f"[dim]CTR: Using cached {mode} digest for {Path(ctr_dir_real).name}[/dim]")
        return _DIGEST_CACHE[cache_key]

    # Check if this run was recently found incomplete (avoid spamming errors)
    if ctr_dir_real in _INCOMPLETE_RUNS:
        time_since_last_check = time.time() - _INCOMPLETE_RUNS[ctr_dir_real]
        if time_since_last_check < _INCOMPLETE_RETRY_DELAY:
            # Still within retry delay, silently return None
            return None

    # Cache miss - try to generate digest
    try:
        # Try to get existing event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, need to use nested loop
                import nest_asyncio
                nest_asyncio.apply()
                digest = loop.run_until_complete(get_ctr_digest_async(ctr_dir, mode))
            else:
                digest = loop.run_until_complete(get_ctr_digest_async(ctr_dir, mode))
        except RuntimeError:
            # No event loop, create one
            digest = asyncio.run(get_ctr_digest_async(ctr_dir, mode))

        # Store in cache and clear from incomplete list
        _DIGEST_CACHE[cache_key] = digest
        if ctr_dir_real in _INCOMPLETE_RUNS:
            del _INCOMPLETE_RUNS[ctr_dir_real]
        return digest

    except FileNotFoundError as e:
        # CTR data files missing - this is expected when CTR is still running in background
        # Mark as incomplete and only log the first time
        import time
        is_first_attempt = ctr_dir_real not in _INCOMPLETE_RUNS
        _INCOMPLETE_RUNS[ctr_dir_real] = time.time()

        if is_first_attempt:
            console.print(f"[dim]CTR: Digest not yet available, CTR analysis may still be running ({Path(ctr_dir).name})[/dim]")
        return None
    except Exception as e:
        # Other errors - log and return None
        console.print(f"[yellow]CTR: Digest generation failed: {e}[/yellow]")
        return None


def get_digest_cache_stats() -> Dict[str, any]:
    """Get statistics about the digest cache.

    Returns:
        Dictionary containing:
        - size: Number of cached digests
        - entries: List of (ctr_dir, mode) tuples for cached entries
    """
    return {
        'size': len(_DIGEST_CACHE),
        'entries': [(Path(ctr_dir).name, mode) for (ctr_dir, mode) in _DIGEST_CACHE.keys()]
    }


def clear_digest_cache() -> None:
    """Clear all digest caches (per-run, session-level, and incomplete tracking).

    This is useful when you want to force regeneration of digests,
    for example during testing or development.
    """
    global _DIGEST_CACHE, _INCOMPLETE_RUNS, _SESSION_DIGEST_CACHE
    cached_count = len(_DIGEST_CACHE)
    incomplete_count = len(_INCOMPLETE_RUNS)
    session_count = len(_SESSION_DIGEST_CACHE)
    _DIGEST_CACHE.clear()
    _INCOMPLETE_RUNS.clear()
    _SESSION_DIGEST_CACHE.clear()
    console.print(f"[dim]CTR: All caches cleared ({cached_count} per-run, {session_count} session, {incomplete_count} incomplete)[/dim]")


def mark_ctr_run_complete(ctr_dir: str) -> None:
    """Mark a CTR run as complete and clear it from incomplete tracking.

    This should be called by agents when CTR background task completes successfully.
    It ensures the next system prompt generation will attempt to load the digest.

    Args:
        ctr_dir: Path to CTR results directory
    """
    try:
        ctr_dir_real = str(Path(ctr_dir).resolve())
        if ctr_dir_real in _INCOMPLETE_RUNS:
            del _INCOMPLETE_RUNS[ctr_dir_real]
            console.print(f"[dim]CTR: Marked {Path(ctr_dir_real).name} as complete, digest will be generated on next turn[/dim]")
    except Exception:
        pass  # Silently ignore errors


def update_session_digest(session_id: str, digest: str, mode: Optional[str] = None) -> None:
    """Update the session-level digest cache with a newly generated digest.

    This function should be called by agents immediately after CTR completes and
    the digest is generated. This ensures digest continuity: the new digest becomes
    the "current" digest for this session and will be used on all subsequent turns
    until the next CTR completes.

    Args:
        session_id: Current session ID
        digest: The newly generated digest text (System Prompt Injection Preview content)
        mode: Interpretation mode used ("llm" or "algorithmic")
    """
    if mode is None:
        mode = os.getenv("CAI_CTR_DIGEST_MODE", "llm").lower()

    session_key = (session_id, mode)
    _SESSION_DIGEST_CACHE[session_key] = digest
    console.print(f"[dim]CTR: Updated session digest cache for {session_id} (mode: {mode})[/dim]")


def get_latest_ctr_digest(mode: Optional[str] = None) -> Optional[str]:
    """Get digest of latest CTR results from current session with perfect continuity.

    This function implements a session-level cache to ensure digest continuity:
    - Once a digest is generated, it's cached at the session level
    - All subsequent calls return the cached digest (no file checks, no regeneration)
    - Cache is updated ONLY when a new CTR completes and generates a new digest
    - Old digest continues to be used while new CTR runs in background

    This ensures zero interruption and no repeated processing during CTR execution.

    Args:
        mode: Interpretation mode - "llm" or "algorithmic". If None, uses CAI_CTR_DIGEST_MODE env var

    Returns:
        Digest string or None if no CTR data available for current session
    """
    from cai.ctr.paths import get_ctr_output_base_dir
    from cai.sdk.agents.run_to_jsonl import get_session_recorder

    # Determine mode
    if mode is None:
        mode = os.getenv("CAI_CTR_DIGEST_MODE", "llm").lower()

    # Get current session ID
    session_id = None
    recorder = get_session_recorder()
    if recorder is not None:
        session_id = getattr(recorder, "session_id", None)

    # If no session ID, we can't determine current session - return None
    if not session_id:
        return None

    # Check session-level cache FIRST - this provides instant continuity
    session_key = (session_id, mode)
    if session_key in _SESSION_DIGEST_CACHE:
        # Return cached digest immediately - no file checks, no regeneration needed
        return _SESSION_DIGEST_CACHE[session_key]

    # Session cache miss - need to find and generate initial digest
    # This only happens once per session (or after new CTR completes)
    base_dir = get_ctr_output_base_dir()
    session_dir = Path(base_dir) / session_id

    # Check if session directory exists
    if not session_dir.exists():
        return None

    # Find all run directories in current session, sorted by timestamp
    run_dirs = sorted([d for d in session_dir.iterdir() if d.is_dir() and d.name.startswith('run_')])

    if not run_dirs:
        return None

    # Search backwards through run directories to find the most recent COMPLETE run
    # A complete run has nash_equilibrium.json file
    latest_complete_run = None
    for run_dir in reversed(run_dirs):
        nash_file = run_dir / 'nash_equilibrium.json'
        if nash_file.exists():
            latest_complete_run = str(run_dir)
            break

    if not latest_complete_run:
        # No complete runs found yet
        return None

    try:
        # Generate digest (uses per-run cache internally)
        digest = get_ctr_digest(latest_complete_run, mode)

        if digest:
            # Store in session cache for instant future access
            _SESSION_DIGEST_CACHE[session_key] = digest
            console.print(f"[dim]CTR: Initialized session digest cache from {Path(latest_complete_run).name}[/dim]")

        return digest
    except Exception as e:
        console.print(f"[red]CTR: Failed to generate digest: {e}[/red]")
        return None
