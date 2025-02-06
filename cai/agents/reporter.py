"""
This module provides a Pydantic model for
reporting in Cybersecurity contexts.
"""
import os
from pydantic import BaseModel  # pylint: disable=import-error
from cai.state.pydantic import NetworkState
from cai.types import Agent


class Evidence(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents evidence for a finding"""
    empirical_evidence: str  # Explaination of the evidence
    tool_output_evidence: str  # Optional tool log
    command: str  # Optional command


class Finding(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents a detailed security finding."""
    finding_id: str  # Unique identifier for the finding
    finding_type: str  # e.g., "Vulnerability", "Information Disclosure"
    description: str  # Detailed description of the issue
    cve_cwe: str  # Reference identifiers, such as CVE or CWE
    severity: str  # e.g., "Critical", "High", "Medium", "Low"
    # Detailed explanation of any exploitation steps, if applicable
    exploitation_details: str
    remediation: str  # Recommended mitigation or remediation actions
    remediation_command: str
    evidence: Evidence  # Optional evidence (logs, screenshots, etc.)


class PentestReport(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents a comprehensive, production-grade report."""
    confidential: bool  # True if the report is confidential.
    date: str  # Report date.
    client: str  # Client or project name.
    assessor: str  # Identifier of the penetration tester.
    version: str  # Report version (e.g., "2.1").

    executive_summary: str  # Comprehensive overview for stakeholders.
    scope: str  # Scope & Objectives of the assessment.
    methodology: str  # Detailed methodology applied during the assessment.
    # Tools and Techniques used (if any) with high technical detail.
    tools: list[str]
    findings: list[Finding]  # List of detailed security findings.

    chart_title: str  # Title for the Vulnerability Assessment Metrics chart.
    vuln_critical: int  # Count of Critical vulnerabilities.
    vuln_high: int  # Count of High vulnerabilities.
    vuln_medium: int  # Count of Medium vulnerabilities.
    vuln_low: int  # Count of Low vulnerabilities.

    network_state: NetworkState  # Detailed network state analysis.
    risk_assessment: str  # Risk assessment details.
    remediation_recommendations: str  # Recommended remediation actions.
    conclusion: str  # Final conclusion of the report.
    appendix: str  # Additional documentation or notes.


def instructions(context_variables):  # pylint: disable=unused-argument  # noqa: E501
    """
    Instructions for the pydantic state agent
    """
    return """
    You are a highly sophisticated and persuasive professional security report generator tasked with producing an exceptionally detailed, multi-page report that captures every
     nuance of a security assessment scenario with absolute precision. Your mission is to create a document of technical excellence, comparable to a comprehensive whitepaper, where every observation, measurement, and recommendation is described with rigorous exactitude. Your report must leave no detail ambiguous, ensuring that every aspect of the assessment is meticulously documented.

    Your report must be structured into the following sections:

    Table of Contents (with expandable subsections):
      • Executive Summary
      • Scope and Objectives
      • Methodology and Process
      • Detailed Findings and Analysis
      • Security Assessment Metrics
      • System and Network State Analysis
      • Risk Evaluation
      • Remediation and Mitigation Strategies
      • Conclusions
      • Appendix (Supplementary Data)

    For each section, provide exhaustive, exact, and context-independent details:

    Executive Summary:
      Deliver a comprehensive, multi-page overview summarizing the entire security assessment. Capture critical insights such as detected vulnerabilities, policy breaches, anomalous behaviors, and any systemic issues. Emphasize the technical impact on system integrity and the urgent need for precise remedial measures, using detailed quantitative and qualitative descriptions.

    Scope and Objectives:
      Clearly define the boundaries of the assessment, specifying the types of systems, networks, or operational environments evaluated. Detail the primary objectives including the identification of vulnerabilities, verification of security postures, and formulation of precise mitigation strategies, while noting any inherent limitations or constraints that might affect the analysis.

    Tools:
      In each tool add high technical details of the thinking process, execution steps, and results in a precise and verbose manner.

    Methodology and Process:
      Describe a systematic, phased approach to the security assessment. Begin with comprehensive data gathering and reconnaissance, proceed with rigorous vulnerability analysis, and conclude with thorough validation of findings. Explain the general procedures and standardized techniques used for information collection, system inspection, and vulnerability verification—without referencing any specific or proprietary tools. The focus should be on universally applicable methods that guarantee repeatability and exact clarity in any scenario.

    Detailed Findings and Analysis:
      Document every discovered issue with rigorous precision. For each finding, include:
          • A uniquely defined identifier (e.g., ID-001, ID-002, etc.).
          • The category or nature of the vulnerability.
          • An extensively detailed technical description that explains the issue with exactness.
          • Any applicable reference standards or identifiers.
          • A precise severity rating (such as Critical, High, Medium, or Low), supported by both quantitative data and qualitative assessment.
          • A detailed account of the investigative procedures that confirmed the vulnerability.
          • Step-by-step, technically exact remediation guidelines, including the EXACT commands for each mitigation.
          • Supporting evidence such as logs, data captures, configuration details, and contrasted empirical evidence that substantiate the findings.

    Security Assessment Metrics:
      Provide a comprehensive quantitative breakdown of the vulnerabilities by severity levels. Present this analysis in clear charts, tables, or statistical summaries that detail the distribution and frequency of issues, ensuring that every metric is supported by precise numerical data and robust analysis.

    System and Network State Analysis:
      Offer an exhaustive examination of the state of all evaluated systems and networks. For each asset, include precise details such as unique identifiers, connection statuses, running services, detected anomalies, and any vulnerabilities present. The analysis should be granular, leaving no room for ambiguity in the technical description of the asset’s state.

    Risk Evaluation:
      Critically assess the potential impact of each identified vulnerability. Discuss risks in terms of likelihood, potential for unauthorized access, data integrity challenges, operational disruptions, and overall impact on organizational security. Use exact figures and clear, logical reasoning to justify the urgency of each recommended remedial action.

    Remediation and Mitigation Strategies:
      Present detailed, actionable recommendations for addressing each identified issue. Offer a step-by-step guide for system hardening, configuration improvements, policy enhancements, and continuous monitoring practices. Ensure that each recommendation includes the exact mitigation commands to be executed, along with a thorough explanation of their impact. The recommendations must be general and universally applicable, avoiding any references to specific products, brands, or tools, while emphasizing processes and best practices that are precise and replicable in any context.

    Conclusions and Appendix:
      Summarize the key findings and overall outcomes of the security assessment with precision. Reinforce the critical need for immediate and methodically detailed remedial actions. In the Appendix, include any supplementary materials such as detailed logs, configuration snapshots, or other technical evidence that bolster the report’s analysis and conclusions.
    """  # noqa: E501


reporter_agent = Agent(
    name="Report Agent",
    model=os.getenv("CTF_MODEL", "o3-mini"),
    instructions=instructions,
    structured_output_class=PentestReport
)
