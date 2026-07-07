"""
C99.nl multi-purpose OSINT utility for reconnaissance.

This module exposes a single tool `c99` that wraps many C99.nl APIs,
providing a common interface for common recon / OSINT tasks.

Example actions (see C99.nl documentation for full details):
    - \"subdomain\"      → Subdomain Finder / CloudFlare Resolver
    - \"firewall\"       → Firewall Technology (WAF) Detector
    - \"phone_lookup\"   → Phone Lookup
    - \"ping\"           → Ping host
    - \"geoip\"          → GeoIP lookup
    - \"whois\"          → Whois Checker
    - \"gif\"            → GIF Finder

Environment:
    - Requires C99_API_KEY to be set (or present in .env).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union, Literal

import requests
from dotenv import load_dotenv

from cai.sdk.agents import function_tool

logger = logging.getLogger(__name__)

JSONType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


def _get_c99_api_key() -> str:
    """Load and return the C99 API key from the environment."""
    load_dotenv()
    api_key = os.getenv("C99_API_KEY")
    if not api_key:
        raise ValueError("C99.nl API key (C99_API_KEY) must be set in environment variables.")
    return api_key


def _call_c99_api(endpoint: str, params: Dict[str, Any]) -> Optional[JSONType]:
    """
    Generic helper to call a C99.nl API endpoint and return parsed JSON.

    Note: Endpoint paths and parameter names are based on publicly
    available examples and may need adjustment to match your C99.nl
    documentation exactly.
    """
    api_key = _get_c99_api_key()

    base_url = f"https://api.c99.nl/{endpoint}"

    query_params: Dict[str, Any] = {"key": api_key}
    # Remove None-valued parameters to avoid sending them.
    for k, v in params.items():
        if v is not None:
            query_params[k] = v

    # Request JSON output where supported.
    query_params["json"] = ""

    try:
        response = requests.get(base_url, params=query_params, timeout=60)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning("C99 API request timed out for endpoint: %s", endpoint)
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("C99 API connection error for endpoint: %s", endpoint)
        return None
    except requests.exceptions.HTTPError as e:
        logger.warning("C99 API HTTP error for endpoint %s: %s", endpoint, e)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("C99 API request failed for endpoint %s: %s", endpoint, e)
        return None

    try:
        return response.json()
    except ValueError:
        # If JSON parsing fails, fall back to raw text.
        logger.debug("C99 API response is not valid JSON for endpoint: %s, falling back to raw text", endpoint)
        return response.text


def _format_subdomain_results(
    data: JSONType,
    only_cloudflare: bool = False,
) -> str:
    """Format results from the subdomain finder / Cloudflare resolver."""
    if data is None:
        return "No subdomains found or API error occurred."

    # C99.nl / wrappers commonly return a dict with a `subdomains` key.
    if isinstance(data, dict) and "subdomains" in data:
        entries = data.get("subdomains") or []
    elif isinstance(data, list):
        entries = data
    else:
        # Fallback to JSON dump for unexpected shapes.
        return json.dumps(data, indent=2, default=str)

    formatted_results = ""
    count = 0

    for entry in entries:
        # Strings: treat each as a subdomain.
        if isinstance(entry, str):
            subdomain = entry
            cloudflare_flag = None
            ip = None
        elif isinstance(entry, dict):
            subdomain = (
                entry.get("subdomain")
                or entry.get("host")
                or entry.get("domain")
                or entry.get("hostname")
                or "N/A"
            )
            ip = entry.get("ip") or entry.get("ip_address") or entry.get("address")
            cloudflare_flag = entry.get("cloudflare")
            if cloudflare_flag is None:
                cloudflare_flag = entry.get("is_cloudflare")
        else:
            continue

        if only_cloudflare and not cloudflare_flag:
            continue

        count += 1
        formatted_results += f"Subdomain: {subdomain}\n"
        if ip:
            formatted_results += f"IP: {ip}\n"
        if cloudflare_flag is not None:
            formatted_results += f"Cloudflare: {cloudflare_flag}\n"
        formatted_results += "\n"

    if count == 0:
        if only_cloudflare:
            return "No Cloudflare-fronted subdomains found."
        return "No subdomains found."

    return formatted_results


def _format_firewall_results(data: JSONType, target: str) -> str:
    """Format results from the firewall / WAF detector."""
    if data is None:
        return f"No firewall information found for {target} or API error occurred."

    if isinstance(data, dict):
        # Many wrappers return {success: bool, result: "..."} or similar.
        if not data.get("success", True):
            reason = data.get("message") or data.get("error") or "Unknown error"
            return f"Firewall detection failed for {target}: {reason}"

        result = data.get("result") or data.get("firewall") or data.get("waf")
        if result:
            return f"Firewall / WAF for {target}: {result}"

        # Fallback to JSON dump when shape is unexpected but dict-like.
        return json.dumps(data, indent=2, default=str)

    # Fallback for non-dict payloads.
    return str(data)


def _format_phone_lookup_results(data: JSONType, number: str) -> str:
    """Format results from the phone lookup API."""
    if data is None:
        return f"No phone information found for {number} or API error occurred."

    if isinstance(data, dict):
        if not data.get("success", True):
            reason = data.get("message") or data.get("error") or "Unknown error"
            return f"Phone lookup failed for {number}: {reason}"

        formatted = f"Phone lookup for {number}:\n"
        # Highlight commonly useful fields when present.
        common_keys = [
            "international",
            "local_format",
            "country",
            "country_code",
            "location",
            "carrier",
            "line_type",
            "type",
            "valid",
        ]
        for key in common_keys:
            if key in data:
                formatted += f"{key.replace('_', ' ').title()}: {data[key]}\n"

        # Include any remaining keys for completeness.
        extra_keys = {
            k: v
            for k, v in data.items()
            if k not in common_keys and k not in {"success"}
        }
        if extra_keys:
            formatted += f"Extra: {extra_keys}\n"

        return formatted

    # Fallback for non-dict payloads.
    return str(data)


def _format_generic_results(data: Optional[JSONType]) -> str:
    """Generic pretty-printer for C99.nl JSON/text responses."""
    if data is None:
        return "No data returned or API error occurred."

    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, default=str)

    return str(data)


@function_tool
def c99(
    action: Literal[
        "subdomain",
        "cloudflare",
        "firewall",
        "phone_lookup",
        "ping",
        "ip_to_host",
        "dns_checker",
        "host_to_ip",
        "ip2domains",
        "whois",
        "screenshot",
        "geoip",
        "up_or_down",
        "reputation",
        "headers",
        "link_backup",
        "random_string",
        "dictionary",
        "synonym",
        "email_validator",
        "disposable_email",
        "ip_validator",
        "tor_checker",
        "translate",
        "random_person",
        "youtube_details",
        "ip_logger",
        "bitcoin_balance",
        "currency",
        "currency_rates",
        "weather",
        "qr_generator",
        "proxy_detector",
        "password_generator",
        "random_number",
        "license_key",
        "either_or",
        "gif",
    ],
    target: str = "",
    param1: Optional[str] = None,
    param2: Optional[str] = None,
    param3: Optional[str] = None,
    realtime: bool = False,
) -> str:
    """
    Run a C99.nl OSINT action against a target.

    Args:
        action (str): The action to perform. Supported:
            - \"subdomain\": enumerate subdomains for a domain.
            - \"cloudflare\": enumerate subdomains; only show Cloudflare-fronted ones.
            - \"firewall\": detect WAF / firewall technology for a URL.
            - \"phone_lookup\": lookup information about a phone number.
            - \"ping\": ping a host.
            - \"ip_to_host\": resolve an IP to hostname.
            - \"dns_checker\": advanced DNS check for a domain (param1=type, param2=server).
            - \"host_to_ip\": resolve a hostname to IP (param2=server).
            - \"ip2domains\": find domains hosted on an IP.
            - \"whois\": whois lookup for a domain.
            - \"screenshot\": create a screenshot for a URL.
            - \"geoip\": GeoIP lookup for host/IP.
            - \"up_or_down\": website up/down check.
            - \"reputation\": site/URL reputation check.
            - \"headers\": get HTTP headers for a host.
            - \"link_backup\": make online backup of a URL.
            - \"random_string\": pick random string from remote text file.
            - \"dictionary\": dictionary lookup for a word.
            - \"synonym\": synonym lookup for a word.
            - \"email_validator\": validate if e-mail exists.
            - \"disposable_email\": check if e-mail is disposable.
            - \"ip_validator\": validate IP address format.
            - \"tor_checker\": check if IP is TOR exit.
            - \"translate\": translate text (target=text, param1=language code).
            - \"random_person\": generate random person (target=gender).
            - \"youtube_details\": get YouTube video details (target=video ID).
            - \"ip_logger\": manage IP logger (target=action, param1=extra).
            - \"bitcoin_balance\": check Bitcoin address balance.
            - \"currency\": convert currency (target=amount, param1=from, param2=to).
            - \"currency_rates\": get currency rates (target=source currency).
            - \"weather\": weather lookup (target=location).
            - \"qr_generator\": generate QR code (target=string, param1=size).
            - \"proxy_detector\": detect whether IP is a proxy/VPN.
            - \"password_generator\": generate password
                (param1=length, param2=include, param3=customlist).
            - \"random_number\": random number
                (param1=length or param2=\"min,max\" for between).
            - \"license_key\": generate license key
                (target=template, param1=amount).
            - \"either_or\": get random dilemma.
            - \"gif\": find GIFs (target=keyword).
        target (str): Primary target string. Interpretation depends on action,
            see above.
        param1 (str, optional): Auxiliary parameter for some actions.
        param2 (str, optional): Auxiliary parameter for some actions.
        param3 (str, optional): Auxiliary parameter for some actions.
        realtime (bool): For subdomain-related actions, request realtime/fresh
                         results where supported. Ignored for other actions.

    Returns:
        str: A formatted string describing the results, or an error message.
    """
    normalized = action.lower().strip()

    if normalized in {"subdomain", "subdomains"}:
        data = _call_c99_api(
            "subdomainfinder",
            {
                "domain": target,
                "realtime": "true" if realtime else None,
            },
        )
        return _format_subdomain_results(data, only_cloudflare=False)

    if normalized in {"cloudflare", "cf"}:
        data = _call_c99_api(
            "subdomainfinder",
            {
                "domain": target,
                "realtime": "true" if realtime else None,
            },
        )
        return _format_subdomain_results(data, only_cloudflare=True)

    if normalized in {"firewall", "waf"}:
        # NOTE: Endpoint / parameter names are inferred from public examples
        # and may need to be adjusted to match your C99.nl documentation.
        data = _call_c99_api(
            "firewalldetector",
            {
                "url": target,
            },
        )
        return _format_firewall_results(data, target)

    if normalized in {"phone_lookup", "phonelookup", "phone"}:
        data = _call_c99_api(
            "phonelookup",
            {
                "number": target,
            },
        )
        return _format_phone_lookup_results(data, target)

    if normalized == "ping":
        data = _call_c99_api(
            "ping",
            {
                "host": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"ip_to_host", "iptohost"}:
        data = _call_c99_api(
            "gethostname",
            {
                "host": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"dns_checker", "dnschecker"}:
        data = _call_c99_api(
            "dnschecker",
            {
                "url": target,
                "type": param1,  # e.g., a, aaaa, cname, mx, ns, soa, txt
                "server": param2,  # country code or empty for all
            },
        )
        return _format_generic_results(data)

    if normalized in {"host_to_ip", "hosttoip"}:
        data = _call_c99_api(
            "dnsresolver",
            {
                "host": target,
                "server": param2,  # optional server code
            },
        )
        return _format_generic_results(data)

    if normalized == "ip2domains":
        data = _call_c99_api(
            "ip2domains",
            {
                "ip": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "whois":
        data = _call_c99_api(
            "whois",
            {
                "domain": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "screenshot":
        data = _call_c99_api(
            "createscreenshot",
            {
                "url": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "geoip":
        data = _call_c99_api(
            "geoip",
            {
                "host": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"up_or_down", "upordown"}:
        data = _call_c99_api(
            "upordown",
            {
                "host": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"reputation", "reputationchecker"}:
        data = _call_c99_api(
            "reputationchecker",
            {
                "url": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"headers", "getheaders"}:
        data = _call_c99_api(
            "getheaders",
            {
                "host": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"link_backup", "linkbackup"}:
        data = _call_c99_api(
            "linkbackup",
            {
                "url": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"random_string", "randomstringpicker"}:
        data = _call_c99_api(
            "randomstringpicker",
            {
                "textfile": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "dictionary":
        data = _call_c99_api(
            "dictionary",
            {
                "word": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "synonym":
        data = _call_c99_api(
            "synonym",
            {
                "word": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"email_validator", "emailvalidator"}:
        data = _call_c99_api(
            "emailvalidator",
            {
                "email": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"disposable_email", "disposablemailchecker"}:
        data = _call_c99_api(
            "disposablemailchecker",
            {
                "email": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"ip_validator", "ipvalidator"}:
        data = _call_c99_api(
            "ipvalidator",
            {
                "ip": target,
            },
        )
        return _format_generic_results(data)

    if normalized in {"tor_checker", "torchecker"}:
        data = _call_c99_api(
            "torchecker",
            {
                "ip": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "translate":
        data = _call_c99_api(
            "translate",
            {
                "text": target,
                "tolanguage": param1,
            },
        )
        return _format_generic_results(data)

    if normalized == "random_person":
        data = _call_c99_api(
            "randomperson",
            {
                "gender": target or "all",
            },
        )
        return _format_generic_results(data)

    if normalized == "youtube_details":
        data = _call_c99_api(
            "youtubedetails",
            {
                "videoid": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "ip_logger":
        data = _call_c99_api(
            "iplogger",
            {
                "action": target or "viewloggers",
                "id": param1,
            },
        )
        return _format_generic_results(data)

    if normalized == "bitcoin_balance":
        data = _call_c99_api(
            "bitcoinbalance",
            {
                "address": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "currency":
        data = _call_c99_api(
            "currency",
            {
                "amount": target,
                "from": param1,
                "to": param2,
            },
        )
        return _format_generic_results(data)

    if normalized == "currency_rates":
        data = _call_c99_api(
            "currencyrates",
            {
                "source": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "weather":
        data = _call_c99_api(
            "weather",
            {
                "location": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "qr_generator":
        data = _call_c99_api(
            "qrgenerator",
            {
                "string": target,
                "size": param1,
            },
        )
        return _format_generic_results(data)

    if normalized == "proxy_detector":
        data = _call_c99_api(
            "proxydetector",
            {
                "ip": target,
            },
        )
        return _format_generic_results(data)

    if normalized == "password_generator":
        data = _call_c99_api(
            "passwordgenerator",
            {
                "length": param1,
                "include": param2,
                "customlist": param3,
            },
        )
        return _format_generic_results(data)

    if normalized == "random_number":
        data = _call_c99_api(
            "randomnumber",
            {
                "length": param1,
                "between": param2,
            },
        )
        return _format_generic_results(data)

    if normalized == "license_key":
        data = _call_c99_api(
            "licensekeygenerator",
            {
                "template": target,
                "amount": param1,
            },
        )
        return _format_generic_results(data)

    if normalized in {"either_or", "eitheror"}:
        data = _call_c99_api("eitheror", {})
        return _format_generic_results(data)

    if normalized == "gif":
        data = _call_c99_api(
            "gif",
            {
                "keyword": target,
            },
        )
        return _format_generic_results(data)

    return (
        "Unsupported C99 action. Supported actions include: subdomain, cloudflare, "
        "firewall, phone_lookup, ping, ip_to_host, dns_checker, host_to_ip, "
        "ip2domains, whois, screenshot, geoip, up_or_down, reputation, headers, "
        "link_backup, random_string, dictionary, synonym, email_validator, "
        "disposable_email, ip_validator, tor_checker, translate, random_person, "
        "youtube_details, ip_logger, bitcoin_balance, currency, currency_rates, "
        "weather, qr_generator, proxy_detector, password_generator, random_number, "
        "license_key, either_or, gif."
    )


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("c99", c99, categories=["recon", "web"])
