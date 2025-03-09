"""
Mail Agent module for checking email configuration security.

"""
import dns.resolver  # pylint: disable=import-error
from cai.types import Agent
from cai.tools.misc.cli_utils import execute_cli_command


def get_txt_record(domain, record_type='TXT'):
    """
    Utility function to fetch TXT records for a given domain.
    Returns a list of record strings or an empty list if none found.
    """
    try:
        answers = dns.resolver.resolve(domain, record_type)
        return [rdata.to_text().strip('"') for rdata in answers]
    except Exception:  # pylint: disable=broad-exception-caught
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
    DKIM records are stored in the TXT record of
    <selector>._domainkey.<domain>.
    Returns the DKIM record string if found; otherwise returns None.
    """
    dkim_domain = f"{selector}._domainkey.{domain}"
    txt_records = get_txt_record(dkim_domain, 'TXT')
    if txt_records:
        return txt_records[0]
    return None


def check_mail_spoofing_vulnerability(
        domain: str,
        dkim_selector: str = "default") -> dict:
    """
    Checks if domain is vulnerable to mail spoofing by inspecting SPF,
    DMARC, and DKIM. Returns dict with domain, records found/missing,
    vulnerability status and issues.
    """
    results = {}
    spf_record = check_spf(domain)
    dmarc_record = check_dmarc(domain)
    dkim_record = check_dkim(domain, selector=dkim_selector)

    results['domain'] = domain
    results['spf'] = spf_record if spf_record else "Missing SPF record"
    results['dmarc'] = dmarc_record if dmarc_record else "Missing DMARC record"
    results['dkim'] = (
        dkim_record if dkim_record
        else f"Missing DKIM record (selector: {dkim_selector})"
    )

    vulnerabilities = []
    if not spf_record:
        vulnerabilities.append("SPF")
    if not dmarc_record:
        vulnerabilities.append("DMARC")
    if not dkim_record:
        vulnerabilities.append("DKIM")

    results['vulnerable'] = bool(vulnerabilities)
    results['issues'] = (
        vulnerabilities or ["None detected. All email auth configured."]
    )

    full_string = ""
    for key, value in results.items():
        full_string += f"{key}: {value}\n"
    return full_string


dns_smtp_agent = Agent(
    model="gpt-4o",
    name="DNS_SMTP_Agent",
    description="Agent focused on assessing spoofing DMARC.",
    instructions=(
        "You are an expert in assessing email configuration security. "
        "Inspect domains for mail spoofing vulnerabilities by checking SPF, "
        "DMARC, and DKIM. Use check_mail_spoofing_vulnerability for "
        "detailed reports. Use execute_cli_command for basic scans. "
        "USE ONLY TOOL CALLS, DONT RETURN REASON."
    ),
    functions=[check_mail_spoofing_vulnerability, execute_cli_command]
)
