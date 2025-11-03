# Teams and Parallel Execution

> **⚡ CAI-Pro Exclusive Feature**  
> The Terminal User Interface (TUI) is available exclusively in **CAI-Pro**. To access this feature and unlock advanced multi-agent workflows, visit [Alias Robotics](https://aliasrobotics.com/cybersecurityai.php) for more information.

---

Teams in CAI enable efficient parallel execution across multiple terminals, allowing you to coordinate specialized agents for complex security workflows.

---

## Quick Start with Teams

1. **Navigate to Teams tab** in the sidebar
2. **Click any team button** to configure all four terminals instantly
3. **Send prompts** to individual terminals or broadcast to all
4. **Switch teams** anytime to change your workflow strategy

---

## Parallel Execution Patterns

### Pattern 1: Divide and Conquer

Distribute different aspects of a target across terminals:

```
Terminal 1 (redteam): Web application testing
Terminal 2 (redteam): API endpoint enumeration
Terminal 3 (bug_bounter): Authentication bypass attempts
Terminal 4 (bug_bounter): Input validation testing
```

**Example with Team 1** (2 Red + 2 Bug):

```
T1: Scan example.com for OWASP Top 10 vulnerabilities
T2: Enumerate subdomains and check for takeover
T3: Test for SQL injection in login forms
T4: Analyze JWT token security
```

### Pattern 2: Phased Workflow

Execute sequential phases across terminals:

```
Phase 1: Reconnaissance (all terminals)
Phase 2: Vulnerability discovery (terminals 1-2)
Phase 3: Exploitation (terminals 3-4)
Phase 4: Validation (switch to retester agents)
```

**Example with Team 5** (Red + Blue + Retester + Bug):

```
T1: Initial reconnaissance and enumeration
T2: Defensive posture analysis
T3: Retest previously found vulnerabilities
T4: Hunt for new bug bounty targets
```

### Pattern 3: Simultaneous Validation

Test and validate in parallel:

```
Terminal 1-2: Discover vulnerabilities
Terminal 3-4: Immediately validate findings
```

**Example with Team 6** (2 Red + 2 Retester):

```
T1: Find SQL injection points
T2: Identify XSS vectors
T3: Validate SQLi exploitability
T4: Confirm XSS impact
```

---

## Broadcasting Commands

Send the same command to all terminals simultaneously:

**Method 1: Add "all" flag**
1. Type your command in the input area
2. Add `all` at the end of your prompt
3. Command executes on all four terminals in parallel

**Example use cases**:
- Broadcast reconnaissance: `Enumerate subdomains of example.com all`
- Parallel vulnerability scan: `Scan target.com for SQL injection all`
- Coordinated testing: `Test authentication mechanisms all`

---

## Team Selection Strategies

### For Penetration Testing
- **Team 1** (2 Red + 2 Bug): Comprehensive offensive testing
- **Team 8** (4 Red): Maximum offensive coverage

### For Bug Bounty Hunting
- **Team 10** (4 Bug): Intensive vulnerability research
- **Team 1** (2 Red + 2 Bug): Red team + bug bounty combination

### For Defense Analysis
- **Team 9** (4 Blue): Complete defensive posture review
- **Team 3** (2 Red + 2 Blue): Offense/defense balance

### For Validation Workflows
- **Team 6** (2 Red + 2 Retester): Offensive + validation
- **Team 11** (4 Retester): Comprehensive retest coverage

### For Comprehensive Assessments
- **Team 5** (Red + Blue + Retester + Bug): All-in-one workflow

---

## Coordination Tips

### Context Sharing

Share findings between terminals:

```
T1: discovered SQL injection in /api/users
T2: /load T1 context and exploit the SQL injection
```

### Progressive Refinement

Build on previous results:

```
T1: enumerate subdomains
T2: scan the subdomains found by T1
T3: test authentication on discovered services
T4: validate exploitability of findings
```

### Role Specialization

Assign specific roles to terminals:
- **Scout**: Terminal 1 does reconnaissance
- **Attacker**: Terminals 2-3 exploit findings
- **Validator**: Terminal 4 confirms results

---

## Performance Optimization

### Terminal Distribution
- **Don't overload one terminal**: Distribute prompts evenly
- **Monitor the queue**: Check Queue tab for bottlenecks
- **Use available terminals**: Switch to idle terminals instead of queuing

### Model Selection
- **Fast models for reconnaissance**: Use `alias0-fast` or `alias1` for enumeration
- **Powerful models for exploitation**: Use `alias1` for complex tasks
- **Mix models strategically**: Different models for different terminal roles

### Cost Management
- **Track stats**: Monitor usage in Stats tab
- **Optimize prompts**: Be concise to reduce token consumption
- **Use efficient teams**: Don't use 4 terminals if 2 suffice

---

## Advanced Patterns

### Split Context Analysis

Analyze scenarios from independent perspectives:
- Each terminal maintains isolated context
- Compare different approaches to the same problem
- Identify blind spots through diverse analysis

### Progressive Refinement

Build comprehensive understanding through iterative analysis:
- Terminal 1 identifies initial findings
- Terminal 2 validates and expands on findings
- Terminal 3 explores alternative approaches
- Terminal 4 consolidates and refines results

### Parallel Hypothesis Testing

Test multiple theories simultaneously:
- Each terminal investigates a different hypothesis
- Compare results to identify the most viable approach
- Accelerate discovery through parallel exploration

---

## Related Documentation

- [Sidebar Features](sidebar_features.md) - Team configuration and management
- [Terminals Management](terminals_management.md) - Multi-terminal control
- [Commands Reference](commands_reference.md) - Terminal-specific commands
- [User Interface](user_interface.md) - TUI layout and components

---

*Last updated: October 2025 | CAI TUI v0.6+*

**Quick Reference**: Press `F1` or type `/help teams` for team-specific help.


