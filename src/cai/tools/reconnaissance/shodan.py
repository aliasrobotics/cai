"""
Shodan search utility for reconnaissance.

This module provides functions to search Shodan for information about hosts,
services, and vulnerabilities using the Shodan API.
"""

import logging
import os
import requests
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from cai.sdk.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
def shodan_search(query: str, limit: int = 10) -> str:
    """
    Search Shodan for information based on the provided query.

    Args:
        query (str): The Shodan search query.
        limit (int): Maximum number of results to return. Default is 10.

    Returns:
        str: A formatted string containing the search results.
    """
    results = _perform_shodan_search(query, limit)

    if not results:
        return "No results found or API error occurred."

    formatted_results = ""
    for result in results:
        formatted_results += f"IP: {result.get('ip_str', 'N/A')}\n"
        formatted_results += f"Port: {result.get('port', 'N/A')}\n"
        formatted_results += f"Organization: {result.get('org', 'N/A')}\n"
        formatted_results += f"Hostnames: {', '.join(result.get('hostnames', ['N/A']))}\n"
        formatted_results += f"Country: {result.get('location', {}).get('country_name', 'N/A')}\n"

        if "data" in result:
            formatted_results += (
                f"Banner: {result['data'][:200]}...\n"
                if len(result["data"]) > 200
                else f"Banner: {result['data']}\n"
            )

        formatted_results += "\n"

    return formatted_results


@function_tool
def shodan_host_info(ip: str) -> str:
    """
    Get detailed information about a specific host from Shodan.

    Args:
        ip (str): The IP address of the host.

    Returns:
        str: A formatted string containing host information.
    """
    result = _get_shodan_host_info(ip)

    if not result:
        return f"No information found for IP {ip} or API error occurred."

    formatted_result = f"IP: {result.get('ip_str', 'N/A')}\n"
    formatted_result += f"Organization: {result.get('org', 'N/A')}\n"
    formatted_result += f"Operating System: {result.get('os', 'N/A')}\n"
    formatted_result += f"Country: {result.get('country_name', 'N/A')}\n"
    formatted_result += f"City: {result.get('city', 'N/A')}\n"
    formatted_result += f"ISP: {result.get('isp', 'N/A')}\n"
    formatted_result += f"Last Update: {result.get('last_update', 'N/A')}\n"
    formatted_result += f"Hostnames: {', '.join(result.get('hostnames', ['N/A']))}\n"
    formatted_result += f"Domains: {', '.join(result.get('domains', ['N/A']))}\n\n"

    if "ports" in result:
        formatted_result += f"Open Ports: {', '.join(map(str, result['ports']))}\n\n"

    if "vulns" in result:
        formatted_result += "Vulnerabilities:\n"
        for vuln in result["vulns"]:
            formatted_result += f"- {vuln}\n"

    return formatted_result


def _perform_shodan_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Helper function to perform Shodan searches.

    Args:
        query (str): The Shodan search query.
        limit (int): Maximum number of results to return.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing the search results.
    """
    load_dotenv()
    api_key = os.getenv("SHODAN_API_KEY")

    if not api_key:
        raise ValueError("Shodan API key (SHODAN_API_KEY) must be set in environment variables.")

    base_url = "https://api.shodan.io/shodan/host/search"

    params = {
        "key": api_key,
        "query": query,
        "limit": min(limit, 100),  # Shodan API has limits
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if "matches" not in data:
            return []

        return data["matches"][:limit]

    except requests.exceptions.Timeout:
        logger.warning("Shodan API request timed out for query: %s", query)
        return []
    except requests.exceptions.ConnectionError:
        logger.warning("Shodan API connection error for query: %s", query)
        return []
    except requests.exceptions.HTTPError as e:
        logger.warning("Shodan API HTTP error: %s", e)
        return []
    except (ValueError, KeyError) as e:
        logger.warning("Shodan API response parsing error: %s", e)
        return []
    except requests.exceptions.RequestException as e:
        logger.warning("Shodan API request failed: %s", e)
        return []


def _get_shodan_host_info(ip: str) -> Optional[Dict[str, Any]]:
    """
    Helper function to get host information from Shodan.

    Args:
        ip (str): The IP address of the host.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing host information or None if an error occurs.
    """
    load_dotenv()
    api_key = os.getenv("SHODAN_API_KEY")

    if not api_key:
        raise ValueError("Shodan API key (SHODAN_API_KEY) must be set in environment variables.")

    base_url = f"https://api.shodan.io/shodan/host/{ip}"

    params = {"key": api_key}

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        logger.warning("Shodan API request timed out for IP: %s", ip)
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("Shodan API connection error for IP: %s", ip)
        return None
    except requests.exceptions.HTTPError as e:
        logger.warning("Shodan API HTTP error for IP %s: %s", ip, e)
        return None
    except ValueError as e:
        logger.warning("Shodan API response parsing error for IP %s: %s", ip, e)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("Shodan API request failed for IP %s: %s", ip, e)
        return None


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("shodan_search", shodan_search, categories=["recon", "network"])
TOOL_REGISTRY.register("shodan_host_info", shodan_host_info, categories=["recon", "network"])
