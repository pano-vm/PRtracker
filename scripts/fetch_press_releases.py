import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from urllib.request import Request, urlopen

from google import genai

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
    "ofcom",
    "price hike",
    "mid-contract price hikes",
]

TOPIC_KEYWORDS = {
    "broadband": [
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
    ],
    "mobile": [
        "mobile",
        "mobiles",
        "phone",
        "phones",
        "mobile phone",
        "sim",
        "sim-only",
        "handset",
        "smartphone",
        "data",
    ],
    "network": [
        "network",
        "connectivity",
        "coverage",
        "4g",
        "5g",
    ],
    "pricing": [
        "price",
        "pricing",
        "price hike",
        "price rises",
        "cost",
        "bill",
        "tariff",
        "deal",
        "deals",
        "bundle",
        "bundles",
        "mid-contract",
    ],
    "regulation": [
        "ofcom",
        "regulation",
        "regulatory",
        "rules",
        "consumer",
        "complaint",
        "complaints",
        "rights",
        "mid-contract",
    ],
    "streaming and TV": [
        "tv",
        "streaming",
        "sport",
        "sports",
        "entertainment",
        "cinema",
    ],
    "partnerships": [
        "partner",
        "partners",
        "partnership",
        "partnerships",
        "collaboration",
        "collaborates",
    ],
    "infrastructure": [
        "infrastructure",
        "rollout",
        "roll-out",
        "expansion",
        "expand",
        "upgrade",
        "build",
        "builds",
        "deployment",
    ],
}

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
    # "comparethemarket": {
    #     "brand": "Compare the Market",
    #     "group": "Affiliates",
    #     "listing_urls": [
    #         "https://www.comparethemarket.com/inside-ctm/media-centre/"
    #     ],
    #     "allowed_domains": {"www.comparethemarket.com"},
    # },
    "moneysavingexpert": {
        "brand": "MoneySavingExpert",
        "group": "Affiliates",
        "listing_urls": [
            "https://www.moneysavingexpert.com/pressoffice/",
            "https://www.moneysavingexpert.com/pressoffice/page/2/",
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def extract_mse_date_from_url(url: str) -> str | None:
    match = re.search(r"/pressoffice/(\d{4})/", url)
    if not match:
        return None

    year = match.group(1)

    try:
        dt = datetime.strptime(f"{year}-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def extract_moneysavingexpert_listing_items(html: str, base: str) -> list[dict]:
    items = []

    matches = re.finditer(
        r'<a[^>]+href=["\'](?P<href>/pressoffice/\d{4}/[^"\']+/?)["\'][^>]*>(?P<title>.*?)</a>',
        html,
        flags=re.I | re.S,
    )

    seen = set()

    for match in matches:
        href = unescape(match.group("href")).strip()
        title_html = match.group("title")

        title = re.sub(r"<[^>]+>", "", title_html)
        title = re.sub(r"\s+", " ", unescape(title)).strip()

        url = strip_tracking(urljoin(base, href)).rstrip("/")

        if not title or url in seen:
            continue
        seen.add(url)

        items.append({
            "title": title,
            "url": url,
            "publish_datetime": extract_mse_date_from_url(url),
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
        ".css",
        ".js",
        ".json",
        ".xml",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".ico",
        ".pdf",
        ".mp4",
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


def detect_topics(title: str) -> list[str]:
    if not title:
        return []

    title_lower = title.lower()
    matched_topics = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in title_lower for keyword in keywords):
            matched_topics.append(topic)

    return matched_topics


def format_topic_list(topics: list[str]) -> str:
    if not topics:
        return ""

    if len(topics) == 1:
        return topics[0]

    if len(topics) == 2:
        return f"{topics[0]} and {topics[1]}"

    return f"{topics[0]}, {topics[1]} and {topics[2]}"


def format_brand_list(brands: list[str]) -> str:
    if not brands:
        return ""

    if len(brands) == 1:
        return brands[0]

    if len(brands) == 2:
        return f"{brands[0]} and {brands[1]}"

    return f"{brands[0]}, {brands[1]} and {brands[2]}"


def dedupe_items_by_title_and_url(all_brand_data: list[dict]) -> list[dict]:
    deduped = []
    seen = set()

    for brand_data in all_brand_data:
        brand = brand_data.get("brand", "")
        group = brand_data.get("group", "")
        for item in brand_data.get("items", []):
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            key = (title.lower(), url.lower())

            if not title or key in seen:
                continue

            seen.add(key)
            deduped.append({
                "brand": brand,
                "group": group,
                "title": title,
                "url": url,
                "publish_datetime": item.get("publish_datetime"),
            })

    return deduped


def generate_overview(all_brand_data: list[dict]) -> dict:
    all_items = dedupe_items_by_title_and_url(all_brand_data)

    topic_counts = Counter()
    telecom_brand_counts = Counter()
    affiliate_topic_counts = Counter()
    topic_brand_counts = defaultdict(Counter)

    for item in all_items:
        brand = item["brand"]
        group = item["group"]
        title = item["title"]

        matched_topics = detect_topics(title)
        if not matched_topics:
            continue

        if group == "Telecoms":
            telecom_brand_counts[brand] += 1

        for topic in matched_topics:
            topic_counts[topic] += 1
            topic_brand_counts[topic][brand] += 1

            if group == "Affiliates":
                affiliate_topic_counts[topic] += 1

    top_topics = [topic for topic, _ in topic_counts.most_common(3)]
    top_telecom_brands = [brand for brand, _ in telecom_brand_counts.most_common(2)]

    summary_parts = []

    if top_topics:
        summary_parts.append(
            f"Recent telecom news is focused on {format_topic_list(top_topics)}."
        )
    else:
        summary_parts.append(
            "Recent telecom announcements span product updates, network developments and consumer-facing news across major UK brands."
        )

    if top_telecom_brands:
        strongest_brand_topic = None
        for topic in top_topics:
            if topic_brand_counts[topic]:
                strongest_brand_topic = topic
                break

        if strongest_brand_topic in {"broadband", "network", "infrastructure"}:
            summary_parts.append(
                f"{format_brand_list(top_telecom_brands)} are leading network and infrastructure-related announcements."
            )
        elif strongest_brand_topic in {"mobile", "pricing"}:
            summary_parts.append(
                f"{format_brand_list(top_telecom_brands)} are leading mobile and consumer offer announcements."
            )
        else:
            summary_parts.append(
                f"{format_brand_list(top_telecom_brands)} are among the most active brands in the current update."
            )

    if affiliate_topic_counts:
        top_affiliate_topic, _ = affiliate_topic_counts.most_common(1)[0]

        if top_affiliate_topic == "regulation":
            summary_parts.append(
                "Affiliate coverage is focused on regulation and consumer rights."
            )
        elif top_affiliate_topic == "pricing":
            summary_parts.append(
                "Affiliate coverage is focused on pricing, deals and consumer-facing changes."
            )
        else:
            summary_parts.append(
                f"Affiliate coverage is also highlighting {top_affiliate_topic}."
            )

    summary = " ".join(summary_parts).strip()

    return {
        "generated_at": utc_now_iso(),
        "summary": summary,
    }

def build_topic_trends(all_brand_data: list[dict]) -> list[dict]:
    topic_counts = Counter()

    for brand_data in all_brand_data:
        group = brand_data.get("group", "")
        items = brand_data.get("items", []) or []

        if group != "Telecoms":
            continue

        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            matched_topics = detect_topics(title)
            for topic in matched_topics:
                topic_counts[topic] += 1

    trends = [
        {"topic": topic, "count": count}
        for topic, count in topic_counts.most_common(6)
    ]

    return trends

def build_competitor_momentum(all_brand_data: list[dict]) -> list[dict]:
    momentum = []
    now = datetime.now(timezone.utc)
    window_days = 30

    for brand_data in all_brand_data:
        brand = brand_data.get("brand", "")
        group = brand_data.get("group", "")
        items = brand_data.get("items", []) or []

        if group != "Telecoms":
            continue

        recent_count = 0

        for item in items:
            publish_datetime = item.get("publish_datetime")
            if not publish_datetime:
                continue

            try:
                published = datetime.fromisoformat(publish_datetime.replace("Z", "+00:00"))
                age_days = (now - published).days

                if age_days <= window_days:
                    recent_count += 1
            except Exception:
                continue

        momentum.append({
            "brand": brand,
            "count": recent_count,
        })

    momentum.sort(key=lambda item: item["count"], reverse=True)
    return momentum


def generate_ai_overview(all_brand_data: list[dict]) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        fallback = generate_overview(all_brand_data)
        fallback["signals"] = []
        fallback["momentum"] = build_competitor_momentum(all_brand_data)
        fallback["topic_trends"] = build_topic_trends(all_brand_data)
        return fallback

    all_items = dedupe_items_by_title_and_url(all_brand_data)

    if not all_items:
        return {
            "generated_at": utc_now_iso(),
            "summary": "No recent telecom press releases were available for summarisation.",
            "signals": [],
            "momentum": build_competitor_momentum(all_brand_data),
            "topic_trends": build_topic_trends(all_brand_data),
        }

    lines = []
    for item in all_items[:80]:
        brand = item.get("brand", "Unknown brand")
        title = (item.get("title") or "").strip()
        if title:
            safe_title = title.replace("\n", " ").strip()
            lines.append(f"Brand: {brand} | Headline: {safe_title[:220]}")

    prompt = (
        "You are analysing telecom press releases for Virgin Media O2's competitive intelligence dashboard.\n\n"
        "Virgin Media O2 is our company. All other telecom brands should be treated as competitors.\n\n"
        "Return valid JSON only with this exact structure:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "signals": [\n'
        "    {\n"
        '      "brand": "string",\n'
        '      "type": "string",\n'
        '      "headline": "string",\n'
        '      "impact": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Instructions:\n"
        "- Write a concise 3 sentence summary.\n"
        "- Focus on competitor developments, market themes, risks and opportunities for Virgin Media O2.\n"
        "- Treat Vodafone, BT, EE, Three and Sky as competitors.\n"
        "- Treat MoneySavingExpert and uSwitch as affiliate or consumer/regulatory commentary.\n"
        "- Select the 3 most strategically relevant competitor signals.\n"
        "- Each signal must include brand, type, headline and impact.\n"
        "- 'type' should be something like Network investment, Pricing, Partnership, Regulation, Product launch or Consumer sentiment.\n"
        "- 'impact' should explain why it matters for Virgin Media O2 in one sentence.\n"
        "- Do not include markdown.\n"
        "- Do not include code fences.\n"
        "- Output valid JSON only.\n\n"
        "Press release headlines:\n"
        + "\n".join(lines)
    )

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )

        raw_text = (response.text or "").strip()

        if not raw_text:
            fallback = generate_overview(all_brand_data)
            fallback["signals"] = []
            fallback["momentum"] = build_competitor_momentum(all_brand_data)
            fallback["topic_trends"] = build_topic_trends(all_brand_data)
            return fallback

        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(cleaned)

        summary = (parsed.get("summary") or "").strip()
        signals = parsed.get("signals") or []

        if not summary:
            fallback = generate_overview(all_brand_data)
            fallback["signals"] = []
            fallback["momentum"] = build_competitor_momentum(all_brand_data)
            fallback["topic_trends"] = build_topic_trends(all_brand_data)
            return fallback

        cleaned_signals = []
        for signal in signals[:3]:
            brand = str(signal.get("brand", "")).strip()
            signal_type = str(signal.get("type", "")).strip()
            headline = str(signal.get("headline", "")).strip()
            impact = str(signal.get("impact", "")).strip()

            if not headline:
                continue

            cleaned_signals.append({
                "brand": brand or "Unknown",
                "type": signal_type or "Strategic update",
                "headline": headline,
                "impact": impact or "This development may have competitive implications for Virgin Media O2.",
            })

        return {
            "generated_at": utc_now_iso(),
            "summary": summary,
            "signals": cleaned_signals,
            "momentum": build_competitor_momentum(all_brand_data),
            "topic_trends": build_topic_trends(all_brand_data),
        }

    except Exception as e:
        print("Gemini overview generation failed:", repr(e))
        fallback = generate_overview(all_brand_data)
        fallback["signals"] = []
        fallback["momentum"] = build_competitor_momentum(all_brand_data)
        fallback["topic_trends"] = build_topic_trends(all_brand_data)
        return fallback


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
            "generated_at": utc_now_iso(),
            "items": final,
        }

    if key == "moneysavingexpert":
        items = []

        for listing_url in cfg["listing_urls"]:
            try:
                listing_html = fetch(listing_url)

                print(f"\n[MSE] listing URL: {listing_url}")
                print(f"[MSE] HTML length: {len(listing_html)}")
                print(f"[MSE] contains 'Press Office': {'Press Office' in listing_html}")
                print(f"[MSE] contains '/pressoffice/202': {'/pressoffice/202' in listing_html}")
                print(f"[MSE] contains 'Telecoms Consumer Charter': {'Telecoms Consumer Charter' in listing_html}")
                print(f"[MSE] contains 'O2 price rise': {'O2 price rise' in listing_html}")
                print(f"[MSE] contains 'mid-contract price hikes': {'mid-contract price hikes' in listing_html}")

                start = listing_html.find("Press Office")
                if start != -1:
                    print("[MSE] snippet around Press Office:")
                    print(listing_html[start:start+2000])
                else:
                    print("[MSE] 'Press Office' not found in HTML")

                listing_items = extract_moneysavingexpert_listing_items(listing_html, listing_url)

                print(f"[MSE] extracted count: {len(listing_items)}")
                print("[MSE] sample extracted:", [
                    {
                        "title": item["title"],
                        "url": item["url"],
                        "publish_datetime": item["publish_datetime"],
                    }
                    for item in listing_items[:5]
                ])

                items.extend(listing_items)

            except Exception as e:
                print("[MSE] fetch error:", repr(e))
                continue

        seen = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)

        print(f"[MSE] deduped before filter: {len(deduped)}")
        print("[MSE] deduped titles:", [item["title"] for item in deduped[:10]])

        # TEMP DEBUG - bypass telecom filter for one run
        kept = deduped

        print(f"[MSE] kept after telecom filter: {len(kept)}")
        print("[MSE] kept titles:", [item["title"] for item in kept[:10]])

        dated = [item for item in kept if item.get("publish_datetime")]
        undated = [item for item in kept if not item.get("publish_datetime")]

        dated.sort(key=lambda item: item["publish_datetime"], reverse=True)
        final = (dated + undated)[:10]

        print(f"[MSE] final items written: {len(final)}")

        return {
            "status": "ok",
            "brand": cfg["brand"],
            "group": cfg["group"],
            "generated_at": utc_now_iso(),
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
            "generated_at": utc_now_iso(),
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
        "generated_at": utc_now_iso(),
        "items": final,
    }


def main():
    all_outputs = []

    for key in APPROVED.keys():
        output = build_feed(key)
        all_outputs.append(output)

        path = f"docs/data/{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"Wrote {path} ({len(output['items'])} items)")

    overview = generate_ai_overview(all_outputs)
    overview_path = "docs/data/overview.json"

    with open(overview_path, "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print(f"Wrote {overview_path}")


if __name__ == "__main__":
    main()
