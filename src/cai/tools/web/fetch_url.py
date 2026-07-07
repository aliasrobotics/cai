"""LLM-friendly URL fetcher.

Downloads a single URL and returns its main content as Markdown (HTML),
extracted text (PDF), pretty-printed JSON, or plain text. Designed for use
by CAI agents as a "read the web" tool after running a search.

Design notes:

* Static HTTP only. No JavaScript rendering. SPAs that ship an empty
  ``<html><script>...</script></html>`` shell will not work — this is
  intentional to keep the tool fast, lightweight and OPSEC-friendly.
* httpx is the primary client. If httpx hits a Cloudflare "Just a moment"
  challenge or returns 403/503 with an anti-bot HTML body, the call is
  retried with ``curl-cffi`` (Chrome TLS fingerprint).
* SSRF guard blocks loopback / RFC1918 / link-local / cloud-metadata hosts
  and non-http(s) schemes by default. Bypass via ``CAI_FETCH_ALLOW_INTERNAL``.
* DNS-rebinding mitigation: hostnames are resolved exactly once before the
  request and the resulting IP is *pinned*. httpx is told to dial the IP
  literal while keeping the original FQDN in the ``Host`` header and
  ``sni_hostname`` TLS extension. Redirects are followed manually so each
  hop is re-validated by the SSRF guard.
* All output is wrapped by ``sanitize_external_content`` to defang
  prompt-injection payloads embedded in remote content.
* Errors never raise; they are returned as sanitized strings so the LLM can
  reason about them.

This module is intentionally a single ~600 LOC file (cohesive: SSRF guard
+ fetch + extract + JS-required detector + tool wrapper); splitting it
would create three trivial sub-modules sharing one tool. Cortocircuito
del PRP §8 aceptado.
"""

from __future__ import annotations

import asyncio
import io
import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx

from cai.agents.guardrails import sanitize_external_content
from cai.sdk.agents import function_tool

# Cloud-metadata hostnames that must never be reachable through the tool.
_METADATA_HOSTS: frozenset[str] = frozenset(
    {
        "metadata.google.internal",
        "metadata",
        "metadata.azure.com",
        "instance-data",
    }
)

# Numeric metadata endpoints (IMDS).
_METADATA_IPS: frozenset[str] = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure / DigitalOcean / Alibaba
        "100.100.100.200",  # Alibaba Cloud secondary
        "fd00:ec2::254",  # AWS IPv6 IMDS
    }
)

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Heuristic markers for anti-bot interstitials.
_ANTIBOT_MARKERS: tuple[bytes, ...] = (
    b"Just a moment",
    b"cf-browser-verification",
    b"challenge-platform",
    b"__cf_chl",
    b"Attention Required! | Cloudflare",
)

# Clamp range for the user-controlled ``max_chars`` parameter.
_MAX_CHARS_MIN = 1024
_MAX_CHARS_MAX = 1_000_000
_MAX_CHARS_DEFAULT = 80_000

# Cap for redirect chains followed manually.
_MAX_REDIRECTS = 5


