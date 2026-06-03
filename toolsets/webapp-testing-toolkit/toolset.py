"""webapp-testing-toolkit — URL checking and basic HTTP diagnostics.
===================================================================="""


try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def check_url(*, url: str) -> dict:
    """Check if a URL is reachable and return status info.

    Args:
        url: Full URL to check.

    Returns:
        dict with: url, status_code, reachable, content_type, redirect_url, latency_ms
    """
    import urllib.request
    import urllib.error
    import time
    try:
        start = time.monotonic()
        req = urllib.request.Request(url, method='HEAD',
            headers={'User-Agent': 'ToolStore/1.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        latency = round((time.monotonic() - start) * 1000)
        return {"url": url, "status_code": resp.status, "reachable": True,
                "content_type": resp.headers.get('Content-Type', ''),
                "redirect_url": resp.url if resp.url != url else None,
                "latency_ms": latency}
    except urllib.error.HTTPError as e:
        return {"url": url, "status_code": e.code, "reachable": True,
                "content_type": e.headers.get('Content-Type', '') if hasattr(e, 'headers') else ''}
    except Exception as e:
        return {"url": url, "reachable": False, "error": str(e)}


@tool
def extract_urls(*, text: str, base_url: str = "") -> dict:
    """Extract all URLs from a block of text and optionally resolve relative links.

    Args:
        text:     The text to scan for URLs.
        base_url: If provided, resolve relative URLs against this base.

    Returns:
        dict with "urls" list and "count".
    """
    import re
    from urllib.parse import urljoin

    urls = re.findall(r'https?://[^\s<>"\'\)]+|/[^\s<>"\'\)]+\.\w+|(?<=\s)/[^\s<>"\'\)]{2,}', text)
    seen = set()
    result = []
    for u in urls:
        u = u.rstrip('.,;:!?')
        if u in seen:
            continue
        seen.add(u)
        if base_url and not u.startswith('http'):
            u = urljoin(base_url, u)
        result.append(u)

    return {"urls": result, "count": len(result)}
