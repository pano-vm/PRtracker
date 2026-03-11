import json
import re
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
    "phone",
    "phones",
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
            "https://www.skygroup.sky/api/search?searchTerm=&filterBy=&userLocale=en-gb&currentPage=0"
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
    if brand_key in {"comparethemarket", "moneysavingexpert"}:
        combined = f"{title} {url}"
        return contains_telecom_keyword(combined)
    return True


def fetch(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    qs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]
    new_q = urlencode(qs)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment)
    )


def domain_allowed(url: str, allowed: set[str]) -> bool:
    return urlparse(url).netloc in allowed


def extract_links(html: str, base: str, allowed_domains: set[str]) -> list[str]:
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
    urls = []

    for href in hrefs:
        if href.startswith("#"):
            continue
        if href.lower().startswith("javascript:") or href.lower().startswith("mailto:"):
            continue

        full = urljoin(base, unescape(href))
        full = strip_tracking(full)

        if domain_allowed(full, allowed_domains):
            urls.append(full)

    seen = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def extract_vodafone_press_release_links(html: str, base: str) -> list[str]:
    links = []
    article_blocks = re.findall(r"<article\b.*?</article>", html, flags=re.I | re.S)

    for block in article_blocks:
        if not re.search(r'>\s*Press Release\s*<', block, flags=re.I):
            continue

        match = re.search(
            r'href=["\'](https://www\.vodafone\.co\.uk/newscentre/[^"\']+)["\']',
            block,
            flags=re.I,
        )
        if match:
            url = strip_tracking(unescape(match.group(1)))
            links.append(url)

    seen = set()
    deduped = []
    for url in links:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def extract_bt_article_links(html: str, base: str) -> list[str]:
    links = []
    matches = re.findall(
        r'<a[^>]+class=["\'][^"\']*text_latestnews_more[^"\']*["\'][^>]+href=["\'](.*?)["\']',
        html,
        flags=re.I | re.S,
    )

    for href in matches:
        url = strip_tracking(urljoin(base, unescape(href)))
        if urlparse(url).netloc == "newsroom.bt.com":
            links.append(url)

    seen = set()
    deduped = []
    for url in links:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def extract_comparethemarket_listing_items(html: str, base: str) -> list[dict]:
    items = []

    matches = re.findall(
        r'href="(https://www\.comparethemarket\.com/inside-ctm/media-centre/[^"]+/)"',
        html,
        flags=re.I,
    )

    seen = set()

    for url in matches:
        clean_url = strip_tracking(unescape(url)).rstrip("/")

        if clean_url == "https://www.comparethemarket.com/inside-ctm/media-centre":
            continue

        if clean_url in seen:
            continue

        seen.add(clean_url)

        slug = clean_url.rsplit("/", 1)[-1]

        title = slug.replace("-", " ").strip().title()

        items.append({
            "title": title,
            "url": clean_url,
            "publish_datetime": None,
        })

    return items


def extract_uswitch_listing_items(html: str, base: str) -> list[dict]:
    items = []

    matches = re.finditer(
        r'<a[^>]+href=["\'](/media-centre/[^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    )

    for match in matches:
        href = match.group(1)
        title_html = match.group(2)

        url = strip_tracking(urljoin(base, unescape(href)))

        if urlparse(url).netloc != "www.uswitch.com":
            continue
        if "/media-centre/category/" in url:
            continue
        if "?page=" in url:
            continue
        if not re.search(r"/media-centre/\d{4}/\d{2}/", url):
            continue

        title = re.sub(r"<[^>]+>", "", title_html)
        title = unescape(title).strip()

        if not title:
            continue

        items.append({
            "title": title,
            "url": url,
            "publish_datetime": extract_date_from_uswitch_url(url),
        })

    seen = set()
    deduped = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)

    return deduped


def extract_sky_api_items(api_url: str) -> list[dict]:
    raw = fetch(api_url)
    data = json.loads(raw)
    results = data.get("results", [])

    items = []
    for result in results:
        title = (result.get("title") or "").strip()
        publish_date = result.get("publishDate")
        slug = result.get("slug") or ""

        if not title or not slug:
            continue

        url = urljoin("https://www.skygroup.sky", slug)
        items.append({
            "title": title,
            "url": strip_tracking(url),
            "publish_datetime": normalise_iso(publish_date) if publish_date else None,
        })

    return items


def parse_title(html: str) -> str | None:
    match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.I,
    )
    if match:
        return unescape(match.group(1)).strip()

    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if match:
        return re.sub(r"\s+", " ", unescape(match.group(1))).strip()

    return None


def normalise_title(title: str) -> str:
    if not title:
        return title

    letters = [c for c in title if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        return title.title()

    return title


def parse_publish_datetime(html: str) -> str | None:
    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html, flags=re.I)
    if match:
        return normalise_iso(match.group(1))

    match = re.search(
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.I,
    )
    if match:
        return normalise_iso(match.group(1))

    match = re.search(
        r'<meta[^>]+name=["\']publish_date["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.I,
    )
    if match:
        return normalise_iso(match.group(1))

    return None


def normalise_iso(value: str) -> str | None:
    if not value:
        return None

    value = value.strip()

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            continue

    return None


