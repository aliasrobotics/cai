"""
This module defines data models for generating NIS2 compliance reports.
It includes classes for compliance assessments, evidence, KPI indicators,
and the overall NIS2 report structure.
"""

import os
from pydantic import BaseModel  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error
from extensions.report.nis2.support_agents.risk_agent import RiskAssessment  # pylint: disable=import-error # noqa: E501


class ComplianceAssessment(BaseModel):  # pylint: disable=too-few-public-methods  # noqa: E501
    """
    Represents various compliance assessment criteria for the NIS2 report.

    Each field corresponds to a specific compliance criterion and indicates
    whether the criterion has been met. The values can only be:
    - "[ ]" for not met
    - "[x]" for met.
    """
    A2_risk_assessments: str
    A3_critical_assess: str
    B3_simulations: str
    D1_supply_chain_risks: str
    D2_supply_chain_evaluation: str
    E1_vulnerability_testing: str
    F1_regular_audits: str
    F2_kpis_effectiveness: str
    F3_risk_reports: str
    H1_data_encryption: str
    J1_mfa_usage: str
    J2_communications_protection: str


class Evidence(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents evidence for a finding"""
    empirical_evidence: str  # Explaination of the evidence
    tool_output_evidence: str  # Command output
    command: str  # Command used


class KPIIndicators(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents Key Performance Indicators (KPIs)
      for compliance assessment."""
    name: str  # The name of the KPI
    description: str  # A detailed description of what the KPI measures
    value: str  # The current value or status of the KPI


class NIS2Report(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Represents a NIS2 compliance report.

    """
    date: str  # The date of the report
    client: str  # The name of the client for whom the report is generated
    targets: str  # The targets of the assessment
    executive_summary: str  # A summary of the report's findings and recommendations  # noqa E501
    compliance_assessment: ComplianceAssessment  # The compliance assessment details # noqa E501
    total_complian: int  # Total compliance score or count
    history_pentesting: str  # History of pentesting activities
    # history_nis2: str  # History of NIS2 assessments
    # risk_supply_chain: dict  # A dictionary containing supply chain risk
    # assessment details
    recommendations: str  # Recommendations based on the assessment findings
    evidence_A3: list[str]  # Critical assets identified
    evidence_H1: Evidence  # Evidence related to data encryption
    evidence_J2: Evidence  # Evidence related to communications are protected
    risk: RiskAssessment  # The risk assessment details
    critical_assets: list[str]  # Critical assets of the company are identified
    kpis: list[KPIIndicators]


def instructions(context_variables):  # pylint: disable=unused-argument  # noqa: E501
    """
    Instructions for the nis2 report agent
    """

    return """
    You are an intelligent agent responsible for generating a comprehensive
    NIS2 compliance report. Your task is to fill in the `NIS2Report`
    class with accurate data based on the compliance assessment results.

    The `compliance_assessment` field must only contain values of
    either "[ ]" or "[x]" for each of the following criteria:
    - A2_risk_assessments
    - A3_critical_assess
    - B3_simulations
    - D1_supply_chain_risks
    - D2_supply_chain_evaluation
    - E1_vulnerability_testing
    - F1_regular_audits
    - H1_data_encryption
    - J1_mfa_usage
    - J2_communications_protection

    Ensure that the report includes:
    - Date: The date when the report is generated.
    - Client Name: The name of the client for whom the report is prepared
    - Targets: The specific targets of the assessment, detailing which
       systems, areas and IP were evaluated
    - Executive Summary: A concise summary of the compilance of NIS2.
    - evidence_A3: a list of critical assets for the company has been
      identified
    - In evidence_J2 and evidence_H1 indicates for each one:
      - A description of the security finding.
      - The linux command used to verify the finding.
      - The output of the linux command used.
    - Propose a KPI indicators to measure the effectiveness of cybersecurity
    - History pentensting: This refers to a set of LLM messages from past
      conversations regarding pentesting. It includes any relevant history
      from pentesting DO NOT MODIFY THIS VALE, use it as it is.

    Your output should be structured and detailed,
    ensuring clarity and precision in the compliance assessment values.
"""


reporter_agent = Agent(
    name="Nis2 Report Agent",
    model=os.getenv("CTF_MODEL", "qwen2.5:14b"),
    instructions=instructions,
    structured_output_class=NIS2Report
)

def transfer_to_reporter_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to reporter agent.
    Accepts any keyword arguments but ignores them."""
    return reporter_agent
