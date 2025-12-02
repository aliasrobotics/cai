"""
Module for analyzing HTTP requests and responses with security focus.

This module provides utilities for making HTTP requests and analyzing
the responses from a security testing perspective, including header
analysis, parameter inspection, and security vulnerability detection.
"""

from urllib.parse import urlparse
import requests  # pylint: disable=E0401
from cai.sdk.agents import function_tool


@function_tool(strict_mode=False)
def web_request_framework(  # noqa: E501 # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
                            url: str = "",
                            method: str = "GET",
                            headers: dict = None,
                            data: dict = None,
                            cookies: dict = None,
                            params: dict = None,
                            ctf=None) -> str:  # pylint: disable=unused-argument  # noqa: E501
    """
    Analyze HTTP requests and responses in detail for security testing.

    Args:
        url: Target URL to analyze
        method: HTTP method (GET, POST, etc.)
        headers: Request headers
        data: Request body data
        cookies: Request cookies
        params: URL parameters
        ctf: CTF object to use for context
    Returns:
        str: Detailed analysis of the HTTP interaction including:
            - Request details (method, headers, parameters)
            - Response analysis (status, headers, body)
            - Security observations
            - Potential vulnerabilities
            - Suggested attack vectors
    """
    try:
        # Initialize analysis results
        analysis = []
        analysis.append("\n=== HTTP Request Analysis ===\n")

        # Analyze URL structure
        parsed_url = urlparse(url)
        analysis.append("URL Analysis:")
        analysis.append(f"- Scheme: {parsed_url.scheme}")
        analysis.append(f"- Domain: {parsed_url.netloc}")
        analysis.append(f"- Path: {parsed_url.path}")
        analysis.append(f"- Parameters: {parsed_url.query}")

        # Analyze request components
        analysis.append("\nRequest Details:")
        analysis.append(f"- Method: {method}")

        if headers:
            analysis.append("\nHeaders Analysis:")
            for header, value in headers.items():
                analysis.append(f"- {header}: {value}")

        if cookies:
            analysis.append("\nCookies Analysis:")
            for cookie, value in cookies.items():
                analysis.append(f"- {cookie}: {value}")

        if params:
            analysis.append("\nParameters Analysis:")
            for param, value in params.items():
                analysis.append(f"- {param}: {value}")

        if data:
            analysis.append("\nBody Data Analysis:")
            for key, value in data.items():
                analysis.append(f"- {key}: {value}")

        # Make the request and analyze response
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            cookies=cookies,
            params=params,
            verify=False,
            allow_redirects=True
        )

        analysis.append("\n=== HTTP Response Analysis ===\n")
        analysis.append(f"Status Code: {response.status_code}")

        analysis.append("\nResponse Headers:")
        for header, value in response.headers.items():
            analysis.append(f"- {header}: {value}")

        analysis.append(f"\nResponse Size: {len(response.content)} bytes")

        # Security observations
        analysis.append("\n=== Security Analysis ===\n")

        # Check security headers
        security_headers = [
            'Strict-Transport-Security',
            'Content-Security-Policy',
            'X-Frame-Options',
            'X-XSS-Protection',
            'X-Content-Type-Options'
        ]

        missing_headers = []
        for header in security_headers:
            if header not in response.headers:
                missing_headers.append(header)

        if missing_headers:
            analysis.append("Missing Security Headers:")
            for header in missing_headers:
                analysis.append(f"- {header}")

        # Check for sensitive information
        sensitive_patterns = [
            'password',
            'token',
            'key',
            'secret',
            'admin',
            'root'
        ]

        for pattern in sensitive_patterns:
            if pattern in response.text.lower():
                analysis.append(
                    f"\nPotential sensitive information found: '{pattern}'")

        return "\n".join(analysis)

    except Exception as e:  # pylint: disable=broad-except
        return f"Error analyzing request: {str(e)}"
