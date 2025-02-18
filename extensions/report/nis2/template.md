# 📌 NIS2 Compliance Report

| **Date**    | **Client**   | **Assessor** | **Version** | **Targets** |
|-------------|--------------|--------------|-------------|------------|
| ${date or ""}     | ${client}  | CAI          | 2.1         | ${targets or ""} |

The NIS2 Directive (Directive (EU) 2022/2555) is an EU-wide cybersecurity framework designed to enhance the cyber resilience of critical sectors and ensure a high common level of cybersecurity across the European Union. This report evaluates compliance with NIS2 requirements.

---

<strong>Table of Contents</strong>

1. [Executive Summary](#1-executive-summary)
2. [Assessment Overview](#2-assessment-overview)
3. [Compliance Status](#3-compliance-status)
4. [Recommendations](#4-recommendations)
5. [Appendix](#5-appendix)

---

# 1. Executive Summary
${executive_summary or "No executive summary provided."}

---

# 2. Assessment Overview

🔹 A. Security Policies and Risk Analysis
- ${compliance_assessment.get("A1_security_policy", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 A1. The organization has a formal information security policy (cybersecurity governance framework + roles and responsibilities defined)
- ${compliance_assessment.get("A2_risk_assessments", "[ ]") if compliance_assessment else "[ ]"} A2. Risk assessments are performed periodically
- ${compliance_assessment.get("A3_critical_assess", "[ ]") if compliance_assessment else "[ ]"} A3. Critical assets of the company are identified and documented
- ${compliance_assessment.get("A4_security_controls", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 A4. Security controls have been implemented based on risk analysis

🔹 B. Incident Management
- ${compliance_assessment.get("B1_incident_response", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 B1. An incident response protocol for cybersecurity exists (Plans and procedures)
- ${compliance_assessment.get("B2_responsible_teams", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 B2. Responsible teams have been defined for incident
- ${compliance_assessment.get("B3_simulations", "[ ]") if compliance_assessment else "[ ]"} B3. CAI conducts cyberattack simulations and detection, notification, and response (solve by CAI)
- ${compliance_assessment.get("B4_incident_documentation", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 B4. Incidents are documented and analyzed to prevent recurrence

🔹 C. Business Continuity and Disaster Recovery
- ${compliance_assessment.get("C1_business_continuity_plan", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 C1. Development of plans (crisis, continuity, contingencies) to ensure business continuity in case of an incident (A business continuity plan (BCP))
- ${compliance_assessment.get("C2_backups_encrypted", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 C2. Backups are performed regularly and encrypted
- ${compliance_assessment.get("C3_recovery_times_defined", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 C3. Recovery times (RTO/RPO) have been defined in case of failure

🔹 D. Supply Chain Security
- ${compliance_assessment.get("D1_supply_chain_security", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 D1. The security of suppliers and service providers is assessed
- ${compliance_assessment.get("D2_contracts_cybersecurity", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 D2. Contracts include cybersecurity requirements for third parties
- ${compliance_assessment.get("D3_supplier_risk_management", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 D3. Security controls have been implemented for managing supplier risk

🔹E. Security in System Development and Maintenance
- ${compliance_assessment.get("E1_vulnerability_testing", "[ ]") if compliance_assessment else "[ ]"} E1. Regular vulnerability scanning and penetration testing on software and networks
- ${compliance_assessment.get("E2_vulnerability_management", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 E2. The disclosure and correction of vulnerabilities is managed
- ${compliance_assessment.get("E3_secure_sdlc", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 E3. A secure software development cycle (secure SDLC) is followed

🔹 F. Risk Management Measures Assessment
- ${compliance_assessment.get("F1_regular_audits", "[ ]") if compliance_assessment else "[ ]"} F1. Regular audits are conducted to assess security
- ${compliance_assessment.get("F2_kpis_effectiveness", "[ ]") if compliance_assessment else "[ ]"} F2. Performance indicators (KPIs) exist to measure the effectiveness of cybersecurity
- ${compliance_assessment.get("F3_risk_reports", "[ ]") if compliance_assessment else "[ ]"} F3. Risk reports are prepared for senior management

🔹 G. Cyber Hygiene and Cybersecurity Training
- ${compliance_assessment.get("G1_cybersecurity_training", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 G1. Employees receive cybersecurity training and awareness program.
- ${compliance_assessment.get("G2_cyber_hygiene_practices", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 G2. Cyber hygiene practices (secure passwords, updates, etc.) are implemented
- ${compliance_assessment.get("G3_phishing_simulations", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 G3. Phishing simulations for awareness are conducted

🔹 H. Cryptography and Encryption Policies
- ${compliance_assessment.get("H1_data_encryption", "[ ]") if compliance_assessment else "[ ]"} H1. Data encryption is used for sensitive information to preserve data integrity, confidentiality, and authenticity.
- ${compliance_assessment.get("H2_cryptographic_standards", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 H2. Appropriate cryptographic standards (AES, RSA, TLS) are applied
- ${compliance_assessment.get("H3_key_management", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 H3. Key management practices Encryption protocols comply with international regulations

🔹 I. Human Resources Security and Access Control
- ${compliance_assessment.get("I1_access_controls", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 I1. Access controls are implemented based on the principle of least privilege
- ${compliance_assessment.get("I2_employee_profiles", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 I2. Employees, who access to sensitive information, have well-defined profiles and permissions
- ${compliance_assessment.get("I3_asset_inventory", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 I3. Assess measures regarding asset corporate inventory.

🔹 J. Authentication and Secure Communications
- ${compliance_assessment.get("J1_mfa_usage", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 J1. Multi-factor authentication (MFA) is used for critical access
- ${compliance_assessment.get("J2_communications_protection", "[ ]") if compliance_assessment else "[ ]"} J2. Voice, video, and text communications are protected
- ${compliance_assessment.get("J3_emergency_communications", "[ ]") if compliance_assessment else "[ ]"} ✍🏼 J3. A secure emergency communications system is in place

---

# 3. Compliance Status
${"##"} 3.1 **Overall compliance:**
Compliance with CAI possibilities: ${"✅ (9/9)" if total_complian == 9 else "❌ (" + str(total_complian) + "/9)"}

${"##"} 3.2 **Compliance Evaluation from CAI:**

${"###"} **A. Risk Management**

**A1. The organization has a formal information security policy**: Needs manual check ✍🏼

**A2. Risk assessments are performed periodically:** ${"✅" if compliance_assessment.get("A2_risk_assessments") == "[x]" else "❌"}

${"Our organization conducts periodic risk assessments as part of our comprehensive cybersecurity strategy. This process is supported by regularly scheduled penetration testing, which helps identify vulnerabilities and assess potential threats. Each penetration test is documented in detailed reports, and findings are analyzed to evaluate risks and prioritize mitigation efforts (Refer to F3 for more details). Additionally, our risk assessment documentation tracks these vulnerabilities over time, ensuring continuous monitoring and improvement. By maintaining this structured approach, we demonstrate our commitment to proactively managing security risks and enhancing our overall cybersecurity posture." if compliance_assessment.get("A2_risk_assessments") == "[x]" else "No periodic penetration testing or risk assessments are conducted"}

**A3. Critical assets of the company are identified and documented:** ${"✅" if compliance_assessment.get("A2_risk_assessments") == "[x]" else "❌"}

% for asset in (evidence_A3 or []):
- ❗ ${asset or ""}
% endfor

**A4. Security controls have been implemented based on risk analysis:** Needs manual check ✍🏼

---

${"###"} **B. Incident Management**

**B1. An incident response protocol for cybersecurity exists:** Needs manual check ✍🏼

**B2. Responsible teams have been defined for incident management:** Needs manual check ✍🏼

**B3. Cyberattack simulations are conducted regularly:** ${"✅" if compliance_assessment.get("B3_simulations") == "[x]" else "❌"}

<details>
  <summary>
Example of a previus simulation:
  </summary>

```json
 ${history_pentesting or "No additional history provided."}

```
</details>


**B4. Incidents are documented and analyzed to prevent recurrence:** Needs manual check ✍🏼

---

${"###"} **C. Business Continuity and Disaster Recovery**

**C1. Development of plans (crisis, continuity, contingencies) to ensure business continuity in case of an incident (A business continuity plan (BCP)):** Needs manual check ✍🏼

**C2. Backups are performed regularly and encrypted:** Needs manual check ✍🏼

**C3. Recovery times (RTO/RPO) have been defined in case:** Needs manual check ✍🏼

---

${"###"} **D. Supply Chain Security**

**D1. The security of suppliers and service providers is assessed:** Needs manual check ✍🏼

**D2. Contracts include cybersecurity requirements for third parties:** Needs manual check ✍🏼

**D3. Security controls have been implemented for managing supplier risk:** Needs manual check ✍🏼

---

${"###"} **E. Security in System Development and Maintenance**

**E1. Regular vulnerability scanning and penetration testing on software and networks:** ${"✅" if compliance_assessment.get("E1_vulnerability_testing") == "[x]" else "❌"}


<details>
  <summary>
Example of a previus penetration testing:
  </summary>

```json
 ${history_pentesting or "No additional history provided."}

```
</details


**E2. The disclosure and correction of vulnerabilities is managed:** Needs manual check ✍🏼

**E3. A secure software development cycle (secure SDLC) is followed:** Needs manual check ✍🏼

---

${"###"} **F. Risk Management Measures Assessment**

**F1. Regular audits are conducted to assess security:** ${"✅" if compliance_assessment.get("F1_regular_audits") == "[x]" else "❌"}

${"Our organization regularly evaluates potential security risks to ensure a proactive approach to threat management. This ongoing process helps strengthen our defenses and maintain a secure environmen (Refer to F3 for more details)." if compliance_assessment.get("F1_regular_audits") == "[x]" else "No regular audits are conducted"}

**F2. Performance indicators (KPIs) exist to measure the effectiveness of cybersecurity:** ${"✅" if compliance_assessment.get("F2_kpis_effectiveness") == "[x]" else "❌"}

| **Name** | **Description** | **Value** |
|--------------------------|--------------------------------|--------------------------------------|
% for kpi in (kpis if kpis else []):
| ${kpi.get('name', ' ')} | ${kpi.get('description', ' ')} | ${kpi.get('value', ' ')} |
% endfor


**F3. Risk reports are prepared for senior management:** ${"✅" if compliance_assessment.get("F3_risk_reports") == "[x]" else "❌"}

Company name: ${risk.get('company_name', 'N/A') if risk else 'N/A'}
Assessment carried out by: CAI
Date assessment was carried out: ${risk.get('date_assessment', '') if risk else ''}

| **What are the hazards?** | **Who might be harmed and how?** | **What are you already doing to control the risks?** | **What further action do you need to take to control the risks?** | **Who needs to carry out the action?** | **When is the action needed by?** | **Done** |
|--------------------------|--------------------------------|--------------------------------------|--------------------------------------------------|-----------------------------|----------------------|------|
% for hazard in (risk.get('hazards', []) if risk else []):
| ${hazard.get('name', ' ')} | ${hazard.get('harmed', ' ')} | ${hazard.get('current_measures', ' ')} | ${hazard.get('actions', ' ')} | ${hazard.get('responsible', ' ')} | ${hazard.get('deadline', ' ')} | :x: |
% endfor

---

${"###"} **G. Cyber Hygiene and Cybersecurity Training**

**G1. Employees receive cybersecurity training and awareness program.:** Needs manual check ✍🏼

**G2. Cyber hygiene practices (secure passwords, updates, etc.) are implemented:** Needs manual check ✍🏼

**G3. Phishing simulations for awareness are conducted:** Needs manual check ✍🏼

---

${"###"} **H. Cryptography and Encryption Policies**
**H1. Data encryption is used for sensitive information to preserve data integrity, confidentiality, and authenticity:**  ${"✅" if compliance_assessment.get("H1_data_encryption") == "[x]" else "❌"}
% if evidence_H1:
Evidence:
- Empirical Evidence: ${evidence_H1.get("empirical_evidence") or "N/A"}
- Command: `${evidence_H1.get("command") or "N/A"}`
- Tool Log:

```
${evidence_H1.get("tool_output_evidence") or "N/A"}
```

% endif

**H2. Appropriate cryptographic standards (AES, RSA, TLS) are applied** Needs manual check ✍🏼

**H3. Key management practices Encryption protocols comply with international regulations** Needs manual check ✍🏼

---

${"###"} **I. Human Resources Security and Access Control**

**I1. Access controls are implemented based on the principle of least privilege:** Needs manual check ✍🏼

**I2. Employees, who access to sensitive information, have well-defined profiles and permissions:** Needs manual check ✍🏼

**I3. Assess measures regarding asset corporate inventory:** Needs manual check ✍🏼

---

${"###"} **J. Authentication and Secure Communications**

**J1. Multi-factor authentication (MFA) is used for critical access:** Needs manual check ✍🏼

**J2. Voice, video, and text communications are protected:** ${"✅" if compliance_assessment.get("J2_communications_protection") == "[x]" else "❌"}
% if evidence_J2:
Evidence:
- Empirical Evidence: ${evidence_J2.get("empirical_evidence") or "N/A"}
- Command: `${evidence_J2.get("empirical_evidence") or "N/A"}`
- Tool Log:

```
${evidence_J2.get("tool_output_evidence") or "N/A"}
```

% endif

**J3. A secure emergency communications system is in place:** Needs manual check ✍🏼

---

# 4. Recommendations

${recommendations or "No additional recommendations."}

---

# 5. Appendix
${"##"} 5.1  History of the nis2 agent

```json
 ${history or "No additional history provided."}

```

---

${"##"} 5.2  History of the previous pentesting

```json
 ${history_pentesting or "No additional history provided."}

```