class _SSRFBlocked(Exception):
    """Raised when an outbound request is blocked by the SSRF guard."""


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _unwrap_mapped_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Return the embedded IPv4 address for IPv4-mapped IPv6 addresses.

    ``::ffff:169.254.169.254`` and ``::ffff:127.0.0.1`` route to the same
    hosts as their bare IPv4 forms, but a plain string comparison against
    ``_METADATA_IPS`` misses them and some Python versions do not flag the
    mapped form as private/link-local. Unwrapping to the embedded IPv4 makes
    the metadata and private-range checks apply uniformly. Non-mapped
    addresses are returned unchanged.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped if mapped is not None else ip


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _check_ssrf(url: str, *, allow_internal: bool) -> str:
    """Validate *url* and return the IP literal that must be dialed.

    Resolving DNS here (and only here) is what makes the tool resistant to
    DNS rebinding: the caller must connect to the returned IP rather than
    re-resolving the FQDN.

    Returns:
        The IP literal (IPv4 or IPv6 string) to dial.

    Raises:
        _SSRFBlocked: if scheme, host or any resolved IP is forbidden.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()

    if scheme not in _ALLOWED_SCHEMES:
        raise _SSRFBlocked(
            f"scheme '{scheme}' is not allowed (only http/https)"
        )

    host = (parts.hostname or "").lower()
    if not host:
        raise _SSRFBlocked("URL has no host component")

    # Cloud metadata is ALWAYS blocked, regardless of CAI_FETCH_ALLOW_INTERNAL.
    if host in _METADATA_HOSTS or host in _METADATA_IPS:
        raise _SSRFBlocked(f"host '{host}' is a cloud-metadata endpoint")

    # Literal IP path.
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None  # not a literal IP; fall through to FQDN resolution

    if ip_obj is not None:
        # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) so the checks
        # below cannot be bypassed with the mapped form of a blocked address.
        ip_obj = _unwrap_mapped_ip(ip_obj)
        # Cloud metadata is ALWAYS blocked, regardless of allow_internal. The
        # string pre-check above only matches the bare IPv4 literal, so the
        # mapped IPv6 form is caught here.
        if str(ip_obj) in _METADATA_IPS:
            raise _SSRFBlocked(f"host '{host}' is a cloud-metadata endpoint")
        if not allow_internal and _is_unsafe_ip(ip_obj):
            raise _SSRFBlocked(f"host '{host}' is a private/reserved address")
        return host

    # FQDN: resolve, validate every record, return the first safe IP.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise _SSRFBlocked(f"cannot resolve host '{host}': {exc}") from exc

    safe_ips: list[str] = []
    for info in infos:
        raw_addr = info[4][0]
        ip_str = str(raw_addr)  # getaddrinfo returns int for AF_UNIX edge cases
        try:
            ip = _unwrap_mapped_ip(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
        if str(ip) in _METADATA_IPS:
            raise _SSRFBlocked(
                f"host '{host}' resolves to cloud-metadata IP '{ip_str}'"
            )
        if not allow_internal and _is_unsafe_ip(ip):
            raise _SSRFBlocked(
                f"host '{host}' resolves to private/loopback/link-local '{ip_str}'"
            )
        safe_ips.append(ip_str)

    if not safe_ips:
        raise _SSRFBlocked(f"no usable IPs for host '{host}'")
    # Only the first safe A/AAAA record is returned; happy-eyeballs over the
    # remaining records is not implemented (the connection just fails if the
    # first IP is down). Adequate for read-the-web fetches; revisit if we
    # start using fetch_url against multi-homed hosts with flaky primaries.
    return safe_ips[0]


def _build_pinned_url(url: str, resolved_ip: str) -> tuple[str, str]:
    """Return ``(pinned_url, original_host_header)``.

    The pinned URL replaces the FQDN with the validated IP so httpx dials
    that exact address. The Host header still carries the original FQDN so
    virtual hosting works and the TLS cert is verified against the right name.
    If the URL already used an IP literal, the URL is returned unchanged.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host == resolved_ip.lower():
        return url, parts.netloc

    ip_for_netloc = (
        f"[{resolved_ip}]" if ":" in resolved_ip else resolved_ip
    )
    netloc = (
        f"{ip_for_netloc}:{parts.port}" if parts.port else ip_for_netloc
    )
    pinned = urlunsplit(
        (parts.scheme, netloc, parts.path or "/", parts.query, parts.fragment)
    )
    return pinned, parts.netloc


def _looks_like_antibot(body: bytes, status: int) -> bool:
    if status in (403, 503):
        return True
    sample = body[:4096]
    return any(marker in sample for marker in _ANTIBOT_MARKERS)


