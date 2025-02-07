import dns.resolver
from cai import Agent
import os
from cai.tools.common import run_command
import dns.resolver
from cai.tools.llm_plugins.cli_utils import execute_cli_command

def get_txt_record(domain, record_type='TXT'):
    """
    Utility function to fetch TXT records for a given domain.
    Returns a list of record strings or an empty list if none found.
    """
    try:
        answers = dns.resolver.resolve(domain, record_type)
        # Clean up the returned strings (remove extraneous quotes)
        return [rdata.to_text().strip('"') for rdata in answers]
    except Exception:
        return []

def check_spf(domain: str):
    """
    Checks for the presence of an SPF record in the domain's TXT records.
    Returns the SPF record string if found; otherwise, returns None.
    """
    txt_records = get_txt_record(domain, 'TXT')
    for record in txt_records:
        if record.lower().startswith("v=spf1"):
            return record
    return None

def check_dmarc(domain: str):
    """
    Checks for the presence of a DMARC record.
    DMARC records are stored in the TXT record of _dmarc.<domain>.
    Returns the DMARC record string if found; otherwise, returns None.
    """
    dmarc_domain = f"_dmarc.{domain}"
    txt_records = get_txt_record(dmarc_domain, 'TXT')
    for record in txt_records:
        if record.lower().startswith("v=dmarc1"):
            return record
    return None

def check_dkim(domain: str, selector: str = "default"):
    """
    Checks for the presence of a DKIM record using the specified selector.
    DKIM records are stored in the TXT record of <selector>._domainkey.<domain>.
    Returns the DKIM record string if found; otherwise, returns None.
    """
    dkim_domain = f"{selector}._domainkey.{domain}"
    txt_records = get_txt_record(dkim_domain, 'TXT')
    # DKIM records may not have a fixed start, so presence of any record is taken as configuration.
    if txt_records:
        return txt_records[0]
    return None

def check_mail_spoofing_vulnerability(domain: str, dkim_selector: str = "default") -> dict:
    """
    Checks if the given domain is vulnerable to mail spoofing by inspecting
    key email authentication mechanisms: SPF, DMARC, and DKIM.

    Returns a dictionary with the following keys:
      - domain: the checked domain
      - spf: the SPF record found or a message indicating it is missing
      - dmarc: the DMARC record found or a message indicating it is missing
      - dkim: the DKIM record found or a message indicating it is missing
      - vulnerable: True if any of the records are missing, otherwise False
      - issues: a list of which records are missing or a message if all are configured
    """
    results = {}
    
    spf_record = check_spf(domain)
    dmarc_record = check_dmarc(domain)
    dkim_record = check_dkim(domain, selector=dkim_selector)
    
    results['domain'] = domain
    results['spf'] = spf_record if spf_record else "Missing SPF record"
    results['dmarc'] = dmarc_record if dmarc_record else "Missing DMARC record"
    results['dkim'] = dkim_record if dkim_record else f"Missing DKIM record (selector: {dkim_selector})"
    
    vulnerabilities = []
    if not spf_record:
        vulnerabilities.append("SPF")
    if not dmarc_record:
        vulnerabilities.append("DMARC")
    if not dkim_record:
        vulnerabilities.append("DKIM")
        
    results['vulnerable'] = True if vulnerabilities else False
    results['issues'] = vulnerabilities if vulnerabilities else ["None detected. All email authentication mechanisms appear configured."]
    
    full_string = ""
    for key, value in results.items():
        line = f"{key}: {value}"
        full_string += line + "\n"
    return full_string

dns_smtp_agent = Agent(
    model="gpt-4o",
    name="DNS_SMTP_Agent",
    instructions=(
        "You are an expert in assessing email configuration security. Your role is to inspect "
        "domains for mail spoofing vulnerabilities by evaluating SPF, DMARC, and DKIM records. "
        "Use the check_mail_spoofing_vulnerability function to generate a detailed report."
        "Use execute cli command for superficial scans"
        "USE ONLY TOOL CALLS, DONT RETURN REASON"
        "Then return to cli_agent"
    ),
    functions=[check_mail_spoofing_vulnerability, execute_cli_command]
)
