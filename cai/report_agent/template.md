% if confidential:
# :lock: Confidential Penetration Testing Report
% else:
# :shield: Penetration Testing Report
% endif

| **Date**    | **Client**   | **Assessor** | **Version** |
|-------------|--------------|--------------|-------------|
| ${date or ""}     | placeholder  | CAI          | 2.1         |

---

<details>
  <summary><strong>Table of Contents</strong> (Click to Expand)</summary>

1. [Executive Summary](#1-executive-summary)
2. [Scope & Objectives](#2-scope--objectives)
3. [Methodology](#3-methodology)
4. [Tools and Techniques](#tools-and-techniques)
5. [Detailed Findings](#4-detailed-findings)
  - [Vulnerability Assessment Metrics](#41-vulnerability-assessment-metrics)
  - [Network State Analysis](#42-network-state-analysis)
6. [Risk Assessment](#5-risk-assessment)
7. [Remediation Recommendations](#6-remediation-recommendations)
8. [Conclusion](#7-conclusion)
9. [Appendix](#8-appendix)
</details>

---

## 1. Executive Summary

> ${executive_summary or "No executive summary provided."}

---

## 2. Scope & Objectives

The following section delineates the scope and objectives of this penetration testing engagement:

${scope or "No scope defined."}

---

## 3. Methodology

The assessment was conducted using a systematic and comprehensive approach that encompasses reconnaissance, vulnerability analysis, exploitation, and validation:

${methodology or "No methodology provided."}


% if tools:

<strong>Detailed Tools and Techniques</strong>

% for tool in (tools or []):
- 🛠 ${tool or ""}
% endfor


% endif

---

## 4. Detailed Findings

% for finding in (findings or []):
<details>
  <summary>
    <strong>🚨 Finding ID: ${finding.finding_id or "N/A"}</strong> | <em>Type:</em> ${finding.finding_type or "N/A"} | <em>Severity:</em> ${finding.severity or "N/A"}
  </summary>

**Description:**
${finding.description or "No description provided."}

% if finding.cve_cwe:
**References:** ${finding.cve_cwe}
% endif

**Exploitation Details:**
${finding.exploitation_details or "No exploitation details provided."}

**Remediation Recommendation:**
${finding.remediation or "No remediation recommendation provided."}

**Remediation Actions:**
${finding.remediation_command or "No remediation command provided."}

% if finding.evidence:
**Evidence:**
- Empirical Evidence: ${finding.evidence.empirical_evidence or "N/A"}
- Tool Log: ${finding.evidence.tool_output_evidence or "N/A"}
- Command: ${finding.evidence.command or "N/A"}
% endif

</details>

<br>
% endfor

---

## 4.1 Vulnerability Assessment Metrics

<strong> Vulnerability Severity Distribution Chart</strong>

```mermaid
pie
    title ${chart_title or "Vulnerability Severity Distribution"}
    "Critical" : ${vuln_critical or 0}
    "High"     : ${vuln_high or 0}
    "Medium"   : ${vuln_medium or 0}
    "Low"      : ${vuln_low or 0}
```

*Note: The displayed values are placeholders and may vary based on actual assessment data.*

---

## 4.2 Network State Analysis

% if network_state and network_state.network:
% for endpoint in (network_state.network or []):
<strong>Host: ${endpoint.ip or "N/A"}</strong>

### Open Ports

% if endpoint.ports:
| Port Number | Service Name | Version | Vulnerabilities |
|-------------|--------------|---------|-----------------|
% for port in (endpoint.ports or []):
| ${port.port or "N/A"} | ${port.service or "N/A"} | ${port.version or "N/A"} | ${", ".join(port.vulns or []) if (port.vulns or []) else "None"} |
% endfor
% else:
_No open ports detected._
% endif

### Executed Exploits

% if endpoint.exploits:
| Exploit Name | Exploit Type | Status |
|--------------|--------------|--------|
% for exploit in (endpoint.exploits or []):
| ${exploit.name or "N/A"} | ${exploit.exploit_type or "N/A"} | ${exploit.status or "N/A"} |
% endfor
% else:
_No exploit attempts recorded._
% endif

### Discovered Files

% if endpoint.files:
| File Name |
|-----------|
% for file in (endpoint.files or []):
| ${file or "N/A"} |
% endfor
% else:
_No files discovered._
% endif

### Identified Users

% if endpoint.users:
| User Identifier |
|-----------------|
% for user in (endpoint.users or []):
| ${user or "N/A"} |
% endfor
% else:
_No users identified._
% endif


% endfor
% else:
_No network state data available._
% endif

---

## 5. Risk Assessment

> ${risk_assessment or "Risk assessment details are not provided."}

---

## 6. Remediation Recommendations

> ${remediation_recommendations or "No remediation recommendations available."}

---

## 7. Conclusion

> ${conclusion or "Conclusion pending further evaluation."}

---

## 8. Appendix: Penetration testing exercise in JSON format
${history or "No additional history provided."}
