"""
JS Surface Mapper - extract high-signal attack surface hints from JS assets.

Baseline functionality (framework-agnostic):
- Fetch entry HTML pages and collect JS asset URLs
- Fetch JS assets (bounded)
- Extract API endpoints, full URLs, GraphQL hints, WS/SSE endpoints
- Optionally fetch sourcemaps and extract from sourcesContent

This tool is intentionally deterministic and bounded to avoid crawling noise.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests  # type: ignore

from cai.sdk.agents import function_tool


_FULL_URL_RE = re.compile(r"https?://[^\s\"'<>\\)]+")
_WS_URL_RE = re.compile(r"wss?://[^\s\"'<>\\)]+")
_GQL_ENDPOINT_RE = re.compile(r"/graphql\b|/gql\b", re.IGNORECASE)
_GQL_OPNAME_RE = re.compile(r"operationName\s*[:=]\s*[\"']([A-Za-z0-9_]{2,})[\"']")
_GQL_OP_RE = re.compile(r"\b(query|mutation|subscription)\s+([A-Za-z0-9_]{2,})")
_PERSISTED_HASH_RE = re.compile(r"sha256Hash\s*[:=]\s*[\"']([a-fA-F0-9]{16,64})[\"']")

# Broad-but-targeted path patterns for endpoints
_PATH_ENDPOINT_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:"
    r"api|graphql|gql|v\d+|admin|internal|export|download|uploads|files|"
    r"report|reports|billing|oauth|auth|login|logout|session|sessions|"
    r"token|tokens|users|user|account|accounts|tenant|tenants|org|orgs|"
    r"organization|organizations|project|projects|team|teams|workspace|workspaces|"
    r"invoice|invoices|payment|checkout|order|orders|cart|carts|subscription|subscriptions|"
    r"feature|features|flag|flags|debug|preview|staging"
    r")(?:[A-Za-z0-9_\-./?=&%]*)"
)

_SOURCE_MAP_RE = re.compile(r"^\s*//#\s*sourceMappingURL\s*=\s*(\S+)\s*$", re.MULTILINE)

_HIGH_VALUE_STRINGS = [
    "admin", "entitlement", "featureflag", "feature_flag", "flag", "debug",
    "internal", "staging", "preview", "billing", "invoice", "payment", "export",
    "report", "impersonate", "impersonation", "role", "permission", "rbac",
    "tenant", "organization", "workspace",
]


@dataclass
class _ExtractionResult:
    origins: Set[str] = field(default_factory=set)
    endpoints: Set[str] = field(default_factory=set)
    graphql_endpoints: Set[str] = field(default_factory=set)
    graphql_ops: Set[str] = field(default_factory=set)
    persisted_hashes: Set[str] = field(default_factory=set)
    ws_endpoints: Set[str] = field(default_factory=set)
    high_value: Set[str] = field(default_factory=set)


class _AssetHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.script_srcs: List[str] = []
        self.inline_scripts: List[str] = []
        self._in_script: bool = False
        self._current_inline: List[str] = []
        self.link_hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "script":
            src = attrs_dict.get("src", "").strip()
            if src:
                self.script_srcs.append(src)
            else:
                self._in_script = True
                self._current_inline = []
        elif tag.lower() == "link":
            rel = attrs_dict.get("rel", "").lower()
            href = attrs_dict.get("href", "").strip()
            as_attr = attrs_dict.get("as", "").lower()
            if href and (rel in ("modulepreload", "preload") or as_attr == "script"):
                self.link_hrefs.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_script:
            content = "".join(self._current_inline).strip()
            if content:
                self.inline_scripts.append(content)
            self._in_script = False
            self._current_inline = []

    def handle_data(self, data: str) -> None:
        if self._in_script and data:
            self._current_inline.append(data)


def _normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = "http://" + base_url
    return base_url.rstrip("/")


def _origin(url: str) -> str:
    p = urlparse(url)
    if not p.scheme or not p.netloc:
        return ""
    return f"{p.scheme}://{p.netloc}"


def _fetch_text(url: str, headers: Optional[Dict[str, str]], cookies: Optional[Dict[str, str]],
                timeout: int, max_bytes: int) -> Tuple[str, Optional[str]]:
    try:
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=timeout, verify=False, stream=True)
        resp.raise_for_status()
        data = bytearray()
        for chunk in resp.iter_content(chunk_size=16384):
            if not chunk:
                continue
            data.extend(chunk)
            if len(data) >= max_bytes:
                break
        # Best-effort decode
        text = data.decode(errors="replace")
        return text, None
    except Exception as exc:  # pylint: disable=broad-except
        return "", f"{url} -> {exc}"


def _extract_from_text(text: str, source_label: str, base_origin: str) -> _ExtractionResult:
    result = _ExtractionResult()
    if not text:
        return result

    for url in _FULL_URL_RE.findall(text):
        result.origins.add(_origin(url))
        if _GQL_ENDPOINT_RE.search(url):
            result.graphql_endpoints.add(url)

    for url in _WS_URL_RE.findall(text):
        result.ws_endpoints.add(url)
        result.origins.add(_origin(url))

    for path in _PATH_ENDPOINT_RE.findall(text):
        if path.startswith("/"):
            result.endpoints.add(path)
            if _GQL_ENDPOINT_RE.search(path):
                result.graphql_endpoints.add(urljoin(base_origin + "/", path))

    for op in _GQL_OPNAME_RE.findall(text):
        result.graphql_ops.add(op)
    for _, op in _GQL_OP_RE.findall(text):
        result.graphql_ops.add(op)

    for h in _PERSISTED_HASH_RE.findall(text):
        result.persisted_hashes.add(h)

    lowered = text.lower()
    for s in _HIGH_VALUE_STRINGS:
        if s in lowered:
            result.high_value.add(s)

    return result


def _merge_result(target: _ExtractionResult, src: _ExtractionResult) -> None:
    target.origins |= src.origins
    target.endpoints |= src.endpoints
    target.graphql_endpoints |= src.graphql_endpoints
    target.graphql_ops |= src.graphql_ops
    target.persisted_hashes |= src.persisted_hashes
    target.ws_endpoints |= src.ws_endpoints
    target.high_value |= src.high_value


@function_tool(strict_mode=False)
def js_surface_mapper(  # pylint: disable=too-many-arguments,too-many-locals
    base_url: str,
    entry_paths: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    same_origin_only: bool = True,
    max_assets: int = 30,
    max_bytes_per_asset: int = 2_000_000,
    include_sourcemaps: bool = False,
    timeout: int = 10,
) -> str:
    """
    Extract JS-derived attack surface hints from a web application.

    Args:
        base_url: Base URL of the app (e.g., https://example.com)
        entry_paths: HTML entry paths to parse (default ["/"])
        headers: Optional request headers (auth)
        cookies: Optional request cookies (auth)
        same_origin_only: Only fetch JS from base origin (default True)
        max_assets: Cap JS assets fetched (default 30)
        max_bytes_per_asset: Cap bytes per asset (default 2,000,000)
        include_sourcemaps: Fetch and parse sourcemaps (default False)
        timeout: Request timeout (seconds)

    Returns:
        JSON string with extracted surface hints and evidence.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        return json.dumps({"error": "base_url is required"}, ensure_ascii=True)

    base_origin = _origin(base_url)
    entry_paths = entry_paths or ["/"]

    assets: List[str] = []
    inline_sources: List[Tuple[str, str]] = []
    errors: List[str] = []
    evidence: Dict[str, Set[str]] = {}
    sourcemaps_info: List[Dict[str, object]] = []

    # Fetch entry HTML pages
    for path in entry_paths:
        entry_url = path if path.startswith("http") else urljoin(base_url + "/", path.lstrip("/"))
        html, err = _fetch_text(entry_url, headers, cookies, timeout, max_bytes_per_asset)
        if err:
            errors.append(err)
            continue
        parser = _AssetHTMLParser()
        parser.feed(html)

        # Inline script content
        for idx, script in enumerate(parser.inline_scripts):
            inline_sources.append((f"{entry_url}#inline{idx+1}", script))

        # External JS assets
        for src in parser.script_srcs + parser.link_hrefs:
            full = src if src.startswith("http") else urljoin(entry_url, src)
            assets.append(full)

    # De-dup assets and apply limits
    seen: Set[str] = set()
    dedup_assets: List[str] = []
    for a in assets:
        if a in seen:
            continue
        seen.add(a)
        if same_origin_only and _origin(a) and _origin(a) != base_origin:
            continue
        dedup_assets.append(a)
        if len(dedup_assets) >= max_assets:
            break

    extraction = _ExtractionResult(origins={base_origin})

    # Extract from inline scripts
    for label, content in inline_sources:
        res = _extract_from_text(content, label, base_origin)
        _merge_result(extraction, res)

    # Fetch JS assets and extract
    for asset_url in dedup_assets:
        js, err = _fetch_text(asset_url, headers, cookies, timeout, max_bytes_per_asset)
        if err:
            errors.append(err)
            continue
        res = _extract_from_text(js, asset_url, base_origin)
        _merge_result(extraction, res)

        # Evidence mapping
        for ep in res.endpoints:
            evidence.setdefault(ep, set()).add(asset_url)
        for op in res.graphql_ops:
            evidence.setdefault(f"gql_op:{op}", set()).add(asset_url)
        for g in res.graphql_endpoints:
            evidence.setdefault(f"gql_endpoint:{g}", set()).add(asset_url)
        for w in res.ws_endpoints:
            evidence.setdefault(f"ws:{w}", set()).add(asset_url)

        # Sourcemap discovery
        if include_sourcemaps:
            for sm in _SOURCE_MAP_RE.findall(js):
                sm_url = sm if sm.startswith("http") else urljoin(asset_url, sm)
                sm_text, sm_err = _fetch_text(sm_url, headers, cookies, timeout, max_bytes_per_asset)
                if sm_err:
                    errors.append(sm_err)
                    continue
                try:
                    sm_json = json.loads(sm_text)
                    sources_content = sm_json.get("sourcesContent") or []
                    sourcemaps_info.append({
                        "url": sm_url,
                        "sourcesContent": bool(sources_content),
                        "source_count": len(sm_json.get("sources", []) or []),
                    })
                    # Extract from sourcesContent (bounded)
                    for idx, src in enumerate(sources_content[:50]):
                        res_map = _extract_from_text(src or "", f"{sm_url}#src{idx+1}", base_origin)
                        _merge_result(extraction, res_map)
                        for ep in res_map.endpoints:
                            evidence.setdefault(ep, set()).add(sm_url)
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(f"{sm_url} -> sourcemap parse error: {exc}")

    # Build output
    endpoints_by_origin: Dict[str, List[str]] = {}
    for ep in sorted(extraction.endpoints):
        endpoints_by_origin.setdefault(base_origin, []).append(ep)

    output = {
        "base_url": base_url,
        "origins": sorted(o for o in extraction.origins if o),
        "assets_fetched": dedup_assets,
        "endpoints": endpoints_by_origin,
        "graphql": {
            "endpoints": sorted(extraction.graphql_endpoints),
            "operation_names": sorted(extraction.graphql_ops),
            "persisted_query_hints": sorted(extraction.persisted_hashes),
        },
        "ws_sse": sorted(extraction.ws_endpoints),
        "sourcemaps": sourcemaps_info,
        "high_value_strings": sorted(extraction.high_value),
        "evidence": {k: sorted(list(v))[:3] for k, v in evidence.items()},
        "errors": errors,
    }

    return json.dumps(output, ensure_ascii=True)
