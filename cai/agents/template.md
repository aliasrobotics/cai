% if confidential:
# :lock: Confidential Penetration Testing Report
% else:
# :shield: Penetration Testing Report
% endif

| **Date**    | **Client**   | **Assessor**   | **Version**  |
|-------------|--------------|----------------|--------------|
| ${date}     | placeholder  | CAI     | 2.1   |

---

<details>
  <summary><strong>Table of Contents</strong> (Click to Expand)</summary>

  1. [Executive Summary](#1-executive-summary)
  2. [Scope & Objectives](#2-scope--objectives)
  3. [Methodology](#3-methodology)
  4. Findings
      - [Vulnerability Assessment Metrics](#41-vulnerability-assessment-metrics)
      - [Network State Analysis](#42-network-state-analysis)
  5. [Risk Assessment](#5-risk-assessment)
  6. [Remediation Recommendations](#6-remediation-recommendations)
  7. [Conclusion](#7-conclusion)
  8. [Appendix](#8-appendix)
</details>

---

## 1. Executive Summary

> ${executive_summary}

---

## 2. Scope & Objectives

${scope}

---

## 3. Methodology

${methodology}

% if tools:
<details>
  <summary><strong>Tools and Techniques</strong> (Click to Expand)</summary>

% for tool in tools:
- 🛠 ${tool}
% endfor

</details>
% endif

## 4. Findings

% for finding in findings:
<details>
  <summary>
    <strong>🚨 Finding ID: ${finding.finding_id}</strong> | **Type:** ${finding.finding_type} | **Severity:** ${finding.severity}
  </summary>

- **Description:** ${finding.description}
% if finding.cve_cwe:
- **References:** ${finding.cve_cwe}
% endif
- **Exploitation Details:** ${finding.exploitation_details}
- **Remediation Recommendation:** ${finding.remediation}
% if finding.evidence:
- **Evidence:** ${finding.evidence}
% endif

</details>
<br>
% endfor

## 4.1 Vulnerability Assessment Metrics

<details>
  <summary><strong>View Vulnerability Severity Distribution Chart</strong></summary>

~~~mermaid
pie
    title Vulnerability Severity Distribution
    "Critical" : 25
    "High"     : 35
    "Medium"   : 25
    "Low"      : 15
~~~

*Note: Values are placeholders and may vary based on the actual assessment.*
</details>

## 4.2 Network State Analysis

% if network_state and network_state.network:
% for endpoint in network_state.network:
<details>
  <summary><strong>🖥 Endpoint: ${endpoint.ip_address}</strong></summary>

**Open Ports:**
% if endpoint.open_ports:
% for port in endpoint.open_ports:
- **Port:** ${port.port_number} | **Service:** ${port.service_name} | **Version:** ${port.version} | **Vulnerabilities:** ${", ".join(port.vulnerabilities) if port.vulnerabilities else "None"}
% endfor
% else:
- _No open ports detected._
% endif

**Executed Exploits:**
% if endpoint.executed_exploits:
% for exploit in endpoint.executed_exploits:
- **Exploit:** ${exploit.exploit_name} | **Type:** ${exploit.exploit_type} | **Status:** ${exploit.status} | **Details:** ${exploit.details}
% endfor
% else:
- _No exploit attempts recorded._
% endif

**Discovered Files:**
% if endpoint.discovered_files:
% for file in endpoint.discovered_files:
- ${file}
% endfor
% else:
- _No files discovered._
% endif

**Identified Users:**
% if endpoint.identified_users:
% for user in endpoint.identified_users:
- ${user}
% endfor
% else:
- _No users identified._
% endif

</details>
% endfor
% else:
_No network state data available._
% endif

## 5. Risk Assessment

> ${risk_assessment if risk_assessment else "Risk assessment details are not provided."}

---

## 6. Remediation Recommendations

> ${remediation_recommendations if remediation_recommendations else "No remediation recommendations available."}

---

## 7. Conclusion

> ${conclusion if conclusion else "Conclusion pending further evaluation."}

---

## 8. Appendix

${appendix if appendix else "No additional documentation provided."}
