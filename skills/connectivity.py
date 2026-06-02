"""
connectivity.py
───────────────
Detect whether the host machine is online and expose helpers for
web search (online) and local RAG fallback (offline).

Usage
-----
    from skills.connectivity import is_online, web_search, search_or_rag

    if is_online():
        results = web_search("python async generators")
    else:
        results = rag_search("python async generators")
"""

from __future__ import annotations

import socket
import urllib.request
from typing import Any

# ── connectivity probe ──────────────────────────────────────────────────────

_PROBE_HOST = "1.1.1.1"
_PROBE_PORT = 53
_PROBE_TIMEOUT = 2.0  # seconds


def is_online(host: str = _PROBE_HOST, port: int = _PROBE_PORT,
              timeout: float = _PROBE_TIMEOUT) -> bool:
    """Return True when a TCP connection to *host:port* succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── online: web search via DuckDuckGo (no key required) ────────────────────

def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Perform a DuckDuckGo Lite search and return a list of
    ``{"title": …, "url": …, "snippet": …}`` dicts.

    Requires: ``pip install duckduckgo-search``
    Falls back gracefully to an empty list if the library is absent or the
    network call fails.
    """
    try:
        from duckduckgo_search import DDGS  # type: ignore
        with DDGS() as ddgs:
            return [
                {"title": r.get("title", ""),
                 "url": r.get("href", ""),
                 "snippet": r.get("body", "")}
                for r in ddgs.text(query, max_results=max_results)
            ]
    except Exception as exc:  # noqa: BLE001
        print(f"[connectivity] web_search failed: {exc}")
        return []


def fetch_page(url: str, timeout: float = 10.0) -> str:
    """
    Fetch plain-text content from *url* using stdlib only.
    Returns an empty string on any error.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "claw-code-offline/1.0 (offline-mode)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"[connectivity] fetch_page failed for {url}: {exc}")
        return ""


# ── unified search_or_rag ───────────────────────────────────────────────────

def search_or_rag(query: str, rag_fn: Any | None = None,
                  max_results: int = 5) -> list[dict[str, str]]:
    """
    When online → web_search.
    When offline → call *rag_fn(query)* if provided, else return [].

    Parameters
    ----------
    query       : natural-language query string
    rag_fn      : callable(query: str) → list[dict] (from rag_skill)
    max_results : number of results to request from web search
    """
    if is_online():
        print("[connectivity] Online – using web search.")
        return web_search(query, max_results=max_results)

    print("[connectivity] Offline – falling back to local RAG.")
    if rag_fn is not None:
        try:
            return rag_fn(query)
        except Exception as exc:  # noqa: BLE001
            print(f"[connectivity] RAG fallback failed: {exc}")
    return []