def _default_headers(user_agent: str | None) -> dict[str, str]:
    return {
        "User-Agent": user_agent
        or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/pdf,application/json;q=0.9,*/*;q=0.5"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _fetch_httpx_pinned(
    url: str,
    resolved_ip: str,
    *,
    timeout: int,
    max_bytes: int,
    user_agent: str | None,
) -> tuple[bytes, str, int, str | None]:
    """Fetch *url* by dialing *resolved_ip* (DNS-rebinding-safe).

    Returns ``(body, content_type, status, location)``. ``location`` is the
    raw ``Location`` header when the response is 3xx; ``None`` otherwise.
    """
    pinned_url, host_header = _build_pinned_url(url, resolved_ip)
    parts = urlsplit(url)

    headers = _default_headers(user_agent)
    headers["Host"] = host_header

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout,
        http2=False,
    ) as client:
        request = client.build_request("GET", pinned_url, headers=headers)
        if parts.scheme == "https" and parts.hostname:
            # Tell the TLS layer to use the original FQDN for SNI and cert
            # verification, even though we are dialing the IP literal.
            request.extensions["sni_hostname"] = parts.hostname

        resp = await client.send(request, stream=True)
        try:
            chunks: list[bytes] = []
            received = 0
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                received += len(chunk)
                if received >= max_bytes:
                    break
            body = b"".join(chunks)[:max_bytes]
            ctype = resp.headers.get("content-type", "").split(";", 1)[0].strip()
            status = resp.status_code
            location = (
                resp.headers.get("location")
                if 300 <= status < 400
                else None
            )
        finally:
            await resp.aclose()
    return body, ctype, status, location


def _fetch_curl_cffi_sync(
    url: str,
    resolved_ip: str,  # kept for API symmetry with the httpx path (see docstring)
    *,
    timeout: int,
    max_bytes: int,
    user_agent: str | None,
) -> tuple[bytes, str, int]:
    """Synchronous curl-cffi fallback (Chrome TLS fingerprint).

    Known limitation: curl-cffi's high-level API does not expose ``--resolve``,
    so this fallback path lets curl re-resolve the FQDN. We accept the
    narrower DNS-rebinding window because this code path only runs when
    httpx hit an anti-bot challenge AND its own SSRF check (with IP pinning)
    already passed for the same URL milliseconds earlier.
    """
    from curl_cffi import requests as curl_requests  # local import (heavy)

    resp = curl_requests.get(
        url,
        impersonate="chrome124",
        timeout=timeout,
        allow_redirects=False,
        headers=_default_headers(user_agent),
    )
    body = resp.content[:max_bytes] if resp.content else b""
    ctype = resp.headers.get("content-type", "").split(";", 1)[0].strip()
    return body, ctype, resp.status_code


def _detect_kind(body: bytes, content_type: str) -> str:
    """Return one of: 'pdf', 'html', 'json', 'text', 'unknown'."""
    if body[:5] == b"%PDF-" or content_type == "application/pdf":
        return "pdf"
    if content_type.startswith("application/json"):
        return "json"
    if content_type.startswith("text/html") or content_type in {
        "application/xhtml+xml",
        "application/xml",
    }:
        return "html"
    if not content_type:
        stripped = body[:64].lstrip()
        if stripped[:1] in (b"{", b"["):
            try:
                json.loads(body.decode("utf-8", errors="replace"))
                return "json"
            except (ValueError, UnicodeDecodeError):
                pass
        if b"<html" in body[:1024].lower() or b"<!doctype html" in body[:1024].lower():
            return "html"
    if content_type.startswith("text/"):
        return "text"
    return "unknown"


def _decode_body(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
    if match:
        try:
            return body.decode(match.group(1), errors="replace")
        except LookupError:
            pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1", errors="replace")


# Phrases that strongly indicate the page is a JavaScript-required SPA
# or a frame-busting redirect, where the static HTML body contains no
# useful content for the LLM. Evidence from debug session ab1027:
# - NVD vuln/search returns 200 with body "You are viewing this page in
#   an unauthorized frame window. This is a potential security issue,
#   you are being redirected to ..."
# - cve.org SPA returns 200 with body "We're sorry but the CVE Website
#   doesn't work properly without JavaScript ..."
_JS_REQUIRED_PATTERNS: tuple[str, ...] = (
    "doesn't work properly without javascript",
    "please enable javascript",
    "javascript is required",
    "you need to enable javascript",
    "you are viewing this page in an unauthorized frame window",
    "this is a potential security issue, you are being redirected",
)

# URL → suggested alternative endpoint when fetch_url hits a JS-required
# wall. Keys are substrings matched against the original URL host/path.
_JS_FALLBACK_HINTS: tuple[tuple[str, str], ...] = (
    (
        "nvd.nist.gov/vuln",
        "Use the JSON API instead: "
        "https://services.nvd.nist.gov/rest/json/cves/2.0"
        "?keywordSearch=YOUR_TERM&resultsPerPage=20",
    ),
    (
        "cve.org",
        "Use the legacy MITRE search instead: "
        "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=YOUR_TERM",
    ),
)


def _detect_js_required(html_lower: str) -> str | None:
    """Return the matched indicator if the page is JS-dependent, else None."""
    for needle in _JS_REQUIRED_PATTERNS:
        if needle in html_lower:
            return needle
    return None


def _build_js_required_message(url: str, indicator: str, body_size: int) -> str:
    suggestion = ""
    for key, hint in _JS_FALLBACK_HINTS:
        if key in url.lower():
            suggestion = f"\nSuggestion for this host: {hint}\n"
            break
    if not suggestion:
        suggestion = (
            "\nSuggestion: look for a JSON/REST API endpoint, an RSS/Atom "
            "feed, or a static documentation mirror of this resource.\n"
        )
    return (
        f"[fetch_url] {url}\n"
        f"# Status: 200 but page requires JavaScript to render useful content\n"
        f'# Detected pattern: "{indicator}"\n'
        f"# Bytes received: {body_size}\n\n"
        "This URL serves a JavaScript-only Single-Page-Application or a "
        "frame-busting redirect page. fetch_url does not execute JavaScript, "
        "so no usable content can be extracted from this URL."
        f"{suggestion}"
    )


def _extract_html(body: bytes, content_type: str) -> str:
    import trafilatura  # local import to keep startup cost low

    html = _decode_body(body, content_type)
    md = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_formatting=True,
        favor_recall=True,
    )
    if md:
        return md
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "[empty document]"


def _extract_pdf(body: bytes) -> str:
    from pypdf import PdfReader  # local import

    reader = PdfReader(io.BytesIO(body))
    pages: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:  # pylint: disable=broad-except
            txt = ""
        pages.append(f"## Page {idx}\n\n{txt.strip()}")
    return "\n\n".join(pages) if pages else "[empty PDF]"


def _extract_json(body: bytes, content_type: str) -> str:
    text = _decode_body(body, content_type)
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError:
        return text


def _extract(body: bytes, content_type: str) -> str:
    kind = _detect_kind(body, content_type)
    if kind == "pdf":
        return _extract_pdf(body)
    if kind == "html":
        return _extract_html(body, content_type)
    if kind == "json":
        return _extract_json(body, content_type)
    if kind == "text":
        return _decode_body(body, content_type)
    return f"[Unsupported content type: {content_type or 'unknown'}]"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    dropped = len(text) - max_chars
    return text[:max_chars] + f"\n\n[...truncated {dropped} chars]"


def _clamp_max_chars(value: int) -> int:
    """Clamp ``max_chars`` into the safe operating range."""
    if value <= 0:
        return _MAX_CHARS_DEFAULT
    return max(_MAX_CHARS_MIN, min(value, _MAX_CHARS_MAX))


async def _fetch_with_redirects(
    url: str,
    *,
    allow_internal: bool,
    timeout: int,
    max_bytes: int,
    user_agent: str | None,
) -> tuple[bytes, str, int, str]:
    """Fetch *url* following up to ``_MAX_REDIRECTS`` hops manually.

    Every hop is re-validated by the SSRF guard before connecting. Returns
    ``(body, content_type, status, final_url)``.
    """
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        ip = _check_ssrf(current, allow_internal=allow_internal)
        body, ctype, status, location = await _fetch_httpx_pinned(
            current,
            ip,
            timeout=timeout,
            max_bytes=max_bytes,
            user_agent=user_agent,
        )
        if location and 300 <= status < 400:
            current = str(httpx.URL(current).join(location))
            continue
        return body, ctype, status, current
    raise _SSRFBlocked(f"too many redirects from {url}")


@function_tool
async def fetch_url(
    url: str,
    max_chars: int = _MAX_CHARS_DEFAULT,
    timeout: int = 0,
) -> str:
    """Fetch a single URL and return its main content, ready for an LLM.

    Use this AFTER a web search (``make_google_search``,
    ``query_perplexity``) to read the actual content of a result.

    Behaviour:

    * HTML pages are converted to Markdown with navigation/ads stripped.
    * PDFs are extracted as text, one section per page.
    * JSON endpoints are returned pretty-printed.
    * Plain text is passed through.
    * If a page is protected by a basic anti-bot challenge, the call is
      transparently retried using a Chrome TLS-fingerprint client.
    * Requests to private / loopback / link-local / cloud-metadata hosts are
      blocked by default. Set ``CAI_FETCH_ALLOW_INTERNAL=true`` to allow
      internal targets during an authorised internal pentest.
    * Hostnames are DNS-resolved exactly once and the resulting IP is
      pinned for the request, defeating DNS rebinding. Redirects are
      followed manually so each hop is re-validated.
    * JavaScript is NOT executed; single-page apps that require client-side
      rendering will return an empty shell.

    Args:
        url: HTTP or HTTPS URL to fetch.
        max_chars: Hard cap on returned characters (clamped to
            [1024, 1_000_000]; default 80_000).
        timeout: Per-request timeout in seconds. ``0`` uses ``CAI_FETCH_TIMEOUT``
            (default 20s).

    Returns:
        The extracted content, wrapped in CAI's external-content delimiters
        to defang any embedded prompt-injection payload. Errors are returned
        as sanitized strings; this function never raises.
    """
    allow_internal = _bool_env("CAI_FETCH_ALLOW_INTERNAL", False)
    max_bytes = _int_env("CAI_FETCH_MAX_BYTES", 5_242_880)
    effective_timeout = timeout if timeout > 0 else _int_env("CAI_FETCH_TIMEOUT", 20)
    user_agent = os.getenv("CAI_FETCH_USER_AGENT") or None
    clamped_chars = _clamp_max_chars(max_chars)

    try:
        body, ctype, status, final_url = await _fetch_with_redirects(
            url,
            allow_internal=allow_internal,
            timeout=effective_timeout,
            max_bytes=max_bytes,
            user_agent=user_agent,
        )
    except _SSRFBlocked as exc:
        return sanitize_external_content(
            f"[fetch_url blocked] {exc}. "
            "Set CAI_FETCH_ALLOW_INTERNAL=true to permit internal targets."
        )
    except Exception as exc:  # pylint: disable=broad-except
        return sanitize_external_content(
            f"[fetch_url error] httpx failed: {type(exc).__name__}: {exc}"
        )

    # Anti-bot fallback. We re-validate SSRF on the final URL just in case
    # the redirect chain changed the host.
    if _looks_like_antibot(body, status):
        try:
            ip = _check_ssrf(final_url, allow_internal=allow_internal)
            body2, ctype2, status2 = await asyncio.to_thread(
                _fetch_curl_cffi_sync,
                final_url,
                ip,
                timeout=effective_timeout,
                max_bytes=max_bytes,
                user_agent=user_agent,
            )
            if not _looks_like_antibot(body2, status2):
                body, ctype, status = body2, ctype2, status2
        except Exception:  # pylint: disable=broad-except
            pass  # keep original 4xx/5xx response

    if status >= 400:
        return sanitize_external_content(
            f"[fetch_url] HTTP {status} for {url}. "
            f"Body preview:\n\n{_extract(body, ctype)[:2000]}"
        )

    # Detect JS-required pages / frame-busting redirects on text/html responses.
    # These return HTTP 200 with a body that contains no useful content,
    # so we short-circuit with a clear error pointing the LLM to alternatives.
    if (ctype or "").lower().startswith("text/html"):
        html_lower = _decode_body(body, ctype).lower()
        js_indicator = _detect_js_required(html_lower)
        if js_indicator:
            return sanitize_external_content(
                _build_js_required_message(final_url, js_indicator, len(body))
            )

    extracted = _truncate(_extract(body, ctype), clamped_chars)

    header = (
        f"# Fetched: {final_url}\n"
        f"# Status: {status}\n"
        f"# Content-Type: {ctype or 'unknown'}\n"
        f"# Bytes: {len(body)}\n\n"
    )
    return sanitize_external_content(header + extracted)


# --- Auto-register with ToolRegistry ---
# Registered under "misc" so every agent type (red, blue, bugbounty, purple,
# dfir, plus the default fallback) gets access. Also under "recon" and "web"
# for category-targeted lookups.
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402

TOOL_REGISTRY.register("fetch_url", fetch_url, categories=["recon", "web", "misc"])
