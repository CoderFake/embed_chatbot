from typing import Optional, Tuple, List
import uuid
from fastapi import Request
from urllib.parse import urlsplit


def _parse_forwarded_header(header_value: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse RFC 7239 Forwarded header to extract proto and host.
    Example: Forwarded: for=192.0.2.60;proto=https;host=example.com
    Returns (proto, host)
    """
    try:
        parts = [p.strip() for p in header_value.split(";")]
        kv = {}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.lower()] = v.strip().strip('"')
        return kv.get("proto"), kv.get("host")
    except Exception:
        return None, None


def get_request_origin(request: Request) -> str:
    """
    Get the frontend origin (scheme://host[:port]) for an incoming request.
    Priority:
    1) Origin header (preferred for CORSed requests)
    2) Referer header (fallback)
    3) Forwarded / X-Forwarded-Proto + X-Forwarded-Host (proxy aware)
    4) request.url scheme/netloc (last resort)
    """
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    referer = request.headers.get("referer")
    if referer:
        p = urlsplit(referer)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"

    fwd = request.headers.get("forwarded")
    if fwd:
        proto, host = _parse_forwarded_header(fwd)
        if host:
            scheme = proto or request.url.scheme
            return f"{scheme}://{host}"

    xf_proto = request.headers.get("x-forwarded-proto")
    xf_host = request.headers.get("x-forwarded-host")
    if xf_host:
        host = xf_host.split(",")[0].strip()
        scheme = (xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme)
        return f"{scheme}://{host}"

    return f"{request.url.scheme}://{request.url.netloc}"


def get_request_netloc(request: Request) -> str:
    """
    Get only the netloc (host[:port]) of the frontend origin for this request.
    """
    origin = get_request_origin(request)
    return urlsplit(origin).netloc or request.url.netloc 


def get_subdomain(request: Request) -> Optional[str]:
    """
    Extract subdomain from request host if present.
    - Ignore port
    - Ignore 'www' prefix
    - Return first label when netloc has >= 3 labels (e.g., sub.domain.tld)
    - Return None for IPs, localhost, or bare domains
    """
    try:
        netloc = get_request_netloc(request)
        host = netloc.split(":")[0]
        
        if host == "localhost" or host.replace(".", "").isdigit():
            return None
        labels: List[str] = host.split(".")
        if len(labels) < 3:
            return None
        first = labels[0].lower()
        if first == "www":
            return None
        return first
    except Exception:
        return None


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request, accounting for proxies.
    Priority:
    1) X-Forwarded-For header (first IP in comma-separated list)
    2) X-Real-IP header
    3) request.client.host (direct connection)
    4) 'unknown' as fallback
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()
    
    if request.client and request.client.host:
        return request.client.host
    
    return "unknown"
