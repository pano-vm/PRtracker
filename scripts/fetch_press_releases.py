import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, urlopen

APPROVED = {
    "vodafone": {
        "brand": "Vodafone",
        "listing": "https://www.vodafone.co.uk/newscentre/press-release/",
        "allowed_domains": {"www.vodafone.co.uk"},
    },
    "virginmediao2": {
        "brand": "Virgin Media O2",
        "listing": "https://news.virginmediao2.co.uk/news-views/",
        "allowed_domains": {"news.virginmediao2.co.uk"},
    },
}

UA = "PRtracker/1.0 (+GitHub Actions)"

def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def strip_tracking(url: str) -> str:
    p = urlparse(url)
    qs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    new_q = urlencode(qs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))

def domain_allowed(url: str, allowed: set[str]) -> bool:
    return urlparse(url).netloc in allowed

def extract_links(html: str, base: str, allowed_domains: set[str]) -> list[str]:
    # Simple href extraction. Good enough for a first pass.
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
    out = []
    for h in hrefs:
        if h.startswith("#") or h.lower().startswith("javascript:"):
            continue
        u = strip_tracking(urljoin(base, unescape(h)))
        if domain_allowed(u, allowed_domains):
            out.append(u)
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped

def parse_title(html: str) -> str | None:
    # Prefer og:title
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', html, flags=re.I)
    if m:
        return unescape(m.group(1)).strip()
    # Fallback title tag
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if m:
        t = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
        return t
    return None

def parse_publish_datetime(html: str) -> str | None:
    # Try schema.org datePublished (very common)
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html, flags=re.I)
    if m:
        return normalise_iso(m.group(1))
    # Try meta property article:published_time
    m = re.search(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\'](.*?)["\']', html, flags=re.I)
    if m:
        return normalise_iso(m.group(1))
    # Try meta name publish_date
    m = re.search(r'<meta[^>]+name=["\']publish_date["\'][^>]+content=["\'](.*?)["\']', html, flags=re.I)
    if m:
        return normalise_iso(m.group(1))
    return None

def normalise_iso(value: str) -> str | None:
    v = value.strip()
    # If it is already ISO, keep it. Otherwise try simple date formats.
    try:
        # Handle trailing Z or offset automatically
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            continue
    return None

def build_feed(key: str) -> dict:
    cfg = APPROVED[key]
    listing_html = fetch(cfg["listing"])
    candidates = extract_links(listing_html, cfg["listing"], cfg["allowed_domains"])[:60]

    items = []
    for url in candidates:
        try:
            article_html = fetch(url)
            title = parse_title(article_html) or url
            published = parse_publish_datetime(article_html)
            items.append({
                "title": title,
                "url": url,
                "publish_datetime": published,
            })
        except Exception:
            continue

    # Sort: dated first newest to oldest, undated last
    def sort_key(it):
        pd = it.get("publish_datetime")
        return (0, pd) if pd else (1, "")
    items.sort(key=sort_key, reverse=False)
    # items currently oldest first for dated. Reverse dated section by sorting properly:
    dated = [i for i in items if i.get("publish_datetime")]
    undated = [i for i in items if not i.get("publish_datetime")]
    dated.sort(key=lambda i: i["publish_datetime"], reverse=True)

    final = (dated + undated)[:20]

    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": final,
    }

def main():
    for key in APPROVED.keys():
        out = build_feed(key)
        path = f"data/{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Wrote {path} ({len(out['items'])} items)")

if __name__ == "__main__":
    main()
