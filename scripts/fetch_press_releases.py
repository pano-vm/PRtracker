import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, urlopen

TELECOM_KEYWORDS = [
    "broadband",
    "broad band",
    "fibre",
    "fiber",
    "full fibre",
    "full fiber",
    "internet",
    "wifi",
    "wi-fi",
    "router",
    "gigabit",
    "gig1",
    "gig2",
    "gigafast",
    "speed",
    "network",
    "connectivity",
    "mobile",
    "mobiles",
    "mobile phone",
    "data",
    "4g",
    "5g",
    "telecom",
    "telecoms",
    "telecommunications",
    "tv",
    "streaming",
    "bundle",
    "bundles",
    "home phone",
    "sim",
    "sim-only",
    "broadband deal",
    "phone deal",
    "o2",
    "virgin",
]

APPROVED = {
    "virginmediao2": {
        "brand": "Virgin Media O2",
        "group": "Telecoms",
        "listing_urls": [
            "https://news.virginmediao2.co.uk/news-views/"
        ],
        "allowed_domains": {"news.virginmediao2.co.uk"},
    },
    "vodafone": {
        "brand": "Vodafone",
        "group": "Telecoms",
        "listing_urls": [
            "https://www.vodafone.co.uk/newscentre/press-release/"
        ],
        "allowed_domains": {"www.vodafone.co.uk"},
    },
    "ee": {
        "brand": "EE",
        "group": "Telecoms",
        "listing_urls": [
            "https://newsroom.ee.co.uk/?h=1&d=blog"
        ],
        "allowed_domains": {"newsroom.ee.co.uk"},
    },
    "three": {
        "brand": "Three",
        "group": "Telecoms",
        "listing_urls": [
            "https://www.threemediacentre.co.uk/press-release-browser/",
            "https://www.threemediacentre.co.uk/press-release-browser/page/2/",
        ],
        "allowed_domains": {"www.threemediacentre.co.uk"},
    },
    "bt": {
        "brand": "BT",
        "group": "Telecoms",
        "listing_urls": [
            "https://newsroom.bt.com/?h=1&d=excludehomepage"
        ],
        "allowed_domains": {"newsroom.bt.com"},
    },
    "sky": {
        "brand": "Sky",
        "group": "Telecoms",
        "listing_urls": [
            "https://www.skygroup.sky/press/newsroom"
        ],
        "allowed_domains": {"www.skygroup.sky"},
    },
    "comparethemarket": {
        "brand": "Compare the Market",
        "group": "Affiliates",
        "listing_urls": [
            "https://www.comparethemarket.com/inside-ctm/media-centre/"
        ],
        "allowed_domains": {"www.comparethemarket.com"},
    },
    "moneysavingexpert": {
        "brand": "MoneySavingExpert",
        "group": "Affiliates",
        "listing_urls": [
            "https://www.moneysavingexpert.com/pressoffice/",
            "https://www.moneysavingexpert.com/pressoffice/?page=2",
        ],
        "allowed_domains": {"www.moneysavingexpert.com"},
    },
    "uswitch": {
        "brand": "uSwitch",
        "group": "Affiliates",
        "listing_urls": [
            "https://www.uswitch.com/media-centre/category/broadband/",
            "https://www.uswitch.com/media-centre/category/mobiles/",
        ],
        "allowed_domains": {"www.uswitch.com"},
    },
}

UA = "PRtracker/1.0 (+GitHub Actions)"

def contains_telecom_keyword(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(keyword in t for keyword in TELECOM_KEYWORDS)


def should_keep_item(brand_key: str, title: str, url: str) -> bool:
    # Only filter the affiliate sites that contain mixed-topic press releases
    if brand_key in {"comparethemarket", "moneysavingexpert"}:
        combined = f"{title} {url}"
        return contains_telecom_keyword(combined)
    return True

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

    candidate_urls = []
    for listing_url in cfg["listing_urls"]:
        try:
            listing_html = fetch(listing_url)
            links = extract_links(listing_html, listing_url, cfg["allowed_domains"])
            candidate_urls.extend(links[:40])
        except Exception:
            continue

    # Deduplicate candidate URLs
    seen = set()
    deduped_candidates = []
    for u in candidate_urls:
        if u not in seen:
            seen.add(u)
            deduped_candidates.append(u)

    items = []
    seen_item_urls = set()

    for url in deduped_candidates[:80]:
        try:
            article_html = fetch(url)
            title = parse_title(article_html) or url
            published = parse_publish_datetime(article_html)

            if not should_keep_item(key, title, url):
                continue

            if url in seen_item_urls:
                continue
            seen_item_urls.add(url)

            items.append({
                "title": title,
                "url": url,
                "publish_datetime": published,
            })
        except Exception:
            continue

    dated = [i for i in items if i.get("publish_datetime")]
    undated = [i for i in items if not i.get("publish_datetime")]

    dated.sort(key=lambda i: i["publish_datetime"], reverse=True)

    final = (dated + undated)[:10]

    return {
        "status": "ok",
        "brand": cfg["brand"],
        "group": cfg["group"],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": final,
    }

def main():
    for key in APPROVED.keys():
        out = build_feed(key)
        path = f"docs/data/{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Wrote {path} ({len(out['items'])} items)")

if __name__ == "__main__":
    main()