def extract_date_from_uswitch_url(url: str) -> str | None:
    match = re.search(r"/media-centre/(\d{4})/(\d{2})/", url)
    if not match:
        return None

    year, month = match.groups()

    try:
        dt = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def is_probable_asset(url: str) -> bool:
    lower = url.lower()
    asset_extensions = (
        ".css", ".js", ".json", ".xml", ".png", ".jpg", ".jpeg",
        ".gif", ".svg", ".webp", ".woff", ".woff2", ".ttf", ".ico",
        ".pdf", ".mp4"
    )
    return lower.endswith(asset_extensions) or "/wp-content/" in lower


def is_valid_article_url(brand_key: str, url: str) -> bool:
    lower = url.lower()

    if is_probable_asset(lower):
        return False

    blocked_fragments = [
        "/tag/",
        "/category/",
        "/author/",
        "/page/",
        "/feed/",
        "/wp-content/",
        "/wp-json/",
    ]
    if any(fragment in lower for fragment in blocked_fragments):
        return False

    if brand_key == "vodafone":
        if lower.rstrip("/") == "https://www.vodafone.co.uk/newscentre/press-release":
            return False

    if brand_key == "bt":
        blocked_bt = [
            "https://newsroom.bt.com/",
            "https://newsroom.bt.com/?h=1&d=excludehomepage",
            "https://newsroom.bt.com/archive/",
        ]
        if lower.rstrip("/") in [u.rstrip("/") for u in blocked_bt]:
            return False

    if brand_key == "uswitch":
        if "/media-centre/category/" in lower:
            return False
        if lower.rstrip("/") in [
            "https://www.uswitch.com/media-centre",
            "https://www.uswitch.com/media-centre/category/broadband",
            "https://www.uswitch.com/media-centre/category/mobiles",
        ]:
            return False

    return True


def build_feed(key: str) -> dict:
    cfg = APPROVED[key]

    if key == "sky":
        items = extract_sky_api_items(cfg["listing_urls"][0])
        items = [
            item for item in items
            if should_keep_item(key, item["title"], item["url"])
        ]

        dated = [item for item in items if item.get("publish_datetime")]
        undated = [item for item in items if not item.get("publish_datetime")]

        dated.sort(key=lambda item: item["publish_datetime"], reverse=True)
        final = (dated + undated)[:10]

        return {
            "status": "ok",
            "brand": cfg["brand"],
            "group": cfg["group"],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "items": final,
        }

    if key == "comparethemarket":
        items = []
        for listing_url in cfg["listing_urls"]:
            try:
                listing_html = fetch(listing_url)
                print("comparethemarket html length:", len(listing_html))
                print("comparethemarket has recent section:", "Recent press releases" in listing_html)
                print("comparethemarket page title match:", "<title>Media contacts | Compare the Market</title>" in listing_html)
                print("comparethemarket first 500 chars:", listing_html[:500])
                listing_items = extract_comparethemarket_listing_items(listing_html, listing_url)
                items.extend(listing_items)
            except Exception:
                continue

        seen = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)

        print("comparethemarket extracted:", len(deduped))
        for item in deduped[:10]:
            print("comparethemarket item:", item["title"], "|", item["url"])

        deduped = [
            item for item in deduped
            if should_keep_item(key, item["title"], item["url"])
        ]

        final = deduped[:10]

        return {
            "status": "ok",
            "brand": cfg["brand"],
            "group": cfg["group"],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "items": final,
        }

    if key == "uswitch":
        items = []
        for listing_url in cfg["listing_urls"]:
            try:
                listing_html = fetch(listing_url)
                listing_items = extract_uswitch_listing_items(listing_html, listing_url)
                items.extend(listing_items[:20])
            except Exception:
                continue

        seen = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)

        deduped = [
            item for item in deduped
            if should_keep_item(key, item["title"], item["url"])
        ]

        dated = [item for item in deduped if item.get("publish_datetime")]
        undated = [item for item in deduped if not item.get("publish_datetime")]

        dated.sort(key=lambda item: item["publish_datetime"], reverse=True)
        final = (dated + undated)[:10]

        return {
            "status": "ok",
            "brand": cfg["brand"],
            "group": cfg["group"],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "items": final,
        }

    candidate_urls = []
    for listing_url in cfg["listing_urls"]:
        try:
            listing_html = fetch(listing_url)
            if key == "vodafone":
                links = extract_vodafone_press_release_links(listing_html, listing_url)
            elif key == "bt":
                links = extract_bt_article_links(listing_html, listing_url)
            else:
                links = extract_links(listing_html, listing_url, cfg["allowed_domains"])

            candidate_urls.extend(links[:40])
        except Exception:
            continue

    seen = set()
    deduped_candidates = []
    for url in candidate_urls:
        if url not in seen:
            seen.add(url)
            deduped_candidates.append(url)

    items = []
    seen_item_urls = set()

    for url in deduped_candidates[:80]:
        if not is_valid_article_url(key, url):
            continue

        try:
            article_html = fetch(url)
            title = parse_title(article_html) or url
            title = normalise_title(title)
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

    dated = [item for item in items if item.get("publish_datetime")]
    undated = [item for item in items if not item.get("publish_datetime")]

    dated.sort(key=lambda item: item["publish_datetime"], reverse=True)

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
        output = build_feed(key)
        path = f"docs/data/{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Wrote {path} ({len(output['items'])} items)")


if __name__ == "__main__":
    main()
